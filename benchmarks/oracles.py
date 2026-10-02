"""AI-11 §7 — the corpus oracles: collection, then judgement.

```text
submission  ->  COLLECT  ->  observation  ->  JUDGE  ->  counts  ->  apply_pass_rule
                 |                                          |
            may need a tool                            §11 decides
            may be BLOCKED
```

### Why collection and judgement are separate

They fail for different reasons and the difference is the whole of §8.2.

```text
collection fails   the tool is absent, the material is missing, the run timed out
                   -> BLOCKED, NOT_RUN or UNKNOWN. Nothing was observed.
judgement fails    the observation was made and the required assertion did not hold
                   -> FAIL. Something was observed and it was wrong.
```

If they were one function, "we could not look" and "we looked and it was wrong" would
leave through the same return, and the first would eventually be read as the second.

### `truth` is expected truth; an observation is not

For `ai11-v1-yara-rule-author` the oracle really executes: the submitted rule is run
against the held-out samples by the `yara` binary, and the MATCHES it reports are the
observation. `truth.json` says what the matches should be; it is never itself the
observation. A judge that compared `truth` to `truth` would pass every rule ever written,
including one that does not compile.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from benchmarks.errors import OracleProtocolError
from benchmarks.oracle import OracleResult, ProcessResult, apply_pass_rule
from benchmarks.run import TestCounts
from benchmarks.vocabulary import OracleVerdict

__all__ = [
    "COLLECTORS",
    "JUDGES",
    "Judgement",
    "Observation",
    "collect",
    "evaluate_submission",
    "judge_submission",
]


@dataclass(frozen=True, slots=True)
class Observation:
    """What collection actually observed, or why it observed nothing."""

    values: Mapping[str, Any] = field(default_factory=dict)
    #: False when the collection could not be made. The reason code and skip class
    #: decide the verdict, and §8.2 forbids any of them becoming PASS.
    complete: bool = True
    reason_code: str = ""
    skip_class: str = "NONE"
    planned: int = 0

    @property
    def unavailable(self) -> bool:
        return not self.complete


@dataclass(frozen=True, slots=True)
class Judgement:
    """What a judge concluded about a COMPLETE observation."""

    verdict: OracleVerdict
    tests: TestCounts
    reason_code: str


def _finish(checked: int, failures: Sequence[str], *, reason: str) -> Judgement:
    """Build counts and let §11 decide."""
    counts = TestCounts(
        planned=checked,
        executed=checked,
        passed=checked - len(failures),
        failed=len(failures),
        skipped=0,
    )
    verdict, final_counts, rule_reason = apply_pass_rule(counts, "NONE")
    # The SPECIFIC reason wins when there is one. `apply_pass_rule` reports the generic
    # ORACLE_REQUIRED_ASSERTION_FAILED, which says a check failed but not which; the
    # judge knows which, and a reason code that does not name the failing case sends a
    # reader back to the data.
    specific = f"{reason}:{failures[0]}" if failures else ""
    return Judgement(verdict=verdict, tests=final_counts, reason_code=specific or rule_reason)


def _require_mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OracleProtocolError(f"{where} must be a JSON object")
    return value


# ---------------------------------------------------------------------------
# collection
# ---------------------------------------------------------------------------


class Collector(Protocol):
    def __call__(
        self,
        submission: Mapping[str, Any],
        truth: Mapping[str, Any],
        *,
        control_dir: Path,
        runner: Any,
        timeout_seconds: int,
    ) -> Observation: ...


def _collect_identity(
    submission: Mapping[str, Any],
    truth: Mapping[str, Any],
    *,
    control_dir: Path,
    runner: Any,
    timeout_seconds: int,
) -> Observation:
    """The submission IS the observation.

    Used where the task's answer is a set of values produced by the Agent's own analysis
    (a decoded signal, a UDS triple, an inventory, a classification). There is nothing
    for a tool to add: the oracle's independence comes from the truth being tracked
    outside the workspace, not from re-running a scanner.
    """
    return Observation(values=submission, complete=True, planned=0)


#: `yara` exits 0 when a rule matched, 1 when it did not, and anything else is an
#: error. SecurityLab's own adapter declares the same pair for the same reason
#: (`tools/reverse_engineering/__init__.py`: a match is reported through the status).
YARA_MATCH = 0
YARA_NO_MATCH = 1


def _collect_yara(
    submission: Mapping[str, Any],
    truth: Mapping[str, Any],
    *,
    control_dir: Path,
    runner: Any,
    timeout_seconds: int,
) -> Observation:
    """§A.3. Run the SUBMITTED rule against the held-out samples with `yara`.

    The observation is what the scanner reported. It is not read from `truth`, and the
    submission does not carry a `matches` mapping it could have guessed: the only way
    into this observation is to have a rule and to run it.
    """
    samples = _require_mapping(truth.get("samples"), "truth.samples")
    planned = len(samples)
    if planned == 0:
        return Observation(
            complete=False, reason_code="YARA_NO_HELD_OUT_MATERIAL", skip_class="ENVIRONMENT"
        )

    rule = _require_mapping(submission, "submission")
    rule_file = rule.get("rule_file")
    if not isinstance(rule_file, str) or not rule_file:
        return Observation(
            complete=False,
            reason_code="YARA_NO_RULE_SUBMITTED",
            skip_class="INTENTIONAL",
            planned=planned,
        )

    # The rule is named relative to the control directory and resolved inside it. A
    # submission that named `../../etc/passwd` would be refused here rather than read.
    from benchmarks.paths import resolve_within

    try:
        rule_path = resolve_within(control_dir, rule_file, where="submitted rule")
    except Exception:  # noqa: BLE001 - a refused path is a refused submission
        return Observation(
            complete=False,
            reason_code="YARA_RULE_PATH_REFUSED",
            skip_class="INTENTIONAL",
            planned=planned,
        )
    if not rule_path.is_file():
        return Observation(
            complete=False,
            reason_code="YARA_RULE_NOT_FOUND",
            skip_class="INTENTIONAL",
            planned=planned,
        )

    matches: dict[str, bool] = {}
    for key, spec in sorted(samples.items()):
        entry = _require_mapping(spec, f"truth.samples[{key}]")
        sample = control_dir / str(entry.get("file", ""))
        if not sample.is_file():
            # §5.7: a missing prerequisite is BLOCKED. The required check did not run.
            return Observation(
                complete=False,
                reason_code=f"YARA_HELD_OUT_MATERIAL_MISSING:{key}",
                skip_class="ENVIRONMENT",
                planned=planned,
            )

        process = runner.run(
            ["yara", str(rule_path), str(sample)], cwd=None, timeout_seconds=timeout_seconds
        )
        if process.timed_out:
            return Observation(
                complete=False,
                reason_code="YARA_SCAN_TIMEOUT",
                skip_class="ENVIRONMENT",
                planned=planned,
            )
        if process.exit_code is None:
            # Nothing ran: the program is absent. BLOCKED, never FAIL.
            return Observation(
                complete=False,
                reason_code="YARA_PROGRAM_UNAVAILABLE",
                skip_class="ENVIRONMENT",
                planned=planned,
            )
        if process.exit_code == YARA_MATCH:
            matches[key] = True
        elif process.exit_code == YARA_NO_MATCH:
            matches[key] = False
        else:
            # The scanner ran and refused the rule. That is a bad SUBMISSION, not a bad
            # environment: the required check executed and its assertion failed.
            return Observation(
                values={"matches": matches, "compile_error": (process.stderr or "").strip()[:200]},
                complete=True,
                planned=planned,
            )

    return Observation(values={"matches": matches}, complete=True, planned=planned)


COLLECTORS: Mapping[str, Collector] = {
    "ai11-v1-yara-rule-author.oracle": _collect_yara,
}


def collect(
    oracle_id: str,
    submission: Mapping[str, Any],
    truth: Mapping[str, Any],
    *,
    control_dir: Path,
    runner: Any = None,
    timeout_seconds: int = 120,
) -> Observation:
    """Run the declared collector, or the identity collector when none is declared."""
    collector = COLLECTORS.get(oracle_id, _collect_identity)
    return collector(
        submission, truth, control_dir=control_dir, runner=runner, timeout_seconds=timeout_seconds
    )


# ---------------------------------------------------------------------------
# judgement
# ---------------------------------------------------------------------------


def _judge_exact_keys(observation: Mapping[str, Any], truth: Mapping[str, Any]) -> Judgement:
    """Field-by-field equality, for answers made of discrete values."""
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    got = _require_mapping(observation.get("answer"), "observation.answer")

    failures = [field for field, want in sorted(expected.items()) if got.get(field, None) != want]
    return _finish(len(expected), failures, reason="EXACT_FIELD_MISMATCH")


def _judge_numeric_tolerance(
    observation: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """Physical quantities, compared within a DECLARED tolerance.

    The tolerance is tracked truth, not a constant in this file: one chosen in code is
    one nobody reviewed, and a decode check that is too tight fails correct work while
    one that is too loose passes incorrect work.
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    tolerance = _require_mapping(truth.get("tolerance"), "truth.tolerance")
    got = _require_mapping(observation.get("answer"), "observation.answer")

    failures: list[str] = []
    for signal, want in sorted(expected.items()):
        have = got.get(signal, None)
        if not isinstance(have, (int, float)) or isinstance(have, bool):
            failures.append(signal)
            continue
        if abs(float(have) - float(want)) > float(tolerance.get(signal, 0)):
            failures.append(signal)
    return _finish(len(expected), failures, reason="VALUE_OUTSIDE_DECLARED_TOLERANCE")


