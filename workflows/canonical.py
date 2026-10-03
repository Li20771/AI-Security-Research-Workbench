"""AI-13 §7.4 — the canonical form. ONE definition, for every digest in the phase.

```text
PREIMAGE   the UTF-8 bytes of the canonical JSON object formed from the record's
           fields EXCLUDING the record's own digest field.
```

An earlier revision of the contract said a checkpoint "carries a digest of its own
bytes", which is circular: the digest field is part of the bytes it would cover, so no
value satisfies it. §7.4 freezes the preimage instead, and this module is that section
in code — the checkpoint digest, the run record digest and the definition digest all
compute through `digest_of` rather than each growing its own encoder.

### Why every rule here is frozen rather than chosen

```text
keys sorted        two writers that agree about the FIELDS must agree about the bytes
no whitespace      otherwise a formatter changes a digest
integers only      two implementations disagreeing about 1.0 vs 1 produce two digests
                   for one fact, and the disagreement is invisible until it matters
null == absent     a digest that turned on whether a writer emitted `null` or omitted
                   a key would make equivalent records differ, and a reader could not
                   tell which had happened
empty != absent    [] is a real value (an empty list of steps) and is PRESENT
```

Nothing in this module reads a file, starts a process, or touches a network.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from workflows.errors import InvalidRecord

__all__ = ["CANONICAL_VERSION", "canonical_body", "digest_of", "verify_digest"]

#: The version of the rules below. It enters no preimage — §7.4 excludes the digest
#: field and nothing else — so changing any rule here is a contract amendment (§20),
#: never a version bump an implementation may take on its own.
CANONICAL_VERSION = 1


def _refuse_non_integer(value: object, where: str) -> None:
    """§7.4: integers only. A float is a digest-covered field is refused."""
    if isinstance(value, bool):
        return
    if isinstance(value, float):
        raise InvalidRecord(
            f"{where} is a float; a digest-covered field carries integers only, because "
            "two implementations that disagree about 1.0 versus 1 produce two digests "
            "for one fact (§7.4)"
        )


def _walk(value: object, where: str) -> Any:
    """Canonicalise one value, refusing what §7.4 does not define."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        _refuse_non_integer(value, where)
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return {str(key): _walk(item, f"{where}.{key}") for key, item in value.items()}
    if isinstance(value, (bytes, bytearray)):
        raise InvalidRecord(
            f"{where} is raw bytes; a record carries references and digests, never "
            "content (§7.2, §15.2)"
        )
    if isinstance(value, Sequence):
        return [_walk(item, f"{where}[]") for item in value]
    raise InvalidRecord(f"{where} is a {type(value).__name__}, which §7.4 does not define")


def _prune(value: Any) -> Any:
    """Drop null-valued object members. §7.4: null and absent are the same."""
    if isinstance(value, dict):
        return {key: _prune(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_prune(item) for item in value]
    return value


def canonical_body(fields: Mapping[str, Any], *, digest_field: str) -> bytes:
    """The PREIMAGE of `fields`, with `digest_field` excluded.

    ```text
    FROZEN: the digest field is excluded, and NOTHING else. A record carrying two
            digest-shaped fields is invalid rather than resolved by preferring one.
    ```
    """
    if digest_field not in fields:
        # A record with no digest field is not excluded-from-its-own-preimage; it is a
        # caller computing a digest over something that is not one of these records.
        raise InvalidRecord(
            f"the record carries no {digest_field!r} field to exclude; §7.4 defines the "
            "preimage of a record that HAS a digest, and a digest over anything else is "
            "a different fact"
        )

    body = {key: value for key, value in fields.items() if key != digest_field}
    canonical = _prune(_walk(body, "body"))
    # `sort_keys` is the code-point ordering §7.4 freezes; `separators` removes the
    # insignificant whitespace; `ensure_ascii=False` keeps strings UTF-8, and
    # `allow_nan=False` refuses the one float JSON would otherwise smuggle through.
    return json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_of(fields: Mapping[str, Any], *, digest_field: str) -> str:
    """SHA-256 over the canonical body, lowercase hexadecimal (§7.4)."""
    return hashlib.sha256(canonical_body(fields, digest_field=digest_field)).hexdigest()


def verify_digest(fields: Mapping[str, Any], *, digest_field: str, reason_code: str) -> None:
    """Raise `InvalidRecord(reason_code)` unless the record's digest verifies.

    The caller names the reason code, because the same check answers a different
    question for a checkpoint (`CHECKPOINT_CORRUPT`) than for a run record, and a
    shared helper that chose one of those names would mislabel the other.
    """
    recorded = fields.get(digest_field)
    if not isinstance(recorded, str) or not recorded:
        raise InvalidRecord(
            f"{reason_code}: the record carries no {digest_field!r}", reason_code=reason_code
        )
    expected = digest_of(fields, digest_field=digest_field)
    if recorded != expected:
        raise InvalidRecord(f"{reason_code}: the digest does not verify", reason_code=reason_code)
