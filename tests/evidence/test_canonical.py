"""Canonicalization: the leaf table, determinism, and collection ordering.

Covers T7, T9, T10 and T11, plus the leaf-table conformance Amendment 1 made
possible.

T9/T10 and T11 are the two halves of one idea, and they pull in opposite
directions on purpose. Set-semantic collections must be **permutation
invariant** — a digest that moves when a caller reorders a list is a digest that
changes when nothing semantic did. Order-semantic collections must be
**sensitive to their ordinal and insensitive to their array position** — a
sequence is a claim, but where it sits in an array is not.

Getting either one wrong is the defect AI-04 paid for twice.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
import sys

import pytest

from plugins.evidence import (
    FIELD_TABLE,
    Inclusion,
    canonical_json,
    content_projection,
    record_projection,
    resolver_paths,
)
from plugins.evidence.errors import DuplicateOrdinal, RecordMalformed

pytestmark = pytest.mark.layer1

#: Every path the §15.2 table marks excluded from `content_digest`. Derived from
#: the table by the test rather than restated, so the two cannot drift.
EXPECTED_CONTENT_EXCLUSIONS = frozenset(
    {
        "evidence_id",
        "producer_version",
        "experiment_id",
        "recorded_at",
        "payload.tool_calls[].result_classification",
        "artifacts.items[].role",
        "artifacts.items[].artifact_ref",
        "record_digest",
    }
)


class TestTheLeafTableIsAuthoritative:
    """§15.2 — the table is the single source of truth for digest behaviour."""

    def test_the_table_has_fifty_two_leaves(self):
        assert len(FIELD_TABLE) == 52

    def test_every_table_path_has_a_resolver(self):
        assert resolver_paths() == frozenset(row.path for row in FIELD_TABLE)

    def test_paths_are_unique(self):
        paths = [row.path for row in FIELD_TABLE]
        assert len(paths) == len(set(paths))

    def test_the_content_exclusions_are_exactly_the_frozen_set(self):
        """§16's exclusion list, read off the table rather than restated."""
        excluded = {
            row.path for row in FIELD_TABLE if row.content is Inclusion.EXCLUDED
        }
        assert excluded == EXPECTED_CONTENT_EXCLUSIONS

    def test_the_two_deferred_leaves_are_absent_from_both_digests(self):
        """§13.1 and §11 require `role` and `result_classification` absent in v1."""
        for path in (
            "artifacts.items[].role",
            "payload.tool_calls[].result_classification",
        ):
            row = next(r for r in FIELD_TABLE if r.path == path)
            assert row.content is Inclusion.EXCLUDED
            assert row.record is Inclusion.EXCLUDED

    def test_no_container_row_survives(self):
        """A container row is what could not express a nested exclusion."""
        containers = {"payload", "references.context", "artifacts.items"}
        assert not [r for r in FIELD_TABLE if r.path in containers]

    def test_artifact_ref_is_the_only_locator(self):
        locators = [r.path for r in FIELD_TABLE if r.role.value == "locator"]
        assert locators == ["artifacts.items[].artifact_ref"]

    def test_observed_at_is_per_kind(self):
        row = next(r for r in FIELD_TABLE if r.path == "observed_at")
        assert row.content is Inclusion.PER_KIND


class TestT7Determinism:
    """T7 — same semantics, same content digest, independently of this process."""

    def test_two_independent_parses_agree(self, record_factory, build):
        a, b = build(record_factory()), build(record_factory())
        assert a.integrity.content_digest == b.integrity.content_digest

    def test_the_digest_recomputes_from_the_canonical_string(self, record_factory, build):
        record = build(record_factory())
        canonical = canonical_json(content_projection(record))
        assert record.integrity.content_digest == hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    def test_the_record_digest_recomputes_from_the_canonical_string(self, record_factory, build):
        record = build(record_factory())
        canonical = canonical_json(record_projection(record))
        assert record.integrity.record_digest == hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    def test_a_separate_interpreter_reaches_the_same_value(self, record_factory, build):
        """The cross-process half of T7.

        Scoped to this environment: a spawned process can fail on handle
        inheritance before any assertion runs, which is a limitation of the host
        rather than a determinism result, so it is reported as a skip.
        """
        record = build(record_factory())
        program = (
            "import hashlib,json,sys;"
            "payload=json.loads(sys.stdin.read());"
            "canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,"
            "separators=(',',':'),allow_nan=False);"
            "print(hashlib.sha256(canonical.encode('utf-8')).hexdigest())"
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-c", program],
                input=json.dumps(content_projection(record)),
                capture_output=True, text=True, timeout=60,
            )
        except OSError as exc:  # pragma: no cover - environment limitation
            pytest.skip(f"cannot spawn an interpreter here: {exc}")
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == record.integrity.content_digest


