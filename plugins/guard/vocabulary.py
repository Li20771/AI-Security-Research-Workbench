"""Guard's typed vocabulary.

Implements AI-04 contract §2, §3, §4.2, §11.3, §14.2, §18.2. Every enumerated
type here is **closed**: §4.2 forbids treating an unlisted value as an ordinary
one, so each is a `StrEnum` and a value outside its set is unsupported rather
than merely unfamiliar.

**Nothing frozen elsewhere is restated.** AI-02's `CapabilityStatus` and AI-03's
`WorkingTreeState`, `ItemKind`, `StatusValue` and `Freshness` are *imported*
wherever they are used (§28.2 of the plan: redefining one is a defect, not a
convenience — two definitions in one repository means two places to update and
one of them gets forgotten). They are re-exported here only so a caller has one
import for Guard's surface.

Two things are easy to get wrong and are called out in the code:

* `BLOCKED` appears in both `GuardDecision` and the Workbench *test* status
  vocabulary (§3). They are different types with different meanings, which is
  why the decision record carries `CheckResult` (§18.2) rather than a shared
  untyped `status` string -- the collision AI-03 already paid for once with
  `ContextStatus.COMPLETE`.
* `GuardDecision` and `CheckResult` are **never** interchangeable, and
  `aggregate` is the only function that combines check results.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Iterable, Mapping

# --------------------------------------------------------------------------
# Frozen elsewhere -- imported, never redefined (§28.2)
# --------------------------------------------------------------------------

from plugins.context.vocabulary import (  # noqa: F401  (re-exported)
    Freshness,
    ItemKind,
    StatusValue,
    WorkingTreeState,
)
from providers.model_profile import CapabilityStatus  # noqa: F401  (re-exported)


class GuardDecision(StrEnum):
    """The four authorization outcomes (contract §2.1). Exactly four.

    Non-equivalent: `UNKNOWN`, `BLOCKED` and `DENY` are each `!= ALLOW`.

    `UNKNOWN` is a *definite statement about a fact* -- an upstream truth model
    says the fact is unknown (§2.3) -- not a synonym for "we could not look".
    That is `BLOCKED`.
    """

    ALLOW = "ALLOW"
    DENY = "DENY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class CheckResult(StrEnum):
    """The outcome of evaluating one predicate or precondition (contract §18.2).

    A **distinct type** from `GuardDecision`, never represented by a shared
    untyped `status` string: `BLOCKED` is a decision, and a check is never
    `BLOCKED`, it is `UNAVAILABLE`.
    """

    SATISFIED = "SATISFIED"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"
    INDETERMINATE = "INDETERMINATE"


#: The aggregation precedence, frozen by §14.2. Higher rank wins.
#:
#:     UNAVAILABLE > INDETERMINATE > REJECTED > SATISFIED
#:
#: `UNAVAILABLE` outranks `INDETERMINATE` because both stop the walk and the tie
#: goes to the actionable report: an unsupported or missing input can be
#: supplied or fixed, whereas an unknown fact can only be established -- and
#: fixing the first frequently dissolves the second.
CHECK_RESULT_RANK: Mapping[CheckResult, int] = {
    CheckResult.UNAVAILABLE: 3,
    CheckResult.INDETERMINATE: 2,
    CheckResult.REJECTED: 1,
    CheckResult.SATISFIED: 0,
}

#: How each aggregate maps to a decision (§18.2). `REJECTED` maps to nothing:
#: a rejected candidate simply does not decide, and the walk continues.
AGGREGATE_DECISION: Mapping[CheckResult, GuardDecision | None] = {
    CheckResult.UNAVAILABLE: GuardDecision.BLOCKED,
    CheckResult.INDETERMINATE: GuardDecision.UNKNOWN,
    CheckResult.SATISFIED: None,  # the candidate's effect decides
    CheckResult.REJECTED: None,  # continue the walk
}


def aggregate(results: Iterable[CheckResult]) -> CheckResult:
    """Combine predicate results by the frozen §14.2 precedence.

    **Order-independent by construction.** It reduces by `max` over a total
    rank, so it is commutative and associative: any permutation of the same
    results yields the same aggregate. That is what lets §20.3 declare `match`
    and `conditions[]` set-semantic without an order-dependent result hiding
    underneath a determinism guarantee.

    An empty collection aggregates to `SATISFIED`: every predicate of an empty
    set holds vacuously, which is what §11.1 means by "an empty list is TRUE".
    """
    highest = CheckResult.SATISFIED
    for result in results:
        if CHECK_RESULT_RANK[result] > CHECK_RESULT_RANK[highest]:
            highest = result
    return highest


# --------------------------------------------------------------------------
# Guard's own closed vocabularies (§4, §4.2)
# --------------------------------------------------------------------------


class ActorType(StrEnum):
    """Contract §4. Closed."""

    HUMAN = "human"
    AGENT = "agent"
    SERVICE = "service"
    UNKNOWN = "unknown"


class PermissionLevel(StrEnum):
    """Contract §4.1, frozen from AI-00 §6 -- the six levels, verbatim.

    A first-class field, never inferred from `action.id`: encoding privilege in
    an opaque identifier loses a frozen architectural concept and makes rules
    that key on it unwritable.
    """

    READ = "read"
    ANALYZE = "analyze"
    TEST = "test"
    MODIFY = "modify"
    SYSTEM_CHANGE = "system-change"
    REMOTE_CHANGE = "remote-change"


class TargetKind(StrEnum):
    """Contract §4. Closed."""

    REPOSITORY = "repository"
    FILESYSTEM = "filesystem"
    SYSTEM = "system"
    SERVICE = "service"
    NETWORK = "network"
    REMOTE = "remote"
    CAN_BUS = "can_bus"
    ECU = "ecu"
    VEHICLE = "vehicle"
    ACTUATOR = "actuator"
    PROVIDER = "provider"
    SECRET_MATERIAL = "secret_material"
    UNKNOWN = "unknown"


class TargetEnvironment(StrEnum):
    """Contract §4, §16. Closed.

    §16: `unknown` is never inferred to be `simulated`. An unclassified target
    is not a safe target.
    """

    SIMULATED = "simulated"
    ISOLATED = "isolated"
    REAL = "real"
    UNKNOWN = "unknown"


class TargetInterface(StrEnum):
    """Contract §4, §16. Closed."""

    SIMULATOR = "simulator"
    ISOLATED_HARNESS = "isolated_harness"
    VCAN = "vcan"
    CAN = "can"
    CAN_FD = "can_fd"
    LIN = "lin"
    ETHERNET = "ethernet"
    UNKNOWN = "unknown"


class TargetSensitivity(StrEnum):
    """Contract §4, §17. Closed."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SECRET_MATERIAL = "secret_material"
    UNKNOWN = "unknown"


