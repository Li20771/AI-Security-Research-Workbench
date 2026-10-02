"""AI-11 §8, §11, §14 — the verdict, the skip rule and the aggregate.

Layer 2: behaviour through a fake process seam, no network, nothing spawned.

This module is the one §20.2 calls load-bearing. Its job is to make the six refusals
below unfalsifiable-in-reverse: each of them asserts that a state which is NOT a pass
cannot be recorded as one.
"""

from __future__ import annotations

import pytest

from benchmarks.errors import OracleProtocolError
from benchmarks.oracle import (
    ORACLE_RECORD_SENTINEL,
    OracleProcessOutcome,
    OracleResult,
    ProcessResult,
    aggregate_oracle_verdicts,
    aggregate_security_status,
    apply_pass_rule,
    judge_observation,
    parse_oracle_record,
    run_oracle_command,
)
from benchmarks.run import TestCounts
from benchmarks.vocabulary import OracleVerdict, SecurityBoundaryStatus

pytestmark = pytest.mark.layer2

PASSING = {
    "verdict": "PASS",
    "planned": 3,
    "executed": 3,
    "passed": 3,
    "failed": 0,
    "skipped": 0,
    "skip_class": "NONE",
    "reason_code": "",
}


def record(**overrides: object) -> dict:
    payload = dict(PASSING)
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# T1 — the vocabulary is closed (§8.1)
# ---------------------------------------------------------------------------


def test_T1_oracle_verdict_has_exactly_six_members() -> None:
    assert [m.value for m in OracleVerdict] == [
        "PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN", "UNAVAILABLE",
    ]


def test_T2_a_verdict_outside_the_vocabulary_is_not_admitted() -> None:
    verdict, _, reason = judge_observation(
        record(verdict="SUCCESS"), OracleProcessOutcome(exit_code=0)
    )
    assert verdict is OracleVerdict.UNKNOWN
    assert reason == "ORACLE_VERDICT_NOT_IN_VOCABULARY"


# ---------------------------------------------------------------------------
# T3 — the six refusals
# ---------------------------------------------------------------------------


def test_T3_exit_zero_is_not_pass() -> None:
    """The rule this whole module exists for. Exit 0, and nothing was reported."""
    verdict, counts, reason = judge_observation(None, OracleProcessOutcome(exit_code=0))
    assert verdict is OracleVerdict.UNKNOWN
    assert verdict is not OracleVerdict.PASS
    assert reason == "ORACLE_REPORTED_NOTHING"
    assert counts.planned == 0


def test_T4_not_run_is_not_pass() -> None:
    verdict, _, _ = judge_observation(
        record(skipped=3, executed=0, passed=0, skip_class="INTENTIONAL"),
        OracleProcessOutcome(exit_code=0),
    )
    assert verdict is OracleVerdict.NOT_RUN


def test_T5_blocked_is_not_pass() -> None:
    verdict, _, _ = judge_observation(None, OracleProcessOutcome(exit_code=2))
    assert verdict is OracleVerdict.BLOCKED


def test_T6_unknown_is_not_pass() -> None:
    verdict, _, _ = judge_observation(
        record(skipped=1, executed=2, passed=2, skip_class="SOMETHING_ELSE"),
        OracleProcessOutcome(exit_code=0),
    )
    assert verdict is OracleVerdict.UNKNOWN


def test_T7_unavailable_claimed_by_an_oracle_is_carried_not_upgraded() -> None:
    verdict, _, _ = judge_observation(
        record(verdict="UNAVAILABLE"), OracleProcessOutcome(exit_code=0)
    )
    assert verdict is OracleVerdict.UNAVAILABLE


def test_T8_completed_is_not_pass() -> None:
    """AI-08's COMPLETED is a claim about an execution, never about a task.

    The two vocabularies are separate types, and neither converts into the other.
    """
    from agents.result import AgentExecutionOutcome

    assert AgentExecutionOutcome.COMPLETED.value == "COMPLETED"
    assert "COMPLETED" not in [m.value for m in OracleVerdict]
    assert "PASS" not in [m.value for m in AgentExecutionOutcome]


