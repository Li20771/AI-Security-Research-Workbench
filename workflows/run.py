"""AI-13 §6, §15 — the run record. The LEDGER, and the authority for every bound.

```text
RunRecord    the workflow execution LEDGER: the account of what a run has done.
             Authority for BOUNDS, because a bound is a fact about the whole run.

Checkpoint   a disposable RESUME SNAPSHOT: what is needed to continue.
             Authority for nothing. It may be discarded at any time.
```

```text
FROZEN: the separation is load-bearing. A bound enforced from a checkpoint would be
        escapable by discarding one: spend three attempts, delete the checkpoint,
        resume, and a "maximum three attempts" rule has spent none. Every counter a
        bound is enforced from lives on the RUN RECORD.
```

That rule is why the counters below are FIELDS of this record rather than anything
recomputed from checkpoints, and why `workflows.policy` — which computes the effective
bounds — does not import `workflows.checkpoint` at all. The absence of that import is
the structural form of the rule, and a test asserts it.

### Attempt identity is not execution identity

```text
FROZEN: one attempt at one step IS one AI-08 execution, with its OWN ExecutionId.
AttemptId = (run_id, step_id, attempt_no)    AI-13's identity for the attempt
ExecutionId                                  the execution's own, opaque, never reused
```

A retry lineage is a sequence of AttemptIds, each pointing at a DISTINCT ExecutionId —
never one ExecutionId with a counter on it. The engine refuses an attempt whose
ExecutionId another attempt already used, because that is precisely the shape this
rule forbids.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from workflows.canonical import digest_of, verify_digest
from workflows.checkpoint import ArtifactRef
from workflows.errors import InvalidRecord
from workflows.instants import is_instant
from workflows.vocabulary import TERMINAL_STATES, FailureClass, StepState, WorkflowState

__all__ = [
    "RUN_DIGEST_FIELD",
    "AttemptId",
    "AttemptRecord",
    "RunRecord",
    "StepRecord",
    "new_run_id",
]

#: The one field §7.4 excludes from a run record's preimage. It uses the same canonical
#: form as every other digest here, "so a second self-digest ambiguity cannot appear in
#: the artifact a reader trusts most" (§15.2).
RUN_DIGEST_FIELD = "run_digest"

#: §5, §15.1. Facts about a run that its own successors may not move. A deadline a
#: later record could extend is not a bound; a workspace a later record could change is
#: not the place the earlier steps ran.
_FIXED_FOR_THE_LIFE_OF_A_RUN = (
    "run_id",
    "workflow_id",
    "revision",
    "definition_digest",
    "workspace_identity",
    "created_at",
    "declared",
    "workflow_deadline",
    "retry_deadline",
)

#: §12, §15.1. Counters a bound is enforced from. They may only ever go UP: a successor
#: that could lower one would restore budget that a run has already spent, which is the
#: same escape §15.1 closes for checkpoints and §8.3 closes for deadlines.
_NEVER_DECREASES = (
    "consumed_total_attempts",
    "consumed_checkpoints",
    "consumed_checkpoint_bytes",
    "consumed_artifact_bytes",
)


def new_run_id() -> str:
    """A `WorkflowRunId`. Opaque, unique, never reused, never derived (§5)."""
    return f"run-{uuid.uuid4().hex[:16]}"


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidRecord(f"{where} must be an object")
    return value


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidRecord(f"{where} must be a non-empty string")
    return value


def _instant(value: object, where: str) -> str:
    text = _text(value, where)
    if not is_instant(text):
        raise InvalidRecord(
            f"{where} is not an ISO-8601 UTC instant with second resolution and a "
            "trailing Z (§8.3)"
        )
    return text


#: §11.2. The alphabet a DECLARED reference may use, and its bound.
_REFERENCE_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
MAX_REFERENCE_CHARS = 200


def _reference(value: object, where: str) -> str:
    """A DECLARED reference: an identifier, bounded, and never free-form text.

    §11.2 records WHO cancelled and WHY "as a declared reference", and the difference
    between a reference and a sentence is the whole of the rule. A field that could hold
    a sentence is a field that could hold a secret, a transcript or a judgement, and the
    run record is the artifact a reader trusts most — so the shape is enforced here
    rather than promised in a comment.

    This refuses to adjudicate nothing: it checks the FORM of what was declared, not
    whether the reason was good, which §11.2 leaves alone.
    """
    if not isinstance(value, str) or not value:
        raise InvalidRecord(f"{where} must be a non-empty string")
    if len(value) > MAX_REFERENCE_CHARS:
        raise InvalidRecord(f"{where} must be at most {MAX_REFERENCE_CHARS} characters")
    if not _REFERENCE_RE.match(value):
        raise InvalidRecord(
            f"{where} may contain only A-Z a-z 0-9 . _ : - and no whitespace; §11.2 "
            "records a declared REFERENCE, not free-form text"
        )
    return value


def _counter(value: object, where: str) -> int:
    """A consumed counter, read back strictly.

    `int(value)` would accept `True` and truncate `1.5` to `1`, and a counter a bound is
    enforced from is the last place a silent coercion belongs: §7.4 already refuses a
    float in a digest-covered field, and a counter is one.
    """
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidRecord(f"{where} must be a non-negative integer (§7.4, §12)")
    return value


@dataclass(frozen=True, slots=True)
class AttemptId:
    """§6.3. AI-13's identity for one attempt at one step."""

    run_id: str
    step_id: str
    attempt_no: int

    def __post_init__(self) -> None:
        if not self.run_id or not self.step_id:
            raise InvalidRecord("AttemptId needs a run_id and a step_id")
        if isinstance(self.attempt_no, bool) or not isinstance(self.attempt_no, int):
            raise InvalidRecord("AttemptId.attempt_no must be an integer")
        if self.attempt_no < 1:
            raise InvalidRecord(
                "AttemptId.attempt_no must be >= 1; §6.3 starts an attempt count at 1 "
                "and increases it by exactly 1"
            )

    def to_body(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "step_id": self.step_id,
            "attempt_no": self.attempt_no,
        }


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    """§15.2. One attempt, with the evidence it rests on as REFERENCES."""

    attempt_id: AttemptId
    execution_id: str
    #: `None` means UNCLASSIFIED — §9.1's absence of a classification, not a tenth
    #: member of the vocabulary.
    failure_class: FailureClass | None
    reason_code: str
    started_at: str
    ended_at: str
    succeeded: bool
    artifact_refs: tuple[ArtifactRef, ...] = ()
    #: §15.2's "the decision id it rests on", as a REFERENCE. `None` when the attempt
    #: rested on no decision — an attempt that asked nothing has no decision to name,
    #: and inventing one would be the record asserting an authorization nobody gave.
    #:
    #: This field is the reason §15.1's separation is load-bearing rather than tidy: a
    #: decision id belongs on the LEDGER, where §15.2 requires it, and is FORBIDDEN on
    #: the checkpoint, which a resumed attempt reads. `workflows.checkpoint` refuses
    #: the name outright, so the record can carry what the snapshot must not.
    decision_id: str | None = None

    @property
    def unclassified(self) -> bool:
        return self.failure_class is None and not self.succeeded

    def to_body(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id.to_body(),
            "execution_id": self.execution_id,
            # Rendered as null when unclassified, and §7.4 drops null from the preimage,
            # so "no class" is genuinely absent from the canonical body rather than
            # carried as a value a reader could mistake for a member.
            "failure_class": str(self.failure_class) if self.failure_class else None,
            "reason_code": self.reason_code,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "succeeded": self.succeeded,
            "artifact_refs": [ref.to_body() for ref in self.artifact_refs],
            "decision_id": self.decision_id,
        }


