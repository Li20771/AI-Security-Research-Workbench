"""AI-10 §15, §16, §17, §18 — the boundaries, and the gate that holds them.

A gate that passes because there is nothing to check is not a gate. The
non-vacuity tests here run the AI-10 Layer 0 check against a scratch tree
carrying each violation in turn, so the rule is proven to fire rather than
trusted to.
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys

import pytest

from agents.request import AgentExecutionRequest

from tests.review.conftest import module_names, review_modules

pytestmark = pytest.mark.layer2

POLICY = "scripts/ci/layer0_policy.py"


def _policy_module():
    spec = importlib.util.spec_from_file_location("layer0_policy_under_test", POLICY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_gate_on(tmp_path, files: dict[str, str], *, dirs: tuple[str, ...] = ()) -> list[str]:
    """Run the AI-10 gate against a scratch tree.

    The real repository root stays importable, so the behavioural half of the
    gate still reads the real vocabularies; the structural half reads the
    scratch tree, which is where the injected violation lives.
    """
    module = _policy_module()
    scratch = tmp_path / "repo"
    (scratch / "review").mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        (scratch / "review" / name).write_text(source, encoding="utf-8")
    for relative in dirs:
        (scratch / relative).mkdir(parents=True, exist_ok=True)

    original = module.ROOT
    module.ROOT = scratch
    added = str(scratch)
    try:
        return module.check_ai10_review_layer()
    finally:
        module.ROOT = original
        if added in sys.path:
            sys.path.remove(added)


class TestTheGate:
    def test_it_is_registered_in_the_layer_zero_script(self):
        source = pathlib.Path(POLICY).read_text(encoding="utf-8")
        assert "def check_ai10_review_layer()" in source
        assert '"review layer core-service boundary"' in source

    def test_it_runs_green_on_the_real_tree(self):
        assert _policy_module().check_ai10_review_layer() == []

    def test_a_missing_review_directory_is_a_problem(self, tmp_path):
        module = _policy_module()
        scratch = tmp_path / "repo"
        scratch.mkdir()
        original = module.ROOT
        module.ROOT = scratch
        try:
            problems = module.check_ai10_review_layer()
        finally:
            module.ROOT = original
        assert problems and "review/" in problems[0]

    def test_a_plugin_layer_is_a_problem(self, tmp_path):
        problems = _run_gate_on(
            tmp_path, {"ok.py": ""}, dirs=("plugins/review",)
        )
        assert any("plugins/review" in problem for problem in problems)

    def test_a_package_initializer_is_a_problem(self, tmp_path):
        problems = _run_gate_on(tmp_path, {"__init__.py": ""})
        assert any("__init__.py" in problem for problem in problems)

    def test_a_reverse_dependency_is_a_problem(self, tmp_path):
        problems = _run_gate_on(tmp_path, {"ok.py": ""}, dirs=("agents",))
        scratch_agents = tmp_path / "repo" / "agents"
        (scratch_agents / "leaky.py").write_text(
            "import review.material\n", encoding="utf-8"
        )
        module = _policy_module()
        original = module.ROOT
        module.ROOT = tmp_path / "repo"
        added = str(module.ROOT)
        try:
            problems = module.check_ai10_review_layer()
        finally:
            module.ROOT = original
            if added in sys.path:
                sys.path.remove(added)
        assert any("must not depend on the review layer" in problem for problem in problems)

    @pytest.mark.parametrize(
        "source,needle",
        [
            ("import providers\n", "providers"),
            ("import routing\n", "routing"),
            ("import tools\n", "tools"),
            ("import subprocess\n", "subprocess"),
            ("import socket\n", "socket"),
            ("import os\n", "os"),
            ("import pathlib\n", "pathlib"),
            ("import random\n", "random"),
            ("from plugins.guard import evaluate\n", "plugins.guard"),
            ("from plugins.evidence import EvidenceRecord\n", "plugins.evidence"),
            ("VALUE = 'PASS'\n", "PASS"),
            ("VALUE = 'VERIFIED'\n", "VERIFIED"),
            ("class LeakyAdapter:\n    pass\n", "LeakyAdapter"),
            ("class LeakyTransport:\n    pass\n", "LeakyTransport"),
            ("def run(policy):\n    return policy\n", "policy"),
            ("def run(evaluator):\n    return evaluator\n", "evaluator"),
            ("open('x')\n", "open"),
            ("VALUE = 'SecurityLab/'\n", "SecurityLab/"),
            ("eval('1')\n", "eval"),
        ],
    )
    def test_a_violation_is_caught(self, tmp_path, source, needle):
        problems = _run_gate_on(tmp_path, {"leaky.py": source})
        assert problems, f"the gate reported nothing for {source!r}"
        assert any(needle in problem for problem in problems), problems


class TestTheAmendmentTwoAssertionsAreNotVacuous:
    """§5.4. The gate must catch a drift in the third vocabulary, not just read it."""

    def test_a_fourth_status_member_is_caught(self, monkeypatch):
        import enum

        import review.vocabulary as vocabulary

        module = _policy_module()

        class Extended(enum.StrEnum):
            NOT_APPLICABLE = "NOT_APPLICABLE"
            UNCHECKED = "UNCHECKED"
            OBSERVED = "OBSERVED"
            INDEPENDENT = "INDEPENDENT"

        monkeypatch.setattr(vocabulary, "IndependenceObservationStatus", Extended)
        problems = module.check_ai10_review_layer()
        assert any("IndependenceObservationStatus" in problem for problem in problems), problems

    def test_a_case_without_the_field_is_caught(self, monkeypatch):
        import dataclasses

        import review.case as case_module

        module = _policy_module()

        @dataclasses.dataclass(frozen=True, slots=True)
        class Bare:
            review_case_id: str = "rc-1"

        monkeypatch.setattr(case_module, "ReviewCase", Bare)
        problems = module.check_ai10_review_layer()
        assert any("independence_status" in problem for problem in problems), problems


class TestIdentity:
    def test_review_is_a_directory_at_the_root(self):
        assert pathlib.Path("review").is_dir()

    def test_it_is_not_a_plugin_package(self):
        for forbidden in ("plugins/review", "agents/review", "routing/review", "integrations/review"):
            assert not pathlib.Path(forbidden).exists(), forbidden

    def test_it_is_reached_as_a_namespace_package(self):
        assert not pathlib.Path("review/__init__.py").exists()


class TestDependencies:
    @pytest.mark.parametrize(
        "forbidden",
        [
            "providers",
            "routing",
            "tools",
            "plugins.guard",
            "plugins.evidence",
            "subprocess",
            "socket",
            "os",
            "pathlib",
        ],
    )
    def test_no_module_imports_it(self, forbidden):
        for path in review_modules():
            names = module_names(path)
            assert not any(
                name == forbidden or name.startswith(forbidden + ".")
                for name in names
            ), f"{path}: {forbidden}"

    def test_only_the_allowed_plugin_surfaces_are_reached(self):
        for path in review_modules():
            for name in module_names(path):
                if name.startswith("plugins."):
                    assert name.startswith(
                        ("plugins.security_tools", "plugins.context")
                    ), f"{path}: {name}"

    def test_the_import_graph_of_review_is_the_frozen_one(self):
        """The whole package's first-party imports, as one auditable set."""
        allowed = {
            "agents.independence",
            "agents.result",
            "agents.vocabulary",
            "review",
            "plugins.security_tools",
            "review.case",
            "review.claim",
            "review.comparison",
            "review.decision",
            "review.digest",
            "review.errors",
            "review.finding",
            "review.independence",
            "review.material",
            "review.validation",
            "review.verification",
            "review.vocabulary",
        }
        found: set[str] = set()
        for path in review_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if not node.module.startswith("__"):
                        found.add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if not alias.name.startswith("__"):
                            found.add(alias.name)
        first_party = {
            name
            for name in found
            if name.split(".")[0] in {"agents", "plugins", "providers", "review", "routing", "tools"}
        }
        assert first_party <= allowed, first_party - allowed


