"""The §15.8 signing boundary — the mint side, as a dormant capability.

**AI-06 declares an interface and consumes an implementation.** The signing
capability is INJECTED BY THE DEPLOYMENT and is NOT BUILT here: this module
generates no key, reads none from a file, a variable or a configuration
member, and ships none. The private key is never in this repository
(§15.8:1121-1133). What this module owns is the CONTRACT-ENFORCING GATE that
decides WHAT may be signed (the Step 1 design's ROLE 2): the injected signer
is trusted-by-injection and dumb; this helper is untrusted-by-default and
refuses more than it signs.

```text
DORMANT CAPABILITY. Nothing in this repository calls producer_proof_for.
The §7.3.13 approved call-site set stays EMPTY; no production caller of
admit() or admit_to_store() exists; composition/ imports nothing from here
and never holds a signer. Wiring a call site is the joint change's act, not
this module's. Until then this is §17.2c-class preparation: the boundary
exists and is tested; nothing is activated.
```

The checks, and the order they run in, follow §15.8's own rule — CHECK, THEN
SIGN (:1191-1195): every check precedes the call to `signer.sign`, and a
refusal produces NO proof at all (no placeholder, no empty proof, no proof
by anything else — :1134-1139). The order AMONG the checks is this module's
choice, recorded here: no frozen clause orders them (AI-05 §7.3.7 leaves
in-stage ordering to the implementation), and the order below puts the
cheapest, most structural refusals first.

READING (recorded for the AI-06 owner, alongside the Step 1 design's
readings): §15.8:1186-1189 — "it is given them by the party that owns them,
and it refuses when a value it was given disagrees with what that party's
own source says" — is implemented here as GIVEN-VALUE CONSISTENCY. The
helper owns neither the actor declaration nor the workspace single source;
it is handed the owning phase's declared actor and the single source's
workspace id, and it refuses when the submitted mapping disagrees with
either. It does not re-derive the workspace id from the workspace root and
does not consult the actor's declaration source itself.

The bytes signed are AI-05 §7.3.4's signed input for the SUBMITTED MAPPING —
AI-05's serializer (`plugins/evidence/signed_input.py`), imported, never
restated (§15.8:1229-1232). This module adds no serializer, no intermediate
envelope format and no second canonical form. The proof envelope it returns
is exactly §7.3.3's two members, `message_b64u` and `signature`, and nothing
else.
"""

from __future__ import annotations

import base64
from typing import Any, Mapping, Protocol, Sequence

from plugins.evidence.models import (
    ActorType,
    EvidenceKind,
    ObservationFamily,
    ProducerType,
    admitted_events_for,
)
from plugins.evidence.signed_input import signed_input
from plugins.security_tools.errors import (
    SignerSignatureMalformed,
    SignerTokenMismatch,
    SignerUnavailable,
    SigningActorMismatch,
    SigningFieldUnmapped,
    SigningPayloadMismatch,
    SigningRegistryMismatch,
    SigningWorkspaceMismatch,
)
from plugins.security_tools.evidence import execution_payload_for
from plugins.security_tools.result import ToolResult

__all__ = ["ProducerSigner", "producer_proof_for"]


class ProducerSigner(Protocol):
    """The deployment's signing capability (§15.8:1125-1128) — two things, nothing else.

    ```text
    producer_token  the token this signer speaks for
    sign(message)   the signature over EXACTLY those bytes, 64 raw bytes
    ```

    Not key lookup (the signer IS bound to one key at injection; selection
    by token happens independently on the verify side, §7.3.5 V3). Not
    identity binding (the signer authenticates nothing; it is the thing
    authentication is ABOUT, §7.3.1). Not proof construction (the envelope is
    the HELPER's job; the signer knows no domain tags, versions or
    encodings). The return encoding IS a design choice, not a contract one:
    this module VALIDATES what `sign` returns before using it and owns the
    conversion to §7.3.3's 128 lowercase hexadecimal characters.
    """

    producer_token: str

    def sign(self, message: bytes) -> bytes: ...


# --------------------------------------------------------------------------
# The closed field-source map (§15.8:1169-1189)
#
# Every key the signature can cover sits in exactly one of the three source
# classes, and a key that appears nowhere below is REFUSED BEFORE SIGNING.
# This is also where the fields AI-05 itself generates are refused on the
# mint side: `evidence_id`, `record_digest`, `content_digest`, the
# `integrity` and `identity` blocks and `provenance.recorded_at` are NOT in
# the map, so a submitted mapping carrying one is refused here — which
# matters because construction does not refuse an `integrity` or `identity`
# block (it rebuilds both, models.py:1577-1585) and the signature would
# otherwise cover a block with no defined source.
# --------------------------------------------------------------------------

