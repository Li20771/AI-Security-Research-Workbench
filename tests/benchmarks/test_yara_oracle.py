"""AI-11 §7, §A.3 — the YARA oracle: real collection, then judgement. Layer 2.

The oracle for `ai11-v1-yara-rule-author` does not compare a `matches` mapping the
submission supplied. It takes a RULE, runs it against the held-out samples with the
`yara` binary, and judges the matches the SCANNER reported. `truth.json` says what those
matches should be; it is never itself the observation.

### The exit code is not the observation

MEASURED, YARA 4.5.0:

```text
match       exit 0, stdout "<rule identifier> <target>"
no match    exit 0, stdout ""
failure     non-zero, stderr diagnostic, stdout empty
```

The CLI exits 0 for BOTH readings. The collector once treated `0` as "matched" and `1`
as "did not match", which is a contract yara has never had; against the real corpus that
turned the correct reference rule into four hits and two failures, and the samples it
wrongly failed were exactly the two the rule correctly does not match. The reading now
comes from stdout, attributed to a rule identifier taken from the SUBMITTED rule — and
output that cannot be attributed is UNKNOWN rather than either answer.

### The two kinds of scanner in this file

`yara` is not installed on every host. The tests below therefore come in two kinds, and
the difference is stated rather than blurred:

```text
StubYara            a declared test double implementing the CLI contract ABOVE and the
                    small subset of rule syntax the corpus uses. It exercises the
                    MACHINERY. It does not encode a contract of its own invention: an
                    earlier version of it implemented `0 = match, 1 = no match`, agreed
                    with the defect, and let every test here pass.
ScriptedYara        a scanner that returns the record a test declares, without
                    evaluating anything. For tests about how an OBSERVATION is read,
                    which the evaluator must not be able to satisfy.
real yara           the test marked `skipif`. It is the one that settles whether the
                    fixtures and the reference rule actually agree.
```
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import pytest

from benchmarks.errors import OracleProtocolError
from benchmarks.executor import ReferenceExecutor, ReferenceVariant
from benchmarks.oracle import ProcessResult
from benchmarks.oracles import (
    YaraReading,
    collect,
    declared_rule_names,
    evaluate_submission,
    judge_submission,
    parse_yara_matches,
)
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
    """A scanner that refuses the rule — the compile-error path.

    The exit code and the message are the ones YARA 4.5.0 was measured to produce for a
    rule with a syntax error: **1**, not 2. That matters, because `1` is the code the old
    collector read as "the rule did not match" — so this runner doubles as the case that
    says a refused rule is not a non-match.
    """

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        return ProcessResult(
            exit_code=1,
            stderr='error: rule "ai11_reference_answer" in known_good.yar(9): '
            "syntax error, unexpected '}'",
        )


#: "this sample matched the submitted rule" — expanded into the CLI's actual output.
_MATCH = object()

#: "this sample did not match" — exit 0 with an empty stdout.
_NO_MATCH = object()


class ScriptedYara:
    """A scanner that answers with exactly the record the test declares.

    It evaluates no rule at all. `_MATCH` and `_NO_MATCH` are expanded into the
    byte-for-byte output the real CLI produces — naming the submitted rule and echoing
    the target path this invocation was given — and any other value is returned as the
    test wrote it. A test about how an OBSERVATION is read must not be satisfiable by an
    evaluator that already knows the answer.
    """

    def __init__(
        self, records: Mapping[str, Any], *, rule_name: str = "ai11_reference_answer"
    ) -> None:
        self.records = records
        self.rule_name = rule_name
        self.calls: list[list[str]] = []
        self.responses: list[ProcessResult] = []

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        args = list(argv)
        self.calls.append(args)
        record = self.records[Path(args[2]).name]
        if record is _MATCH:
            record = ProcessResult(exit_code=0, stdout=f"{self.rule_name} {args[2]}\n")
        elif record is _NO_MATCH:
            record = ProcessResult(exit_code=0, stdout="")
        self.responses.append(record)
        return record


def _collect_with(task, control, runner, rule_file: str = "known_good.yar"):
    return collect(
        ORACLE_ID,
        {"rule_file": rule_file},
        ReferenceExecutor(task, CORPUS_ROOT).truth(),
        control_dir=control,
        runner=runner,
    )


def _assert_the_reference_rule_is_observed_correctly(task, control, runner) -> None:
    """The focused semantic assertion for the corrected collector.

    Y30 reinstates the old exit-code reading and requires THIS to fail. If it still
    passed, it would be a test that cannot detect the defect it was written for.
    """
    observation = _collect_with(task, control, runner)
    assert observation.complete, observation.reason_code
    assert observation.values["matches"] == {
        "holdout_positive_beacon": True,
        "holdout_positive_ecu": True,
        "holdout_negative_benign": False,
        "holdout_negative_clean": False,
    }


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

    It is not an environment problem: the program was present and answered. The reason
    code names what happened rather than guessing which failure it was — `yara` exits
    non-zero both for a rule it cannot compile and for a target it cannot open, and the
    exit code does not separate them. The scanner's own message is in the observation.
    """
    result = _evaluate(task, ReferenceVariant.KNOWN_GOOD, BrokenRuleYara())
    assert result.verdict is OracleVerdict.FAIL
    assert result.verdict is not OracleVerdict.BLOCKED
    assert result.reason_code == "YARA_SCANNER_REFUSED_SUBMISSION"


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


