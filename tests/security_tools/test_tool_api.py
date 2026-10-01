"""The Tool API — T1 to T7, and T42 to T44.

Covers the request shape, the argument schema, the rule that permission is
supplied rather than inferred, and the registry's refusal to authorize.
"""

from __future__ import annotations

import pytest

import tools
from plugins.security_tools import (
    AdapterFamily,
    PermissionLevel,
    ToolOutcome,
    ToolRequest,
    ToolRegistry,
)
from plugins.security_tools import errors as st_errors
from plugins.security_tools.descriptor import (
    ArgumentSpec,
    EnvironmentRequirement,
    OperationSpec,
    ToolDescriptor,
)
from plugins.security_tools.dispatch import invoke
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.result import ToolResult

from tests.security_tools.conftest import FakeRunner, request_mapping

pytestmark = pytest.mark.layer1


def _registry() -> ToolRegistry:
    return tools.default_registry()


# --------------------------------------------------------------------------
# T1, T2 — shape
# --------------------------------------------------------------------------


class TestT1WellFormedRequest:
    def test_a_well_formed_request_parses(self):
        request = ToolRequest.from_mapping(request_mapping())

        assert request.tool.tool_id == "git"
        assert request.operation == "status"
        assert request.permission_level is PermissionLevel.READ
        assert request.timeout_seconds == 30

    def test_it_round_trips_through_its_own_mapping(self):
        request = ToolRequest.from_mapping(request_mapping())

        again = ToolRequest.from_mapping(request.to_mapping())

        assert again == request


class TestT2MalformedRequestRefused:
    @pytest.mark.parametrize(
        "mutation",
        [
            {"raw_command": "rm -rf /"},
            {"command": "git status"},
            {"policy": {}},
            {"credential": "sk-abcdefgh"},
        ],
    )
    def test_an_undeclared_top_level_field_is_refused(self, mutation):
        with pytest.raises(st_errors.ToolRequestMalformed):
            ToolRequest.from_mapping({**request_mapping(), **mutation})

    def test_a_missing_workspace_is_refused(self):
        mapping = request_mapping()
        del mapping["workspace"]

        with pytest.raises(st_errors.ToolRequestMalformed):
            ToolRequest.from_mapping(mapping)

    def test_a_bad_schema_version_is_refused(self):
        with pytest.raises(st_errors.ToolRequestMalformed):
            ToolRequest.from_mapping({**request_mapping(), "schema_version": 2})


# --------------------------------------------------------------------------
# T3, T4 — the registry is a closed description
# --------------------------------------------------------------------------


class TestT3UnknownToolRefused:
    def test_an_unregistered_tool_is_refused(self, allow, policy, runner, tmp_path):
        request = ToolRequest.from_mapping(
            request_mapping(root=str(tmp_path), tool_id="not-a-tool")
        )

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.outcome is ToolOutcome.UNKNOWN
        assert result.reason_code == "UNKNOWN_TOOL"

    def test_the_adapter_is_never_reached(self, allow, policy, runner, tmp_path):
        request = ToolRequest.from_mapping(
            request_mapping(root=str(tmp_path), tool_id="not-a-tool")
        )

        invoke(request, registry=_registry(), evaluator=allow, policy=policy, runner=runner)

        assert runner.calls == []
        assert allow.seen == []


class TestT4UnknownOperationRefused:
    def test_an_undeclared_operation_is_refused(self, allow, policy, runner, tmp_path):
        request = ToolRequest.from_mapping(
            request_mapping(root=str(tmp_path), operation="push")
        )

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.outcome is ToolOutcome.UNKNOWN
        assert result.reason_code == "UNKNOWN_OPERATION"

    def test_guard_is_not_asked_about_an_undeclared_operation(
        self, allow, policy, runner, tmp_path
    ):
        request = ToolRequest.from_mapping(
            request_mapping(root=str(tmp_path), operation="push")
        )

        invoke(request, registry=_registry(), evaluator=allow, policy=policy, runner=runner)

        assert allow.seen == []


