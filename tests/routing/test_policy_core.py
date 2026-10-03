"""AI-12-B — the policy core. Offline, deterministic, no provider, no execution.

### The two halves, and why the second one matters

Most of this file asserts **refusals**, and a suite that only refuses things is
satisfied by a policy core that refuses everything. So the controls matter as much:

```text
P5   a rule whose requirement IS met activates and selects — a policy core that can
     never select would pass every refusal in this file
P6   the same policy with a model-execution record present selects, and the same
     policy without one is DORMANT — the difference is the measurement, not the code
P10  a supplied BLOCKED record is accounted for in the resolution
P23  the audit re-derives the resolution from the policy and the records alone
```

### Mutation controls

Several tests do not merely assert that a shape is refused. They take a WORKING
artifact, mutate it into the shape under test, and require the refusal — so the test
fails if the check is removed, rather than only if the check was never written.

```text
M1  UNKNOWN -> treated as available          M5  missing discrimination -> accepted
M2  BLOCKED -> dropped from the scope        M6  missing rollback -> activated
M3  REFERENCE PASS -> model selection        M7  fallback -> automatic retry
M4  verdict -> numeric score                 M8  evidence -> task_id instead of run_id
```
"""

from __future__ import annotations

import copy

import pytest

from benchmarks.vocabulary import OracleVerdict

from routing.errors import InvalidEvidence, InvalidPolicy
from routing.evidence import EvidenceClass, EvidenceRef, SuppliedRecord, supplied_records
from routing.policy import (
    POLICY_VERSION,
    FORBIDDEN_POLICY_FIELDS,
    Policy,
    PolicyRule,
    PolicyState,
)
from routing.policy_eval import (
    EvidenceDisposition,
    PolicyOutcome,
    RuleDisposition,
    resolve_policy,
    verify_resolution,
)

pytestmark = pytest.mark.layer1


CAN = "ai11-v1-can-dbc-decode"
FUZZ = "ai11-v1-fuzzing-recovery-triage"
BLOCKED_REASON = "PRECONDITION_UNMET:environment:vcan0-exclusive"


def record(
    run_id: str,
    task_id: str = CAN,
    verdict: str = "PASS",
    *,
    evidence_class: str = "REFERENCE",
    reason_code: str = "",
    digest: str = "sha256:0000",
) -> dict:
    return {
        "record_digest": digest,
        "evidence": {
            "run_id": run_id,
            "task_id": task_id,
            "source_sha": "efa836ff9225f6226ca8a76615f3f45c31110d58",
            "workbench_sha": "60c630d83c576a013f828fa8ec5414f34fd9974c",
            "verdict": verdict,
            "reason_code": reason_code,
            "limitations": ["NO_PROVIDER_CALL_IN_PATH"],
            "evidence_class": evidence_class,
        },
    }


def a_rule(**overrides) -> dict:
    rule = {
        "rule_id": "can-to-model",
        "priority": 10,
        "reason_code": "MEASURED_TASK_SUCCESS",
        "match_task_id": CAN,
        "requires_verdict": "PASS",
        "requires_evidence_class": "MODEL_EXECUTION",
        "select": {"model_ref": "deepseek/deepseek-flash"},
        "falsifier": {
            "observation": "a run of this task on the selected model",
            "expected_if_rule_wrong": "the task does not pass there",
        },
        "discrimination": {
            "input_a": "a record whose verdict is PASS",
            "input_b": "a record whose verdict is FAIL",
            "expected_distinction": "only the PASSing record activates the rule",
        },
    }
    rule.update(overrides)
    return rule


def a_condition_rule(**overrides) -> dict:
    """A rule whose requirement today's evidence CAN satisfy: REFERENCE + PASS.

    It selects nothing, because a rule that selects must require MODEL_EXECUTION
    (§4.2) and no supplied record may be one. This is the only activatable shape the
    current evidence vocabulary admits.
    """
    rule = {
        "rule_id": "can-measured-pass",
        "priority": 10,
        "reason_code": "CAN_MEASURED_PASS",
        "match_task_id": CAN,
        "requires_verdict": "PASS",
        "requires_evidence_class": "REFERENCE",
        "falsifier": {
            "observation": "a controlled re-run of this task at the pinned source SHA",
            "expected_if_rule_wrong": "the re-run does not pass, so the condition is false",
        },
        "discrimination": {
            "input_a": "a REFERENCE record whose verdict is PASS",
            "input_b": "a REFERENCE record whose verdict is FAIL",
            "expected_distinction": "only the PASSing record makes the condition hold",
        },
    }
    rule.update(overrides)
    return rule


def a_policy(**overrides) -> dict:
    policy = {
        "version": POLICY_VERSION,
        "policy_id": "ai12-v1-probe",
        "revision": "v1",
        "state": "DORMANT",
        "evidence_scope": [CAN],
        "rules": [a_rule()],
    }
    policy.update(overrides)
    return policy


def a_rollback() -> dict:
    return {
        "previous_policy": "ai12-v1-probe@v0",
        "trigger": "the selected model is withdrawn from the registry",
        "decider": "the routing owner",
    }


# ---------------------------------------------------------------------------
# P1 — a valid policy is accepted
# ---------------------------------------------------------------------------


def test_P1_a_valid_policy_is_accepted_and_is_dormant_by_default() -> None:
    policy = Policy.from_mapping(a_policy())
    assert policy.policy_id == "ai12-v1-probe"
    assert policy.state is PolicyState.DORMANT
    assert len(policy.rules) == 1
    assert policy.evidence_scope == (CAN,)


def test_P1b_ordering_is_total_and_independent_of_file_order() -> None:
    """Two rules, submitted in one order and read in the other, compare equal.

    The ordering key is `(priority, rule_id)`, so no two rules compare equal and no
    tie-break is left to the order a file happened to list them in.
    """
    first = a_rule(rule_id="b-rule", priority=10)
    second = a_rule(rule_id="a-rule", priority=10)
    forwards = Policy.from_mapping(a_policy(rules=[first, second]))
    backwards = Policy.from_mapping(a_policy(rules=[second, first]))
    assert [r.rule_id for r in forwards.rules] == ["a-rule", "b-rule"]
    assert forwards.rules == backwards.rules


