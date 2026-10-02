"""AI-10 §6.2, §7.1 — the bounded field validators.

Every field AI-10 accepts passes through exactly one of these. They exist so
that "bounded" is one implementation rather than a rule restated at each call
site, and so that a new field cannot be added without choosing a bound.

Two of them are deliberately not local:

```text
reference()   uses AI-08's own reference grammar, imported by identity. A second
              reference grammar would be a second definition of the same shape.
mapping()     refuses a non-mapping rather than coercing one. Silent coercion is
              how a scalar becomes a record nobody decided to create.
```
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from agents.result import is_valid_result_reference

from review.errors import InvalidIdentifier, InvalidReference, ReviewError
from review.vocabulary import MAX_IDENTIFIER_CHARS

__all__ = [
    "bounded_text",
    "closed_keys",
    "identifier",
    "mapping",
    "reference",
    "refused_keys",
    "sequence",
    "single_line",
    "subject",
]

#: Identifiers are opaque tokens. The charset keeps them single-line, greppable
#: and free of the separators a composite key would need.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._:-]+$")

#: A finding subject (§9.1) and a verification subject (§10.2). A whole
#: material, or one claim inside it.
_SUBJECT_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}(#[A-Za-z0-9._:-]{1,64})?$")


def mapping(value: object, where: str) -> Mapping[str, Any]:
    """A mapping, or a refusal. Never a coercion."""
    if not isinstance(value, Mapping):
        raise ReviewError(f"{where} must be an object")
    return value


def sequence(value: object, where: str, *, error: type[ReviewError] = ReviewError) -> tuple:
    """A bounded array, as a tuple. A string is not an array of characters."""
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise error(f"{where} must be an array")
    return tuple(value)


def identifier(
    value: object,
    where: str,
    *,
    maximum: int = MAX_IDENTIFIER_CHARS,
) -> str:
    """An opaque single-line identifier: `[A-Za-z0-9._:-]`, bounded."""
    if not isinstance(value, str) or not value:
        raise InvalidIdentifier(f"{where} must be a non-empty string")
    if len(value) > maximum:
        raise InvalidIdentifier(f"{where} must be at most {maximum} characters")
    if not _IDENTIFIER_RE.match(value):
        raise InvalidIdentifier(
            f"{where} may contain only A-Z a-z 0-9 . _ : - and no whitespace"
        )
    return value


def single_line(
    value: object,
    where: str,
    *,
    maximum: int,
    error: type[ReviewError] = ReviewError,
    allow_empty: bool = False,
) -> str:
    """Bounded text that cannot carry a line break.

    A line break is how one bounded field becomes a transcript, so a field that
    is meant to be a label refuses one.
    """
    if not isinstance(value, str):
        raise error(f"{where} must be a string")
    if not value and not allow_empty:
        raise error(f"{where} must be a non-empty string")
    if len(value) > maximum:
        raise error(f"{where} must be at most {maximum} characters")
    if "\n" in value or "\r" in value:
        raise error(f"{where} must be a single line")
    return value


def bounded_text(
    value: object,
    where: str,
    *,
    maximum: int,
    error: type[ReviewError] = ReviewError,
    allow_empty: bool = False,
) -> str:
    """Bounded text. Prose is allowed to wrap; length is still the bound.

    AI-10 is not a content classifier (§15.2). The enforceable half of the
    secrecy boundary is that the value is bounded and never persisted, not that
    its content is inspected.
    """
    if not isinstance(value, str):
        raise error(f"{where} must be a string")
    if not value.strip() and not allow_empty:
        raise error(f"{where} must be a non-empty string")
    if len(value) > maximum:
        raise error(f"{where} must be at most {maximum} characters")
    if "\x00" in value:
        raise error(f"{where} must not contain a NUL character")
    return value


def reference(value: object, where: str) -> str:
    """One of AI-08's two declared reference shapes (§6.2).

    ```text
    sha256:<64 lowercase hex>
    ref:<opaque token>
    ```

    A reference is a DECLARATION. It is not dereferenced here, and nothing in
    AI-10 asserts that the referenced thing exists.
    """
    if not isinstance(value, str) or not is_valid_result_reference(value):
        raise InvalidReference(
            f"{where} must be `sha256:<64 lowercase hex>` or `ref:<opaque token>`; "
            "raw content is not a reference"
        )
    return value


def subject(value: object, where: str = "subject") -> str:
    """`"<material_id>"` or `"<material_id>#<claim_id>"` — what an observation names.

    A whole material or one claim inside it. Nothing else: a subject is a label
    for what was observed, and a free-form one would be a place for content to
    ride in.
    """
    if not isinstance(value, str) or not _SUBJECT_RE.match(value):
        raise ReviewError(
            f"{where} must be `<material_id>` or `<material_id>#<claim_id>`, "
            "each part a bounded identifier"
        )
    return value


def closed_keys(
    raw: Mapping[str, Any],
    allowed: frozenset[str],
    where: str,
    *,
    error: type[ReviewError] = ReviewError,
) -> None:
    """Refuse a key the schema does not define.

    An unlisted field reaching a record is a field nobody decided should be
    there, which is the rule every `to_mapping` in this repository already
    states from the other side.
    """
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise error(
            f"{where} has field(s) the contract does not define: "
            f"{', '.join(map(str, unknown))}"
        )


def refused_keys(
    raw: Mapping[str, Any],
    refused: frozenset[str],
    where: str,
    why: str,
    *,
    error: type[ReviewError] = ReviewError,
) -> None:
    """Refuse named keys with a message that says why, not just "unknown".

    A refusal that explains itself is the difference between a caller fixing the
    call and a caller guessing.
    """
    found = sorted(name for name in raw if name in refused or name.startswith("recommended"))
    if found:
        raise error(f"{where} carries a field the contract refuses: {', '.join(found)}. {why}")
