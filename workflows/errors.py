"""AI-13's refusal vocabulary.

The repository's rule, inherited rather than restated: a message names the field, the
rule, and at most a shape fact — never an interpolated value, because a message is a
place a value escapes to a log.

Two families, and the difference matters:

```text
InvalidRecord / InvalidDefinition   the artifact is not usable. A refusal, raised.
WorkflowRefused                     the workflow will not proceed, and the REASON is a
                                    terminal state the caller must record. A value
                                    carried by the run, not an exception to catch.
```

The second family exists because §18 gives AI-13-B an obligation it must discharge
with a NAMED reason rather than a crash: a definition declaring an approval step is
refused with `APPROVAL_STEP_NOT_IMPLEMENTED`, and a refusal a caller cannot see is a
refusal a caller cannot report.
"""

from __future__ import annotations

__all__ = [
    "InvalidCheckpoint",
    "InvalidDefinition",
    "InvalidRecord",
    "WorkflowRefused",
    "WorkflowsError",
]


class WorkflowsError(Exception):
    """Base class for an AI-13 refusal raised while validating an artifact."""

    reason_code: str = "WORKFLOW_ERROR"

    def __init__(self, message: str, *, reason_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if reason_code is not None:
            self.reason_code = reason_code


class InvalidRecord(WorkflowsError):
    """A record does not match the frozen shape — a field, a digest, a forbidden key."""

    reason_code = "INVALID_RECORD"


class InvalidDefinition(WorkflowsError):
    """A workflow definition is not usable (§5, §6, §12)."""

    reason_code = "INVALID_DEFINITION"


class InvalidCheckpoint(WorkflowsError):
    """A checkpoint is not usable, or carries something §7.2 forbids."""

    reason_code = "INVALID_CHECKPOINT"


class WorkflowRefused(WorkflowsError):
    """The workflow will not proceed, and the refusal is a declared reason code.

    Raised where the caller must SEE the refusal rather than merely fail: a definition
    declaring an approval step is refused by name (§18), and a caller that received a
    bare exception could not record which of AI-13's rules stopped it.
    """

    reason_code = "WORKFLOW_REFUSED"
