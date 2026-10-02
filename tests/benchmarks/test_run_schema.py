"""AI-11 §6, §9, §10, §18 — the BenchmarkRun. Layer 1: contract and schema.

Two invariants carry this module: the REFERENCE/agent_id rule, and the rule that an
unavailable measurement is null WITH a reason rather than a zero.
"""

from __future__ import annotations

import pytest

from benchmarks.errors import InvalidBenchmarkRun
from benchmarks.run import (
    RUN_ID_RE,
    BenchmarkRun,
    HostRecord,
    TestCounts,
    ToolTraceEntry,
    new_run_id,
)
from benchmarks.vocabulary import (
    ExecutorKind,
    LimitationCode,
    OracleVerdict,
    ProvenanceClass,
    SecurityBoundaryStatus,
)

pytestmark = pytest.mark.layer1

RUN_ID = "run-0123456789abcdef"


def valid_run(**overrides: object) -> BenchmarkRun:
    """A REFERENCE run that validates, because that is the v1 default.

    It carries the two limitations v1 always carries, so that the null-measurement rule
    is satisfied by construction and a test that wants to break it has to say so.
    """
    base: dict[str, object] = {
        "run_id": RUN_ID,
        "task_id": "ai11-v1-can-dbc-decode",
        "task_version": 1,
        "executor_kind": ExecutorKind.REFERENCE,
        "agent_id": None,
        "execution_id": None,
        "workbench_sha": "c111855116dfca860a74c76f337a7aa7b023e8b7",
        "source_sha": "efa836ff9225f6226ca8a76615f3f45c31110d58",
        "workspace_identity": {"workspace_id": "ai11-efa836ff9225", "manifest_digest": "a" * 64},
        "host": HostRecord(python="3.14.5", workbench_sha="c1118551"),
        "started_at": "2026-10-02T00:00:00Z",
        "finished_at": "2026-10-02T00:00:01Z",
        "duration_ms": 1000,
        "limitations": [
            LimitationCode.NO_PROVIDER_CALL_IN_PATH.value,
        ],
    }
    base.update(overrides)
    return BenchmarkRun(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T1 — run id (§6.2)
# ---------------------------------------------------------------------------


def test_T1_run_id_grammar() -> None:
    assert RUN_ID_RE.match(RUN_ID)
    assert new_run_id("0123456789abcdef") == RUN_ID
    for bad in ("run-", "run-XYZ", "run-0123456789ABCDEF", "0123456789abcdef", "run-0123456789abcde"):
        assert not RUN_ID_RE.match(bad)


def test_T2_a_bad_run_id_is_refused() -> None:
    with pytest.raises(InvalidBenchmarkRun):
        valid_run(run_id="run-not-hex")


# ---------------------------------------------------------------------------
# T3 — executor_kind (§6.1, §20.4)
# ---------------------------------------------------------------------------


def test_T3_reference_run_carries_a_null_agent_id() -> None:
    run = valid_run()
    assert run.executor_kind is ExecutorKind.REFERENCE
    assert run.agent_id is None


def test_T4_reference_must_not_be_written_into_agent_id() -> None:
    """§6.1, FROZEN. `reference` is not an AI-08 AgentId.

    AI-08 §5.4 forbids treating an unregistered token as a new Agent, and a benchmark
    that registered a fake Agent to have something to run would be doing exactly that.
    """
    for bad in ("reference", "REFERENCE", "ref", "none", ""):
        with pytest.raises(InvalidBenchmarkRun) as excinfo:
            valid_run(agent_id=bad)
        assert "agent_id" in str(excinfo.value)


def test_T5_an_agent_run_must_name_a_registered_agent() -> None:
    with pytest.raises(Exception):
        valid_run(executor_kind=ExecutorKind.AGENT, agent_id="gpt-5")
    run = valid_run(executor_kind=ExecutorKind.AGENT, agent_id="dsh")
    assert run.agent_id == "dsh"


def test_T6_agent_id_goes_through_ai08s_own_boundary() -> None:
    """The identity rule is AI-08's, not a second copy here."""
    run = valid_run(executor_kind=ExecutorKind.AGENT, agent_id="codex")
    assert run.agent_id == "codex"


# ---------------------------------------------------------------------------
# T7 — TestCounts (§11)
# ---------------------------------------------------------------------------


def test_T7_counts_must_add_up() -> None:
    TestCounts(planned=10, executed=10, passed=10, failed=0, skipped=0)
    with pytest.raises(InvalidBenchmarkRun) as excinfo:
        TestCounts(planned=234, executed=0, passed=0, failed=0, skipped=1)
    assert "do not add up" in str(excinfo.value)

    with pytest.raises(InvalidBenchmarkRun):
        TestCounts(planned=2, executed=2, passed=1, failed=0, skipped=0)


def test_T8_the_skip_case_is_representable_and_visibly_not_a_pass() -> None:
    """The measured shape: 234 planned, 0 executed, 234 skipped, exit 0."""
    counts = TestCounts(planned=234, executed=0, passed=0, failed=0, skipped=234)
    assert counts.skipped == 234
    assert not counts.all_required_executed
    assert not counts.all_executed_passed


def test_T9_counts_reject_negatives_and_bools() -> None:
    with pytest.raises(InvalidBenchmarkRun):
        TestCounts(planned=-1)
    with pytest.raises(InvalidBenchmarkRun):
        TestCounts(planned=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# T10 — null is not zero (§9.4)
# ---------------------------------------------------------------------------


def test_T10_null_measurements_require_a_named_reason() -> None:
    with pytest.raises(InvalidBenchmarkRun) as excinfo:
        valid_run(limitations=[])
    assert "NO_PROVIDER_CALL_IN_PATH" in str(excinfo.value)


def test_T11_an_unregistered_limitation_code_is_refused() -> None:
    with pytest.raises(InvalidBenchmarkRun):
        valid_run(limitations=["BECAUSE"])


def test_T12_a_parameterised_limitation_code_is_admitted() -> None:
    run = valid_run(
        limitations=[
            LimitationCode.NO_PROVIDER_CALL_IN_PATH.value,
            "PRECONDITION_UNMET:program:yara",
        ]
    )
    assert "PRECONDITION_UNMET:program:yara" in run.limitations


def test_T13_zero_is_never_a_substitute_for_absent() -> None:
    """A run that measured tokens records them; a run that could not, records null.

    There is no state in which `token_usage` is `0` because nothing was measured.
    """
    run = valid_run()
    assert run.token_usage is None
    assert run.to_mapping()["token_usage"] is None


def test_T14_a_measured_token_usage_is_carried_verbatim() -> None:
    run = valid_run(
        token_usage={"usage_status": "REPORTED", "total_tokens": 41},
        limitations=[LimitationCode.NO_PROVIDER_CALL_IN_PATH.value],
    )
    assert run.to_mapping()["token_usage"]["total_tokens"] == 41


# ---------------------------------------------------------------------------
# T15 — provenance classes (§9.1)
# ---------------------------------------------------------------------------


def test_T15_provenance_classes_are_closed_and_distinct() -> None:
    assert sorted(m.value for m in ProvenanceClass) == ["DOCUMENTED", "MEASURED", "STATIC"]


def test_T16_the_two_axes_are_separate_types() -> None:
    """§14.1. Merging the vocabularies is the first step of merging the axes."""
    assert OracleVerdict is not SecurityBoundaryStatus
    assert not issubclass(OracleVerdict, SecurityBoundaryStatus)
    assert not issubclass(SecurityBoundaryStatus, OracleVerdict)


def test_T17_a_run_can_be_a_pass_with_a_violation() -> None:
    """Both pairings are legal and are recorded as they are."""
    run = valid_run(
        task_status=OracleVerdict.PASS,
        security_boundary_status=SecurityBoundaryStatus.VIOLATION,
    )
    assert run.task_status is OracleVerdict.PASS
    assert run.security_boundary_status is SecurityBoundaryStatus.VIOLATION

    run2 = valid_run(
        task_status=OracleVerdict.FAIL,
        security_boundary_status=SecurityBoundaryStatus.NO_VIOLATION,
    )
    assert run2.task_status is OracleVerdict.FAIL
    assert run2.security_boundary_status is SecurityBoundaryStatus.NO_VIOLATION


def test_T18_no_composite_score_field_exists() -> None:
    """§23. There is no field a single number could be written into."""
    projected = set(valid_run().to_mapping())
    for forbidden in ("score", "rank", "winner", "grade", "overall", "weighted"):
        assert forbidden not in projected


# ---------------------------------------------------------------------------
# T19 — the tool trace boundary (§10.1)
# ---------------------------------------------------------------------------


def test_T19_tool_trace_carries_no_arguments_or_output() -> None:
    entry = ToolTraceEntry(
        ordinal=0,
        what_ran="git/read_file",
        tool_version="1.0.0",
        outcome="COMPLETED",
        guard_decision="ALLOW",
        guard_decision_id="dec-1",
        guard_reason_code="RULE_MATCHED",
        duration_ms=3,
    )
    projected = entry.to_mapping()
    assert set(projected) == {
        "ordinal", "what_ran", "tool_version", "outcome", "guard", "duration_ms"
    }
    assert set(projected["guard"]) == {"decision", "decision_id", "reason_code", "evaluated"}
    for forbidden in ("arguments", "stdout", "stderr", "exit_code", "command"):
        assert forbidden not in projected


def test_T20_a_pre_guard_refusal_is_not_an_evaluation() -> None:
    """§10.2. An empty decision id is AI-06's own signal that nothing evaluated."""
    entry = ToolTraceEntry(
        ordinal=0,
        what_ran="terminal/run",
        tool_version="1.0.0",
        outcome="BLOCKED",
        guard_decision=None,
        guard_decision_id="",
        guard_reason_code="",
    )
    assert entry.is_pre_guard_refusal
    assert not entry.was_evaluated
    assert not entry.is_guard_refusal
    assert entry.to_mapping()["guard"]["decision"] is None


def test_T21_a_guard_refusal_is_not_a_bypass() -> None:
    """§10.3. A refusal is evidence the boundary worked."""
    entry = ToolTraceEntry(
        ordinal=0,
        what_ran="vehicle_network/vcan_can_send",
        tool_version="1.0.0",
        outcome="NOT_RUN",
        guard_decision="DENY",
        guard_decision_id="dec-9",
        guard_reason_code="NO_APPLICABLE_RULE",
    )
    assert entry.was_evaluated
    assert entry.is_guard_refusal
    assert not entry.is_pre_guard_refusal


def test_T22_tool_trace_projects_an_ai08_ref() -> None:
    """Reads only the attributes AI-08 declares; a richer object leaks nothing."""
    class RicherCall:
        ordinal = 2
        what_ran = "tests/pytest"
        tool_version = "1.0.0"
        outcome = "COMPLETED"
        guard_decision = "ALLOW"
        guard_decision_id = "dec-2"
        guard_reason_code = "RULE_MATCHED"
        duration_ms = 11
        arguments = {"secret": "must not leak"}
        stdout = "must not leak"

    entry = ToolTraceEntry.from_tool_call_ref(RicherCall())
    assert entry.what_ran == "tests/pytest"
    assert "must not leak" not in str(entry.to_mapping())


# ---------------------------------------------------------------------------
# T23 — projection (§18.1)
# ---------------------------------------------------------------------------


def test_T23_run_projection_is_an_explicit_allowlist() -> None:
    projected = set(valid_run().to_mapping())
    assert projected == {
        "schema_version", "run_id", "task_id", "task_version", "executor_kind",
        "agent_id", "execution_id", "provider", "model", "model_ref", "workbench_sha",
        "source_sha", "workspace_identity", "host", "started_at", "finished_at",
        "duration_ms", "tool_trace", "tests", "git_before", "git_after", "diff_digest",
        "oracle_results", "task_status", "regression_status", "security_boundary_status",
        "token_usage", "cost", "limitations",
    }


def test_T24_no_raw_content_field_exists_anywhere() -> None:
    """§18.2, for every status including FAILED and BLOCKED."""
    projected = set(valid_run().to_mapping())
    for forbidden in (
        "raw_output", "model_output", "prompt", "completion", "reasoning",
        "tool_arguments", "stdout", "stderr", "diff", "credentials", "task_body",
    ):
        assert forbidden not in projected


def test_T25_schema_version_is_closed() -> None:
    with pytest.raises(InvalidBenchmarkRun):
        valid_run(schema_version=2)
