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

### Why these tests build a source repository

They used to name `D:/SecurityLab` — a path that exists only on the machine the axis was
developed on. On any other host `validate_source_root()` correctly refused it, every run
came back `BLOCKED / PRECONDITION_UNMET:source_root`, and the tests failed for a reason
that had nothing to do with the regression axis. The refusal was right; hardcoding a
developer's checkout was not.

They now use `_make_source_repo()` — the real miniature SecurityLab the workspace tests
already build, carrying the DBC the CAN oracle decodes. The source-root precondition is
therefore satisfied by REAL material rather than mocked away, and the lifecycle under
test is the whole one:

```text
execute_task() -> validate_source_root() -> derive_source_tree() -> evaluate_regression()
               -> _record() -> BenchmarkRun
```

Two of these tests would otherwise pass for the wrong reason on a host without the
repository, and that is worth naming:

```text
G2  asserts regression_status is NOT_RUN and results == () — which is ALSO what a run
    blocked before the evaluator produces. It counts the evaluator's calls, so the
    environment's default cannot be mistaken for the bypass being measured.
G4  asserts a condition that is vacuously true when the axis recorded nothing. It now
    requires a measured verdict first.
```
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


@pytest.fixture
def source_repo(tmp_path: Path) -> tuple[Path, str]:
    """A real, readable miniature source repository — see `_make_source_repo`.

    It carries `labs/vehicle/can-basic/demo.dbc`, whose two signals decode the corpus's
    frozen frame to exactly the values `truth.json` records. Nothing here is mocked: the
    precondition is met by material, and the oracle then derives from it.
    """
    return _make_source_repo(tmp_path)


@pytest.fixture
def runnable_task(can_task: TaskDefinition, source_repo: tuple[Path, str]) -> TaskDefinition:
    """The REAL corpus CAN task, pinned to the fixture repository's revision.

    Everything the axis judges — the workspace declaration, the oracle, the control
    material, the regression condition — is the corpus's own. Only the revision pin
    moves: the corpus names the upstream SecurityLab commit, and the fixture is a
    miniature repository with its own HEAD that no upstream sha could resolve in.
    """
    _, sha = source_repo
    raw = can_task.to_mapping()
    raw["source_sha"] = sha
    return TaskDefinition.from_mapping(raw)


# ---------------------------------------------------------------------------
# G1 — the defect itself: the RECORD must carry the measured verdict
# ---------------------------------------------------------------------------


def test_G1_record_carries_the_regression_verdict_not_a_literal(
    runnable_task: TaskDefinition, source_repo: tuple[Path, str], tmp_path: Path
) -> None:
    """The anti-regression test. It fails the moment the literal comes back.

    `evaluate_regression` is replaced with one that returns a verdict NO run could
    reach by accident. If `_record` still writes `NOT_RUN`, this fails.
    """
    repo, _ = source_repo
    sentinel = OracleVerdict.UNKNOWN
    sentinel_results = ({"condition_id": "sentinel", "verdict": "UNKNOWN"},)

    original = runner.evaluate_regression
    runner.evaluate_regression = lambda **kwargs: (sentinel, "SENTINEL", sentinel_results)
    try:
        outcome = execute_task(
            task=runnable_task,
            corpus_root=CORPUS_ROOT,
            source_root=repo,
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
    runnable_task: TaskDefinition, source_repo: tuple[Path, str], tmp_path: Path
) -> None:
    """Removing the evaluation must change the record, not leave NOT_RUN behind.

    With the evaluator bypassed the default is NOT_RUN — which is the ONLY place
    NOT_RUN may come from, and it is distinguishable from a measured verdict.

    NOT_RUN is also what a run blocked BEFORE the evaluator records, so the calls are
    counted: without that, a host whose source root could not be read would satisfy this
    test while measuring nothing at all.
    """
    repo, _ = source_repo
    calls: list[dict] = []

    def bypassed(**kwargs):  # noqa: ANN003, ANN202
        calls.append(kwargs)
        return OracleVerdict.NOT_RUN, "BYPASSED", ()

    original = runner.evaluate_regression
    runner.evaluate_regression = bypassed
    try:
        outcome = execute_task(
            task=runnable_task,
            corpus_root=CORPUS_ROOT,
            source_root=repo,
            scratch_root=tmp_path / "scratch",
            run_id=new_run_id("fedcba9876543210"),
        )
    finally:
        runner.evaluate_regression = original

    assert calls, (
        "the run never reached the regression evaluator, so NOT_RUN here is the "
        "environment's default rather than the bypass this test is about"
    )
    assert outcome.run.regression_status is OracleVerdict.NOT_RUN
    assert outcome.run.regression_results == (), "a bypassed evaluation produced results"


