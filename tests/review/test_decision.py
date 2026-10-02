"""AI-10 §12 — the human decision: supplied, never generated.

The review layer has no path that produces a decision. These tests hold both
halves of that: the constructor requires one, and the raw boundary refuses
anything that would make one machine-made.
"""

from __future__ import annotations

import dataclasses

import pytest

from review.decision import HumanDecision
from review.errors import InvalidDecision, InvalidIdentifier
from review.vocabulary import MAX_RATIONALE_CHARS, HumanDecisionKind

pytestmark = pytest.mark.layer1


def decision(**overrides) -> HumanDecision:
    values = {
        "decision_id": "hd-1",
        "review_case_id": "rc-1",
        "actor_id": "li",
        "decision": "ACCEPTED",
        "rationale": "accepted as the basis for the next step",
        "recorded_at": "2026-10-02T00:02:00Z",
    }
    values.update(overrides)
    return HumanDecision(**values)


class TestShape:
    def test_a_human_decision_is_valid(self):
        built = decision()
        assert built.decision is HumanDecisionKind.ACCEPTED
        assert built.actor_id == "li"

    def test_the_vocabulary_is_exactly_three_members(self):
        assert {member.value for member in HumanDecisionKind} == {
            "ACCEPTED",
            "REJECTED",
            "DEFERRED",
        }

    def test_a_decision_outside_the_vocabulary_is_refused(self):
        with pytest.raises(InvalidDecision):
            decision(decision="APPROVED")

    def test_the_decision_is_required(self):
        with pytest.raises(TypeError):
            HumanDecision(decision_id="hd-1", review_case_id="rc-1", actor_id="li")

    def test_the_identifier_fields_are_bounded(self):
        with pytest.raises(InvalidIdentifier):
            decision(decision_id="has space")
        with pytest.raises(InvalidIdentifier):
            decision(review_case_id="")

    def test_the_rationale_is_bounded(self):
        with pytest.raises(InvalidDecision):
            decision(rationale="x" * (MAX_RATIONALE_CHARS + 1))
        assert decision(rationale="").rationale == ""

    def test_there_is_no_field_for_a_recommendation(self):
        fields = {field.name for field in dataclasses.fields(HumanDecision)}
        assert fields == {
            "schema_version",
            "decision_id",
            "review_case_id",
            "actor_id",
            "decision",
            "rationale",
            "recorded_at",
        }


class TestAnAgentDoesNotDecide:
    @pytest.mark.parametrize("agent", ["dsh", "codex"])
    def test_an_agent_id_is_refused_as_the_actor(self, agent):
        with pytest.raises(InvalidDecision) as excinfo:
            decision(actor_id=agent)
        assert "Agent" in str(excinfo.value)

    def test_a_human_identifier_is_accepted(self):
        assert decision(actor_id="li").actor_id == "li"


class TestMachineOrigin:
    @pytest.mark.parametrize(
        "forbidden",
        [
            "model",
            "generated",
            "generated_by",
            "auto",
            "predicted",
            "suggested",
            "confidence",
            "score",
            "rank",
            "probability",
            "correctness",
            "winner",
            "best_agent",
            "vote",
            "votes",
            "majority",
        ],
    )
    def test_a_machine_origin_field_is_refused_by_name(self, forbidden):
        raw = decision().to_mapping()
        raw[forbidden] = "anything"
        with pytest.raises(InvalidDecision) as excinfo:
            HumanDecision.from_mapping(raw)
        assert forbidden in str(excinfo.value)

    @pytest.mark.parametrize("forbidden", ["recommended", "recommended_decision"])
    def test_a_recommendation_field_is_refused(self, forbidden):
        raw = decision().to_mapping()
        raw[forbidden] = "ACCEPTED"
        with pytest.raises(InvalidDecision):
            HumanDecision.from_mapping(raw)

    def test_an_unknown_field_is_refused(self):
        raw = decision().to_mapping()
        raw["extra"] = 1
        with pytest.raises(InvalidDecision):
            HumanDecision.from_mapping(raw)

    def test_a_decision_round_trips(self):
        built = decision(decision="DEFERRED")
        assert HumanDecision.from_mapping(built.to_mapping()) == built
