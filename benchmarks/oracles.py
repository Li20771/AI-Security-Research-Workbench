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
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

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
    "COLLECTORS",
    "Observation",
    "OracleContext",
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
        _message, decoded = decode_dbc_frame(dbc_path.read_text(encoding="utf-8"), frame)
    except (ValueError, InspectionUnavailable) as exc:
        return _blocked(
            f"CAN_DECODE_FAILED:{type(exc).__name__}", skip_class="ENVIRONMENT", planned=0
        )

    return Observation(
        values={
            # DERIVED: what the harness decoder read out of the pinned DBC.
            "derived": {signal.name: signal.physical for signal in decoded},
            "raw": {signal.name: signal.raw for signal in decoded},
            # SUBMITTED: what the run claimed. It is compared against, never observed.
            "submitted": dict(_require_mapping(submission, "submission").get("answer") or {}),
            "expected": dict(_require_mapping(truth.get("expected"), "truth.expected")),
        },
        complete=True,
        planned=len(decoded),
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


#: `yara` exits 0 when a rule matched and 1 when it did not; anything else is an error.
#: SecurityLab's own adapter declares the same pair for the same reason
#: (`tools/reverse_engineering/__init__.py`: a match is reported through the status).
YARA_MATCH = 0
YARA_NO_MATCH = 1


def _collect_yara(
    submission: Mapping[str, Any], truth: Mapping[str, Any], context: OracleContext
) -> "Observation":
    """A.3. Run the SUBMITTED rule against the held-out samples with `yara`.

    PREFLIGHT FIRST. Every sample path is resolved and checked before a single scanner
    invocation. A run that scanned three samples and then found the fourth missing has
    EXECUTED three checks, and reporting `executed = 0` would be a false record of what
    the harness did -- in the safe direction, but still false. Either every sample is
    scanned or none is.
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

    # Only now, with every path established, does anything run.
    matches: dict[str, bool] = {}
    for key, sample in resolved.items():
        process = context.runner.run(
            ["yara", str(rule_path), str(sample)],
            cwd=None,
            timeout_seconds=context.timeout_seconds,
        )
        if process.timed_out:
            return _blocked("YARA_SCAN_TIMEOUT", skip_class="ENVIRONMENT", planned=planned)
        if process.exit_code is None:
            return _blocked("YARA_PROGRAM_UNAVAILABLE", skip_class="ENVIRONMENT", planned=planned)
        if process.exit_code == YARA_MATCH:
            matches[key] = True
        elif process.exit_code == YARA_NO_MATCH:
            matches[key] = False
        else:
            # The scanner ran and refused the rule: a bad SUBMISSION, not a bad
            # environment. The required check executed and its assertion failed.
            return Observation(
                values={
                    "matches": matches,
                    "compile_error": (process.stderr or "").strip()[:200],
                },
                complete=True,
                planned=planned,
            )

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
        derived.update(run_binary(binary))
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
    """A.6. The frozen class vocabulary, and the kernel oracle tri-state.

    Tier B: the controlled re-run needs an exclusive `vcan0` and `CAP_NET_ADMIN`. Where
    those are absent this is BLOCKED -- never FAIL, and never a pass. The class names are
    checked against the frozen `CLASS_PRIORITY` before anything is compared, and a truth
    that carries kernel events under a non-AVAILABLE oracle is refused rather than
    compared against.
    """
    expected = _require_mapping(truth.get("expected"), "truth.expected")
    priority = list(truth.get("class_priority", ()))
    if not priority:
        return _blocked("FUZZ_NO_CLASS_PRIORITY", skip_class="ENVIRONMENT", planned=0)

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

    if context.source_root is None:
        return _blocked("FUZZ_SOURCE_ROOT_ABSENT", skip_class="ENVIRONMENT", planned=len(expected))

    generator = context.source_root / "labs/vehicle/can-tools/fuzz/isotp_fuzz.py"
    if not generator.is_file():
        return _blocked("FUZZ_GENERATOR_ABSENT", skip_class="ENVIRONMENT", planned=len(expected))

    # The re-run needs the vcan0 facility the task declares as a precondition. 5.7 makes
    # an unmet precondition BLOCKED, and this is where that is decided rather than
    # discovered halfway through a campaign.
    probe = context.runner.run(
        ["ip", "link", "show", "vcan0"], cwd=None, timeout_seconds=context.timeout_seconds
    )
    if probe.exit_code != 0:
        return _blocked("FUZZ_VCAN0_UNAVAILABLE", skip_class="ENVIRONMENT", planned=len(expected))

    return Observation(
        values={
            "derived": {case: dict(entry) for case, entry in expected.items()},
            "submitted": dict(_require_mapping(submission, "submission").get("answer") or {}),
            "expected": {case: dict(entry) for case, entry in expected.items()},
        },
        complete=True,
        planned=len(expected),
    )


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

    return _finish(len(derived), failures, reason="FUZZ_CLASSIFICATION_MISMATCH")


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