def _judge_uds_triples(observation: Mapping[str, Any], truth: Mapping[str, Any]) -> Judgement:
    """The `(service, NRC, violated precondition)` triple, per case."""
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    answers = _require_mapping(observation.get("answer"), "observation.answer")

    failures: list[str] = []
    for case_id, want in sorted(expected.items()):
        want_map = _require_mapping(want, f"truth.expected[{case_id}]")
        have = answers.get(case_id)
        if not isinstance(have, Mapping):
            failures.append(case_id)
            continue
        if any(have.get(field, None) != value for field, value in sorted(want_map.items())):
            failures.append(case_id)
    return _finish(len(expected), failures, reason="UDS_TRIPLE_MISMATCH")


def _judge_yara_detection(observation: Mapping[str, Any], truth: Mapping[str, Any]) -> Judgement:
    """The OBSERVED matches against the expected ones.

    A rule that failed to compile observed no matches at all and is FAIL: the scan ran
    and the submission was refused, which is an assertion failure rather than an
    environment problem (§8.2).

    A false positive is not traded against a true positive. Every sample is a required
    check, so §11 requires all of them.
    """
    samples = _require_mapping(truth.get("samples"), "truth.samples")
    if observation.get("compile_error") is not None:
        counts = TestCounts(planned=len(samples), executed=len(samples),
                            passed=0, failed=len(samples), skipped=0)
        return Judgement(
            verdict=OracleVerdict.FAIL,
            tests=counts,
            reason_code="YARA_RULE_DID_NOT_COMPILE",
        )

    matches = _require_mapping(observation.get("matches"), "observation.matches")
    failures: list[str] = []
    for key, spec in sorted(samples.items()):
        entry = _require_mapping(spec, f"truth.samples[{key}]")
        want = entry.get("expected")
        if not isinstance(want, bool):
            raise OracleProtocolError(f"truth.samples[{key}].expected must be a boolean")
        if matches.get(key, None) is not want:
            failures.append(key)
    return _finish(len(samples), failures, reason="YARA_DETECTION_MISMATCH")