#: The supplied form's top level: everything `from_mapping` reads, nothing
#: it generates. `references` and `artifacts` are optional and may be absent.
_SUPPLIED_TOP_KEYS = frozenset(
    {"schema_version", "kind", "payload", "provenance", "references", "artifacts"}
)

_PROVENANCE_KEYS = frozenset(
    {
        "producer",
        "producer_version",
        "producer_type",
        "actor",
        "workspace_id",
        "experiment_id",
        "observed_at",
    }
)

_ACTOR_KEYS = frozenset({"id", "type"})

#: The EXECUTION payload's one key, spelled as AI-05's parser reads it.
_PAYLOAD_KEYS = frozenset({"tool_calls[]"})

_TOOL_CALL_KEYS = frozenset({"ordinal", "what_ran", "status"})

_REFERENCES_KEYS = frozenset({"context", "decisions", "supersedes"})

_CONTEXT_REF_KEYS = frozenset(
    {
        "workspace_id",
        "source_kind",
        "source_identity",
        "source_revision",
        "subject",
        "value",
        "item_kind",
        "truth_state",
        "freshness",
    }
)

_RECORD_REF_KEYS = frozenset({"record_ref"})

_SUPERSEDE_REF_KEYS = frozenset({"record_ref", "correction_reason"})

_ARTIFACTS_KEYS = frozenset({"items"})

_ARTIFACT_KEYS = frozenset(
    {"artifact_digest", "external", "owner_workspace_id", "artifact_ref"}
)


def _unmapped(where: str) -> SigningFieldUnmapped:
    return SigningFieldUnmapped(
        f"{where}: this key, or the container it sits in, is outside the closed "
        "field-source map (§15.8:1169-1189). The sources are exactly three — "
        "derived from the ToolResults, caller-assigned where a contract names "
        "the caller (ordinal, and only ordinal), and supplied by the deployment "
        "or the owning phase's declaration — and a field with no defined source "
        "is refused BEFORE the signature is made"
    )


def _require_mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _unmapped(f"{where} (not an object)")
    return value


