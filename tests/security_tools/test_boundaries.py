"""The boundaries — T8 to T29, and T34 to T39.

Guard, workspace, execution, secrets and the vehicle rail. These are the tests
the phase turns on: a Tool layer that executes without an authorization, or
confines a path by string comparison, or reads a parent's environment into a
child, is the defect this contract exists to prevent.
"""

from __future__ import annotations

import os
import pathlib

import pytest

import tools
from plugins.security_tools import (
    AdapterOutcome,
    Invocation,
    PermissionLevel,
    ToolOutcome,
    ToolRequest,
    ToolRegistry,
)
from plugins.security_tools import errors as st_errors
from plugins.security_tools.adapter import execute_argv
from plugins.security_tools.descriptor import (
    ArgumentSpec,
    EnvironmentRequirement,
    OperationSpec,
    ToolDescriptor,
)
from plugins.security_tools.dispatch import invoke
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.paths import contained_path, resolve_root
from plugins.security_tools.redaction import project, redact_text
from plugins.security_tools.runner import SubprocessRunner
from plugins.security_tools.vocabulary import AdapterFamily, FilesystemAccess

from tests.security_tools.conftest import FakeRunner, request_mapping

pytestmark = pytest.mark.layer1


def _registry() -> ToolRegistry:
    return tools.default_registry()


def _git(root, **overrides):
    return ToolRequest.from_mapping(request_mapping(root=str(root), **overrides))


def _vehicle(root, interface="vcan0", **target_overrides):
    target = {
        "kind": "can_bus",
        "identifier": interface,
        "environment": "simulated",
        "interface": "vcan",
        "is_real": False,
        "sensitivity": "internal",
        **target_overrides,
    }
    return ToolRequest.from_mapping(
        request_mapping(
            root=str(root),
            tool_id="vehicle_network",
            family="vehicle_network",
            operation="vcan_can_send",
            arguments={"interface": interface, "frame": "123#0011"},
            permission_level="test",
            target=target,
        )
    )


# --------------------------------------------------------------------------
# T8 to T13 — the Guard boundary
# --------------------------------------------------------------------------


class TestT8GuardAllowExecutes:
    def test_an_allowed_invocation_reaches_the_adapter(self, allow, policy, tmp_path):
        runner = FakeRunner(stdout="clean\n")

        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        assert result.outcome is ToolOutcome.COMPLETED
        assert runner.calls != []
        assert result.stdout.strip() == "clean"

    def test_the_result_names_the_authorization_it_ran_under(
        self, allow, policy, tmp_path
    ):
        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
            runner=FakeRunner(),
        )

        assert str(result.guard_decision) == "ALLOW"


class TestGuardAttributionIsCarriedThrough:
    """§8.1, §8.3. A result names the decision it ran under.

    Review found this missing: the implementation returned only the enum from
    `ask_guard`, so a `ToolResult` could say ALLOW while being unable to name
    which evaluation allowed it. The decision survived and its attribution did
    not. These tests are the regression.
    """

    def test_an_allowed_result_carries_the_evaluations_attribution(
        self, policy, tmp_path
    ):
        from tests.security_tools.conftest import Evaluator
        from plugins.security_tools.vocabulary import GuardDecision

        evaluator = Evaluator(
            GuardDecision.ALLOW,
            reason_code="TEST_REASON",
            decision_id="dec-test-001",
        )

        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=evaluator, policy=policy,
            runner=FakeRunner(),
        )

        assert result.guard["decision"] == "ALLOW"
        assert result.guard["reason_code"] == "TEST_REASON"
        assert result.guard["decision_id"] == "dec-test-001"

    @pytest.mark.parametrize("decision", ["DENY", "BLOCKED", "UNKNOWN"])
    def test_a_refused_result_keeps_its_attribution(
        self, decision, policy, runner, tmp_path
    ):
        from tests.security_tools.conftest import Evaluator
        from plugins.security_tools.vocabulary import GuardDecision

        evaluator = Evaluator(
            GuardDecision(decision),
            reason_code=f"{decision}_REASON",
            decision_id=f"dec-{decision.lower()}-001",
        )

        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=evaluator, policy=policy,
            runner=runner,
        )

        assert result.guard["decision"] == decision
        assert result.guard["reason_code"] == f"{decision}_REASON"
        assert result.guard["decision_id"] == f"dec-{decision.lower()}-001"
        assert runner.calls == [], "a refused invocation must not execute"

    def test_the_attribution_comes_from_one_evaluation(
        self, policy, tmp_path
    ):
        """One evaluator call, one decision, one invocation."""
        from tests.security_tools.conftest import Evaluator
        from plugins.security_tools.vocabulary import GuardDecision

        evaluator = Evaluator(GuardDecision.ALLOW, decision_id="dec-once")

        invoke(
            _git(tmp_path), registry=_registry(), evaluator=evaluator, policy=policy,
            runner=FakeRunner(),
        )

        assert evaluator.calls == 1

    def test_a_request_that_never_reached_guard_says_so(self, allow, policy, runner, tmp_path):
        """No evaluation means no decision_id, and the result does not invent one."""
        request = ToolRequest.from_mapping(
            request_mapping(root=str(tmp_path), tool_id="not-a-tool")
        )

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.guard["decision_id"] == ""
        assert allow.calls == 0

    def test_a_failed_evaluation_carries_no_invented_identifier(
        self, exploding, policy, runner, tmp_path
    ):
        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=exploding, policy=policy,
            runner=runner,
        )

        assert result.guard["decision_id"] == ""
        assert result.reason_code == "GUARD_UNAVAILABLE"