class RealYara:
    """The real scanner, through the same process seam every other runner uses."""

    def __init__(self) -> None:
        self.exits: list[int | None] = []

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        import subprocess

        try:
            completed = subprocess.run(
                list(argv), capture_output=True, text=True,
                timeout=timeout_seconds or 60, shell=False, check=False,
            )
        except FileNotFoundError:
            self.exits.append(None)
            return ProcessResult(exit_code=None)
        self.exits.append(completed.returncode)
        return ProcessResult(
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


@pytest.mark.skipif(
    not yara_available(),
    reason=(
        "the real `yara` binary is not on PATH. The stub above exercises the machinery; "
        "this test is the one that settles whether the held-out fixtures and the "
        "reference rule actually agree, and it is NOT_RUN here rather than passed"
    ),
)
def test_Y14_the_real_scanner_agrees_with_the_corpus(task, control) -> None:
    """The only test that proves the fixtures and the reference rule actually agree.

    Every reading is asserted SAMPLE BY SAMPLE, because the verdict alone would not show
    the defect this exists to catch: under the old exit-code reading the scanner still
    ran and still produced four readings, it just produced the wrong four. The two
    samples the rule does not match are the ones that expose it, so they are named.
    """
    reader = RealYara()
    _assert_the_reference_rule_is_observed_correctly(task, control, reader)
    # All four readings came from exit code 0 — two matches and two non-matches. The
    # exit code carries none of that information.
    assert set(reader.exits) == {0}, reader.exits

    good = _evaluate(task, ReferenceVariant.KNOWN_GOOD, RealYara())
    assert good.verdict is OracleVerdict.PASS, good.reason_code

    bad = _evaluate(task, ReferenceVariant.KNOWN_BAD, RealYara())
    assert bad.verdict is not OracleVerdict.PASS
    assert bad.verdict is OracleVerdict.FAIL, bad.reason_code
    assert bad.reason_code.startswith("YARA_DETECTION_MISMATCH")


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


# ---------------------------------------------------------------------------
# Y20–Y32 — the REAL CLI semantics: exit code 0 is not a match
# ---------------------------------------------------------------------------
#
# MEASURED, YARA 4.5.0:
#
#     match      exit 0, stdout "<rule identifier> <target>"
#     no match   exit 0, stdout ""
#     failure    non-zero, stderr diagnostic, stdout empty
#
# These tests are written against that behaviour rather than against the collector, and
# Y31 reinstates the old reading to prove they fail under it. The stub could not catch
# this defect because it encoded the defect: it answered `0 = match, 1 = no match`, so
# every test in this file agreed with the misreading and the suite stayed green.


def _all_four(**by_sample: Any) -> dict[str, Any]:
    """A per-sample record map, with the samples a test did not name defaulted."""
    records = {
        "holdout_positive_beacon.txt": _NO_MATCH,
        "holdout_positive_ecu.txt": _NO_MATCH,
        "holdout_negative_benign.txt": _NO_MATCH,
        "holdout_negative_clean.txt": _NO_MATCH,
    }
    records.update(by_sample)
    return records


def test_Y20_a_match_is_read_from_stdout_and_the_exit_code_is_zero(task, control) -> None:
    """Requirement Y1/Y3. A matching sample: exit 0, and stdout NAMES the submitted rule."""
    scanner = ScriptedYara(
        _all_four(
            **{
                "holdout_positive_beacon.txt": _MATCH,
                "holdout_positive_ecu.txt": _MATCH,
            }
        )
    )
    observation = _collect_with(task, control, scanner)

    assert observation.complete, observation.reason_code
    assert observation.values["matches"]["holdout_positive_beacon"] is True
    assert observation.values["matches"]["holdout_positive_ecu"] is True
    # The reading is a MATCH, and it arrived on a zero exit — but so does the reading
    # below, which is the point of the next test.
    assert {response.exit_code for response in scanner.responses} == {0}
    assert all(
        response.stdout.startswith("ai11_reference_answer ")
        for response in scanner.responses
        if response.stdout
    )


def test_Y21_the_exit_code_cannot_distinguish_a_match_from_a_non_match(task, control) -> None:
    """Requirement Y2/Y3. Two opposite readings, ONE exit code.

    This is the assertion that says the collector reads stdout rather than the exit
    code. A collector reading the exit code cannot produce both of these from the same
    input, so if either assertion below is dropped, the other stops proving anything.
    """
    scanner = ScriptedYara(
        _all_four(
            **{
                "holdout_positive_beacon.txt": _MATCH,
                "holdout_negative_clean.txt": _NO_MATCH,
            }
        )
    )
    observation = _collect_with(task, control, scanner)

    assert observation.complete, observation.reason_code
    assert observation.values["matches"]["holdout_positive_beacon"] is True
    assert observation.values["matches"]["holdout_negative_clean"] is False
    # Both readings came back on exit code 0. Nothing else about the two invocations
    # differs except stdout.
    assert {response.exit_code for response in scanner.responses} == {0}
    stdout = {
        Path(call[2]).name: response.stdout
        for call, response in zip(scanner.calls, scanner.responses)
    }
    assert stdout["holdout_positive_beacon.txt"].strip() != ""
    assert stdout["holdout_negative_clean.txt"] == ""


def test_Y22_output_that_is_not_a_match_record_is_not_a_match(task, control) -> None:
    """Requirement Y4. Non-empty stdout is not evidence of anything.

    Diagnostic text is not a match record, and a collector that answered "matched"
    because stdout had content in it would turn every warning into a detection.
    """
    noisy = ProcessResult(exit_code=0, stdout="warning: rule may slow down scanning\n")
    scanner = ScriptedYara({name: noisy for name in _all_four()})
    result = _evaluate(task, ReferenceVariant.KNOWN_GOOD, scanner)

    assert result.verdict is not OracleVerdict.PASS
    assert result.verdict is OracleVerdict.UNKNOWN
    assert result.reason_code == "YARA_SCANNER_OUTPUT_UNREADABLE"


def test_Y23_a_refused_rule_is_fail_with_the_counts_of_what_actually_ran(task, control) -> None:
    """Requirement Y5. The real CLI's compile-failure exit code is 1, not 2.

    Under the old reading, exit 1 meant "no match" — so a rule that does not compile was
    recorded as a rule that matched nothing, with all four samples marked executed. Both
    halves of that are false: the scanner refused the submission, and it was invoked
    once.
    """
    scanner = StubYara(
        failure='error: rule "ai11_reference_answer" in known_good.yar(9): '
        "syntax error, unexpected '}'"
    )
    result = _evaluate(task, ReferenceVariant.KNOWN_GOOD, scanner)

    assert result.verdict is OracleVerdict.FAIL
    assert result.verdict is not OracleVerdict.BLOCKED
    assert len(scanner.calls) == 1
    assert result.tests.planned == 4
    assert result.tests.executed == 1, "one invocation is one executed check"
    assert result.tests.failed == 1
    assert result.tests.skipped == 3


def test_Y24_an_environment_that_cannot_scan_observed_nothing(task, control) -> None:
    """Requirements Y6/Y7. An absent program and an expired budget are not non-matches.

    Both are BLOCKED with no observation at all, and neither may be reported as a match
    or a non-match: a host without `yara` would otherwise fail every correct rule it was
    given, which is the same class of error as the one this section corrects.
    """

    class SlowYara:
        def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
            return ProcessResult(exit_code=None, timed_out=True)

    absent = _collect_with(task, control, NoYara())
    assert not absent.complete
    assert absent.reason_code == "YARA_PROGRAM_UNAVAILABLE"
    assert absent.values == {}, "nothing was observed, so there is no reading to report"

    expired = _collect_with(task, control, SlowYara())
    assert not expired.complete
    assert expired.reason_code == "YARA_SCAN_TIMEOUT"
    assert expired.values == {}

    assert _evaluate(task, ReferenceVariant.KNOWN_GOOD, NoYara()).verdict is OracleVerdict.BLOCKED
    assert _evaluate(task, ReferenceVariant.KNOWN_GOOD, SlowYara()).verdict is OracleVerdict.BLOCKED


@pytest.mark.parametrize(
    ("stdout", "why"),
    [
        ("!! not a match record !!\n", "a line that is not a record at all"),
        ("ai11_reference_answer\n", "a record with no target"),
        ("someone_elses_rule sample.txt\n", "a record naming a rule nobody submitted"),
        (
            "ai11_reference_answer /elsewhere/other_sample.txt\n",
            "a record about a different target",
        ),
    ],
)
def test_Y25_unattributable_output_is_unknown_never_a_guess(control, stdout, why) -> None:
    """Requirement Y8. Output the collector cannot attribute produces UNKNOWN.

    Neither "matched" nor "did not match" is a claim this output supports, and the two
    wrong answers are wrong in opposite directions — one invents a detection, the other
    invents a miss.
    """
    record = ProcessResult(exit_code=0, stdout=stdout)
    scanner = ScriptedYara({name: record for name in _all_four()})
    truth = {
        "samples": {
            "holdout_positive_beacon": {
                "file": "holdout_positive_beacon.txt",
                "expected": True,
            }
        }
    }
    observation = collect(
        ORACLE_ID, {"rule_file": "known_good.yar"}, truth, control_dir=control, runner=scanner
    )

    assert not observation.complete, why
    assert observation.reason_code == "YARA_SCANNER_OUTPUT_UNREADABLE"
    assert observation.values == {}


# ---------------------------------------------------------------------------
# Y26–Y28 — the parser itself: records, not merely non-empty text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("", YaraReading.NOT_MATCHED),
        ("\n   \n", YaraReading.NOT_MATCHED),
        ("ai11_reference_answer sample.txt\n", YaraReading.MATCHED),
        (
            "ai11_reference_answer sample.txt\nai11_reference_answer sample.txt\n",
            YaraReading.MATCHED,
        ),
        ("ai11_reference_answer:tagged,tagged2 sample.txt\n", YaraReading.MATCHED),
        ("other_rule sample.txt\n", YaraReading.AMBIGUOUS),
        ("warning: rule may slow down scanning\n", YaraReading.AMBIGUOUS),
        ("ai11_reference_answer\n", YaraReading.AMBIGUOUS),
        ("ai11_reference_answer /elsewhere/other.txt\n", YaraReading.AMBIGUOUS),
        ("some prose that is not a record at all\n", YaraReading.AMBIGUOUS),
    ],
)
def test_Y26_the_parser_reports_what_the_scanner_said(stdout, expected) -> None:
    """The parser's whole job: scanner stdout -> matched / not matched / ambiguous.

    It compares nothing against truth and decides no verdict. A record is bound to the
    submitted rule AND to the scanned target, so neither a stray line nor a record about
    something else can become a detection.
    """
    assert parse_yara_matches(stdout, ("ai11_reference_answer",), target="sample.txt") is expected