def _require_sequence(value: object, where: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _unmapped(f"{where} (not an array)")
    return value


def _check_keys(data: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    for key in data:
        if key not in allowed:
            raise _unmapped(f"{where}.{key}")


def _check_closed_map(mapping: Mapping[str, Any]) -> None:
    """Refuse any key — or container shape — the closed map does not carry.

    Requiredness, grammars and vocabularies remain construction's (§30 steps
    1-4, 4b, 6); this walk enumerates KEYS and SHAPES only, because those are
    what the signature's field-source rule is about.
    """
    _check_keys(mapping, _SUPPLIED_TOP_KEYS, "record")

    provenance = _require_mapping(mapping.get("provenance"), "record.provenance")
    _check_keys(provenance, _PROVENANCE_KEYS, "record.provenance")
    actor = _require_mapping(provenance.get("actor"), "record.provenance.actor")
    _check_keys(actor, _ACTOR_KEYS, "record.provenance.actor")

    payload = _require_mapping(mapping.get("payload"), "record.payload")
    _check_keys(payload, _PAYLOAD_KEYS, "record.payload")
    for index, entry in enumerate(
        _require_sequence(payload.get("tool_calls[]", []), "record.payload.tool_calls[]")
    ):
        where = f"record.payload.tool_calls[{index}]"
        _check_keys(_require_mapping(entry, where), _TOOL_CALL_KEYS, where)

    references = mapping.get("references")
    if references is not None:
        refs = _require_mapping(references, "record.references")
        _check_keys(refs, _REFERENCES_KEYS, "record.references")
        for index, entry in enumerate(
            _require_sequence(refs.get("context", []), "record.references.context")
        ):
            where = f"record.references.context[{index}]"
            _check_keys(_require_mapping(entry, where), _CONTEXT_REF_KEYS, where)
        for index, entry in enumerate(
            _require_sequence(refs.get("decisions", []), "record.references.decisions")
        ):
            where = f"record.references.decisions[{index}]"
            if isinstance(entry, Mapping):
                _check_keys(entry, _RECORD_REF_KEYS, where)
            elif not isinstance(entry, str):
                raise _unmapped(f"{where} (neither a record_ref object nor an id)")
        for index, entry in enumerate(
            _require_sequence(
                refs.get("supersedes", []), "record.references.supersedes"
            )
        ):
            where = f"record.references.supersedes[{index}]"
            _check_keys(_require_mapping(entry, where), _SUPERSEDE_REF_KEYS, where)

    artifacts = mapping.get("artifacts")
    if artifacts is not None:
        arts = _require_mapping(artifacts, "record.artifacts")
        _check_keys(arts, _ARTIFACTS_KEYS, "record.artifacts")
        for index, entry in enumerate(
            _require_sequence(arts.get("items", []), "record.artifacts.items")
        ):
            where = f"record.artifacts.items[{index}]"
            _check_keys(_require_mapping(entry, where), _ARTIFACT_KEYS, where)


# --------------------------------------------------------------------------
# The helper
# --------------------------------------------------------------------------


def producer_proof_for(
    mapping: Mapping[str, Any],
    results: Sequence[ToolResult],
    *,
    signer: ProducerSigner | None,
    actor: Mapping[str, str],
    workspace_id: str,
) -> dict[str, str]:
    """Check the submitted mapping against its sources, then sign it (§15.8).

    Composes, in order — CHECK, THEN SIGN, and a refusal at any step produces
    no proof at all:

    ```text
    1  the signer is present and usable          §15.8:1134-1139
    2  every key is in the closed field-source   §15.8:1169-1189
       map, and every container is the shape
       the map says it is
    3  the signer speaks for the claimed         §15.8:1134-1139
       producer token
    4  the payload IS execution_payload_for      §15.8:1143-1151
       (results) — the one projection path
    5  the actor is the owning phase's declared  §15.8:1151-1157,
       actor, given as a parameter                  the given-value reading
    6  every workspace field is the single       AI-15 §12.2, mirrored
       source's value, given as a parameter        on §18.1's exemptions
    7  kind, family, actor type and producer     §6.5, via the same
       type are consistent with a registry row     rows construction uses
       for this token
    8  SIGN: AI-05 §7.3.4's signed input over    §15.8:1229-1232
       the COMPLETE submitted mapping, through
       AI-05's serializer; the signature is
       validated as exactly 64 bytes before use
    9  the envelope: message_b64u (unpadded       §7.3.3, closed-keyed
       canonical base64url of the signed input)
       and signature (128 lowercase hex) —
       nothing else
    ```

    `actor` and `workspace_id` are the OWNING PHASE's values — the helper is
    given them by the party that owns them and refuses when the mapping
    disagrees; it does not derive either itself. `results` are the
    ToolResults the mapping claims to describe. `signer` is the
    deployment-injected capability; `None` is the ABSENT capability and is
    refused, never faked.

    Returns §7.3.3's envelope for `admit(raw, producer_proof=...)`. The
    mapping is never modified.
    """
    # 1 — the capability itself.
    if signer is None:
        raise SignerUnavailable(
            "no signing capability was injected; §15.8:1134-1139 refuses the "
            "absent capability rather than faking it — no placeholder proof, no "
            "empty proof, no proof signed by anything else, and no submission "
            "asserted to be ready"
        )
    token = getattr(signer, "producer_token", None)
    sign = getattr(signer, "sign", None)
    if not isinstance(token, str) or token == "" or not callable(sign):
        raise SignerUnavailable(
            "the injected signing capability is not usable: it must carry a "
            "non-empty producer_token and a callable sign(message) (§15.8:1125-1128) "
            "— and nothing else is this helper's to assume"
        )

    # 2 — the closed field-source map.
    _check_closed_map(mapping)
    provenance = mapping["provenance"]
    payload = mapping["payload"]

    # 3 — the mint-side token binding.
    claimed = provenance.get("producer")
    if not isinstance(claimed, str) or claimed != token:
        raise SignerTokenMismatch(
            "the injected signer and the mapping's claimed producer do not "
            "agree, or no claim can be read; a signer speaking for another "
            "token cannot produce a proof for this one, so the operation fails "
            "BEFORE the signer is asked to sign (§15.8:1134-1139)"
        )

    # 4 — the one projection path.
    expected_payload = execution_payload_for(tuple(results)).to_mapping()
    if payload != expected_payload:
        raise SigningPayloadMismatch(
            "the mapping's execution payload is not execution_payload_for"
            "(results); §15.2's projection is the ONLY way a ToolResult becomes "
            "record content, and a proof over anything else would authenticate "
            "a claim about facts that were never projected (§15.8:1143-1151)"
        )

    # 5 — the declared actor.
    if not isinstance(actor, Mapping) or provenance.get("actor") != dict(actor):
        raise SigningActorMismatch(
            "the mapping's actor is not the owning phase's declared actor; the "
            "actor is a runtime fact of the execution, and a caller choosing a "
            "different one would be signing a claim about an act somebody else "
            "performed (§15.8:1151-1157)"
        )

    # 6 — the single-source workspace identity, on §18.1's own exemptions.
    if not isinstance(workspace_id, str) or provenance.get("workspace_id") != workspace_id:
        raise SigningWorkspaceMismatch(
            "the mapping's workspace_id is not the single source's value; the "
            "workspace identity has one source (AI-15 §12.2), the helper was "
            "given that source's value, and a mapping naming another workspace "
            "is refused at the source"
        )
    references = mapping.get("references")
    if references is not None:
        for index, entry in enumerate(references.get("context", [])):
            if entry.get("workspace_id") != workspace_id:
                raise SigningWorkspaceMismatch(
                    f"references.context[{index}].workspace_id does not agree "
                    "with the single source's workspace identity; a record is "
                    "scoped to exactly one workspace (§18.1)"
                )
    artifacts = mapping.get("artifacts")
    if artifacts is not None:
        for index, item in enumerate(artifacts.get("items", [])):
            if item.get("external") is True:
                # §18.1's exemption: a declared external dependency carrying
                # its owner. §13.6 has already required that owner present.
                continue
            owner = item.get("owner_workspace_id")
            if owner is not None and owner != workspace_id:
                raise SigningWorkspaceMismatch(
                    f"artifacts.items[{index}].owner_workspace_id does not "
                    "agree with the single source's workspace identity; the "
                    "exemption covers only an artifact explicitly marked "
                    "external with an owner (§18.1)"
                )

    # 7 — the §6.5 registry row, over the same rows construction consults.
    try:
        kind = EvidenceKind(mapping.get("kind"))
    except ValueError:
        kind = None  # refused below; vocabulary is the row's to decide
    family_value = payload.get("family")
    family: ObservationFamily | None
    try:
        family = None if family_value is None else ObservationFamily(family_value)
    except ValueError:
        family = None
    candidates = admitted_events_for(kind, family) if kind is not None else ()
    if not candidates or token not in {row.producer for row in candidates}:
        raise SigningRegistryMismatch(
            "the mapping's event is not consistent with any §6.5 registry row "
            "for this signer's token; kind and family are row-derived, not "
            "free declaration, and a forged event is refused before a "
            "signature exists (§15.8:1218)"
        )
    try:
        actor_type = ActorType(provenance["actor"].get("type"))
        producer_type = ProducerType(provenance.get("producer_type"))
    except ValueError:
        raise SigningRegistryMismatch(
            "the mapping's actor type or producer type is not a vocabulary "
            "member any §6.5 row admits; both are row-derived and are refused "
            "before a signature exists (§15.7)"
        ) from None
    if actor_type not in {row.actor_type for row in candidates}:
        raise SigningRegistryMismatch(
            "the mapping's actor type is not admitted for this event; the §6.5 "
            "row fixes actor.type and it is not free declaration (§15.7)"
        )
    if producer_type not in {row.producer_type for row in candidates}:
        raise SigningRegistryMismatch(
            "the mapping's producer type is not admitted for this event; every "
            "v1 admitted event registers a service producer (§6.6)"
        )

    # 8 — SIGN, over AI-05's serializer and nothing else.
    message = signed_input(mapping)
    raw = sign(message)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != 64:
        raise SignerSignatureMalformed(
            "the signer returned something that is not 64 raw bytes; the "
            "interface returns the signature over EXACTLY those bytes "
            "(§15.8:1125-1128), and a signer returning an encoding of them is "
            "unusable — the failure is made here rather than discovered by the "
            "verifier"
        )
    signature = bytes(raw)

    # 9 — §7.3.3's envelope: exactly two members, and nothing else.
    return {
        "message_b64u": base64.urlsafe_b64encode(message)
        .rstrip(b"=")
        .decode("ascii"),
        "signature": signature.hex(),
    }
