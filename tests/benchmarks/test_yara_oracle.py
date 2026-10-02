"""AI-11 §7, §A.3 — the YARA oracle: real collection, then judgement. Layer 2.

The oracle for `ai11-v1-yara-rule-author` does not compare a `matches` mapping the
submission supplied. It takes a RULE, runs it against the held-out samples with the
`yara` binary, and judges the matches the SCANNER reported. `truth.json` says what those
matches should be; it is never itself the observation.

`yara` is not installed on every host — including the one this was developed on. The
tests below therefore come in two kinds, and the difference is stated rather than
blurred:

```text
StubYara            a declared test double implementing the CLI contract and the small
                    subset of rule syntax the corpus uses. It exercises the MACHINERY.
real yara           the test marked `skipif`. It is the one that settles whether the
                    fixtures and the reference rule actually agree.
```
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.errors import OracleProtocolError
from benchmarks.executor import ReferenceExecutor, ReferenceVariant
from benchmarks.oracle import ProcessResult
from benchmarks.oracles import collect, evaluate_submission, judge_submission
from benchmarks.task import load_task
from benchmarks.vocabulary import OracleVerdict
from tests.benchmarks.conftest import StubYara, yara_available

pytestmark = pytest.mark.layer2

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "tasks"
TASK_ID = "ai11-v1-yara-rule-author"
ORACLE_ID = f"{TASK_ID}.oracle"


@pytest.fixture(scope="module")
def task():
    return load_task(CORPUS_ROOT / TASK_ID / "task.yaml")


@pytest.fixture
def control() -> Path:
    return CORPUS_ROOT / TASK_ID / "control"


def _evaluate(task, variant, runner):
    executor = ReferenceExecutor(task, CORPUS_ROOT)
    return evaluate_submission(
        oracle_id=task.oracle.oracle_id,
        required=task.oracle.required,
        submission=executor.produce(variant).payload,
        truth=executor.truth(),
        control_dir=executor.control,
        runner=runner,
    )


class NoYara:
    """A host where the scanner is absent. Nothing runs, and exit_code is None."""

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        return ProcessResult(exit_code=None)


class BrokenRuleYara:
    """A scanner that refuses the rule — the compile-error path."""

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        return ProcessResult(exit_code=2, stderr="error: syntax error, unexpected '}'")


# ---------------------------------------------------------------------------
# Y1 — the collection really runs the scanner over the held-out material
# ---------------------------------------------------------------------------


def test_Y1_the_collector_runs_yara_over_every_held_out_sample(task, control) -> None:
    """The argv is `yara <rule> <sample>`, once per held-out sample."""
    stub = StubYara()
    executor = ReferenceExecutor(task, CORPUS_ROOT)
    truth = executor.truth()

    observation = collect(
        ORACLE_ID,
        executor.produce(ReferenceVariant.KNOWN_GOOD).payload,
        truth,
        control_dir=control,
        runner=stub,
    )

    assert observation.complete
    assert len(stub.calls) == len(truth["samples"])
    assert all(call[0] == "yara" for call in stub.calls)
    scanned = {Path(call[2]).name for call in stub.calls}
    assert scanned == {spec["file"] for spec in truth["samples"].values()}
    assert all(Path(call[1]).name == "known_good.yar" for call in stub.calls)


def test_Y2_the_observation_comes_from_the_scanner_not_from_truth(task, control) -> None:
    """A rule that matches nothing observes nothing, whatever truth says.

    This is the assertion that separates an observation from expected truth. If the
    oracle were reading truth, this rule would still "pass".
    """
    truth = ReferenceExecutor(task, CORPUS_ROOT).truth()
    empty_rule = control / "known_good.yar"
    assert empty_rule.is_file()

    observation = collect(
        ORACLE_ID,
        {"rule_file": "known_bad.yar"},
        truth,
        control_dir=control,
        runner=StubYara(),
    )
    matches = observation.values["matches"]
    # The false-positive rule fires on the "AFL" decoy, and the observation says so.
    assert matches["holdout_negative_clean"] is True
    assert matches != {key: spec["expected"] for key, spec in truth["samples"].items()}


# ---------------------------------------------------------------------------
# Y3 — the discrimination control
# ---------------------------------------------------------------------------


def test_Y3_the_reference_rule_passes(task, control) -> None:
    result = _evaluate(task, ReferenceVariant.KNOWN_GOOD, StubYara())
    assert result.verdict is OracleVerdict.PASS
    assert result.tests.planned == 4
    assert result.tests.failed == 0


def test_Y4_the_false_positive_rule_does_not_pass(task, control) -> None:
    """§7.4. The known-bad rule compiles and runs, and is WRONG."""
    result = _evaluate(task, ReferenceVariant.KNOWN_BAD, StubYara())
    assert result.verdict is OracleVerdict.FAIL
    assert result.verdict is not OracleVerdict.PASS
    assert result.tests.failed >= 1
    assert result.reason_code.startswith("YARA_DETECTION_MISMATCH")
    # Which samples failed is in the observation, and Y2 checks it there. The reason code
    # names the first failure in sample order, which is not the decoy.
    assert result.tests.planned == 4


# ---------------------------------------------------------------------------
# Y5 — environment versus submission (§8.2)
# ---------------------------------------------------------------------------


def test_Y5_an_absent_scanner_is_blocked_not_failed(task) -> None:
    """Nothing ran, so nothing is known about the rule. BLOCKED, never FAIL."""
    result = _evaluate(task, ReferenceVariant.KNOWN_GOOD, NoYara())
    assert result.verdict is OracleVerdict.BLOCKED
    assert result.verdict is not OracleVerdict.FAIL
    assert result.verdict is not OracleVerdict.PASS
    assert result.reason_code == "YARA_PROGRAM_UNAVAILABLE"
    assert result.limitations


def test_Y6_a_rule_that_does_not_compile_is_fail_not_blocked(task) -> None:
    """The scanner ran and refused the SUBMISSION. That is an assertion failure.

    It is not an environment problem: the program was present and answered.
    """
    result = _evaluate(task, ReferenceVariant.KNOWN_GOOD, BrokenRuleYara())
    assert result.verdict is OracleVerdict.FAIL
    assert result.verdict is not OracleVerdict.BLOCKED
    assert result.reason_code == "YARA_RULE_DID_NOT_COMPILE"


def test_Y7_a_missing_held_out_sample_makes_the_check_incomplete(task, control,
                                                                 tmp_path: Path) -> None:
    """Delete one held-out sample: the required check cannot run.

    The verdict must NOT be PASS. The required checks did not all execute, which is
    exactly what §11 forbids from becoming a pass.
    """
    import shutil as _shutil

    damaged = tmp_path / "control"
    _shutil.copytree(control, damaged)
    (damaged / "holdout_negative_clean.txt").unlink()

    executor = ReferenceExecutor(task, CORPUS_ROOT)
    result = evaluate_submission(
        oracle_id=ORACLE_ID,
        required=task.oracle.required,
        submission=executor.produce(ReferenceVariant.KNOWN_GOOD).payload,
        truth=executor.truth(),
        control_dir=damaged,
        runner=StubYara(),
    )
    assert result.verdict is not OracleVerdict.PASS
    assert result.verdict is OracleVerdict.BLOCKED
    assert result.tests.executed == 0
    assert result.tests.skipped == result.tests.planned


def test_Y8_a_timeout_is_blocked(task) -> None:
    class SlowYara:
        def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
            return ProcessResult(exit_code=None, timed_out=True)

    result = _evaluate(task, ReferenceVariant.KNOWN_GOOD, SlowYara())
    assert result.verdict is OracleVerdict.BLOCKED
    assert result.reason_code == "YARA_SCAN_TIMEOUT"


# ---------------------------------------------------------------------------
# Y9 — the submission cannot name a rule outside the control directory
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rule_file",
    ["../../../etc/passwd", "/etc/passwd", "..\\..\\windows\\system32\\config"],
)
def test_Y9_a_rule_path_outside_control_is_refused(task, control, rule_file: str) -> None:
    """The submission is data. Data that names a location can name the wrong one."""
    truth = ReferenceExecutor(task, CORPUS_ROOT).truth()
    observation = collect(
        ORACLE_ID,
        {"rule_file": rule_file},
        truth,
        control_dir=control,
        runner=StubYara(),
    )
    assert not observation.complete
    assert observation.reason_code == "YARA_RULE_PATH_REFUSED"


def test_Y10_no_rule_submitted_is_a_refusal_not_a_pass(task, control) -> None:
    truth = ReferenceExecutor(task, CORPUS_ROOT).truth()
    observation = collect(ORACLE_ID, {}, truth, control_dir=control, runner=StubYara())
    assert not observation.complete
    assert observation.reason_code == "YARA_NO_RULE_SUBMITTED"


# ---------------------------------------------------------------------------
# Y11 — the judge refuses truth outside the frozen vocabulary
# ---------------------------------------------------------------------------


def test_Y11_a_non_boolean_expectation_is_refused() -> None:
    with pytest.raises(OracleProtocolError):
        judge_submission(
            ORACLE_ID,
            {"matches": {"s": True}},
            {"samples": {"s": {"file": "s.txt", "expected": "yes"}}},
        )


# ---------------------------------------------------------------------------
# Y12 — the held-out material is outside the agent-visible tree
# ---------------------------------------------------------------------------


def test_Y12_held_out_material_is_never_in_the_declared_workspace(task) -> None:
    """§7.2. The oracle reads them from outside; the Agent never can."""
    assert "control" in task.workspace_setup.exclude
    for relative in task.workspace_setup.include:
        assert "control" not in relative, (
            f"the task includes {relative!r}, which is oracle material"
        )
    assert not any(
        "holdout" in relative for relative in task.workspace_setup.include
    )


def test_Y13_the_truth_names_the_exact_files_on_disk(task, control) -> None:
    truth = ReferenceExecutor(task, CORPUS_ROOT).truth()
    for key, spec in truth["samples"].items():
        assert (control / spec["file"]).is_file(), f"{key} -> {spec['file']} is missing"


# ---------------------------------------------------------------------------
# Y14 — the REAL scanner, when the host has one
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not yara_available(),
    reason=(
        "the real `yara` binary is not on PATH. The stub above exercises the machinery; "
        "this test is the one that settles whether the held-out fixtures and the "
        "reference rule actually agree, and it is NOT_RUN here rather than passed"
    ),
)
def test_Y14_the_real_scanner_agrees_with_the_corpus(task, control) -> None:
    """The only test that proves the fixtures and the reference rule actually agree."""

    class RealYara:
        def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
            import subprocess

            try:
                completed = subprocess.run(
                    list(argv), capture_output=True, text=True,
                    timeout=timeout_seconds or 60, shell=False, check=False,
                )
            except FileNotFoundError:
                return ProcessResult(exit_code=None)
            return ProcessResult(
                exit_code=completed.returncode,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
            )

    good = _evaluate(task, ReferenceVariant.KNOWN_GOOD, RealYara())
    assert good.verdict is OracleVerdict.PASS, good.reason_code

    bad = _evaluate(task, ReferenceVariant.KNOWN_BAD, RealYara())
    assert bad.verdict is not OracleVerdict.PASS


# ---------------------------------------------------------------------------
# Y15 — PREFLIGHT: either every sample is scanned or none is
# ---------------------------------------------------------------------------


class CountingYara(StubYara):
    """The stub, but the call list is the assertion."""


@pytest.mark.parametrize("missing", [
    "holdout_positive_beacon.txt",   # first
    "holdout_negative_benign.txt",   # middle
    "holdout_negative_clean.txt",    # last
])
def test_Y15_a_missing_sample_stops_before_any_scan(task, control, tmp_path, missing) -> None:
    """PREFLIGHT. A partially executed run must not be recorded as fully skipped.

    Scanning three samples and then finding the fourth missing has EXECUTED three checks.
    Reporting `executed = 0` would be a false record of what the harness did — in the
    safe direction, but still false. Either every sample is scanned or none is.
    """
    import shutil as _shutil

    damaged = tmp_path / "control"
    _shutil.copytree(control, damaged)
    (damaged / missing).unlink()

    scanner = CountingYara()
    truth = ReferenceExecutor(task, CORPUS_ROOT).truth()
    observation = collect(
        ORACLE_ID,
        {"rule_file": "known_good.yar"},
        truth,
        control_dir=damaged,
        runner=scanner,
    )

    assert scanner.calls == [], (
        f"the scanner was invoked {len(scanner.calls)} time(s) before the missing "
        f"{missing} was noticed; preflight must establish every path first"
    )
    assert not observation.complete
    assert observation.reason_code == "YARA_HELD_OUT_MATERIAL_MISSING"


def test_Y16_the_incomplete_counts_are_planned_n_skipped_n(task, control, tmp_path) -> None:
    """N planned, 0 executed, N skipped — and never a partial count."""
    import shutil as _shutil

    damaged = tmp_path / "control"
    _shutil.copytree(control, damaged)
    (damaged / "holdout_negative_clean.txt").unlink()

    executor = ReferenceExecutor(task, CORPUS_ROOT)
    result = evaluate_submission(
        oracle_id=ORACLE_ID,
        required=task.oracle.required,
        submission=executor.produce(ReferenceVariant.KNOWN_GOOD).payload,
        truth=executor.truth(),
        control_dir=damaged,
        runner=CountingYara(),
    )
    assert result.tests.planned == 4
    assert result.tests.executed == 0
    assert result.tests.skipped == 4
    assert result.verdict is OracleVerdict.BLOCKED
    assert result.verdict is not OracleVerdict.PASS


def test_Y17_a_complete_run_reports_full_execution(task, control) -> None:
    """The other side of the same rule: no skips when nothing is missing."""
    executor = ReferenceExecutor(task, CORPUS_ROOT)
    result = evaluate_submission(
        oracle_id=ORACLE_ID,
        required=task.oracle.required,
        submission=executor.produce(ReferenceVariant.KNOWN_GOOD).payload,
        truth=executor.truth(),
        control_dir=control,
        runner=StubYara(),
    )
    assert result.tests.planned == 4
    assert result.tests.executed == 4
    assert result.tests.skipped == 0


# ---------------------------------------------------------------------------
# Y18 — truth sample paths are contained
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_name", [
    "../../outside.txt",
    "/etc/passwd",
    "C:/outside.txt",
    r"..\..\outside.txt",
    "sub/../../outside.txt",
])
def test_Y18_a_truth_sample_outside_control_is_refused(task, control, bad_name) -> None:
    """The truth file is DATA. Data that names a location can name the wrong one.

    The corpus is tracked and trusted, and the boundary is closed structurally anyway:
    the scanner is never invoked against a path outside the control directory.
    """
    scanner = CountingYara()
    truth = {"samples": {"s": {"file": bad_name, "expected": True}}}
    observation = collect(
        ORACLE_ID,
        {"rule_file": "known_good.yar"},
        truth,
        control_dir=control,
        runner=scanner,
    )
    assert scanner.calls == [], "the scanner was invoked against a refused path"
    assert not observation.complete
    assert observation.reason_code == "YARA_HELD_OUT_MATERIAL_MISSING"


def test_Y19_a_truth_sample_that_is_not_a_file_is_refused(task, control) -> None:
    scanner = CountingYara()
    truth = {"samples": {"s": {"file": "known_good.yar", "expected": True}}}
    observation = collect(
        ORACLE_ID, {"rule_file": "known_good.yar"}, truth, control_dir=control, runner=scanner
    )
    assert observation.complete, "a file inside control/ is legitimate material"
    assert scanner.calls, "and the scanner runs against it"

    scanner2 = CountingYara()
    truth2 = {"samples": {"s": {"file": "../", "expected": True}}}
    observation2 = collect(
        ORACLE_ID, {"rule_file": "known_good.yar"}, truth2, control_dir=control, runner=scanner2
    )
    assert not observation2.complete
    assert scanner2.calls == []
