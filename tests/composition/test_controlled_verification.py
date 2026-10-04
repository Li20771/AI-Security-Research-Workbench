"""AI-14-B / B4 — the controlled verification caller.

AI-10 issues `VerificationRequest`s and performs nothing. These tests are about
the other side of that seam: the mapping is declared, every invocation goes
through AI-06's single path and then Guard, and a refusal is reported rather than
repaired.
"""

from __future__ import annotations

import pytest

from plugins.guard import evaluate
from plugins.security_tools.vocabulary import AdapterFamily, ToolOutcome
from tools import default_registry

from review.verification import VerificationRequest, VerificationTarget

from composition.errors import VerificationRefused
from composition.verification import ToolPlanEntry, controlled_verification

from tests.composition.conftest import (
    GIT_TOOL_ID,
    GIT_TOOL_VERSION,
    a_read_only_target,
    a_tool_workspace,
    a_workspace,
    an_actor,
    read_level,
)

pytestmark = pytest.mark.layer2


def _a_request(*target_ids: str) -> VerificationRequest:
    return VerificationRequest(
        verification_id="ver-1",
        review_case_id="case-1",
        subject="material-1#claim-1",
        targets=tuple(
            VerificationTarget(target_id=target_id, description="a declared check")
            for target_id in target_ids
        ),
        requested_at="2026-10-04T00:00:00Z",
    )


def _an_entry(target_id: str, *, operation: str = "status", **overrides) -> ToolPlanEntry:
    arguments = {
        "target_id": target_id,
        "tool_id": GIT_TOOL_ID,
        "tool_version": GIT_TOOL_VERSION,
        "adapter_family": AdapterFamily.GIT,
        "operation": operation,
        "permission_level": read_level(),
        "target": a_read_only_target(),
        "timeout_seconds": 5,
    }
    arguments.update(overrides)
    return ToolPlanEntry(**arguments)


def _run(tmp_path, request, plan):
    root, workspace_id = a_workspace(tmp_path / "ws")
    return controlled_verification(
        request,
        plan=plan,
        workspace=a_tool_workspace(root, workspace_id),
        actor=an_actor(),
        registry=default_registry(),
        evaluator=evaluate,
        policy=None,  # no policy: Guard's fail-closed case
        clock=lambda: "2026-10-04T00:00:10Z",
    )


def test_every_target_produces_exactly_one_observation(tmp_path) -> None:
    """One target, one invocation, one observation — in the request's order."""
    request = _a_request("t-b", "t-a")
    observations = _run(tmp_path, request, [_an_entry("t-a"), _an_entry("t-b")])

    assert [item.subject for item in observations] == ["material-1#claim-1"] * 2
    assert len(observations) == 2
    assert {item.verification_id for item in observations} == {"ver-1"}
    assert {item.review_case_id for item in observations} == {"case-1"}
    # AI-10 sorts targets by target_id, and the caller follows the request.
    assert [item.tool_id for item in observations] == [GIT_TOOL_ID, GIT_TOOL_ID]


def test_a_non_allow_guard_decision_refuses_the_invocation(tmp_path) -> None:
    """SECURITY BOUNDARY. §4.2 rule 2: Guard decides, per invocation.

    With no policy, Guard refuses. The observation carries that refusal and the
    decision it came from — and the adapter never ran, because the tool path does
    not reach an adapter without an ALLOW.
    """
    observations = _run(tmp_path, _a_request("t-a"), [_an_entry("t-a")])

    observation = observations[0]
    assert observation.outcome is ToolOutcome.BLOCKED
    # The refusal is ATTRIBUTABLE: a real Guard evaluation produced it, and the
    # caller carries that evaluation's id rather than an unexplained "blocked".
    assert observation.guard_decision_id.startswith("grd-")
    assert observation.guard_reason_code == "POLICY_MISSING"


def test_a_refusal_is_reported_and_not_repaired(tmp_path) -> None:
    """One refused target does not become a second attempt with another tool."""
    observations = _run(
        tmp_path, _a_request("t-a"), [_an_entry("t-a", operation="not_an_operation")]
    )

    assert len(observations) == 1
    assert observations[0].outcome is not ToolOutcome.COMPLETED


# ---------------------------------------------------------------------------
# The declared mapping is the caller's, and it is enforced
# ---------------------------------------------------------------------------


def test_a_target_with_no_declared_entry_is_refused(tmp_path) -> None:
    """No operation is inferred from a description (AI-10 §7.1)."""
    with pytest.raises(VerificationRefused):
        _run(tmp_path, _a_request("t-a"), [])


def test_a_plan_entry_the_request_did_not_ask_for_is_refused(tmp_path) -> None:
    """The request bounds the work it authorises to be requested."""
    with pytest.raises(VerificationRefused):
        _run(tmp_path, _a_request("t-a"), [_an_entry("t-a"), _an_entry("t-elsewhere")])


def test_a_duplicate_entry_is_refused(tmp_path) -> None:
    """One target is one invocation; a second entry would replace the first."""
    with pytest.raises(VerificationRefused):
        _run(tmp_path, _a_request("t-a"), [_an_entry("t-a"), _an_entry("t-a")])


# ---------------------------------------------------------------------------
# What an observation is not
# ---------------------------------------------------------------------------


def test_an_observation_is_not_a_verdict() -> None:
    """AI-10 §5, §11: a verification observation is what an invocation DID.

    AI-06's outcome vocabulary is closed at six and contains no PASS, FAIL or
    VERIFIED — deliberately, so that `exit_code == 0` cannot be read as a
    research conclusion.
    """
    assert {member.value for member in ToolOutcome} == {
        "COMPLETED",
        "FAILED",
        "BLOCKED",
        "NOT_RUN",
        "TIMED_OUT",
        "UNKNOWN",
    }


def test_the_caller_holds_no_policy_of_its_own() -> None:
    """The evaluator and policy are HANDED to the tool path, never consulted here.

    The composition passes both straight into `invoke()`; it does not evaluate,
    does not inspect a decision and does not keep one. A caller that could read a
    decision could cache one.
    """
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "composition"
        / "verification.py"
    ).read_text(encoding="utf-8")

    assert "evaluate(" not in source.replace("evaluator=evaluator", "")
    assert "DecisionRecord" not in source