@dataclass(frozen=True, slots=True)
class StepRecord:
    """§15.2. One step's state and its attempt lineage, in order."""

    step_id: str
    state: StepState
    attempts: tuple[AttemptRecord, ...] = ()

    def to_body(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "state": str(self.state),
            "attempts": [attempt.to_body() for attempt in self.attempts],
        }


@dataclass(frozen=True, slots=True)
class RunRecord:
    """§15. The ledger. Immutable; every advance returns a NEW record.

    Immutability is what makes "discarding a checkpoint does not reduce the attempts a
    run has spent" a property rather than a promise: a run's counters cannot be edited
    by anything, including a resume, and only `replace` produces a successor.
    """

    run_id: str
    workflow_id: str
    revision: str
    definition_digest: str
    workspace_identity: str
    state: WorkflowState
    steps: tuple[StepRecord, ...]
    created_at: str
    updated_at: str
    #: The declared bounds, as DECLARED. Recorded so a reader can see what the run was
    #: bounded by, and so a resume can check it is resuming under the same ones.
    declared: Mapping[str, Any]
    #: §8.3. Absolute instants, computed once at creation.
    workflow_deadline: str
    retry_deadline: str | None
    #: The counters a bound is enforced from. On the RECORD, never on a checkpoint.
    consumed_total_attempts: int
    consumed_checkpoints: int
    consumed_checkpoint_bytes: int
    consumed_artifact_bytes: int
    run_digest: str
    #: §11.1, §12. The absolute instant the CURRENT step's declared runtime ends at.
    #:
    #: Anchored when that step's first attempt begins, then PERSISTED — never recomputed
    #: per attempt. A per-attempt `now + step_seconds` would hand every retry and every
    #: resume a fresh step budget, which is the escape §8.3 forbids: a step bounded at
    #: one hour would get a new hour each time the run was picked back up. `None` before
    #: a step has started, which is the only moment there is no step to bound.
    step_deadline: str | None = None
    #: §15.2's "which bound the run reached, if it reached one". `None` for a run that
    #: reached none — including one that ended for a reason that is not a bound, such as
    #: an unclassified failure. Naming a bound there would attribute the stop to a limit
    #: the run never touched.
    reached_bound: str | None = None
    #: §6.3, §8.3. The attempt at the CURRENT step that has BEGUN and has not been
    #: recorded as finished. `None` when no attempt is in flight.
    #:
    #: It exists so that `attempt_no` can never be REUSED across a crash. §6.3 freezes
    #: "never reused, never renumbered", and an attempt whose process died is still an
    #: attempt this run began: without this, a resume would derive the next number from
    #: the COMPLETED attempts alone and hand out the same number a second time. It is
    #: written before the execution starts, for the same reason the step deadline is —
    #: a fact the run spent must not depend on the execution coming back to say so.
    inflight_attempt_no: int | None = None
    #: §11.2. WHO cancelled and WHY, as DECLARED REFERENCES.
    #:
    #: "Cancellation is not a failure of the work, and a run cancelled by a human MUST
    #: NOT be recorded as one. AI-13 records WHO cancelled and WHY as a declared
    #: reference, and does not adjudicate whether the reason was good." Both are
    #: validated as bounded identifiers rather than free text: a reference is what the
    #: contract asks for, and a field that could hold a sentence is a field that could
    #: hold a transcript, a secret or a judgement AI-13 is not entitled to make.
    #:
    #: They are `None` on every run that was not cancelled, which is most of them.
    cancelled_by: str | None = None
    cancelled_reason: str | None = None

    def __post_init__(self) -> None:
        """The construction boundary. Every invariant holds for a PARSED record and a
        CONSTRUCTED one alike, which is the only reason it lives here.

        A rule enforced in `cancel()` alone is a rule that a caller reaches around by
        calling `RunRecord(...)` directly — the typed-object bypass, which is the same
        defect class AI-12-B's review found when a caller labelled its own record
        `MODEL_EXECUTION` and manufactured the prerequisite. The helper is a
        convenience; this is the boundary.
        """
        # §11.2. Format first, so a malformed reference is named as malformed rather
        # than reported as a missing one.
        for name in ("cancelled_by", "cancelled_reason"):
            value = getattr(self, name)
            if value is not None:
                _reference(value, f"run.{name}")

        # §11.2. A CANCELLED run records WHO cancelled and WHY. The converse is refused
        # too: provenance on a run that was never cancelled is a field that means
        # nothing sitting beside records where the same names mean something.
        cancelled = self.state is WorkflowState.CANCELLED
        named = self.cancelled_by is not None and self.cancelled_reason is not None
        if cancelled and not named:
            raise InvalidRecord(
                "a run recorded as CANCELLED carries no cancelled_by and "
                "cancelled_reason; §11.2 records WHO cancelled and WHY as declared "
                "references, and a cancelled run that names neither cannot answer why "
                "it stopped"
            )
        if named and not cancelled:
            raise InvalidRecord(
                f"a run in state {self.state} carries cancellation provenance; §11.2 "
                "records WHO cancelled and WHY on a CANCELLED run, and elsewhere those "
                "fields describe an act that did not happen"
            )

        # §6.3. An AttemptId is (run_id, step_id, attempt_no), and every one recorded
        # HERE must be this run's and this step's. Checked at construction rather than
        # only on append, so a record that arrived through `from_mapping` cannot carry a
        # foreign attempt either — a lineage that names another run is not a lineage.
        for record in self.steps:
            for attempt in record.attempts:
                if attempt.attempt_id.run_id != self.run_id:
                    raise InvalidRecord(
                        "an attempt recorded against this run names a different run; an "
                        "AttemptId is (run_id, step_id, attempt_no) (§6.3)"
                    )
                if attempt.attempt_id.step_id != record.step_id:
                    raise InvalidRecord(
                        "an attempt recorded against a step names a different step; an "
                        "AttemptId is (run_id, step_id, attempt_no) (§6.3)"
                    )

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def step(self, step_id: str) -> StepRecord | None:
        for record in self.steps:
            if record.step_id == step_id:
                return record
        return None

    def attempts_for(self, step_id: str) -> tuple[AttemptRecord, ...]:
        """§15.1. Where a per-step attempt bound is enforced from."""
        record = self.step(step_id)
        return record.attempts if record else ()

    def declared_limit(self, name: str) -> int:
        """§15.2. One declared bound, read from the RECORD.

        The record carries the bounds the run was CREATED under, so a bound enforced
        from here is the one this run declared rather than whatever a definition says
        today. That matters wherever the caller has only the record — which is exactly
        the case for anything charging a counter, and it is why a bound is a fact about
        the run rather than a lookup into a tracked file.
        """
        value = self.declared.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidRecord(
                f"run.declared.{name} is not an integer bound; §15.2 records every bound "
                "the run declared, and a bound that is not a number bounds nothing"
            )
        return value

    def execution_ids(self) -> tuple[str, ...]:
        """Every ExecutionId this run has already produced, in order."""
        return tuple(
            attempt.execution_id for record in self.steps for attempt in record.attempts
        )

    @property
    def body(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "revision": self.revision,
            "definition_digest": self.definition_digest,
            "workspace_identity": self.workspace_identity,
            "state": str(self.state),
            "steps": [record.to_body() for record in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "declared": dict(self.declared),
            "workflow_deadline": self.workflow_deadline,
            "retry_deadline": self.retry_deadline,
            "step_deadline": self.step_deadline,
            "consumed_total_attempts": self.consumed_total_attempts,
            "consumed_checkpoints": self.consumed_checkpoints,
            "consumed_checkpoint_bytes": self.consumed_checkpoint_bytes,
            "consumed_artifact_bytes": self.consumed_artifact_bytes,
            "reached_bound": self.reached_bound,
            "inflight_attempt_no": self.inflight_attempt_no,
            "cancelled_by": self.cancelled_by,
            "cancelled_reason": self.cancelled_reason,
        }

    @property
    def computed_digest(self) -> str:
        return digest_of({**self.body, RUN_DIGEST_FIELD: ""}, digest_field=RUN_DIGEST_FIELD)

    def verify_digest(self) -> None:
        verify_digest(
            {**self.body, RUN_DIGEST_FIELD: self.run_digest},
            digest_field=RUN_DIGEST_FIELD,
            reason_code="RUN_RECORD_CORRUPT",
        )

    def to_mapping(self) -> dict[str, Any]:
        return {**self.body, RUN_DIGEST_FIELD: self.run_digest}

    def _current_step(self) -> StepRecord | None:
        """The step this run is on: the first that has not succeeded.

        §12: "AI-13 v1 runs ONE step at a time." Declared order is part of the
        definition and not a runtime discovery, so the step a run is on follows from its
        own records — and that is also the only step a successor may move.
        """
        for record in self.steps:
            if record.state is not StepState.SUCCEEDED:
                return record
        return None

    def next_attempt_no(self) -> int:
        """§6.3. The ONE attempt number a reservation is allowed to take.

        Derived from the last RECORDED number and not from the COUNT of records. A run
        whose first attempt died before it could be written has a lineage beginning at
        2, and counting its single record would hand out 2 a second time — which is
        exactly the reuse §6.3 forbids, and the reason the in-flight number is persisted
        separately at all.
        """
        current = self._current_step()
        recorded = (
            max((attempt.attempt_id.attempt_no for attempt in current.attempts), default=0)
            if current is not None
            else 0
        )
        return max(recorded, self.inflight_attempt_no or 0) + 1

    def _verify_successor(self, successor: "RunRecord") -> None:
        """§5, §6, §8.3, §11, §12, §14, §15. The predecessor → successor boundary.

        A digest proves a record is internally consistent. It proves NOTHING about the
        step from the record before it — `run.advance(consumed_total_attempts=0)` hashes
        beautifully — so the TRANSITION is what is checked here.

        This is a state machine, not a list of forbidden examples. Every field is
        classified: what creation fixed, what may only increase, what may only be
        appended to, what has a declared set of transitions, and what a terminal state
        freezes. A rule covering only the cases someone thought of leaves the rest
        reachable, and reachable is the whole problem — the caller this defends against
        is not the engine.

        `advance` is the only way in, and there is no unchecked successor path: the
        digest is computed after the transition is accepted, never instead of it.
        """
        # ---- identity, and what creation fixed (§5, §8.3, §15.1) -----------------
        for name in _FIXED_FOR_THE_LIFE_OF_A_RUN:
            if getattr(self, name) != getattr(successor, name):
                raise InvalidRecord(
                    f"a successor changed {name}; it is fixed when the run is created "
                    "and no later record may move it (§5, §15.1)"
                )

        # ---- counters a bound is enforced from (§12, §15.1) ----------------------
        for name in _NEVER_DECREASES:
            if getattr(successor, name) < getattr(self, name):
                raise InvalidRecord(
                    f"a successor lowered {name}; a counter a bound is enforced from "
                    "may only ever increase (§12, §15.1)"
                )

        # ---- step identity and order (§6.1) --------------------------------------
        # A workflow is an ORDERED sequence of declared steps. A successor may move what
        # a step is DOING; it may not change which steps exist, what they are called,
        # how many there are, or what order they are in. Those belong to the definition,
        # and a record free to edit them describes a different workflow than the run
        # bound to (§5).
        if [record.step_id for record in successor.steps] != [
            record.step_id for record in self.steps
        ]:
            raise InvalidRecord(
                "a successor changed the run's step identity or order; the declared "
                "sequence is the definition's, and a record may not add, remove, rename "
                "or reorder a step (§6.1)"
            )

        # ---- the attempt lineage (§6.3, §15.2) -----------------------------------
        appended: list[tuple[str, AttemptRecord]] = []
        for record in self.steps:
            other = successor.step(record.step_id)
            if other is None:  # pragma: no cover - the order check above covers it
                raise InvalidRecord(
                    "a successor dropped a step the run declared (§6.1)"
                )
            if len(other.attempts) < len(record.attempts):
                raise InvalidRecord(
                    "a successor shortened an attempt lineage; a spent attempt cannot "
                    "be unspent (§15.1)"
                )
            for before, after in zip(record.attempts, other.attempts):
                if before != after:
                    raise InvalidRecord(
                        "a successor rewrote a recorded attempt; §15.2 records what an "
                        "attempt WAS, and an attempt number is never reused or "
                        "renumbered (§6.3)"
                    )
            appended.extend(
                (record.step_id, attempt)
                for attempt in other.attempts[len(record.attempts) :]
            )

        # §12. One step at a time, so at most one execution is in flight and at most one
        # attempt can leave it per transition.
        if len(appended) > 1:
            raise InvalidRecord(
                "a successor recorded more than one attempt; AI-13 v1 runs one step at "
                "a time and one attempt leaves flight per transition (§12)"
            )

        # ---- the in-flight attempt's lifecycle (§6.3, §12) -----------------------
        reserved = successor.inflight_attempt_no is not None and (
            successor.inflight_attempt_no != self.inflight_attempt_no
        )
        spent = successor.consumed_total_attempts - self.consumed_total_attempts

        if reserved:
            # A reservation IS the spend. The attempt is counted when the run commits
            # to running it, not when an execution comes back to describe it — which is
            # what stops a run that keeps dying from spending without limit.
            if spent != 1:
                raise InvalidRecord(
                    "a successor reserved an attempt without spending exactly one; an "
                    "attempt is counted when it BEGINS, so the counter and the in-flight "
                    "number move together (§12, §15.1)"
                )
            if successor.inflight_attempt_no != self.next_attempt_no():
                raise InvalidRecord(
                    "a successor reserved an attempt number that is not the next one; "
                    "§6.3 increases the count by exactly one per attempt and never "
                    "reuses a number"
                )
        elif spent != 0:
            raise InvalidRecord(
                "a successor spent attempts without reserving one; the counter moves "
                "only when an attempt begins (§12, §15.1)"
            )

        if appended:
            step_id, attempt = appended[0]
            if attempt.attempt_id.run_id != self.run_id:
                raise InvalidRecord(
                    "a successor recorded an attempt belonging to another run; an "
                    "AttemptId is (run_id, step_id, attempt_no) and all three are this "
                    "run's (§6.3)"
                )
            if attempt.attempt_id.step_id != step_id:
                raise InvalidRecord(
                    "a successor recorded an attempt under a step it does not name; an "
                    "AttemptId is (run_id, step_id, attempt_no) (§6.3)"
                )
            # An attempt may only be RECORDED if it was RESERVED. This is what ties the
            # lineage to the counter: without it a caller could append an arbitrary
            # attempt, with an arbitrary number, that the run never began.
            if attempt.attempt_id.attempt_no != self.inflight_attempt_no:
                raise InvalidRecord(
                    "a successor recorded an attempt that was never in flight; an "
                    "attempt is recorded when the one the run reserved returns, and its "
                    "number is the reserved one (§6.3)"
                )
            if successor.inflight_attempt_no is not None:
                raise InvalidRecord(
                    "a successor recorded an attempt and left it in flight; an attempt "
                    "leaves flight exactly when it is recorded (§6.3)"
                )

        if self.inflight_attempt_no is not None and successor.inflight_attempt_no is None:
            if not appended and not successor.is_terminal:
                raise InvalidRecord(
                    "a successor released the in-flight attempt without recording it "
                    "and without ending the run; an attempt leaves flight only by being "
                    "recorded or by the run stopping (§6.3)"
                )

        # ---- step state (§6.1, §12, §14) -----------------------------------------
        moved = [
            (record, successor.step(record.step_id))
            for record in self.steps
            if successor.step(record.step_id).state is not record.state
        ]
        if len(moved) > 1:
            raise InvalidRecord(
                "a successor moved more than one step; AI-13 v1 runs one step at a "
                "time, so one transition advances at most one (§12)"
            )
        if moved:
            before = moved[0][0]
            current = self._current_step()
            if current is None or before.step_id != current.step_id:
                raise InvalidRecord(
                    "a successor moved a step that is not the one the run is on; steps "
                    "run in their declared order and a later step cannot finish first "
                    "(§6.1)"
                )
            if not appended:
                raise InvalidRecord(
                    "a successor changed a step's state with no attempt recorded; a "
                    "step's state is what its ATTEMPTS did, and a state with no attempt "
                    "behind it is a claim the record does not support (§15.2)"
                )

        # ---- the step deadline (§8.3, §11.1) -------------------------------------
        if self.step_deadline is None:
            if successor.step_deadline is not None and not reserved:
                raise InvalidRecord(
                    "a step deadline appeared without an attempt being reserved; it is "
                    "anchored when a step's first attempt begins, and nowhere else (§8.3)"
                )
        elif successor.step_deadline is None:
            # Released. The worry is a set-difference approximation — "some step
            # succeeded" would let a caller succeed step two to release step one's
            # bound. It is exact here, because exactly one step may move (above) and it
            # must be the step the run is on, which is the step the bound belongs to:
            # that is where it was anchored.
            if not moved or moved[0][1].state is not StepState.SUCCEEDED:
                raise InvalidRecord(
                    "a successor released the step deadline without the step it bounds "
                    "succeeding; a step that has not finished still has its bound, and "
                    "clearing it would grant the retry a fresh one (§8.3)"
                )
        elif successor.step_deadline != self.step_deadline:
            raise InvalidRecord(
                "a successor replaced the step deadline; it is anchored once at the "
                "step's first attempt and read from there (§8.3)"
            )

        # ---- the workflow state (§14) --------------------------------------------
        if self.is_terminal:
            if successor.state is not self.state:
                raise InvalidRecord(
                    "a successor moved a terminal run out of its terminal state; §14 "
                    "gives a terminal state no transition out of it"
                )
        elif successor.state is not self.state:
            if not successor.is_terminal:
                # The one declared non-terminal transition, and one the engine never
                # needs: a run is created RUNNING.
                if not (
                    self.state is WorkflowState.CREATED
                    and successor.state is WorkflowState.RUNNING
                ):
                    raise InvalidRecord(
                        "a successor moved the run to a non-terminal state; a run "
                        "becomes terminal or stays where it is (§14)"
                    )
            elif successor.state is WorkflowState.COMPLETED:
                # §14's COMPLETED is not "the caller says so". It is what a run IS when
                # every declared step has succeeded, and nothing else may produce it.
                if any(
                    record.state is not StepState.SUCCEEDED for record in successor.steps
                ):
                    raise InvalidRecord(
                        "a successor completed a run with steps that have not "
                        "succeeded; COMPLETED is what a run IS when every declared step "
                        "is SUCCEEDED (§14)"
                    )

        # ---- what a terminal state freezes (§15.2) -------------------------------
        for name in ("reached_bound", "cancelled_by", "cancelled_reason"):
            if getattr(self, name) is not None and getattr(successor, name) != getattr(
                self, name
            ):
                raise InvalidRecord(
                    f"a successor changed {name}; what a run reached, and who cancelled "
                    "it, are facts about what happened (§15.2)"
                )

    def advance(self, **changes: Any) -> "RunRecord":
        """§15. The ONE way to make a successor. Recomputes the digest, and refuses a
        transition that violates the predecessor's own history.

        ```text
        FROZEN: the run record of a NON-TERMINAL run MUST NOT be discarded.
        FROZEN: discarding a checkpoint MUST NOT lose, and MUST NOT alter: the attempt
                count, the elapsed or remaining runtime budget, ... or the run's lineage.
        ```

        Those clauses are about a reader trusting the ledger, and they hold only if a
        successor cannot quietly disagree with its predecessor — a property of this
        boundary rather than of the digest.

        There is deliberately NO second, unchecked path to a successor. A convenience
        that skipped the check would be the check's own bypass.
        """
        successor = replace(self, **changes)
        successor = replace(successor, run_digest=successor.computed_digest)
        self._verify_successor(successor)
        return successor

    @classmethod
    def from_mapping(cls, raw: object, *, verify: bool = True) -> "RunRecord":
        data = _mapping(raw, "run")
        if RUN_DIGEST_FIELD not in data:
            raise InvalidRecord(
                f"run record carries no {RUN_DIGEST_FIELD!r}; it uses the same canonical "
                "digest rule as every other record here (§15.2)"
            )

        try:
            state = WorkflowState(data.get("state"))
        except ValueError:
            raise InvalidRecord(
                f"run.state is not one of AI-13's workflow states (§14)"
            ) from None

        raw_steps = data.get("steps", [])
        if isinstance(raw_steps, (str, bytes)) or not isinstance(raw_steps, Sequence):
            raise InvalidRecord("run.steps must be an ordered list")
        steps: list[StepRecord] = []
        for entry in raw_steps:
            step = _mapping(entry, "run.steps[]")
            raw_attempts = step.get("attempts", [])
            attempts: list[AttemptRecord] = []
            for attempt_entry in raw_attempts:
                attempt = _mapping(attempt_entry, "run.steps[].attempts[]")
                attempt_id = _mapping(attempt.get("attempt_id"), "attempt.attempt_id")
                failure_raw = attempt.get("failure_class")
                try:
                    failure = FailureClass(failure_raw) if failure_raw else None
                except ValueError:
                    # §9.1: nine members and no tenth. A class outside them is not a
                    # class this record may carry, and inventing one for it is the
                    # mutation the vocabulary forbids.
                    raise InvalidRecord(
                        "an attempt carries a failure class that is not one of AI-13's "
                        "nine (§9); there is no UNKNOWN member and none is assigned"
                    ) from None
                attempts.append(
                    AttemptRecord(
                        attempt_id=AttemptId(
                            run_id=_text(attempt_id.get("run_id"), "attempt.run_id"),
                            step_id=_text(attempt_id.get("step_id"), "attempt.step_id"),
                            attempt_no=attempt_id.get("attempt_no"),
                        ),
                        execution_id=_text(attempt.get("execution_id"), "attempt.execution_id"),
                        failure_class=failure,
                        reason_code=str(attempt.get("reason_code", "")),
                        started_at=_instant(attempt.get("started_at"), "attempt.started_at"),
                        ended_at=_instant(attempt.get("ended_at"), "attempt.ended_at"),
                        succeeded=bool(attempt.get("succeeded")),
                        artifact_refs=tuple(
                            ArtifactRef.from_mapping(ref, "attempt.artifact_refs[]")
                            for ref in attempt.get("artifact_refs", [])
                        ),
                        decision_id=(
                            _text(attempt.get("decision_id"), "attempt.decision_id")
                            if attempt.get("decision_id")
                            else None
                        ),
                    )
                )
            try:
                step_state = StepState(step.get("state"))
            except ValueError:
                raise InvalidRecord("run.steps[].state is not a step state (§14)") from None
            steps.append(
                StepRecord(
                    step_id=_text(step.get("step_id"), "run.steps[].step_id"),
                    state=step_state,
                    attempts=tuple(attempts),
                )
            )

        record = cls(
            run_id=_text(data.get("run_id"), "run.run_id"),
            workflow_id=_text(data.get("workflow_id"), "run.workflow_id"),
            revision=_text(data.get("revision"), "run.revision"),
            definition_digest=_text(data.get("definition_digest"), "run.definition_digest"),
            workspace_identity=_text(data.get("workspace_identity"), "run.workspace_identity"),
            state=state,
            steps=tuple(steps),
            created_at=_instant(data.get("created_at"), "run.created_at"),
            updated_at=_instant(data.get("updated_at"), "run.updated_at"),
            declared=dict(_mapping(data.get("declared", {}), "run.declared")),
            workflow_deadline=_instant(data.get("workflow_deadline"), "run.workflow_deadline"),
            retry_deadline=(
                _instant(data.get("retry_deadline"), "run.retry_deadline")
                if data.get("retry_deadline")
                else None
            ),
            consumed_total_attempts=_counter(data.get("consumed_total_attempts"), "run.consumed_total_attempts"),
            consumed_checkpoints=_counter(data.get("consumed_checkpoints"), "run.consumed_checkpoints"),
            consumed_checkpoint_bytes=_counter(
                data.get("consumed_checkpoint_bytes"), "run.consumed_checkpoint_bytes"
            ),
            consumed_artifact_bytes=_counter(
                data.get("consumed_artifact_bytes"), "run.consumed_artifact_bytes"
            ),
            run_digest=_text(data.get(RUN_DIGEST_FIELD), f"run.{RUN_DIGEST_FIELD}"),
            step_deadline=(
                _instant(data.get("step_deadline"), "run.step_deadline")
                if data.get("step_deadline")
                else None
            ),
            reached_bound=(
                _text(data.get("reached_bound"), "run.reached_bound")
                if data.get("reached_bound")
                else None
            ),
            inflight_attempt_no=(
                _counter(data.get("inflight_attempt_no"), "run.inflight_attempt_no")
                if data.get("inflight_attempt_no")
                else None
            ),
            # Both are validated by `__post_init__`, so a parsed record and a
            # constructed one are held to the same rule.
            cancelled_by=data.get("cancelled_by") or None,
            cancelled_reason=data.get("cancelled_reason") or None,
        )
        if verify:
            record.verify_digest()
        return record
