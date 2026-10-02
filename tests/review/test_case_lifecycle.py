"""AI-10 §5, §14 — the lifecycle: the legal transitions, and every refusal.

```text
NOT_RUN != PASS
BLOCKED != PASS
UNRESOLVED != PASS
```

A case that ends in one of the closure states is complete. Nothing here upgrades
one into a success, and nothing forces a case to a conclusion it did not reach.
"""

from __future__ import annotations

import pytest

from agents.vocabulary import AgentId

from review.case import (
    close,
    close_with_decision,
    create_case,
    observe_independence,
    observe_verification,
    record_comparison,
    record_decision,
    request_verification,
    supply_materials,
)
from review.decision import HumanDecision
from review.errors import InvalidCase, InvalidTransition, ProvenanceMismatch
from review.material import ReviewMaterial
from review.verification import VerificationObservation, VerificationRequest
from review.vocabulary import HumanDecisionKind, ReviewCaseState

from tests.review.conftest import claim, sha256, target

pytestmark = pytest.mark.layer2


def request_for(case_id: str, subject: str) -> VerificationRequest:
    return VerificationRequest(
        verification_id="vr-1",
        review_case_id=case_id,
        subject=subject,
        targets=(target(),),
        requested_at="2026-10-02T00:00:00Z",
    )


def observation_for(case_id: str, subject: str) -> VerificationObservation:
    return VerificationObservation(
        verification_id="vr-1",
        review_case_id=case_id,
        subject=subject,
        outcome="COMPLETED",
        tool_id="tests",
        operation="run",
        guard_decision_id="gd-1",
        observed_at="2026-10-02T00:01:00Z",
    )


def decision_for(case_id: str, kind: str = "ACCEPTED") -> HumanDecision:
    return HumanDecision(
        decision_id="hd-1",
        review_case_id=case_id,
        actor_id="li",
        decision=kind,
        rationale="accepted as the basis for the next step",
        recorded_at="2026-10-02T00:02:00Z",
    )


@pytest.fixture
def supplied(pair):
    """A case in MATERIALS_SUPPLIED with two aligned materials."""
    _, _, left, right = pair
    # The case is scoped to the workspace AI-03 resolved for the executions the
    # materials are attributed to, which is what makes the fixture real.
    case = create_case(workspace_id=left.workspace_id, review_case_id="rc-1")
    case = supply_materials(case, left=left, right=right)
    assert case.state is ReviewCaseState.MATERIALS_SUPPLIED
    return case, left, right


class TestCreateAndSupply:
    def test_a_new_case_is_created_and_empty(self):
        case = create_case(workspace_id="ws-1")
        assert case.state is ReviewCaseState.CREATED
        assert case.left_material_id is None
        assert case.right_material_id is None
        assert case.review_case_id.startswith("rc-")
        assert not case.terminal

    def test_supplying_materials_advances_to_materials_supplied(self, pair):
        _, _, left, right = pair
        case = supply_materials(
            create_case(workspace_id=left.workspace_id, review_case_id="rc-1"),
            left=left,
            right=right,
        )
        assert case.state is ReviewCaseState.MATERIALS_SUPPLIED
        assert (case.left_material_id, case.right_material_id) == ("m-left", "m-right")

    def test_two_sides_must_be_two_agents(self, pair):
        _, right_record, left, _ = pair
        same = ReviewMaterial(
            material_id="m-other",
            agent_id=AgentId.DSH,
            execution_id=right_record.result.execution_id,
            workspace_id=left.workspace_id,
            input_digest=left.input_digest,
            source_status="COMPLETED",
            claims=(claim(),),
        )
        with pytest.raises(InvalidCase):
            supply_materials(
                create_case(workspace_id=left.workspace_id, review_case_id="rc-1"),
                left=left,
                right=same,
            )

    def test_the_two_sides_must_be_two_materials(self, pair):
        _, _, left, _ = pair
        with pytest.raises(InvalidCase):
            supply_materials(
                create_case(workspace_id=left.workspace_id, review_case_id="rc-1"),
                left=left,
                right=left,
            )

    def test_a_foreign_workspace_material_is_refused(self, pair):
        _, _, left, right = pair
        foreign = ReviewMaterial(
            material_id="m-foreign",
            agent_id=AgentId.CODEX,
            execution_id=right.execution_id,
            workspace_id="ws-elsewhere",
            input_digest=sha256("b"),
            source_status="COMPLETED",
            claims=(claim(),),
        )
        with pytest.raises(InvalidCase):
            supply_materials(
                create_case(workspace_id=left.workspace_id, review_case_id="rc-1"),
                left=left,
                right=foreign,
            )

    def test_supplying_twice_is_refused(self, supplied):
        case, left, right = supplied
        with pytest.raises(InvalidTransition):
            supply_materials(case, left=left, right=right)