# ---------------------------------------------------------------------------
# T9 — process states (§8.2)
# ---------------------------------------------------------------------------


def test_T9_an_absent_program_is_blocked_not_failed() -> None:
    """Nothing ran, so nothing is known about the thing checked."""
    verdict, _, reason = judge_observation(None, OracleProcessOutcome(exit_code=None))
    assert verdict is OracleVerdict.BLOCKED
    assert reason == "ORACLE_PROGRAM_UNAVAILABLE"
    assert verdict is not OracleVerdict.FAIL


def test_T10_a_timeout_is_blocked_not_failed() -> None:
    verdict, _, reason = judge_observation(
        None, OracleProcessOutcome(exit_code=None, timed_out=True)
    )
    assert verdict is OracleVerdict.BLOCKED
    assert reason == "ORACLE_TIMEOUT_EXPIRED"


def test_T11_exit_two_is_the_repositorys_environment_convention() -> None:
    """scripts/repro/README.md:12 — 2 is a missing dependency, not a failed check."""
    verdict, _, reason = judge_observation(None, OracleProcessOutcome(exit_code=2))
    assert verdict is OracleVerdict.BLOCKED
    assert reason == "ORACLE_DEPENDENCY_MISSING"


def test_T12_a_non_zero_exit_without_a_record_is_unknown() -> None:
    verdict, _, reason = judge_observation(None, OracleProcessOutcome(exit_code=1))
    assert verdict is OracleVerdict.UNKNOWN
    assert reason == "ORACLE_DID_NOT_COMPLETE_PROTOCOL"


# ---------------------------------------------------------------------------
# T13 — skip-aware PASS (§11)
# ---------------------------------------------------------------------------


def test_T13_the_measured_skip_case_cannot_pass() -> None:
    """234 planned, 0 executed, 234 skipped, exit 0 — SecurityLab's measured shape.

    Its `run_tests.sh` skips every e2e case on a host without vcan0 and still exits 0.
    A benchmark that trusted the exit code would manufacture a PASS here.
    """
    verdict, counts, reason = judge_observation(
        record(planned=234, executed=0, passed=0, failed=0, skipped=234,
               skip_class="ENVIRONMENT"),
        OracleProcessOutcome(exit_code=0),
    )
    assert verdict is OracleVerdict.BLOCKED
    assert counts.skipped == 234
    assert reason == "ORACLE_REQUIRED_CHECK_SKIPPED_ENVIRONMENT"


@pytest.mark.parametrize(
    "skip_class,expected",
    [
        ("ENVIRONMENT", OracleVerdict.BLOCKED),
        ("INTENTIONAL", OracleVerdict.NOT_RUN),
        ("UNKNOWN", OracleVerdict.UNKNOWN),
        ("NONE", OracleVerdict.UNKNOWN),
    ],
)
def test_T14_a_skip_is_classified_never_ignored(skip_class: str, expected: OracleVerdict) -> None:
    verdict, _, _ = judge_observation(
        record(planned=5, executed=4, passed=4, skipped=1, skip_class=skip_class),
        OracleProcessOutcome(exit_code=0),
    )
    assert verdict is expected
    assert verdict is not OracleVerdict.PASS


def test_T15_all_required_executed_and_passed_is_the_only_pass() -> None:
    verdict, counts, _ = judge_observation(record(), OracleProcessOutcome(exit_code=0))
    assert verdict is OracleVerdict.PASS
    assert counts.all_required_executed
    assert counts.all_executed_passed


def test_T16_a_failed_assertion_is_fail() -> None:
    verdict, _, reason = judge_observation(
        record(planned=3, executed=3, passed=2, failed=1),
        OracleProcessOutcome(exit_code=0),
    )
    assert verdict is OracleVerdict.FAIL
    assert reason == "ORACLE_REQUIRED_ASSERTION_FAILED"


# ---------------------------------------------------------------------------
# T17 — non-vacuity (§7.4, §20.2)
# ---------------------------------------------------------------------------


