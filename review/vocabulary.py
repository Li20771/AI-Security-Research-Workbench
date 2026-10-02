"""AI-10 §5, §7, §9, §12 — the vocabularies AI-10 owns, and its bounds.

Three closed vocabularies and one set of bounds, and nothing else:

```text
ReviewCaseState      eleven members   AI-10's lifecycle vocabulary (§5.2)
ReviewSide           two members      LEFT and RIGHT are POSITIONS (§4.2)
ReviewFindingKind    eight members    AI-10's structural observations (§9.2)
HumanDecisionKind    three members    AI-10's human-decision vocabulary (§12.2)
```

**Nothing frozen elsewhere is restated.** `AgentId` and `AgentExecutionOutcome` are
imported from AI-08 where they are used, and `ToolOutcome` from AI-06. Redefining
one would put two definitions of one vocabulary in the repository — the defect
AI-04 §28.2 names and AI-05 §7.1 paid for once.

### The words that collide, recorded rather than repaired

`BLOCKED` appears in `GuardDecision`, `ToolOutcome`, `AgentExecutionOutcome` and in
`ReviewCaseState`. `UNRESOLVED` is both a case state and a finding kind. They are
different types answering different questions, and none may be merged, compared or
converted into another. AI-10 inherits the known cost AI-04 §3, AI-07 §10.1 and
AI-08 §11.2 each record.

### The bounds are security bounds

Every field AI-10 accepts is bounded. A field nobody bounded is a field through
which a transcript, a log or a secret reaches the review layer, and the review
layer is not a content classifier — §15.2 of the contract says plainly where that
guarantee stops.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "BOUNDS",
    "CLOSURE_CASE_STATES",
    "FORBIDDEN_CLAIM_FIELDS",
    "FORBIDDEN_MATERIAL_FIELDS",
    "HumanDecisionKind",
    "IndependenceObservationStatus",
    "ReviewCaseState",
    "ReviewFindingKind",
    "ReviewSide",
    "TERMINAL_CASE_STATES",
]

# --------------------------------------------------------------------------
# §6.2 — the bounded constants, frozen for v1
# --------------------------------------------------------------------------

BOUNDS: dict[str, int] = {
    "max_claims_per_material": 32,
    "max_statement_chars": 1024,
    "max_evidence_refs_per_claim": 32,
    "max_verification_targets_per_claim": 8,
    "max_target_description_chars": 256,
    "max_input_digest_chars": 128,
    "max_rationale_chars": 512,
    "max_identifier_chars": 64,
    "max_execution_id_chars": 128,
    "max_workspace_id_chars": 512,
    "max_subject_chars": 160,
}

MAX_CLAIMS_PER_MATERIAL = BOUNDS["max_claims_per_material"]
MAX_STATEMENT_CHARS = BOUNDS["max_statement_chars"]
MAX_EVIDENCE_REFS_PER_CLAIM = BOUNDS["max_evidence_refs_per_claim"]
MAX_VERIFICATION_TARGETS_PER_CLAIM = BOUNDS["max_verification_targets_per_claim"]
MAX_TARGET_DESCRIPTION_CHARS = BOUNDS["max_target_description_chars"]
MAX_INPUT_DIGEST_CHARS = BOUNDS["max_input_digest_chars"]
MAX_RATIONALE_CHARS = BOUNDS["max_rationale_chars"]
MAX_IDENTIFIER_CHARS = BOUNDS["max_identifier_chars"]
MAX_EXECUTION_ID_CHARS = BOUNDS["max_execution_id_chars"]
MAX_WORKSPACE_ID_CHARS = BOUNDS["max_workspace_id_chars"]
MAX_SUBJECT_CHARS = BOUNDS["max_subject_chars"]


class ReviewSide(StrEnum):
    """§4.2. The two positions in a comparison. Closed, exactly two.

    ```text
    LEFT    a position. Not a role, not precedence, not authority.
    RIGHT   a position. Not a role, not precedence, not authority.
    ```

    `LEFT` does not mean primary, first or better, and `RIGHT` does not mean
    secondary. The words name where a material sits in a comparison and nothing
    else.
    """

    LEFT = "LEFT"
    RIGHT = "RIGHT"


class ReviewCaseState(StrEnum):
    """§5.2. The review lifecycle. Closed, exactly eleven. FROZEN.

    ```text
    CREATED                  the case exists; no material has been supplied
    MATERIALS_SUPPLIED       both sides hold a supplied ReviewMaterial
    INDEPENDENCE_OBSERVED    AI-08's I1-I8 predicate ran and its finding was recorded
    COMPARISON_RECORDED      the structural comparison produced its findings
    VERIFICATION_REQUESTED   at least one VerificationRequest was issued
    VERIFICATION_OBSERVED    at least one VerificationObservation was recorded
    HUMAN_DECISION_RECORDED  a HumanDecision was supplied by a human caller
    CLOSED                   the case is finished; terminal

    UNRESOLVED               terminal closure without a determination
    BLOCKED                  terminal closure: a case-level precondition prevented it
    NOT_RUN                  terminal closure: the review was intentionally not executed
    ```

    `BLOCKED` here is a REVIEW-CASE state. It is not `GuardDecision.BLOCKED`, not
    `ToolOutcome.BLOCKED` and not `AgentExecutionOutcome.BLOCKED`.

    No member of this vocabulary means a truth verdict, and none may be recorded
    as one.
    """

    CREATED = "CREATED"
    MATERIALS_SUPPLIED = "MATERIALS_SUPPLIED"
    INDEPENDENCE_OBSERVED = "INDEPENDENCE_OBSERVED"
    COMPARISON_RECORDED = "COMPARISON_RECORDED"
    VERIFICATION_REQUESTED = "VERIFICATION_REQUESTED"
    VERIFICATION_OBSERVED = "VERIFICATION_OBSERVED"
    HUMAN_DECISION_RECORDED = "HUMAN_DECISION_RECORDED"
    CLOSED = "CLOSED"
    UNRESOLVED = "UNRESOLVED"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"


#: The closure states reachable by an explicit closure act (§5.3).
CLOSURE_CASE_STATES: frozenset[ReviewCaseState] = frozenset(
    {
        ReviewCaseState.UNRESOLVED,
        ReviewCaseState.BLOCKED,
        ReviewCaseState.NOT_RUN,
    }
)

#: Terminal states. No transition leaves one.
TERMINAL_CASE_STATES: frozenset[ReviewCaseState] = frozenset(
    {ReviewCaseState.CLOSED} | set(CLOSURE_CASE_STATES)
)


class IndependenceObservationStatus(StrEnum):
    """§5.4 (Amendment 2). Whether an independence observation was obtained.

    Closed, exactly three. It is a SECOND AXIS beside `ReviewCaseState`: the
    lifecycle says where a review is, and this says whether AI-08's predicate was
    ever run over a supplied, aligned pair of ExecutionRecords.

    ```text
    NOT_APPLICABLE   the case does not yet hold two materials, so an independence
                     observation has no subject
    UNCHECKED        the case holds two materials, and no qualifying pair of
                     ExecutionRecords has been supplied (§6.4's required record)
    OBSERVED         two ExecutionRecords were supplied, every declared attribution
                     field agreed with them, and structural_independence ran
    ```

    ```text
    UNCHECKED means only that the observation has not been obtained. It is NOT
    non-independence, NOT a failure, NOT a violation, NOT a negative finding, and
    NOT `ReviewCaseState.NOT_RUN` or `ReviewCaseState.BLOCKED`.

    OBSERVED does not mean correct, does not mean the two sides agree, does not
    mean the material provenance is verified, and does not mean anything is true.

    No member may describe a pair as independent, non-independent or failed. That
    question belongs to AI-08's finding, which is itself a finding and not a
    verdict.
    ```
    """

    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCHECKED = "UNCHECKED"
    OBSERVED = "OBSERVED"


class ReviewFindingKind(StrEnum):
    """§9.2. The structural observations. Closed, exactly eight. FROZEN.

    ```text
    IDENTICAL_MATERIAL            the two materials' claims_digest are equal
    MATERIAL_DIFFERENCE           the two materials' claims_digest differ
    CLAIM_OVERLAP                 a claim content digest appears on BOTH sides
    CLAIM_UNIQUE_TO_LEFT          a claim content digest appears on the LEFT side only
    CLAIM_UNIQUE_TO_RIGHT         a claim content digest appears on the RIGHT side only
    EVIDENCE_REFERENCE_DIFFERENCE an overlapping claim's evidence_refs sets are not equal
    VERIFICATION_REQUIRED         a claim declares a verification_target with no observation
    UNRESOLVED                    the comparison could not be completed
    ```

    A finding is an OBSERVATION. It is not a verdict, not a ranking, and not a
    statement about which side is right (§9.4).
    """

    IDENTICAL_MATERIAL = "IDENTICAL_MATERIAL"
    MATERIAL_DIFFERENCE = "MATERIAL_DIFFERENCE"
    CLAIM_OVERLAP = "CLAIM_OVERLAP"
    CLAIM_UNIQUE_TO_LEFT = "CLAIM_UNIQUE_TO_LEFT"
    CLAIM_UNIQUE_TO_RIGHT = "CLAIM_UNIQUE_TO_RIGHT"
    EVIDENCE_REFERENCE_DIFFERENCE = "EVIDENCE_REFERENCE_DIFFERENCE"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


class HumanDecisionKind(StrEnum):
    """§12.2. The human's disposition. Closed, exactly three. FROZEN.

    ```text
    ACCEPTED    the human accepted the case's material as a basis for the human's
                own next act. Not a truth verdict, not a verification, and not a
                claim about correctness.
    REJECTED    the human rejected it. Not a statement that any claim is false.
    DEFERRED    the human declined to accept or reject now. The case remains open.
    ```

    None of the three means the material is right. The vocabulary records an act,
    not an outcome about the world.
    """

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


#: §7.3 — field names that never exist on a claim, and never mean anything here.
#: Held as data so the schema, the tests and the Layer 0 gate all read one list.
FORBIDDEN_CLAIM_FIELDS: frozenset[str] = frozenset(
    {
        "confidence",
        "correctness",
        "probability",
        "winner",
        "score",
        "rank",
        "weight",
        "priority",
        "weighting",
        "accuracy",
        "quality",
        "trust",
        "recommendation",
        "recommended",
    }
)

#: §7.3 / §6.2 — the same rule for a material's own field set.
FORBIDDEN_MATERIAL_FIELDS: frozenset[str] = frozenset(
    {
        "confidence",
        "correctness",
        "probability",
        "winner",
        "score",
        "rank",
        "weight",
        "priority",
        "recommendation",
        "recommended",
        "transcript",
        "raw_output",
        "messages",
        "prompt",
        "stdout",
        "stderr",
    }
)
