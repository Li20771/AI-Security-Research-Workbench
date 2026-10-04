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

import uuid
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from workflows.approval import ApprovalReference, ApprovalScope, WorkflowApproval
from workflows.canonical import digest_of, verify_digest
from workflows.checkpoint import ArtifactRef
from workflows.errors import InvalidRecord
from workflows.instants import is_instant, parse_instant
from workflows.references import reference
from workflows.vocabulary import TERMINAL_STATES, FailureClass, StepState, WorkflowState

__all__ = [
    "RUN_DIGEST_FIELD",
    "AttemptId",
    "AttemptRecord",
    "RunRecord",
    "StepRecord",
    "new_run_id",
    "record_approval",
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

#: §14, §15.2. Which bound a terminal state is ALLOWED to have reached. The reason codes
#: are the ones AI-13-B already emits — this maps them, it does not invent any.
#:
#: `RETRY_DEADLINE_REACHED` appears on both sides, and that is not an oversight: §8.3
#: makes the retry bound a DEADLINE when an attempt would begin after it (TIMED_OUT via
#: the bound check) and a RESOURCE bound when an attempt overran it (RESOURCE_EXHAUSTED
#: via the post-attempt check). One name, two terminal states, both declared.
_BOUNDS_BY_TERMINAL_STATE: dict[WorkflowState, frozenset[str]] = {
    WorkflowState.TIMED_OUT: frozenset(
        {"WORKFLOW_DEADLINE_REACHED", "STEP_DEADLINE_REACHED", "RETRY_DEADLINE_REACHED"}
    ),
    WorkflowState.RESOURCE_EXHAUSTED: frozenset(
        {
            "ATTEMPT_BOUND_REACHED",
            "CHECKPOINT_COUNT_BOUND_REACHED",
            "CHECKPOINT_BYTES_BOUND_REACHED",
            "ARTIFACT_BOUND_REACHED",
            "RETRY_DEADLINE_REACHED",
        }
    ),
}

#: §12. The step states an ATTEMPT can produce, keyed by what the attempt did.
#:
#: The engine sets SUCCEEDED on success, READY when a retryable failure leaves the step
#: to run again, and FAILED when the attempt is refused outright. Nothing else is
#: produced from an attempt, so nothing else is admitted here: a state whose cause is not
#: an attempt would be a claim the record cannot support.
_STEP_STATES_BY_OUTCOME: dict[bool, frozenset[StepState]] = {
    True: frozenset({StepState.SUCCEEDED}),
    False: frozenset({StepState.READY, StepState.FAILED}),
}

#: §13, §14. The ONE family of step-state transitions that NO attempt produced.
#:
#: An approval happens BEFORE the attempt it gates (§13.2: an approval binds to the
#: attempt it authorizes, and is obtained before that attempt runs), so a step enters
#: AWAITING_APPROVAL with nothing behind it and leaves to READY, where an attempt then
#: begins normally. Every other state change still requires an attempt (§15.2).
#:
#: Named as an explicit set rather than as "AWAITING_APPROVAL is special" so the
#: exception has edges: it is these transitions, not a state that may go anywhere.
_APPROVAL_WAIT_STEP_TRANSITIONS: frozenset[tuple[StepState, StepState]] = frozenset(
    {
        # the run arrives at an approval step. From READY or from PENDING: only the
        # first step of a run is ever READY, and an approval point may sit anywhere.
        (StepState.READY, StepState.AWAITING_APPROVAL),
        (StepState.PENDING, StepState.AWAITING_APPROVAL),
        # §13.1.2 (Amendment 4). Arriving also leaves the GATED step READY — the state
        # the wait's arrival describes. Listed here so the no-attempt rule admits it;
        # `_is_approval_wait_entry` is what confines it to that one pairing.
        (StepState.PENDING, StepState.READY),
        # §13.1.2: an approval was accepted, and the WAIT is what completed. A wait is
        # not an execution, so this SUCCEEDED has no attempt behind it — the one
        # step-state transition in the contract that none produces.
        (StepState.AWAITING_APPROVAL, StepState.SUCCEEDED),
        # §13.4: denied, or the wait expired — both are APPROVAL_DENIED for the step
        (StepState.AWAITING_APPROVAL, StepState.BLOCKED),
        # §13.3: with no designated ingress the step is BLOCKED where it STANDS, rather
        # than after a wait nothing could end. It has not entered the wait to leave it.
        (StepState.READY, StepState.BLOCKED),
        (StepState.PENDING, StepState.BLOCKED),
        # §8.3: the workflow deadline ran out while the run was waiting
        (StepState.AWAITING_APPROVAL, StepState.TIMED_OUT),
        # §13.1.3 (Amendment 3): an explicit retry re-enters the wait. Listed here so the
        # no-attempt rule admits it; `_is_approval_retry_re_entry` is what confines it.
        (StepState.SUCCEEDED, StepState.AWAITING_APPROVAL),
    }
)

#: §13, §14. The only non-terminal run transitions besides CREATED -> RUNNING.
#:
#: Waiting for a human is not an end state and not an open one: the run is somewhere it
#: can leave, in both directions, and §13.4's declared deadline is what guarantees it
#: leaves. Nothing else becomes reachable by adding this pair.
_APPROVAL_WAIT_RUN_TRANSITIONS: frozenset[tuple[WorkflowState, WorkflowState]] = (
    frozenset(
        {
            (WorkflowState.RUNNING, WorkflowState.AWAITING_APPROVAL),
            (WorkflowState.AWAITING_APPROVAL, WorkflowState.RUNNING),
        }
    )
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


def _sequence(value: object, where: str) -> Sequence[Mapping[str, Any]]:
    """A list of objects, read back strictly."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise InvalidRecord(f"{where} must be a list")
    return [_mapping(entry, f"{where}[]") for entry in value]


def _boolean(value: object, where: str) -> bool:
    """A JSON boolean, read back strictly.

    `bool(value)` turns `"false"` into True — a non-empty string is truthy — and accepts
    `1` as an outcome. That is an ILLEGAL value converted into a legal one, which is the
    one thing this module's construction boundary refuses to do; the parser has to hold
    the same line or the two boundaries disagree about what a record may say.
    """
    if not isinstance(value, bool):
        raise InvalidRecord(f"{where} must be a boolean (§15.2)")
    return value


def record_approval(
    run: "RunRecord",
    approval: WorkflowApproval,
    *,
    step_id: str,
    attempt_no: int,
    now: str,
) -> "RunRecord":
    """§13.1.2, §13.3. THE acceptance transition, and the only path an approval is recorded on.

    It takes the VERIFIED value and not a reference a caller assembled. `WorkflowApproval`
    cannot exist without a `Provenance`; a `Provenance` cannot be constructed unless its
    signature verifies UNDER THE ANCHOR THIS DEPLOYMENT DESIGNATED; and
    `RunRecord.advance` refuses `approvals` outright — so no call to this function can
    append an entry that did not begin with an Ed25519 check against that anchor, and no
    successor the ENGINE produces gains a ledger entry any other way.

    What that does and does not say is a boundary, so it is spelled out rather than left
    to the reader. This is the only path by which the engine APPENDS to a ledger, and it
    accepts only a verified value. It is NOT a claim that a `RunRecord` handed to the
    engine came from this path: the engine cannot distinguish a record read back from a
    caller's store from one assembled with the same contents, and it does not claim to
    (see the SECURITY BOUNDARY note above `class RunRecord`). The origin of a complete
    record is the persistence boundary's; what this function guarantees is the
    predecessor → successor transition it performs.

    Everything the transition does is the ACCEPTANCE's shape: one reference is appended,
    the WAIT becomes SUCCEEDED, the run returns to RUNNING, and the wait's deadline is
    released. The GATED step is not in this tuple — an approval authorizes an attempt
    rather than running one, and §13.1.2 leaves it READY and untouched.
    """
    gate = run._current_step()
    if gate is None:  # pragma: no cover - a waiting run always has one
        raise InvalidRecord(
            "this run has no step in flight, so there is no wait for an approval to end"
        )

    reference = ApprovalReference(
        step_id=step_id,
        attempt_no=attempt_no,
        scope_digest=approval.scope_digest,
        artifact_reference=approval.artifact_reference,
        actor_reference=approval.actor_reference,
        decided_at=approval.decided_at,
    )
    return run._successor(
        approvals=run.approvals + (reference,),
        state=WorkflowState.RUNNING,
        approval_deadline=None,
        updated_at=now,
        steps=tuple(
            replace(record, state=StepState.SUCCEEDED)
            if record.step_id == gate.step_id
            else record
            for record in run.steps
        ),
    )


def _is_approval_wait_entry(
    run: "RunRecord", moved: list[tuple[StepRecord, StepRecord]]
) -> bool:
    """§13.1.2 (Amendment 4). Whether this successor is a run ARRIVING at an approval point.

    Arriving moves two steps, and it is the only transition that may. The run's CURRENT
    step enters the wait, and the step immediately after it — the one the approval point
    gates — becomes READY. Amendment 4's arrival says exactly that, and saying it in one
    transition rather than two is what keeps the record from ever showing a run waiting at
    a point whose gated step is still PENDING.

    Everything about the pair is pinned: the moving step must be the current one, the
    second must be IMMEDIATELY after it, each must make exactly one of those two
    transitions, and no third step may move.
    """
    current = run._current_step()
    if current is None:
        return False

    pairs = {before.step_id: (before.state, after.state) for before, after in moved}
    if pairs.get(current.step_id) not in {
        (StepState.READY, StepState.AWAITING_APPROVAL),
        (StepState.PENDING, StepState.AWAITING_APPROVAL),
    }:
        return False

    ids = [record.step_id for record in run.steps]
    index = ids.index(current.step_id)
    if index + 1 >= len(ids):
        return False
    gated_id = ids[index + 1]
    if pairs.get(gated_id) != (StepState.PENDING, StepState.READY):
        return False

    return set(pairs) == {current.step_id, gated_id}


def _is_approval_retry_re_entry(
    before_record: StepRecord, after_record: StepRecord, successor: "RunRecord"
) -> bool:
    """§13.1.3 (Amendment 4). Whether this is the ONE backward transition admitted.

    Four conditions, all required, and the third is what Amendment 4 changed. It is no
    longer "the last attempt failed RETRYABLE" but "the NEXT LEGAL ATTEMPT has no
    accepted approval covering it". A retryable failure was ONE way to arrive at such a
    number; a process dying after reserving an attempt but before recording any result is
    another — and a rule written for the first left the second with no legal path at all,
    which is the hole Amendment 4 closes.

    The step being moved must be the approval point that GATES the failing step, and that
    is established without knowing step kinds. An approval names (step_id, attempt_no)
    and can only have come from the approval point IMMEDIATELY PRECEDING that step
    (§6.1, Amendment 2) — so if the step immediately after the one being moved holds an
    approval, the one being moved IS that approval point, and no other step can stand
    there.
    """
    if (before_record.state, after_record.state) != (
        StepState.SUCCEEDED,
        StepState.AWAITING_APPROVAL,
    ):
        return False

    ids = [record.step_id for record in successor.steps]
    index = ids.index(before_record.step_id)
    if index + 1 >= len(ids):
        return False
    gated = successor.step(ids[index + 1])
    if gated is None or gated.state is not StepState.READY:
        return False

    if not successor.approvals_for(gated.step_id):
        return False

    # §13.1.2, §13.1.3. And the next legal attempt must NOT already be approved: a wait
    # is never re-opened for an attempt that is already authorized.
    recorded = max(
        (attempt.attempt_id.attempt_no for attempt in gated.attempts), default=0
    )
    next_no = max(recorded, successor.inflight_attempt_no or 0) + 1
    return not successor.approval_covers(gated.step_id, next_no)


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

    def __post_init__(self) -> None:
        """§6.3, §9, §15.2. The CONSTRUCTION boundary: what an attempt may BE.

        `from_mapping` validates a parsed attempt; this validates a BUILT one, so the
        two boundaries admit the same records. That symmetry is the project's rule —
        "a digest proves a record is self-consistent, a construction/successor boundary
        proves it is legal" — and a direct constructor is precisely the path that
        reaches a record without passing a parser.

        The type annotations above are documentation. They are not a check, and a caller
        is not obliged to read them.
        """
        # §6.3. An attempt's identity is (run_id, step_id, attempt_no). A value that is
        # not an AttemptId carries no identity for the run record to verify against —
        # and `RunRecord.__post_init__` verifies exactly that.
        if not isinstance(self.attempt_id, AttemptId):
            raise InvalidRecord(
                "an attempt's identity must be an AttemptId; §6.3 makes it (run_id, "
                "step_id, attempt_no), and a value that is not one has no identity to "
                "be checked"
            )

        # §9. The vocabulary is CLOSED. A class outside the nine is not a class: §9.1 has
        # no UNKNOWN member, nothing is coerced into TERMINAL_FAILURE, and a value that
        # merely compares equal to a member — a bare `"TERMINAL_FAILURE"` string — is
        # not one. `isinstance` against the enum is what separates them.
        if self.failure_class is not None and not isinstance(
            self.failure_class, FailureClass
        ):
            raise InvalidRecord(
                "an attempt carries a failure class that is not one of AI-13's nine; "
                "§9.1 closes the vocabulary, there is no UNKNOWN member, and a value "
                "outside the nine is not a class this record may carry"
            )

        # §15.2. A boolean fact, and not a truthy one. `succeeded=1` decides an outcome
        # by a language rule rather than by what the record says, and a reader comparing
        # the record against the JSON it was written from would find them disagreeing.
        if not isinstance(self.succeeded, bool):
            raise InvalidRecord(
                "an attempt's succeeded must be a boolean; whether an attempt succeeded "
                "is not a truthiness question (§15.2)"
            )

        # §9, §15.2. An outcome and a classification are one fact. A FailureClass
        # classifies a FAILURE, so an attempt recorded as having succeeded cannot carry
        # one; §9.1's "matched none of the nine" is the OTHER case — `failure_class is
        # None`, which `unclassified` reports and which stays the only way to say it.
        if self.succeeded and self.failure_class is not None:
            raise InvalidRecord(
                "an attempt recorded as succeeded carries a failure class; §9's nine "
                "classes classify failures, and this attempt had none"
            )

        # §8.3, §15.2. WHEN the attempt ran, in the one timestamp shape the phase has.
        # `from_mapping` validates these through `_instant`; without the same check here
        # the constructor produced records that could be WRITTEN and never READ BACK —
        # a durable ledger that fails the moment someone tries to use it, which is the
        # worst moment for it to fail.
        for name in ("started_at", "ended_at"):
            if not is_instant(getattr(self, name)):
                raise InvalidRecord(
                    f"an attempt's {name} must be an ISO-8601 UTC instant with second "
                    "resolution and a trailing Z (§8.3); the record is written under that "
                    "rule and read back under it"
                )
        if parse_instant(self.ended_at) < parse_instant(self.started_at):
            raise InvalidRecord(
                "an attempt ended before it began; §15.2 records when an attempt began "
                "and when it ended, and those two instants are ordered"
            )

        # §6.3, §7.2. The artifacts the attempt referenced, as the tuple of references
        # `from_mapping` builds. Anything else used to survive construction and fail at
        # `to_body()` — which puts the failure at serialization time rather than at the
        # boundary that admitted the value.
        if not isinstance(self.artifact_refs, tuple) or not all(
            isinstance(ref, ArtifactRef) for ref in self.artifact_refs
        ):
            raise InvalidRecord(
                "an attempt's artifact_refs must be a tuple of ArtifactRef; §7.2 carries "
                "an artifact as a reference and a digest, and the bytes live outside"
            )

        # §6.3. The execution this attempt produced, recorded as a REFERENCE. It is what
        # makes an attempt an attempt, and `from_mapping` requires a non-empty string for
        # it, so the constructor does too.
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise InvalidRecord(
                "an attempt's execution_id must be a non-empty string; §6.3 records the "
                "ExecutionId the attempt produced, and an attempt that produced none is "
                "not this record"
            )

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


# ---------------------------------------------------------------------------
# SECURITY BOUNDARY — the RunRecord the engine is handed
# ---------------------------------------------------------------------------
#
# AI-13 trusts the RunRecord supplied by its persistence boundary as the current
# workflow state. AI-13 validates the record's own structural invariants and every
# predecessor -> successor transition it performs. AI-13 does not authenticate the
# origin of an externally supplied RunRecord, because v1 defines no record-level
# trust root, signing authority or distributed persistence protocol.
#
# That is a property of the contract's architecture rather than a gap in it. §3.2 has
# the engine hold no state between process lifetimes — "a run advances when something
# asks it to advance", and what asks it is a record — and §8.3/T23 require bounds and
# counters to be READ BACK from that record on resume. Between calls the run IS the
# record the caller kept, so a record restored from a store and a record assembled with
# the same contents are the same value here. Origin is therefore a property of the
# persistence boundary, and record-level authentication is a mechanism this phase does
# not define and does not claim.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunRecord:
    """§15. The ledger. Immutable; every advance returns a NEW record.

    Immutability is what makes "discarding a checkpoint does not reduce the attempts a
    run has spent" a property rather than a promise: a run's counters cannot be edited
    by anything, including a resume, and only `replace` produces a successor.

    Immutability is a property of the value, not of its origin: a record the caller
    supplies is taken as the run's state (see the SECURITY BOUNDARY note above).
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
    #: §13.4. The absolute instant the APPROVAL WAIT for the current step ends at.
    #:
    #: Anchored once when the run enters AWAITING_APPROVAL and persisted from there, by
    #: the same rule as the step deadline and for the same reason: §8.3 makes time spent
    #: awaiting an approval consume the run's budget, and a wait whose bound restarted
    #: on every resume would be a way to ask a human slowly, forever.
    approval_deadline: str | None = None
    #: §15.2. Every approval this run ACCEPTED, as REFERENCES.
    #:
    #: Only accepted ones appear. A refusal is not a decision and is not recorded
    #: (§13.3): writing a forgery here would turn it into a legitimate human act in the
    #: one artifact a reader trusts most.
    approvals: tuple[ApprovalReference, ...] = ()

    def __post_init__(self) -> None:
        """The construction boundary. Every invariant holds for a PARSED record and a
        CONSTRUCTED one alike, which is the only reason it lives here.

        A rule enforced in `cancel()` alone is a rule that a caller reaches around by
        calling `RunRecord(...)` directly — the typed-object bypass, which is the same
        defect class AI-12-B's review found when a caller labelled its own record
        `MODEL_EXECUTION` and manufactured the prerequisite. The helper is a
        convenience; this is the boundary.

        What it is the boundary FOR is worth stating, because the word is easy to
        over-read: it validates the RECORD-LOCAL invariants — the ones a record can be
        held to without knowing where it came from. It does not authenticate the
        external persistence source of a complete record, and it cannot: §3.2 gives the
        engine no state between process lifetimes, and this phase defines no
        record-level trust root (see the SECURITY BOUNDARY note above `class
        RunRecord`). "Every invariant holds for a constructed record too" means a caller
        cannot reach around a rule by using a constructor; it does not mean the record's
        origin has been checked.
        """
        # §15.2. The declared bounds are FROZEN, not merely un-assignable. `frozen=True`
        # stops `run.declared = ...`; it does nothing about `run.declared["x"] = ...`,
        # which edits the bound every limit in the phase is enforced from — behind
        # `advance`, behind `_verify_successor`, and behind the digest, which was
        # computed over the values as they were.
        #
        # A read-only VIEW is not enough on its own: a proxy over a dict someone else
        # still holds is a lock whose key is on the table. The mapping is COPIED, so no
        # reference to the mutable original survives construction.
        if not isinstance(self.declared, Mapping):
            raise InvalidRecord(
                "run.declared must be a mapping of the bounds the run declared; §15.2 "
                "records every bound, and a bound that is not in one bounds nothing"
            )
        object.__setattr__(
            self, "declared", MappingProxyType(dict(self.declared))
        )

        # §11.2. Format first, so a malformed reference is named as malformed rather
        # than reported as a missing one.
        for name in ("cancelled_by", "cancelled_reason"):
            value = getattr(self, name)
            if value is not None:
                reference(value, f"run.{name}")

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

        # §13.1, §15.2. An approval is recorded against a scope THIS RUN can RECOMPUTE.
        #
        # The reference carries the two run-local parts of the scope, and the run carries
        # the other four as its own identity — so the six-field digest is derivable here
        # rather than taken on trust. That is what refuses "an approval from run A stored
        # on run B": the digest simply does not come out, and a check that only compared
        # a stored string to itself would accept it.
        for entry in self.approvals:
            if self.step(entry.step_id) is None:
                raise InvalidRecord(
                    "an approval is recorded against a step this run does not declare; "
                    "§13.2 binds an approval to one step of one run"
                )
            expected = ApprovalScope(
                workflow_id=self.workflow_id,
                revision=self.revision,
                definition_digest=self.definition_digest,
                run_id=self.run_id,
                step_id=entry.step_id,
                attempt_no=entry.attempt_no,
            ).digest
            if entry.scope_digest != expected:
                raise InvalidRecord(
                    "an approval's scope digest does not come out of THIS run's "
                    "identity and the step and attempt it names; §13.2 binds an approval "
                    "to exactly six fields, four of which are the run's own"
                )

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def step(self, step_id: str) -> StepRecord | None:
        for record in self.steps:
            if record.step_id == step_id:
                return record
        return None

    def next_attempt_no_at(self, step_id: str) -> int:
        """§6.3. The number the next attempt at `step_id` will take.

        From the last RECORDED number for that step and never from the count of its
        records — a lineage beginning at 2 has one record, and counting it would hand out
        2 again — and from the in-flight number, because a process that died after
        reserving an attempt spent a number no record mentions.
        """
        recorded = max(
            (attempt.attempt_id.attempt_no for attempt in self.attempts_for(step_id)),
            default=0,
        )
        return max(recorded, self.inflight_attempt_no or 0) + 1

    def approval_covers(self, step_id: str, attempt_no: int) -> bool:
        """§13.1.2, §13.2. Whether an ACCEPTED approval covers this exact attempt.

        It answers over the SIX-FIELD SCOPE, not over a step: `attempt_no` is one of the
        six, so "an approval exists for this step" is a strictly weaker question and the
        wrong one. An approval for attempt 1 does not cover attempt 2, and no amount of
        sameness elsewhere — same run, same step, same revision, same digest — makes it.
        """
        return any(
            entry.step_id == step_id and entry.attempt_no == attempt_no
            for entry in self.approvals
        )

    def approvals_for(self, step_id: str) -> tuple[ApprovalReference, ...]:
        """Every accepted approval recorded against `step_id`, in order."""
        return tuple(entry for entry in self.approvals if entry.step_id == step_id)

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
            "approval_deadline": self.approval_deadline,
            "approvals": [entry.to_body() for entry in self.approvals],
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
        """§6.3. The number the next attempt at the step the run is ON will take."""
        current = self._current_step()
        if current is None:
            return 1
        return self.next_attempt_no_at(current.step_id)

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

        # ---- §13.1.2 (Amendment 4). THE ADMISSION GATE, at the record boundary ---
        # An attempt appended at a step this run has APPROVED must be covered by an
        # approval for its EXACT number. `begin_attempt` enforces this with the
        # definition in hand; this enforces it for a successor built by ANYONE, because
        # a digest proves a record is self-consistent and never that its transition was
        # permitted — `digest validation != transition validation`.
        #
        # A step the run has not approved is not distinguishable here from a step no
        # approval point gates, and §15.2 gives a run record no field that would tell
        # them apart. What CAN be said mechanically is said: once a step is approved,
        # every attempt at it is covered, so the ungated attempt after an approval —
        # which is the whole of GAP-4 — is refused.
        for step_id, attempt in appended:
            if not self.approvals_for(step_id):
                continue
            if not successor.approval_covers(step_id, attempt.attempt_id.attempt_no):
                raise InvalidRecord(
                    "a successor recorded an attempt at an approved step with no "
                    "accepted approval covering THAT attempt number; §13.2 makes an "
                    "approval bind to one attempt, and an attempt that runs without one "
                    "is the gate being skipped"
                )

        if self.inflight_attempt_no is not None and successor.inflight_attempt_no is None:
            if not appended and not successor.is_terminal:
                raise InvalidRecord(
                    "a successor released the in-flight attempt without recording it "
                    "and without ending the run; an attempt leaves flight only by being "
                    "recorded or by the run stopping (§6.3)"
                )

        # §6.3. A retry lineage is a sequence of AttemptIds, each pointing at a DISTINCT
        # ExecutionId — "never one ExecutionId with a counter on it". The engine refuses
        # a repeat when it sees one, but that is the engine choosing to check; this is
        # the record's own rule, and it holds for a lineage assembled by anyone.
        produced = [
            attempt.execution_id
            for record in successor.steps
            for attempt in record.attempts
        ]
        if len(set(produced)) != len(produced):
            raise InvalidRecord(
                "a successor's lineage points two attempts at one ExecutionId; §6.3 "
                "makes a retry a sequence of distinct executions, never one execution "
                "with a counter on it"
            )

        # ---- step state (§6.1, §12, §14) -----------------------------------------
        moved = [
            (record, successor.step(record.step_id))
            for record in self.steps
            if successor.step(record.step_id).state is not record.state
        ]
        if moved:
            # Two named exceptions, and nothing else moves a step without an attempt.
            wait_entry = _is_approval_wait_entry(self, moved)
            retry_re_entry = len(moved) == 1 and _is_approval_retry_re_entry(
                moved[0][0], moved[0][1], successor
            )

            if len(moved) > 1 and not wait_entry:
                raise InvalidRecord(
                    "a successor moved more than one step; AI-13 v1 runs one step at a "
                    "time, and the only transition that moves two is a run arriving at "
                    "an approval point (§12, §13.1.2)"
                )

            if appended:
                # Having an attempt is necessary and not sufficient. The state has to be
                # one THAT attempt produced: a failed attempt recorded against a
                # SUCCEEDED step disguises a failure as a success, and it also releases
                # the step deadline, so the disguise buys a fresh budget as well as a
                # false record.
                outcome = appended[0][1].succeeded
                if moved[0][1].state not in _STEP_STATES_BY_OUTCOME[outcome]:
                    raise InvalidRecord(
                        "a successor moved a step to a state its attempt does not "
                        "support; an attempt that SUCCEEDED is what makes a step "
                        "SUCCEEDED, and an attempt that did not cannot make it one (§15.2)"
                    )
            elif not wait_entry:
                for before_step, after_step in moved:
                    if (
                        before_step.state,
                        after_step.state,
                    ) in _APPROVAL_WAIT_STEP_TRANSITIONS and (
                        (before_step, after_step) == moved[0]
                    ):
                        continue
                    raise InvalidRecord(
                        "a successor changed a step's state with no attempt recorded; a "
                        "step's state is what its ATTEMPTS did, and the only transitions "
                        "no attempt produces are the approval wait's (§13, §15.2)"
                    )

            # §13.1.3. The one backward transition is judged on its own terms, because
            # the step it moves is deliberately NOT the one the run is on — being earlier
            # than the current step is what "backward" means here. Arriving is judged by
            # `_is_approval_wait_entry`, which pins the pair to the current step itself.
            if not (wait_entry or retry_re_entry):
                current = self._current_step()
                if current is None or moved[0][0].step_id != current.step_id:
                    raise InvalidRecord(
                        "a successor moved a step that is not the one the run is on; "
                        "steps run in their declared order and a later step cannot "
                        "finish first, and only an explicit retry may move an earlier "
                        "one (§6.1, §13.1.3)"
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

        # ---- the approval deadline (§8.3, §13.4) ---------------------------------
        # Read from the record, anchored once, and never re-derived — the same rule as
        # the step deadline, for the same reason. §8.3 makes time spent awaiting an
        # approval consume the run's budget; a bound that restarted on every resume
        # would be a way to ask a human slowly, forever.
        entered_wait = (
            successor.state is WorkflowState.AWAITING_APPROVAL
            and self.state is not WorkflowState.AWAITING_APPROVAL
        )
        left_wait = (
            self.state is WorkflowState.AWAITING_APPROVAL
            and successor.state is not WorkflowState.AWAITING_APPROVAL
        )
        if self.approval_deadline is None:
            if successor.approval_deadline is not None and not entered_wait:
                raise InvalidRecord(
                    "an approval deadline appeared without the run entering the wait; "
                    "it is anchored when a run begins waiting, and nowhere else (§13.4)"
                )
        elif successor.approval_deadline is None:
            if not left_wait:
                raise InvalidRecord(
                    "a successor released the approval deadline without leaving the "
                    "wait; a wait that has not ended still has its bound, and clearing "
                    "it would let the wait run forever (§13.4)"
                )
        elif successor.approval_deadline != self.approval_deadline:
            raise InvalidRecord(
                "a successor replaced the approval deadline; it is anchored once and "
                "read from there (§8.3, §13.4)"
            )

        # ---- the approvals a run has accepted (§15.2) ----------------------------
        if len(successor.approvals) < len(self.approvals):
            raise InvalidRecord(
                "a successor removed an approval from the ledger; §15.2 records every "
                "approval a run accepted, and a decision cannot be un-made"
            )
        for recorded, kept in zip(self.approvals, successor.approvals):
            if recorded != kept:
                raise InvalidRecord(
                    "a successor rewrote a recorded approval; §15.2 records the scope "
                    "digest and artifact reference of every approval a run accepted"
                )
        if len(successor.approvals) > len(self.approvals):
            if len(successor.approvals) - len(self.approvals) > 1:
                raise InvalidRecord(
                    "a successor recorded more than one approval; one transition "
                    "resolves one wait (§12, §13.2)"
                )
            if self.state is not WorkflowState.AWAITING_APPROVAL:
                raise InvalidRecord(
                    "a successor recorded an approval while the run was not waiting for "
                    "one; §13.2 binds an approval to the attempt it authorizes, and an "
                    "approval accepted outside a wait authorizes nothing"
                )

        # ---- §13.1.2, §13.3. LEAVING THE WAIT *IS* AN ACCEPTANCE ------------------
        # The approval point becoming SUCCEEDED and the run returning to RUNNING are what
        # an ACCEPTED approval DOES. A successor that performs them without appending one
        # has closed a wait that nothing answered — which is how a caller walks past the
        # human gate while leaving the ledger looking undisturbed.
        #
        # The rule is not "the approval count went up": a caller-built `ApprovalReference`
        # is not provenance, and a count is not a claim about where a value came from. What
        # is checked is that the ONE appended entry names the step this wait gates and the
        # attempt that step will actually run — the two facts the acceptance transition is
        # FOR. That an entry can only be appended by `record_approval` is enforced where
        # the append happens; this is the other half, and the two are independent.
        appended_approvals = successor.approvals[len(self.approvals):]
        if self.state is WorkflowState.AWAITING_APPROVAL:
            if successor.state is WorkflowState.RUNNING:
                if len(appended_approvals) != 1:
                    raise InvalidRecord(
                        "a successor returned a waiting run to RUNNING without recording "
                        "exactly one accepted approval; §13.1.2 makes an approval the "
                        "thing that ends the wait, and a wait that ends without one ended "
                        "for no reason the record can name"
                    )
                entry = appended_approvals[0]
                current = self._current_step()
                ids = [record.step_id for record in self.steps]
                index = ids.index(current.step_id) if current is not None else -1
                gated_id = ids[index + 1] if 0 <= index < len(ids) - 1 else None
                if gated_id is None or entry.step_id != gated_id:
                    raise InvalidRecord(
                        "a successor recorded an approval for a step the waiting approval "
                        "point does not gate; §6.1 makes the gated step the IMMEDIATELY "
                        "following declared step"
                    )
                if entry.attempt_no != self.next_attempt_no_at(gated_id):
                    raise InvalidRecord(
                        "a successor recorded an approval that does not name the NEXT "
                        "legal attempt of the gated step; §13.2 binds an approval to one "
                        "attempt, and one for any other number authorizes nothing"
                    )
                if successor.step(current.step_id).state is not StepState.SUCCEEDED:
                    raise InvalidRecord(
                        "a successor returned a waiting run to RUNNING without the "
                        "approval point itself becoming SUCCEEDED; §13.1.2 makes the WAIT "
                        "the thing that completed"
                    )
            elif successor.state is not WorkflowState.AWAITING_APPROVAL and appended_approvals:
                raise InvalidRecord(
                    "a successor recorded an approval while the run stopped waiting some "
                    "other way; an approval is accepted INTO a wait and not beside a "
                    "denial, an expiry or a deadline (§13.4)"
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
                # Two declared non-terminal transitions and no others: a run is created
                # RUNNING, and §13 lets it wait for a human and stop waiting. Nothing
                # else becomes reachable — in particular a run still becomes COMPLETED
                # only when every declared step has SUCCEEDED, below.
                if not (
                    (
                        self.state is WorkflowState.CREATED
                        and successor.state is WorkflowState.RUNNING
                    )
                    or (self.state, successor.state) in _APPROVAL_WAIT_RUN_TRANSITIONS
                ):
                    raise InvalidRecord(
                        "a successor moved the run to a non-terminal state; a run "
                        "becomes terminal, waits for an approval, or stays where it is "
                        "(§13, §14)"
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

        # ---- reached_bound is a FACT, not terminal metadata (§15.2) --------------
        # "which bound the run reached, IF it reached one". A run that never ended cannot
        # have reached one, and a run that ended because its work failed did not reach
        # one either — naming one there would attribute the stop to a limit nothing
        # touched, which is worse than saying nothing.
        bound = successor.reached_bound
        if bound is not None:
            if not successor.is_terminal:
                raise InvalidRecord(
                    "a non-terminal run names a bound it reached; a run reaches a bound "
                    "when one STOPS it, and a run still going has not been stopped (§15.2)"
                )
            if bound not in _BOUNDS_BY_TERMINAL_STATE.get(successor.state, frozenset()):
                raise InvalidRecord(
                    f"a run in state {successor.state} names a bound that state cannot "
                    "have reached; §15.2 records which bound stopped the run, and the "
                    "reason must be one that state is reachable by"
                )

    def _successor(self, **changes: Any) -> "RunRecord":
        """Build a successor and verify the transition. PRIVATE, and the reason `advance`
        can refuse a field at all.

        `record_approval` is its only caller outside `advance` itself, and it passes an
        approval a VERIFICATION produced rather than a reference a caller assembled. That
        is what separates the two: one caller holds a value that cannot exist without an
        Ed25519 check against the deployment's designated anchor, and the other is the
        whole outside world.

        That separation is about what this method WRITES, not about where its input came
        from: `self` is a record the caller supplied and this method takes it as the
        run's state (see the SECURITY BOUNDARY note above `class RunRecord`).
        """
        successor = replace(self, **changes)
        successor = replace(successor, run_digest=successor.computed_digest)
        self._verify_successor(successor)
        return successor

    def advance(self, **changes: Any) -> "RunRecord":
        """§15. The ONE way a CALLER makes a successor. Recomputes the digest, and refuses
        a transition that violates the predecessor's own history.

        The approval ledger is NOT among the fields it will write. An `ApprovalReference`
        is a plain record a caller can build, and a hand-built one is indistinguishable
        from a verified one BY ITS FIELDS — which is exactly why the ledger may not be
        written through a path that only looks at fields. `record_approval` is the one
        path a SUCCESSOR appends through, and it takes a `WorkflowApproval`, which cannot
        exist without a `Provenance`, which verifies itself against the anchor this
        deployment designated — so the value is not merely well formed, it is designated.

        ```text
        FROZEN: the run record of a NON-TERMINAL run MUST NOT be discarded.
        FROZEN: discarding a checkpoint MUST NOT lose, and MUST NOT alter: the attempt
                count, the elapsed or remaining runtime budget, ... or the run's lineage.
        ```

        Those clauses are about a reader trusting the ledger, and they hold only if a
        successor cannot quietly disagree with its predecessor — a property of this
        boundary rather than of the digest.

        Both rules are TRANSITION rules, and a transition rule is all either is. They
        constrain what a successor may do to the predecessor it is derived from; they do
        not authenticate a complete record supplied from outside, and neither does the
        constructor. Transition validation is not digest validation, and neither of them
        is origin authentication — the persistence boundary owns where a record came from
        (see the SECURITY BOUNDARY note above `class RunRecord`).
        """
        if "approvals" in changes:
            raise InvalidRecord(
                "the approval ledger is not a field a successor may write; §13.3 accepts "
                "an approval only through the designated ingress, and `record_approval` "
                "is the one path that appends a VERIFIED one"
            )
        return self._successor(**changes)

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
                        succeeded=_boolean(attempt.get("succeeded"), "attempt.succeeded"),
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
            approval_deadline=(
                _instant(data.get("approval_deadline"), "run.approval_deadline")
                if data.get("approval_deadline")
                else None
            ),
            approvals=tuple(
                ApprovalReference(
                    step_id=_text(entry.get("step_id"), "approval.step_id"),
                    attempt_no=entry.get("attempt_no"),
                    scope_digest=_text(
                        entry.get("scope_digest"), "approval.scope_digest"
                    ),
                    artifact_reference=_text(
                        entry.get("artifact_reference"),
                        "approval.artifact_reference",
                    ),
                    actor_reference=_text(
                        entry.get("actor_reference"), "approval.actor_reference"
                    ),
                    decided_at=_instant(
                        entry.get("decided_at"), "approval.decided_at"
                    ),
                )
                for entry in _sequence(data.get("approvals", []), "run.approvals")
            ),
            cancelled_by=data.get("cancelled_by") or None,
            cancelled_reason=data.get("cancelled_reason") or None,
        )
        if verify:
            record.verify_digest()
        return record