# --------------------------------------------------------------------------
# T5 — the argument schema
# --------------------------------------------------------------------------


class TestT5ArgumentSchemaEnforced:
    def test_an_undeclared_argument_is_refused(self, allow, policy, runner, tmp_path):
        request = ToolRequest.from_mapping(
            request_mapping(root=str(tmp_path), arguments={"colour": "red"})
        )

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.reason_code == "TOOL_REQUEST_MALFORMED"

    def test_a_missing_required_argument_is_refused(self, allow, policy, runner, tmp_path):
        request = ToolRequest.from_mapping(
            request_mapping(
                root=str(tmp_path),
                tool_id="terminal",
                family="terminal",
                operation="run",
                arguments={},
            )
        )

        result = invoke(
            request, registry=_registry(), evaluator=allow, policy=policy, runner=runner
        )

        assert result.reason_code == "TOOL_REQUEST_MALFORMED"

    def test_a_wrong_typed_argument_is_refused(self):
        spec = OperationSpec(
            name="op",
            permission_level_floor=PermissionLevel.READ,
            summary="x",
            arguments=(ArgumentSpec("limit", "integer"),),
        )

        with pytest.raises(st_errors.ToolRequestMalformed):
            spec.validate_arguments({"limit": "many"})

    def test_a_value_outside_choices_is_refused(self):
        spec = OperationSpec(
            name="op",
            permission_level_floor=PermissionLevel.READ,
            summary="x",
            arguments=(ArgumentSpec("mode", "string", choices=("a", "b")),),
        )

        with pytest.raises(st_errors.ToolRequestMalformed):
            spec.validate_arguments({"mode": "c"})

    def test_an_over_long_argument_is_refused(self):
        spec = OperationSpec(
            name="op",
            permission_level_floor=PermissionLevel.READ,
            summary="x",
            arguments=(ArgumentSpec("path", "string", maximum_length=8),),
        )

        with pytest.raises(st_errors.ToolRequestMalformed):
            spec.validate_arguments({"path": "x" * 9})


# --------------------------------------------------------------------------
# T6, T7 — permission is supplied, never inferred
# --------------------------------------------------------------------------


class TestT6PermissionLevelRequired:
    def test_a_request_without_a_level_is_refused(self):
        with pytest.raises(st_errors.PermissionLevelMissing):
            ToolRequest.from_mapping(request_mapping(permission_level=None))

    def test_the_refusal_is_its_own_code(self):
        with pytest.raises(st_errors.PermissionLevelMissing) as excinfo:
            ToolRequest.from_mapping(request_mapping(permission_level=None))

        assert excinfo.value.reason_code == "PERMISSION_LEVEL_MISSING"

    def test_an_unlisted_level_is_refused(self):
        with pytest.raises(st_errors.ToolRequestMalformed):
            ToolRequest.from_mapping(request_mapping(permission_level="sudo"))


class TestT7PermissionIsNeverInferred:
    """§6.2. The level is whatever the caller said, whatever the operation is.

    AI-04 §4.1 in that contract's own words: *"An implementer must never infer
    the permission level from `action.id`."* A layer that upgraded a request
    because the operation looked privileged would be deciding privilege from a
    name, which is the defect F-09 exists to prevent.
    """

    def test_a_low_level_for_a_high_floor_operation_is_not_upgraded(
        self, allow, policy, runner, tmp_path
    ):
        # `tests.pytest` has a `test` floor; the caller asks for `read`.
        request = ToolRequest.from_mapping(
            request_mapping(
                root=str(tmp_path),
                tool_id="tests",
                family="tests",
                operation="pytest",
                permission_level="read",
            )
        )

        assert request.permission_level is PermissionLevel.READ

        invoke(request, registry=_registry(), evaluator=allow, policy=policy, runner=runner)

        # Whatever Guard decided, the level that reached it is the supplied one.
        assert allow.seen[-1].action.permission_level is PermissionLevel.READ

    def test_the_operation_name_never_sets_the_level(self):
        for level in ("read", "analyze", "test", "modify", "system-change"):
            request = ToolRequest.from_mapping(
                request_mapping(operation="status", permission_level=level)
            )
            assert str(request.permission_level) == level

    def test_the_tool_id_never_sets_the_level(self):
        request = ToolRequest.from_mapping(
            request_mapping(tool_id="git", permission_level="analyze")
        )

        assert request.permission_level is PermissionLevel.ANALYZE

    def test_no_inference_helper_exists_in_the_package(self):
        """Structural: there is no function that could derive a level."""
        import ast
        import pathlib

        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(pathlib.Path("plugins/security_tools").glob("*.py"))
        )
        tree = ast.parse(source)
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        assert "infer_permission_level" not in called
        assert "permission_for" not in called


