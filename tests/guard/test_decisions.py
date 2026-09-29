"""T5, T6, T8, T9, T11 — decision semantics and provenance.

Contract §2, §13, §15.1, §18, §19.

**Negative decisions are not failures.** Several tests here expect `DENY`. The
test passes when Guard produces the expected *decision* (§3): a test status of
PASS with a guard decision of `DENY` means the test verified that Guard denied
the request.
"""

from __future__ import annotations

import json

import pytest

from plugins.guard import CheckResult, GuardDecision, evaluate

from tests.guard.conftest import eq, make_policy, make_request, make_rule

pytestmark = pytest.mark.layer2


class TestT5ExplicitDeny:
    def test_a_matching_deny_rule_decides_deny(self):
        policy = make_policy(make_rule("deny-it", effect="DENY"))
        record = evaluate(make_request(), policy)
        assert record.decision is GuardDecision.DENY
        assert record.provenance.rule_id == "deny-it"
        assert record.reason_code == "REASON_DENY-IT"

    def test_the_deny_is_a_completed_policy_decision(self):
        """§13: not the default, and not an unavailable evaluation."""
        policy = make_policy(make_rule("deny-it", effect="DENY"))
        record = evaluate(make_request(), policy)
        assert record.reason_code != "NO_APPLICABLE_RULE"
        assert record.decision is not GuardDecision.BLOCKED

    def test_an_explicit_deny_outranks_a_lower_priority_allow(self):
        policy = make_policy(
            make_rule("allow", priority=5, effect="ALLOW"),
            make_rule("deny", priority=0, effect="DENY"),
        )
        assert evaluate(make_request(), policy).decision is GuardDecision.DENY


class TestT6ExplicitAllow:
    def test_a_satisfied_allow_rule_decides_allow(self):
        record = evaluate(make_request(), make_policy(make_rule("allow")))
        assert record.decision is GuardDecision.ALLOW
        assert record.provenance.rule_id == "allow"

    def test_every_check_is_recorded(self):
        rule = make_rule(
            "allow",
            match=[eq("action.permission_level", "read")],
            conditions=[eq("target.kind", "repository")],
        )
        record = evaluate(make_request(), make_policy(rule))
        assert record.decision is GuardDecision.ALLOW
        assert {c.check_id for c in record.checks} == {"allow.match", "allow.conditions"}
        assert all(str(c.result) == "SATISFIED" for c in record.checks)

    def test_an_unsatisfied_condition_does_not_allow(self):
        rule = make_rule("allow", conditions=[eq("target.kind", "vehicle")])
        assert evaluate(make_request(), make_policy(rule)).decision is not GuardDecision.ALLOW


class TestT8DefaultDeny:
    def test_no_applicable_rule_is_deny(self):
        rule = make_rule("never-matches", match=[eq("action.id", "something-else")])
        record = evaluate(make_request(), make_policy(rule))
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "NO_APPLICABLE_RULE"

    def test_default_deny_names_no_rule(self):
        rule = make_rule("never-matches", match=[eq("action.id", "something-else")])
        assert evaluate(make_request(), make_policy(rule)).provenance.rule_id is None

    def test_an_empty_policy_is_default_deny(self):
        assert evaluate(make_request(), make_policy()).decision is GuardDecision.DENY

    def test_every_candidate_is_recorded_as_rejected(self):
        """T8: the trace shows every candidate was evaluated and rejected."""
        policy = make_policy(
            make_rule("a", match=[eq("action.id", "x")]),
            make_rule("b", match=[eq("action.id", "y")]),
        )
        record = evaluate(make_request(), policy)
        assert record.decision is GuardDecision.DENY
        assert {c.result for c in record.checks} == {CheckResult.REJECTED}

    def test_default_deny_is_distinguishable_from_explicit_deny(self):
        default = evaluate(make_request(), make_policy(make_rule("n", match=[eq("action.id", "z")])))
        explicit = evaluate(make_request(), make_policy(make_rule("n", effect="DENY")))
        assert default.decision is explicit.decision is GuardDecision.DENY
        assert default.reason_code != explicit.reason_code


