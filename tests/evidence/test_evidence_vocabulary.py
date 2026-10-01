"""AI-05 vocabulary, the two AI-05-owned closed sets, and the role constraint.

Covers T4, T4b and T4c, and the Amendment 1 additions `ProducerType` and
`ObservationFamily`.

Three layers are asserted separately, because they answer different questions and
conflating them is how a vocabulary member gets mistaken for an admitted value:

    vocabulary membership   is the value a member of the closed set?
    admission               is that member admissible for THIS event?
    cross-field             does the whole record agree with the registry?

`agent` is a valid `ProducerType` member and is still REJECTED for every v1
admitted event, because all six registry rows register `service`.
"""

from __future__ import annotations

import pytest

from plugins.evidence import errors as ev_errors
from plugins.evidence.vocabulary import (
    PERMITTED_ACTOR_TYPES,
    ActorType,
    AdmissionOutcome,
    EvidenceKind,
    FieldClass,
    ObservationFamily,
    ProducerType,
    actor_type_is_permitted,
    producer_type_is_permitted,
)
from plugins.guard.vocabulary import ActorType as GuardActorType

pytestmark = pytest.mark.layer1


class TestFrozenElsewhereIsImportedNotRestated:
    def test_actor_type_is_ai_04_s_own_object(self):
        """§3: frozen types are imported, never redefined."""
        assert ActorType is GuardActorType

    def test_the_inherited_vocabulary_is_unchanged(self):
        """AI-05 adds no member, removes none, renames none."""
        assert {m.value for m in ActorType} == {
            "human",
            "agent",
            "service",
            "unknown",
        }

    def test_producer_type_is_not_actor_type(self):
        """Amendment 1 §7.1: `producer_type` does not use `ActorType`.

        If AI-05 had expressed the producer role as "ActorType minus human", the
        two types would be one type, and `human` would have to be removed from a
        frozen vocabulary to say so.
        """
        assert ProducerType is not ActorType
        assert not issubclass(ProducerType, ActorType)
        assert not issubclass(ActorType, ProducerType)


class TestT4ClosedVocabulary:
    """T4 — an unlisted value is rejected, never treated as ordinary."""

    def test_evidence_kind_has_exactly_three_members(self):
        assert [k.value for k in EvidenceKind] == [
            "OBSERVATION",
            "DECISION",
            "EXECUTION",
        ]

    def test_admission_outcome_has_exactly_three_members(self):
        assert [o.value for o in AdmissionOutcome] == [
            "ACCEPTED",
            "REJECTED",
            "UNAVAILABLE",
        ]

    def test_there_is_no_free_text_field_class(self):
        """§14.2 — Class 5 does not exist. The absence is the boundary."""
        assert "free_text" not in {c.value for c in FieldClass}

    def test_an_unlisted_kind_is_rejected(self, record_factory):
        from plugins.evidence import EvidenceRecord

        with pytest.raises(ev_errors.UnsupportedVocabulary):
            EvidenceRecord.from_mapping(
                record_factory(kind="SPECULATION"), clock=lambda: "t"
            )


class TestProducerType:
    """Amendment 1 §7.1 — the AI-05-owned producer vocabulary."""

    def test_the_vocabulary_has_exactly_three_members(self):
        assert [m.value for m in ProducerType] == ["agent", "service", "unknown"]

    def test_human_is_not_a_producer_type_member(self):
        """The role constraint, expressed as a vocabulary fact.

        `human` is an `ActorType` member and is not a `ProducerType` member, so
        the state `producer = human, producer_type = human` is unrepresentable
        rather than merely forbidden.
        """
        assert not producer_type_is_permitted("human")
        assert "human" not in {m.value for m in ProducerType}

    def test_the_three_members_are_permitted(self):
        for value in ("agent", "service", "unknown"):
            assert producer_type_is_permitted(value) is True, value

    def test_an_unlisted_value_is_not_permitted(self):
        assert producer_type_is_permitted("robot") is False

    def test_actor_type_still_permits_human(self):
        """The vocabulary was not narrowed to make the producer rule work."""
        assert actor_type_is_permitted("human") is True
        assert ActorType.HUMAN in PERMITTED_ACTOR_TYPES


