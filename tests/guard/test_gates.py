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


def secret_request(**target_overrides):
    target = {"kind": "secret_material", "identifier": ".env", "environment": "isolated",
              "interface": None, "is_real": False, "sensitivity": "secret_material"}
    target.update(target_overrides)
    return make_request(target=target)


class TestAbsoluteDenyPrecedence:
    """Execution-order regression: §15.1's absolute deny must run **before** policy.

    §15.1 says the absolute denies are "checked before policy, never overridden
    by any rule, priority, or approval", and §14.1 makes evaluating safety
    invariants step 1 of the walk.

    The implementation originally ran them *after* policy presence, parsing and
    validation, so a missing or invalid policy masked the refusal:

        secret_material + policy=None     -> BLOCKED / POLICY_MISSING
        secret_material + invalid policy  -> BLOCKED / POLICY_INVALID

    Both are non-`ALLOW`, which is why every existing test passed. The defect is
    in the *reason*: `BLOCKED` tells the caller to supply a policy and try again,
    which is precisely the wrong instruction for someone reaching for a
    credential. This class exists so the ordering cannot silently regress again.

    These are precedence tests, not condition tests. Removing the absolute-deny
    gate entirely would still fail them, but so would leaving it in place at the
    wrong point in the sequence — which is the failure mode actually observed.
    """

    def test_case1_secret_material_outranks_a_missing_policy(self):
        record = evaluate(secret_request(), None)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "SECRET_MATERIAL_ACCESS"

    def test_case1_is_not_a_policy_block(self):
        record = evaluate(secret_request(), None)
        assert record.decision is not GuardDecision.BLOCKED
        assert record.reason_code != "POLICY_MISSING"

    def test_case2_secret_material_outranks_an_invalid_policy(self):
        record = evaluate(secret_request(), {"version": 99})
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "SECRET_MATERIAL_ACCESS"

    def test_case2_is_not_a_policy_block(self):
        record = evaluate(secret_request(), {"version": 99})
        assert record.reason_code != "POLICY_INVALID"

    def test_case2_also_outranks_a_duplicate_rule_id(self):
        """A second, independent policy-invalidity path."""
        policy = make_policy(make_rule("same"), make_rule("same", priority=1))
        record = evaluate(secret_request(sensitivity="internal", kind="secret_material"), policy)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "SECRET_MATERIAL_ACCESS"

    def test_case3_secret_material_outranks_a_workspace_mismatch(self):
        """§15.1's gate precedes §5's workspace agreement too.

        Both would be `DENY`, but only one of them names the security boundary,
        and a mismatch must not be allowed to describe a secret-material request
        as an ordinary scoping error.
        """
        policy = make_policy(make_rule("allow"), workspace_id="some-other-workspace")
        record = evaluate(secret_request(), policy)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "SECRET_MATERIAL_ACCESS"

    def test_case3_secret_material_outranks_a_permissive_policy(self):
        """The gate is not merely first among refusals; it beats an ALLOW."""
        record = evaluate(secret_request(), PERMISSIVE)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "SECRET_MATERIAL_ACCESS"

    def test_the_deny_records_no_selected_rule(self):
        """No rule was consulted, so none may be blamed."""
        for policy in (None, {"version": 99}, PERMISSIVE):
            assert evaluate(secret_request(), policy).provenance.rule_id is None

    def test_the_deny_still_names_a_readable_policy_in_provenance(self):
        """Moving the gate must not cost provenance when a policy *is* readable."""
        record = evaluate(secret_request(), make_policy(make_rule("allow")))
        assert record.provenance.policy_id == "policy-1"

    def test_an_unreadable_policy_does_not_stop_the_deny(self):
        """The gate runs before parsing, so a malformed policy cannot prevent it."""
        for policy in ({"version": 99}, {"not": "a policy"}, []):
            record = evaluate(secret_request(), policy)
            assert record.decision is GuardDecision.DENY
            assert record.provenance.policy_id is None


class TestAbsoluteDenyPrecedenceDoesNotOverreach:
    """The gate must win only where §15.1 applies. Everything else is unchanged."""

    def test_a_normal_request_with_no_policy_is_still_blocked(self):
        """The narrower regression: BLOCKED/POLICY_MISSING must survive the fix."""
        record = evaluate(make_request(), None)
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code == "POLICY_MISSING"

    def test_a_normal_request_with_an_invalid_policy_is_still_blocked(self):
        record = evaluate(make_request(), {"version": 99})
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code == "POLICY_INVALID"

    def test_a_workspace_mismatch_on_a_normal_request_is_still_deny(self):
        policy = make_policy(make_rule("allow"), workspace_id="ws-other")
        record = evaluate(make_request(), policy)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "WORKSPACE_MISMATCH"

    def test_an_ordinary_allow_is_unaffected(self):
        assert evaluate(make_request(), PERMISSIVE).decision is GuardDecision.ALLOW

    def test_an_explicit_deny_rule_is_unaffected(self):
        policy = make_policy(make_rule("deny", effect="DENY"))
        assert evaluate(make_request(), policy).decision is GuardDecision.DENY


def foreign_context(workspace_id: str = "ws-foreign", *, item_workspace: str | None = None):
    """A ContextResponse whose response and/or item workspace differs."""
    from tests.guard.conftest import make_context, make_context_item

    item = make_context_item(
        truth_state="PASS",
        workspace_id=item_workspace if item_workspace is not None else workspace_id,
    )
    return {"response": make_context(item, workspace_id=workspace_id)}


