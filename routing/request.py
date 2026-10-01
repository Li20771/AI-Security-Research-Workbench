"""The RouterRequest. Contract §5.

**Descriptors only.** A request carries no prompt body, no message content, no
tool arguments and no credential: AI-07 routes on what a task *is*, not on what
it says. §5.3 refuses content for the same reason AI-04 §4 does — a field nobody
defined is a field a credential can ride in on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from plugins.guard.vocabulary import ActorType, PermissionLevel

from providers.model_profile import CapabilityName
from providers.profile import ModelRef, ProfileError

from routing.errors import InvalidRequest

__all__ = ["RouterRequest"]

_TOP_KEYS = frozenset(
    {
        "schema_version",
        "task",
        "workspace",
        "requested_capability",
        "modality",
        "constraints",
        "sensitivity",
        "require_independence",
        "actor",
        "candidates",
    }
)

#: Fields refused by name, so the refusal says *why* rather than "unknown field".
_CONTENT_KEYS = frozenset(
    {
        "prompt", "messages", "message", "content", "body", "text",
        "tool_args", "tool_arguments", "arguments", "command",
        "api_key", "token", "credential", "secret", "headers", "authorization",
    }
)

#: Contract §6.4: AI-02 exposes no cost-class vocabulary, so a cost-class
#: constraint is refused rather than silently ignored. The name is listed here
#: only so the refusal is specific.
_DEFERRED_CONSTRAINT_KEYS = frozenset({"max_cost_class", "cost_class"})


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidRequest(f"{where} must be an object")
    return value


def _closed(raw: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise InvalidRequest(
            f"{where} has field(s) the contract does not define: "
            f"{', '.join(sorted(map(str, unknown)))}"
        )


def _text_or_none(value: object, where: str, *, maximum: int = 512) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise InvalidRequest(f"{where} must be a non-empty string or null")
    if len(value) > maximum:
        raise InvalidRequest(f"{where} must be at most {maximum} characters")
    if "\n" in value or "\r" in value:
        raise InvalidRequest(f"{where} must be a single line")
    return value


@dataclass(frozen=True, slots=True)
class RouterRequest:
    """§5.1. The complete routing input, minus the rules and minus the registry.

    `sensitivity` is **carried and recorded and changes nothing** (§5.2): it does
    not authorize, and it neither widens nor narrows eligibility in v1, because
    AI-02 has no field it could be compared against.
    """

    task_class: str
    workspace_id: str
    actor_id: str
    actor_type: ActorType
    candidates: tuple[str, ...]
    task_summary: str | None = None
    requested_capability: str | None = None
    modality: str | None = None
    max_latency_class: str | None = None
    sensitivity: PermissionLevel | None = None
    require_independence: bool = False
    schema_version: int = 1

    @classmethod
    def from_mapping(cls, raw: object) -> "RouterRequest":
        if not isinstance(raw, Mapping):
            raise InvalidRequest("request must be an object")

        # Content is refused before shape, so the refusal names the real problem.
        present_content = _CONTENT_KEYS & set(raw)
        if present_content:
            raise InvalidRequest(
                "this request carries content the contract does not define: "
                f"{', '.join(sorted(present_content))}. AI-07 routes on descriptors "
                "(§5.3); a prompt body, a tool argument or a credential is refused "
                "rather than ignored"
            )

        _closed(raw, _TOP_KEYS, "request")

        if raw.get("schema_version") != 1:
            raise InvalidRequest(
                f"schema_version {raw.get('schema_version')!r} is not supported; "
                "this contract defines 1"
            )

        task = _mapping(raw.get("task"), "task")
        _closed(task, frozenset({"task_class", "summary"}), "task")
        task_class = _text_or_none(task.get("task_class"), "task.task_class", maximum=64)
        if task_class is None:
            raise InvalidRequest("task.task_class is required")

        workspace = _mapping(raw.get("workspace"), "workspace")
        _closed(workspace, frozenset({"workspace_id"}), "workspace")
        workspace_id = workspace.get("workspace_id")
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise InvalidRequest("workspace.workspace_id must be non-empty")

        constraints = raw.get("constraints", {})
        if not isinstance(constraints, Mapping):
            raise InvalidRequest("constraints must be an object")
        deferred = _DEFERRED_CONSTRAINT_KEYS & set(constraints)
        if deferred:
            raise InvalidRequest(
                f"constraints.{sorted(deferred)[0]}: AI-02 defines no cost-class "
                "vocabulary, so cost-class routing is DEFERRED in AI-07 v1 (§6.4). "
                "The constraint is refused rather than silently ignored, and AI-07 "
                "does not invent a class of its own"
            )
        _closed(constraints, frozenset({"max_latency_class"}), "constraints")

        actor = _mapping(raw.get("actor"), "actor")
        _closed(actor, frozenset({"id", "type"}), "actor")
        actor_id = actor.get("id")
        if not isinstance(actor_id, str) or not actor_id:
            raise InvalidRequest("actor.id must be a non-empty string")
        try:
            actor_type = ActorType(actor.get("type"))
        except ValueError:
            raise InvalidRequest("actor.type is not one of AI-04's ActorType members") from None

        independence = raw.get("require_independence", False)
        if not isinstance(independence, bool):
            raise InvalidRequest("require_independence must be true or false")

        sensitivity_raw = raw.get("sensitivity")
        sensitivity = None
        if sensitivity_raw is not None:
            try:
                sensitivity = PermissionLevel(sensitivity_raw)
            except ValueError:
                raise InvalidRequest(
                    "sensitivity is not one of AI-04's six permission levels"
                ) from None

        raw_candidates = raw.get("candidates")
        if isinstance(raw_candidates, (str, bytes)) or not isinstance(raw_candidates, Sequence):
            raise InvalidRequest("candidates must be a list")
        candidates: list[str] = []
        for entry in raw_candidates:
            # §5.1 declares `candidates: [{model_ref: string}]`. A bare string is
            # refused rather than accepted as a convenience: the shape is frozen,
            # and a lenient reader is a reader that accepts the next thing too.
            if not isinstance(entry, Mapping):
                raise InvalidRequest(
                    "every candidate must be an object of the form "
                    "{'model_ref': 'provider_id/model_id'}; a bare string is not the "
                    "declared shape (§5.1)"
                )
            unknown_entry = set(entry) - {"model_ref"}
            if unknown_entry:
                raise InvalidRequest(
                    "candidates[] has field(s) the contract does not define: "
                    f"{', '.join(sorted(map(str, unknown_entry)))}"
                )
            try:
                candidates.append(str(ModelRef.parse(entry.get("model_ref"))))
            except ProfileError:
                raise InvalidRequest(
                    "every candidate must be a model reference of the form "
                    "provider_id/model_id"
                ) from None
        if not candidates:
            raise InvalidRequest("candidates must name at least one model reference")

        # §5.1: `requested_capability` is one of AI-02's CapabilityName members.
        # An unknown name is INVALID_REQUEST at the boundary, not a routing miss
        # later: an unlisted value is never treated as an ordinary one.
        capability = _text_or_none(
            raw.get("requested_capability"), "requested_capability", maximum=64
        )
        if capability is not None:
            try:
                CapabilityName(capability)
            except ValueError:
                raise InvalidRequest(
                    "requested_capability is not one of AI-02's capability names; "
                    "an unlisted capability is refused at the request boundary "
                    "rather than routed on as an ordinary one (§5.1)"
                ) from None

        return cls(
            task_class=task_class,
            workspace_id=workspace_id,
            actor_id=actor_id,
            actor_type=actor_type,
            candidates=tuple(candidates),
            task_summary=_text_or_none(task.get("summary"), "task.summary"),
            requested_capability=capability,
            modality=_text_or_none(raw.get("modality"), "modality", maximum=32),
            max_latency_class=_text_or_none(
                constraints.get("max_latency_class"), "constraints.max_latency_class", maximum=32
            ),
            sensitivity=sensitivity,
            require_independence=independence,
        )

    @property
    def ordered_candidates(self) -> tuple[str, ...]:
        """The candidate set, sorted. Contract §7.5.

        The Router never reads the caller's order: permuting `candidates` must not
        change the decision, so the sequence is derived here rather than trusted.
        """
        return tuple(sorted(self.candidates))

    def to_mapping(self) -> dict[str, Any]:
        """The request's own descriptors, for the decision record (§13.3).

        An **explicit allowlist**. Serialising the dataclass would mean a field
        added later enters the record without anyone deciding it should.
        """
        return {
            "task_class": self.task_class,
            "task_summary": self.task_summary,
            "workspace_id": self.workspace_id,
            "requested_capability": self.requested_capability,
            "modality": self.modality,
            "max_latency_class": self.max_latency_class,
            "sensitivity": None if self.sensitivity is None else str(self.sensitivity),
            "require_independence": self.require_independence,
            "actor": {"id": self.actor_id, "type": str(self.actor_type)},
            "candidates": list(self.ordered_candidates),
        }
