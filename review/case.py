"""AI-10 §5, §14 — the case and its lifecycle.

```text
CREATED -> MATERIALS_SUPPLIED -> INDEPENDENCE_OBSERVED -> COMPARISON_RECORDED
        -> VERIFICATION_REQUESTED -> VERIFICATION_OBSERVED -> HUMAN_DECISION_RECORDED
        -> CLOSED

any non-terminal state -> UNRESOLVED | BLOCKED | NOT_RUN      (explicit closure)
```

Every transition is an EXPLICIT act of a caller. None is automatic, none is
time-based, and none is inferred from another record arriving. A case that ends
UNRESOLVED, BLOCKED or NOT_RUN is a complete, honest outcome.

### A case is a value

Advancing a case produces a new value; the previous one is unchanged. The case
holds the two material identifiers and the state, and nothing else — findings,
observations and decisions are separate values the caller holds, because a case
that accumulated content would be the durable store this contract refuses to
create.

### Two axes, not one — §5.4 (Amendment 2)

```text
state                 where the review is in its lifecycle       §5.2
independence_status   whether an independence observation was
                      obtained                                  §5.4
```

They are orthogonal. A case in `COMPARISON_RECORDED` may hold `UNCHECKED` (no
ExecutionRecords were supplied — §6.4's required record) or `OBSERVED` (they
were, and §8.2's conditions held), and both are complete, honest records.
`UNCHECKED` is NOT a lifecycle state and MUST NOT become one: it describes an
observation that was not made, not a phase a review is in.

### Two boundaries worth stating where a reader will find them

```text
v1 exercises at most ONE verification round. §5.3 has no transition from
VERIFICATION_OBSERVED back to VERIFICATION_REQUESTED, so a second request after
an observation is refused like any other illegal transition. A second round is
an amendment, not an implementation choice — and that same rule is what makes
"one request, at most one observation" structural rather than stored.

DEFERRED does not close a case. §12.2 leaves the case open, so a superseding
decision may be recorded, and CLOSED requires an ACCEPTED or REJECTED decision
to be supplied again at the closure act.
```
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass

from agents.independence import ExecutionRecord, IndependenceFinding

from review import independence as independence_module
from review.comparison import compare
from review.decision import HumanDecision
from review.errors import InvalidCase, InvalidTransition, InvalidVerification
from review.finding import ReviewFinding
from review.material import ReviewMaterial
from review.validation import identifier, single_line
from review.verification import VerificationObservation, VerificationRequest
from review.vocabulary import (
    CLOSURE_CASE_STATES,
    MAX_WORKSPACE_ID_CHARS,
    TERMINAL_CASE_STATES,
    HumanDecisionKind,
    IndependenceObservationStatus,
    ReviewCaseState,
)

__all__ = [
    "ReviewCase",
    "close",
    "close_with_decision",
    "create_case",
    "new_review_case_id",
    "observe_independence",
    "observe_verification",
    "record_comparison",
    "record_decision",
    "request_verification",
    "supply_materials",
]

#: Every state from which a caller may still act.
NON_TERMINAL_CASE_STATES: frozenset[ReviewCaseState] = (
    frozenset(ReviewCaseState) - TERMINAL_CASE_STATES
)

#: The states that require both materials to be present. A closure state may or
#: may not hold them: a case may be closed as NOT_RUN before anything was
#: supplied.
_STATES_REQUIRING_MATERIALS: frozenset[ReviewCaseState] = frozenset(
    {
        ReviewCaseState.MATERIALS_SUPPLIED,
        ReviewCaseState.INDEPENDENCE_OBSERVED,
        ReviewCaseState.COMPARISON_RECORDED,
        ReviewCaseState.VERIFICATION_REQUESTED,
        ReviewCaseState.VERIFICATION_OBSERVED,
        ReviewCaseState.HUMAN_DECISION_RECORDED,
        ReviewCaseState.CLOSED,
    }
)


def new_review_case_id() -> str:
    """§5.1. A new opaque case id.

    Opaque by construction: it encodes no Agent, no task, no workspace content
    and no outcome. The `rc-` prefix is a label, not a namespace that carries
    meaning (the ExecutionId rule, AI-08 §7.2, applied here).
    """
    return f"rc-{uuid.uuid4().hex[:16]}"


@dataclass(frozen=True, slots=True)
class ReviewCase:
    """§5.1. One review, at one point in its lifecycle.

    `state` and `independence_status` answer two different questions and are
    never derived from each other (§5.4).

    ```text
    The constructor is a VALUE boundary, not an act boundary. It enforces the
    structural invariants a case must satisfy — two distinct sides, materials
    present where the state requires them, the two axes consistent — and it
    cannot enforce that the acts which produced the value were legal, because a
    case does not store its acts. Only `observe_independence` runs AI-08's
    predicate, and only `close_with_decision` closes a decided case.
    ```
    """

    review_case_id: str
    workspace_id: str
    left_material_id: str | None = None
    right_material_id: str | None = None
    state: ReviewCaseState = ReviewCaseState.CREATED
    independence_status: IndependenceObservationStatus = (
        IndependenceObservationStatus.NOT_APPLICABLE
    )
    schema_version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "review_case_id",
            identifier(self.review_case_id, "case.review_case_id"),
        )
        object.__setattr__(
            self,
            "workspace_id",
            single_line(
                self.workspace_id,
                "case.workspace_id",
                maximum=MAX_WORKSPACE_ID_CHARS,
                error=InvalidCase,
            ),
        )
        for name in ("left_material_id", "right_material_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, identifier(value, f"case.{name}"))

        try:
            state = ReviewCaseState(self.state)
        except ValueError as exc:
            raise InvalidCase(
                f"case.state must be one of "
                f"{[member.value for member in ReviewCaseState]}; got {self.state!r}"
            ) from exc
        object.__setattr__(self, "state", state)

        try:
            status = IndependenceObservationStatus(self.independence_status)
        except ValueError as exc:
            raise InvalidCase(
                "case.independence_status must be one of "
                f"{[member.value for member in IndependenceObservationStatus]}; got "
                f"{self.independence_status!r}. It is a second axis, not a twelfth "
                "lifecycle state (§5.4)"
            ) from exc
        object.__setattr__(self, "independence_status", status)

        if self.schema_version != 1:
            raise InvalidCase(
                f"case.schema_version {self.schema_version!r} is not supported; "
                "this contract defines 1"
            )

        has_materials = (
            self.left_material_id is not None and self.right_material_id is not None
        )
        if (
            self.left_material_id is not None
            and self.left_material_id == self.right_material_id
        ):
            raise InvalidCase(
                "a case has two sides, and they are two materials; the same "
                "material_id on both sides is not a comparison (§5.1)"
            )
        if state is ReviewCaseState.CREATED and has_materials:
            raise InvalidCase(
                "a case in CREATED holds no material; supplying one is the act "
                "that advances it (§5.3)"
            )
        if state in _STATES_REQUIRING_MATERIALS and not has_materials:
            raise InvalidCase(
                f"a case in {state} holds two materials; it cannot be in that "
                "state without them (§5.3)"
            )

        # §5.4. The axes stay consistent without either being derived from the
        # other: a case with no materials has nothing to observe, a case with
        # materials that was never observed is UNCHECKED, and the one state that
        # says an observation happened requires the status that says so.
        if (
            state is ReviewCaseState.CREATED
            and status is not IndependenceObservationStatus.NOT_APPLICABLE
        ):
            raise InvalidCase(
                f"a case in CREATED holds no materials, so independence_status is "
                f"NOT_APPLICABLE; got {status} (§5.4)"
            )
        if (
            state in _STATES_REQUIRING_MATERIALS
            and status is IndependenceObservationStatus.NOT_APPLICABLE
        ):
            raise InvalidCase(
                f"a case in {state} holds two materials, so independence_status is "
                "UNCHECKED or OBSERVED; NOT_APPLICABLE would say there is nothing "
                "to observe (§5.4)"
            )
        if (
            state is ReviewCaseState.INDEPENDENCE_OBSERVED
            and status is not IndependenceObservationStatus.OBSERVED
        ):
            raise InvalidCase(
                f"a case in INDEPENDENCE_OBSERVED holds the observation, so "
                f"independence_status is OBSERVED; got {status} (§5.4)"
            )

    @property
    def terminal(self) -> bool:
        """Whether the case is finished. A terminal case takes no further acts."""
        return self.state in TERMINAL_CASE_STATES

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "review_case_id": self.review_case_id,
            "workspace_id": self.workspace_id,
            "left_material_id": self.left_material_id,
            "right_material_id": self.right_material_id,
            "state": str(self.state),
            "independence_status": str(self.independence_status),
        }


# --------------------------------------------------------------------------
# transitions
# --------------------------------------------------------------------------


def _require_state(
    case: ReviewCase, allowed: tuple[ReviewCaseState, ...], what: str
) -> None:
    if case.terminal:
        raise InvalidTransition(
            f"case {case.review_case_id!r} is {case.state}; a terminal case takes "
            "no further acts"
        )
    if case.state not in allowed:
        raise InvalidTransition(
            f"{what} is not a transition §5.3 permits from {case.state}; "
            f"legal here: {[str(state) for state in allowed]}"
        )


def _require_same_case(case: ReviewCase, other_case_id: str, what: str) -> None:
    if other_case_id != case.review_case_id:
        raise InvalidCase(
            f"{what} belongs to review case {other_case_id!r}, not to "
            f"{case.review_case_id!r}"
        )


def _require_case_materials(
    case: ReviewCase, left: ReviewMaterial, right: ReviewMaterial
) -> None:
    if (left.material_id, right.material_id) != (
        case.left_material_id,
        case.right_material_id,
    ):
        raise InvalidCase(
            "the materials supplied are not the ones this case holds; a case "
            "compares the two sides it was given and does not substitute others"
        )


def _require_subject_of_case(
    case: ReviewCase,
    subject: str,
    *,
    left: ReviewMaterial,
    right: ReviewMaterial,
) -> None:
    """§10.2. The subject names a material of THIS case and a claim it DECLARES.

    Membership is checked against the two materials the caller hands in, not
    against a copy stored on the case: a case holds identifiers, and the values
    are produced at each act. Nothing is repaired and nothing is matched
    approximately — a subject naming a claim that does not exist is refused,
    because a verification of a claim nobody declared is not a verification of
    anything.
    """
    material_id, separator, claim_id = subject.partition("#")
    sides = {left.material_id: left, right.material_id: right}
    material = sides.get(material_id)
    if material is None:
        raise InvalidCase(
            f"subject {subject!r} names material {material_id!r}, which is not "
            "one of this case's two sides"
        )
    if not separator or not claim_id:
        raise InvalidCase(
            f"subject {subject!r} names a material and no claim; a verification "
            "answers a specific declared claim (§10.2)"
        )
    declared = {claim.claim_id for claim in material.claims}
    if claim_id not in declared:
        raise InvalidVerification(
            f"subject {subject!r} names claim {claim_id!r}, which material "
            f"{material_id!r} does not declare. A subject is never repaired, and "
            "an approximate match is not a match"
        )


def create_case(
    *, workspace_id: str, review_case_id: str | None = None
) -> ReviewCase:
    """The first act. A case is scoped to ONE workspace (§5.1)."""
    return ReviewCase(
        review_case_id=review_case_id or new_review_case_id(),
        workspace_id=workspace_id,
    )


def supply_materials(
    case: ReviewCase, *, left: ReviewMaterial, right: ReviewMaterial
) -> ReviewCase:
    """§4.2. Two sides, two distinct registered AgentIds, one workspace."""
    _require_state(case, (ReviewCaseState.CREATED,), "supplying materials")
    if left.material_id == right.material_id:
        raise InvalidCase(
            "the two sides must be two materials; the same material_id on both "
            "sides is not a comparison"
        )
    if left.agent_id == right.agent_id:
        raise InvalidCase(
            f"both sides are attributed to {left.agent_id}; cross-agent review "
            "compares two DISTINCT registered AgentIds (§4.2)"
        )
    for material in (left, right):
        if material.workspace_id != case.workspace_id:
            raise InvalidCase(
                f"material {material.material_id!r} is scoped to workspace "
                f"{material.workspace_id!r}, but the case is scoped to "
                f"{case.workspace_id!r}; materials are refused rather than "
                "re-scoped (§5.1)"
            )
    return dataclasses.replace(
        case,
        left_material_id=left.material_id,
        right_material_id=right.material_id,
        state=ReviewCaseState.MATERIALS_SUPPLIED,
        independence_status=IndependenceObservationStatus.UNCHECKED,
    )


def record_comparison(
    case: ReviewCase,
    *,
    left: ReviewMaterial,
    right: ReviewMaterial,
) -> tuple[ReviewCase, tuple[ReviewFinding, ...]]:
    """§9. The comparison runs here; the findings are returned, not stored.

    `independence_status` is NOT touched: a case compared after an observation
    keeps OBSERVED, a case compared without one keeps UNCHECKED (§5.4).
    """
    _require_state(
        case,
        (ReviewCaseState.MATERIALS_SUPPLIED, ReviewCaseState.INDEPENDENCE_OBSERVED),
        "recording a comparison",
    )
    _require_case_materials(case, left, right)
    findings = compare(left, right, review_case_id=case.review_case_id)
    return (
        dataclasses.replace(case, state=ReviewCaseState.COMPARISON_RECORDED),
        findings,
    )


def observe_independence(
    case: ReviewCase,
    *,
    left: ReviewMaterial,
    right: ReviewMaterial,
    left_record: ExecutionRecord,
    right_record: ExecutionRecord,
) -> tuple[ReviewCase, IndependenceFinding]:
    """§8.2. Reachable only when both records are supplied AND both agree.

    The finding is AI-08's own object, returned unchanged. Recording that an
    observation did not happen is a different thing, and a case without it
    records nothing negative.
    """
    _require_state(
        case, (ReviewCaseState.MATERIALS_SUPPLIED,), "observing independence"
    )
    _require_case_materials(case, left, right)
    independence_module.require_aligned_declaration(left, left_record)
    independence_module.require_aligned_declaration(right, right_record)
    finding = independence_module.observe_independence(left_record, right_record)
    return (
        dataclasses.replace(
            case,
            state=ReviewCaseState.INDEPENDENCE_OBSERVED,
            independence_status=IndependenceObservationStatus.OBSERVED,
        ),
        finding,
    )


def request_verification(
    case: ReviewCase,
    *,
    request: VerificationRequest,
    left: ReviewMaterial,
    right: ReviewMaterial,
) -> ReviewCase:
    """§10.2. A request authorizes nothing and executes nothing.

    The two materials are handed in, not stored: the subject must name a claim
    that one of them actually DECLARES, and the case keeps identifiers only
    (§5.1).
    """
    _require_state(
        case, (ReviewCaseState.COMPARISON_RECORDED,), "requesting verification"
    )
    _require_same_case(case, request.review_case_id, "the verification request")
    _require_case_materials(case, left, right)
    _require_subject_of_case(case, request.subject, left=left, right=right)
    return dataclasses.replace(case, state=ReviewCaseState.VERIFICATION_REQUESTED)


def observe_verification(
    case: ReviewCase,
    *,
    request: VerificationRequest,
    observation: VerificationObservation,
    left: ReviewMaterial,
    right: ReviewMaterial,
) -> ReviewCase:
    """§10.3. The observation is a projection of an AI-06 execution.

    Nothing here fabricates one: an observation exists because a controlled
    verification caller reported what an invocation did. What this function
    checks is the STRUCTURAL binding between the request and the observation —
    the ids, the case and the subject must all agree, and no field is inferred,
    repaired or matched by guesswork.

    ```text
    one request -> at most one observation
    ```

    That rule is structural rather than stored: after an observation the case is
    in VERIFICATION_OBSERVED, §5.3 provides no transition back to
    VERIFICATION_REQUESTED, and a second observation is refused like any other
    illegal transition. AI-10 keeps no record of requests.

    What is NOT claimed: AI-10 cannot prove the observation describes a real
    AI-06 invocation. It verifies structure, and the controlled caller remains
    the only source of an observation (§11.2).
    """
    _require_state(
        case, (ReviewCaseState.VERIFICATION_REQUESTED,), "observing a verification"
    )
    _require_same_case(case, request.review_case_id, "the verification request")
    _require_same_case(case, observation.review_case_id, "the verification observation")

    if request.verification_id != observation.verification_id:
        raise InvalidVerification(
            f"the observation answers verification {observation.verification_id!r}, "
            f"but this case requested {request.verification_id!r}. An observation "
            "that does not answer the request in hand is refused rather than "
            "matched to it"
        )
    if request.subject != observation.subject:
        raise InvalidVerification(
            f"the request is about {request.subject!r} and the observation is about "
            f"{observation.subject!r}; a subject is never substituted"
        )

    _require_case_materials(case, left, right)
    # The two subjects are equal by the check above, so one membership check
    # answers for both: the claim must be one this case's materials declare.
    _require_subject_of_case(case, request.subject, left=left, right=right)
    return dataclasses.replace(case, state=ReviewCaseState.VERIFICATION_OBSERVED)


def record_decision(case: ReviewCase, *, decision: HumanDecision) -> ReviewCase:
    """§12. A human act. There is no path here that derives one."""
    _require_state(
        case,
        (
            ReviewCaseState.COMPARISON_RECORDED,
            ReviewCaseState.VERIFICATION_OBSERVED,
            ReviewCaseState.HUMAN_DECISION_RECORDED,
        ),
        "recording a human decision",
    )
    _require_same_case(case, decision.review_case_id, "the human decision")
    return dataclasses.replace(case, state=ReviewCaseState.HUMAN_DECISION_RECORDED)


def close(case: ReviewCase, *, state: ReviewCaseState) -> ReviewCase:
    """§5.3. An explicit closure: UNRESOLVED, BLOCKED or NOT_RUN.

    Reached from any non-terminal state, including CREATED. None of the three is
    a pass, and none is upgraded into one.
    """
    try:
        target = ReviewCaseState(state)
    except ValueError as exc:
        raise InvalidTransition(
            f"close() takes one of {[str(s) for s in CLOSURE_CASE_STATES]}; "
            f"got {state!r}"
        ) from exc
    if target not in CLOSURE_CASE_STATES:
        raise InvalidTransition(
            f"close() closes as {[str(s) for s in CLOSURE_CASE_STATES]}; "
            f"{target} is reached by its own act, never by close()"
        )
    _require_state(case, tuple(sorted(NON_TERMINAL_CASE_STATES, key=str)), "closing")
    return dataclasses.replace(case, state=target)


def close_with_decision(case: ReviewCase, *, decision: HumanDecision) -> ReviewCase:
    """§5.3. CLOSED, and only an ACCEPTED or REJECTED decision closes a case.

    The decision is supplied at the closure act rather than remembered on the
    case, so a closure cannot happen without one being in hand. A DEFERRED
    decision leaves the case open (§12.2).
    """
    _require_state(
        case, (ReviewCaseState.HUMAN_DECISION_RECORDED,), "closing a decided case"
    )
    _require_same_case(case, decision.review_case_id, "the human decision")
    if decision.decision is HumanDecisionKind.DEFERRED:
        raise InvalidTransition(
            "a DEFERRED decision leaves the case open; only ACCEPTED or REJECTED "
            "closes it (§12.2)"
        )
    return dataclasses.replace(case, state=ReviewCaseState.CLOSED)
