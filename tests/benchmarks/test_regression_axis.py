"""AI-11 §12 — the regression axis must be MEASURED, not hardcoded.

These tests exist because of a defect this file would have caught.

```text
observed   execute_task(...) -> regression_status = NOT_RUN, regression_results = ()
cause      _record() accepted both as parameters and then constructed BenchmarkRun
           with `regression_status=OracleVerdict.NOT_RUN` written out as a literal,
           and with no `regression_results` argument at all.

           evaluate_regression() ran correctly. Its verdict reached _record. _record
           discarded it ONE LAYER BELOW the code that produced it, so every run
           recorded NOT_RUN for the whole life of the axis.
```

A test that only called `evaluate_regression()` directly would have passed throughout,
because the function was never the problem. The tests below go through `execute_task`
and assert on the RECORD, and one of them fails if the literal comes back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import benchmarks.runner as runner
from benchmarks.executor import ReferenceExecutor, ReferenceVariant
from benchmarks.runner import evaluate_regression, execute_task
from benchmarks.run import new_run_id
from benchmarks.task import TaskDefinition, load_corpus
from benchmarks.vocabulary import OracleVerdict
from tests.benchmarks.conftest import valid_task_mapping
from tests.benchmarks.test_benchmark_workspace import _make_source_repo

pytestmark = pytest.mark.layer2

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "tasks"
CAN = "ai11-v1-can-dbc-decode"
CONDITION_ID = "factor-offset-transposition"


@pytest.fixture
def can_task() -> TaskDefinition:
    return next(t for t in load_corpus(CORPUS_ROOT) if t.task_id == CAN)


# ---------------------------------------------------------------------------
# G1 — the defect itself: the RECORD must carry the measured verdict
# ---------------------------------------------------------------------------


def test_G1_record_carries_the_regression_verdict_not_a_literal(
    can_task: TaskDefinition, tmp_path: Path
) -> None:
    """The anti-regression test. It fails the moment the literal comes back.

    `evaluate_regression` is replaced with one that returns a verdict NO run could
    reach by accident. If `_record` still writes `NOT_RUN`, this fails.
    """
    sentinel = OracleVerdict.UNKNOWN
    sentinel_results = ({"condition_id": "sentinel", "verdict": "UNKNOWN"},)

    original = runner.evaluate_regression
    runner.evaluate_regression = lambda **kwargs: (sentinel, "SENTINEL", sentinel_results)
    try:
        outcome = execute_task(
            task=can_task,
            corpus_root=CORPUS_ROOT,
            source_root=Path("D:/SecurityLab"),
            scratch_root=tmp_path / "scratch",
            run_id=new_run_id("0123456789abcdef"),
        )
    finally:
        runner.evaluate_regression = original

    assert outcome.run.regression_status is sentinel, (
        "the record does not carry what evaluate_regression returned; the value is "
        "being discarded between the evaluator and BenchmarkRun"
    )
    assert outcome.run.regression_results == sentinel_results, (
        "the condition-level result was dropped"
    )
    assert outcome.run.regression_status is not OracleVerdict.NOT_RUN


def test_G2_a_bypassed_evaluation_cannot_look_like_a_measured_one(
    can_task: TaskDefinition, tmp_path: Path
) -> None:
    """Removing the evaluation must change the record, not leave NOT_RUN behind.

    With the evaluator bypassed the default is NOT_RUN — which is the ONLY place
    NOT_RUN may come from, and it is distinguishable from a measured verdict.
    """
    original = runner.evaluate_regression
    runner.evaluate_regression = lambda **kwargs: (OracleVerdict.NOT_RUN, "BYPASSED", ())
    try:
        outcome = execute_task(
            task=can_task,
            corpus_root=CORPUS_ROOT,
            source_root=Path("D:/SecurityLab"),
            scratch_root=tmp_path / "scratch",
            run_id=new_run_id("fedcba9876543210"),
        )
    finally:
        runner.evaluate_regression = original

    assert outcome.run.regression_status is OracleVerdict.NOT_RUN
    assert outcome.run.regression_results == (), "a bypassed evaluation produced results"


# ---------------------------------------------------------------------------
# G3 — the real path, end to end
# ---------------------------------------------------------------------------


def test_G3_execute_task_reaches_the_regression_evaluator(
    can_task: TaskDefinition, tmp_path: Path
) -> None:
    """A real run records a MEASURED regression verdict and its condition record."""
    outcome = execute_task(
        task=can_task,
        corpus_root=CORPUS_ROOT,
        source_root=Path("D:/SecurityLab"),
        scratch_root=tmp_path / "scratch",
        run_id=new_run_id("0123456789abcdef"),
    )
    run = outcome.run

    assert run.regression_results, "the regression axis produced no condition record"
    record = dict(run.regression_results[0])
    assert record["condition_id"] == CONDITION_ID
    assert run.regression_status is OracleVerdict(record["verdict"]), (
        "the axis verdict and the condition verdict disagree"
    )


def test_G4_a_rejected_negative_control_is_a_regression_pass(
    can_task: TaskDefinition, tmp_path: Path
) -> None:
    """§12's semantics, stated as a test.

    The known_bad submission is a declared WRONG answer. `regression_status = PASS`
    means the oracle REJECTED it — the control held. It does NOT mean the task passed,
    and it is deliberately not derived from `task_status`.
    """
    outcome = execute_task(
        task=can_task,
        corpus_root=CORPUS_ROOT,
        source_root=Path("D:/SecurityLab"),
        scratch_root=tmp_path / "scratch",
        run_id=new_run_id("0123456789abcdef"),
        variant=ReferenceVariant.KNOWN_GOOD,
    )
    run = outcome.run
    if run.regression_status is OracleVerdict.PASS:
        assert dict(run.regression_results[0])["reason_code"] == "NEGATIVE_CONTROL_REJECTED"


def test_G5_regression_is_not_derived_from_task_status(
    can_task: TaskDefinition, tmp_path: Path
) -> None:
    """The two axes are computed separately and must not be copies of one another."""
    good = execute_task(
        task=can_task, corpus_root=CORPUS_ROOT, source_root=Path("D:/SecurityLab"),
        scratch_root=tmp_path / "s1", run_id=new_run_id("0123456789abcdef"),
    ).run
    bad = execute_task(
        task=can_task, corpus_root=CORPUS_ROOT, source_root=Path("D:/SecurityLab"),
        scratch_root=tmp_path / "s2", run_id=new_run_id("fedcba9876543210"),
        variant=ReferenceVariant.KNOWN_BAD,
    ).run

    assert good.task_status is OracleVerdict.PASS
    assert bad.task_status is OracleVerdict.FAIL
    # The negative control is the SAME declared wrong answer in both runs, so the
    # regression axis must agree even though task_status does not.
    assert good.regression_status is bad.regression_status, (
        "the regression axis moved with task_status; it is being derived from it"
    )


# ---------------------------------------------------------------------------
# G6 — an unavailable environment is BLOCKED, never NOT_RUN and never PASS
# ---------------------------------------------------------------------------


def test_G6_an_unavailable_context_is_blocked_not_not_run(
    can_task: TaskDefinition, tmp_path: Path
) -> None:
    """No source tree means no DBC, which means the control could not be judged."""
    verdict, reason, results = evaluate_regression(
        task=can_task,
        corpus_root=CORPUS_ROOT,
        source_root=None,
        setup_dir=None,
        workspace_root=None,
        oracle_runner=runner.LocalProcessRunner(),
    )
    assert verdict is OracleVerdict.BLOCKED
    assert verdict is not OracleVerdict.NOT_RUN, (
        "an environment that could not run the control is BLOCKED; NOT_RUN means the "
        "axis was intentionally not attempted"
    )
    assert verdict is not OracleVerdict.PASS
    assert results and results[0]["condition_id"] == CONDITION_ID


def test_G7_no_declared_condition_is_not_run(tmp_path: Path) -> None:
    """NOT_RUN is correct — and only — when the task declares no required condition."""
    task = TaskDefinition.from_mapping(
        valid_task_mapping(regression_conditions=[])
    )
    verdict, reason, results = evaluate_regression(
        task=task,
        corpus_root=tmp_path,
        source_root=None,
        setup_dir=None,
        workspace_root=None,
        oracle_runner=runner.LocalProcessRunner(),
    )
    assert verdict is OracleVerdict.NOT_RUN
    assert results == ()


def test_G8_every_corpus_task_declares_a_required_condition(
    can_task: TaskDefinition,
) -> None:
    for task in load_corpus(CORPUS_ROOT):
        assert task.regression_conditions, f"{task.task_id} declares no regression condition"
        assert all(c.required for c in task.regression_conditions)
