"""Canonicalization and semantic digests.

Implements AI-04 contract §20.

Three digests, three different jobs:

    policy_digest       over the canonical *representation* of a policy
    request_digest      over the semantic request projection (§20.5)
    evaluation_digest   over the decision and its trace (§20.6)

**Runtime-only fields never enter any of them** (§20.4): `decision_id`,
`evaluated_at`, `retrieved_at`, `cache_hit`, and any generated identifier or
timestamp. They record *when* and *how* a read happened, not *what it said*.
Two evaluations over the same context read at different times have identical
semantic inputs and must produce identical digests; including a timestamp would
make §20 unsatisfiable rather than merely inconvenient.

**Two orders, deliberately different** (§20.3, D-18). `policy.rules[]` is sorted
by `rule_id` for the digest — an arbitrary but stable choice, because a digest
must not depend on how a file was written. The *evaluation trace* records the
semantic order §12.2.2 produces, which is not that sequence. Conflating them
would either make the digest file-order-dependent or misreport the order rules
were actually evaluated in.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence

from plugins.context.context import ContextItem, ContextResponse
from plugins.guard.models import CheckRecord, GuardRequest
from plugins.guard.policy import Policy, Rule

#: Fields excluded from every digest (§20.4). Named here so the exclusion is
#: auditable in one place rather than implied by what each projection happens
#: to leave out.
RUNTIME_ONLY_FIELDS: frozenset[str] = frozenset(
    {
        "decision_id",
        "evaluated_at",
        "retrieved_at",
        "cache_hit",
    }
)


def canonical_json(value: Any) -> str:
    """The canonical serialization of §20.2.

    UTF-8-safe, object keys sorted by Unicode code point, no insignificant
    whitespace, enums rendered as their canonical string.

    `null` and absent are different and are not conflated: a field **in** a
    projection whose value is not established is serialized as `null`; a field
    **outside** a projection is not serialized at all. The projections in
    `request_projection` and `evaluation_projection` fix which is which.
    """
    return json.dumps(
        _normalise(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _normalise(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if isinstance(value, (set, frozenset)):
        # A bare set has no canonical order, so serialising one would be an
        # order-dependent digest. Every set-semantic collection in this package
        # is sorted before it reaches here; a set arriving unsorted is a bug,
        # and refusing beats guessing.
        raise TypeError(
            "a set has no canonical order; sort it into a list before digesting "
            "(§20.3 fixes the order per collection)"
        )
    return value


def sha256_hex(payload: str) -> str:
    """SHA-256 over UTF-8 bytes, lowercase hexadecimal (§20.2)."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def digest_of(value: Any) -> str:
    return sha256_hex(canonical_json(value))


def policy_digest(policy: Policy) -> str:
    """The digest of a policy's canonical form (§9, §20.2).

    Computed, never trusted: §9.2 makes a mismatch between a declared `digest`
    and this value an invalid policy.
    """
    return digest_of(policy.to_semantic_dict())


# --------------------------------------------------------------------------
# Projections (§20.5)
# --------------------------------------------------------------------------


def _item_projection(item: ContextItem) -> dict[str, Any]:
    """One context item's semantic projection.

    `retrieved_at` and `cache_hit` are excluded per §20.4 — they say when and
    how the read happened, not what it said.
    """
    return {
        "subject": item.subject,
        "item_kind": str(item.item_kind),
        "value": item.value,
        "truth_state": str(item.truth_state),
        "freshness": str(item.freshness),
        "source_kind": str(item.source_kind),
        "source_identity": item.source_identity,
        "source_revision": item.source_revision,
        "superseded_by": (
            item.superseded_by.render() if item.superseded_by is not None else None
        ),
    }


def context_projection(response: ContextResponse | None) -> dict[str, Any] | None:
    """The semantic context projection (§20.5).

    Items are **set-semantic**: sorted by `(subject, source_kind,
    source_identity, source_revision, value)`, which is total because a subject
    plus a source read plus a value identifies an item. Sorting makes the digest
    independent of the order AI-03 happened to assemble the lists in.
    """
    if response is None:
        return None

    items = [
        _item_projection(item)
        for item in (*response.facts, *response.history, *response.plans)
    ]
    items.sort(
        key=lambda entry: (
            entry["subject"],
            entry["source_kind"],
            entry["source_identity"],
            entry["source_revision"] or "",
            entry["value"],
        )
    )
    return {
        "workspace_id": response.workspace.workspace_id,
        "items": items,
    }


def request_projection(request: GuardRequest) -> dict[str, Any]:
    """The semantic request projection (§20.5).

    Every field listed by the contract is present, with `null` where a value was
    not supplied — the projection is what makes "not established" and "absent"
    distinguishable in the canonical form.
    """
    return {
        "schema_version": request.schema_version,
        "actor": request.actor.to_dict(),
        "workspace": request.workspace.to_dict(),
        "action": request.action.to_dict(),
        "capability": request.capability.id,
        "target": request.target.to_dict(),
        "context": context_projection(request.context),
        "capability_state": {
            "records": sorted(
                (
                    {
                        "capability_id": record.capability_id,
                        "status": str(record.status),
                    }
                    for record in request.capability_state
                ),
                key=lambda entry: (entry["capability_id"], entry["status"]),
            )
        },
        "approval": request.approval.to_dict(),
    }


def request_digest(request: GuardRequest) -> str:
    return digest_of(request_projection(request))


# --------------------------------------------------------------------------
# Evaluation digest (§20.6)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuleTraceEntry:
    """One candidate's place in the §14.1 walk.

    Order-semantic: the sequence of these is the ordered rule evaluation trace,
    and §20.6 hashes it in order. It is **not** sorted — sorting it would report
    an order the evaluator did not use.
    """

    rule_id: str
    effect: str
    match_result: str
    aggregate: str
    candidate: bool
    decided: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "effect": self.effect,
            "match_result": self.match_result,
            "aggregate": self.aggregate,
            "candidate": self.candidate,
            "decided": self.decided,
        }


def evaluation_projection(
    *,
    request_digest_value: str,
    policy: Policy,
    policy_digest_value: str,
    trace: Sequence[RuleTraceEntry],
    context_refs: Iterable[str],
    decision: str,
    reason_code: str,
    rule_id: str | None,
) -> dict[str, Any]:
    """The §20.6 projection.

    `checks` — the trace — is order-semantic and preserved. `context_refs` is
    set-semantic and sorted. Both choices come from §20.3 and are frozen.
    """
    return {
        "request_digest": request_digest_value,
        "policy": {
            "policy_id": policy.policy_id,
            "revision": policy.revision,
            "digest": policy_digest_value,
        },
        "trace": [entry.to_dict() for entry in trace],
        "context_refs": sorted(context_refs),
        "decision": decision,
        "reason_code": reason_code,
        "rule_id": rule_id,
    }


def evaluation_digest(projection: Mapping[str, Any]) -> str:
    return digest_of(projection)


def checks_projection(checks: Sequence[CheckRecord]) -> list[dict[str, Any]]:
    """The record's `checks[]`, in trace order (§20.3 order-semantic)."""
    return [check.to_dict() for check in checks]


__all__ = [
    "RUNTIME_ONLY_FIELDS",
    "RuleTraceEntry",
    "canonical_json",
    "checks_projection",
    "context_projection",
    "digest_of",
    "evaluation_digest",
    "evaluation_projection",
    "policy_digest",
    "request_digest",
    "request_projection",
    "sha256_hex",
]