def test_Y27_a_record_is_matched_by_identity_not_by_being_present() -> None:
    """One submitted rule matching is a match; one it did not submit is not attributable."""
    stdout = "second_rule sample.txt\n"
    assert parse_yara_matches(stdout, ["first_rule", "second_rule"], target="sample.txt") is (
        YaraReading.MATCHED
    )
    assert parse_yara_matches(stdout, ["first_rule"], target="sample.txt") is YaraReading.AMBIGUOUS
    # No declaration at all: nothing this output can be attributed to.
    assert parse_yara_matches(stdout, [], target="sample.txt") is YaraReading.AMBIGUOUS


def test_Y28_the_identity_comes_from_the_submitted_rule_not_from_this_repository(control) -> None:
    """The identifier is read out of the submitted file, so ANY rule is recognised.

    A collector that looked for a name written into itself would recognise the reference
    answer and nothing else — a discrimination control that cannot discriminate.
    """
    assert declared_rule_names((control / "known_good.yar").read_text(encoding="utf-8")) == (
        "ai11_reference_answer",
    )
    assert declared_rule_names((control / "known_bad.yar").read_text(encoding="utf-8")) == (
        "ai11_reference_false_positive",
    )
    # Comments are not declarations, and `private`/`global` are modifiers, not names.
    assert declared_rule_names(
        "/*\nrule commented_out {\n}\n*/\nprivate rule real_one : tag { condition: true }\n"
    ) == ("real_one",)


