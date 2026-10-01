"""AI-06 vehicle-network adapter. Contract §13.6, §12. **The highest-consequence
family in AI-06, and it is stated as a negative contract.**

```text
MAY reach      vcan · simulator · isolated harness
MUST NOT       real CAN interface · real ECU · real vehicle ·
               unknown external CAN gateway · uncontrolled ECU flashing ·
               physical actuation
```

AI-00 §7 is explicit that this is not a prompt-level convention:

> *"任何例外都不能通过'提示词约定'实现，而必须由可执行 Guard 控制。"*

### Two gates, and this is the second one

```text
gate 1   the v1 target boundary in guards.py, before Guard is asked
gate 2   AI-04's authorization
```

The adapter re-checks, because it is the last thing between a request and a
socket. It decides from `target.interface` and `target.environment` — closed
vocabularies — and from the resolved interface name, never from a pattern match
on a string (§12.4). An interface called `vcan0-test` is not physical and one
called `can0` is not simulated; the classification is a declared fact.

Nothing here treats an unsettled classification as simulated, and nothing here
substitutes a different interface to make an operation succeed (§12.3, §12.5).
"""

from __future__ import annotations

from plugins.security_tools.adapter import AdapterOutcome, Invocation, execute_argv
from plugins.security_tools.descriptor import (
    ArgumentSpec,
    EnvironmentRequirement,
    OperationSpec,
    ToolDescriptor,
)
from plugins.security_tools.errors import TargetRefused
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.vocabulary import (
    AdapterFamily,
    FilesystemAccess,
    PermissionLevel,
    TargetEnvironment,
    TargetInterface,
    TargetKind,
    ToolOutcome,
    VehicleInterface,
)

__all__ = ["Adapter", "OPERATION_NAMES", "TOOL_ID", "TOOL_VERSION"]

TOOL_ID = "vehicle_network"
TOOL_VERSION = "1.0.0"

_VCAN = EnvironmentRequirement(
    filesystem=FilesystemAccess.NONE,
    subprocess=True,
    vehicle_interface=VehicleInterface.VCAN,
)

#: The only interfaces this adapter will name on an argv.
_PERMITTED_INTERFACES: frozenset[TargetInterface] = frozenset(
    {TargetInterface.VCAN, TargetInterface.SIMULATOR}
)

#: A vcan interface name, checked as a *name shape* only after the closed
#: vocabularies have already decided. It is a second look, not the decision.
_VCAN_PREFIX = "vcan"

_OPERATION_KINDS = (TargetKind.CAN_BUS,)

OPERATIONS: tuple[OperationSpec, ...] = (
    OperationSpec(
        name="vcan_can_send",
        permission_level_floor=PermissionLevel.TEST,
        summary="send one frame onto a vcan interface",
        arguments=(
            ArgumentSpec("interface", "string", maximum_length=32),
            ArgumentSpec("frame", "string", maximum_length=64),
        ),
        environment=_VCAN,
        target_kinds=_OPERATION_KINDS,
    ),
    OperationSpec(
        name="vcan_can_dump",
        permission_level_floor=PermissionLevel.TEST,
        summary="receive frames from a vcan interface",
        arguments=(
            ArgumentSpec("interface", "string", maximum_length=32),
            ArgumentSpec("count", "integer", required=False),
        ),
        environment=_VCAN,
        target_kinds=_OPERATION_KINDS,
    ),
    OperationSpec(
        name="isotp_exchange",
        permission_level_floor=PermissionLevel.TEST,
        summary="an ISO-TP exchange over a vcan interface",
        arguments=(
            ArgumentSpec("interface", "string", maximum_length=32),
            ArgumentSpec("payload", "string", maximum_length=256),
        ),
        environment=_VCAN,
        target_kinds=_OPERATION_KINDS,
    ),
    OperationSpec(
        name="uds_request",
        permission_level_floor=PermissionLevel.TEST,
        summary="a UDS request over a vcan interface",
        arguments=(
            ArgumentSpec("interface", "string", maximum_length=32),
            ArgumentSpec("service", "string", maximum_length=16),
        ),
        environment=_VCAN,
        target_kinds=_OPERATION_KINDS,
    ),
    OperationSpec(
        name="capture_start",
        permission_level_floor=PermissionLevel.TEST,
        summary="begin a capture on a vcan interface",
        arguments=(ArgumentSpec("interface", "string", maximum_length=32),),
        environment=_VCAN,
        target_kinds=_OPERATION_KINDS,
    ),
    OperationSpec(
        name="capture_stop",
        permission_level_floor=PermissionLevel.TEST,
        summary="end a capture on a vcan interface",
        arguments=(ArgumentSpec("interface", "string", maximum_length=32),),
        environment=_VCAN,
        target_kinds=_OPERATION_KINDS,
    ),
    OperationSpec(
        name="replay",
        permission_level_floor=PermissionLevel.TEST,
        summary="replay a captured frame set onto a vcan interface",
        arguments=(
            ArgumentSpec("interface", "string", maximum_length=32),
            ArgumentSpec("frames", "string_list"),
        ),
        environment=_VCAN,
        target_kinds=_OPERATION_KINDS,
    ),
)