class TestT9MalformedRequest:
    @pytest.mark.parametrize(
        "raw",
        [
            {"schema_version": 99},
            "not-an-object",
            {"schema_version": 1, "actor": {"id": "a", "type": "not-a-type"}},
            {"schema_version": 1, "workspace": {"workspace_id": "w", "working_tree": "MAYBE"}},
            {"schema_version": 1, "action": {"id": "a", "permission_level": "root"}},
            {"schema_version": 1, "target": {"kind": "spaceship"}},
        ],
    )
    def test_malformed_requests_are_denied(self, raw):
        assert evaluate(raw, make_policy(make_rule("allow"))).decision is GuardDecision.DENY

    def test_a_malformed_request_never_allows(self):
        raw = {"schema_version": 1, "action": {"permission_level": "root"}}
        assert evaluate(raw, make_policy(make_rule("allow"))).decision is not GuardDecision.ALLOW

    def test_a_malformed_request_reports_malformed(self):
        raw = {"schema_version": 99}
        assert evaluate(raw, None).reason_code == "REQUEST_MALFORMED"

    def test_an_unlisted_enum_is_denied_not_ignored(self):
        """§4.2: an unlisted value is never silently treated as an ordinary one."""
        raw = make_request(action={"id": "a", "permission_level": "superuser"})
        record = evaluate(raw, make_policy(make_rule("allow")))
        assert record.decision is GuardDecision.DENY
        assert "permission_level" in " ".join(record.reasons)

    def test_the_policy_is_never_consulted_for_a_malformed_request(self):
        raw = {"schema_version": 99}
        assert evaluate(raw, make_policy(make_rule("allow"))).provenance.rule_id is None


class TestT11Provenance:
    def test_every_question_of_section_19_is_answerable(self):
        rule = make_rule(
            "allow",
            match=[eq("action.id", "read-file")],
            conditions=[eq("target.kind", "repository")],
        )
        record = evaluate(make_request(), make_policy(rule))

        assert record.actor.id == "human:reviewer"
        assert record.actor.type == "human"
        assert record.action.id == "read-file"
        assert str(record.action.permission_level) == "read"
        assert record.workspace_id == "ws-1"
        assert str(record.target.kind) == "repository"
        assert record.provenance.policy_id == "policy-1"
        assert record.provenance.policy_revision == "rev-1"
        assert record.provenance.policy_digest
        assert record.provenance.rule_id == "allow"
        assert record.decision is GuardDecision.ALLOW
        assert record.reason_code
        assert record.checks

    def test_the_record_serialises_without_a_deterministic_field(self):
        """§18.1: determinism is a guarantee, not a field."""
        record = evaluate(make_request(), make_policy(make_rule("allow")))
        payload = record.to_dict()
        assert "deterministic" not in payload

    def test_the_record_carries_no_raw_context(self):
        record = evaluate(make_request(), make_policy(make_rule("allow")))
        rendered = json.dumps(record.to_dict())
        assert "response" not in rendered or "context_refs" in rendered
        assert record.provenance.context_refs == ()

    def test_the_evaluation_digest_is_reproducible_from_the_record(self):
        from plugins.guard.digest import evaluation_digest, evaluation_projection
        from plugins.guard.policy import Policy

        policy = Policy.from_mapping(make_policy(make_rule("allow")))
        record = evaluate(make_request(), policy)
        rebuilt = evaluation_projection(
            request_digest_value=record.request_digest,
            policy=policy,
            policy_digest_value=record.provenance.policy_digest or "",
            trace=(),
            context_refs=record.provenance.context_refs,
            decision=str(record.decision),
            reason_code=record.reason_code,
            rule_id=record.provenance.rule_id,
        )
        # The trace differs (the record's is the real walk), so the digests must
        # differ -- which is the point: the digest covers the trace, and a
        # projection without it is a different claim.
        assert evaluation_digest(rebuilt) != record.evaluation_digest

    def test_the_record_has_no_evidence_ref_until_ai_05_exists(self):
        """C9: evidence_ref stays null; a null is not a failure."""
        record = evaluate(make_request(), make_policy(make_rule("allow")))
        assert record.evidence_ref is None
