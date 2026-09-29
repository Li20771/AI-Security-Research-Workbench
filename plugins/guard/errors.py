"""Guard failure taxonomy.

Implements AI-04 contract §21 and §27 of the AI-04-B brief. Every failure in
this package maps to a *decision*, never to an escaping exception: a caller
that received a traceback would learn nothing about what was wrong, and the
only safe default in the absence of an answer is `BLOCKED`.

The mapping is fixed by the contract and is not a judgement call here:

    malformed request                  -> DENY     (§21)
    invalid / missing / unsupported    -> BLOCKED  (§9.2, §11.6, §21)
    upstream truth UNKNOWN             -> UNKNOWN  (§2.3)
    unexpected evaluator failure       -> BLOCKED  (fail-closed, §27)

These classes exist so the *reason* survives the conversion. `BLOCKED` on its
own tells a caller nothing; `BLOCKED` plus `POLICY_DUPLICATE_RULE_ID` tells
them exactly what to fix.
"""

from __future__ import annotations


class GuardError(Exception):
    """Base class. Never raised out of `evaluate` -- it is converted."""

    #: Machine-readable reason code recorded on the decision.
    reason_code: str = "GUARD_ERROR"


class RequestMalformed(GuardError):
    """The request cannot be read as an authorization input.

    A determined negative finding about the *input*, so §21 makes it `DENY`.
    This is deliberately not `BLOCKED`: the request is not missing something
    Guard needed, it is wrong.
    """

    reason_code = "REQUEST_MALFORMED"


class RequestUnscoped(GuardError):
    """The request carries no usable workspace scope (§15.1 absolute deny)."""

    reason_code = "REQUEST_UNSCOPED"


class PolicyInvalid(GuardError):
    """A supplied policy violates a §9.2 validation invariant.

    `BLOCKED`, never `DENY`: an invalid policy is an input Guard could not use,
    not a decision that the request is forbidden.
    """

    reason_code = "POLICY_INVALID"


class PolicyDigestMismatch(PolicyInvalid):
    """Declared digest does not match the canonical form (§9.2)."""

    reason_code = "POLICY_DIGEST_MISMATCH"


class PolicyDuplicateRuleId(PolicyInvalid):
    """Two rules share a `rule_id` (§9.2, Amendment 9)."""

    reason_code = "POLICY_DUPLICATE_RULE_ID"


class PolicyMissing(GuardError):
    """No policy was supplied (§9.1)."""

    reason_code = "POLICY_MISSING"


class PolicyWorkspaceMismatch(GuardError):
    """The policy names a different workspace from the request (§5).

    A *determined* mismatch, so §21 makes it `DENY` rather than `BLOCKED`.
    """

    reason_code = "POLICY_WORKSPACE_MISMATCH"


class WorkspaceUnresolvable(GuardError):
    """The request's workspace cannot be resolved (§21)."""

    reason_code = "WORKSPACE_UNRESOLVABLE"


class PredicateUnsupported(GuardError):
    """An unsupported predicate, field, literal or vocabulary value (§11.6).

    Never `REJECTED`: a policy defect must not present as a clean "this rule
    does not apply and something else may allow it".
    """

    reason_code = "PREDICATE_UNSUPPORTED"


class OrderingCycle(GuardError):
    """The specificity relation contained a cycle (§12.2.2).

    Should be unreachable: `⊏` is a partial order. The guard exists because the
    alternative to detecting it is an infinite loop, and an infinite loop in an
    authorization path is worse than a refusal.
    """

    reason_code = "ORDERING_CYCLE"


__all__ = [
    "GuardError",
    "OrderingCycle",
    "PolicyDigestMismatch",
    "PolicyDuplicateRuleId",
    "PolicyInvalid",
    "PolicyMissing",
    "PolicyWorkspaceMismatch",
    "PredicateUnsupported",
    "RequestMalformed",
    "RequestUnscoped",
    "WorkspaceUnresolvable",
]
