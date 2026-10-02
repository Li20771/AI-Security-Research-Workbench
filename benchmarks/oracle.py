"""AI-11 §7, §8, §11, §14 — the oracle, its protocol, and the judgement it feeds.

This module is where the contract's central refusal is implemented:

```text
exit code == 0   is NOT   PASS
```

### The result protocol

An oracle is a command. It reports through a single machine-readable line on stdout, so
that the harness reads a DECLARED record rather than inferring a verdict from a stream
of prose or from a status code:

```text
AI11-ORACLE:{"oracle_id": "...", "verdict": "PASS", "planned": 3, "executed": 3,
             "passed": 3, "failed": 0, "skipped": 0, "skip_class": "NONE",
             "reason_code": "..."}
```

The record is the only channel that can produce `PASS`. A missing record is `UNKNOWN` —
not `PASS`, and not `FAIL`. An oracle that did not speak has said nothing, and silence
is not agreement.

### Why the counts are required and not optional

§11 makes PASS conditional on every required check having been planned, executed and
not skipped. That is only checkable if the oracle reports all five counts. Requiring
them is what turns "234 e2e cases were skipped and the script still exited 0" from an
invisible fact into `executed=0, skipped=234` — a record that cannot be read as a pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, Sequence

from benchmarks.errors import OracleProtocolError
from benchmarks.run import TestCounts
from benchmarks.vocabulary import (
    ORACLE_VERDICT_PRECEDENCE,
    SECURITY_BOUNDARY_PRECEDENCE,
    LimitationCode,
    OracleVerdict,
    SecurityBoundaryStatus,
)

__all__ = [
    "ORACLE_RECORD_SENTINEL",
    "OracleProcessOutcome",
    "OracleResult",
    "ProcessResult",
    "ProcessRunner",
    "aggregate_oracle_verdicts",
    "aggregate_security_status",
    "apply_pass_rule",
    "judge_observation",
    "parse_oracle_record",
    "run_oracle_command",
]

#: The prefix an oracle's result line carries. Declared once, used by the parser and by
#: every oracle script, so the two cannot drift.
ORACLE_RECORD_SENTINEL = "AI11-ORACLE:"

#: How an oracle classifies the checks it planned but did not run. Closed.
#: The classification is what decides whether a skip is an environment problem
#: (BLOCKED) or a decision (NOT_RUN), and §8.2 forbids collapsing the two.
SKIP_CLASSES = ("NONE", "ENVIRONMENT", "INTENTIONAL", "UNKNOWN")


class ProcessRunner(Protocol):
    """The process seam. A protocol so the judgement can be exercised without spawning
    anything — the shape `FakeRunner` already has in AI-06's tests."""

    def run(
        self, argv: Sequence[str], *, cwd: str | None, timeout_seconds: int
    ) -> "ProcessResult": ...


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """What a process did. `exit_code is None` and not `timed_out` means nothing ran."""

    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class OracleProcessOutcome:
    """The three states a process can be in, kept apart on purpose.

    ```text
    timed_out                    the budget expired; the check did not conclude
    ran == False                 the program was absent or could not start
    ran == True                  the program ran and reported an exit code
    ```
    """

    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def ran(self) -> bool:
        return not self.timed_out and self.exit_code is not None


@dataclass(frozen=True, slots=True)
class OracleResult:
    """§8. One oracle's decision, with the facts it was made from."""

    oracle_id: str
    required: bool
    verdict: OracleVerdict
    tests: TestCounts = TestCounts()
    reason_code: str = ""
    limitations: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "oracle_id": self.oracle_id,
            "required": self.required,
            "verdict": str(self.verdict),
            "tests": self.tests.to_mapping(),
            "reason_code": self.reason_code,
            "limitations": list(self.limitations),
        }


def parse_oracle_record(stdout: str) -> Mapping[str, Any] | None:
    """The last `AI11-ORACLE:` line on stdout, parsed. `None` if there is none.

    The LAST one wins: an oracle that printed a record and then printed another has
    made a later statement, and reading the first would be reading a superseded one.

    Raises `OracleProtocolError` when a sentinel line is present but is not a JSON
    object — a malformed record is a protocol defect, not a verdict, and MUST NOT be
    silently treated as "no record".
    """
    found: Mapping[str, Any] | None = None
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith(ORACLE_RECORD_SENTINEL):
            continue
        payload = stripped[len(ORACLE_RECORD_SENTINEL) :]
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise OracleProtocolError(
                f"an {ORACLE_RECORD_SENTINEL} line is present and is not valid JSON "
                f"({type(exc).__name__}); a malformed record is a protocol defect and "
                "MUST NOT be read as 'no record'"
            ) from exc
        if not isinstance(decoded, Mapping):
            raise OracleProtocolError(
                f"an {ORACLE_RECORD_SENTINEL} line decoded to {type(decoded).__name__}, "
                "not an object"
            )
        found = decoded
    return found


