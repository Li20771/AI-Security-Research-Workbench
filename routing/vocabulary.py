"""AI-07's own vocabulary. Contract §10.1.

```text
RoutingOutcome — closed, owned by AI-07

    SELECTED            one eligible candidate was selected
    NO_ELIGIBLE_MODEL   no candidate satisfied the rules and constraints
    MODEL_UNAVAILABLE   a selected candidate is no longer resolvable
    INVALID_REQUEST     the request does not match §5.1
    INVALID_RULES       the rule set is not usable (§12.4)
    ROUTER_ERROR        the Router could not complete the evaluation
```

**This is AI-07's own and is not merged with any other.** Contract §10.1:

```text
GuardDecision   AI-04's   ALLOW|DENY|BLOCKED|UNKNOWN
StatusValue     AI-03's   PASS|FAIL|BLOCKED|NOT_RUN|UNKNOWN
ToolOutcome     AI-06's   COMPLETED|FAILED|BLOCKED|NOT_RUN|TIMED_OUT|UNKNOWN
```

`BLOCKED` and `UNKNOWN` appear in more than one of those. That is a known cost, recorded by AI-04
§3 as a defect AI-03 already paid for once, and AI-07 does not remove it by merging the types.

**`SELECTED` means one thing**: the Router selected a model profile. It does not mean the task
succeeded, the provider succeeded, a tool succeeded, the research passed, or any Evidence passed.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["RoutingOutcome"]


class RoutingOutcome(StrEnum):
    """What AI-07 says about an evaluation. Contract §10.1. Closed."""

    SELECTED = "SELECTED"
    NO_ELIGIBLE_MODEL = "NO_ELIGIBLE_MODEL"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_RULES = "INVALID_RULES"
    ROUTER_ERROR = "ROUTER_ERROR"