class TestT9T10SetSemanticCollections:
    """T9/T10 — permutation invariance, asserted for **every** set collection."""

    @staticmethod
    def _permutations(items):
        return list(itertools.permutations(items))

    def test_context_references_are_permutation_invariant(self, record_factory, build):
        from tests.evidence.conftest import make_context_ref

        items = [
            make_context_ref(subject="git.head", value="PASS"),
            make_context_ref(subject="git.branch", value="main"),
            make_context_ref(subject="git.working_tree", value="CLEAN"),
        ]
        digests = {
            build(record_factory(references={"context": list(ordering)}))
            .integrity.content_digest
            for ordering in self._permutations(items)
        }
        assert len(digests) == 1, "the context collection is SET-semantic (§15.4)"

    def test_decision_references_are_permutation_invariant(self, record_factory, build):
        refs = ["ev-" + s.rjust(16, "0") for s in ("1", "2", "3")]
        items = [{"record_ref": r} for r in refs]
        digests = {
            build(record_factory(references={"decisions": list(ordering)}))
            .integrity.content_digest
            for ordering in self._permutations(items)
        }
        assert len(digests) == 1

    def test_supersede_references_are_permutation_invariant(self, record_factory, build):
        items = [
            {"record_ref": "ev-" + s.rjust(16, "0"), "correction_reason": reason}
            for s, reason in (("1", "one"), ("2", "two"), ("3", "three"))
        ]
        digests = {
            build(record_factory(references={"supersedes": list(ordering)}))
            .integrity.content_digest
            for ordering in self._permutations(items)
        }
        assert len(digests) == 1

    def test_artifacts_are_permutation_invariant(self, record_factory, build):
        from tests.evidence.conftest import make_artifact

        items = [
            make_artifact(artifact_digest="a" * 64, artifact_ref="loc-1"),
            make_artifact(artifact_digest="b" * 64, artifact_ref="loc-2"),
            make_artifact(artifact_digest="c" * 64, artifact_ref="loc-3"),
        ]
        digests = {
            build(record_factory(artifacts={"items": list(ordering)}))
            .integrity.content_digest
            for ordering in self._permutations(items)
        }
        assert len(digests) == 1, "the artifact collection is SET-semantic (§15.4)"

    def test_reasons_are_permutation_invariant(self, decision_factory, build):
        """Amendment 1 declared `payload.reasons[]` SET. It was ORDER before."""
        reasons = ["alpha", "beta", "gamma"]
        digests = {
            build(decision_factory(payload={
                "decision": "ALLOW", "reason_code": "R",
                "input_digest": "b" * 64, "reasons": list(ordering),
            })).integrity.content_digest
            for ordering in self._permutations(reasons)
        }
        assert len(digests) == 1

    def test_ordering_never_uses_the_locator(self, record_factory, build):
        """§13.2 — `artifact_ref` is not an ordering input."""
        from tests.evidence.conftest import make_artifact

        left = build(record_factory(artifacts={"items": [
            make_artifact(artifact_digest="a" * 64, artifact_ref="loc-1"),
            make_artifact(artifact_digest="b" * 64, artifact_ref="loc-2"),
        ]}))
        right = build(record_factory(artifacts={"items": [
            make_artifact(artifact_digest="b" * 64, artifact_ref="loc-9"),
            make_artifact(artifact_digest="a" * 64, artifact_ref="loc-8"),
        ]}))
        assert left.integrity.content_digest == right.integrity.content_digest

    def test_a_genuinely_different_set_does_change_the_digest(self, record_factory, build):
        """The control: permutation invariance must not mean insensitivity."""
        from tests.evidence.conftest import make_context_ref

        a = build(record_factory(references={
            "context": [make_context_ref(value="PASS")]}))
        b = build(record_factory(references={
            "context": [make_context_ref(value="FAIL")]}))
        assert a.integrity.content_digest != b.integrity.content_digest