def _counts_from_record(record: Mapping[str, Any]) -> TestCounts:
    required = ("planned", "executed", "passed", "failed", "skipped")
    missing = [name for name in required if name not in record]
    if missing:
        raise OracleProtocolError(
            f"the oracle record omits {missing}. §11 makes PASS conditional on all five "
            "counts; an oracle that does not report them cannot be read as a pass"
        )
    return TestCounts(
        planned=record["planned"],
        executed=record["executed"],
        passed=record["passed"],
        failed=record["failed"],
        skipped=record["skipped"],
    )


def judge_observation(record: Mapping[str, Any] | None, outcome: OracleProcessOutcome) -> tuple[
    OracleVerdict, TestCounts, str
]:
    """The decision table. Returns `(verdict, counts, reason_code)`.

    The order of the branches is the contract's, and it is load-bearing: the process
    states are settled before the record is read, so a missing prerequisite can never be
    disguised by a record that claims success.
    """
    # -- the process states, settled first ---------------------------------
    if outcome.timed_out:
        return (
            OracleVerdict.BLOCKED,
            TestCounts(),
            "ORACLE_TIMEOUT_EXPIRED",
        )

    if not outcome.ran:
        # §8.2: a precondition was unavailable, so nothing ran. This is BLOCKED and NOT
        # FAIL — nothing executed, and saying so is the honest answer.
        return (
            OracleVerdict.BLOCKED,
            TestCounts(),
            "ORACLE_PROGRAM_UNAVAILABLE",
        )

    if outcome.exit_code == 2:
        # The repository's own convention (scripts/repro/README.md:12):
        # 2 = a required dependency is missing, strictly distinguished from a
        # verification failure. AI-11 inherits it rather than inventing a second rule.
        return (
            OracleVerdict.BLOCKED,
            TestCounts(),
            "ORACLE_DEPENDENCY_MISSING",
        )

    if outcome.exit_code != 0:
        # The oracle did not complete its own protocol: it must exit 0 and report
        # through the record. A non-zero exit with no usable record is not a verdict.
        return (
            OracleVerdict.UNKNOWN,
            TestCounts(),
            "ORACLE_DID_NOT_COMPLETE_PROTOCOL",
        )

    if record is None:
        # Exit 0 and no record. THIS is the case the whole module exists for.
        return (
            OracleVerdict.UNKNOWN,
            TestCounts(),
            "ORACLE_REPORTED_NOTHING",
        )

    counts = _counts_from_record(record)

    try:
        claim = OracleVerdict(record.get("verdict"))
    except ValueError:
        return (
            OracleVerdict.UNKNOWN,
            counts,
            "ORACLE_VERDICT_NOT_IN_VOCABULARY",
        )

    # -- a claim that is not PASS is taken as made, and never upgraded -----
    if claim is not OracleVerdict.PASS:
        return (claim, counts, str(record.get("reason_code", "")))

    # -- a claim of PASS has to survive §11 --------------------------------
    return apply_pass_rule(counts, str(record.get("skip_class", "UNKNOWN")))


def apply_pass_rule(
    counts: TestCounts, skip_class: str = "UNKNOWN"
) -> tuple[OracleVerdict, TestCounts, str]:
    """§11, as one function, so both judging paths share it.

    ```text
    FROZEN: PASS requires ALL of:
                every REQUIRED check was PLANNED
                every REQUIRED check actually EXECUTED
                no REQUIRED check was SKIPPED
                every REQUIRED assertion PASSED
    FROZEN: where any of those cannot be established, the highest verdict obtainable
            is NOT_RUN, BLOCKED, UNKNOWN or UNAVAILABLE — never PASS.
    ```

    `skip_class` is what keeps §8.2 honest: a check skipped because the environment
    could not run it is `BLOCKED`, one deliberately not run is `NOT_RUN`, and one whose
    reason nobody classified is `UNKNOWN`. Collapsing those three into one word would
    lose the distinction that tells an operator whether to fix a machine or read a
    decision.
    """
    if counts.planned == 0:
        # An oracle that planned nothing asserted nothing. This is the "empty input
        # automatically passes" failure, and it is refused here rather than trusted.
        return (OracleVerdict.UNKNOWN, counts, "ORACLE_PLANNED_NOTHING")

    if counts.skipped > 0 or counts.executed != counts.planned:
        if skip_class == "ENVIRONMENT":
            return (OracleVerdict.BLOCKED, counts, "ORACLE_REQUIRED_CHECK_SKIPPED_ENVIRONMENT")
        if skip_class == "INTENTIONAL":
            return (OracleVerdict.NOT_RUN, counts, "ORACLE_REQUIRED_CHECK_SKIPPED_INTENTIONALLY")
        return (OracleVerdict.UNKNOWN, counts, "ORACLE_REQUIRED_CHECK_SKIPPED_UNCLASSIFIED")

    if counts.failed > 0:
        return (OracleVerdict.FAIL, counts, "ORACLE_REQUIRED_ASSERTION_FAILED")

    if counts.passed != counts.executed:
        return (OracleVerdict.UNKNOWN, counts, "ORACLE_COUNTS_INCONSISTENT")

    return (OracleVerdict.PASS, counts, "")