class TestNoAgentInputInjection:
    def test_review_never_touches_an_execution_request(self):
        for path in review_modules():
            names = module_names(path)
            assert "AgentExecutionRequest" not in names, path
            assert "agents.request" not in names, path

    def test_the_request_has_no_field_for_review_material(self):
        fields = {field.name for field in AgentExecutionRequest.__dataclass_fields__.values()}
        for forbidden in ("material", "review", "review_material", "claims", "finding"):
            assert forbidden not in fields

    def test_review_does_not_import_the_runtime(self):
        for path in review_modules():
            names = module_names(path)
            assert "agents.runtime" not in names, path
            assert "execute" not in names, path


class TestNoEvidenceIsWritten:
    def test_no_module_reaches_the_evidence_plugin(self):
        for path in review_modules():
            names = module_names(path)
            assert not any(name.startswith("plugins.evidence") for name in names), path

    def test_no_module_names_an_evidence_type(self):
        for path in review_modules():
            names = module_names(path)
            for forbidden in (
                "EvidenceRecord",
                "admit_to_store",
                "evidence_id",
                "StagedEvidenceStore",
            ):
                assert forbidden not in names, f"{path}: {forbidden}"

    def test_no_producer_token_is_borrowed(self):
        for path in review_modules():
            source = path.read_text(encoding="utf-8")
            assert "ai-04" not in source, path
            assert "ai-06" not in source, path