def test_Y29_a_rule_the_collector_has_never_seen_is_still_observed(task, control, tmp_path) -> None:
    """The same point, end to end: a rule name this repository has never heard of."""
    import shutil as _shutil

    custom = tmp_path / "control"
    _shutil.copytree(control, custom)
    (custom / "custom.yar").write_text(
        "rule a_rule_this_repository_never_declared { condition: true }\n", encoding="utf-8"
    )

    scanner = ScriptedYara(
        _all_four(**{name: _MATCH for name in _all_four()}),
        rule_name="a_rule_this_repository_never_declared",
    )
    observation = _collect_with(task, custom, scanner, rule_file="custom.yar")

    assert observation.complete, observation.reason_code
    assert set(observation.values["matches"].values()) == {True}


# ---------------------------------------------------------------------------
# Y30 — the reference fixtures, and the falsifiability of everything above
# ---------------------------------------------------------------------------


def test_Y30_the_reference_fixtures_agree_with_the_held_out_corpus(task, control) -> None:
    """Requirements Y9/Y10, on the corrected double.

    The declared CORRECT rule matches both positives and neither negative; the declared
    INCORRECT one false-positives on `holdout_negative_clean`, which is why it is the
    discrimination control. Both readings are asserted exactly, because a verdict alone
    would not show which samples produced it.
    """
    good = _collect_with(task, control, StubYara())
    assert good.complete, good.reason_code
    assert good.values["matches"] == {
        "holdout_positive_beacon": True,
        "holdout_positive_ecu": True,
        "holdout_negative_benign": False,
        "holdout_negative_clean": False,
    }
    assert _evaluate(task, ReferenceVariant.KNOWN_GOOD, StubYara()).verdict is OracleVerdict.PASS

    bad = _collect_with(task, control, StubYara(), rule_file="known_bad.yar")
    assert bad.complete, bad.reason_code
    assert bad.values["matches"]["holdout_negative_clean"] is True, "the declared false positive"
    assert bad.values["matches"]["holdout_negative_benign"] is False
    result = _evaluate(task, ReferenceVariant.KNOWN_BAD, StubYara())
    assert result.verdict is not OracleVerdict.PASS
    assert result.verdict is OracleVerdict.FAIL


