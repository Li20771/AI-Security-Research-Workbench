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

import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Collection, Mapping, Protocol, Sequence

from benchmarks.decoders import (
    InspectionUnavailable,
    decode_dbc_frame,
    inspect_elf,
    inspect_firmware,
    run_binary,
)
from benchmarks.errors import OracleProtocolError, WorkspaceDerivationError
from benchmarks.paths import resolve_within
from benchmarks.oracle import OracleResult, apply_pass_rule
from benchmarks.run import TestCounts
from benchmarks.vocabulary import OracleVerdict

__all__ = [
    "COLLECTORS",
    "JUDGES",
    "Judgement",
    "Observation",
    "OracleContext",
    "YaraMatchRecord",
    "YaraReading",
    "collect",
    "declared_rule_names",
    "evaluate_submission",
    "judge_submission",
    "parse_yara_matches",
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


@dataclass(frozen=True, slots=True)
class OracleContext:
    """Everything a collector may read.

    `control_dir` holds the oracle's own material. `source_root` and `setup_dir` hold the
    PINNED material and the artefacts the harness BUILT from it -- which is where an
    independent observation comes from. `workspace_root` is the agent-visible tree and is
    deliberately NOT used by any derivation: an oracle that read the answer out of the
    tree the Agent wrote would be reading the Agent's own work back.
    """

    control_dir: Path
    source_root: Path | None = None
    setup_dir: Path | None = None
    workspace_root: Path | None = None
    runner: Any = None
    timeout_seconds: int = 120


class Collector(Protocol):
    def __call__(
        self, submission: Mapping[str, Any], truth: Mapping[str, Any], context: OracleContext
    ) -> "Observation": ...


def _digest(path: Path) -> str:
    """A recorded fact about a built artefact. Never asserted as truth.

    `build_fw.sh` calls `mksquashfs` without a reproducible-time flag, so the image
    digest is NOT stable across runs. It is recorded because a reader wants to know which
    image was measured; it is never compared against a frozen value.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blocked(reason_code: str, *, skip_class: str, planned: int) -> "Observation":
    return Observation(
        complete=False, reason_code=reason_code, skip_class=skip_class, planned=planned
    )


def _resolve_sample(control_dir: Path, name: object, where: str) -> Path:
    """Resolve one material file INSIDE the control directory.

    The control corpus is tracked and trusted, and the boundary is still closed
    structurally: a truth file is DATA, and data that names a location can name the wrong
    one. `resolve_within` refuses absolute paths, drive letters, UNC paths, backslashes
    and `..`, so a corrupted or hand-edited truth cannot point the scanner outside.
    """
    if not isinstance(name, str) or not name:
        raise OracleProtocolError(f"{where} must name a file")
    path = resolve_within(control_dir, name, where=where)
    if not path.is_file():
        raise OracleProtocolError(f"{where} names {name!r}, which is not a file")
    return path


# ---------------------------------------------------------------------------
# collectors
# ---------------------------------------------------------------------------


def _collect_can(
    submission: Mapping[str, Any], truth: Mapping[str, Any], context: OracleContext
) -> "Observation":
    """A.1. Decode the frame in the HARNESS and compare to the submission.

    The observation is what the harness decoder read out of the pinned DBC and the frozen
    frame. The submission's numbers are never the observation; they are what the
    observation is compared against.
    """
    dbc_rel = truth.get("dbc")
    frame = truth.get("frame")
    if not isinstance(dbc_rel, str) or not isinstance(frame, str):
        return _blocked("CAN_TRUTH_INCOMPLETE", skip_class="ENVIRONMENT", planned=0)
    if context.source_root is None:
        return _blocked("CAN_SOURCE_ROOT_ABSENT", skip_class="ENVIRONMENT", planned=0)

    try:
        dbc_path = resolve_within(context.source_root, dbc_rel, where="truth.dbc")
    except WorkspaceDerivationError:
        return _blocked("CAN_DBC_PATH_REFUSED", skip_class="ENVIRONMENT", planned=0)
    if not dbc_path.is_file():
        return _blocked(f"CAN_DBC_MISSING:{dbc_rel}", skip_class="ENVIRONMENT", planned=0)

    try:
        decoded = decode_dbc_frame(dbc_path, frame, runner=context.runner)
    except InspectionUnavailable as exc:
        # A.1 names cantools. An absent decoder is BLOCKED — never FAIL, and never a
        # substitute decoder wearing cantools' name.
        return _blocked(exc.reason_code, skip_class="ENVIRONMENT", planned=0)

    derived = {name: float(value) for name, value in decoded["values"].items()}
    return Observation(
        values={
            # DERIVED: what the harness's cantools invocation read out of the pinned DBC.
            "derived": derived,
            "raw": dict(decoded.get("raw", {})),
            # SUBMITTED: what the run claimed. It is compared against, never observed.
            "submitted": dict(_require_mapping(submission, "submission").get("answer") or {}),
            "expected": dict(_require_mapping(truth.get("expected"), "truth.expected")),
        },
        complete=True,
        planned=len(derived),
    )


def _collect_uds(
    submission: Mapping[str, Any], truth: Mapping[str, Any], context: OracleContext
) -> "Observation":
    """A.2. A tracked deterministic definition, and nothing else.

    A.2 explicitly permits this: the independent source of truth is the tracked
    definition, held outside the agent-visible tree. No external dependency is invented
    to make this task look like the others.
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    # A.2's independent source of truth IS the tracked definition, so it is the derived
    # side. The submission is still the submitted side: the judge compares the two.
    return Observation(
        values={
            "derived": dict(expected),
            "submitted": dict(_require_mapping(submission, "submission").get("answer") or {}),
            "expected": dict(expected),
        },
        complete=True,
        planned=len(expected),
    )


# ---------------------------------------------------------------------------
# the `yara` CLI: what stdout says, and what the exit code does NOT say
# ---------------------------------------------------------------------------
#
# MEASURED against YARA 4.5.0. The CLI exits 0 BOTH when a rule matched and when it did
# not; what separates the two is stdout, where one line per matching rule is printed as
# `<rule identifier> <target>` and a non-match prints nothing at all.
#
# ```text
# yara known_good.yar holdout_positive_beacon.txt
#   -> exit 0, stdout "ai11_reference_answer holdout_positive_beacon.txt"
# yara known_good.yar holdout_negative_clean.txt
#   -> exit 0, stdout ""
# yara <rule with a syntax error> <sample>
#   -> exit 1, stdout "", stderr "error: rule ...: syntax error, ..."
# ```
#
# The exit code therefore carries NO match information. A collector that read `0` as
# "matched" reports every scanned sample as a hit — which is what happened here: the
# correct reference rule was recorded as four hits and two failures, and the two samples
# it "failed" are exactly the two it correctly does not match.

#: One match record. The CLI prints one line per rule that matched, `<identifier>
#: <target>`; under `-g` it appends the rule's tags to the identifier as `:tag[,tag]`,
#: so tags are parsed OFF rather than mistaken for part of the name.
_YARA_MATCH_LINE = re.compile(
    r"^(?P<rule>[A-Za-z_]\w*)(?::[A-Za-z_]\w*(?:,[A-Za-z_]\w*)*)?\s+(?P<target>\S.*)$"
)

#: A rule declaration. `private` and `global` may precede it, tags may follow the name.
#: Anchored at the start of a line, which is also what excludes a `//`-commented-out
#: declaration without having to tokenise string literals (a rule file may legitimately
#: contain `//` inside a literal, as `known_good.yar` does in a URL).
_YARA_RULE_DECLARATION = re.compile(
    r"^[ \t]*(?:(?:private|global)[ \t]+)*rule[ \t]+([A-Za-z_]\w*)", re.MULTILINE
)

#: A `/* ... */` comment. Removed before declarations are read, so a rule commented out
#: across several lines is not counted as declared.
_YARA_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


class YaraReading(StrEnum):
    """What ONE completed `yara` invocation says about the SUBMITTED rule.

    Three values, and the third is the point: output this parser cannot attribute to the
    submitted rule is AMBIGUOUS rather than rounded to the nearer of the other two.
    """

    MATCHED = "MATCHED"
    NOT_MATCHED = "NOT_MATCHED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class YaraMatchRecord:
    """One `<rule identifier> <target>` line the scanner printed."""

    rule: str
    target: str


def declared_rule_names(rule_text: str) -> tuple[str, ...]:
    """The identifiers a submitted rule file DECLARES, in file order.

    The identity a match record has to name comes from the SUBMITTED rule, never from a
    constant in this module: a collector that looked for the reference rule's name would
    recognise the reference answer and nothing else, which is a discrimination control
    that cannot discriminate.
    """
    return tuple(_YARA_RULE_DECLARATION.findall(_YARA_BLOCK_COMMENT.sub(" ", rule_text)))


def _comparable(path: Path) -> str:
    """One path in the form the PLATFORM considers canonical, and nothing beyond it.

    `normpath` collapses `.`, `..` and repeated separators; `normcase` folds letter case
    and separator style on the platforms that consider them equivalent. Nothing is
    resolved through a symlink, and nothing is invented.
    """
    return os.path.normcase(os.path.normpath(str(path)))


def _same_target(reported: str, scanned: Path) -> bool:
    """Whether a match record's target is the file THIS invocation scanned.

    A record is bound to the target by PATH, never by name. `yara` echoes back the target
    it was given, and the collector gives it exactly one — `str(sample)` for the sample
    under scan — so the comparison is:

    ```text
        the reported path, normalised the way the platform normalises paths
        ==
        the scanned path, normalised the same way
    ```

    A shared BASENAME is deliberately not enough. `A/clean.txt` and `B/clean.txt` are two
    different files, and accepting a record about the second because it is called the
    same thing as the first would attribute a detection to a file that was never scanned
    — an attribution bug in the one place the oracle decides what was observed.
    """
    try:
        candidate = Path(reported)
    except (OSError, ValueError):  # pragma: no cover - a path the platform refuses
        return False
    return _comparable(candidate) == _comparable(scanned)


def parse_yara_matches(
    stdout: str,
    submitted_rule_names: Collection[str],
    *,
    target: str | Path | None = None,
) -> YaraReading:
    """Read ONE completed invocation's stdout as an observation about the SUBMITTED rule.

    Its only inputs are the scanner's own output and the identity of what was submitted.
    It does NOT read truth, does NOT decide a benchmark verdict, and does NOT guess: it
    reports what the scanner said, or that it cannot tell.

    ```text
    empty stdout                                  NOT_MATCHED
    a record naming a declared rule (and target)  MATCHED
    a line that is not a match record             AMBIGUOUS
    a record naming a rule nobody submitted       AMBIGUOUS
    a record about a different target             AMBIGUOUS
    ```

    AMBIGUOUS is not "no match" and not "match". Warning text, a diagnostic, or a record
    about something else is output the scanner produced that this collector cannot
    attribute, and both of the other answers would be a claim the scanner did not make.
    """
    declared = {str(name) for name in submitted_rule_names}

    records: list[YaraMatchRecord] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parsed = _YARA_MATCH_LINE.match(line.strip())
        if parsed is None:
            return YaraReading.AMBIGUOUS
        records.append(
            YaraMatchRecord(rule=parsed.group("rule"), target=parsed.group("target"))
        )

    if target is not None:
        scanned = Path(target)
        attributable = [record for record in records if _same_target(record.target, scanned)]
        if len(attributable) != len(records):
            return YaraReading.AMBIGUOUS
        records = attributable

    if any(record.rule not in declared for record in records):
        return YaraReading.AMBIGUOUS

    return YaraReading.MATCHED if records else YaraReading.NOT_MATCHED


#: A.6's tracked generator, relative to the pinned source root.
FUZZ_GENERATOR = "labs/vehicle/can-tools/fuzz/isotp_fuzz.py"

#: §27.1. The ONE controlled rerun. `--json` is absent because the generator has no
#: such argument, and `--max-cases` is absent because it truncates the case set that
#: §27.2 defines the authoritative set to be.
FUZZ_RERUN_SEED = 12345

#: §27.6. The generator's own output names, relative to the run's `--out` directory.
FUZZ_SUMMARY_FILE = "smoke-summary.json"

#: §27.7. The declared precondition this collector may not assume away.
VCAN0_EXCLUSIVE_REASON = "PRECONDITION_UNMET:environment:vcan0-exclusive"

#: §27.5. One smoke run executes every case against a live ECU, each with its own
#: readiness poll and case deadline. MEASURED at `efa836f`: 76 s for the 30-case set.
#: The generic inspection timeout is sized for a single tool invocation, so the rerun
#: takes the larger of the two rather than a number chosen for a different shape of
#: work. It stays under the task's own 900 s budget.
FUZZ_RERUN_TIMEOUT_SECONDS = 600

#: §27.2. The identifiers the pinned generator NEVER emits. A truth or control file
#: that carries one is stale material from a different oracle, refused by name rather
#: than mapped, renamed or converted.
_FUZZ_STALE_CASE_ID = re.compile(r"^smoke-case-\d+$")

#: §27.8. The recovery probe, read from the pinned generator's TRACKED schema
#: (`case_schema.py:272-273`) rather than from a submission or a capture.
FUZZ_RECOVERY_REQUEST = "10 01"
FUZZ_RECOVERY_EXPECTED = "50 01 00 32 00 64"

#: §27.8. The subject the recovery observation is about: the virtual ECU the generator
#: starts, one fresh process per case.
FUZZ_ECU_SCRIPT = "labs/vehicle/uds-basic/ecu/ecu.py"


class ReproductionUnavailable(RuntimeError):
    """The controlled rerun produced no usable observation, and why."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class FuzzCase:
    """One executed case, as the run itself recorded it.

    Only the fields §27 lets the oracle use: the classification, the kernel reading in
    §27.4's representation, and the §27.8 subject-side facts. `timestamp`,
    `duration_ms`, `errno`, `ecu_log_tail` and the rest of the per-run capture are
    deliberately NOT carried: §18.2 forbids them in a record, and reading them into the
    observation would put them one attribute away from one.
    """

    case_id: str
    klass: str
    kernel_oracle: str
    kernel_events: int | None
    process_alive: bool
    recovery: str
    recovery_response: str | None
    #: The probe the case DECLARES (tracked, from the generator's own case
    #: construction). Carried so the regression can prove the run answered the probe
    #: the contract names, rather than whatever a file happened to contain.
    recovery_request: str
    recovery_expected: str


@dataclass(frozen=True, slots=True)
class FuzzReproduction:
    """What ONE controlled rerun produced, read from the run's own output files."""

    cases: tuple[FuzzCase, ...]
    planned: int
    exit_code: int
    early_stop: bool


def _fuzz_case_result(path: Path) -> Mapping[str, Any]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproductionUnavailable(
            f"FUZZ_CASE_FILE_UNREADABLE:{path.name}", f"{type(exc).__name__}"
        ) from exc
    if not isinstance(decoded, Mapping):
        raise ReproductionUnavailable(f"FUZZ_CASE_FILE_NOT_AN_OBJECT:{path.name}")
    return decoded


def vcan0_exclusivity_reason(runner: Any, timeout_seconds: int) -> str:
    """§27.7. Why exclusive use of `vcan0` is NOT demonstrated — or "" if it is.

    Existence is not exclusivity. `ip link show vcan0` proves the interface exists and
    proves nothing about who else is on it, so it is NOT this function and must never
    be recorded as evidence of exclusivity.

    §27.7 admits NO lockfile, flock, network namespace, socket-ownership probe or other
    scheme, and refuses "no obvious process was found" as proof. A pseudo-lock that has
    not been measured against the real failure it claims to exclude turns an unverified
    assumption into a recorded fact, which is worse than the honest BLOCKED. So this
    returns a reason on every host until an explicit, auditable mechanism is admitted by
    a further amendment — and this single function is where such a mechanism would plug
    in, with the measurement that justifies it.
    """
    probe = runner.run(
        ["ip", "link", "show", "vcan0"], cwd=None, timeout_seconds=timeout_seconds
    )
    if probe.exit_code is None:
        return "vcan0 is not present on this host: `ip link show vcan0` did not run"
    if probe.exit_code != 0:
        return "vcan0 is not present on this host: `ip link show vcan0` exited non-zero"
    return (
        "vcan0 exists but exclusive use cannot be demonstrated: §27.7 admits no "
        "lockfile, flock, namespace or socket-ownership mechanism, and 'no obvious "
        "process was found' is not a proof"
    )


def run_fuzz_smoke(
    *,
    runner: Any,
    source_root: Path,
    out_dir: Path,
    timeout_seconds: int,
    python: str | None = None,
) -> FuzzReproduction:
    """§27.1, §27.5, §27.6. Run the pinned generator ONCE and read what it wrote.

    The observation comes from the run's own per-case files. stdout is an operational
    log and is never parsed: the generator prints `summary written: <path>` last, and
    no line of its stdout is a record.

    Exit codes are §27.5's, not "non-zero means the environment is broken":

    ```text
    0                        a complete candidate observation
    1 + the run's own files  a COMPLETED run that stopped on a high-priority finding;
                             the observation is INCOMPLETE, never an environment failure
    2                        the harness invoked the generator wrongly — a defect
    1 + no files             the generator never started (its imports are python-can
                             and can-isotp); an environment fact, reported as one
    ```
    """
    generator = Path(source_root) / FUZZ_GENERATOR
    if not generator.is_file():
        raise ReproductionUnavailable(
            "FUZZ_GENERATOR_ABSENT",
            f"{FUZZ_GENERATOR} is not in the derived source tree at the pinned SHA",
        )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    process = runner.run(
        [
            python or sys.executable,
            str(generator),
            "--smoke",
            "--seed",
            str(FUZZ_RERUN_SEED),
            "--out",
            str(out_dir),
        ],
        cwd=str(source_root),
        timeout_seconds=max(timeout_seconds, FUZZ_RERUN_TIMEOUT_SECONDS),
    )
    if process.timed_out:
        raise ReproductionUnavailable("FUZZ_RERUN_TIMEOUT")
    if process.exit_code is None:
        raise ReproductionUnavailable("FUZZ_GENERATOR_UNAVAILABLE")

    case_files = sorted(
        path for path in out_dir.glob("*.json") if path.name != FUZZ_SUMMARY_FILE
    )
    summary_path = out_dir / FUZZ_SUMMARY_FILE
    produced = summary_path.is_file() or bool(case_files)

    early_stop = False
    if process.exit_code != 0:
        if process.exit_code == 1 and produced:
            # §27.5: the run COMPLETED and stopped on a finding. Not an environment
            # failure, and not a pass either.
            early_stop = True
        elif process.exit_code == 2:
            raise ReproductionUnavailable(
                "FUZZ_INVOCATION_DEFECT:2",
                "the generator rejected the harness's own command line; this is a "
                "defect in the harness and MUST NOT be reported as an environment "
                "limitation",
            )
        elif not produced:
            raise ReproductionUnavailable(
                "FUZZ_GENERATOR_DEPENDENCY_UNAVAILABLE",
                f"the generator exited {process.exit_code} without writing anything; "
                "its interpreter dependencies (python-can, can-isotp) are the "
                "environment fact this names",
            )
        else:
            raise ReproductionUnavailable(
                f"FUZZ_RERUN_NO_OBSERVATION:{process.exit_code}"
            )

    if not summary_path.is_file():
        raise ReproductionUnavailable(
            "FUZZ_RERUN_OUTPUT_UNREADABLE",
            f"the run wrote no {FUZZ_SUMMARY_FILE}; without it the case count the "
            "generator CONSTRUCTED is unknown, and §27.9 counts cases",
        )
    summary = _fuzz_case_result(summary_path)
    planned = summary.get("total")
    if not isinstance(planned, int) or isinstance(planned, bool) or planned <= 0:
        raise ReproductionUnavailable(
            "FUZZ_RERUN_OUTPUT_UNREADABLE", f"{FUZZ_SUMMARY_FILE} carries no case count"
        )

    cases: list[FuzzCase] = []
    for path in case_files:
        document = _fuzz_case_result(path)
        case_id = document.get("case_id")
        result = document.get("result")
        if not isinstance(case_id, str) or not isinstance(result, Mapping):
            raise ReproductionUnavailable(f"FUZZ_CASE_FILE_INCOMPLETE:{path.name}")
        kernel = result.get("kernel_oracle")
        raw_events = result.get("kernel_events")
        if kernel not in ("AVAILABLE", "UNAVAILABLE", "ERROR"):
            raise ReproductionUnavailable(
                f"FUZZ_KERNEL_ORACLE_NOT_TRISTATE:{case_id}", repr(kernel)
            )
        # §27.4, and the ONLY place the normalisation happens. The generator reports a
        # LIST of matching kernel-anomaly lines when its oracle was AVAILABLE, and null
        # when it was not; the record carries the COUNT. An empty list is 0 because the
        # oracle ran and found nothing — and an empty list MUST NOT become 0 for an
        # oracle that did not run, so the two branches never meet.
        if kernel == "AVAILABLE":
            if not isinstance(raw_events, list):
                raise ReproductionUnavailable(
                    f"FUZZ_KERNEL_EVENTS_NOT_A_LIST:{case_id}", repr(raw_events)
                )
            events: int | None = len(raw_events)
        else:
            if raw_events is not None:
                raise ReproductionUnavailable(
                    f"FUZZ_KERNEL_EVENTS_UNDER_UNAVAILABLE_ORACLE:{case_id}",
                    "a non-AVAILABLE kernel oracle records null, never a count",
                )
            events = None
        declared = document.get("expected")
        declared = declared if isinstance(declared, Mapping) else {}
        cases.append(
            FuzzCase(
                case_id=case_id,
                klass=str(result.get("class", "")),
                kernel_oracle=str(kernel),
                kernel_events=events,
                process_alive=bool(result.get("process_alive")),
                recovery=str(result.get("recovery", "")),
                recovery_response=result.get("recovery_response"),
                recovery_request=str(declared.get("recovery_request", "")),
                recovery_expected=str(declared.get("recovery_expected", "")),
            )
        )

    return FuzzReproduction(
        cases=tuple(cases),
        planned=planned,
        exit_code=process.exit_code,
        early_stop=early_stop,
    )


def _normalise_fuzz_cases(
    reproduction: FuzzReproduction, priority: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """The derived observation, keyed by the generator's OWN case identifiers.

    §27.2: identity comes from `case_schema.make_case_id()`. Nothing here renames,
    renumbers, aliases or maps a case, and a case the run did not write is simply
    absent — it is never filled in from a truth file, a control file or a capture.
    """
    derived: dict[str, dict[str, Any]] = {}
    for case in reproduction.cases:
        if case.klass not in priority:
            raise ReproductionUnavailable(f"FUZZ_CLASS_NOT_FROZEN:{case.case_id}")
        derived[case.case_id] = {
            "class": case.klass,
            "kernel_oracle": case.kernel_oracle,
            "kernel_events": case.kernel_events,
        }
    return derived


def _collect_yara(
    submission: Mapping[str, Any], truth: Mapping[str, Any], context: OracleContext
) -> "Observation":
    """A.3. Run the SUBMITTED rule against the held-out samples with `yara`.

    PREFLIGHT FIRST. Every sample path is resolved and checked before a single scanner
    invocation. A run that scanned three samples and then found the fourth missing has
    EXECUTED three checks, and reporting `executed = 0` would be a false record of what
    the harness did -- in the safe direction, but still false. Either every sample is
    scanned or none is.

    THE EXIT CODE IS NOT THE OBSERVATION. A completed `yara` invocation exits 0 whether
    or not the rule matched; the match is reported on stdout as `<rule identifier>
    <target>` and a non-match is reported as nothing. See the measurement record above
    `parse_yara_matches`. Reading `exit_code == 0` as "matched" is the defect this
    collector was corrected for: it reported all four held-out samples as hits and
    turned a correct reference rule into two failures.
    """
    samples = _require_mapping(truth.get("samples"), "truth.samples")
    planned = len(samples)
    if planned == 0:
        return _blocked("YARA_NO_HELD_OUT_MATERIAL", skip_class="ENVIRONMENT", planned=0)

    rule = _require_mapping(submission, "submission")
    rule_file = rule.get("rule_file")
    if not isinstance(rule_file, str) or not rule_file:
        return _blocked("YARA_NO_RULE_SUBMITTED", skip_class="INTENTIONAL", planned=planned)

    try:
        rule_path = _resolve_sample(context.control_dir, rule_file, "submitted rule")
    except (OracleProtocolError, WorkspaceDerivationError):
        return _blocked("YARA_RULE_PATH_REFUSED", skip_class="INTENTIONAL", planned=planned)

    try:
        resolved = {
            key: _resolve_sample(
                context.control_dir,
                _require_mapping(spec, f"truth.samples[{key}]").get("file"),
                f"truth.samples[{key}].file",
            )
            for key, spec in sorted(samples.items())
        }
    except (OracleProtocolError, WorkspaceDerivationError):
        # A refused or missing sample path. NO scanner invocation has happened.
        return _blocked("YARA_HELD_OUT_MATERIAL_MISSING", skip_class="ENVIRONMENT", planned=planned)

    # The identity the scanner's output must name. Read from the SUBMITTED rule file, so
    # that any rule is recognised by its own declared name rather than by a name baked
    # into this module.
    try:
        rule_text = rule_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _blocked(
            f"YARA_RULE_UNREADABLE:{type(exc).__name__}", skip_class="ENVIRONMENT", planned=planned
        )
    declared = declared_rule_names(rule_text)

    # Only now, with every path established, does anything run.
    matches: dict[str, bool] = {}
    for key, sample in resolved.items():
        process = context.runner.run(
            ["yara", str(rule_path), str(sample)],
            cwd=None,
            timeout_seconds=context.timeout_seconds,
        )
        # The process states are settled first, and in this order, because they are four
        # different facts (§8.2):
        #   an expired budget            the check did not conclude      -> BLOCKED
        #   no exit code                 the program was not there       -> BLOCKED
        #   a non-zero exit              the program RAN and refused     -> the submission
        #   exit 0                       the program completed           -> read stdout
        if process.timed_out:
            return _blocked("YARA_SCAN_TIMEOUT", skip_class="ENVIRONMENT", planned=planned)
        if process.exit_code is None:
            return _blocked("YARA_PROGRAM_UNAVAILABLE", skip_class="ENVIRONMENT", planned=planned)
        if process.exit_code != 0:
            # The scanner ran and refused the rule: a bad SUBMISSION, not a bad
            # environment. The required check executed and its assertion failed -- and
            # one invocation is not N. The counts say how much actually executed: this
            # invocation ran and failed, the remaining samples were never attempted.
            return Observation(
                values={
                    "matches": matches,
                    "scanner_error": (process.stderr or "").strip()[:200],
                    "exit_code": process.exit_code,
                    "invocations": len(matches) + 1,
                },
                complete=True,
                planned=planned,
            )

        reading = parse_yara_matches(process.stdout or "", declared, target=sample)
        if reading is YaraReading.AMBIGUOUS:
            # Exit 0, and output this collector cannot attribute to the submitted rule.
            # Nothing was observed about THIS sample, and neither of the other two
            # readings is a claim the scanner made. UNKNOWN, never a guess.
            return _blocked("YARA_SCANNER_OUTPUT_UNREADABLE", skip_class="UNKNOWN", planned=planned)
        matches[key] = reading is YaraReading.MATCHED

    return Observation(values={"matches": matches}, complete=True, planned=planned)


def _collect_firmware(
    submission: Mapping[str, Any], truth: Mapping[str, Any], context: OracleContext
) -> "Observation":
    """A.4. Inspect the image the harness BUILT, not the fixture.

    The image is read from the setup area -- where the builder put it -- so the
    observation comes from the artefact, and the digest is recorded rather than asserted.
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    planned = len(expected)
    if context.setup_dir is None:
        return _blocked("FIRMWARE_SETUP_DIR_ABSENT", skip_class="ENVIRONMENT", planned=planned)

    images = sorted(context.setup_dir.glob("*.squashfs"))
    if not images:
        return _blocked("FIRMWARE_IMAGE_ABSENT", skip_class="ENVIRONMENT", planned=planned)

    try:
        derived = inspect_firmware(images[0], extract_to=context.setup_dir / "rootfs")
    except InspectionUnavailable as exc:
        return _blocked(exc.reason_code, skip_class="ENVIRONMENT", planned=planned)

    return Observation(
        values={
            "derived": dict(derived),
            "submitted": dict(_require_mapping(submission, "submission").get("answer") or {}),
            "expected": dict(expected),
            "image_digest": _digest(images[0]),
        },
        complete=True,
        planned=planned,
    )


def _collect_reverse(
    submission: Mapping[str, Any], truth: Mapping[str, Any], context: OracleContext
) -> "Observation":
    """A.5. Inspect and EXECUTE the binary the harness BUILT.

    Architecture and linkage come from `readelf`; stdout and the exit code come from
    running it. None of the four depends on a SYMBOL ADDRESS: the addresses the labs
    README records are a property of one toolchain build rather than of the source, and
    an oracle keyed on them would fail on the next compiler.
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    planned = len(expected)
    if context.setup_dir is None:
        return _blocked("REVERSE_SETUP_DIR_ABSENT", skip_class="ENVIRONMENT", planned=planned)

    binaries = [path for path in sorted(context.setup_dir.glob("hello_arm64")) if path.is_file()]
    if not binaries:
        return _blocked("REVERSE_BINARY_ABSENT", skip_class="ENVIRONMENT", planned=planned)

    binary = binaries[0]
    try:
        derived = dict(inspect_elf(binary))
        # A.5: the binary is AArch64 and the task declares qemu-aarch64, so it is run
        # through the declared emulator rather than executed on the host.
        derived.update(run_binary(binary, launcher=["qemu-aarch64"]))
    except InspectionUnavailable as exc:
        return _blocked(exc.reason_code, skip_class="ENVIRONMENT", planned=planned)

    return Observation(
        values={
            "derived": derived,
            "submitted": dict(_require_mapping(submission, "submission").get("answer") or {}),
            "expected": dict(expected),
        },
        complete=True,
        planned=planned,
    )


def _collect_fuzz(
    submission: Mapping[str, Any], truth: Mapping[str, Any], context: OracleContext
) -> "Observation":
    """A.6, as §27 freezes it. The controlled rerun IS the observation.

    Three things this collector deliberately does NOT do, each of which it did before
    the amendment:

    ```text
    it does not pass --json          the generator has no such argument, and invoking it
                                     is a harness defect (exit 2), not a finding
    it does not parse stdout         the run's per-case files are the observation; the
                                     last stdout line is "summary written: <path>"
    it does not invent case ids      identity is `case_schema.make_case_id()`; the
                                     `smoke-case-NN` names the previous truth carried
                                     are refused by name, never mapped
    ```
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    priority = list(truth.get("class_priority", ()))
    if not priority:
        return _blocked("FUZZ_NO_CLASS_PRIORITY", skip_class="ENVIRONMENT", planned=0)

    # §27.2. Stale identifiers from a different oracle are refused, not translated.
    stale = sorted(key for key in expected if _FUZZ_STALE_CASE_ID.match(str(key)))
    if stale:
        return _blocked(
            f"FUZZ_TRUTH_MATERIAL_STALE:{stale[0]}",
            skip_class="ENVIRONMENT",
            planned=len(expected),
        )

    for case_id, spec in sorted(expected.items()):
        entry = _require_mapping(spec, f"truth.expected[{case_id}]")
        if entry.get("class") not in priority:
            return _blocked(
                f"FUZZ_CLASS_NOT_FROZEN:{case_id}", skip_class="ENVIRONMENT", planned=0
            )
        if entry.get("kernel_oracle") != "AVAILABLE" and entry.get("kernel_events") is not None:
            raise OracleProtocolError(
                f"truth.expected[{case_id}] carries kernel_events under a "
                f"{entry.get('kernel_oracle')} kernel oracle; an unavailable oracle "
                "records null, never zero"
            )

    planned_from_material = len(expected)
    if context.source_root is None:
        return _blocked(
            "FUZZ_SOURCE_ROOT_ABSENT", skip_class="ENVIRONMENT", planned=planned_from_material
        )

    # §27.7, BEFORE anything runs: §5.7 makes an unmet precondition BLOCKED, and the
    # harness must establish it rather than discover it halfway through a case set.
    # Existence is not exclusivity, and this repository admits no mechanism that
    # demonstrates exclusivity — so on every current host the honest answer is BLOCKED.
    exclusivity = vcan0_exclusivity_reason(context.runner, context.timeout_seconds)
    if exclusivity:
        return _blocked(
            VCAN0_EXCLUSIVE_REASON,
            skip_class="ENVIRONMENT",
            planned=planned_from_material,
        )

    try:
        reproduction = run_fuzz_smoke(
            runner=context.runner,
            source_root=context.source_root,
            out_dir=context.setup_dir or (context.source_root / "fuzz-cases"),
            timeout_seconds=context.timeout_seconds,
        )
        derived = _normalise_fuzz_cases(reproduction, priority)
    except ReproductionUnavailable as exc:
        # The reason code names WHAT happened. An invocation defect is not an
        # environment limitation, and an incomplete run is not a blocked one.
        return _blocked(
            exc.reason_code, skip_class="ENVIRONMENT", planned=planned_from_material
        )

    # §27.3: `truth.expected` must BE the authoritative case set. A case the run
    # produced that the material does not name means the material is not this task's;
    # and a complete run whose case set differs means the same thing.
    unlisted = sorted(set(derived) - set(expected))
    if unlisted:
        return _blocked(
            f"FUZZ_TRUTH_CASE_IDS_NOT_AUTHORITATIVE:{unlisted[0]}",
            skip_class="ENVIRONMENT",
            planned=planned_from_material,
        )
    if not reproduction.early_stop and set(derived) != set(expected):
        missing = sorted(set(expected) - set(derived))
        return _blocked(
            f"FUZZ_TRUTH_CASE_IDS_NOT_AUTHORITATIVE:{missing[0]}",
            skip_class="ENVIRONMENT",
            planned=planned_from_material,
        )

    return Observation(
        values={
            "derived": derived,
            "submitted": dict(_require_mapping(submission, "submission").get("answer") or {}),
            "expected": {case: dict(entry) for case, entry in expected.items()},
            # §27.9. The counts describe CASES: `planned` is what the generator
            # CONSTRUCTED for this invocation — read from the run's own summary, not
            # from a truth file — and `executed` is what it actually wrote a result
            # for. An early stop leaves the difference visible instead of hiding it.
            "planned": reproduction.planned,
        },
        complete=True,
        planned=reproduction.planned,
    )


# ---------------------------------------------------------------------------
# A.6 — the subject-side regression observation (§27.8)
# ---------------------------------------------------------------------------


def _residual_ecu_processes(
    runner: Any, source_root: Path, timeout_seconds: int
) -> tuple[bool, str]:
    """§27.8's "no residual process remains", observed on the post-execution state.

    §12 makes the regression a HARNESS act on the state the run left behind, so this is
    a process listing taken after the reproduction rather than a field the generator
    reports: the generator stops each case's ECU itself, and a stop that failed is only
    visible from outside it.

    Returns `(residual, reason_code)`. A listing that could not be taken is NOT "no
    residual process" — it is an observation that was not made, and the caller records
    it as one.
    """
    probe = runner.run(
        ["ps", "-eo", "args="], cwd=None, timeout_seconds=min(timeout_seconds, 60)
    )
    if probe.exit_code != 0:
        return False, "FUZZ_REGRESSION_PROCESS_STATE_UNOBSERVABLE"
    needle = FUZZ_ECU_SCRIPT.replace("/", os.sep)
    for line in (probe.stdout or "").splitlines():
        if needle in line.replace("/", os.sep) and "ps -eo" not in line:
            return True, ""
    return False, ""


def evaluate_ecu_recovery(
    *,
    source_root: Path | None,
    setup_dir: Path | None,
    runner: Any,
    timeout_seconds: int,
) -> tuple[OracleVerdict, str]:
    """§27.8. `ecu-survives-and-recovers`, measured on the SUBJECT.

    Two of the three observations come from the controlled reproduction the pinned
    generator performs, read out of the run's own case files:

    ```text
    1  the ECU process survived   result.process_alive, for every case
    3  the declared probe was     recovery == PASS and recovery_response == the
       answered                   tracked expected response, for every case
    ```

    The third is taken from the post-execution state, because a process that outlived
    its case is not something the case file can report:

    ```text
    2  no residual process        no ECU process remains after the run
    ```

    It NEVER looks at a submission: an answer that asserts its own recovery is not
    evidence of one, and `the negative control was rejected` is not a measurement of a
    process (§27.8). The condition is about the ECU, not about the answer.
    """
    if source_root is None or setup_dir is None:
        return OracleVerdict.BLOCKED, "FUZZ_REGRESSION_CONTEXT_ABSENT"

    exclusive = vcan0_exclusivity_reason(runner, timeout_seconds)
    if exclusive:
        return OracleVerdict.BLOCKED, VCAN0_EXCLUSIVE_REASON

    try:
        reproduction = run_fuzz_smoke(
            runner=runner,
            source_root=Path(source_root),
            out_dir=Path(setup_dir) / "fuzz-regression",
            timeout_seconds=timeout_seconds,
        )
    except ReproductionUnavailable as exc:
        return OracleVerdict.BLOCKED, exc.reason_code

    if not reproduction.cases:
        return OracleVerdict.BLOCKED, "FUZZ_REGRESSION_NO_CASES"
    if reproduction.early_stop:
        # The case set did not run to the end, so "the ECU survived the run" is not a
        # fact this run established. Not a failure — an observation that is incomplete.
        return OracleVerdict.UNKNOWN, "FUZZ_REGRESSION_STOPPED_EARLY"

    # Provenance first: prove the run answered the probe the CONTRACT names, rather
    # than reporting whatever some file contained.
    for case in reproduction.cases:
        if case.recovery_request != FUZZ_RECOVERY_REQUEST:
            return OracleVerdict.BLOCKED, f"FUZZ_REGRESSION_PROBE_DRIFT:{case.case_id}"
        if case.recovery_expected != FUZZ_RECOVERY_EXPECTED:
            return OracleVerdict.BLOCKED, f"FUZZ_REGRESSION_PROBE_DRIFT:{case.case_id}"

    crashed = sorted(c.case_id for c in reproduction.cases if not c.process_alive)
    if crashed:
        return OracleVerdict.FAIL, f"ECU_DID_NOT_SURVIVE:{crashed[0]}"

    unrecovered = sorted(
        c.case_id
        for c in reproduction.cases
        if c.recovery != "PASS" or c.recovery_response != FUZZ_RECOVERY_EXPECTED
    )
    if unrecovered:
        return OracleVerdict.FAIL, f"ECU_DID_NOT_RECOVER:{unrecovered[0]}"

    residual, unobservable = _residual_ecu_processes(
        runner, Path(source_root), timeout_seconds
    )
    if unobservable:
        return OracleVerdict.BLOCKED, unobservable
    if residual:
        return OracleVerdict.FAIL, "ECU_PROCESS_RESIDUAL"

    return OracleVerdict.PASS, "ECU_SURVIVED_AND_RECOVERED"


#: §27.8. Conditions whose observation is about the SUBJECT rather than about the
#: answer, keyed by `(task_id, condition_id)`. Everything else keeps the generic
#: negative-control evaluation: the entry is absent for the other five tasks, so their
#: regression verdicts are reached by exactly the path they were reached by before.
SUBJECT_SIDE_REGRESSIONS: Mapping[
    tuple[str, str], Callable[..., tuple[OracleVerdict, str]]
] = {
    ("ai11-v1-fuzzing-recovery-triage", "ecu-survives-and-recovers"): evaluate_ecu_recovery,
}


#: The per-oracle collectors.
#:
#: Every v1 corpus task has one. There is no fallback: an unregistered oracle_id is
#: REFUSED, so a corpus entry cannot silently acquire an identity collector and turn a
#: submission into its own observation.
COLLECTORS: Mapping[str, Collector] = {
    "ai11-v1-can-dbc-decode.oracle": _collect_can,
    "ai11-v1-uds-nrc-triage.oracle": _collect_uds,
    "ai11-v1-yara-rule-author.oracle": _collect_yara,
    "ai11-v1-firmware-syn-ecu-inventory.oracle": _collect_firmware,
    "ai11-v1-reverse-arm64-triage.oracle": _collect_reverse,
    "ai11-v1-fuzzing-recovery-triage.oracle": _collect_fuzz,
}


def collect(
    oracle_id: str,
    submission: Mapping[str, Any],
    truth: Mapping[str, Any],
    *,
    control_dir: Path,
    source_root: Path | None = None,
    setup_dir: Path | None = None,
    workspace_root: Path | None = None,
    runner: Any = None,
    timeout_seconds: int = 120,
) -> "Observation":
    """Run the declared collector. An unregistered oracle is refused."""
    collector = COLLECTORS.get(oracle_id)
    if collector is None:
        raise OracleProtocolError(
            f"no collector is registered for oracle_id {oracle_id!r}. Every corpus oracle "
            "declares how its observation is made; there is no default, because a default "
            "would let a submission become its own observation. Registered: "
            f"{sorted(COLLECTORS)}"
        )
    return collector(
        submission,
        truth,
        OracleContext(
            control_dir=control_dir,
            source_root=source_root,
            setup_dir=setup_dir,
            workspace_root=workspace_root,
            runner=runner,
            timeout_seconds=timeout_seconds,
        ),
    )


# ---------------------------------------------------------------------------
# judgement
# ---------------------------------------------------------------------------


def _oracle_self_check(
    derived: Mapping[str, Any], expected: Mapping[str, Any], *, where: str
) -> str:
    """Whether the HARNESS's own derivation agrees with the tracked expectation.

    This runs before any submission is judged, and its purpose is to catch an oracle that
    has gone wrong rather than a run that has. A decoder that disagrees with the tracked
    truth has produced no usable observation, and reporting the run as FAIL would blame
    the submission for the harness's defect.
    """
    for field, want in sorted(expected.items()):
        have = derived.get(field, None)
        if isinstance(want, (int, float)) and not isinstance(want, bool):
            if not isinstance(have, (int, float)) or abs(float(have) - float(want)) > 1e-9:
                return f"{where}:{field}"
        elif have != want:
            return f"{where}:{field}"
    return ""


def _judge_derived_against_submitted(
    observation: Mapping[str, Any], truth: Mapping[str, Any], *, reason: str
) -> Judgement:
    """The shared comparison: the run's answer against what the harness DERIVED.

    Every task whose oracle derives its own value uses this. The submission is the thing
    judged; `derived` is the thing it is judged against; `expected` is the tracked truth
    that the derivation itself is checked against first.
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    derived = _require_mapping(observation.get("derived"), "observation.derived")
    submitted = _require_mapping(observation.get("submitted"), "observation.submitted")

    mismatch = _oracle_self_check(derived, expected, where="ORACLE_DERIVATION_DISAGREES")
    if mismatch:
        # The checks did NOT execute: the oracle had no usable observation to judge
        # against. planned = N, executed = 0, skipped = N is the honest record.
        return Judgement(
            verdict=OracleVerdict.UNKNOWN,
            tests=TestCounts(planned=len(expected), executed=0, passed=0,
                             failed=0, skipped=len(expected)),
            reason_code=mismatch,
        )

    failures = [
        field for field, want in sorted(derived.items()) if submitted.get(field, None) != want
    ]
    return _finish(len(derived), failures, reason=reason)


def _judge_exact_keys(observation: Mapping[str, Any], truth: Mapping[str, Any]) -> Judgement:
    """Discrete values: architecture, linkage, a version string."""
    return _judge_derived_against_submitted(
        observation, truth, reason="EXACT_FIELD_MISMATCH"
    )


def _judge_numeric_tolerance(
    observation: Mapping[str, Any], truth: Mapping[str, Any]
) -> Judgement:
    """Physical quantities, compared within a DECLARED tolerance.

    The tolerance is tracked truth, not a constant in this file: one chosen in code is
    one nobody reviewed, and a decode check that is too tight fails correct work while
    one that is too loose passes incorrect work.
    """
    tolerance = _require_mapping(truth.get("tolerance"), "truth.tolerance")
    derived = _require_mapping(observation.get("derived"), "observation.derived")
    submitted = _require_mapping(observation.get("submitted"), "observation.submitted")
    expected = _require_mapping(truth.get("expected"), "truth.expected")

    mismatch = _oracle_self_check(derived, expected, where="ORACLE_DERIVATION_DISAGREES")
    if mismatch:
        return Judgement(
            verdict=OracleVerdict.UNKNOWN,
            tests=TestCounts(planned=len(derived), executed=0, passed=0,
                             failed=0, skipped=len(derived)),
            reason_code=mismatch,
        )

    failures: list[str] = []
    for signal, want in sorted(derived.items()):
        have = submitted.get(signal, None)
        if not isinstance(have, (int, float)) or isinstance(have, bool):
            failures.append(signal)
            continue
        if abs(float(have) - float(want)) > float(tolerance.get(signal, 0)):
            failures.append(signal)
    return _finish(len(derived), failures, reason="VALUE_OUTSIDE_DECLARED_TOLERANCE")


def _judge_uds_triples(observation: Mapping[str, Any], truth: Mapping[str, Any]) -> Judgement:
    """The `(service, NRC, violated precondition)` triple, per case."""
    derived = _require_mapping(observation.get("derived"), "observation.derived")
    submitted = _require_mapping(observation.get("submitted"), "observation.submitted")

    failures: list[str] = []
    for case_id, want in sorted(derived.items()):
        want_map = _require_mapping(want, f"observation.derived[{case_id}]")
        have = submitted.get(case_id)
        if not isinstance(have, Mapping):
            failures.append(case_id)
            continue
        if any(have.get(field, None) != value for field, value in sorted(want_map.items())):
            failures.append(case_id)
    return _finish(len(derived), failures, reason="UDS_TRIPLE_MISMATCH")


def _judge_yara_detection(observation: Mapping[str, Any], truth: Mapping[str, Any]) -> Judgement:
    """The OBSERVED matches against the expected ones.

    A rule the scanner refused observed no matches at all and is FAIL: the scan ran and
    the submission was refused, which is an assertion failure rather than an environment
    problem (§8.2). The scanner's own message is carried in the observation, so the
    reason code can stay a statement about what happened rather than a guess at which
    failure it was: `yara` exits non-zero both for a rule that does not compile and for a
    target it cannot open, and the exit code does not separate them.

    A false positive is not traded against a true positive. Every sample is a required
    check, so §11 requires all of them.
    """
    samples = _require_mapping(truth.get("samples"), "truth.samples")
    if observation.get("scanner_error") is not None:
        # Factually correct counts. A rule the scanner refused on the first invocation
        # produced ONE executed check that failed, not N; the rest were never attempted.
        # Reporting `executed = N` would be a false record of what the harness did.
        invocations = int(observation.get("invocations", 1))
        planned = len(samples)
        attempted = min(max(invocations, 1), planned)
        counts = TestCounts(
            planned=planned,
            executed=attempted,
            passed=0,
            failed=attempted,
            skipped=planned - attempted,
        )
        return Judgement(
            verdict=OracleVerdict.FAIL,
            tests=counts,
            reason_code="YARA_SCANNER_REFUSED_SUBMISSION",
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
    derived = _require_mapping(observation.get("derived"), "observation.derived")
    answers = _require_mapping(observation.get("submitted"), "observation.submitted")

    failures: list[str] = []
    for case_id, want in sorted(derived.items()):
        want_map = _require_mapping(want, f"truth.expected[{case_id}]")
        have = answers.get(case_id)
        if not isinstance(have, Mapping):
            failures.append(case_id)
            continue

        want_class = want_map.get("class")
        if want_class not in priority:
            raise OracleProtocolError(
                f"observation.derived[{case_id}].class {want_class!r} is not a member of "
                "the frozen class priority; truth outside the frozen vocabulary is not "
                "truth this oracle can use"
            )
        if have.get("class") != want_class:
            failures.append(case_id)
            continue

        want_kernel = want_map.get("kernel_oracle")
        want_events = want_map.get("kernel_events", None)
        have_events = have.get("kernel_events", None)

        if want_kernel not in ("AVAILABLE", "UNAVAILABLE", "ERROR"):
            raise OracleProtocolError(
                f"observation.derived[{case_id}].kernel_oracle {want_kernel!r} is not one "
                "of AVAILABLE, UNAVAILABLE or ERROR"
            )
        if want_kernel != "AVAILABLE":
            if want_events is not None:
                raise OracleProtocolError(
                    f"observation.derived[{case_id}] carries kernel_events under a "
                    f"{want_kernel} kernel oracle; SecurityLab's own rule is that an "
                    "unavailable oracle records null, never zero"
                )
            if have_events is not None:
                failures.append(case_id)
            continue
        if have_events != want_events:
            failures.append(case_id)

    # §27.9. `planned` is what the generator CONSTRUCTED for this invocation, carried
    # by the collector from the run's own summary; `executed` is what it actually wrote
    # a result for. Neither is borrowed from a truth file: a count that describes what
    # a file says instead of what the harness ran is not a measurement.
    planned = observation.get("planned", len(derived))
    if not isinstance(planned, int) or isinstance(planned, bool) or planned < len(derived):
        planned = len(derived)

    executed = len(derived)
    counts = TestCounts(
        planned=planned,
        executed=executed,
        passed=executed - len(failures),
        failed=len(failures),
        skipped=planned - executed,
    )
    verdict, counts, rule_reason = apply_pass_rule(counts, "NONE")

    if counts.skipped > 0:
        # §27.5: the run completed and stopped on a high-priority finding. The
        # observation is real AND incomplete — a different fact from a failed check,
        # and the reason code has to say which one a reader is looking at.
        reason = "FUZZ_RERUN_STOPPED_EARLY"
        return Judgement(
            verdict=verdict,
            tests=counts,
            reason_code=f"{reason}:{failures[0]}" if failures else reason,
        )

    specific = f"FUZZ_CLASSIFICATION_MISMATCH:{failures[0]}" if failures else ""
    return Judgement(verdict=verdict, tests=counts, reason_code=specific or rule_reason)


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
    source_root: Path | None = None,
    setup_dir: Path | None = None,
    workspace_root: Path | None = None,
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
        source_root=source_root,
        setup_dir=setup_dir,
        workspace_root=workspace_root,
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
