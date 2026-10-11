"""The ONE READER of the designated producer trust configuration (§7.3.11).

This module is the sole place `WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG` is read,
the sole place the resulting state lives, and the sole place §7.3.5's V1-V5 run.
§7.3.2 states the properties; §7.3.11 names the mechanism this module implements.

Four things about it are load-bearing and each is stated where it happens:

**The read is the module's initialization.** There is no function that reads the
variable (§7.3.11, "WHEN THE READ HAPPENS"). A second read would be a second
trust root, and a function-shaped read is a read that can be called twice.

**Initialization does not raise.** An invalid configuration is a STATE this
process holds, not an exception and not a failure to import. A module whose
import raised would leave the caller with no admission result at all, and would
make a deployment misconfiguration appear as a programming error rather than as
the REJECTED outcome §7.3.8 defines.

**The state is private and immutable.** It is never returned as a whole, never
handed out as a structure another module could mutate, and not rebindable by any
code in this repository. §31.3's IMMUTABLE STATE rule; §31.3's trust-boundary
qualification records what that rule does and does not deliver — it is a
SOURCE-TREE rule, not a runtime sandbox.

**No public function accepts a trust root.** Not a key, a mapping, an anchor, a
verifier, a configuration object or a configuration path. §7.3.2 and §31.3.

The configuration carries PUBLIC key material only. This module holds verification
keys and cannot mint the proofs it checks, which is the same boundary AI-13 §13.3
draws for its own anchor — drawn here independently, because §7.3.10 keeps the
two trust domains apart.

This module imports `os` and `json`, which §31.3 permits for it and for no other
module in this package. That exception is two imports in one named module, not a
relaxation of the package's I/O boundary: it may not read a file, call `open()`,
walk a path, or reach any configuration source other than the one variable below.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from plugins.evidence.errors import (
    AuthenticationInputMismatch,
    AuthenticationKeyUnavailable,
    AuthenticationProofMalformed,
    AuthenticationProofMissing,
    AuthenticationSignatureInvalid,
    MissingRequiredField,
    RecordMalformed,
)
from plugins.evidence.grammar import g_text
from plugins.evidence.models import ADMITTED_EVENTS
from plugins.evidence.signed_input import signed_input

__all__ = ["authenticate", "designated_key_for"]

#: §7.3.11 — the ONE place the designated mapping is read from. This literal is
#: the only occurrence of the variable's name outside the test launcher, and
#: §31.3's NO MUTATION rule makes a second occurrence a finding.
_ENV_NAME = "WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG"

#: §7.3.11 — the value's members, closed-keyed and both required.
_MEMBERS = frozenset({"collision_policy", "producer_keys"})

#: §7.3.11 — exactly the two JSON strings; it SELECTS between §7.3.2's policies.
_POLICIES = frozenset({"A", "B"})

#: §7.3.11 — a public key is exactly 64 LOWERCASE hexadecimal characters.
_HEX_LOWER = frozenset("0123456789abcdef")

#: §7.3.3 — RFC 4648 §5: A-Z a-z 0-9 - _ , and no padding.
_B64U = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)

#: §7.3.3 — the signature is 64 bytes, carried as 128 lowercase hex characters.
_SIGNATURE_CHARS = 128

#: §7.3.5 V3 — the state's two SHAPES, and both are final (§7.3.11).
class _Invalid:
    """The process-lifetime state when startup found no usable configuration.

    §7.3.11: an INVALID state is RETAINED as INVALID. Every admission reaching
    V3 under it is REJECTED with AUTHENTICATION_KEY_UNAVAILABLE — the same code,
    for every submission, for the rest of the process. There is no re-read, no
    default, and no last-known-good fallback for it to reach.
    """

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class _Designated:
    """A VALID mapping: the policy it selects and the keys it designates.

    Frozen and slotted. `keys` is a read-only view, and this object is never
    returned by any public function of this module — the reader answers a
    PER-TOKEN question and exposes neither the mapping nor the policy table.
    """

    policy: str
    keys: Mapping[str, bytes]
    recognized: frozenset[str]


_INVALID = _Invalid()


def _reject_constant(name: str) -> Any:
    """§7.3.11 — `NaN`, `Infinity` and `-Infinity` are NOT JSON."""
    raise ValueError(f"{name} is not JSON (RFC 8259 does not define it)")


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """§7.3.11 — duplicate object keys are REFUSED, at every level.

    `json.loads` keeps the LAST duplicate, which is a silent choice about which
    trust root the deployment holds. This hook sees every pair, so it can refuse
    instead of choosing.
    """
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _decode_public_key(value: object) -> bytes | None:
    """§7.3.11 — 64 lowercase hex characters decoding to 32 bytes, or nothing.

    Uppercase is REFUSED, never normalized: a value AI-05 accepts is a value
    AI-05 must not rewrite (§14.5.1's case policy, applied here for the same
    reason).
    """
    if not isinstance(value, str) or len(value) != 64:
        return None
    for char in value:
        if char not in _HEX_LOWER:
            return None
    return bytes.fromhex(value)


def _collision_rule_holds(
    keys: Mapping[str, bytes], recognized: frozenset[str], policy: str
) -> bool:
    """§7.3.2's group rule, over the WHOLE mapping (§7.3.11).

    Grouped BY PUBLIC KEY. A group containing AT LEAST ONE recognized token
    makes the whole mapping non-compliant and fails it closed under BOTH
    policies. A group consisting ENTIRELY of unregistered tokens is the ONE case
    the two policies treat differently — tolerated under A, refused under B.
    """
    groups: dict[bytes, list[str]] = {}
    for token, key in keys.items():
        groups.setdefault(key, []).append(token)
    for members in groups.values():
        if len(members) < 2:
            continue
        if any(token in recognized for token in members):
            return False
        if policy == "B":
            return False
    return True


def _build_state(supplied: object) -> _Designated | _Invalid:
    """Validate the whole configuration, or return `_INVALID`.

    §7.3.11: validation is COMPLETE and partial acceptance is forbidden. The
    reader must not authenticate against the entries it managed to parse, must
    not skip a malformed entry and continue, and must not recover silently.
    Every refusal path here returns the same `_INVALID` state, so a deployment
    misconfiguration and an absent variable are indistinguishable from outside —
    which is correct, because they have the same consequence.
    """
    if not isinstance(supplied, str) or supplied == "":
        return _INVALID
    try:
        supplied.encode("utf-8")
    except UnicodeEncodeError:
        return _INVALID
    try:
        document = json.loads(
            supplied,
            object_pairs_hook=_pairs_to_object,
            parse_constant=_reject_constant,
        )
    except (ValueError, TypeError):
        return _INVALID
    if not isinstance(document, dict) or set(document.keys()) != _MEMBERS:
        return _INVALID

    policy = document["collision_policy"]
    if not isinstance(policy, str) or policy not in _POLICIES:
        return _INVALID

    raw_keys = document["producer_keys"]
    if not isinstance(raw_keys, dict):
        return _INVALID

    keys: dict[str, bytes] = {}
    for token, value in raw_keys.items():
        decoded = _decode_public_key(value)
        if decoded is None:
            return _INVALID
        keys[token] = decoded

    # §6.5 remains the SOLE authority on whether a token is recognized; this
    # consults it and does not restate it. A `producer_keys` entry is not
    # evidence of recognition.
    recognized = frozenset(row.producer for row in ADMITTED_EVENTS)
    if not _collision_rule_holds(keys, recognized, policy):
        return _INVALID

    return _Designated(
        policy=policy,
        keys=MappingProxyType(dict(keys)),
        recognized=recognized,
    )


# --------------------------------------------------------------------------
# INITIALIZATION — §7.3.11's one read.
#
# This is a module-level READ and not a call. There is deliberately no function
# that reads the variable, because a function-shaped read is one that can run
# twice. `os.environ.get` READS the running process's environment; §31.3's
# NO MUTATION rule forbids WRITING it, and this module contains no write.
# --------------------------------------------------------------------------

_SUPPLIED_VALUE = os.environ.get(_ENV_NAME)

_STATE: _Designated | _Invalid = _build_state(_SUPPLIED_VALUE)


# --------------------------------------------------------------------------
# §7.3.5 V1-V5
# --------------------------------------------------------------------------


def _envelope(proof: object) -> tuple[str, str]:
    """V1 — the proof envelope is validated (§7.3.3, §7.3.5).

    An omitted or `None` proof is AUTHENTICATION_PROOF_MISSING rather than a
    `TypeError`: §7.3.3 makes that a REJECTED RESULT, because a required
    positional parameter would raise before admission could return anything and
    §22.1 defines three outcomes of which an exception is not one.
    """
    if proof is None:
        raise AuthenticationProofMissing(
            "no producer proof was supplied; §7.3.3 makes the proof a required "
            "argument of both entry points, and omitting it or passing None is "
            "REJECTED with AUTHENTICATION_PROOF_MISSING rather than a TypeError"
        )
    if not isinstance(proof, Mapping):
        raise AuthenticationProofMalformed(
            f"the producer proof is {type(proof).__name__}, not an object "
            "carrying message_b64u and signature (§7.3.3)"
        )
    if set(proof.keys()) != {"message_b64u", "signature"}:
        raise AuthenticationProofMalformed(
            "the producer proof must carry exactly message_b64u and signature, "
            "and nothing else (§7.3.3)"
        )
    message = proof["message_b64u"]
    signature = proof["signature"]
    if not isinstance(message, str) or message == "":
        raise AuthenticationProofMalformed(
            "message_b64u must be a non-empty string in the unpadded Base64url "
            "alphabet (§7.3.3)"
        )
    for char in message:
        if char not in _B64U:
            raise AuthenticationProofMalformed(
                "message_b64u carries a character outside the Base64url alphabet, "
                "or '=' padding; both are refused rather than skipped (§7.3.3)"
            )
    if not isinstance(signature, str) or len(signature) != _SIGNATURE_CHARS:
        raise AuthenticationProofMalformed(
            "signature must be exactly 128 lowercase hexadecimal characters, a "
            "64-byte Ed25519 signature (§7.3.3)"
        )
    for char in signature:
        if char not in _HEX_LOWER:
            raise AuthenticationProofMalformed(
                "signature must be LOWERCASE hexadecimal; uppercase is refused "
                "rather than normalized (§7.3.3)"
            )
    return message, signature


def _claimed_producer(raw: object) -> str:
    """V2 — the claimed producer is read, FOR KEY SELECTION (§7.3.5).

    This is a PRECONDITION READ and not a second shape rule. Step 7b runs before
    typed construction, so it cannot rely on construction's checks having run:
    it reads exactly two things — that `provenance` is an object and that
    `provenance.producer` is the bounded text §7 requires — and reports failure
    with the SAME reason codes construction would report for the same defect.
    The full shape, required-field, vocabulary and class checks remain
    construction's (§30 steps 1-4, 4b, 6).

    NO KEY LOOKUP AND NO CRYPTOGRAPHY PROCEED WITHOUT A READABLE PRODUCER TOKEN
    (§7.3.5 V2, §7.3.8).
    """
    if not isinstance(raw, Mapping):
        raise RecordMalformed(
            "a producer claim cannot be read from a value that is not an object; "
            "§7.3.5 V2 reports the same reason construction would (§7.3.8)"
        )
    if "provenance" not in raw or raw["provenance"] is None:
        raise MissingRequiredField(
            "provenance is absent or null, so the claimed producer token cannot "
            "be read (§7.3.5 V2)"
        )
    provenance = raw["provenance"]
    if not isinstance(provenance, Mapping):
        raise RecordMalformed(
            "provenance is not an object, so the claimed producer token cannot be "
            "read (§7.3.5 V2)"
        )
    if "producer" not in provenance or provenance["producer"] is None:
        raise MissingRequiredField(
            "provenance.producer is absent or null, so the claimed producer token "
            "cannot be read (§7.3.5 V2)"
        )
    # `g_text` is the SAME grammar construction applies, so the reason code a
    # failure carries here is the one construction would have carried.
    return g_text(provenance["producer"], "provenance.producer")


def _decode_message(value: str) -> bytes:
    """V4's first half — `message_b64u` is decoded STRICTLY (§7.3.3).

    Decoding refuses a character outside the alphabet rather than skipping it,
    refuses '=' padding, and is CANONICAL: re-encoding the decoded bytes must
    reproduce the submitted string exactly, so a value whose final quantum
    carries non-zero unused bits is REFUSED as malformed rather than accepted as
    an alias of a valid one.
    """
    padded = value + "=" * (-len(value) % 4)
    try:
        raw = base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AuthenticationProofMalformed(
            "message_b64u is not decodable as unpadded Base64url (§7.3.3)"
        ) from exc
    if base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != value:
        raise AuthenticationProofMalformed(
            "message_b64u is NON-CANONICAL: re-encoding the decoded bytes does "
            "not reproduce the submitted string, so it is refused as malformed "
            "rather than accepted as an alias of a valid one (§7.3.3)"
        )
    return raw


def _verify(key: bytes, signature: str, message: bytes) -> None:
    """V4's second half — the signature is checked over the DECODED bytes.

    Not over the encoded string, and not over a re-encoding of it (§7.3.3). V4
    proves a signature by a key holder; V5 proves the signed bytes are THIS
    submission. Neither implies the other (§7.3.5).
    """
    public_key = Ed25519PublicKey.from_public_bytes(key)
    try:
        public_key.verify(bytes.fromhex(signature), message)
    except InvalidSignature as exc:
        raise AuthenticationSignatureInvalid(
            "the signature does not verify, under the designated key for the "
            "claimed token, over the decoded carried message (§7.3.5 V4)"
        ) from exc


def authenticate(raw: object, proof: object) -> None:
    """Run V1-V5, or raise the one reason code that applies (§7.3.5, §7.3.8).

    Returns `None` on success. Every failure is one of SIX codes and no
    seventh; an unreadable producer token carries an EXISTING shape reason
    instead, because V2 runs before V3 and performs no key lookup.

    Raises only `EvidenceError` subclasses, so `admission.admit`'s single
    handler turns each of them into a REJECTED RESULT. An authentication failure
    is not a Guard DENY, is never recorded as one, and never becomes one
    (§7.3.8).
    """
    message_b64u, signature = _envelope(proof)  # V1
    token = _claimed_producer(raw)  # V2

    state = _STATE
    if isinstance(state, _Invalid) or token not in state.keys:  # V3
        raise AuthenticationKeyUnavailable(
            "this deployment has no usable designated producer trust mapping, or "
            "holds no key for the claimed token (§7.3.2, §7.3.5 V3). A missing, "
            "malformed, incomplete or invalid configuration is the same state: "
            "the deployment authenticates nothing"
        )
    key = state.keys[token]

    carried = _decode_message(message_b64u)  # V4
    _verify(key, signature, carried)  # V4

    # V5 — the verifier reconstructs signed_input FROM THE SUBMITTED MAPPING and
    # requires exact byte equality. A mapping with no canonical serialization
    # raises AUTHENTICATION_INPUT_UNSERIALIZABLE from inside `signed_input`,
    # which is a DIFFERENT failure from "the bytes differ": there no bytes exist
    # at all (§7.3.5 V5).
    expected = signed_input(raw)
    if carried != expected:
        raise AuthenticationInputMismatch(
            "the decoded carried message is not the signed input reconstructed "
            "from the submitted mapping (§7.3.5 V5). The block, not the "
            "signature, means the record was not the one that was signed"
        )


def designated_key_for(token: object) -> bytes | None:
    """§7.3.2 — which key applies to THIS claimed token, or `None`.

    A PER-TOKEN answer. §31.3's IMMUTABLE STATE rule forbids exposing the
    mapping, the policy table or the parsed document, and this function exposes
    none of them; §31.3's NO CALLER-SELECTED TRUST ROOT rule is about what may
    be passed IN, and a producer token is not a trust root.
    """
    state = _STATE
    if isinstance(state, _Invalid) or not isinstance(token, str):
        return None
    return state.keys.get(token)
