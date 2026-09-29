"""The AI-05 vocabulary.

Implements the closed vocabularies the AI-05 contract **owns**, and imports the
ones it does not.

**Nothing frozen elsewhere is restated** (contract §3). `ActorType` comes from
AI-04, and `ItemKind`, `StatusValue` and `Freshness` come from AI-03. Redefining
one would mean two definitions in one repository, one place to update, and one of
them forgotten — which is exactly the defect AI-04 §28.2 names.

The one thing AI-05 adds on top of an imported vocabulary is a **role
constraint**, not a new enum:

    producer_type  MUST be in  { agent, service, unknown }   — NOT human
    actor.type     MUST be in  { human, agent, service, unknown }

`human` stays a member of the inherited `ActorType` because removing it would be
a redefinition of a frozen type. It is simply not reachable in the producer role:
the producer is the component that WROTE the record, and §7 states that a human
does not author an EvidenceRecord directly.

Without the constraint, `producer = human, producer_type = human` would be
schema-legal while contradicting §7 — a state the schema accepts and the prose
forbids. T4b asserts the rejection and T4c is its positive control.
"""

from __future__ import annotations

from enum import StrEnum

# --------------------------------------------------------------------------
# Frozen elsewhere — imported, never redefined
# --------------------------------------------------------------------------

from plugins.context.vocabulary import (  # noqa: F401  (re-exported)
    Freshness,
    ItemKind,
    StatusValue,
)
from plugins.guard.vocabulary import (  # noqa: F401  (re-exported)
    ActorType,
    GuardDecision,
)


class EvidenceKind(StrEnum):
    """The three evidence kinds (contract §6). Exactly three. FROZEN.

    A fourth kind is a contract amendment, not a configuration change.

    `kind` describes **the act the record is about** — not how the Workbench
    happened to observe it (§6.1). So a recorded human approval is a `DECISION`
    whose `actor.type` is `human`, because the act being described is the
    human's decision.
    """

    OBSERVATION = "OBSERVATION"
    DECISION = "DECISION"
    EXECUTION = "EXECUTION"


class AdmissionOutcome(StrEnum):
    """The three admission outcomes (contract §22.1). Exactly three. FROZEN.

    Deliberately **no third `BLOCKED`**. AI-04 §18.2 introduced `CheckResult`
    specifically to avoid a second `BLOCKED`, and AI-04 §3 records that one word
    in two vocabularies is a defect AI-03 already paid for with
    `ContextStatus.COMPLETE`.

        ACCEPTED     the record was admitted
        REJECTED     a contract or content violation; NOTHING was stored
        UNAVAILABLE  a persistence or dependency failure; NOTHING was stored
    """

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"


class FieldClass(StrEnum):
    """The declared field classes (contract §14.2). FROZEN.

    There is **no free-text class**. That absence is the enforceable half of the
    secret boundary: a caller holding an arbitrary string has no field to put it
    in.

    `BOUNDED_SOURCE` is the class whose rule set is the subject of C-1, the
    deferred contract gap. B1 does not implement that rule set; it validates the
    structural classes only.
    """

    STRUCTURAL = "structural"
    VOCABULARY = "vocabulary"
    IDENTIFIER = "identifier"
    BOUNDED_SOURCE = "bounded_source"


class DigestOrigin(StrEnum):
    """Who is permitted to produce a digest value (contract §14.6.1). FROZEN.

    Digest-shaped is not the same as trustworthy. Three fields are AI-05's to
    compute and a caller may not supply them (R1); one is the producer's,
    because the bytes are outside AI-05's boundary.
    """

    AI05_GENERATED = "ai05_generated"
    CALLER_SUPPLIED = "caller_supplied"


#: Fields whose value AI-05 computes and a caller MUST NOT supply (§14.6.1, R1).
AI05_GENERATED_DIGEST_FIELDS: frozenset[str] = frozenset(
    {"content_digest", "record_digest", "value_digest"}
)

#: The one digest field a caller supplies, because the producer holds the bytes
#: and AI-05 never reads them (§13.4, §13.5).
CALLER_SUPPLIED_DIGEST_FIELDS: frozenset[str] = frozenset({"artifact_digest"})


#: The producer role constraint (§7.1). Narrower than the inherited vocabulary.
PERMITTED_PRODUCER_TYPES: frozenset[ActorType] = frozenset(
    {ActorType.AGENT, ActorType.SERVICE, ActorType.UNKNOWN}
)

#: The actor vocabulary, unchanged from AI-04's `ActorType`.
PERMITTED_ACTOR_TYPES: frozenset[ActorType] = frozenset(ActorType)


def producer_type_is_permitted(value: object) -> bool:
    """Whether `value` is a valid **producer** type (§7.1).

    Membership in the inherited vocabulary is necessary but not sufficient:
    `human` is a member and is rejected here.
    """
    try:
        return ActorType(value) in PERMITTED_PRODUCER_TYPES
    except ValueError:
        return False


def actor_type_is_permitted(value: object) -> bool:
    """Whether `value` is a valid **actor** type (§7.1)."""
    try:
        ActorType(value)
    except ValueError:
        return False
    return True


__all__ = [
    "AI05_GENERATED_DIGEST_FIELDS",
    "CALLER_SUPPLIED_DIGEST_FIELDS",
    "PERMITTED_ACTOR_TYPES",
    "PERMITTED_PRODUCER_TYPES",
    "ActorType",
    "AdmissionOutcome",
    "DigestOrigin",
    "EvidenceKind",
    "FieldClass",
    "Freshness",
    "GuardDecision",
    "ItemKind",
    "StatusValue",
    "actor_type_is_permitted",
    "producer_type_is_permitted",
]