def test_T17_an_oracle_that_planned_nothing_cannot_pass() -> None:
    """The "empty input automatically passes" failure, refused centrally."""
    verdict, _, reason = judge_observation(
        record(planned=0, executed=0, passed=0), OracleProcessOutcome(exit_code=0)
    )
    assert verdict is OracleVerdict.UNKNOWN
    assert reason == "ORACLE_PLANNED_NOTHING"


def test_T18_the_pass_rule_refuses_vacuity_directly() -> None:
    verdict, _, reason = apply_pass_rule(TestCounts())
    assert verdict is OracleVerdict.UNKNOWN
    assert reason == "ORACLE_PLANNED_NOTHING"


def test_T19_an_oracle_record_missing_counts_cannot_pass() -> None:
    """All five counts are required, so a skip cannot go unreported."""
    with pytest.raises(OracleProtocolError) as excinfo:
        judge_observation({"verdict": "PASS"}, OracleProcessOutcome(exit_code=0))
    assert "planned" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T20 — the aggregate (§8.4)
# ---------------------------------------------------------------------------


def result(oracle_id: str, verdict: OracleVerdict, required: bool = True) -> OracleResult:
    return OracleResult(oracle_id=oracle_id, required=required, verdict=verdict)


def test_T20_pass_requires_every_required_oracle_to_pass() -> None:
    assert aggregate_oracle_verdicts([result("a", OracleVerdict.PASS)]) is OracleVerdict.PASS
    assert (
        aggregate_oracle_verdicts(
            [result("a", OracleVerdict.PASS), result("b", OracleVerdict.PASS)]
        )
        is OracleVerdict.PASS
    )


@pytest.mark.parametrize(
    "other",
    [
        OracleVerdict.FAIL,
        OracleVerdict.BLOCKED,
        OracleVerdict.NOT_RUN,
        OracleVerdict.UNKNOWN,
        OracleVerdict.UNAVAILABLE,
    ],
)
def test_T21_one_non_pass_required_oracle_blocks_the_pass(other: OracleVerdict) -> None:
    aggregate = aggregate_oracle_verdicts(
        [result("a", OracleVerdict.PASS), result("b", other)]
    )
    assert aggregate is other
    assert aggregate is not OracleVerdict.PASS


def test_T22_no_required_oracle_is_unknown_not_pass() -> None:
    """ "Every member of the empty set is PASS" is vacuously true, and refused."""
    assert aggregate_oracle_verdicts([]) is OracleVerdict.UNKNOWN
    assert (
        aggregate_oracle_verdicts([result("a", OracleVerdict.PASS, required=False)])
        is OracleVerdict.UNKNOWN
    )


def test_T23_an_optional_oracle_cannot_block_a_pass() -> None:
    aggregate = aggregate_oracle_verdicts(
        [result("a", OracleVerdict.PASS), result("b", OracleVerdict.FAIL, required=False)]
    )
    assert aggregate is OracleVerdict.PASS


def test_T24_fail_outranks_every_not_measured_state() -> None:
    """A definite negative finding must never be masked by a not-measured state."""
    aggregate = aggregate_oracle_verdicts(
        [result("a", OracleVerdict.NOT_RUN), result("b", OracleVerdict.FAIL)]
    )
    assert aggregate is OracleVerdict.FAIL


def test_T25_blocked_outranks_the_epistemic_states() -> None:
    aggregate = aggregate_oracle_verdicts(
        [result("a", OracleVerdict.UNKNOWN), result("b", OracleVerdict.BLOCKED)]
    )
    assert aggregate is OracleVerdict.BLOCKED


# ---------------------------------------------------------------------------
# T26 — the security axis (§14)
# ---------------------------------------------------------------------------


def test_T26_security_aggregate_is_a_separate_function_over_a_separate_type() -> None:
    assert aggregate_security_status([]) is SecurityBoundaryStatus.NOT_RUN
    assert (
        aggregate_security_status([SecurityBoundaryStatus.NO_VIOLATION])
        is SecurityBoundaryStatus.NO_VIOLATION
    )


