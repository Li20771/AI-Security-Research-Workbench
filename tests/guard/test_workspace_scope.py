"""T1 — workspace isolation.

Contract §5: exactly one workspace per evaluation, and a mismatch is never
merged, filtered or repaired. §21 makes a mismatch `DENY` and an unresolvable
workspace `BLOCKED` — both determined outcomes, in opposite directions.
"""

from __future__ import annotations

import pytest

from plugins.guard import GuardDecision, evaluate

from tests.guard.conftest import WS, WS_OTHER, make_policy, make_request, make_rule


pytestmark = pytest.mark.layer2


class TestT1WorkspaceIsolation:
    def test_agreeing_workspace_is_evaluated_normally(self):
        record = evaluate(make_request(), make_policy(make_rule("allow")))
        assert record.decision is GuardDecision.ALLOW

    def test_policy_workspace_mismatch_is_deny(self):
        policy = make_policy(make_rule("allow"), workspace_id=WS_OTHER)
        record = evaluate(make_request(), policy)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "WORKSPACE_MISMATCH"

    def test_a_mismatch_names_both_workspaces(self):
        policy = make_policy(make_rule("allow"), workspace_id=WS_OTHER)
        record = evaluate(make_request(), policy)
        joined = " ".join(record.reasons)
        assert WS in joined and WS_OTHER in joined

    def test_the_decision_records_the_requests_workspace(self):
        record = evaluate(make_request(), make_policy(make_rule("allow")))
        assert record.workspace_id == WS

    def test_a_mismatched_policy_is_not_consulted_for_rules(self):
        """A policy for another workspace must not authorize, however permissive."""
        policy = make_policy(make_rule("allow-all", priority=0), workspace_id=WS_OTHER)
        record = evaluate(make_request(), policy)
        assert record.decision is not GuardDecision.ALLOW
        assert record.provenance.rule_id is None

    def test_unscoped_request_is_denied(self):
        raw = make_request(workspace={**make_request()["workspace"], "workspace_id": "  "})
        record = evaluate(raw, make_policy(make_rule("allow")))
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "REQUEST_UNSCOPED"

    def test_missing_workspace_id_is_denied(self):
        workspace = make_request()["workspace"]
        workspace.pop("workspace_id")
        record = evaluate(make_request(workspace=workspace), None)
        assert record.decision is GuardDecision.DENY


class TestContextWorkspaceAgreement:
    """§5's fourth clause: every authorization-relevant item's workspace."""

    @staticmethod
    def _context_with_foreign_item():
        from plugins.context.classification import classify, RawItem
        from plugins.context.context import ContextResponse, FreshnessSummary
        from plugins.context.vocabulary import (
            ContextStatus,
            Freshness,
            ItemKind,
            SourceKind,
            StatusValue,
            WorkingTreeState,
        )
        from plugins.context.workspace import WorkspaceIdentity

        identity = WorkspaceIdentity(
            workspace_id=WS,
            workspace_root="/tmp/ws",
            repository=None,
            branch="main",
            commit="a" * 40,
            detached=False,
            working_tree=WorkingTreeState.CLEAN,
            changed_files=0,
        )
        item = classify(
            RawItem(subject="declared.gate", value="NOT_RUN", declared_state="NOT_RUN"),
            source_kind=SourceKind.EXIT_REPORT,
            source_identity="docs/x.md",
            source_revision="r",
            retrieved_at="2026-09-29T00:00:00Z",
            workspace_id=WS_OTHER,  # foreign
            freshness=Freshness.CURRENT,
        )
        return ContextResponse(
            workspace=identity,
            facts=(),
            history=(item,),
            plans=(),
            sources=(),
            freshness=FreshnessSummary(0, 1, 0, Freshness.STALE),
            status=ContextStatus.PARTIAL,
            conflicts=(),
            retrieved_at="2026-09-29T00:00:00Z",
        )

    def test_a_foreign_context_item_cannot_satisfy_a_condition(self):
        rule = make_rule(
            "needs-fact",
            conditions=[{"field": "declared.gate.truth_state", "op": "eq", "value": "PASS"}],
        )
        raw = make_request(context={"response": self._context_with_foreign_item()})
        record = evaluate(raw, make_policy(rule))
        assert record.decision is not GuardDecision.ALLOW

    def test_a_foreign_context_response_is_not_merged(self):
        from plugins.context.context import ContextResponse, FreshnessSummary
        from plugins.context.vocabulary import ContextStatus, Freshness, WorkingTreeState
        from plugins.context.workspace import WorkspaceIdentity

        foreign = ContextResponse(
            workspace=WorkspaceIdentity(
                workspace_id=WS_OTHER,
                workspace_root="/tmp/other",
                repository=None,
                branch=None,
                commit=None,
                detached=False,
                working_tree=WorkingTreeState.UNKNOWN,
                changed_files=None,
            ),
            facts=(),
            history=(),
            plans=(),
            sources=(),
            freshness=FreshnessSummary(0, 0, 0, Freshness.CURRENT),
            status=ContextStatus.UNKNOWN,
            conflicts=(),
            retrieved_at="2026-09-29T00:00:00Z",
        )
        rule = make_rule(
            "needs-fact",
            conditions=[{"field": "declared.gate.item_kind", "op": "eq", "value": "FACT"}],
        )
        raw = make_request(context={"response": foreign})
        record = evaluate(raw, make_policy(rule))
        assert record.decision is not GuardDecision.ALLOW
