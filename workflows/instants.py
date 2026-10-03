"""AI-13 §8.3 — the one timestamp shape, in one place.

```text
TIMESTAMPS, FROZEN
    format       ISO-8601, UTC, trailing `Z`, second resolution
    a bound is reached when the current time is >= the deadline
```

### Why the shape is validated rather than merely parsed

§8.3 makes a bound an ABSOLUTE instant that survives a resume, and §10.3.1 makes the
narrower of several bounds govern. Both are comparisons between two of these strings.
Two instants that parse but do not share one shape do not compare: `2026-10-03T10:00:00Z`
and `2026-1-3T10:00:00Z` are the same moment written two ways, and a bound decided by
string order would put one of them on the wrong side of the other.

`datetime.strptime` alone is not that check — it accepts `2026-1-3T1:00:00Z`, which §8.3's
"second resolution" does not admit. The round-trip below is the check: a value is one of
these instants only if re-formatting the parsed result reproduces it byte for byte, which
is what makes the shape canonical rather than merely parseable.

Three modules needed this rule — the definition's declared bounds, the run's persisted
deadline, and the bound arithmetic — so it lives here once rather than in three copies
that could disagree about what they accept. A format accepted in one place and refused in
another is how two implementations produce two answers for one bound.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

__all__ = ["INSTANT_FORMAT", "is_instant", "parse_instant", "plus_seconds"]

#: §8.3's frozen format. The only shape any AI-13 instant may take.
INSTANT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def is_instant(text: object) -> bool:
    """True iff `text` is EXACTLY §8.3's shape — not merely parseable by it.

    The round-trip is the whole check. `strptime` alone accepts a non-canonical spelling
    (`2026-1-3T1:00:00Z`), and a second spelling of one instant is a second value for one
    fact — which is the disagreement §8.3 exists to prevent.
    """
    if not isinstance(text, str):
        return False
    try:
        parsed = datetime.strptime(text, INSTANT_FORMAT)
    except ValueError:
        return False
    return parsed.strftime(INSTANT_FORMAT) == text


def parse_instant(text: str) -> datetime:
    """§8.3's instant, parsed as UTC. Callers validate with `is_instant` first."""
    return datetime.strptime(text, INSTANT_FORMAT).replace(tzinfo=timezone.utc)


def plus_seconds(instant: str, seconds: int) -> str:
    """`instant` advanced by `seconds`, as an instant of the same shape.

    This is the one place a DECLARED runtime becomes an ABSOLUTE deadline, and it is
    called at run creation and nowhere else. §8.3: the absolute form is what survives a
    resume, so it is computed once and then read — never re-derived from the duration,
    which is what would hand a resumed run a fresh budget.
    """
    return (parse_instant(instant) + timedelta(seconds=seconds)).strftime(INSTANT_FORMAT)
