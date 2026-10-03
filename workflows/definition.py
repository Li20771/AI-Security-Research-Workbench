"""AI-13 §5, §6, §12, §18 — the workflow definition and its identity.

```text
WorkflowDefinition   a TRACKED artifact under workflows/definitions/, reviewed and
                     versioned in Git. Never generated, never fetched, never
                     discovered at runtime.
```

### What a step may name

§6.1: a step names an EXISTING seam. AI-13-B admits one, and refuses the other:

```text
AGENT_EXECUTION   the step runs an AI-08 execution. AI-13 composes it; it does not
                  implement it. A tool invocation is reached THROUGH that execution,
                  on AI-06's single path — AI-13 never calls a tool, so there is no
                  TOOL_INVOCATION kind here to call one with.
APPROVAL          REFUSED, by name. §18: AI-13-B implements no approval semantics,
                  and half an approval point — a step waiting on a gate nothing
                  opens — is the unbounded state §16 forbids.
```

### A declared bound is a RUNTIME, not a date

```text
Definition = tracked policy data    a duration, reviewed and versioned in Git
RunRecord  = runtime authority      the ABSOLUTE deadline, computed once at creation
```

§8.3 makes the workflow deadline an absolute instant, computed ONCE and persisted. None
of the bounds in this module is an instant: the limits say how long a run and a step may
take, and the retry policy says how long its retries may take. A tracked definition
carrying a date would hand a run a deadline it INHERITED rather than one it was GIVEN —
and a definition amended after a run started could move that run's deadline underneath
it, which is the opposite of what a bound that survives a resume means.

### Why the digest is computed here rather than accepted

`definition_digest` is what a run binds to and what a resume is checked against (§8.1).
A digest accepted from the caller would let the caller decide whether two definitions
are the same definition, which is the one question the digest exists to answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from workflows.canonical import digest_of
from workflows.errors import InvalidDefinition
from workflows.vocabulary import FailureClass

__all__ = [
    "DIGEST_FIELD",
    "MAX_ARTIFACT_BYTES_CEILING",
    "RetryPolicy",
    "ResourceLimits",
    "StepKind",
    "WorkflowDefinition",
    "WorkflowStep",
]

#: The one field §7.4 excludes from the preimage, named once.
DIGEST_FIELD = "definition_digest"

#: A sanity ceiling, not a policy: a bound so large that no run could reach it is a
#: bound nobody declared on purpose, and §12 refuses "a limit nobody wrote down".
MAX_ARTIFACT_BYTES_CEILING = 1 << 40

_DEFINITION_KEYS = frozenset(
    {"workflow_id", "revision", "steps", "limits", "retry_policy", DIGEST_FIELD}
)
_STEP_KEYS = frozenset({"step_id", "kind", "timeout_seconds", "approval_seconds"})
_LIMIT_KEYS = frozenset(
    {
        "workflow_seconds",
        "step_seconds",
        "attempts_per_step",
        "attempts_total",
        "max_checkpoints",
        "max_checkpoint_bytes",
        "max_artifact_bytes",
    }
)
_RETRY_KEYS = frozenset({"policy_id", "applies_to", "max_attempts", "retry_seconds"})


class StepKind(StrEnum):
    """§6.1. Closed. Two members, and one of them is refused by AI-13-B."""

    AGENT_EXECUTION = "AGENT_EXECUTION"
    APPROVAL = "APPROVAL"


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidDefinition(f"{where} must be an object")
    return value


def _closed(raw: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise InvalidDefinition(
            f"{where} has field(s) the contract does not define: "
            f"{', '.join(sorted(map(str, unknown)))}"
        )


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidDefinition(f"{where} must be a non-empty string")
    return value


def _positive_int(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InvalidDefinition(f"{where} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """§10.3. Declared data. A workflow that declares none has no retries.

    `retry_seconds` is a RUNTIME, not a date. §10.3 requires the policy to declare "a
    maximum attempts bound AND a time bound", and the time bound is declared here as a
    duration because a tracked definition cannot know when a run will start. The
    absolute deadline is computed once at run creation and lives on the run record; a
    date written into the definition would be one the run inherits rather than one the
    run was given, and it could not be shorter than the definition's own age.
    """

    policy_id: str
    applies_to: tuple[FailureClass, ...]
    max_attempts: int
    retry_seconds: int

    @classmethod
    def from_mapping(cls, raw: object, where: str = "retry_policy") -> "RetryPolicy":
        data = _mapping(raw, where)
        _closed(data, _RETRY_KEYS, where)

        applies = data.get("applies_to")
        if isinstance(applies, (str, bytes)) or not isinstance(applies, Sequence):
            raise InvalidDefinition(f"{where}.applies_to must be a list of failure classes")
        if not applies:
            raise InvalidDefinition(
                f"{where}.applies_to is empty; a policy that applies to no failure is a "
                "policy that never fires, and writing one is how a workflow acquires "
                "retries nobody reviewed"
            )
        classes: list[FailureClass] = []
        for entry in applies:
            try:
                classes.append(FailureClass(entry))
            except ValueError:
                raise InvalidDefinition(
                    f"{where}.applies_to names {entry!r}, which is not one of AI-13's "
                    "nine failure classes (§9)"
                ) from None

        max_attempts = _positive_int(data.get("max_attempts"), f"{where}.max_attempts")
        if max_attempts < 2:
            raise InvalidDefinition(
                f"{where}.max_attempts is {max_attempts}; a retry policy that permits "
                "one attempt permits no retry, and §10.3 requires the bound to say what "
                "it means rather than be discovered as inert"
            )

        return cls(
            policy_id=_text(data.get("policy_id"), f"{where}.policy_id"),
            applies_to=tuple(classes),
            max_attempts=max_attempts,
            retry_seconds=_positive_int(
                data.get("retry_seconds"), f"{where}.retry_seconds"
            ),
        )

    def covers(self, failure: FailureClass) -> bool:
        return failure in self.applies_to

    def to_body(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "applies_to": [str(item) for item in self.applies_to],
            "max_attempts": self.max_attempts,
            "retry_seconds": self.retry_seconds,
        }


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """§12. Every bound is DECLARED. A workflow that declares none is refused.

    ```text
    Definition = tracked policy data      -> a RUNTIME, declared once and versioned
    RunRecord  = runtime authority        -> the ABSOLUTE deadline, computed once
    ```

    §12 names a "maximum workflow runtime", and that is what is declared here: a
    duration. The definition is a tracked artifact reviewed in Git, so it cannot carry
    the instant a particular run will end — a date written into it would be a bound the
    run INHERITS rather than one it was GIVEN, and a definition amended after a run
    started could move that run's deadline underneath it. §8.3 puts the absolute on the
    run record, computed at creation, which is also what makes it survive a resume.
    """

    workflow_seconds: int
    step_seconds: int
    attempts_per_step: int
    attempts_total: int
    max_checkpoints: int
    max_checkpoint_bytes: int
    max_artifact_bytes: int

    @classmethod
    def from_mapping(cls, raw: object, where: str = "limits") -> "ResourceLimits":
        data = _mapping(raw, where)
        _closed(data, _LIMIT_KEYS, where)
        missing = sorted(_LIMIT_KEYS - set(data))
        if missing:
            # §12: "no limit" and "a limit nobody wrote down" are the same thing at run
            # time, and only one of them is honest.
            raise InvalidDefinition(
                f"{where} omits {', '.join(missing)}; every bound is DECLARED, because "
                "'no limit' and 'a limit nobody wrote down' are the same thing at run "
                "time (§12)"
            )

        max_artifact_bytes = _positive_int(
            data.get("max_artifact_bytes"), f"{where}.max_artifact_bytes"
        )
        if max_artifact_bytes > MAX_ARTIFACT_BYTES_CEILING:
            raise InvalidDefinition(
                f"{where}.max_artifact_bytes exceeds the declared ceiling; a bound no "
                "run could reach is not a bound (§12)"
            )

        return cls(
            workflow_seconds=_positive_int(
                data.get("workflow_seconds"), f"{where}.workflow_seconds"
            ),
            step_seconds=_positive_int(data.get("step_seconds"), f"{where}.step_seconds"),
            attempts_per_step=_positive_int(
                data.get("attempts_per_step"), f"{where}.attempts_per_step"
            ),
            attempts_total=_positive_int(data.get("attempts_total"), f"{where}.attempts_total"),
            max_checkpoints=_positive_int(
                data.get("max_checkpoints"), f"{where}.max_checkpoints"
            ),
            max_checkpoint_bytes=_positive_int(
                data.get("max_checkpoint_bytes"), f"{where}.max_checkpoint_bytes"
            ),
            max_artifact_bytes=max_artifact_bytes,
        )

    def to_body(self) -> dict[str, Any]:
        return {
            "workflow_seconds": self.workflow_seconds,
            "step_seconds": self.step_seconds,
            "attempts_per_step": self.attempts_per_step,
            "attempts_total": self.attempts_total,
            "max_checkpoints": self.max_checkpoints,
            "max_checkpoint_bytes": self.max_checkpoint_bytes,
            "max_artifact_bytes": self.max_artifact_bytes,
        }


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """§6.1. A step names a seam. It carries no state — that lives on the run.

    `timeout_seconds` is the step's declared PER-INVOCATION timeout: the inner bound
    AI-06 already requires of every invocation. It is declared here because AI-13 asks
    for the invocation, and §11.1 makes AI-13's step deadline an OUTER bound that
    composes with it — the engine hands the execution `min(this, the time the outer
    bounds have left)`, so the inner timeout is never removed, never widened, and never
    made optional by the outer one.
    """

    step_id: str
    kind: StepKind
    #: An AGENT_EXECUTION step's per-invocation timeout (§11.1). `None` for an APPROVAL
    #: step, which has no invocation to bound.
    timeout_seconds: int | None = None
    #: §13.4. An APPROVAL step's DECLARED wait. `None` for an AGENT_EXECUTION step.
    #:
    #: An approval "that does not arrive before its declared deadline is
    #: `APPROVAL_DENIED`, not a silent wait. There is no open-ended pending state" — so
    #: the declaration is not optional, and §12's rule that a workflow declaring no
    #: limit is refused applies to this bound exactly as it applies to the others.
    approval_seconds: int | None = None

    @classmethod
    def from_mapping(cls, raw: object, where: str = "steps[]") -> "WorkflowStep":
        data = _mapping(raw, where)
        _closed(data, _STEP_KEYS, where)
        step_id = _text(data.get("step_id"), f"{where}.step_id")
        try:
            kind = StepKind(data.get("kind"))
        except ValueError:
            raise InvalidDefinition(
                f"{where}.kind is not one of {', '.join(k.value for k in StepKind)}; a "
                "step that names no seam AI-13 may reach is not a step this contract "
                "admits (§6.1)"
            ) from None
        if kind is StepKind.APPROVAL:
            # §13.4, §18. AI-13-C enables the approval step, and the ONE thing it must
            # declare is how long the wait may last: a wait with no declared deadline is
            # the open-ended pending state §16 forbids.
            #
            # An approval step declares no per-invocation timeout, because there is no
            # invocation — the step waits for a human, and the human's bound is the
            # approval deadline. A step carrying a field its kind has no use for is
            # refused rather than ignored: ignoring it would let a definition appear to
            # bound something it does not.
            if "timeout_seconds" in data:
                raise InvalidDefinition(
                    f"{where} is an approval step and declares timeout_seconds; there is "
                    "no invocation for an inner timeout to bound, and the bound an "
                    "approval step has is its declared wait (§13.4)"
                )
            approval_seconds = _positive_int(
                data.get("approval_seconds"), f"{where}.approval_seconds"
            )
            return cls(step_id=step_id, kind=kind, approval_seconds=approval_seconds)

        # §11.1: "AI-13 does not make an inner one optional." A step that declared no
        # per-invocation timeout would have only the OUTER bound, which is precisely the
        # composition the contract refuses — so an omitted one is refused here rather
        # than defaulted, for the same reason §12 refuses an omitted limit.
        if "approval_seconds" in data:
            raise InvalidDefinition(
                f"{where} is an execution step and declares approval_seconds; there is "
                "no approval wait for that bound to govern (§13.4)"
            )
        timeout_seconds = _positive_int(
            data.get("timeout_seconds"), f"{where}.timeout_seconds"
        )
        return cls(step_id=step_id, kind=kind, timeout_seconds=timeout_seconds)

    def to_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"step_id": self.step_id, "kind": str(self.kind)}
        if self.kind is StepKind.APPROVAL:
            body["approval_seconds"] = self.approval_seconds
        else:
            body["timeout_seconds"] = self.timeout_seconds
        return body


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """§5. A tracked artifact, validated on construction, ordered as declared."""

    workflow_id: str
    revision: str
    steps: tuple[WorkflowStep, ...]
    limits: ResourceLimits
    definition_digest: str
    retry_policy: RetryPolicy | None = None

    @classmethod
    def from_mapping(cls, raw: object) -> "WorkflowDefinition":
        data = _mapping(raw, "definition")
        _closed(data, _DEFINITION_KEYS, "definition")

        if DIGEST_FIELD not in data:
            raise InvalidDefinition(
                f"definition carries no {DIGEST_FIELD!r}; a run binds to it and a resume "
                "is checked against it (§5, §8.1), so it is not optional"
            )

        workflow_id = _text(data.get("workflow_id"), "definition.workflow_id")
        revision = _text(data.get("revision"), "definition.revision")

        raw_steps = data.get("steps")
        if isinstance(raw_steps, (str, bytes)) or not isinstance(raw_steps, Sequence):
            raise InvalidDefinition("definition.steps must be an ordered list (§6.1)")
        steps = tuple(
            WorkflowStep.from_mapping(entry, f"definition.steps[{index}]")
            for index, entry in enumerate(raw_steps)
        )
        if not steps:
            raise InvalidDefinition(
                "definition.steps is empty; a workflow with no steps has nothing to "
                "bound, and an empty sequence would satisfy every limit vacuously"
            )
        seen = [step.step_id for step in steps]
        duplicates = sorted({sid for sid in seen if seen.count(sid) > 1})
        if duplicates:
            raise InvalidDefinition(
                f"definition.steps repeats {', '.join(duplicates)}; a step's identity is "
                "(workflow_id, revision, step_id) and a duplicate makes it ambiguous (§6.1)"
            )

        # §6.1 (Amendment 2). An APPROVAL step MUST be IMMEDIATELY followed in declared
        # order by exactly one execution-seam step, and THAT step is the one it gates.
        #
        # Two things follow, and both are refused here rather than discovered at run
        # time. An approval point at the END of a workflow has nothing to gate. And an
        # approval point followed by ANOTHER approval point would let the second wait
        # reach past the first — which is what Amendment 2 forbids, because two waits
        # naming one (step_id, attempt_no) would have identical scope identity and no
        # field able to tell them apart.
        for index, entry in enumerate(steps):
            if entry.kind is not StepKind.APPROVAL:
                continue
            following = steps[index + 1] if index + 1 < len(steps) else None
            if following is None:
                raise InvalidDefinition(
                    f"definition.steps[{index}] is an approval step and the LAST step; an "
                    "approval point must be immediately followed by the execution-seam "
                    "step it gates (§6.1)"
                )
            if following.kind is StepKind.APPROVAL:
                raise InvalidDefinition(
                    f"definition.steps[{index}] is an approval step immediately followed "
                    "by another approval step; an approval wait may not skip another "
                    "approval wait, or the two would name one scope (§6.1, Amendment 2)"
                )

        limits = ResourceLimits.from_mapping(data.get("limits"), "definition.limits")

        retry_raw = data.get("retry_policy")
        retry = (
            None
            if retry_raw is None
            else RetryPolicy.from_mapping(retry_raw, "definition.retry_policy")
        )

        definition = cls(
            workflow_id=workflow_id,
            revision=revision,
            steps=steps,
            limits=limits,
            definition_digest=_text(data.get(DIGEST_FIELD), f"definition.{DIGEST_FIELD}"),
            retry_policy=retry,
        )
        return definition

    @property
    def body(self) -> dict[str, Any]:
        """Everything the digest covers, with the digest field excluded (§7.4)."""
        return {
            "workflow_id": self.workflow_id,
            "revision": self.revision,
            "steps": [step.to_body() for step in self.steps],
            "limits": self.limits.to_body(),
            "retry_policy": self.retry_policy.to_body() if self.retry_policy else None,
        }

    @property
    def computed_digest(self) -> str:
        return digest_of({**self.body, DIGEST_FIELD: ""}, digest_field=DIGEST_FIELD)

    def step(self, step_id: str) -> WorkflowStep | None:
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def gating_step(self, step_id: str) -> WorkflowStep | None:
        """§6.1 (Amendments 1, 2). The approval point that gates `step_id`, if one does.

        An approval point gates the step IMMEDIATELY AFTER it, and validation refuses a
        definition that puts two approval points in a row — so a step has AT MOST one
        gating approval point, and finding it is a lookup of the preceding step rather
        than a search for the best match. A step with none is not gated at all.
        """
        target = self.step(step_id)
        if target is None:
            return None
        index = self.steps.index(target)
        if index == 0:
            return None
        previous = self.steps[index - 1]
        return previous if previous.kind is StepKind.APPROVAL else None

    def gated_step(self, step_id: str) -> WorkflowStep | None:
        """§6.1 (Amendment 2). The execution-seam step an approval point gates.

        The IMMEDIATELY FOLLOWING declared step and nothing else. There is no selector,
        no name and no index — a target a definition could point anywhere, or reach
        past, would be a target two approval points could share.

        Validation has already refused a definition where the following step is missing
        or is itself an approval step, so a `WorkflowStep` returned here is always an
        execution seam.
        """
        entry = self.step(step_id)
        if entry is None or entry.kind is not StepKind.APPROVAL:
            return None
        index = self.steps.index(entry)
        return self.steps[index + 1] if index + 1 < len(self.steps) else None

    def verify_digest(self) -> None:
        """§5. A definition whose digest does not match its own body is not usable."""
        if self.definition_digest != self.computed_digest:
            raise InvalidDefinition(
                "definition_digest does not match the definition's canonical body; a "
                "run binds to this value and a resume is checked against it (§5)",
                reason_code="DEFINITION_DIGEST_MISMATCH",
            )