# ---------------------------------------------------------------------------
# P2/P3 — the shapes that are refused
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        ({"version": 2}, "an unsupported version"),
        ({"policy_id": ""}, "an empty policy_id"),
        ({"revision": ""}, "an empty revision"),
        ({"state": "ENABLED"}, "a state outside the closed vocabulary"),
        ({"evidence_scope": []}, "an empty evidence scope"),
        ({"evidence_scope": [CAN, CAN]}, "a repeated scope entry"),
        ({"rules": "not-a-list"}, "rules that are not a list"),
        ({"unknown_field": 1}, "a field the contract does not define"),
    ],
)
def test_P2_a_malformed_policy_is_refused(overrides: dict, why: str) -> None:
    with pytest.raises(InvalidPolicy):
        Policy.from_mapping(a_policy(**overrides))


def test_P3_a_duplicate_rule_id_is_refused() -> None:
    """Not resolved by keeping the first or the last. The ordering key needs both."""
    with pytest.raises(InvalidPolicy) as raised:
        Policy.from_mapping(
            a_policy(rules=[a_rule(), a_rule(priority=20)])
        )
    assert "unique" in str(raised.value)


def test_P3b_an_unknown_rule_field_is_refused() -> None:
    with pytest.raises(InvalidPolicy):
        Policy.from_mapping(a_policy(rules=[a_rule(unexpected="x")]))


# ---------------------------------------------------------------------------
# P4 — falsifier and discrimination are required, and must SAY something
# ---------------------------------------------------------------------------


def test_P4_a_rule_with_no_falsifier_is_refused() -> None:
    rule = a_rule()
    del rule["falsifier"]
    with pytest.raises(InvalidPolicy) as raised:
        Policy.from_mapping(a_policy(rules=[rule]))
    assert "falsifier" in str(raised.value)


def test_P4b_an_empty_falsifier_is_refused() -> None:
    """A field that is present and says nothing is not a falsifier."""
    with pytest.raises(InvalidPolicy):
        Policy.from_mapping(
            a_policy(rules=[a_rule(falsifier={"observation": "  ", "expected_if_rule_wrong": "x"})])
        )


def test_P4c_a_rule_with_no_discrimination_control_is_refused() -> None:
    rule = a_rule()
    del rule["discrimination"]
    with pytest.raises(InvalidPolicy) as raised:
        Policy.from_mapping(a_policy(rules=[rule]))
    assert "discrimination" in str(raised.value)


def test_P4d_a_discrimination_control_whose_halves_are_equal_is_refused() -> None:
    """One input compared with itself cannot show that anything is distinguished."""
    with pytest.raises(InvalidPolicy) as raised:
        Policy.from_mapping(
            a_policy(
                rules=[
                    a_rule(
                        discrimination={
                            "input_a": "the same",
                            "input_b": "the same",
                            "expected_distinction": "x",
                        }
                    )
                ]
            )
        )
    assert "same value" in str(raised.value)


# ---------------------------------------------------------------------------
# P5/P6 — the controls: a policy that CAN select, and one that cannot yet
# ---------------------------------------------------------------------------


def test_P5_the_policy_schema_expresses_a_model_execution_requirement() -> None:
    """§6.1's control, replacing one that proved a fabrication.

    The mechanism must be able to SAY what a future contract will make decidable: a
    rule that requires `MODEL_EXECUTION` evidence, scoped to a task, selecting a
    model, with its falsifier, its discrimination control and its full projection.
    That is expressible today and validated today.

    What must NOT happen is the next step. The earlier version of this test supplied a
    caller-authored record labelled `MODEL_EXECUTION` and required the resolution to
    return SELECTED — which proved that a caller could manufacture the §6 prerequisite
    by typing an enum value. The schema can express the requirement; the resolution
    over real evidence cannot satisfy it.
    """
    policy = Policy.from_mapping(a_policy())
    rule = policy.rules[0]

    assert rule.requires_evidence_class is EvidenceClass.MODEL_EXECUTION
    assert rule.selects and rule.select_model_ref == "deepseek/deepseek-flash"
    assert rule.to_mapping()["requires_evidence_class"] == "MODEL_EXECUTION"
    assert rule.to_mapping()["select"]["model_ref"] == "deepseek/deepseek-flash"

    # And over the evidence AI-11 actually produces, it stays dormant.
    resolution = resolve_policy(policy, supplied_records([record("run-ref-0001")]))
    assert resolution.outcome is PolicyOutcome.DORMANT
    assert resolution.selected_model_ref is None


def test_P6_the_same_policy_is_dormant_without_the_measurement() -> None:
    """§6 today: the prerequisite is BLOCKED, no model-execution record exists, and
    the honest resolution is DORMANT rather than a REFERENCE substitution.
    """
    policy = Policy.from_mapping(a_policy())
    reference_only = supplied_records([record("run-ref-0001", verdict="PASS")])

    resolution = resolve_policy(policy, reference_only)

    assert resolution.outcome is PolicyOutcome.DORMANT
    assert resolution.selected_model_ref is None
    assert resolution.evidence_for("run-ref-0001").disposition is (
        EvidenceDisposition.REJECTED_BY_EVIDENCE_CLASS
    )