class TestComparison:
    def test_comparison_is_legal_from_materials_supplied(self, supplied):
        case, left, right = supplied
        advanced, findings = record_comparison(case, left=left, right=right)
        assert advanced.state is ReviewCaseState.COMPARISON_RECORDED
        assert findings

    def test_comparison_from_a_created_case_is_refused(self, pair):
        _, _, left, right = pair
        case = create_case(workspace_id=left.workspace_id, review_case_id="rc-1")
        with pytest.raises(InvalidTransition):
            record_comparison(case, left=left, right=right)

    def test_a_case_without_records_records_no_independence_answer(self, supplied):
        """No records, no observation — and no negative finding either.

        The case skips INDEPENDENCE_OBSERVED entirely. Nothing describes it as
        independent or non-independent, because nothing observed either.
        """
        case, left, right = supplied
        advanced, _findings = record_comparison(case, left=left, right=right)
        assert advanced.state is ReviewCaseState.COMPARISON_RECORDED
        assert advanced.state is not ReviewCaseState.INDEPENDENCE_OBSERVED
        mapping = advanced.to_mapping()
        assert "independent" not in mapping
        assert "independence" not in mapping

    def test_substituted_materials_are_refused(self, supplied):
        case, left, right = supplied
        substitute = ReviewMaterial(
            material_id="m-substitute",
            agent_id=AgentId.CODEX,
            execution_id=right.execution_id,
            workspace_id=right.workspace_id,
            input_digest=right.input_digest,
            source_status="COMPLETED",
            claims=(claim(),),
        )
        with pytest.raises(InvalidCase):
            record_comparison(case, left=left, right=substitute)


class TestIndependenceObservation:
    def test_an_aligned_pair_is_observed(self, pair):
        left_record, right_record, left, right = pair
        case = create_case(workspace_id=left.workspace_id, review_case_id="rc-1")
        case = supply_materials(case, left=left, right=right)
        advanced, finding = observe_independence(
            case,
            left=left,
            right=right,
            left_record=left_record,
            right_record=right_record,
        )
        assert advanced.state is ReviewCaseState.INDEPENDENCE_OBSERVED
        assert finding.independent is True

    def test_a_mismatched_declaration_is_refused(self, pair):
        left_record, right_record, left, right = pair
        wrong = ReviewMaterial(
            material_id="m-wrong",
            agent_id=AgentId.CODEX,
            execution_id="ex-something-else",
            workspace_id=right.workspace_id,
            input_digest=right.input_digest,
            source_status="COMPLETED",
            claims=(claim(),),
        )
        case = create_case(workspace_id=left.workspace_id, review_case_id="rc-1")
        case = supply_materials(case, left=left, right=wrong)
        with pytest.raises(ProvenanceMismatch):
            observe_independence(
                case,
                left=left,
                right=wrong,
                left_record=left_record,
                right_record=right_record,
            )

    def test_observing_after_a_comparison_is_refused(self, pair):
        left_record, right_record, left, right = pair
        case = create_case(workspace_id=left.workspace_id, review_case_id="rc-1")
        case = supply_materials(case, left=left, right=right)
        case, _findings = record_comparison(case, left=left, right=right)
        with pytest.raises(InvalidTransition):
            observe_independence(
                case,
                left=left,
                right=right,
                left_record=left_record,
                right_record=right_record,
            )