class TestNoObservationIsFabricated:
    def test_no_module_constructs_a_verification_observation(self):
        """An observation exists because a caller reported one.

        The only construction of `VerificationObservation` in the package is its
        own class definition; nothing in review/ produces one, so there is no
        path that announces a verification that did not run.
        """
        for path in review_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"VerificationObservation", "VerificationRequest"}
            ]
            if path.name == "verification.py":
                # The module defines the types; it still never calls them.
                assert calls == [], path
            else:
                assert calls == [], f"{path} constructs {calls}"

    def test_no_module_constructs_a_guard_decision(self):
        for path in review_modules():
            names = module_names(path)
            assert "GuardDecision" not in names, path

    def test_no_module_can_report_an_execution(self):
        for path in review_modules():
            names = module_names(path)
            for forbidden in ("ToolResult", "invoke", "execute", "run_execution", "dispatch"):
                assert forbidden not in names, f"{path}: {forbidden}"

    def test_no_module_writes_anywhere(self):
        """No log, no console, no file. Material content has nowhere to go."""
        for path in review_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names = module_names(path)
            assert "logging" not in names, path
            calls = {
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            assert "print" not in calls, path
            assert "open" not in calls, path


class TestNoPersistence:
    def test_no_module_opens_a_file(self):
        for path in review_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = {
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            assert "open" not in calls, path

    def test_no_module_imports_a_store_or_a_serializer_for_one(self):
        for path in review_modules():
            names = module_names(path)
            for forbidden in ("sqlite3", "pickle", "tempfile", "shutil"):
                assert forbidden not in names, f"{path}: {forbidden}"


class TestNoDirectGuardOrTools:
    def test_no_module_imports_guard(self):
        for path in review_modules():
            names = module_names(path)
            assert "plugins.guard" not in names, path
            assert "GuardRequest" not in names, path
            assert "GuardDecision" not in names, path

    def test_no_module_calls_evaluate(self):
        for path in review_modules():
            names = module_names(path)
            assert "evaluate" not in names, path

    def test_review_holds_no_policy_evaluator_or_registry(self):
        for path in review_modules():
            names = module_names(path)
            for forbidden in ("policy", "evaluator", "registry", "ToolRequest"):
                assert forbidden not in names, f"{path}: {forbidden}"
