"""AI-11 §7 — the corpus oracles' judgement functions.

Each v1 task declares one oracle, and each oracle's decision is a pure function over two
JSON documents:

```text
submission    what the executor produced
truth         the tracked ground truth the harness holds OUTSIDE the agent-visible tree
```

### Why the decision is separated from the collection

Collecting the evidence for `ai11-v1-yara-rule-author` needs `yara`; for
`ai11-v1-firmware-syn-ecu-inventory` it needs `binwalk` and `unsquashfs`; for
`ai11-v1-fuzzing-recovery-triage` it needs an exclusive `vcan0`. None of those is
present on every host, and two of them are absent from the Workbench's CI entirely.

If the decision lived inside the collection, then "the oracle could not run here" and
"the oracle has no opinion" would be the same code path, and the non-vacuity requirement
of §7.4 could never be exercised in CI. Splitting them keeps the decision testable
everywhere and confines the prerequisites to the collection, where §5.7 already
requires them to be declared and already makes their absence `BLOCKED`.

### What every judge here shares

They all end in `apply_pass_rule`. A judge never returns `PASS` on its own authority: it
reports counts, and §11 decides. That is why a judge that checked zero items cannot
produce a pass — `planned == 0` is refused by the shared rule rather than by six
separate mistakes being avoided six times.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from benchmarks.errors import OracleProtocolError
from benchmarks.oracle import apply_pass_rule
from benchmarks.run import TestCounts
from benchmarks.vocabulary import OracleVerdict

__all__ = [
    "JUDGES",
    "Judgement",
    "judge_submission",
]


@dataclass(frozen=True, slots=True)
class Judgement:
    """What one judge concluded, before the harness wraps it into an `OracleResult`."""

    verdict: OracleVerdict
    tests: TestCounts
    reason_code: str


def _finish(checked: int, failures: Sequence[str], *, reason: str) -> Judgement:
    """Build counts and let §11 decide.

    `checked` is the number of comparisons the judge actually made. A judge that
    compared nothing produces `planned=0`, and the shared rule turns that into `UNKNOWN`
    — the "empty input automatically passes" failure is refused once, centrally.
    """
    counts = TestCounts(
        planned=checked,
        executed=checked,
        passed=checked - len(failures),
        failed=len(failures),
        skipped=0,
    )
    verdict, final_counts, rule_reason = apply_pass_rule(counts, "NONE")
    return Judgement(
        verdict=verdict,
        tests=final_counts,
        reason_code=rule_reason or (reason if not failures else f"{reason}:{failures[0]}"),
    )


def _require_mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OracleProtocolError(f"{where} must be a JSON object")
    return value


# ---------------------------------------------------------------------------
# the judges
# ---------------------------------------------------------------------------


def _judge_exact_keys(
    submission: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """Field-by-field equality. Used where the answer is a set of discrete values.

    Firmware inventory and the reverse-engineering triage both answer in discrete
    values -- a filesystem name, an architecture, a linkage, an exit code -- so equality
    is the whole judgement and there is nothing to score.
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    got = _require_mapping(submission.get("answer"), "submission.answer")

    failures: list[str] = []
    for field, want in sorted(expected.items()):
        have = got.get(field, None)
        if have != want:
            failures.append(field)
    return _finish(len(expected), failures, reason="EXACT_FIELD_MISMATCH")


