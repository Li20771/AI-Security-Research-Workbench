"""AI-07's refusal vocabulary. Contract §10, §12.4.

Each carries a stable `reason_code` and **never an interpolated value**. The rule
is AI-05's and AI-06's: an error message is a place a value escapes to a log, and
a request field is a place a credential can be. A message here names the field,
the rule, and at most a shape fact.

There are deliberately only two, because the contract has only two refusal
conditions that are not outcomes: a request that does not match §5.1, and a rule
set that is not usable (§12.4). Everything else is a `RoutingOutcome` — a value,
not an exception.
"""

from __future__ import annotations

__all__ = ["InvalidEvidence", "InvalidPolicy", "InvalidRequest", "InvalidRules", "RoutingError"]


class RoutingError(Exception):
    """Base class for an AI-07 refusal raised while validating input."""

    reason_code: str = "ROUTING_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidRequest(RoutingError):
    """The request does not match §5.1.

    A field the contract does not define is refused rather than ignored, so a
    prompt body, a tool argument or a credential cannot ride along unremarked.
    An unsupported cost-class or latency-class constraint is this too: §6.4 makes
    it `INVALID_REQUEST` rather than silently ignored.
    """

    reason_code = "INVALID_REQUEST"


class InvalidRules(RoutingError):
    """The rule set is not usable (§12.4).

    An unsupported version, a duplicate `rule_id`, an unknown field, a malformed
    priority, an empty `select`, or a `model_ref` that is not syntactically a
    model ref. A `model_ref` that is well-formed but absent from AI-02's registry
    is **not** this: that is `MODEL_UNAVAILABLE` at evaluation (§7.7, §27).
    """

    reason_code = "INVALID_RULES"


class InvalidPolicy(RoutingError):
    """AI-12 §5. The policy artifact is not usable.

    An unsupported version, a duplicate `rule_id`, an unknown field, a rule with no
    falsifier or no discrimination control, a selecting rule justified by REFERENCE
    evidence (§4.2), a `task_id` used where an evidence identity is required (§5.3),
    a score/weight/confidence field the contract does not define (§4.3, §9), or an
    activatable policy with no rollback metadata (§8).

    A policy that is well-formed but cannot be activated because the measurement it
    needs does not exist is **not** this. That is `DORMANT`, which is a state, not a
    refusal.
    """

    reason_code = "INVALID_POLICY"


class InvalidEvidence(RoutingError):
    """AI-12 §4.1. The supplied AI-11 record set is not usable.

    A missing identity field, a verdict outside AI-11's six, an unknown field, or
    two records claiming one `run_id`. A record that is absent altogether is not
    this either: absence is `UNKNOWN`, and §4.1 forbids regenerating it.
    """

    reason_code = "INVALID_EVIDENCE"
