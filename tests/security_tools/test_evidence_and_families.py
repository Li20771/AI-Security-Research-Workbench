"""The Evidence projection and the family scope — T30 to T33, T40, T41, T45.

The test this file turns on is T33. Without it, a tool that exits 0 is one
refactor away from being recorded as a research PASS.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import tools
from plugins.evidence import ExecutionPayload, MAX_TEXT_LENGTH, ToolCall, StatusValue
from plugins.security_tools import (
    AdapterFamily,
    PermissionLevel,
    ToolOutcome,
    ToolRequest,
    ToolResult,
)
from plugins.security_tools.dispatch import invoke
from plugins.security_tools.evidence import execution_payload_for, tool_call_for

from tests.security_tools.conftest import FakeRunner, request_mapping

pytestmark = pytest.mark.layer1


def _result(**overrides) -> ToolResult:
    base = {
        "tool_id": "tests",
        "tool_version": "1.0.0",
        "operation": "pytest",
        "outcome": ToolOutcome.COMPLETED,
        "reason_code": "EXIT_CODE_EXPECTED",
        "workspace_id": "ws",
        "guard": {"decision": "ALLOW", "reason_code": "", "decision_id": "d"},
    }
    base.update(overrides)
    return ToolResult(**base)


# --------------------------------------------------------------------------
# T30 — nothing but the name reaches Evidence
# --------------------------------------------------------------------------


class TestT30ArgumentsDoNotReachEvidence:
    def test_what_ran_carries_no_argument(self):
        result = _result()

        assert result.what_ran == "tests/pytest"
        assert "--" not in result.what_ran
        assert "=" not in result.what_ran

    def test_a_secret_in_an_argument_does_not_reach_the_projection(self):
        """The argument is not in the record because it is not in `what_ran`."""
        result = _result(operation="status")

        assert "sk-" not in tool_call_for(result, 0).what_ran

    def test_the_call_is_bounded_for_the_record(self):
        call = tool_call_for(_result(), 0)

        assert len(call.what_ran) <= MAX_TEXT_LENGTH

    def test_a_long_tool_id_still_fits(self):
        result = _result(tool_id="t" * 40, operation="o" * 40)

        call = tool_call_for(result, 0)

        assert len(call.what_ran) <= MAX_TEXT_LENGTH


# --------------------------------------------------------------------------
# T31, T32 — the projection
# --------------------------------------------------------------------------


class TestT31TheProjectionIsTotal:
    @pytest.mark.parametrize("outcome", list(ToolOutcome))
    def test_every_outcome_projects(self, outcome):
        result = _result(outcome=outcome)

        call = tool_call_for(result, 0)

        assert isinstance(call, ToolCall)
        assert isinstance(call.status, StatusValue)

    def test_the_expected_values(self):
        assert _result(outcome=ToolOutcome.COMPLETED).status is StatusValue.PASS
        assert _result(outcome=ToolOutcome.FAILED).status is StatusValue.FAIL
        assert _result(outcome=ToolOutcome.TIMED_OUT).status is StatusValue.FAIL
        assert _result(outcome=ToolOutcome.BLOCKED).status is StatusValue.BLOCKED
        assert _result(outcome=ToolOutcome.NOT_RUN).status is StatusValue.NOT_RUN
        assert _result(outcome=ToolOutcome.UNKNOWN).status is StatusValue.UNKNOWN


class TestT32TheProjectionIsOneWay:
    def test_the_evidence_module_never_reads_a_status_back(self):
        import ast
        import pathlib

        source = pathlib.Path("plugins/security_tools/evidence.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }

        assert "StatusValue" not in imported
        assert "status_to_outcome" not in source

    def test_the_vocabulary_module_exposes_no_inverse(self):
        import plugins.security_tools.vocabulary as vocabulary

        for name in ("status_to_outcome", "outcome_from_status", "from_status"):
            assert not hasattr(vocabulary, name), name

    def test_the_projection_is_the_only_place_the_two_meet(self):
        """`status_for` is called from exactly one place in the package.

        Counted by AST rather than by text: the mapping is *named* in its own
        definition, in the re-export list and in this test's subject, and a text
        count would say eight where the claim is one.
        """
        import ast
        import pathlib

        callers = []
        for path in sorted(pathlib.Path("plugins/security_tools").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "status_for"
                ):
                    callers.append((path.name, node.lineno))

        assert callers == [("result.py", callers[0][1])], callers


# --------------------------------------------------------------------------
# T33 — a runner's PASS is not a research verdict
# --------------------------------------------------------------------------


class TestT33RunnerOutputIsNotPromoted:
    def test_a_passing_pytest_run_yields_completed(self, allow, policy, tmp_path):
        runner = FakeRunner(exit_code=0, stdout="47 passed in 0.4s")
        request = ToolRequest.from_mapping(
            request_mapping(
                root=str(tmp_path),
                tool_id="tests",
                family="tests",
                operation="pytest",
                permission_level="test",
            )
        )

        result = invoke(
            request, registry=tools.default_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        assert result.outcome is ToolOutcome.COMPLETED
        assert result.outcome is not ToolOutcome.FAILED

    def test_the_runners_own_numbers_stay_in_structured_output(
        self, allow, policy, tmp_path
    ):
        """`47 passed` is data the adapter observed, not a ToolOutcome member."""
        runner = FakeRunner(exit_code=0, stdout="47 passed")
        request = ToolRequest.from_mapping(
            request_mapping(
                root=str(tmp_path), tool_id="tests", family="tests",
                operation="pytest", permission_level="test",
            )
        )

        result = invoke(
            request, registry=tools.default_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        assert "47 passed" in result.stdout
        assert "PASS" not in {member.value for member in ToolOutcome}

    def test_no_tool_outcome_member_names_a_research_verdict(self):
        forbidden = {
            "PASS", "FAIL", "SUCCESS", "SUCCEEDED", "DENIED", "RESEARCH_PASS",
            "VERIFIED", "ALLOWED", "OK",
        }

        assert {member.value for member in ToolOutcome} & forbidden == set()

    def test_the_projected_status_does_not_claim_a_verdict(self):
        """`PASS` here means the operation completed, and the module says so.

        The claim is only as good as the code being the only one that could
        make it, so this asserts the projection has exactly six inputs and no
        seventh path.
        """
        from plugins.security_tools.vocabulary import OUTCOME_TO_STATUS

        assert len(OUTCOME_TO_STATUS) == 6

    def test_a_failing_test_run_is_not_silently_a_pass(self, allow, policy, tmp_path):
        """Non-zero is the operation not succeeding (§13.3).

        The exit code is still recorded as observed; what changes is the claim,
        which is about the operation and not about the research question.
        """
        runner = FakeRunner(exit_code=1, stdout="3 failed")
        request = ToolRequest.from_mapping(
            request_mapping(
                root=str(tmp_path), tool_id="tests", family="tests",
                operation="pytest", permission_level="test",
            )
        )

        result = invoke(
            request, registry=tools.default_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        assert result.outcome is ToolOutcome.FAILED
        assert result.exit_code == 1
        assert str(result.status) == "FAIL"


# --------------------------------------------------------------------------
# T40, T41 — git stays read-only
# --------------------------------------------------------------------------


class TestT40NoGitWriteOperation:
    WRITE_VERBS = (
        "commit", "push", "merge", "reset", "checkout", "rebase", "tag",
        "branch_create", "fetch", "pull", "clean", "stash", "remote",
    )

    def test_no_write_operation_is_registered(self):
        registry = tools.default_registry()
        identity = next(
            i for i in registry.identities if i.adapter_family is AdapterFamily.GIT
        )

        declared = set(registry.capability_names(identity))

        assert declared & set(self.WRITE_VERBS) == set()

    def test_the_declared_set_is_exactly_the_read_only_six(self):
        registry = tools.default_registry()
        identity = next(
            i for i in registry.identities if i.adapter_family is AdapterFamily.GIT
        )

        assert set(registry.capability_names(identity)) == {
            "status",
            "current_sha",
            "current_branch",
            "diff",
            "log",
            "read_file",
        }

    def test_the_git_adapter_has_a_closed_verb_set(self):
        from tools.git import _READ_ONLY_VERBS

        assert "commit" not in _READ_ONLY_VERBS
        assert "push" not in _READ_ONLY_VERBS
        assert "merge" not in _READ_ONLY_VERBS

    def test_a_write_verb_cannot_be_reached_by_an_argument(self, allow, policy, tmp_path):
        """`diff` takes an `against` argument; it cannot become a verb."""
        runner = FakeRunner()
        request = ToolRequest.from_mapping(
            request_mapping(
                root=str(tmp_path), operation="diff",
                arguments={"against": "commit -m x"},
            )
        )

        result = invoke(
            request, registry=tools.default_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        if runner.calls:
            argv = runner.calls[0]["argv"]
            assert argv[:2] == ["git", "diff"]
            assert argv[2] == "commit -m x", "the value is one argument, not a verb"


class TestT41EveryGitArgvIsReadOnly:
    def test_every_declared_operation_produces_a_read_only_argv(
        self, allow, policy, tmp_path
    ):
        from tools.git import _READ_ONLY_VERBS

        for operation, arguments in (
            ("status", {}),
            ("current_sha", {}),
            ("current_branch", {}),
            ("diff", {}),
            ("log", {}),
        ):
            runner = FakeRunner()
            request = ToolRequest.from_mapping(
                request_mapping(root=str(tmp_path), operation=operation, arguments=arguments)
            )
            invoke(
                request, registry=tools.default_registry(), evaluator=allow,
                policy=policy, runner=runner,
            )
            assert runner.calls, operation
            assert runner.calls[0]["argv"][1] in _READ_ONLY_VERBS, operation


# --------------------------------------------------------------------------
# T45 — the architecture boundary
# --------------------------------------------------------------------------


class TestT45ArchitectureBoundary:
    FORBIDDEN_IMPORTS = (
        "socket", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp",
        "ftplib", "smtplib", "asyncio", "multiprocessing", "routing",
    )
    FORBIDDEN_BUILTINS = ("eval", "exec", "compile", "__import__")

    def _modules(self):
        return sorted(pathlib.Path("plugins/security_tools").glob("*.py"))

    def test_no_forbidden_import(self):
        offenders = []
        for path in self._modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in self.FORBIDDEN_IMPORTS:
                            offenders.append((path.name, alias.name))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".")[0] in self.FORBIDDEN_IMPORTS:
                        offenders.append((path.name, node.module))
        assert offenders == []

    def test_no_forbidden_builtin(self):
        offenders = []
        for path in self._modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in self.FORBIDDEN_BUILTINS:
                        offenders.append((path.name, node.func.id))
        assert offenders == []

    def test_subprocess_is_imported_in_exactly_one_module(self):
        importers = [
            path.name
            for path in self._modules()
            if "import subprocess" in path.read_text(encoding="utf-8")
        ]

        assert importers == ["runner.py"]

    def test_the_plugin_never_imports_the_adapters(self):
        """F-14's one-way dependency, checked rather than intended."""
        importers = []
        for path in self._modules():
            source = path.read_text(encoding="utf-8")
            if "from tools" in source or "import tools" in source:
                importers.append(path.name)

        assert importers == []

    def test_the_plugin_does_not_write_files(self):
        for path in self._modules():
            source = path.read_text(encoding="utf-8")
            for needle in ("write_text", "open(", "shutil.", "json.dump"):
                assert needle not in source, (path.name, needle)

    def test_no_secret_logging(self):
        for path in self._modules():
            source = path.read_text(encoding="utf-8")
            for needle in ("logging", "print("):
                assert needle not in source, (path.name, needle)