class TestVerification:
    def test_a_request_is_legal_after_a_comparison(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        case = request_verification(case, request=request_for(case.review_case_id, "m-left#c1"))
        assert case.state is ReviewCaseState.VERIFICATION_REQUESTED

    def test_a_request_before_a_comparison_is_refused(self, supplied):
        case, _, _ = supplied
        with pytest.raises(InvalidTransition):
            request_verification(case, request=request_for(case.review_case_id, "m-left#c1"))

    def test_a_request_for_another_case_is_refused(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        with pytest.raises(InvalidCase):
            request_verification(case, request=request_for("rc-other", "m-left#c1"))

    def test_a_subject_outside_the_case_is_refused(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        with pytest.raises(InvalidCase):
            request_verification(case, request=request_for(case.review_case_id, "m-elsewhere#c1"))

    def test_an_observation_needs_a_request_first(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        with pytest.raises(InvalidTransition):
            observe_verification(
                case, observation=observation_for(case.review_case_id, "m-left#c1")
            )

    def test_an_observation_after_a_request_advances_the_case(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        case = request_verification(case, request=request_for(case.review_case_id, "m-left#c1"))
        case = observe_verification(
            case, observation=observation_for(case.review_case_id, "m-left#c1")
        )
        assert case.state is ReviewCaseState.VERIFICATION_OBSERVED

    def test_one_round_in_v1_a_second_request_is_refused(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        case = request_verification(case, request=request_for(case.review_case_id, "m-left#c1"))
        case = observe_verification(
            case, observation=observation_for(case.review_case_id, "m-left#c1")
        )
        with pytest.raises(InvalidTransition):
            request_verification(case, request=request_for(case.review_case_id, "m-left#c1"))


class TestHumanDecision:
    def test_a_decision_after_a_comparison_is_recorded(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        case = record_decision(case, decision=decision_for(case.review_case_id))
        assert case.state is ReviewCaseState.HUMAN_DECISION_RECORDED

    def test_a_decision_for_another_case_is_refused(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        with pytest.raises(InvalidCase):
            record_decision(case, decision=decision_for("rc-other"))

    def test_a_decision_cannot_be_recorded_before_a_comparison(self, supplied):
        case, _, _ = supplied
        with pytest.raises(InvalidTransition):
            record_decision(case, decision=decision_for(case.review_case_id))

    def test_deferred_leaves_the_case_open(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        deferred = decision_for(case.review_case_id, "DEFERRED")
        case = record_decision(case, decision=deferred)
        with pytest.raises(InvalidTransition):
            close_with_decision(case, decision=deferred)
        assert not case.terminal

    def test_a_superseding_decision_may_be_recorded(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        case = record_decision(case, decision=decision_for(case.review_case_id, "DEFERRED"))
        case = record_decision(case, decision=decision_for(case.review_case_id, "ACCEPTED"))
        case = close_with_decision(case, decision=decision_for(case.review_case_id, "ACCEPTED"))
        assert case.state is ReviewCaseState.CLOSED

    def test_only_an_accepted_or_rejected_decision_closes(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        case = record_decision(case, decision=decision_for(case.review_case_id, "REJECTED"))
        case = close_with_decision(case, decision=decision_for(case.review_case_id, "REJECTED"))
        assert case.state is ReviewCaseState.CLOSED

    def test_closing_without_a_decision_is_refused(self, supplied):
        case, left, right = supplied
        case, _ = record_comparison(case, left=left, right=right)
        with pytest.raises(InvalidTransition):
            close_with_decision(case, decision=decision_for(case.review_case_id))


class TestClosure:
    @pytest.mark.parametrize("state", ["UNRESOLVED", "BLOCKED", "NOT_RUN"])
    def test_each_closure_state_is_reachable_and_terminal(self, supplied, state):
        case, _, _ = supplied
        closed = close(case, state=state)
        assert closed.state is ReviewCaseState(state)
        assert closed.terminal

    def test_a_case_may_close_before_anything_is_supplied(self):
        case = close(create_case(workspace_id="ws-1", review_case_id="rc-1"), state="NOT_RUN")
        assert case.state is ReviewCaseState.NOT_RUN
        assert case.left_material_id is None

    def test_close_refuses_a_non_closure_state(self, supplied):
        case, _, _ = supplied
        for state in ("CLOSED", "MATERIALS_SUPPLIED", "HUMAN_DECISION_RECORDED"):
            with pytest.raises(InvalidTransition):
                close(case, state=state)

    def test_a_terminal_case_takes_no_further_acts(self, supplied):
        case, left, right = supplied
        closed = close(case, state="BLOCKED")
        with pytest.raises(InvalidTransition):
            record_comparison(closed, left=left, right=right)
        with pytest.raises(InvalidTransition):
            close(closed, state="UNRESOLVED")
        with pytest.raises(InvalidTransition):
            record_decision(closed, decision=decision_for(closed.review_case_id))

    def test_a_closure_state_is_not_a_success(self, supplied):
        case, _, _ = supplied
        for state in ("UNRESOLVED", "BLOCKED", "NOT_RUN"):
            closed = close(case, state=state)
            assert closed.state is not ReviewCaseState.CLOSED
            assert closed.state.value not in {"CLOSED", "MATERIALS_SUPPLIED"}


class TestCaseInvariants:
    def test_created_cannot_hold_materials(self):
        from review.case import ReviewCase

        with pytest.raises(InvalidCase):
            ReviewCase(
                review_case_id="rc-1",
                workspace_id="ws-1",
                left_material_id="m1",
                right_material_id="m2",
                state=ReviewCaseState.CREATED,
            )

    def test_a_supplied_state_requires_both_materials(self):
        from review.case import ReviewCase

        with pytest.raises(InvalidCase):
            ReviewCase(
                review_case_id="rc-1",
                workspace_id="ws-1",
                state=ReviewCaseState.MATERIALS_SUPPLIED,
            )

    def test_the_state_vocabulary_is_closed(self):
        from review.case import ReviewCase

        with pytest.raises(InvalidCase):
            ReviewCase(
                review_case_id="rc-1",
                workspace_id="ws-1",
                state="APPROVED",
            )
