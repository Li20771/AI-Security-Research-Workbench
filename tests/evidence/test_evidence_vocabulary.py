"""AI-05 vocabulary and role constraint.

Covers T4, T4b and T4c.

T4b and T4c are a **pair**, and neither is sufficient alone. T4b asserts that
`producer_type = human` is rejected. A system that rejected `human` in every role
would also pass T4b — and would break the recorded human approval of §6.3, where
`actor.type` must be `human`. T4c is the control that proves the constraint is a
ROLE constraint rather than a vocabulary edit.
"""

from __future__ import annotations

import pytest

from plugins.evidence import errors as ev_errors
from plugins.evidence.vocabulary import (
    PERMITTED_ACTOR_TYPES,
    PERMITTED_PRODUCER_TYPES,
    ActorType,
    AdmissionOutcome,
    EvidenceKind,
    FieldClass,
    actor_type_is_permitted,
    producer_type_is_permitted,
)
from plugins.guard.vocabulary import ActorType as GuardActorType

pytestmark = pytest.mark.layer1


class TestFrozenElsewhereIsImportedNotRestated:
    def test_actor_type_is_ai_04_s_own_object(self):
        """§3: frozen types are imported, never redefined.

        If AI-05 defined its own `ActorType`, this identity check would fail —
        which is the point: two definitions in one repository means two places to
        update and one of them forgotten.
        """
        assert ActorType is GuardActorType

    def test_the_inherited_vocabulary_is_unchanged(self):
        """AI-05 adds no member, removes none, renames none."""
        assert {m.value for m in ActorType} == {
            "human",
            "agent",
            "service",
            "unknown",
        }


class TestT4ClosedVocabulary:
    """T4 — an unlisted value is rejected, never treated as ordinary."""

    def test_evidence_kind_has_exactly_three_members(self):
        assert [k.value for k in EvidenceKind] == [
            "OBSERVATION",
            "DECISION",
            "EXECUTION",
        ]

    def test_admission_outcome_has_exactly_three_members(self):
        """Deliberately no third `BLOCKED` (§22.1).

        AI-04 §18.2 introduced `CheckResult` specifically to avoid a second
        `BLOCKED`, and §3 records that one word in two vocabularies is a defect
        AI-03 already paid for.
        """
        assert [o.value for o in AdmissionOutcome] == [
            "ACCEPTED",
            "REJECTED",
            "UNAVAILABLE",
        ]

    def test_there_is_no_free_text_field_class(self):
        """§14.2 — Class 5 does not exist. The absence is the boundary."""
        assert {c.value for c in FieldClass} == {
            "structural",
            "vocabulary",
            "identifier",
            "bounded_source",
        }
        assert "free_text" not in {c.value for c in FieldClass}

    def test_an_unlisted_kind_is_rejected(self, record_factory):
        from plugins.evidence import EvidenceRecord

        raw = record_factory(kind="SPECULATION")
        with pytest.raises(ev_errors.UnsupportedVocabulary):
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")


class TestT4bProducerRoleConstraint:
    """T4b — `producer_type = human` is REJECTED (§7.1)."""

    def test_human_is_a_member_of_the_inherited_vocabulary(self):
        """The premise of T4b: this is a role rule, not a vocabulary edit."""
        assert ActorType.HUMAN in PERMITTED_ACTOR_TYPES
        assert ActorType.HUMAN not in PERMITTED_PRODUCER_TYPES

    def test_the_producer_role_permits_three_values(self):
        assert PERMITTED_PRODUCER_TYPES == {
            ActorType.AGENT,
            ActorType.SERVICE,
            ActorType.UNKNOWN,
        }

    def test_human_is_not_a_permitted_producer_type(self):
        assert producer_type_is_permitted("human") is False
        assert producer_type_is_permitted(ActorType.HUMAN) is False

    def test_the_other_three_are_permitted(self):
        for value in ("agent", "service", "unknown"):
            assert producer_type_is_permitted(value) is True, value

    def test_a_record_with_a_human_producer_is_rejected(self, record_factory):
        from plugins.evidence import EvidenceRecord

        raw = record_factory()
        raw["provenance"]["producer_type"] = "human"
        with pytest.raises(ev_errors.ProducerRoleViolation) as excinfo:
            EvidenceRecord.from_mapping(raw, clock=lambda: "t")
        assert excinfo.value.reason_code == "PRODUCER_ROLE_VIOLATION"

    def test_the_rejection_is_distinct_from_an_unlisted_value(self, record_factory):
        """`human` is listed; the caller must be told which problem they have."""
        from plugins.evidence import EvidenceRecord

        listed_but_wrong_role = record_factory()
        listed_but_wrong_role["provenance"]["producer_type"] = "human"
        with pytest.raises(ev_errors.ProducerRoleViolation):
            EvidenceRecord.from_mapping(listed_but_wrong_role, clock=lambda: "t")

        genuinely_unlisted = record_factory()
        genuinely_unlisted["provenance"]["producer_type"] = "robot"
        with pytest.raises(ev_errors.UnsupportedVocabulary) as excinfo:
            EvidenceRecord.from_mapping(genuinely_unlisted, clock=lambda: "t")
        assert not isinstance(excinfo.value, ev_errors.ProducerRoleViolation)


class TestT4cActorRoleControl:
    """T4c — `actor.type = human` is ACCEPTED. The positive control for T4b."""

    def test_human_is_a_permitted_actor_type(self):
        assert actor_type_is_permitted("human") is True
        assert ActorType.HUMAN in PERMITTED_ACTOR_TYPES

    def test_a_human_approved_decision_is_accepted(self, build):
        """§6.3 — a recorded human approval is a DECISION whose actor is human.

        If T4b had been implemented by removing `human` from the vocabulary,
        this record could not be built, and the Workbench would be unable to
        record the one act the approval model depends on.
        """
        record = build(
            {
                "schema_version": 1,
                "kind": "DECISION",
                "provenance": {
                    "producer": "workbench-approval-recorder",
                    "producer_version": "1.0.0",
                    "producer_type": "service",
                    "actor": {"id": "human:reviewer", "type": "human"},
                    "workspace_id": "ws-1",
                },
                "payload": {
                    "decision": "ALLOW",
                    "reason_code": "APPROVED_BY_REVIEWER",
                    "reasons": ["reviewed at the GitHub checkpoint"],
                },
            }
        )
        assert str(record.provenance.actor.type) == "human"
        assert str(record.provenance.producer_type) == "service"
        assert record.integrity.content_digest is not None