class TestT9GuardDenyDoesNotExecute:
    def test_a_denied_invocation_does_not_run(self, deny, policy, runner, tmp_path):
        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=deny, policy=policy,
            runner=runner,
        )

        assert result.outcome is ToolOutcome.NOT_RUN
        assert runner.calls == []

    def test_the_refusal_is_a_result_not_an_exception(self, deny, policy, runner, tmp_path):
        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=deny, policy=policy,
            runner=runner,
        )

        assert result.reason_code == "GUARD_DENY"


class TestT10GuardBlockedDoesNotExecute:
    def test_a_blocked_invocation_does_not_run(self, blocked, policy, runner, tmp_path):
        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=blocked, policy=policy,
            runner=runner,
        )

        assert result.outcome is ToolOutcome.BLOCKED
        assert runner.calls == []


class TestT11GuardUnknownDoesNotExecute:
    def test_an_unknown_decision_does_not_run(self, unknown, policy, runner, tmp_path):
        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=unknown, policy=policy,
            runner=runner,
        )

        assert result.outcome is ToolOutcome.UNKNOWN
        assert runner.calls == []


class TestT12NoExecutionWithoutGuard:
    """§9.2. An evaluator that failed is not an evaluator that allowed."""

    def test_a_raising_evaluator_does_not_execute(
        self, exploding, policy, runner, tmp_path
    ):
        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=exploding, policy=policy,
            runner=runner,
        )

        assert runner.calls == []
        assert result.outcome is ToolOutcome.BLOCKED

    def test_a_raising_evaluator_fails_closed_not_open(
        self, exploding, policy, runner, tmp_path
    ):
        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=exploding, policy=policy,
            runner=runner,
        )

        assert result.reason_code == "GUARD_UNAVAILABLE"
        assert result.outcome is not ToolOutcome.COMPLETED

    @pytest.mark.parametrize(
        "decision", ["ALLOW", "DENY", "BLOCKED", "UNKNOWN"]
    )
    def test_every_decision_is_handled(self, decision, policy, runner, tmp_path):
        from tests.security_tools.conftest import Evaluator
        from plugins.security_tools.vocabulary import GuardDecision

        evaluator = Evaluator(GuardDecision(decision))

        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=evaluator, policy=policy,
            runner=runner,
        )

        if decision == "ALLOW":
            assert runner.calls != []
        else:
            assert runner.calls == []


