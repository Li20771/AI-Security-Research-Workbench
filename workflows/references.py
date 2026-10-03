"""AI-13 §11.2, §13.1 — the DECLARED REFERENCE, validated once.

Several fields in this phase are references rather than content: who cancelled a run
(§11.2), and who produced an approval (§13.1). They share one rule, and it lives here so
that two of them cannot drift apart — a shape accepted at one boundary and refused at
another is how two implementations produce two answers for one fact.

```text
FROZEN: §11.2 records WHO cancelled and WHY "as a declared reference", and does not
        adjudicate whether the reason was good.
```

The difference between a reference and a sentence is the whole of the rule. A field that
could hold a sentence is a field that could hold a secret, a transcript or a judgement,
and the records here are the artifacts a reader trusts most — so the shape is enforced
rather than promised in a comment.

This module deliberately does NOT live in `run.py`. An approval's actor reference is
validated before any run record exists, and a validator that lived with the run record
would make the approval module import it — which is the direction the dependency must
not run.
"""

from __future__ import annotations

import re

from workflows.errors import InvalidRecord

__all__ = ["MAX_REFERENCE_CHARS", "REFERENCE_ALPHABET", "reference"]

#: §11.2. The alphabet a DECLARED reference may use, and its bound.
REFERENCE_ALPHABET = "A-Za-z0-9._:-"
_REFERENCE_RE = re.compile(rf"^[{REFERENCE_ALPHABET}]+$")
MAX_REFERENCE_CHARS = 200


def reference(value: object, where: str) -> str:
    """A DECLARED reference: an identifier, bounded, and never free-form text.

    The message names the field and the rule and no value, because an error message is a
    place a value escapes to a log.
    """
    if not isinstance(value, str) or not value:
        raise InvalidRecord(f"{where} must be a non-empty string")
    if len(value) > MAX_REFERENCE_CHARS:
        raise InvalidRecord(f"{where} must be at most {MAX_REFERENCE_CHARS} characters")
    if not _REFERENCE_RE.match(value):
        raise InvalidRecord(
            f"{where} may contain only {REFERENCE_ALPHABET} and no whitespace; this is "
            "a declared REFERENCE, not free-form text"
        )
    return value
