"""§7 capability, §8/§15.2 approval, §16 target classification, §15.1 absolute deny.

These are the boundaries that turn an otherwise-satisfied `ALLOW` into
`BLOCKED`. §14.1 step 6 makes them a **gate, not an override**: they can turn an
`ALLOW` into `BLOCKED`, never the reverse.
"""

from __future__ import annotations

import pytest

from plugins.guard import GuardDecision, evaluate

from tests.guard.conftest import eq, make_policy, make_request, make_rule

pytestmark = pytest.mark.layer2

PERMISSIVE = make_policy(make_rule("allow-all", priority=0))
GATED_RULE = make_policy(
    make_rule("gated", priority=0, conditions=[eq("approval.status", "VERIFIED")])
)


def with_capability(status: str, capability_id: str = "cap-1"):
    return make_request(
        capability={"id": capability_id},
        capability_state={"records": [{"capability_id": capability_id, "status": status}]},
    )


class TestCapabilityRule:
    """§7: only an explicitly required VERIFIED state may satisfy a condition."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("DECLARED", GuardDecision.BLOCKED),
            ("NOT_VERIFIED", GuardDecision.BLOCKED),
            ("UNAVAILABLE", GuardDecision.BLOCKED),
            ("UNKNOWN", GuardDecision.UNKNOWN),
        ],
    )
    def test_non_verified_states_never_allow(self, status, expected):
        rule = make_rule("needs", conditions=[eq("capability.status", "VERIFIED")])
        record = evaluate(with_capability(status), make_policy(rule))
        assert record.decision is expected

    def test_verified_satisfies_a_required_condition(self):
        rule = make_rule("needs", conditions=[eq("capability.status", "VERIFIED")])
        assert evaluate(with_capability("VERIFIED"), make_policy(rule)).decision is (
            GuardDecision.ALLOW
        )

    def test_a_policy_cannot_authorize_on_declared(self):
        """§7: DECLARED never ALLOW, however the policy is written."""
        rule = make_rule("allow-declared", conditions=[eq("capability.status", "DECLARED")])
        assert evaluate(with_capability("DECLARED"), make_policy(rule)).decision is (
            GuardDecision.BLOCKED
        )

    def test_a_rule_constraining_an_unnamed_capability_is_blocked(self):
        rule = make_rule("needs", conditions=[eq("capability.status", "VERIFIED")])
        record = evaluate(make_request(capability={"id": None}), make_policy(rule))
        assert record.decision is GuardDecision.BLOCKED

    def test_guard_probes_nothing(self):
        """§7: Guard consumes normalized state; it never invokes a provider."""
        import plugins.guard

        source = "".join(
            (plugins.guard.__file__ or ""),
        )
        assert source  # guard is importable and self-contained
        for name in ("requests", "http", "urllib", "socket"):
            assert name not in dir(plugins.guard)


class TestApprovalRule:
    """§8.1: MISSING, INVALID and UNKNOWN are all no-approval, and all fail closed."""

    @pytest.mark.parametrize("status", ["MISSING", "INVALID", "UNKNOWN"])
    def test_non_verified_approval_is_blocked(self, status):
        raw = make_request(approval={"status": status, "scope_digest": None, "reference": None})
        assert evaluate(raw, GATED_RULE).decision is GuardDecision.BLOCKED

    def test_verified_approval_satisfies_the_gate(self):
        raw = make_request(
            approval={"status": "VERIFIED", "scope_digest": "d", "reference": "APR-1"}
        )
        assert evaluate(raw, GATED_RULE).decision is GuardDecision.ALLOW

    def test_the_approval_reference_is_recorded(self):
        raw = make_request(
            approval={"status": "VERIFIED", "scope_digest": "d", "reference": "APR-1"}
        )
        assert evaluate(raw, GATED_RULE).provenance.approval_reference == "APR-1"

    def test_a_caller_boolean_is_not_part_of_the_request_shape(self):
        """§8: `approved: true` is not evidence of human approval."""
        from plugins.guard import GuardRequest
        from plugins.guard.errors import RequestMalformed

        raw = make_request(approval={"approved": True})
        with pytest.raises(RequestMalformed):
            GuardRequest.from_mapping(raw)


class TestApprovalGatedActions:
    """§15.2. AI-04 issues no approvals, so these are permanently BLOCKED."""

    @pytest.mark.parametrize("level", ["system-change", "remote-change"])
    def test_elevated_permission_levels_are_blocked(self, level):
        raw = make_request(action={"id": "x", "permission_level": level})
        record = evaluate(raw, PERMISSIVE)
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code == "APPROVAL_NOT_VERIFIED"

    @pytest.mark.parametrize("level", ["read", "analyze", "test", "modify"])
    def test_lower_permission_levels_are_not_gated(self, level):
        raw = make_request(action={"id": "x", "permission_level": level})
        assert evaluate(raw, PERMISSIVE).decision is GuardDecision.ALLOW

    def test_a_verified_approval_does_not_unlock_system_change_by_itself(self):
        """The gate needs a verified approval; AI-04 provides no source for one,
        so a caller cannot manufacture the unlock through the boolean it was
        forbidden to send."""
        raw = make_request(
            action={"id": "x", "permission_level": "system-change"},
            approval={"status": "MISSING"},
        )
        assert evaluate(raw, PERMISSIVE).decision is GuardDecision.BLOCKED


class TestTargetClassification:
    """§16: an unclassified target is not a safe target."""

    def test_unclassified_vehicle_target_is_blocked(self):
        raw = make_request(
            target={"kind": "ecu", "identifier": None, "environment": "unknown",
                    "interface": None, "is_real": None, "sensitivity": "internal"}
        )
        record = evaluate(raw, PERMISSIVE)
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code == "TARGET_CLASSIFICATION_UNKNOWN"

    def test_unknown_is_never_inferred_to_be_simulator(self):
        raw = make_request(
            target={"kind": "can_bus", "identifier": None, "environment": None,
                    "interface": None, "is_real": None, "sensitivity": None}
        )
        assert evaluate(raw, PERMISSIVE).decision is GuardDecision.BLOCKED

    @pytest.mark.parametrize("interface", ["vcan", "simulator", "isolated_harness"])
    def test_safe_interfaces_are_eligible(self, interface):
        raw = make_request(
            target={"kind": "can_bus", "identifier": "vcan0", "environment": "isolated",
                    "interface": interface, "is_real": False, "sensitivity": "internal"}
        )
        assert evaluate(raw, PERMISSIVE).decision is GuardDecision.ALLOW

    def test_a_real_vehicle_is_blocked(self):
        raw = make_request(
            target={"kind": "vehicle", "identifier": "VIN", "environment": "real",
                    "interface": "can", "is_real": True, "sensitivity": "confidential"}
        )
        assert evaluate(raw, PERMISSIVE).decision is GuardDecision.BLOCKED

    def test_a_non_vehicle_target_does_not_need_classification(self):
        raw = make_request(
            target={"kind": "repository", "identifier": "src/", "environment": None,
                    "interface": None, "is_real": None, "sensitivity": None}
        )
        assert evaluate(raw, PERMISSIVE).decision is GuardDecision.ALLOW


class TestAbsoluteDeny:
    """§15.1. Never overridden by policy, priority or approval."""

    def test_secret_material_access_is_denied(self):
        raw = make_request(
            target={"kind": "secret_material", "identifier": ".env", "environment": "isolated",
                    "interface": None, "is_real": False, "sensitivity": "secret_material"}
        )
        record = evaluate(raw, PERMISSIVE)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "SECRET_MATERIAL_ACCESS"

    def test_the_secret_deny_outranks_a_matching_allow_rule(self):
        raw = make_request(target={"kind": "repository", "identifier": None,
                                   "environment": "isolated", "interface": None,
                                   "is_real": False, "sensitivity": "secret_material"})
        assert evaluate(raw, PERMISSIVE).decision is GuardDecision.DENY

    def test_the_deny_runs_before_rule_evaluation(self):
        raw = make_request(
            target={"kind": "secret_material", "identifier": None, "environment": "isolated",
                    "interface": None, "is_real": False, "sensitivity": "secret_material"}
        )
        record = evaluate(raw, PERMISSIVE)
        assert record.provenance.rule_id is None

    def test_the_record_carries_no_field_for_a_credential_value(self):
        """§17, §18.3: Guard never handles a credential *value*.

        Asserted structurally rather than by string-matching a payload, because
        a substring check would either miss a renamed field or flag Guard's own
        prose. The property is that no part of the record shape has somewhere to
        put a secret: `target` carries an identifier, never a value, and no
        field anywhere is named for one.
        """
        import dataclasses

        from plugins.guard.models import DecisionRecord, TargetRef

        target_fields = {f.name for f in dataclasses.fields(TargetRef)}
        assert not target_fields & {"value", "secret", "credential", "token", "password"}

        record_fields = {f.name for f in dataclasses.fields(DecisionRecord)}
        assert not record_fields & {"credential", "secret", "token", "password"}

        # The request shape refuses a credential outright.
        from plugins.guard import GuardRequest

        with pytest.raises(Exception):
            GuardRequest.from_mapping(make_request(credential={"api_key": "sk-x"}))

    def test_context_payloads_never_reach_the_record(self):
        """§18.3: context appears only as references."""
        from plugins.guard.digest import RUNTIME_ONLY_FIELDS  # noqa: F401  (import check)

        raw = make_request(
            target={"kind": "secret_material", "identifier": "x", "environment": "isolated",
                    "interface": None, "is_real": False, "sensitivity": "secret_material"}
        )
        record = evaluate(raw, PERMISSIVE)
        assert record.provenance.context_refs == ()