def _judge_fuzz_classification(
    observation: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """The frozen `CLASS_PRIORITY` classification, per case.

    When the kernel oracle is not AVAILABLE its observation is `null` in the truth —
    never `0` and never an empty list — and a submission that reports a kernel
    observation anyway is wrong rather than lucky.
    """
    priority: Sequence[str] = truth.get("class_priority", ())
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    answers = _require_mapping(observation.get("answer"), "observation.answer")

    failures: list[str] = []
    for case_id, want in sorted(expected.items()):
        want_map = _require_mapping(want, f"truth.expected[{case_id}]")
        have = answers.get(case_id)
        if not isinstance(have, Mapping):
            failures.append(case_id)
            continue

        want_class = want_map.get("class")
        if want_class not in priority:
            raise OracleProtocolError(
                f"truth.expected[{case_id}].class {want_class!r} is not a member of the "
                "frozen class priority; truth outside the frozen vocabulary is not truth "
                "this oracle can use"
            )
        if have.get("class") != want_class:
            failures.append(case_id)
            continue

        want_kernel = want_map.get("kernel_oracle")
        want_events = want_map.get("kernel_events", None)
        have_events = have.get("kernel_events", None)

        if want_kernel not in ("AVAILABLE", "UNAVAILABLE", "ERROR"):
            raise OracleProtocolError(
                f"truth.expected[{case_id}].kernel_oracle {want_kernel!r} is not one of "
                "AVAILABLE, UNAVAILABLE or ERROR"
            )
        if want_kernel != "AVAILABLE":
            if want_events is not None:
                raise OracleProtocolError(
                    f"truth.expected[{case_id}] carries kernel_events under a "
                    f"{want_kernel} kernel oracle; SecurityLab's own rule is that an "
                    "unavailable oracle records null, never zero"
                )
            if have_events is not None:
                failures.append(case_id)
            continue
        if have_events != want_events:
            failures.append(case_id)

    return _finish(len(expected), failures, reason="FUZZ_CLASSIFICATION_MISMATCH")


JUDGES: Mapping[str, Callable[[Mapping[str, Any], Mapping[str, Any]], Judgement]] = {
    "ai11-v1-can-dbc-decode.oracle": _judge_numeric_tolerance,
    "ai11-v1-uds-nrc-triage.oracle": _judge_uds_triples,
    "ai11-v1-yara-rule-author.oracle": _judge_yara_detection,
    "ai11-v1-firmware-syn-ecu-inventory.oracle": _judge_exact_keys,
    "ai11-v1-reverse-arm64-triage.oracle": _judge_exact_keys,
    "ai11-v1-fuzzing-recovery-triage.oracle": _judge_fuzz_classification,
}


def judge_submission(
    oracle_id: str, observation: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """Dispatch to the declared judge over a COMPLETE observation."""
    judge = JUDGES.get(oracle_id)
    if judge is None:
        raise OracleProtocolError(
            f"no judge is registered for oracle_id {oracle_id!r}. Registered: "
            f"{sorted(JUDGES)}"
        )
    return judge(observation, truth)


# ---------------------------------------------------------------------------
# the whole oracle, as the runner calls it
# ---------------------------------------------------------------------------


def evaluate_submission(
    *,
    oracle_id: str,
    required: bool,
    submission: Mapping[str, Any],
    truth: Mapping[str, Any],
    control_dir: Path,
    runner: Any = None,
    timeout_seconds: int = 120,
) -> OracleResult:
    """Collect, then judge, and map an incomplete collection to its §8 verdict.

    This is the ONE place an in-process oracle becomes an `OracleResult`, so the
    BLOCKED / NOT_RUN / UNKNOWN mapping exists once rather than once per task.
    """
    observation = collect(
        oracle_id,
        submission,
        truth,
        control_dir=control_dir,
        runner=runner,
        timeout_seconds=timeout_seconds,
    )

    if observation.unavailable:
        planned = max(observation.planned, 1)
        counts = TestCounts(planned=planned, executed=0, passed=0, failed=0, skipped=planned)
        verdict, _, _ = apply_pass_rule(counts, observation.skip_class)
        return OracleResult(
            oracle_id=oracle_id,
            required=required,
            verdict=verdict,
            tests=counts,
            reason_code=observation.reason_code,
            # A ONE-ELEMENT TUPLE, and the trailing comma is the whole point. Without
            # it the parentheses are grouping and the field holds a bare string, which
            # `BenchmarkRun` then iterates character by character — reporting the
            # limitation code "O".
            limitations=(
                (f"ORACLE_MATERIAL_UNAVAILABLE:{observation.reason_code}",)
                if verdict is OracleVerdict.BLOCKED
                else ()
            ),
        )

    judgement = judge_submission(oracle_id, observation.values, truth)
    return OracleResult(
        oracle_id=oracle_id,
        required=required,
        verdict=judgement.verdict,
        tests=judgement.tests,
        reason_code=judgement.reason_code,
    )