class TestT11OrderSemanticCollections:
    """T11 — ordinal decides, array position does not."""

    @staticmethod
    def _execution(actor_type, calls):
        return {
            "schema_version": 1,
            "kind": "EXECUTION",
            "provenance": {
                "producer": "ai-06", "producer_version": "1.0.0",
                "producer_type": "service",
                "actor": {"id": "ai-06", "type": actor_type},
                "workspace_id": "ws-1",
            },
            "payload": {"tool_calls[]": calls},
        }

    def test_array_order_does_not_matter_when_ordinals_are_kept(self, build):
        calls = [
            {"ordinal": 0, "what_ran": "git status", "status": "PASS"},
            {"ordinal": 1, "what_ran": "pytest", "status": "PASS"},
            {"ordinal": 2, "what_ran": "git diff", "status": "PASS"},
        ]
        canonical = build(self._execution("service", calls)).integrity.content_digest
        for ordering in itertools.permutations(calls):
            assert build(
                self._execution("service", list(ordering))
            ).integrity.content_digest == canonical

    def test_changing_an_ordinal_changes_the_digest(self, build):
        original = [
            {"ordinal": 0, "what_ran": "a", "status": "PASS"},
            {"ordinal": 1, "what_ran": "b", "status": "PASS"},
        ]
        swapped = [
            {"ordinal": 1, "what_ran": "a", "status": "PASS"},
            {"ordinal": 0, "what_ran": "b", "status": "PASS"},
        ]
        assert build(
            self._execution("service", original)
        ).integrity.content_digest != build(
            self._execution("service", swapped)
        ).integrity.content_digest

    def test_the_ordinal_survives_into_the_projection(self, build):
        record = build(self._execution("service", [
            {"ordinal": 1, "what_ran": "b", "status": "PASS"},
            {"ordinal": 0, "what_ran": "a", "status": "PASS"},
        ]))
        ordinals = [
            c["ordinal"] for c in content_projection(record)["payload"]["tool_calls[]"]
        ]
        assert ordinals == [0, 1], "the projection is emitted in ordinal order"

    def test_a_duplicate_ordinal_is_rejected(self, build):
        """§11.1. A duplicate leaves the ordering indeterminate."""
        with pytest.raises(DuplicateOrdinal):
            build(self._execution("service", [
                {"ordinal": 0, "what_ran": "a", "status": "PASS"},
                {"ordinal": 0, "what_ran": "b", "status": "PASS"},
            ]))

    def test_a_non_integer_ordinal_is_rejected(self, build):
        with pytest.raises(RecordMalformed):
            build(self._execution("service", [
                {"ordinal": "0", "what_ran": "a", "status": "PASS"}]))

    def test_a_negative_ordinal_is_rejected(self, build):
        with pytest.raises(RecordMalformed):
            build(self._execution("service", [
                {"ordinal": -1, "what_ran": "a", "status": "PASS"}]))


class TestCanonicalJsonPrimitive:
    """§15 — the rules AI-04 §20.2 freezes, imported rather than restated."""

    def test_keys_are_sorted_and_whitespace_is_absent(self):
        assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    def test_enum_values_render_as_their_canonical_string(self):
        from plugins.evidence import EvidenceKind

        assert canonical_json(EvidenceKind.OBSERVATION) == '"OBSERVATION"'

    def test_a_bare_set_is_refused_rather_than_guessed_at(self):
        with pytest.raises(TypeError):
            canonical_json({"items": {1, 2, 3}})

    def test_canonicalization_does_not_lowercase_anything(self):
        """§15 — canonicalization represents; it does not repair."""
        assert canonical_json({"d": "ABC"}) == '{"d":"ABC"}'