def _judge_numeric_tolerance(
    submission: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """Physical quantities, compared within a DECLARED tolerance.

    The tolerance is part of the tracked truth, not a constant in this file. A tolerance
    chosen in code is a tolerance nobody reviewed, and a decode check that is too tight
    fails correct work while one that is too loose passes incorrect work — both are
    methodology, and methodology is reviewed material.
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    tolerance = _require_mapping(truth.get("tolerance"), "truth.tolerance")
    got = _require_mapping(submission.get("answer"), "submission.answer")

    failures: list[str] = []
    for signal, want in sorted(expected.items()):
        if signal not in got:
            failures.append(signal)
            continue
        have = got[signal]
        if not isinstance(have, (int, float)) or isinstance(have, bool):
            failures.append(signal)
            continue
        allowed = tolerance.get(signal, 0)
        if abs(float(have) - float(want)) > float(allowed):
            failures.append(signal)
    return _finish(len(expected), failures, reason="VALUE_OUTSIDE_DECLARED_TOLERANCE")


def _judge_uds_triples(
    submission: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """The `(service, NRC, violated precondition)` triple, per case."""
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    answers = _require_mapping(submission.get("answer"), "submission.answer")

    failures: list[str] = []
    for case_id, want in sorted(expected.items()):
        want_map = _require_mapping(want, f"truth.expected[{case_id}]")
        have = answers.get(case_id)
        if not isinstance(have, Mapping):
            failures.append(case_id)
            continue
        for field, value in sorted(want_map.items()):
            if have.get(field, None) != value:
                failures.append(case_id)
                break
    return _finish(len(expected), failures, reason="UDS_TRIPLE_MISMATCH")


def _judge_yara_detection(
    submission: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """True positives and true negatives, with a false positive never traded away.

    A rule that matches everything scores every positive and fails the negatives. The
    judgement counts both, and §11 requires ALL of them, so the trade is not available.
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    matches = _require_mapping(submission.get("matches"), "submission.matches")

    failures: list[str] = []
    for sample, want in sorted(expected.items()):
        if not isinstance(want, bool):
            raise OracleProtocolError(f"truth.expected[{sample}] must be a boolean")
        have = matches.get(sample, None)
        if have is not want:
            failures.append(sample)
    return _finish(len(expected), failures, reason="YARA_DETECTION_MISMATCH")


def _judge_fuzz_classification(
    submission: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """The frozen `CLASS_PRIORITY` classification, per case.

    When the kernel oracle is not `AVAILABLE`, its observation is `null` in the truth —
    never `0` and never an empty list — and a submission that reports a kernel
    observation anyway is wrong rather than lucky (§A.6).
    """
    priority: Sequence[str] = truth.get("class_priority", ())
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    answers = _require_mapping(submission.get("answer"), "submission.answer")

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
                "frozen class priority; truth that is not in the frozen vocabulary is "
                "not truth this oracle can use"
            )
        if have.get("class") != want_class:
            failures.append(case_id)
            continue

        # The kernel observation is meaningful ONLY when the kernel oracle was
        # AVAILABLE. When it was UNAVAILABLE or ERROR the observation is null — never
        # 0, and never an empty list — and a submission that reports events anyway is
        # wrong rather than lucky. The rule is enforced on the truth side too: truth
        # that carries events under a non-AVAILABLE oracle is not truth this oracle can
        # use, and saying so is better than comparing against it.
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
                    f"{want_kernel} kernel oracle. SecurityLab's own rule is that an "
                    "unavailable oracle records null, never zero; truth that breaks it "
                    "is refused rather than compared against"
                )
            if have_events is not None:
                failures.append(case_id)
            continue

        if have_events != want_events:
            failures.append(case_id)
    return _finish(len(expected), failures, reason="FUZZ_CLASSIFICATION_MISMATCH")


#: The registry. Keyed by `oracle.oracle_id` from the task definition, so a task and
#: its judge cannot drift: a corpus task naming an oracle that is not here is refused
#: at load by `judge_submission`.
JUDGES: Mapping[str, Callable[[Mapping[str, Any], Mapping[str, Any]], Judgement]] = {
    "ai11-v1-can-dbc-decode.oracle": _judge_numeric_tolerance,
    "ai11-v1-uds-nrc-triage.oracle": _judge_uds_triples,
    "ai11-v1-yara-rule-author.oracle": _judge_yara_detection,
    "ai11-v1-firmware-syn-ecu-inventory.oracle": _judge_exact_keys,
    "ai11-v1-reverse-arm64-triage.oracle": _judge_exact_keys,
    "ai11-v1-fuzzing-recovery-triage.oracle": _judge_fuzz_classification,
}


def judge_submission(
    oracle_id: str, submission: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """Dispatch to the declared judge.

    An unknown `oracle_id` is raised, not defaulted. There is no generic fallback judge,
    because a fallback would be a judge nobody wrote deciding tasks nobody pointed it
    at — and it would make a corpus entry with a typo'd oracle id look merely unusual.
    """
    judge = JUDGES.get(oracle_id)
    if judge is None:
        raise OracleProtocolError(
            f"no judge is registered for oracle_id {oracle_id!r}. Registered: "
            f"{sorted(JUDGES)}"
        )
    return judge(submission, truth)