class TestT13OneDecisionOneInvocation:
    def test_a_second_invocation_asks_again(self, allow, policy, tmp_path):
        request = _git(tmp_path)

        invoke(request, registry=_registry(), evaluator=allow, policy=policy,
               runner=FakeRunner())
        invoke(request, registry=_registry(), evaluator=allow, policy=policy,
               runner=FakeRunner())

        assert len(allow.seen) == 2

    def test_nothing_caches_a_decision(self):
        """Structural: no module in the package stores a decision."""
        import plugins.security_tools as package
        import pathlib

        for path in sorted(pathlib.Path("plugins/security_tools").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            for name in ("_DECISION_CACHE", "decision_cache", "cached_decision"):
                assert name not in source, f"{path.name} names {name}"


# --------------------------------------------------------------------------
# T14 to T17 — workspace containment
# --------------------------------------------------------------------------


class TestT14ToT17Containment:
    def test_a_path_inside_the_root_resolves(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.txt").write_text("hello", encoding="utf-8")
        root = resolve_root(str(tmp_path))

        resolved = contained_path(root, "src/a.txt")

        assert resolved.read_text(encoding="utf-8") == "hello"

    def test_dotdot_traversal_is_refused(self, tmp_path):
        root = resolve_root(str(tmp_path))

        with pytest.raises(st_errors.PathEscapesWorkspace):
            contained_path(root, "../outside.txt")

    def test_an_absolute_path_outside_the_root_is_refused(self, tmp_path):
        root = resolve_root(str(tmp_path))

        with pytest.raises(st_errors.PathEscapesWorkspace):
            contained_path(root, str(tmp_path.parent / "outside.txt"))

    def test_a_symlink_escape_is_refused(self, tmp_path):
        """Resolution, not string comparison: this is the case a prefix check misses."""
        outside = tmp_path.parent / "outside-target"
        outside.mkdir(exist_ok=True)
        workspace = tmp_path / "ws"
        workspace.mkdir()
        link = workspace / "escape"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):  # pragma: no cover - platform
            pytest.skip("this host does not allow symlink creation")
        root = resolve_root(str(workspace))

        with pytest.raises(st_errors.PathEscapesWorkspace):
            contained_path(root, "escape/anything.txt")

    def test_missing_root_is_refused_rather_than_defaulted(self, allow, policy, runner, tmp_path):
        request = ToolRequest.from_mapping(
            request_mapping(root=None, operation="read_file", arguments={"path": "x"})
        )

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.outcome is ToolOutcome.BLOCKED
        assert result.reason_code == "WORKSPACE_UNRESOLVABLE"


class TestT18NoDiscovery:
    def test_the_paths_module_has_no_search(self):
        import ast
        import pathlib

        source = pathlib.Path("plugins/security_tools/paths.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }

        for name in ("parent", "parents", "rglob", "walk", "glob", "cwd"):
            assert name not in called, f"paths.py calls .{name}()"

    def test_no_package_module_reads_the_working_directory(self):
        import pathlib

        for path in sorted(pathlib.Path("plugins/security_tools").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            assert 'Path.cwd()' not in source, path.name
            assert "os.getcwd()" not in source, path.name


class TestT19SecurityLabUnreachable:
    """F-02, F-17. The other workspace is not a special case and not reachable."""

    def test_no_module_names_securitylab(self):
        import pathlib

        offenders = []
        for root in ("plugins/security_tools", "tools"):
            for path in sorted(pathlib.Path(root).rglob("*.py")):
                text = path.read_text(encoding="utf-8")
                # The package documents the boundary, so the *name* appears in
                # prose; what must not appear is a path or an import.
                for needle in ("SecurityLab/", "Li20771/SecurityLab", "import securitylab"):
                    if needle in text:
                        offenders.append((str(path), needle))
        assert offenders == []

    def test_a_workspace_outside_the_root_cannot_be_reached(self, tmp_path):
        """There is no parameter by which a second workspace could be named."""
        request = _git(tmp_path)

        assert set(request.to_mapping()) == {
            "schema_version",
            "workspace",
            "tool",
            "operation",
            "arguments",
            "actor",
            "permission_level",
            "target",
            "execution",
            "approval",
        }
        assert set(request.workspace.__slots__) if hasattr(
            request.workspace, "__slots__"
        ) else True
        assert not hasattr(request.workspace, "sibling")
        assert not hasattr(request.workspace, "securitylab")


# --------------------------------------------------------------------------
# T20 to T27 — the execution boundary
# --------------------------------------------------------------------------


class TestT20ArgvNeverAShell:
    def test_the_runner_module_never_enables_a_shell(self):
        import ast
        import pathlib

        source = pathlib.Path("plugins/security_tools/runner.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                for keyword in node.keywords:
                    if keyword.arg == "shell":
                        assert isinstance(keyword.value, ast.Constant)
                        assert keyword.value.value is False

    def test_the_runner_module_has_no_shell_parameter(self):
        import inspect

        signature = inspect.signature(SubprocessRunner.run)
        assert "shell" not in signature.parameters

    def test_argv_is_a_list_not_a_string(self, allow, policy, tmp_path):
        runner = FakeRunner()
        invoke(_git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
               runner=runner)

        assert runner.calls
        argv = runner.calls[0]["argv"]
        assert isinstance(argv, list)
        assert all(isinstance(part, str) for part in argv)

    def test_no_adapter_uses_a_shell_keyword(self):
        import ast
        import pathlib

        for path in sorted(pathlib.Path("tools").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for keyword in node.keywords:
                        assert keyword.arg != "shell", path


class TestT21ShellMetacharactersAreData:
    def test_a_metacharacter_reaches_the_program_as_an_argument(
        self, allow, policy, tmp_path
    ):
        """`;`, `|`, `$()` and `&&` are data, because there is no shell."""
        runner = FakeRunner()
        request = ToolRequest.from_mapping(
            request_mapping(
                root=str(tmp_path),
                tool_id="terminal",
                family="terminal",
                operation="run",
                permission_level="test",
                arguments={"program": "echo", "args": ["a; rm -rf /", "b|c", "$(x)", "d&&e"]},
            )
        )

        invoke(request, registry=_registry(), evaluator=allow, policy=policy, runner=runner)

        assert runner.calls[0]["argv"] == [
            "echo",
            "a; rm -rf /",
            "b|c",
            "$(x)",
            "d&&e",
        ]

    def test_an_undeclared_program_is_refused(self, allow, policy, runner, tmp_path):
        request = ToolRequest.from_mapping(
            request_mapping(
                root=str(tmp_path),
                tool_id="terminal",
                family="terminal",
                operation="run",
                permission_level="test",
                arguments={"program": "bash", "args": ["-c", "rm -rf /"]},
            )
        )

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.outcome is ToolOutcome.BLOCKED
        assert runner.calls == []


class TestT22EnvironmentIsNotInherited:
    def test_a_parent_only_variable_does_not_reach_the_child(
        self, allow, policy, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("SECRET_X", "must-not-travel")
        runner = FakeRunner()

        invoke(_git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
               runner=runner)

        assert "SECRET_X" not in runner.calls[0]["environment"]

    def test_a_declared_variable_does_reach_the_child(self, allow, policy, tmp_path):
        runner = FakeRunner()
        request = ToolRequest.from_mapping(
            request_mapping(root=str(tmp_path), environment={"LANG": "C"})
        )

        invoke(request, registry=_registry(), evaluator=allow, policy=policy, runner=runner)

        assert runner.calls[0]["environment"]["LANG"] == "C"

    def test_the_whole_parent_environment_is_not_passed(self):
        from plugins.security_tools.adapter import _BASELINE_ENVIRONMENT_NAMES

        assert len(_BASELINE_ENVIRONMENT_NAMES) <= 8
        assert "SECRET_X" not in _BASELINE_ENVIRONMENT_NAMES


class TestT23TimeoutRequired:
    def test_a_request_without_a_timeout_is_refused(self):
        with pytest.raises(st_errors.TimeoutMissing):
            ToolRequest.from_mapping(request_mapping(timeout_seconds=None))

    def test_a_zero_timeout_is_refused(self):
        with pytest.raises(st_errors.ToolRequestMalformed):
            ToolRequest.from_mapping(request_mapping(timeout_seconds=0))

    def test_a_negative_timeout_is_refused(self):
        with pytest.raises(st_errors.ToolRequestMalformed):
            ToolRequest.from_mapping(request_mapping(timeout_seconds=-1))

    def test_the_runner_refuses_a_non_positive_timeout(self, tmp_path):
        with pytest.raises(st_errors.ExecutionRefused):
            SubprocessRunner().run(
                ["echo"], cwd=str(tmp_path), environment={}, timeout_seconds=0
            )


class TestT24TimeoutTerminates:
    def test_a_timed_out_process_yields_timed_out(self, allow, policy, tmp_path):
        runner = FakeRunner(timed_out=True)

        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        assert result.outcome is ToolOutcome.TIMED_OUT

    def test_the_timeout_reaches_the_runner(self, allow, policy, tmp_path):
        runner = FakeRunner()
        request = ToolRequest.from_mapping(
            request_mapping(root=str(tmp_path), timeout_seconds=7)
        )

        invoke(request, registry=_registry(), evaluator=allow, policy=policy, runner=runner)

        assert runner.calls[0]["timeout_seconds"] == 7

    def test_the_real_runner_passes_the_deadline_to_subprocess(self):
        import ast
        import pathlib

        source = pathlib.Path("plugins/security_tools/runner.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        keywords = {
            keyword.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
        }
        assert "timeout" in keywords


class TestT25NonZeroExitIsNotAutomaticallyFailed:
    def test_a_declared_non_zero_exit_is_completed(self, allow, policy, tmp_path):
        """YARA reports a match through its status; §11.5 exists for this."""
        runner = FakeRunner(exit_code=1)
        request = ToolRequest.from_mapping(
            request_mapping(
                root=str(tmp_path),
                tool_id="reverse_engineering",
                family="reverse_engineering",
                operation="yara_scan",
                permission_level="test",
                arguments={"rules": "r.yar", "target": "t.bin"},
            )
        )
        (tmp_path / "r.yar").write_text("rule x { condition: true }", encoding="utf-8")
        (tmp_path / "t.bin").write_bytes(b"\x00")

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.outcome is ToolOutcome.COMPLETED
        assert result.exit_code == 1

    def test_an_undeclared_exit_is_failed(self, allow, policy, tmp_path):
        runner = FakeRunner(exit_code=3)

        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        assert result.outcome is ToolOutcome.FAILED
        assert result.exit_code == 3


class TestT26OutputIsBounded:
    def test_a_long_stream_is_truncated_and_marked(self, allow, policy, tmp_path):
        from plugins.security_tools.result import BOUNDED_OUTPUT_CHARS

        runner = FakeRunner(stdout="x" * (BOUNDED_OUTPUT_CHARS + 100))

        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        assert result.truncated is True
        assert len(result.stdout) == BOUNDED_OUTPUT_CHARS

    def test_a_short_stream_is_not_marked(self, allow, policy, tmp_path):
        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
            runner=FakeRunner(stdout="short"),
        )

        assert result.truncated is False

    def test_the_bound_is_not_the_evidence_leaf_bound(self):
        """§15.5: a ToolResult is not a record."""
        from plugins.security_tools.result import BOUNDED_OUTPUT_CHARS
        from plugins.evidence import MAX_TEXT_LENGTH

        assert BOUNDED_OUTPUT_CHARS > MAX_TEXT_LENGTH


class TestT27ExitCodeRecordedAsObserved:
    @pytest.mark.parametrize("code", [0, 1, 2, 127, 255])
    def test_the_exit_code_is_recorded(self, allow, policy, runner, tmp_path, code):
        runner.exit_code = code

        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        assert result.exit_code == code


# --------------------------------------------------------------------------
# T28, T29 — secrets
# --------------------------------------------------------------------------


class TestT28TheProjectionRuns:
    @pytest.mark.parametrize(
        "text",
        [
            "Authorization: Bearer abcdefghijklmnop",
            "sk-abcdefghijklmnopqrst",
            "API_KEY=supersecretvalue",
            "-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----",
            "postgres://user:hunter2@host/db",
            "ghp_abcdefghijklmnopqrstuvwx",
        ],
    )
    def test_known_shaped_material_is_masked(self, text):
        masked, hit = redact_text(text)

        assert hit is True
        assert "supersecretvalue" not in masked
        assert "hunter2" not in masked

    def test_a_clean_string_is_untouched(self):
        masked, hit = redact_text("git status --porcelain")

        assert hit is False
        assert masked == "git status --porcelain"

    def test_structured_output_is_projected_too(self):
        _, _, structured, hit = project("", "", {"token": "API_KEY=abc123def456"})

        assert hit is True
        assert "abc123def456" not in str(structured)

    def test_a_result_records_that_it_was_redacted(self, allow, policy, tmp_path):
        runner = FakeRunner(stdout="Authorization: Bearer abcdefghijklmnop")

        result = invoke(
            _git(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
            runner=runner,
        )

        assert result.redacted is True
        assert "abcdefghijklmnop" not in result.stdout
        assert result.stdout.strip() == "[redacted]"

    def test_a_digest_is_not_destroyed(self):
        """The projection is a filter, not an entropy rule.

        AI-05 §14.5 records what applying a long-run rule outside its domain
        does: every digest and revision is replaced. A 64-character hex digest
        is a legitimate value here and must survive.
        """
        digest = "b" * 64

        masked, hit = redact_text(digest)

        assert hit is False
        assert masked == digest


class TestT29EnvironmentIsNotDumped:
    def test_no_module_writes_a_whole_environment(self):
        import pathlib

        for path in sorted(pathlib.Path("plugins/security_tools").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            assert "dict(os.environ)" not in source, path.name
            assert "os.environ.copy()" not in source, path.name


# --------------------------------------------------------------------------
# T34 to T39 — the vehicle boundary
# --------------------------------------------------------------------------


class TestT34ToT36RealHardwareRefused:
    @pytest.mark.parametrize(
        "target",
        [
            {"kind": "vehicle", "interface": "can", "environment": "real", "is_real": True},
            {"kind": "ecu", "interface": "can", "environment": "real", "is_real": True},
            {"kind": "can_bus", "interface": "can_fd", "environment": "real", "is_real": True},
            {"kind": "actuator", "interface": "can", "environment": "real", "is_real": True},
        ],
    )
    def test_a_real_target_is_refused(self, allow, policy, runner, tmp_path, target):
        request = _vehicle(tmp_path, **target)

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.outcome is ToolOutcome.BLOCKED
        assert result.reason_code == "TARGET_REFUSED"
        assert runner.calls == []

    def test_the_refusal_happens_before_guard_is_asked(self, allow, policy, runner, tmp_path):
        request = _vehicle(tmp_path, interface="can_fd", environment="real", is_real=True)

        invoke(request, registry=_registry(), evaluator=allow, policy=policy, runner=runner)

        assert allow.seen == []


class TestT37UnknownClassificationRefused:
    @pytest.mark.parametrize("environment", ["unknown", None])
    def test_an_unsettled_environment_is_refused(
        self, allow, policy, runner, tmp_path, environment
    ):
        request = _vehicle(tmp_path, environment=environment)

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.outcome is ToolOutcome.BLOCKED
        assert runner.calls == []

    def test_unknown_is_never_read_as_simulated(self, allow, policy, runner, tmp_path):
        request = _vehicle(tmp_path, environment="unknown")

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.outcome is not ToolOutcome.COMPLETED


class TestT38NoTargetSubstitution:
    def test_a_refused_interface_is_not_swapped_for_vcan(
        self, allow, policy, runner, tmp_path
    ):
        request = _vehicle(tmp_path, interface="can0")

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert runner.calls == []
        assert result.outcome is ToolOutcome.BLOCKED

    def test_the_adapter_accepts_no_interface_but_vcan(
        self, allow, policy, runner, tmp_path
    ):
        """The name is checked *after* the closed vocabularies have decided."""
        runner = FakeRunner()
        request = _vehicle(tmp_path, interface="can0")

        invoke(request, registry=_registry(), evaluator=allow, policy=policy, runner=runner)

        assert runner.calls == []


class TestT39VcanIsAccepted:
    def test_a_vcan_target_runs(self, allow, policy, tmp_path):
        runner = FakeRunner()
        request = _vehicle(tmp_path)

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.outcome is ToolOutcome.COMPLETED
        assert runner.calls[0]["argv"][0] == "cansend"
        assert runner.calls[0]["argv"][1] == "vcan0"

    def test_the_interface_reaches_argv_as_one_argument(self, allow, policy, tmp_path):
        runner = FakeRunner()

        invoke(_vehicle(tmp_path), registry=_registry(), evaluator=allow, policy=policy,
               runner=runner)

        assert "vcan0" in runner.calls[0]["argv"]
