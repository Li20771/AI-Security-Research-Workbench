"""AI-08 §7 — the execution request, and the execution identity.

**Descriptors only.** A request carries no `ContextResponse`, no credential, no
tool argument and no Guard decision. §7.3 refuses them by name for the same
reason AI-04 §4 and AI-07 §5.3 refuse them at their own boundaries: a field
nobody defined is a field a credential can ride in on.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from agents.vocabulary import AgentId, resolve_agent

__all__ = ["AgentExecutionRequest", "new_execution_id"]

_TOP_KEYS = frozenset(
    {
        "schema_version",
        "agent_id",
        "workspace",
        "task",
        "input",
        "context",
    }
)

#: Fields refused by name, so the refusal says *why* rather than "unknown field".
_REFUSED_KEYS = frozenset(
    {
        # §7.3: the request carries no ContextResponse. Two competing semantics
        # — "the request carries context" and "the execution establishes
        # context" — cannot both hold, and AI-08-A Amendment 1 settled which.
        "context_response", "contextresponse", "response",
        # §7.3: no credential reaches this boundary.
        "api_key", "apikey", "token", "credential", "secret", "password",
        "headers", "authorization", "bearer",
        # §7.3: no tool argument reaches this boundary either.
        "arguments", "tool_args", "tool_arguments", "command",
        # §10: a result is not an input. I3, stated as a refusal.
        "agent_result", "result", "previous_result", "other_result",
    }
)

_CONTEXT_KEYS = frozenset({"descriptor"})


def new_execution_id() -> str:
    """§7.2. A new opaque `ExecutionId`.

    Opaque by construction: the value encodes no agent, no workspace, no task,
    no timestamp and no outcome, so nothing can be parsed out of one. A reader
    that wants to know which Agent ran reads `agent_id`, not this.

    Created per execution, never reused, never derived from another execution's
    id (§7.2). The `ex-` prefix is a label, not a namespace that encodes
    anything.
    """
    return f"ex-{uuid.uuid4().hex[:16]}"


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{where} must be an object")
    return value


def _text(value: object, where: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where} must be a non-empty string")
    if len(value) > maximum:
        raise ValueError(f"{where} must be at most {maximum} characters")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{where} must be a single line")
    return value


@dataclass(frozen=True, slots=True)
class AgentExecutionRequest:
    """§7.3. The complete execution input, minus the body and minus the policy.

    It carries **no** `ContextResponse`. The execution runtime establishes one
    ContextResponse for the execution and the execution owns it (§8.1); a
    `ContextResponse` supplied here is REFUSED rather than ignored, because
    accepting one would restore the competing semantics Amendment 1 removed.
    """

    agent_id: AgentId
    workspace_root: str
    task: str
    input_digest: str
    context_descriptor: str | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        """Resolve the identity through `resolve_agent`, at construction (§6.2).

        **This is the fix for a real defect.** Until it existed, the annotation
        said `AgentId` but nothing enforced it: a dataclass does not check
        annotations, so `AgentExecutionRequest(agent_id="not-registered", ...)`
        constructed happily. Two things then went wrong, both reproduced:

        ```text
        BLOCKED path    the runtime returns before it builds a ToolGateway, so
                        an AgentResult was produced whose declared identity was
                        'not-registered' — a result attributed to no registered
                        Agent.
        COMPLETED path  ToolGateway.__init__ called AgentId(...) on the way past,
                        so a ValueError escaped execute() entirely — breaking
                        §7.1.1, one terminal result per execution.
        ```

        The constructor now calls the SAME boundary the rest of the layer uses
        rather than adding a second identity rule beside it, so §6.2's claim
        that `resolve_agent` is the only place a candidate becomes an `AgentId`
        is structural instead of aspirational. An unregistered candidate is
        refused before an execution is accepted, not partway through one.

        A frozen dataclass needs `object.__setattr__`; the value written is
        always an `AgentId`, so the field cannot hold anything else afterwards.
        """
        object.__setattr__(self, "agent_id", resolve_agent(self.agent_id))

    @classmethod
    def from_mapping(cls, raw: object) -> "AgentExecutionRequest":
        if not isinstance(raw, Mapping):
            raise ValueError("request must be an object")

        refused = _REFUSED_KEYS & set(raw)
        if refused:
            raise ValueError(
                "this request carries a field the contract does not define: "
                f"{', '.join(sorted(refused))}. §7.3 fixes the request shape — a "
                "ContextResponse, a credential, a tool argument or another "
                "execution's result is refused rather than ignored"
            )

        unknown = set(raw) - _TOP_KEYS
        if unknown:
            raise ValueError(
                "request has field(s) the contract does not define: "
                f"{', '.join(sorted(map(str, unknown)))}"
            )

        if raw.get("schema_version") != 1:
            raise ValueError(
                f"schema_version {raw.get('schema_version')!r} is not supported; "
                "this contract defines 1"
            )

        # Through the one boundary, as the constructor is. `UnknownAgent` is a
        # `ValueError`, so the raw boundary keeps refusing malformed input with
        # the same exception type it always did — and the refusal message comes
        # from `resolve_agent` rather than from a second copy of the rule here.
        agent_id = resolve_agent(raw.get("agent_id"))

        workspace = _mapping(raw.get("workspace"), "workspace")
        workspace_unknown = set(workspace) - {"root"}
        if workspace_unknown:
            raise ValueError(
                "workspace has field(s) the contract does not define: "
                f"{', '.join(sorted(map(str, workspace_unknown)))}"
            )
        workspace_root = _text(workspace.get("root"), "workspace.root", maximum=4096)

        context_descriptor = None
        if raw.get("context") is not None:
            context = _mapping(raw.get("context"), "context")
            context_unknown = set(context) - _CONTEXT_KEYS
            if context_unknown:
                raise ValueError(
                    "context has field(s) the contract does not define: "
                    f"{', '.join(sorted(map(str, context_unknown)))}. §7.3 allows "
                    "a context DESCRIPTOR and nothing else; a ContextResponse "
                    "is an output of the execution, never a request input"
                )
            context_descriptor = _text(
                context.get("descriptor"), "context.descriptor", maximum=512
            )

        return cls(
            agent_id=agent_id,
            workspace_root=workspace_root,
            task=_text(raw.get("task"), "task", maximum=128),
            input_digest=_text(raw.get("input"), "input", maximum=128),
            context_descriptor=context_descriptor,
        )

    def to_mapping(self) -> dict[str, Any]:
        """The request's own descriptors, as an **explicit allowlist**.

        `dataclasses.asdict` would put every field into a record, so a field
        added later would reach an auditable artefact without anyone deciding
        it should.
        """
        return {
            "schema_version": self.schema_version,
            "agent_id": str(self.agent_id),
            "workspace": {"root": self.workspace_root},
            "task": self.task,
            "input": self.input_digest,
            "context": (
                None
                if self.context_descriptor is None
                else {"descriptor": self.context_descriptor}
            ),
        }