def test_Y31_the_old_exit_code_reading_makes_these_tests_fail(task, control, monkeypatch) -> None:
    """Requirement Y11. Falsifiability, not coverage.

    The collector calls the parser only after a completed invocation, so a parser that
    answers MATCHED without reading stdout IS the old `exit_code == 0 -> matched`
    reading, reinstated. Under it the focused assertion must FAIL: it reports every
    sample as a hit, and the two held-out negatives become failures of a rule that
    correctly does not match them.

    This is the test that says the tests above can detect the defect. If this passes,
    one of them is not testing what it claims.
    """
    import benchmarks.oracles as oracles

    def exit_code_era(stdout, submitted_rule_names, *, target=None):  # noqa: ANN001, ANN202
        return YaraReading.MATCHED

    monkeypatch.setattr(oracles, "parse_yara_matches", exit_code_era)

    with pytest.raises(AssertionError):
        _assert_the_reference_rule_is_observed_correctly(task, control, StubYara())

    # And the end-to-end consequence, which is what the campaign record showed: a
    # correct rule, four executed checks, two failures.
    result = _evaluate(task, ReferenceVariant.KNOWN_GOOD, StubYara())
    assert result.verdict is OracleVerdict.FAIL
    assert result.tests.executed == 4
    assert result.tests.failed == 2


def test_Y32_the_double_speaks_the_contract_the_real_cli_was_measured_to_have(control) -> None:
    """A double that disagrees with its tool is worse than no double.

    The stub is asserted directly, because its OUTPUT is what the collector reads. When
    the stub encoded `0 = match, 1 = no match` this test would have failed, and the
    defect would have been caught at its source instead of in a campaign record.
    """
    rule = control / "known_good.yar"
    beacon = (control / "holdout_positive_beacon.txt").resolve()
    clean = (control / "holdout_negative_clean.txt").resolve()

    matched = StubYara().run(["yara", str(rule), str(beacon)], cwd=None, timeout_seconds=5)
    assert matched.exit_code == 0
    assert matched.stdout == f"ai11_reference_answer {beacon}\n"
    assert matched.stderr == ""

    missed = StubYara().run(["yara", str(rule), str(clean)], cwd=None, timeout_seconds=5)
    assert missed.exit_code == 0, "a non-match is NOT a non-zero exit — the CLI exits 0"
    assert missed.stdout == ""
    assert missed.stderr == ""

    refused = StubYara(failure='error: rule "x" in y.yar(1): syntax error').run(
        ["yara", str(rule), str(beacon)], cwd=None, timeout_seconds=5
    )
    assert refused.exit_code != 0
    assert refused.stdout == ""
    assert refused.stderr
