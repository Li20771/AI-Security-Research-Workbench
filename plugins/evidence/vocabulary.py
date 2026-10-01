"""The AI-05 vocabulary.

Implements the closed vocabularies the AI-05 contract **owns**, and imports the
ones it does not.

**Nothing frozen elsewhere is restated** (contract §3). `ActorType` comes from
AI-04, and `ItemKind`, `StatusValue` and `Freshness` come from AI-03. Redefining
one would mean two definitions in one repository, one place to update, and one of
them forgotten — which is exactly the defect AI-04 §28.2 names.

AI-05 **owns** two vocabularies, both added by Amendment 1:

    ProducerType       agent | service | unknown
    ObservationFamily  SOURCE_READ | PROVIDER_PROBE | CAPABILITY_OBSERVATION

It **imports** four and does not redefine them:

    ActorType      AI-04   the type of actor.type
    GuardDecision  AI-04
    ItemKind       AI-03
    StatusValue    AI-03
    Freshness      AI-03

`producer_type` is a `ProducerType`, **not** an `ActorType`. Before Amendment 1
the contract expressed the producer role as "`ActorType` minus `human`", which
left `producer = human, producer_type = human` schema-legal while the prose
forbade it. A closed three-member type admits no such state.

**Vocabulary membership and admission are two different checks.** `agent` is a
valid `ProducerType` member and is still REJECTED for every v1 admitted event,
because all six registry rows (§6.5) register `service`. `producer_type_is_permitted`
answers the vocabulary question; the registry answers the admission question.
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


class ProducerType(StrEnum):
    """The producer role vocabulary (Amendment 1, §7.1). Closed, owned by AI-05.

    **This is not `ActorType`.** Before Amendment 1 the contract described
    `producer_type` as a narrower use of AI-04's `ActorType`, which made the
    producer role a constraint on another component's type. The two are now
    distinct types and `ActorType` is not redefined.

    Membership here is necessary but not sufficient for admission: all six v1
    admitted events in the §6.5 registry require `service`, so `agent` and
    `unknown` are valid vocabulary members that no admitted v1 record may use.
    Vocabulary membership and admission are separate checks.
    """

    AGENT = "agent"
    SERVICE = "service"
    UNKNOWN = "unknown"


class ObservationFamily(StrEnum):
    """The observation family vocabulary (Amendment 1, §6.7). Closed, owned by AI-05.

    Exactly three members. `family` is REQUIRED on every OBSERVATION, selects the
    binding arm and the status field, and is never inferred from a producer name.
    A fourth member requires an amendment.
    """

    SOURCE_READ = "SOURCE_READ"
    PROVIDER_PROBE = "PROVIDER_PROBE"
    CAPABILITY_OBSERVATION = "CAPABILITY_OBSERVATION"


#: The actor vocabulary, unchanged from AI-04's `ActorType`.
PERMITTED_ACTOR_TYPES: frozenset[ActorType] = frozenset(ActorType)


def producer_type_is_permitted(value: object) -> bool:
    """Whether `value` is a member of `ProducerType` (§7.1).

    This is the VOCABULARY check only. Whether the member is admissible for a
    given event is the registry's question, not this one: `agent` is a valid
    member and is still REJECTED for every v1 admitted event, because §6.5
    registers `service` for all six.
    """
    try:
        ProducerType(value)
    except ValueError:
        return False
    return True


def actor_type_is_permitted(value: object) -> bool:
    """Whether `value` is a member of AI-04's `ActorType` (§7.1)."""
    try:
        ActorType(value)
    except ValueError:
        return False
    return True


__all__ = [
    "AI05_GENERATED_DIGEST_FIELDS",
    "CALLER_SUPPLIED_DIGEST_FIELDS",
    "PERMITTED_ACTOR_TYPES",
    "ActorType",
    "AdmissionOutcome",
    "DigestOrigin",
    "EvidenceKind",
    "FieldClass",
    "Freshness",
    "GuardDecision",
    "ItemKind",
    "ObservationFamily",
    "ProducerType",
    "StatusValue",
    "actor_type_is_permitted",
    "producer_type_is_permitted",
]