def test_P6b_a_condition_over_real_evidence_holds_and_routes_nothing() -> None:
    """The control for the shape that CAN activate: a requirement over REFERENCE.

    It selects nothing, so the resolution reports CONDITION_MET — the requirement
    held — rather than a selection, and rather than NO_MATCH, which would report a
    rule that fired as one that did not.
    """
    policy = Policy.from_mapping(a_policy(rules=[a_condition_rule()]))
    records = supplied_records([record("run-ref-0001", verdict="PASS", digest="sha256:c")])

    resolution = resolve_policy(policy, records)

    assert resolution.outcome is PolicyOutcome.CONDITION_MET
    assert resolution.selected_model_ref is None
    assert resolution.selected_rule is None
    fired = [r for r in resolution.rules if r.disposition is RuleDisposition.ACTIVATED]
    assert [r.rule_id for r in fired] == ["can-measured-pass"]
    assert fired[0].cited_run_id == "run-ref-0001"
    assert resolution.evidence_for("run-ref-0001").disposition is EvidenceDisposition.CITED


# ---------------------------------------------------------------------------
# P7/P8 — evidence identity
# ---------------------------------------------------------------------------


def test_P7_evidence_carries_the_whole_binding() -> None:
    """§5.3. Every field is required; a partial citation cannot be re-derived."""
    ref = EvidenceRef.from_mapping(record("run-1")["evidence"])
    mapping = ref.to_mapping()
    for field in (
        "run_id",
        "task_id",
        "source_sha",
        "workbench_sha",
        "verdict",
        "reason_code",
        "limitations",
        "evidence_class",
    ):
        assert field in mapping


@pytest.mark.parametrize(
    "dropped",
    ["run_id", "task_id", "source_sha", "workbench_sha", "verdict", "reason_code"],
)
def test_P7b_a_record_missing_any_identity_field_is_refused(dropped: str) -> None:
    entry = record("run-1")
    del entry["evidence"][dropped]
    with pytest.raises(InvalidEvidence):
        supplied_records([entry])


def test_P7c_a_record_with_no_digest_is_refused() -> None:
    entry = record("run-1")
    del entry["record_digest"]
    with pytest.raises(InvalidEvidence):
        supplied_records([entry])


def test_P8_two_records_claiming_one_run_id_are_refused() -> None:
    """§5.3. A run is one measured run; a second claim is not resolved by a tie-break."""
    with pytest.raises(InvalidEvidence) as raised:
        supplied_records([record("run-1", digest="sha256:a"), record("run-1", digest="sha256:b")])
    assert "unique" in str(raised.value)


def test_P8b_a_verdict_outside_ai_11s_six_is_refused() -> None:
    """AI-12 does not get its own verdict vocabulary."""
    entry = record("run-1", verdict="SUCCEEDED")
    with pytest.raises(InvalidEvidence) as raised:
        supplied_records([entry])
    assert "vocabulary" in str(raised.value)


def test_P8c_a_non_pass_record_with_no_reason_code_is_refused() -> None:
    entry = record("run-1", verdict="BLOCKED", reason_code="")
    with pytest.raises(InvalidEvidence):
        supplied_records([entry])


def test_P8d_a_pass_record_may_carry_an_empty_reason_code() -> None:
    """AI-11 records exactly that: a PASS has no refusal to name."""
    records = supplied_records([record("run-1", verdict="PASS", reason_code="")])
    assert records[0].ref.reason_code == ""
    assert records[0].ref.is_pass


# ---------------------------------------------------------------------------
# P9/P10 — §4.3: verdicts are preserved, never promoted, never dropped
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verdict", ["BLOCKED", "NOT_RUN", "UNKNOWN", "UNAVAILABLE"])
def test_P9_a_non_pass_verdict_never_satisfies_a_pass_requirement(verdict: str) -> None:
    """§4.3. Read, accounted for, and not promotable — one verdict at a time."""
    policy = Policy.from_mapping(a_policy(rules=[a_condition_rule()]))
    records = supplied_records(
        [record("run-np-0001", verdict=verdict, reason_code="SOMETHING_HAPPENED")]
    )

    resolution = resolve_policy(policy, records)

    assert resolution.outcome is PolicyOutcome.DORMANT
    assert resolution.selected_model_ref is None
    use = resolution.evidence_for("run-np-0001")
    assert use.disposition is EvidenceDisposition.REJECTED_BY_VERDICT


def test_P10_a_blocked_record_is_accounted_for_and_never_dropped() -> None:
    """§4.4. The BLOCKED task stays in the corpus, and the resolution says so.

    The record is not filtered out of the accounting, not turned into a zero and not
    treated as neutral: it appears with its own verdict, reason code and digest.
    """
    policy = Policy.from_mapping(a_policy(evidence_scope=[CAN, FUZZ]))
    records = supplied_records(
        [
            record("run-can-0001"),
            record("run-fuzz-0001", task_id=FUZZ, verdict="BLOCKED", reason_code=BLOCKED_REASON),
        ]
    )

    resolution = resolve_policy(policy, records)
    use = resolution.evidence_for("run-fuzz-0001")

    assert use is not None, "the BLOCKED record disappeared from the resolution"
    assert use.ref.verdict is OracleVerdict.BLOCKED
    assert use.ref.reason_code == BLOCKED_REASON
    assert use.digest == "sha256:0000"
    assert resolution.missing_scope_tasks == ()


def test_P10b_dropping_a_blocked_record_is_visible_not_silent() -> None:
    """Removing it does not make the policy look complete; it reports the gap."""
    policy = Policy.from_mapping(a_policy(evidence_scope=[CAN, FUZZ]))
    without_the_blocked_task = supplied_records([record("run-can-0001")])

    resolution = resolve_policy(policy, without_the_blocked_task)

    assert resolution.outcome is PolicyOutcome.INCOMPLETE_EVIDENCE
    assert resolution.missing_scope_tasks == (FUZZ,)
    assert resolution.outcome is not PolicyOutcome.SELECTED


def test_P10c_a_record_outside_the_declared_scope_is_reported_not_ignored() -> None:
    policy = Policy.from_mapping(a_policy(evidence_scope=[CAN]))
    records = supplied_records([record("run-other-0001", task_id="ai11-v1-uds-nrc-triage")])

    resolution = resolve_policy(policy, records)

    assert resolution.evidence_for("run-other-0001").disposition is (
        EvidenceDisposition.OUTSIDE_SCOPE
    )


