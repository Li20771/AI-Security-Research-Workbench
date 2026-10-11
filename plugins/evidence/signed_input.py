"""AI-05-CJ-1 — the canonical serialization of the SIGNED INPUT (§7.3.4, §7.3.6).

**This module is not the digest path.** `guard/digest.canonical_json` serializes
the §15.2 digest projections, and its docstring records that it sorts object keys
by *Unicode code point*. AI-05-CJ-1 rule 2 requires RFC 8785's ordering — by
*UTF-16 code unit*, compared as unsigned 16-bit values. §7.3.6 states that the
two orders differ only for keys containing characters above the BMP, that every
field name the Evidence schema admits is ASCII so the two coincide on conforming
input, and that an implementation sorting by code point **is non-conforming even
where the output matches**. §7.3.6 also forbids unifying the two. They are two
functions, over two values, for two purposes; this is the signed-input one.

This module imports neither `json` nor `os`. It needs neither: the profile
renders JSON text by hand, which is what makes it possible to obey rule 4's
escaping and rule 7's integer domain exactly rather than approximately. Keeping
it import-free also keeps it inside `EVIDENCE_IO_MODULES`' restriction — only
`store.py` and `producer_auth.py` may reach a filesystem import, and this module
is neither.

The profile has exactly one extension over RFC 8785, and it is in the number
domain: INTEGERS are plain decimal with arbitrary precision, which is what
preserves `g_ordinal`'s existing unbounded non-negative integer rule
(grammar.py:380-392).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping

from plugins.evidence.errors import AuthenticationInputUnserializable

__all__ = [
    "DOMAIN_TAG",
    "PROOF_VERSION",
    "SEPARATOR",
    "canonical_serialization",
    "signed_input",
]

#: §7.3.4 — the ASCII bytes `workbench.evidence.producer-proof`, 33 of them.
DOMAIN_TAG = b"workbench.evidence.producer-proof"

#: §7.3.4 — the ASCII bytes `1`. Part of the signed input and NOT negotiated.
PROOF_VERSION = b"1"

#: §7.3.4 — a single 0x00 byte.
SEPARATOR = b"\x00"


#: §7.3.6 rule 4 — RFC 8785's minimal escape set, and NOTHING else is escaped.
#: Every other character is emitted literally, INCLUDING U+007F and every
#: non-ASCII character: "café" is five UTF-8 bytes, not eleven ASCII characters.
_ESCAPES: dict[str, str] = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}


def _unserializable(why: str) -> AuthenticationInputUnserializable:
    return AuthenticationInputUnserializable(
        f"the submitted mapping has no AI-05-CJ-1 canonical serialization: {why}. "
        "§7.3.6 refuses a value it cannot serialize rather than coercing, partially "
        "serializing or repairing it — a coercion would mean the producer and the "
        "verifier signed different bytes while both believing otherwise (§7.3.5 V5)"
    )


def _render_string(value: str) -> str:
    """Rule 4. Escapes the minimal set; emits everything else literally."""
    out = ['"']
    for char in value:
        escape = _ESCAPES.get(char)
        if escape is not None:
            out.append(escape)
        elif char < " ":
            # Rule 4: other C0 controls as \u00xx, with LOWERCASE hex digits.
            out.append("\\u%04x" % ord(char))
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _ordering_key(key: str) -> bytes:
    """Rule 2 — RFC 8785's key ordering, as bytes we can compare lexicographically.

    Big-endian UTF-16 encodes each code unit as two bytes, so byte-wise
    comparison of two encoded keys is exactly the required comparison of their
    code-unit sequences as unsigned 16-bit values, shorter-first on a prefix.
    Sorting the decoded `str` instead would be code-point order, which rule 2
    names as a real trap and refuses.
    """
    return key.encode("utf-16-be")


def _render(value: Any) -> str:
    """Rules 1, 2, 6 and 7. Raises for anything out of domain."""
    # Rule 1 dispatch order matters: `isinstance(True, int)` is True, so `bool`
    # is tested BEFORE `int`, or `True` would render as `1`.
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, StrEnum):
        # Rule 1: the member's canonical STRING value — the same bytes a plain
        # `str` of that value produces. RFC 8785 has no notion of an enum.
        return _render_string(str(value))
    if isinstance(value, str):
        return _render_string(value)
    if isinstance(value, int):
        # Rule 7: plain decimal, arbitrary precision. Python's `str(int)` is
        # exactly that — no exponent, no decimal point, no leading zeros.
        return str(value)
    if isinstance(value, Mapping):
        return _render_object(value)
    if isinstance(value, (list, tuple)):
        # Rule 1: array order is PRESERVED, never sorted (rule 6 separators).
        return "[" + ",".join(_render(item) for item in value) + "]"
    raise _unserializable(
        f"{type(value).__name__} is not in AI-05-CJ-1's domain (rule 1); float, "
        "Decimal, bytes, set, frozenset and datetime are each refused, never coerced"
    )


def _render_object(mapping: Mapping[Any, Any]) -> str:
    keys = list(mapping.keys())
    for key in keys:
        if not isinstance(key, str):
            raise _unserializable(
                f"an object key is {type(key).__name__}, not a string (rule 1); "
                "AI-05-CJ-1 renders keys as strings and does not coerce one"
            )
    try:
        ordered = sorted(keys, key=_ordering_key)
    except UnicodeEncodeError as exc:
        raise _unserializable(
            "an object key carries an unpaired surrogate, which is out of domain "
            "(rule 9)"
        ) from exc
    members: list[str] = []
    for key in ordered:
        members.append(_render_string(key) + ":" + _render(mapping[key]))
    return "{" + ",".join(members) + "}"


def canonical_serialization(value: Any) -> bytes:
    """The AI-05-CJ-1 canonical bytes of `value` (§7.3.6).

    Returns BYTES, not text: rule 5 makes UTF-8 encoding the last step, and the
    bytes are what a signer signs and a verifier compares. Raises
    `AuthenticationInputUnserializable` for any value the profile refuses —
    including a string carrying an unpaired surrogate, which rule 9 refuses
    because rule 5 cannot be applied to it.
    """
    text = _render(value)
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise _unserializable(
            "a string carries an unpaired surrogate, so rule 5 cannot be applied "
            "to it (rule 9)"
        ) from exc


def signed_input(mapping: Any) -> bytes:
    """§7.3.4 — the bytes a producer signs and a verifier reconstructs.

    ```text
    DOMAIN_TAG || SEPARATOR || PROOF_VERSION || SEPARATOR || canonical_serialization(mapping)
    ```

    The tag and the version are INSIDE the signed bytes rather than checked
    beside them, so neither can be changed, downgraded or upgraded without
    invalidating every proof minted under the other one (§7.3.6, vectors 3
    and 4).
    """
    return (
        DOMAIN_TAG
        + SEPARATOR
        + PROOF_VERSION
        + SEPARATOR
        + canonical_serialization(mapping)
    )
