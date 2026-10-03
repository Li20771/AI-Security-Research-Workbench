"""AI-13 §8 — resume integrity, and the short list of what a resume may inherit.

```text
FROZEN: resume requires ALL of, verified before an attempt is created:
            workflow_id and revision match
            definition_digest matches
            workspace identity matches EXACTLY
            the checkpoint's own digest is intact
FROZEN: any mismatch is a terminal state for the run, named for the mismatch. None is
        retryable and none is repaired by choosing the closer of two values.
```

### What a resumed attempt inherits

```text
FROZEN: a new attempt inherits DECLARED STATE ONLY — which steps completed, their
        declared outcomes, and artifact references.
```

`InheritedState` has exactly two fields, and that is the point: the list of things a
resume may NOT carry is long — authorization, an approval, a context payload, tool
state, a model selection, a RouterDecision, a capability status — and a structure with
two fields cannot carry any of them. A seventh field would have to be added
deliberately, and a test asserts the field set for exactly that reason.

### What resume does NOT re-derive

```text
FROZEN: v1 has NO re-derivation. A workspace identity that differs in any way is
        `WORKSPACE_CHANGED` and the run is terminal.
```

There is no "re-derived and therefore equivalent" path here, because defining what would
make two workspaces equivalent is a mechanism with no requirement behind it yet.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from workflows.checkpoint import ArtifactRef, Checkpoint
from workflows.definition import WorkflowDefinition
from workflows.errors import InvalidCheckpoint
from workflows.run import RunRecord
from workflows.vocabulary import WorkflowState

__all__ = ["INHERITED_FIELDS", "InheritedState", "ResumeCheck", "inherited_state", "verify_resume"]

#: §8.2. The complete list. A structure with these two fields cannot carry a third
#: thing, and `tests/workflows` asserts the set so a third cannot arrive quietly.
INHERITED_FIELDS = ("completed_steps", "artifact_refs")


@dataclass(frozen=True, slots=True)
class InheritedState:
    """Exactly what a resumed attempt receives, and nothing else (§8.2)."""

    completed_steps: tuple[str, ...]
    artifact_refs: tuple[ArtifactRef, ...] = ()


@dataclass(frozen=True, slots=True)
class ResumeCheck:
    """Whether a resume may proceed, and the terminal state when it may not."""

    allowed: bool
    reason_code: str = ""
    terminal_state: WorkflowState | None = None
    detail: str = ""


def verify_resume(
    *,
    definition: WorkflowDefinition,
    run: RunRecord,
    checkpoint: Checkpoint,
    workspace_identity: str,
) -> ResumeCheck:
    """§8.1. Every binding is checked BEFORE an attempt is created.

    The checkpoint's own digest is verified first, because a checkpoint that does not
    verify cannot tell us anything about the other three: reading its fields to compare
    them would be reading values that already failed their integrity check.
    """
    try:
        checkpoint.verify_digest()
    except Exception:  # noqa: BLE001 - the refusal is the finding, and it is re-issued
        return ResumeCheck(
            allowed=False,
            reason_code="CHECKPOINT_CORRUPT",
            terminal_state=WorkflowState.CHECKPOINT_CORRUPT,
            detail="the checkpoint's digest does not verify against §7.4's preimage",
        )

    if checkpoint.run_id != run.run_id:
        # Not one of §8.1's three: those describe a run meeting a changed world, and
        # this is a caller handing over an artifact that belongs to a different run.
        # Calling it "corrupt" would name the wrong fact about a well-formed record.
        raise InvalidCheckpoint(
            "the checkpoint belongs to a different run; a resume is a run meeting its "
            "OWN snapshot, and a snapshot from another run is not a mismatch of the "
            "definition, the workspace or the digest",
            reason_code="CHECKPOINT_FOR_ANOTHER_RUN",
        )

    if checkpoint.workflow_id != definition.workflow_id:
        return ResumeCheck(
            allowed=False,
            reason_code="DEFINITION_CHANGED",
            terminal_state=WorkflowState.DEFINITION_CHANGED,
            detail="the checkpoint names a different workflow",
        )

    if checkpoint.revision != definition.revision:
        # §5. A definition that changed may have changed what a completed step MEANT,
        # and a resumed run whose earlier steps were interpreted by different rules is
        # a run whose record cannot be read.
        return ResumeCheck(
            allowed=False,
            reason_code="DEFINITION_CHANGED",
            terminal_state=WorkflowState.DEFINITION_CHANGED,
            detail="the checkpoint's revision is not the definition's revision",
        )

    if checkpoint.definition_digest != definition.definition_digest:
        # Checked separately from the revision string on purpose: a revision is a label
        # its author chose, and the digest is the bytes. Two definitions can share a
        # revision and differ, and only the digest catches that.
        return ResumeCheck(
            allowed=False,
            reason_code="DEFINITION_CHANGED",
            terminal_state=WorkflowState.DEFINITION_CHANGED,
            detail="the checkpoint's definition digest is not the definition's",
        )

    if run.definition_digest != definition.definition_digest:
        return ResumeCheck(
            allowed=False,
            reason_code="DEFINITION_CHANGED",
            terminal_state=WorkflowState.DEFINITION_CHANGED,
            detail="the RUN was created against a different definition digest",
        )

    if run.workspace_identity != workspace_identity:
        # The RUN is where the identity it started under is recorded (§15.2); the
        # checkpoint names its run, not its workspace. Comparing a caller-supplied value
        # against the run's own is the only comparison that means anything, because a
        # checkpoint that could assert its own workspace could also assert a different
        # one and pass.
        return ResumeCheck(
            allowed=False,
            reason_code="WORKSPACE_CHANGED",
            terminal_state=WorkflowState.WORKSPACE_CHANGED,
            detail="the workspace identity is not the one this run started under",
        )

    if definition.step(checkpoint.step_id) is None:
        raise InvalidCheckpoint(
            f"the checkpoint names step {checkpoint.step_id!r}, which is not in the "
            "definition; a resume cannot continue a step the workflow does not declare",
            reason_code="CHECKPOINT_NAMES_AN_UNKNOWN_STEP",
        )

    return ResumeCheck(allowed=True)


def inherited_state(checkpoint: Checkpoint) -> InheritedState:
    """§8.2. The DECLARED STATE a resumed attempt receives, and nothing else.

    Everything the checkpoint carries that is not on this list stays where it is: a
    checkpoint cannot hand an attempt an authorization, an approval, a context, tool
    state or a model selection, because this function does not return one and the
    structure it returns could not hold one.
    """
    return InheritedState(
        completed_steps=checkpoint.completed_steps,
        artifact_refs=checkpoint.artifact_refs,
    )


def inherited_field_names() -> tuple[str, ...]:
    """The field set of `InheritedState`, for the test that asserts it (§8.2)."""
    return tuple(field.name for field in fields(InheritedState))


def as_mapping(state: InheritedState) -> dict[str, Any]:
    """A mapping of the inherited state, for a reader or a log line."""
    return {
        "completed_steps": list(state.completed_steps),
        "artifact_refs": [ref.to_body() for ref in state.artifact_refs],
    }