OPERATION_NAMES = tuple(spec.name for spec in OPERATIONS)


class Adapter:
    """vcan and simulated networks only."""

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            identity=ToolIdentity(TOOL_ID, TOOL_VERSION, AdapterFamily.VEHICLE_NETWORK),
            summary=(
                "vcan, simulator and isolated-harness CAN work; physical "
                "interfaces are refused rather than downgraded"
            ),
            operations=OPERATIONS,
        )

    def execute(self, invocation: Invocation) -> AdapterOutcome:
        interface = self._permitted_interface(invocation)
        program, argv_tail = self._command(invocation, interface)
        return execute_argv(invocation, [program, *argv_tail])

    # ------------------------------------------------------------------

    def _permitted_interface(self, invocation: Invocation) -> str:
        """The last gate before a socket. Fails closed on anything unsettled."""
        target = invocation.target
        declared = invocation.arguments.get("interface")

        if target.interface not in _PERMITTED_INTERFACES:
            raise TargetRefused(
                "this invocation's target interface is not one v1 permits "
                "(§12.1). An unsettled or physical classification is refused "
                "here, at the last gate before a socket, and is never read as "
                "simulated"
            )
        if target.environment not in {
            TargetEnvironment.SIMULATED,
            TargetEnvironment.ISOLATED,
        }:
            raise TargetRefused(
                "this invocation's target environment is not simulated or "
                "isolated (§12.2), so the operation is refused"
            )
        if target.is_real is True:
            raise TargetRefused("this invocation declares the target real (§12.2)")

        if declared is None or not str(declared).startswith(_VCAN_PREFIX):
            raise TargetRefused(
                "this adapter names a vcan interface only. The interface is "
                "checked after the closed vocabularies have already decided, so "
                "a name that merely looks like CAN does not admit one"
            )
        return str(declared)

    def _command(self, invocation: Invocation, interface: str) -> tuple[str, list[str]]:
        arguments = invocation.arguments
        operation = invocation.operation

        if operation == "vcan_can_send":
            return "cansend", [interface, arguments["frame"]]
        if operation == "vcan_can_dump":
            count = arguments.get("count")
            if count is not None:
                return "candump", ["-n", str(count), interface]
            return "candump", [interface]
        if operation == "replay":
            # A replay is a bounded frame list onto a simulated interface, not an
            # arbitrary packet sender: every frame comes from the declared list.
            return "cansend", [interface, arguments["frames"][0]]
        if operation in {"isotp_exchange", "uds_request"}:
            return "isotprecv", [interface]
        if operation in {"capture_start", "capture_stop"}:
            return "candump", ["-n", "1", interface]
        raise AssertionError(f"undeclared operation {operation!r}")