# --------------------------------------------------------------------------
# T42, T43, T44 — the registry and the families
# --------------------------------------------------------------------------


class TestT42RegistryDoesNotAuthorize:
    def test_the_registry_holds_no_policy(self):
        registry = _registry()

        for name in ("policy", "evaluate", "guard", "authorize", "allow", "deny"):
            assert not hasattr(registry, name), name

    def test_the_registry_module_reaches_no_guard_decision(self):
        import ast
        import pathlib

        source = pathlib.Path("plugins/security_tools/registry.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }

        assert "evaluate" not in called
        assert "GuardDecision" not in source.replace("GuardDecision ", "")


class TestT43ExactlyEightFamilies:
    def test_the_vocabulary_is_exactly_eight(self):
        assert len(AdapterFamily) == 8

    def test_the_members_are_the_frozen_eight(self):
        assert {member.value for member in AdapterFamily} == {
            "git",
            "github",
            "tests",
            "terminal",
            "mcp",
            "vehicle_network",
            "firmware",
            "reverse_engineering",
        }

    def test_the_default_registry_represents_all_eight(self):
        assert _registry().families == frozenset(AdapterFamily)

    def test_a_ninth_family_is_not_constructible(self):
        with pytest.raises(ValueError):
            AdapterFamily("wireshark")


class TestT44TheAdapterProtocolIsUniform:
    def test_every_family_implements_the_same_two_members(self):
        for adapter in (cls() for cls in tools.ADAPTERS):
            assert isinstance(adapter, object)
            assert isinstance(adapter.descriptor, ToolDescriptor)
            assert callable(adapter.execute)

    def test_every_descriptor_declares_its_own_family(self):
        for adapter in (cls() for cls in tools.ADAPTERS):
            identity = adapter.descriptor.identity
            assert identity.adapter_family in AdapterFamily

    def test_every_tool_id_matches_its_family_name(self):
        """A description that disagrees with its own directory is a defect."""
        for adapter in (cls() for cls in tools.ADAPTERS):
            identity = adapter.descriptor.identity
            assert identity.tool_id == str(identity.adapter_family)


class TestTheOutcomeProjectionIsTotal:
    def test_every_outcome_maps(self):
        from plugins.security_tools.vocabulary import OUTCOME_TO_STATUS

        assert set(OUTCOME_TO_STATUS) == set(ToolOutcome)

    def test_there_is_no_inverse(self):
        import plugins.security_tools.vocabulary as vocabulary

        for name in ("status_to_outcome", "outcome_for", "from_status"):
            assert not hasattr(vocabulary, name), name

    def test_a_result_projects_its_own_outcome(self):
        result = ToolResult(
            tool_id="git",
            tool_version="1.0.0",
            operation="status",
            outcome=ToolOutcome.COMPLETED,
            reason_code="OK",
            workspace_id="ws",
            guard={"decision": "ALLOW", "reason_code": "", "decision_id": ""},
        )

        assert str(result.status) == "PASS"
        assert result.what_ran == "git/status"