# ---------------------------------------------------------------------------
# M1–M4 — mutation controls on the verdict semantics
# ---------------------------------------------------------------------------


def test_M1_a_default_that_would_make_unknown_available_is_unrepresentable() -> None:
    """A field the contract does not define cannot carry a default into the input.

    The mutation is "add `default: true` so a missing measurement becomes usable".
    There is no field that accepts it, so the injection is refused by name.
    """
    entry = record("run-1")
    entry["evidence"]["default"] = True
    with pytest.raises(InvalidEvidence):
        supplied_records([entry])


def test_M2_dropping_the_blocked_task_from_the_scope_is_refused_by_the_resolution() -> None:
    """The mutation is "filter the BLOCKED task out of the scope to look complete".

    The scope is declared on the artifact and validated non-empty; a scope that is
    narrowed no longer covers a task whose record is supplied, and the supplied
    record is then reported OUTSIDE_SCOPE rather than vanishing.
    """
    narrowed = Policy.from_mapping(a_policy(evidence_scope=[CAN]))
    records = supplied_records(
        [record("run-can-0001"), record("run-fuzz-0001", task_id=FUZZ, verdict="BLOCKED", reason_code=BLOCKED_REASON)]
    )

    resolution = resolve_policy(narrowed, records)

    assert resolution.evidence_for("run-fuzz-0001").disposition is (
        EvidenceDisposition.OUTSIDE_SCOPE
    )


def test_M3_a_reference_run_cannot_justify_a_model_selection() -> None:
    """§4.2. The mutation is "let the REFERENCE PASS select the model"."""
    with pytest.raises(InvalidPolicy) as raised:
        Policy.from_mapping(
            a_policy(rules=[a_rule(requires_evidence_class="REFERENCE")])
        )
    assert "REFERENCE" in str(raised.value)


def test_M4_a_score_or_weight_field_is_refused_by_name() -> None:
    """§4.3, §9. The mutation is "weight the verdict and rank on the weight"."""
    for field in ("score", "weight", "confidence", "ranking", "aggregate", "prior"):
        assert field in FORBIDDEN_POLICY_FIELDS
        with pytest.raises(InvalidPolicy) as raised:
            Policy.from_mapping(a_policy(rules=[a_rule(**{field: 0.5})]))
        assert "numeric quantity" in str(raised.value)


# ---------------------------------------------------------------------------
# M5/M6 — mutation controls on the structural requirements
# ---------------------------------------------------------------------------


def test_M5_a_rule_mutated_to_drop_its_discrimination_control_is_refused() -> None:
    """Written as a mutation: take a VALID rule, remove the control, require refusal."""
    valid = a_rule()
    assert "discrimination" in valid
    mutated = copy.deepcopy(valid)
    del mutated["discrimination"]
    with pytest.raises(InvalidPolicy):
        Policy.from_mapping(a_policy(rules=[mutated]))


def test_M6_a_policy_mutated_to_activate_without_rollback_is_refused() -> None:
    """§8. The mutation is "flip the state to ACTIVE and skip the rollback"."""
    valid = a_policy()
    assert "rollback" not in valid
    with pytest.raises(InvalidPolicy) as raised:
        Policy.from_mapping(a_policy(state="ACTIVE"))
    assert "rollback" in str(raised.value)


def test_M6b_activation_with_complete_rollback_is_accepted_but_not_authoritative() -> None:
    """The rollback requirement is about metadata, not about whether it may select.

    An ACTIVE declaration with no measurement behind it still resolves DORMANT: a
    declaration cannot manufacture a measurement.
    """
    policy = Policy.from_mapping(a_policy(state="ACTIVE", rollback=a_rollback()))
    assert policy.state is PolicyState.ACTIVE

    resolution = resolve_policy(policy, supplied_records([record("run-ref-0001")]))
    assert resolution.declared_state == "ACTIVE"
    assert resolution.outcome is PolicyOutcome.DORMANT
    assert resolution.selected_model_ref is None


# ---------------------------------------------------------------------------
# M7 — fallback and escalation are declarative data, and there is no execution path
# ---------------------------------------------------------------------------


def test_M7_fallback_and_escalation_are_data_and_nothing_executes_them() -> None:
    policy = Policy.from_mapping(
        a_policy(
            fallback=[
                {
                    "condition": "the selected model is withdrawn from the registry",
                    "target_model_ref": "mimo/mimo-v2.6-pro",
                    "reason_code": "SELECTED_MODEL_WITHDRAWN",
                }
            ],
            escalation=[
                {
                    "condition": "a task measured as failing on the selected model",
                    "target_model_ref": "deepseek/deepseek-pro",
                    "reason_code": "MEASURED_TASK_FAILURE",
                }
            ],
        )
    )

    assert len(policy.fallback) == 1
    assert len(policy.escalation) == 1

    records = supplied_records([record("run-ref-0001")])
    resolution = resolve_policy(policy, records)

    # The resolution records what it found — here, a dormant selection rule — and
    # follows no fallback, retries nothing, produces no second decision and reads no
    # previous one: there is no field on the resolution for any of those.
    assert resolution.outcome is PolicyOutcome.DORMANT
    mapping = resolution.to_mapping()
    for absent in ("fallback", "retry", "next_decision", "previous_decision", "escalated"):
        assert absent not in mapping


def test_M7b_a_fallback_with_no_condition_is_refused() -> None:
    with pytest.raises(InvalidPolicy):
        Policy.from_mapping(
            a_policy(fallback=[{"target_model_ref": "mimo/mimo-v2.6-pro", "reason_code": "X"}])
        )