def test_T27_a_violation_is_never_masked_by_a_not_observed_state() -> None:
    aggregate = aggregate_security_status(
        [SecurityBoundaryStatus.NOT_RUN, SecurityBoundaryStatus.VIOLATION]
    )
    assert aggregate is SecurityBoundaryStatus.VIOLATION


def test_T28_the_two_axes_do_not_share_a_vocabulary_object() -> None:
    assert {m.value for m in SecurityBoundaryStatus} != {m.value for m in OracleVerdict}
    # They share spellings, so identity is the only safe comparison — and it must fail.
    assert SecurityBoundaryStatus.NOT_RUN is not OracleVerdict.NOT_RUN


# ---------------------------------------------------------------------------
# T29 — the wire protocol (§7.3)
# ---------------------------------------------------------------------------


def test_T29_the_last_record_wins() -> None:
    stdout = (
        f"{ORACLE_RECORD_SENTINEL}{{\"verdict\": \"FAIL\"}}\n"
        f"{ORACLE_RECORD_SENTINEL}{{\"verdict\": \"PASS\"}}\n"
    )
    assert parse_oracle_record(stdout) == {"verdict": "PASS"}


def test_T30_no_record_is_none_not_an_error() -> None:
    assert parse_oracle_record("just some output\nno sentinel here\n") is None


def test_T31_a_malformed_record_is_a_protocol_defect() -> None:
    """It must NOT be read as "no record" — the oracle spoke and was not understood."""
    with pytest.raises(OracleProtocolError):
        parse_oracle_record(f"{ORACLE_RECORD_SENTINEL}not json\n")


def test_T32_a_record_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(OracleProtocolError):
        parse_oracle_record(f"{ORACLE_RECORD_SENTINEL}[1, 2, 3]\n")


def test_T33_the_sentinel_is_declared_once() -> None:
    assert ORACLE_RECORD_SENTINEL == "AI11-ORACLE:"


# ---------------------------------------------------------------------------
# T34 — run_oracle_command through a fake seam
# ---------------------------------------------------------------------------


class FakeRunner:
    """The only process seam in these tests. It starts nothing."""

    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        self.calls: list[list[str]] = []

    def run(self, argv, *, cwd, timeout_seconds):  # noqa: ANN001, ANN201
        self.calls.append(list(argv))
        return self.result


def test_T34_a_passing_oracle_through_the_seam() -> None:
    import json

    runner = FakeRunner(
        ProcessResult(exit_code=0, stdout=ORACLE_RECORD_SENTINEL + json.dumps(PASSING) + "\n")
    )
    result_ = run_oracle_command(
        ["python3", "-m", "benchmarks.replay", "t"],
        runner=runner,
        cwd=None,
        timeout_seconds=10,
        oracle_id="o",
    )
    assert result_.verdict is OracleVerdict.PASS
    assert result_.tests.planned == 3
    assert runner.calls == [["python3", "-m", "benchmarks.replay", "t"]]


def test_T35_exit_zero_with_no_record_through_the_seam() -> None:
    runner = FakeRunner(ProcessResult(exit_code=0, stdout="all good\n"))
    result_ = run_oracle_command(
        ["oracle"], runner=runner, cwd=None, timeout_seconds=10, oracle_id="o"
    )
    assert result_.verdict is OracleVerdict.UNKNOWN


def test_T36_a_blocked_oracle_carries_a_limitation_code() -> None:
    runner = FakeRunner(ProcessResult(exit_code=2))
    result_ = run_oracle_command(
        ["oracle"], runner=runner, cwd=None, timeout_seconds=10, oracle_id="o"
    )
    assert result_.verdict is OracleVerdict.BLOCKED
    assert result_.limitations
    assert result_.limitations[0].startswith("ORACLE_MATERIAL_UNAVAILABLE")


def test_T37_an_empty_command_is_refused() -> None:
    with pytest.raises(OracleProtocolError):
        run_oracle_command(
            [], runner=FakeRunner(ProcessResult(exit_code=0)), cwd=None,
            timeout_seconds=10, oracle_id="o",
        )