# ---------------------------------------------------------------------------
# G3 — the real path, end to end
# ---------------------------------------------------------------------------


def test_G3_execute_task_reaches_the_regression_evaluator(
    runnable_task: TaskDefinition, source_repo: tuple[Path, str], tmp_path: Path
) -> None:
    """A real run records a MEASURED regression verdict and its condition record.

    `task_status` is asserted first, so a run that never got past the source root cannot
    be read as the axis having measured something.
    """
    repo, _ = source_repo
    outcome = execute_task(
        task=runnable_task,
        corpus_root=CORPUS_ROOT,
        source_root=repo,
        scratch_root=tmp_path / "scratch",
        run_id=new_run_id("0123456789abcdef"),
    )
    run = outcome.run

    assert run.task_status is OracleVerdict.PASS, (
        f"the lifecycle did not reach the oracle ({run.limitations}); the regression "
        "axis cannot have measured anything"
    )

    assert run.regression_results, "the regression axis produced no condition record"
    record = dict(run.regression_results[0])
    assert record["condition_id"] == CONDITION_ID
    assert run.regression_status is OracleVerdict(record["verdict"]), (
        "the axis verdict and the condition verdict disagree"
    )


def test_G4_a_rejected_negative_control_is_a_regression_pass(
    runnable_task: TaskDefinition, source_repo: tuple[Path, str], tmp_path: Path
) -> None:
    """§12's semantics, stated as a test.

    The known_bad submission is a declared WRONG answer. `regression_status = PASS`
    means the oracle REJECTED it — the control held. It does NOT mean the task passed,
    and it is deliberately not derived from `task_status`.

    A MEASURED verdict is required before the condition is read: an axis that recorded
    nothing would satisfy the conditional below while proving nothing.
    """
    repo, _ = source_repo
    outcome = execute_task(
        task=runnable_task,
        corpus_root=CORPUS_ROOT,
        source_root=repo,
        scratch_root=tmp_path / "scratch",
        run_id=new_run_id("0123456789abcdef"),
        variant=ReferenceVariant.KNOWN_GOOD,
    )
    run = outcome.run
    assert run.regression_status is not OracleVerdict.NOT_RUN, (
        f"the regression axis was never evaluated ({run.regression_status}); there is "
        "no negative-control result to read"
    )
    assert run.regression_results, "a measured axis records a condition result"
    if run.regression_status is OracleVerdict.PASS:
        assert dict(run.regression_results[0])["reason_code"] == "NEGATIVE_CONTROL_REJECTED"


def test_G5_regression_is_not_derived_from_task_status(
    runnable_task: TaskDefinition, source_repo: tuple[Path, str], tmp_path: Path
) -> None:
    """The two axes are computed separately and must not be copies of one another."""
    repo, _ = source_repo
    good = execute_task(
        task=runnable_task, corpus_root=CORPUS_ROOT, source_root=repo,
        scratch_root=tmp_path / "s1", run_id=new_run_id("0123456789abcdef"),
    ).run
    bad = execute_task(
        task=runnable_task, corpus_root=CORPUS_ROOT, source_root=repo,
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