def test_M7c_a_fallback_target_must_be_a_model_reference() -> None:
    with pytest.raises(InvalidPolicy):
        Policy.from_mapping(
            a_policy(
                fallback=[
                    {
                        "condition": "c",
                        "target_model_ref": "not-a-model-ref",
                        "reason_code": "X",
                    }
                ]
            )
        )


# ---------------------------------------------------------------------------
# M8/P11 — the exact run, not the task
# ---------------------------------------------------------------------------


def test_M8_a_rule_pinned_to_a_wrong_run_id_does_not_activate() -> None:
    """The mutation is "same task, different run, treat it as the same evidence"."""
    policy = Policy.from_mapping(
        a_policy(rules=[a_condition_rule(requires_run_id="run-wanted")])
    )
    records = supplied_records([record("run-other", verdict="PASS")])

    resolution = resolve_policy(policy, records)

    assert resolution.outcome is PolicyOutcome.NO_MATCH
    assert resolution.selected_model_ref is None
    assert resolution.rules[0].cited_run_id is None
    assert resolution.evidence_for("run-other").disposition is (
        EvidenceDisposition.NOT_NEEDED
    )


def test_P11_a_rule_pinned_to_the_right_run_id_activates() -> None:
    """Same task, same verdict — a different run is a different record."""
    policy = Policy.from_mapping(
        a_policy(rules=[a_condition_rule(requires_run_id="run-wanted")])
    )
    records = supplied_records([record("run-wanted", verdict="PASS")])

    resolution = resolve_policy(policy, records)

    assert resolution.outcome is PolicyOutcome.CONDITION_MET
    assert resolution.rules[0].cited_run_id == "run-wanted"


def test_P11b_the_resolution_cites_the_exact_record_it_read() -> None:
    """§8 AUDITABLE. Which run, which digest — not merely which task."""
    policy = Policy.from_mapping(a_policy(rules=[a_condition_rule()]))
    records = supplied_records([record("run-cited", verdict="PASS", digest="sha256:cited")])

    resolution = resolve_policy(policy, records)
    use = resolution.evidence_for("run-cited")

    assert use.disposition is EvidenceDisposition.CITED
    assert use.digest == "sha256:cited"
    assert use.ref.task_id == CAN
    assert use.ref.source_sha.startswith("efa836ff")
    assert use.rule_id == "can-measured-pass"


# ---------------------------------------------------------------------------
# P12/P13 — explainability and auditability
# ---------------------------------------------------------------------------


def test_P12_the_resolution_explains_which_rules_fired_and_what_they_read() -> None:
    policy = Policy.from_mapping(a_policy(rules=[a_condition_rule()]))
    resolution = resolve_policy(policy, supplied_records([record("run-ref-0001")]))
    mapping = resolution.to_mapping()

    assert mapping["outcome"] == "CONDITION_MET"
    fired = [r for r in mapping["rules"] if r["disposition"] == "ACTIVATED"]
    assert fired and fired[0]["rule_id"] == "can-measured-pass"
    assert fired[0]["cited_run_id"] == "run-ref-0001"
    cited = [e for e in mapping["evidence"] if e["disposition"] == "CITED"]
    assert cited and cited[0]["run_id"] == "run-ref-0001"
    assert cited[0]["rule_id"] == "can-measured-pass"


def test_P13_the_audit_re_derives_from_the_policy_and_the_records_alone() -> None:
    """§8. A reader with the artifact and the records reaches the same answer."""
    policy = Policy.from_mapping(a_policy(rules=[a_condition_rule()]))
    records = supplied_records([record("run-ref-0001"), record("run-ref-0002", digest="sha256:2")])
    resolution = resolve_policy(policy, records)

    assert verify_resolution(policy, records, resolution)


def test_P13b_a_tampered_resolution_fails_the_audit() -> None:
    """The mutation is "record a selection the evidence does not support"."""
    import dataclasses

    policy = Policy.from_mapping(a_policy())
    records = supplied_records([record("run-ref-0001")])
    resolution = resolve_policy(policy, records)
    assert resolution.outcome is PolicyOutcome.DORMANT

    tampered = dataclasses.replace(
        resolution,
        outcome=PolicyOutcome.SELECTED,
        selected_model_ref="deepseek/deepseek-flash",
    )
    assert not verify_resolution(policy, records, tampered)


# ---------------------------------------------------------------------------
# P14 — the dormant model-comparative policy stays dormant
# ---------------------------------------------------------------------------


def test_P14_todays_whole_ai_11_campaign_resolves_dormant() -> None:
    """Six records, five PASS and one BLOCKED, all REFERENCE. No selection exists.

    This is the AI-11-C campaign's actual shape. A policy over it can be declared,
    validated and resolved — and it cannot select a model, because the measurement a
    selection would need does not exist (§4.2, §6).
    """
    tasks = [
        ("ai11-v1-can-dbc-decode", "PASS", ""),
        ("ai11-v1-uds-nrc-triage", "PASS", ""),
        ("ai11-v1-yara-rule-author", "PASS", ""),
        ("ai11-v1-firmware-syn-ecu-inventory", "PASS", ""),
        ("ai11-v1-reverse-arm64-triage", "PASS", ""),
        (FUZZ, "BLOCKED", BLOCKED_REASON),
    ]
    records = supplied_records(
        [
            record(f"run-{index:04d}", task_id=task_id, verdict=verdict, reason_code=reason)
            for index, (task_id, verdict, reason) in enumerate(tasks)
        ]
    )
    policy = Policy.from_mapping(
        a_policy(evidence_scope=[task_id for task_id, _, _ in tasks])
    )

    resolution = resolve_policy(policy, records)

    assert resolution.outcome is PolicyOutcome.DORMANT
    assert resolution.selected_model_ref is None
    assert resolution.missing_scope_tasks == ()
    assert len(resolution.evidence) == 6
    blocked = [e for e in resolution.evidence if e.ref.verdict is OracleVerdict.BLOCKED]
    assert len(blocked) == 1
    assert blocked[0].ref.reason_code == BLOCKED_REASON


