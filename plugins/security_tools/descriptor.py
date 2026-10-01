"""Tool descriptors and the argument schema (contract §7).

A descriptor answers *what is this tool, what can it do, and what does it need*
— and nothing about whether it may run. **The registry describes; Guard
authorizes; the adapter executes** (§7.4, §10 of the brief).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from plugins.security_tools.errors import ToolRequestMalformed
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.vocabulary import (
    FilesystemAccess,
    PermissionLevel,
    TargetKind,
    VehicleInterface,
)

__all__ = [
    "ArgumentSpec",
    "EnvironmentRequirement",
    "OperationSpec",
    "ToolDescriptor",
]

#: The argument types the v1 schema vocabulary can enforce (contract §7.3).
#: Deliberately small: a general-purpose validation framework is not adopted for
#: v1, and a schema AI-06 cannot enforce is not a schema.
ARGUMENT_TYPES = ("string", "integer", "boolean", "string_list")


@dataclass(frozen=True, slots=True)
class ArgumentSpec:
    """One declared argument (contract §7.3)."""

    name: str
    type: str
    required: bool = True
    summary: str = ""
    choices: tuple[str, ...] = ()
    maximum_length: int | None = None

    def validate(self, value: object, where: str) -> None:
        """Refuse a value the declaration does not admit.

        Messages name the field and the expectation, and never echo the value:
        an argument is where a credential can live, and an error message is a
        place a value escapes to a log.
        """
        if self.type == "string":
            if not isinstance(value, str):
                raise ToolRequestMalformed(f"{where} must be a string")
            if self.maximum_length is not None and len(value) > self.maximum_length:
                raise ToolRequestMalformed(
                    f"{where} must be at most {self.maximum_length} characters"
                )
            if "\n" in value or "\r" in value:
                raise ToolRequestMalformed(f"{where} must be a single line")
            if self.choices and value not in self.choices:
                raise ToolRequestMalformed(
                    f"{where} must be one of {sorted(self.choices)}"
                )
        elif self.type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ToolRequestMalformed(f"{where} must be an integer")
        elif self.type == "boolean":
            if not isinstance(value, bool):
                raise ToolRequestMalformed(f"{where} must be true or false")
        elif self.type == "string_list":
            if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
                raise ToolRequestMalformed(f"{where} must be a list of strings")
            for entry in value:
                if not isinstance(entry, str):
                    raise ToolRequestMalformed(f"{where} must contain only strings")
        else:  # pragma: no cover - construction guards this
            raise ToolRequestMalformed(f"{where} has an undeclared type")


@dataclass(frozen=True, slots=True)
class EnvironmentRequirement:
    """What an operation needs in order to run at all (contract §7.2).

    A description, used by the registry to answer questions. It is **not** a
    grant, and `subprocess` being `True` here does not authorize a process —
    Guard does (§9.1).
    """

    filesystem: FilesystemAccess = FilesystemAccess.NONE
    subprocess: bool = False
    network: bool = False
    vehicle_interface: VehicleInterface = VehicleInterface.NONE

    def to_mapping(self) -> dict[str, Any]:
        return {
            "filesystem": str(self.filesystem),
            "subprocess": self.subprocess,
            "network": self.network,
            "vehicle_interface": str(self.vehicle_interface),
        }


@dataclass(frozen=True, slots=True)
class OperationSpec:
    """One declared operation (contract §7.2).

    `permission_level_floor` **describes** the operation. It is not the
    request's `permission_level` and MUST NOT be used to derive it (§6.2): the
    caller supplies the level, and the floor exists so that a caller asking for
    `git.log` at `modify` has a visible mismatch rather than a silent one.
    """

    name: str
    permission_level_floor: PermissionLevel
    summary: str
    arguments: tuple[ArgumentSpec, ...] = ()
    target_kinds: tuple[TargetKind, ...] = ()
    environment: EnvironmentRequirement = field(default_factory=EnvironmentRequirement)
    may_modify_workspace: bool = False
    produces_artifacts: bool = False
    #: The exit codes that mean the operation COMPLETED (contract §11.5).
    #: Declared per operation because the semantics genuinely vary: a search
    #: tool reports "no match" through its status, and a test runner reports
    #: failing tests through one. Any other exit code is FAILED.
    expected_exit_codes: frozenset[int] = frozenset({0})

    def argument(self, name: str) -> ArgumentSpec | None:
        for spec in self.arguments:
            if spec.name == name:
                return spec
        return None

    def validate_arguments(self, raw: object, where: str = "arguments") -> dict[str, Any]:
        """Refuse an undeclared argument, a missing required one, or a bad type.

        An argument the schema does not define is refused rather than ignored
        (§7.3). This runs **before** Guard is asked, so a malformed invocation
        never reaches the evaluator.
        """
        if raw is None:
            data: Mapping[str, Any] = {}
        elif isinstance(raw, Mapping):
            data = raw
        else:
            raise ToolRequestMalformed(f"{where} must be an object")

        declared = {spec.name for spec in self.arguments}
        unknown = set(data) - declared
        if unknown:
            raise ToolRequestMalformed(
                f"{where} has argument(s) this operation does not declare: "
                f"{', '.join(sorted(map(str, unknown)))}"
            )

        validated: dict[str, Any] = {}
        for spec in self.arguments:
            if spec.name not in data:
                if spec.required:
                    raise ToolRequestMalformed(
                        f"{where}.{spec.name} is required by this operation"
                    )
                continue
            spec.validate(data[spec.name], f"{where}.{spec.name}")
            validated[spec.name] = data[spec.name]
        return validated


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """What a tool is and what it declares (contract §7.1).

    Everything here is a description. Nothing here is a permission.
    """

    identity: ToolIdentity
    summary: str
    operations: tuple[OperationSpec, ...]

    def operation(self, name: str) -> OperationSpec | None:
        for spec in self.operations:
            if spec.name == name:
                return spec
        return None

    @property
    def capability_names(self) -> tuple[str, ...]:
        """§5.4: the declared operation names. A description, not a grant."""
        return tuple(spec.name for spec in self.operations)

    @property
    def needs_network(self) -> bool:
        """Whether any declared operation can reach a network (§16)."""
        return any(spec.environment.network for spec in self.operations)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "tool": self.identity.to_mapping(),
            "summary": self.summary,
            "operations": [
                {
                    "name": spec.name,
                    "permission_level_floor": str(spec.permission_level_floor),
                    "summary": spec.summary,
                    "target_kinds": [str(kind) for kind in spec.target_kinds],
                    "environment": spec.environment.to_mapping(),
                    "may_modify_workspace": spec.may_modify_workspace,
                    "produces_artifacts": spec.produces_artifacts,
                    "expected_exit_codes": sorted(spec.expected_exit_codes),
                }
                for spec in self.operations
            ],
        }