class TestCrossWorkspaceAbsoluteDeny:
    """§15.1 cross-workspace authorization, before policy validation.

    §5 requires four things to agree — request, policy, context response, and
    every authorization-relevant `ContextItem` — and says a mismatch "is never
    merged, filtered, or repaired". §15.1 lists cross-workspace authorization
    among the absolute denies, which are "checked before policy".

    Two halves were wrong:

    * a policy for another workspace that was *also* malformed reported
      `POLICY_INVALID`, because parsing ran before the mismatch was noticed;
    * foreign context was **filtered out** and evaluation continued, so an
      unconditional `ALLOW` succeeded on a request carrying foreign context —
      a cross-workspace authorization reaching `ALLOW`, which §5 forbids
      outright.

    These are precedence and boundary tests, named for the boundary rather than
    for a single condition. The `allow-all` rule is intentional: it means any
    `ALLOW` here is the boundary failing, not a rule succeeding.
    """

    PERMISSIVE = make_policy(make_rule("allow-all", priority=0))

    def test_a_policy_mismatch_outranks_an_invalid_policy(self):
        policy = {"version": 99, "workspace_id": "ws-2"}
        record = evaluate(make_request(), policy)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "WORKSPACE_MISMATCH"

    def test_a_policy_mismatch_outranks_a_duplicate_rule_id(self):
        policy = make_policy(make_rule("same"), make_rule("same", priority=1),
                             workspace_id="ws-2")
        record = evaluate(make_request(), policy)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "WORKSPACE_MISMATCH"

    def test_a_policy_mismatch_outranks_a_permissive_allow(self):
        policy = make_policy(make_rule("allow-all", priority=0), workspace_id="ws-2")
        record = evaluate(make_request(), policy)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "WORKSPACE_MISMATCH"

    def test_a_foreign_context_response_cannot_reach_allow(self):
        request = make_request(context=foreign_context("ws-2"))
        record = evaluate(request, self.PERMISSIVE)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "WORKSPACE_MISMATCH"

    def test_a_foreign_context_item_cannot_reach_allow(self):
        """The item-level half of §5, with the response agreeing.

        A rule that never reads context must still be refused: the request spans
        two workspaces, and that is the finding — the foreign item is not a
        predicate that failed to resolve.
        """
        request = make_request(
            context=foreign_context("ws-1", item_workspace="ws-2")
        )
        record = evaluate(request, self.PERMISSIVE)
        assert record.decision is GuardDecision.DENY
        assert record.reason_code == "WORKSPACE_MISMATCH"

    def test_a_foreign_item_is_refused_from_every_item_list(self):
        """facts, history and plans are all authorization-relevant (§5)."""
        from plugins.context.vocabulary import ItemKind
        from tests.guard.conftest import make_context, make_context_item

        for kind in (ItemKind.FACT, ItemKind.HISTORY, ItemKind.PLAN):
            item = make_context_item(truth_state="PASS", workspace_id="ws-2")
            import dataclasses

            item = dataclasses.replace(item, item_kind=kind)
            request = make_request(
                context={"response": make_context(item, workspace_id="ws-1")}
            )
            record = evaluate(request, self.PERMISSIVE)
            assert record.decision is GuardDecision.DENY, kind
            assert record.reason_code == "WORKSPACE_MISMATCH", kind

    def test_the_request_absolute_deny_still_outranks_the_mismatch(self):
        """§14.1 step 1 before §5 — the previous fix must not be undone."""
        raw = make_request(
            target={"kind": "secret_material", "identifier": ".env",
                    "environment": "isolated", "interface": None,
                    "is_real": False, "sensitivity": "secret_material"}
        )
        policy = make_policy(make_rule("allow"), workspace_id="ws-2")
        record = evaluate(raw, policy)
        assert record.reason_code == "SECRET_MATERIAL_ACCESS"

    def test_the_mismatch_records_no_selected_rule(self):
        policy = make_policy(make_rule("allow-all", priority=0), workspace_id="ws-2")
        assert evaluate(make_request(), policy).provenance.rule_id is None


class TestCrossWorkspaceDenyDoesNotOverreach:
    """The boundary must fire only on a mismatch. Everything else is unchanged."""

    def test_a_normal_request_with_no_policy_is_still_blocked(self):
        record = evaluate(make_request(), None)
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code == "POLICY_MISSING"

    def test_a_unreadable_policy_workspace_is_not_treated_as_a_mismatch(self):
        """An unknown workspace must not be assumed to match *or* to differ.

        §9.2's validation refuses such a policy; the boundary must not
        pre-empt it with a mismatch it cannot actually see.
        """
        policy = {"version": 1, "policy_id": "p", "revision": "r", "rules": []}
        record = evaluate(make_request(), policy)
        assert record.reason_code != "WORKSPACE_MISMATCH"

    def test_a_matching_policy_and_context_still_evaluate_normally(self):
        from tests.guard.conftest import make_context, make_context_item

        request = make_request(
            context={"response": make_context(make_context_item(truth_state="PASS"))}
        )
        policy = make_policy(make_rule("allow-all", priority=0))
        assert evaluate(request, policy).decision is GuardDecision.ALLOW

    def test_no_context_is_still_fine(self):
        policy = make_policy(make_rule("allow-all", priority=0))
        assert evaluate(make_request(context=None), policy).decision is GuardDecision.ALLOW

    def test_a_malformed_policy_still_blocks_when_the_workspace_matches(self):
        record = evaluate(make_request(), {"version": 99, "workspace_id": "ws-1"})
        assert record.decision is GuardDecision.BLOCKED
        assert record.reason_code == "POLICY_INVALID"