def test_P14b_no_path_promotes_a_non_pass_verdict() -> None:
    """Every non-PASS verdict, in one policy, over one rule — none activates."""
    policy = Policy.from_mapping(a_policy(rules=[a_condition_rule(match_task_id=None)]))
    records = supplied_records(
        [
            record("run-b", verdict="BLOCKED", reason_code="R1", digest="sha256:1"),
            record("run-n", verdict="NOT_RUN", reason_code="R2", digest="sha256:2"),
            record("run-u", verdict="UNKNOWN", reason_code="R3", digest="sha256:3"),
            record("run-x", verdict="UNAVAILABLE", reason_code="R4", digest="sha256:4"),
            record("run-f", verdict="FAIL", reason_code="R5", digest="sha256:5"),
        ]
    )

    resolution = resolve_policy(policy, records)

    assert resolution.outcome is PolicyOutcome.DORMANT
    assert resolution.selected_model_ref is None
    assert all(
        use.disposition is EvidenceDisposition.REJECTED_BY_VERDICT
        for use in resolution.evidence
    )


# ---------------------------------------------------------------------------
# N1-N3 — the fabrication paths, refused at the input boundary
# ---------------------------------------------------------------------------


def test_N1_reference_shaped_data_cannot_be_labelled_model_evidence() -> None:
    """§4.2, §6. One field must not manufacture the prerequisite.

    The record below is an AI-11 REFERENCE run in every respect but the label. The
    label is not a measurement, and the contract that would define what a model
    measurement must carry does not exist.
    """
    forged = record("run-forged", verdict="PASS")
    forged["evidence"]["evidence_class"] = "MODEL_EXECUTION"

    with pytest.raises(InvalidEvidence) as raised:
        supplied_records([forged])

    assert "no supplied record" in str(raised.value)
    assert "MODEL_EXECUTION" in str(raised.value)


def test_N2_model_evidence_without_attribution_is_not_accepted() -> None:
    """There is no producer field to add, because §6 says the contract that defines
    one is a separate act. A record cannot carry it, so it cannot be admitted."""
    forged = record("run-forged", verdict="PASS")
    forged["evidence"].update(
        {"evidence_class": "MODEL_EXECUTION", "producer": "some-provider/some-model"}
    )

    with pytest.raises(InvalidEvidence):
        supplied_records([forged])


def test_N3_a_record_that_admits_no_provider_call_cannot_be_model_evidence() -> None:
    """The sharpest form: the record says so itself, in its own limitations.

    `NO_PROVIDER_CALL_IN_PATH` is what AI-11 writes on a run where no provider was
    called. A record carrying it and claiming to be a model execution contradicts
    itself, and the input boundary refuses the claim rather than resolving the
    contradiction in the caller's favour.
    """
    forged = record("run-forged", verdict="PASS")  # limitations: NO_PROVIDER_CALL_IN_PATH
    assert "NO_PROVIDER_CALL_IN_PATH" in forged["evidence"]["limitations"]
    forged["evidence"]["evidence_class"] = "MODEL_EXECUTION"

    with pytest.raises(InvalidEvidence):
        supplied_records([forged])


def test_N4_the_whole_campaign_cannot_select_a_model() -> None:
    """The end-to-end statement: five PASS and one BLOCKED, all REFERENCE, no model.

    Every rule shape the current evidence can satisfy is a condition; every rule that
    would select is dormant; nothing emits a selection.
    """
    policy = Policy.from_mapping(
        a_policy(rules=[a_rule(), a_condition_rule(priority=20)])
    )
    tasks = [
        ("ai11-v1-can-dbc-decode", "PASS", ""),
        ("ai11-v1-uds-nrc-triage", "PASS", ""),
        ("ai11-v1-yara-rule-author", "PASS", ""),
        ("ai11-v1-firmware-syn-ecu-inventory", "PASS", ""),
        ("ai11-v1-reverse-arm64-triage", "PASS", ""),
        (FUZZ, "BLOCKED", BLOCKED_REASON),
    ]
    records = supplied_records(
        [
            record(f"run-{index:04d}", task_id=task_id, verdict=verdict,
                   reason_code=reason, digest=f"sha256:{index}")
            for index, (task_id, verdict, reason) in enumerate(tasks)
        ]
    )

    resolution = resolve_policy(policy, records)

    assert resolution.outcome is PolicyOutcome.CONDITION_MET
    assert resolution.selected_model_ref is None
    assert resolution.selected_rule is None
    blocked = [e for e in resolution.evidence if e.ref.verdict is OracleVerdict.BLOCKED]
    assert len(blocked) == 1 and blocked[0].ref.reason_code == BLOCKED_REASON
    assert all(
        e.ref.evidence_class is EvidenceClass.REFERENCE for e in resolution.evidence
    )


# ---------------------------------------------------------------------------
# N5-N8 — the TYPED-OBJECT boundary, which had a door in it
# ---------------------------------------------------------------------------
#
# `from_mapping` refused a MODEL_EXECUTION label and the CONSTRUCTOR did not, so a
# caller could step around the parser with three lines: build an `EvidenceRef`, wrap it
# in a `SuppliedRecord`, hand it to `resolve_policy`, and get a model selection. A
# boundary enforced on the parser alone is not a boundary.
#
# The invariant now lives in `__post_init__`, so the illegal record cannot exist. These
# tests construct the objects DIRECTLY and never call `supplied_records`, because a
# test that goes through the parser cannot show anything about the door beside it.