class ApprovalStatus(StrEnum):
    """Contract §8, §4. Closed.

    Only `VERIFIED` may satisfy an approval-gated condition. `UNKNOWN` is
    `BLOCKED` rather than `UNKNOWN` because approval is a precondition *this
    contract owns* and is fail-closed about (§8.1), unlike context and
    capability, whose truth models Guard merely inherits.
    """

    VERIFIED = "VERIFIED"
    MISSING = "MISSING"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class RuleEffect(StrEnum):
    """Contract §10. `BLOCKED` and `UNKNOWN` are outcomes, not policy effects.

    If a policy could declare "block", a policy author could fabricate the
    appearance of an unsatisfied precondition.
    """

    ALLOW = "ALLOW"
    DENY = "DENY"


#: Effect rank for §12 step 3: `DENY` before `ALLOW` at equal priority. Lower
#: wins.
EFFECT_RANK: Mapping[RuleEffect, int] = {
    RuleEffect.DENY: 0,
    RuleEffect.ALLOW: 1,
}


#: Environments and interfaces that §16 treats as safe defaults, eligible for
#: normal policy evaluation. Everything else -- including `unknown` -- is not.
SAFE_ENVIRONMENTS: frozenset[TargetEnvironment] = frozenset(
    {TargetEnvironment.SIMULATED, TargetEnvironment.ISOLATED}
)

SAFE_INTERFACES: frozenset[TargetInterface] = frozenset(
    {
        TargetInterface.SIMULATOR,
        TargetInterface.ISOLATED_HARNESS,
        TargetInterface.VCAN,
    }
)


__all__ = [
    "AGGREGATE_DECISION",
    "CHECK_RESULT_RANK",
    "EFFECT_RANK",
    "SAFE_ENVIRONMENTS",
    "SAFE_INTERFACES",
    "ActorType",
    "ApprovalStatus",
    "CapabilityStatus",
    "CheckResult",
    "Freshness",
    "GuardDecision",
    "ItemKind",
    "PermissionLevel",
    "RuleEffect",
    "StatusValue",
    "TargetEnvironment",
    "TargetInterface",
    "TargetKind",
    "TargetSensitivity",
    "WorkingTreeState",
    "aggregate",
]