class TestT4bProducerRoleConstraint:
    """T4b — `producer_type = human` is REJECTED (§7.1)."""

    def test_human_is_a_member_of_the_inherited_vocabulary(self):
        """The premise of T4b: this is a role rule, not a vocabulary edit."""
        assert ActorType.HUMAN in PERMITTED_ACTOR_TYPES
        assert "human" not in {m.value for m in ProducerType}

    def test_a_record_with_a_human_producer_type_is_rejected(self, record_factory):
        from plugins.evidence import EvidenceRecord

        raw = record_factory()
        raw["provenance"]["producer_type"] = "human"
        with pytest.raises(ev_errors.ProducerRoleViolation) as excinfo:
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")
        assert excinfo.value.reason_code == "PRODUCER_ROLE_VIOLATION"

    def test_the_rejection_is_distinct_from_an_unlisted_value(self, record_factory):
        """`human` is listed in ActorType; the caller must be told which problem."""
        from plugins.evidence import EvidenceRecord

        listed_but_wrong_role = record_factory()
        listed_but_wrong_role["provenance"]["producer_type"] = "human"
        with pytest.raises(ev_errors.ProducerRoleViolation):
            EvidenceRecord.from_mapping(listed_but_wrong_role, clock=lambda: "t")

        genuinely_unlisted = record_factory()
        genuinely_unlisted["provenance"]["producer_type"] = "robot"
        with pytest.raises(ev_errors.ProducerRoleViolation) as excinfo:
            EvidenceRecord.from_mapping(genuinely_unlisted, clock=lambda: "t")
        assert not isinstance(excinfo.value, ev_errors.CrossFieldViolation)


class TestT4cActorRoleControl:
    """T4c — `human` remains a valid ACTOR type. The positive control for T4b.

    **Restated by Amendment 1.** Before it, this class asserted that a
    human-approved DECISION is ACCEPTED. The record is now REJECTED, because v1
    admits the AI-04 Guard arm only and that arm's actor is a service; the human
    approval arm is deferred with no producer token. `human` is still a valid
    `ActorType`, which is what T4b's control has to prove, so the vocabulary
    assertion is kept and the record-level assertion is inverted with the reason
    recorded here.
    """

    def test_human_is_a_permitted_actor_type(self):
        assert actor_type_is_permitted("human") is True
        assert ActorType.HUMAN in PERMITTED_ACTOR_TYPES

    def test_a_decision_with_a_human_actor_is_rejected(self, decision_factory):
        """§6.6. A human approval is not representable in v1."""
        from plugins.evidence import EvidenceRecord

        raw = decision_factory()
        raw["provenance"]["actor"] = {"id": "human:reviewer", "type": "human"}
        with pytest.raises(ev_errors.ActorTypeNotAdmitted) as excinfo:
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")
        assert excinfo.value.reason_code == "ACTOR_TYPE_NOT_ADMITTED"

    def test_human_is_not_rejected_as_a_vocabulary_member(self, decision_factory):
        """The rejection is a role rule, not a vocabulary edit.

        `ActorType.HUMAN` parses; it is the cross-field rule that refuses it,
        which is a different error type and a different repair for the caller.
        """
        from plugins.evidence import EvidenceRecord

        raw = decision_factory()
        raw["provenance"]["actor"] = {"id": "human:reviewer", "type": "human"}
        with pytest.raises(ev_errors.CrossFieldViolation) as excinfo:
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")
        assert not isinstance(excinfo.value, ev_errors.ProducerRoleViolation)


class TestObservationFamily:
    """Amendment 1 §6.7 — the AI-05-owned observation vocabulary."""

    def test_exactly_three_members(self):
        assert [f.value for f in ObservationFamily] == [
            "SOURCE_READ",
            "PROVIDER_PROBE",
            "CAPABILITY_OBSERVATION",
        ]

    def test_an_unknown_fourth_member_is_rejected(self, record_factory):
        from plugins.evidence import EvidenceRecord

        raw = record_factory()
        raw["payload"]["family"] = "SOURCE_WRITE"
        with pytest.raises(ev_errors.UnsupportedVocabulary):
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")