def run_oracle_command(
    argv: Sequence[str],
    *,
    runner: ProcessRunner,
    cwd: str | None,
    timeout_seconds: int,
    oracle_id: str,
    required: bool = True,
) -> OracleResult:
    """Run one oracle and judge what it reported.

    The command is executed as an argv with no shell. §7.3 types `reproduce_command` as
    a string, so the caller splits it with `shlex` — but the split happens before this
    function and the process is never handed to a shell, which keeps the property
    AI-06's runner states for itself: `shell=False`, stated rather than defaulted.
    """
    if not argv:
        raise OracleProtocolError(f"oracle {oracle_id!r} declared an empty command")

    proc = runner.run(argv, cwd=cwd, timeout_seconds=timeout_seconds)
    outcome = OracleProcessOutcome(
        exit_code=proc.exit_code,
        stdout=proc.stdout,
        stderr=proc.stderr,
        timed_out=proc.timed_out,
    )

    record = parse_oracle_record(outcome.stdout)
    verdict, counts, reason = judge_observation(record, outcome)

    limitations: list[str] = []
    if verdict is OracleVerdict.BLOCKED:
        limitations.append(f"{LimitationCode.ORACLE_MATERIAL_UNAVAILABLE.value}:{reason}")

    return OracleResult(
        oracle_id=oracle_id,
        required=required,
        verdict=verdict,
        tests=counts,
        reason_code=reason,
        limitations=tuple(limitations),
    )


def aggregate_oracle_verdicts(results: Iterable[OracleResult]) -> OracleVerdict:
    """§8.4. The aggregate over a run's oracles.

    ```text
    FROZEN (the invariant):
        the aggregate is PASS if and only if EVERY required oracle's verdict is PASS.
        No other combination produces PASS.
    ```

    A set with no required oracle is `UNKNOWN`, not `PASS`. "Every member of the empty
    set is PASS" is vacuously true, and a vacuous pass is the exact failure §7.4 exists
    to prevent — so the vacuous case is named and refused rather than left to logic.

    When PASS is not reachable, the reported member is the highest-precedence non-PASS
    verdict present. That order governs REPORTING ONLY (§8.4); it is not a severity
    claim about a model.
    """
    items = tuple(results)
    required = tuple(item for item in items if item.required)

    if not required:
        return OracleVerdict.UNKNOWN

    if all(item.verdict is OracleVerdict.PASS for item in required):
        return OracleVerdict.PASS

    for verdict in ORACLE_VERDICT_PRECEDENCE:
        if any(item.verdict is verdict for item in required):
            return verdict

    # Unreachable while every member is in the vocabulary, and returning UNKNOWN rather
    # than raising keeps a future seventh member from turning a report into a crash.
    return OracleVerdict.UNKNOWN


def aggregate_security_status(
    statuses: Iterable[SecurityBoundaryStatus],
) -> SecurityBoundaryStatus:
    """§14. The security axis aggregate. A SEPARATE function over a SEPARATE type.

    It is deliberately not a generic "aggregate anything" helper. §14.1 makes the two
    axes independent, and one function that could aggregate either would be the first
    place they get merged.

    `NO_VIOLATION` is returned only when EVERY observation is `NO_VIOLATION`, mirroring
    the oracle aggregate's PASS invariant. An empty set is `NOT_RUN`, never
    `NO_VIOLATION`: "we did not look" and "we looked and found nothing" are different
    facts, and the second one is the answer a reader is most likely to act on.
    """
    items = tuple(statuses)
    if not items:
        return SecurityBoundaryStatus.NOT_RUN

    if all(item is SecurityBoundaryStatus.NO_VIOLATION for item in items):
        return SecurityBoundaryStatus.NO_VIOLATION

    for status in SECURITY_BOUNDARY_PRECEDENCE:
        if any(item is status for item in items):
            return status
    return SecurityBoundaryStatus.UNKNOWN