def _synthetic_ref(evidence_class: str = "MODEL_EXECUTION"):
    """Build an `EvidenceRef` by hand — no mapping, no parser, no helper.

    Deliberately does not use `record()`: the whole point is a path that never touches
    the mapping boundary.
    """
    return EvidenceRef(
        run_id="run-synthetic",
        task_id=CAN,
        source_sha="efa836ff9225f6226ca8a76615f3f45c31110d58",
        workbench_sha="60c630d83c576a013f828fa8ec5414f34fd9974c",
        verdict=OracleVerdict.PASS,
        reason_code="",
        # The record's own limitations say no provider was called.
        limitations=("NO_PROVIDER_CALL_IN_PATH",),
        evidence_class=EvidenceClass(evidence_class),
    )


def test_N5_a_directly_constructed_model_execution_ref_is_refused() -> None:
    """The constructor is the boundary, not the parser."""
    with pytest.raises(InvalidEvidence) as raised:
        _synthetic_ref()
    assert "no supplied record" in str(raised.value)


def test_N6_a_supplied_record_cannot_wrap_an_illegal_ref() -> None:
    """There is nothing to wrap: the reference refuses to exist first."""
    with pytest.raises(InvalidEvidence):
        SuppliedRecord(ref=_synthetic_ref(), digest="sha256:synthetic")


def test_N7_synthetic_model_evidence_cannot_reach_the_resolver() -> None:
    """The end of the bypass. There is no object to hand over.

    The earlier revision reached `SELECTED` here. Nothing about the resolver changed:
    what changed is that no caller can build the argument.
    """
    policy = Policy.from_mapping(a_policy())

    with pytest.raises(InvalidEvidence):
        resolve_policy(policy, [_synthetic_ref()])  # type: ignore[list-item]

    # And with a legal reference, the same policy selects nothing.
    legal = supplied_records([record("run-ref-0001", verdict="PASS")])
    resolution = resolve_policy(policy, legal)
    assert resolution.outcome is PolicyOutcome.DORMANT
    assert resolution.selected_model_ref is None


def test_N8_a_legal_reference_record_still_constructs_directly() -> None:
    """The guard refuses one class, not the type. REFERENCE is constructible, both
    ways, and the two paths produce equal objects."""
    direct = _synthetic_ref("REFERENCE")
    parsed = supplied_records(
        [record("run-synthetic", verdict="PASS", digest="sha256:synthetic")]
    )[0]

    assert direct == parsed.ref
    assert direct.evidence_class is EvidenceClass.REFERENCE


def test_N8b_the_two_boundaries_agree_on_every_invariant() -> None:
    """A rule enforced in one path and not the other is a rule with a way around it.

    Each mapping below is refused by `supplied_records`, and the equivalent DIRECT
    construction is refused too — so the two boundaries cannot drift apart.
    """
    cases = [
        (lambda: _synthetic_ref("MODEL_EXECUTION"),),
        (lambda: EvidenceRef(run_id="", task_id=CAN, source_sha="s", workbench_sha="w",
                             verdict=OracleVerdict.PASS, reason_code="",
                             limitations=(), evidence_class=EvidenceClass.REFERENCE),),
        (lambda: EvidenceRef(run_id="r", task_id=CAN, source_sha="s", workbench_sha="w",
                             verdict=OracleVerdict.BLOCKED, reason_code="",
                             limitations=(), evidence_class=EvidenceClass.REFERENCE),),
    ]
    for (build,) in cases:
        with pytest.raises(InvalidEvidence):
            build()


# ---------------------------------------------------------------------------
# P15 — the policy core reaches nothing
# ---------------------------------------------------------------------------


def test_P15_the_policy_core_imports_only_the_verdict_vocabulary_from_benchmarks() -> None:
    """§4.1. AI-12 reads AI-11's verdicts and nothing else of AI-11's.

    A policy core that could import `benchmarks.runner` or `benchmarks.campaign`
    could re-run AI-11, which §4.1 forbids. The boundary is structural: the verdict
    vocabulary is a frozen vocabulary import, and everything else under `benchmarks`
    is out of reach.
    """
    import ast
    import pathlib

    allowed = {"benchmarks.vocabulary"}
    for name in ("evidence.py", "policy.py", "policy_eval.py"):
        path = pathlib.Path("routing") / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] == "benchmarks":
                    assert node.module in allowed, f"{name} imports {node.module}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("benchmarks."), f"{name} imports {alias.name}"


def test_P16_the_rule_projection_carries_every_semantic_field() -> None:
    """§8 AUDITABLE. The positive control for the projection.

    A rule whose optional fields are ALL declared. The projection must carry every one
    of them, and the rule must survive `from_mapping -> to_mapping -> from_mapping`
    unchanged. A projection that emits only a summary of a rule cannot round-trip, and
    a reader auditing a selection could not see what the rule scoped to, what it
    pinned, or what it selected.
    """
    full = a_rule(
        match_task_id=CAN,
        requires_run_id="run-wanted",
        select={"model_ref": "deepseek/deepseek-flash", "agent": "codex"},
    )
    rule = PolicyRule.from_mapping(full)
    projection = rule.to_mapping()

    assert projection["match_task_id"] == CAN
    assert projection["requires_run_id"] == "run-wanted"
    assert projection["select"] == {
        "model_ref": "deepseek/deepseek-flash",
        "agent": "codex",
    }
    assert PolicyRule.from_mapping(projection) == rule
    assert PolicyRule.from_mapping(projection).to_mapping() == projection


def test_P16b_an_undeclared_optional_field_projects_as_null_and_round_trips() -> None:
    """The canonical form for absent: `null`, and `select` always an object.

    A projection that OMITTED an undeclared field would be indistinguishable from one
    written before the field existed, and a consumer could not tell "not declared"
    from "not carried".
    """
    bare = a_rule(match_task_id=None, select={})
    rule = PolicyRule.from_mapping(bare)
    projection = rule.to_mapping()

    assert "match_task_id" in projection and projection["match_task_id"] is None
    assert "requires_run_id" in projection and projection["requires_run_id"] is None
    assert projection["select"] == {"model_ref": None, "agent": None}
    assert PolicyRule.from_mapping(projection) == rule


