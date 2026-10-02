"""AI-10 §8 — AI-08's independence, consumed read-only.

```text
independence  !=  comparison
independence  !=  verification
independence  !=  correctness
```

The tests here hold the seam: AI-10 calls AI-08's predicate, records AI-08's
finding unchanged, and adds nothing to it.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from agents.independence import (
    ExecutionRecord,
    IndependenceFinding,
    structural_independence,
)

from review import independence as review_independence
from review.errors import ProvenanceMismatch

from tests.review.conftest import material_for, run_agent_execution, review_modules

pytestmark = pytest.mark.layer2

INDEPENDENCE_SOURCE = pathlib.Path("review/independence.py")


class TestAlignment:
    def test_an_aligned_declaration_passes(self, pair):
        left_record, _, left, _ = pair
        review_independence.require_aligned_declaration(left, left_record)

    @pytest.mark.parametrize(
        "field,value",
        [
            ("execution_id", "ex-other"),
            ("workspace_id", "ws-other"),
            ("input_digest", "sha256:" + "c" * 64),
        ],
    )
    def test_a_mismatched_field_is_refused(self, pair, field, value):
        left_record, _, left, _ = pair
        mismatched = dataclasses.replace(left, **{field: value})
        with pytest.raises(ProvenanceMismatch) as excinfo:
            review_independence.require_aligned_declaration(mismatched, left_record)
        assert field in str(excinfo.value)

    def test_a_mismatched_agent_is_refused(self, pair, workspace_root):
        left_record, _, left, _ = pair
        from agents.vocabulary import AgentId

        other = material_for(
            run_agent_execution(workspace_root, agent_id=AgentId.CODEX), "m-other"
        )
        mismatched = dataclasses.replace(
            left,
            agent_id=other.agent_id,
            execution_id=other.execution_id,
            input_digest=other.input_digest,
        )
        with pytest.raises(ProvenanceMismatch):
            review_independence.require_aligned_declaration(mismatched, left_record)

    def test_the_refusal_explains_itself(self, pair):
        left_record, _, left, _ = pair
        mismatched = dataclasses.replace(left, execution_id="ex-other")
        with pytest.raises(ProvenanceMismatch) as excinfo:
            review_independence.require_aligned_declaration(mismatched, left_record)
        assert "refused" in str(excinfo.value)


class TestObservation:
    def test_the_observation_is_ai08s_own_finding(self, pair):
        left_record, right_record, _, _ = pair
        finding = review_independence.observe_independence(left_record, right_record)
        assert isinstance(finding, IndependenceFinding)

    def test_it_is_the_same_answer_the_predicate_gives(self, pair):
        left_record, right_record, _, _ = pair
        assert review_independence.observe_independence(
            left_record, right_record
        ).to_mapping() == structural_independence(left_record, right_record).to_mapping()

    def test_it_is_symmetric_like_the_predicate(self, pair):
        left_record, right_record, _, _ = pair
        forward = review_independence.observe_independence(left_record, right_record)
        backward = review_independence.observe_independence(right_record, left_record)
        assert forward.to_mapping() == backward.to_mapping()


class TestNoSecondVocabulary:
    def test_the_finding_type_is_imported_not_redefined(self):
        source = INDEPENDENCE_SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        classes = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        assert classes == []
        functions = [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        assert functions == ["require_aligned_declaration", "observe_independence"]

    def test_no_module_in_review_defines_an_independence_predicate(self):
        forbidden = {
            "structural_independence",
            "IndependenceFinding",
            "ExecutionRecord",
            "I1_IDENTITY_SEPARATION",
            "INDEPENDENCE_CONDITIONS",
        }
        for path in review_modules():
            if path == INDEPENDENCE_SOURCE:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            defined = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.ClassDef, ast.FunctionDef))
            }
            assert not (defined & forbidden), f"{path}: {defined & forbidden}"

    def test_the_finding_carries_only_its_two_condition_labels(self):
        fields = {field.name for field in dataclasses.fields(IndependenceFinding)}
        assert fields == {"satisfied", "violated"}

    def test_an_observation_is_not_converted_into_a_review_finding(self, pair):
        left_record, right_record, _, _ = pair
        finding = review_independence.observe_independence(left_record, right_record)
        # There is no path from an independence finding to a review finding, and
        # the review finding's shape has nothing an independence answer could
        # be stored in.
        from review.finding import ReviewFinding

        fields = {field.name for field in dataclasses.fields(ReviewFinding)}
        assert "independent" not in fields
        assert "satisfied" not in fields
        assert "violated" not in fields
        assert not hasattr(finding, "verdict")


class TestReadOnly:
    def test_review_does_not_modify_the_agent_layer(self):
        """A read-only consumer imports; it does not write back."""
        source = INDEPENDENCE_SOURCE.read_text(encoding="utf-8")
        assert "from agents.independence import" in source
        for forbidden in ("setattr", "monkeypatch", "register", "install"):
            assert forbidden not in source

    def test_the_execution_record_is_untouched_by_an_observation(self, pair):
        left_record, right_record, _, _ = pair
        before = (left_record.result.to_mapping(), right_record.result.to_mapping())
        review_independence.observe_independence(left_record, right_record)
        after = (left_record.result.to_mapping(), right_record.result.to_mapping())
        assert before == after

    def test_the_record_type_is_ai08s(self, pair):
        left_record, _, _, _ = pair
        assert isinstance(left_record, ExecutionRecord)
