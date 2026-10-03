"""AI-13 §7 — the checkpoint. An immutable, DISPOSABLE resume snapshot.

```text
FROZEN: a checkpoint names (workflow_id, revision, definition_digest, run_id, step_id,
        attempt_no) and carries a digest of its own bytes.
FROZEN: a checkpoint is IMMUTABLE. Resume appends a new checkpoint; it never edits one.
```

### What a checkpoint may not carry, and why the scan is by NAME

§7.2 forbids a list of things that are not state: authorization, approval, context,
tool state, model selection, capability relaxation, raw output, secrets, repository
content, and an AI-05 record. Every one of those is a NAME a field would carry, so the
check is a name scan over every level of the mapping rather than a check on the fields
this module happens to know about.

```text
FROZEN: anything large or raw is stored OUTSIDE the checkpoint and referenced from it by
        reference and digest.
```

A scan that only looked at the top level would miss `{"step": {"guard_decision": ...}}`,
which is how a forbidden field actually arrives — not at the root, but nested inside
something that looks like ordinary state.

### Why this is not AI-05 Evidence

§7.3: a checkpoint is NOT an EvidenceRecord, MUST NOT be written as one, and MUST NOT be
reshaped into one. AI-05 admits six events from six named producers and a workflow
event is not among them; §22.2 REJECTS raw tool output outright. `record_digest` and
`evidence_id` are in the forbidden set below for that reason — not because a checkpoint
could not have those names, but because a record that HAS them is a record shaped like
the thing AI-05 owns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from workflows.canonical import digest_of, verify_digest
from workflows.errors import InvalidCheckpoint

__all__ = [
    "ARTIFACT_REF_KEYS",
    "CHECKPOINT_DIGEST_FIELD",
    "FORBIDDEN_KEYS",
    "ArtifactRef",
    "Checkpoint",
]

#: The one field §7.4 excludes from a checkpoint's preimage.
CHECKPOINT_DIGEST_FIELD = "checkpoint_digest"

#: §7.1. Everything a checkpoint may carry, and nothing else.
CHECKPOINT_KEYS = frozenset(
    {
        "workflow_id",
        "revision",
        "definition_digest",
        "run_id",
        "step_id",
        "attempt_no",
        "completed_steps",
        "artifact_refs",
        "created_at",
        CHECKPOINT_DIGEST_FIELD,
    }
)

#: An artifact is carried as a reference and a digest. Never as content (§7.2).
ARTIFACT_REF_KEYS = frozenset({"reference", "digest"})

#: §7.2. The names a forbidden thing would arrive under, checked at EVERY level.
FORBIDDEN_KEYS = frozenset(
    {
        # authorization
        "guard_decision", "guard", "decision_id", "allow", "authorization",
        "authorized", "permission", "capability_status", "capability",
        # approval (§13 — AI-13-B implements none of it)
        "approval", "approval_status", "approver", "approved", "scope_digest",
        # §13. AI-13-C's approval shapes. A checkpoint that could carry any of
        # these would be a resume snapshot carrying an authorization or a way back
        # into a wait — the one thing §7.2 keeps out of disposable state.
        "provenance", "actor_reference", "decided_at", "artifact_reference",
        # routing and model selection
        "router_decision", "routing_decision", "model_ref", "selected_model",
        "model_selection", "candidate_set", "route",
        # context
        "context", "context_response", "context_decision", "context_payload",
        "context_item",
        # tool state and results
        "tool_state", "tool_result", "tool_output", "tool_stdout", "tool_stderr",
        "tool_call", "tool_calls",
        # raw content of any kind
        "raw", "raw_output", "raw_log", "prompt", "prompt_body", "completion",
        "completion_body", "provider_response", "response_body", "stdout", "stderr",
        "diff", "diff_body", "file_content", "repository_content", "content",
        # secrets
        "credential", "credentials", "secret", "secrets", "token", "key", "api_key",
        "password", "private_key", "header", "headers",
        # AI-05's record shape
        "evidence_record", "evidence_id", "content_digest", "record_digest",
        "producer", "family",
    }
)


def _scan(value: object, where: str) -> None:
    """Walk the whole mapping, refusing a forbidden NAME at any depth."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = str(key)
            if name.lower() in FORBIDDEN_KEYS:
                raise InvalidCheckpoint(
                    f"{where}.{name} is a field a checkpoint MUST NOT carry (§7.2); it "
                    "is a resume snapshot, not an authorization record, not an approval, "
                    "not a tool or model result, and not evidence",
                    reason_code="CHECKPOINT_CARRIES_FORBIDDEN_STATE",
                )
            _scan(item, f"{where}.{name}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _scan(item, f"{where}[{index}]")


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidCheckpoint(f"{where} must be an object")
    return value


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidCheckpoint(f"{where} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """§7.2. A reference and a digest. The bytes live outside."""

    reference: str
    digest: str

    @classmethod
    def from_mapping(cls, raw: object, where: str) -> "ArtifactRef":
        data = _mapping(raw, where)
        unknown = set(data) - ARTIFACT_REF_KEYS
        if unknown:
            raise InvalidCheckpoint(
                f"{where} carries {', '.join(sorted(map(str, unknown)))}; an artifact is "
                "referenced by a reference and a digest, and a third field is how its "
                "bytes would arrive (§7.2)",
                reason_code="CHECKPOINT_CARRIES_FORBIDDEN_STATE",
            )
        return cls(
            reference=_text(data.get("reference"), f"{where}.reference"),
            digest=_text(data.get("digest"), f"{where}.digest"),
        )

    def to_body(self) -> dict[str, Any]:
        return {"reference": self.reference, "digest": self.digest}


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """§7.1. Immutable, disposable, and bound to exactly one attempt."""

    workflow_id: str
    revision: str
    definition_digest: str
    run_id: str
    step_id: str
    attempt_no: int
    completed_steps: tuple[str, ...]
    created_at: str
    checkpoint_digest: str
    artifact_refs: tuple[ArtifactRef, ...] = ()

    @classmethod
    def from_mapping(cls, raw: object, *, verify: bool = True) -> "Checkpoint":
        data = _mapping(raw, "checkpoint")

        # The forbidden scan runs FIRST and over the whole mapping: a forbidden field is
        # a more important finding than an unknown one, and reporting "unknown field
        # guard_decision" would name the shape and not the rule.
        _scan(data, "checkpoint")

        unknown = set(data) - CHECKPOINT_KEYS
        if unknown:
            raise InvalidCheckpoint(
                f"checkpoint has field(s) the contract does not define: "
                f"{', '.join(sorted(map(str, unknown)))}"
            )

        attempt_no = data.get("attempt_no")
        if isinstance(attempt_no, bool) or not isinstance(attempt_no, int) or attempt_no < 1:
            raise InvalidCheckpoint(
                "checkpoint.attempt_no must be an integer >= 1; §6.3 starts an attempt "
                "count at 1 and increases it by exactly 1"
            )

        completed = data.get("completed_steps", [])
        if isinstance(completed, (str, bytes)) or not isinstance(completed, Sequence):
            raise InvalidCheckpoint("checkpoint.completed_steps must be a list")
        completed_steps = tuple(_text(entry, "checkpoint.completed_steps[]") for entry in completed)

        raw_refs = data.get("artifact_refs", [])
        if isinstance(raw_refs, (str, bytes)) or not isinstance(raw_refs, Sequence):
            raise InvalidCheckpoint("checkpoint.artifact_refs must be a list")
        artifact_refs = tuple(
            ArtifactRef.from_mapping(entry, f"checkpoint.artifact_refs[{index}]")
            for index, entry in enumerate(raw_refs)
        )

        checkpoint = cls(
            workflow_id=_text(data.get("workflow_id"), "checkpoint.workflow_id"),
            revision=_text(data.get("revision"), "checkpoint.revision"),
            definition_digest=_text(
                data.get("definition_digest"), "checkpoint.definition_digest"
            ),
            run_id=_text(data.get("run_id"), "checkpoint.run_id"),
            step_id=_text(data.get("step_id"), "checkpoint.step_id"),
            attempt_no=attempt_no,
            completed_steps=completed_steps,
            created_at=_text(data.get("created_at"), "checkpoint.created_at"),
            checkpoint_digest=_text(
                data.get(CHECKPOINT_DIGEST_FIELD), f"checkpoint.{CHECKPOINT_DIGEST_FIELD}"
            ),
            artifact_refs=artifact_refs,
        )
        if verify:
            checkpoint.verify_digest()
        return checkpoint

    @property
    def body(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "revision": self.revision,
            "definition_digest": self.definition_digest,
            "run_id": self.run_id,
            "step_id": self.step_id,
            "attempt_no": self.attempt_no,
            "completed_steps": list(self.completed_steps),
            "artifact_refs": [ref.to_body() for ref in self.artifact_refs],
            "created_at": self.created_at,
        }

    @property
    def computed_digest(self) -> str:
        return digest_of(
            {**self.body, CHECKPOINT_DIGEST_FIELD: ""}, digest_field=CHECKPOINT_DIGEST_FIELD
        )

    def verify_digest(self) -> None:
        """§7.4 and §8.1. A checkpoint that does not verify is `CHECKPOINT_CORRUPT`."""
        verify_digest(
            {**self.body, CHECKPOINT_DIGEST_FIELD: self.checkpoint_digest},
            digest_field=CHECKPOINT_DIGEST_FIELD,
            reason_code="CHECKPOINT_CORRUPT",
        )

    def to_mapping(self) -> dict[str, Any]:
        return {**self.body, CHECKPOINT_DIGEST_FIELD: self.checkpoint_digest}