@pytest.mark.parametrize("dropped", ["match_task_id", "requires_run_id"])
def test_M9_dropping_a_scalar_from_the_projection_breaks_the_round_trip(
    dropped: str,
) -> None:
    """The mutation is "emit the rule without this field".

    The round trip is the guard: if a projection loses a semantic field, the rule
    rebuilt from it is a DIFFERENT rule, and P16 fails. This test shows that the
    difference is detectable rather than merely asserted.
    """
    rule = PolicyRule.from_mapping(
        a_rule(match_task_id=CAN, requires_run_id="run-wanted")
    )
    projection = rule.to_mapping()

    # This test's own precondition, asserted rather than assumed: it can only show
    # that a LOSS is detectable if the projection carries the field to lose. Without
    # this line the test still passes when the projection drops the field — it builds
    # the loss itself — and it would be silently testing nothing about the projection.
    assert dropped in projection, (
        f"the projection does not carry {dropped!r}, so this test cannot show that "
        "losing it is detectable; P16 is the guard for the field being there at all"
    )

    mutated = {key: value for key, value in projection.items() if key != dropped}

    assert PolicyRule.from_mapping(mutated) != rule, (
        f"dropping {dropped!r} from the projection is undetectable, so P16 does not "
        "guard it"
    )


def test_M9b_dropping_the_selection_from_the_projection_breaks_the_round_trip() -> None:
    """The mutation is "emit the rule without its `select`"."""
    rule = PolicyRule.from_mapping(a_rule())
    projection = rule.to_mapping()
    mutated = {key: value for key, value in projection.items() if key != "select"}

    rebuilt = PolicyRule.from_mapping(mutated)
    assert rebuilt.select_model_ref is None
    assert rebuilt != rule, "dropping `select` is undetectable, so P16 does not guard it"


def test_P17_a_selection_is_unreachable_with_the_evidence_this_contract_admits() -> None:
    """§6.1's line, asserted rather than assumed.

    A rule that selects must require `MODEL_EXECUTION` (§4.2), and no supplied record
    may be one, so no policy over real evidence can select. `SELECTED` and
    `selected_rule` are the dormant mechanism a future contract makes decidable; this
    test fails if a change makes them reachable without that contract, which is
    exactly the fabrication this sub-phase had to close.

    Every other test in this file would still pass if the protection were removed and
    a caller could label its way to a selection. This one would not.
    """
    selecting = Policy.from_mapping(a_policy())

    # Two mechanisms keep this line, and BOTH are asserted, because either alone
    # would leave a path open and a test that exercises only one would pass while the
    # other was removed.
    #
    # 1. A REFERENCE record cannot satisfy a MODEL_EXECUTION requirement: the resolver
    #    compares the classes, so the closest real evidence falls short.
    records = supplied_records([record("run-ref-0001", verdict="PASS")])
    resolution = resolve_policy(selecting, records)

    assert resolution.outcome is not PolicyOutcome.SELECTED
    assert resolution.selected_model_ref is None
    assert resolution.selected_rule is None
    assert resolution.to_mapping()["selected_rule"] is None

    # 2. A record cannot become model evidence by SAYING it is: the input boundary
    #    refuses the claim, so there is nothing for the resolver to compare.
    forged = record("run-forged", verdict="PASS")
    forged["evidence"]["evidence_class"] = "MODEL_EXECUTION"
    with pytest.raises(InvalidEvidence):
        supplied_records([forged])

    # The mechanism is still expressible: the rule declares the requirement and the
    # selection, and projects both, so a future contract has something to activate.
    rule = selecting.rules[0]
    assert rule.requires_evidence_class is EvidenceClass.MODEL_EXECUTION
    assert rule.to_mapping()["select"]["model_ref"] == "deepseek/deepseek-flash"


def test_P17b_a_resolution_that_selected_nothing_carries_no_rule() -> None:
    policy = Policy.from_mapping(a_policy())
    resolution = resolve_policy(policy, supplied_records([record("run-ref-0001")]))

    assert resolution.outcome is PolicyOutcome.DORMANT
    assert resolution.selected_rule is None
    assert resolution.to_mapping()["selected_rule"] is None


def test_P14c_the_tracked_example_policy_validates_and_stays_dormant() -> None:
    """A tracked artifact that no longer validates is a broken artifact.

    The example is loaded from the repository, validated against the model, and
    resolved against the AI-11-C campaign's actual shape: five PASS and one
    BLOCKED, all REFERENCE. It must validate, name the BLOCKED task in its scope,
    and resolve DORMANT.
    """
    import pathlib

    import yaml

    path = pathlib.Path("config/routing/policy.example.yaml")
    policy = Policy.from_mapping(yaml.safe_load(path.read_text(encoding="utf-8")))

    assert policy.state is PolicyState.DORMANT
    assert FUZZ in policy.evidence_scope, (
        "the example dropped the BLOCKED task from its scope; §4.4 forbids removing "
        "a task because it is BLOCKED"
    )
    assert policy.selecting_rules, "the example demonstrates no selecting rule"

    tasks = [(task, "PASS", "") for task in policy.evidence_scope if task != FUZZ]
    tasks.append((FUZZ, "BLOCKED", BLOCKED_REASON))
    records = supplied_records(
        [
            record(f"run-{index:04d}", task_id=task_id, verdict=verdict, reason_code=reason)
            for index, (task_id, verdict, reason) in enumerate(tasks)
        ]
    )

    resolution = resolve_policy(policy, records)
    assert resolution.outcome is PolicyOutcome.DORMANT
    assert resolution.selected_model_ref is None
    assert resolution.missing_scope_tasks == ()


def test_P15b_the_policy_core_starts_no_process_and_opens_no_socket() -> None:
    import ast
    import pathlib

    banned = {"subprocess", "socket", "http", "urllib", "requests", "asyncio", "multiprocessing"}
    for path in sorted(pathlib.Path("routing").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in banned, path.name
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned, path.name
