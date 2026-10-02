"""AI-11 §7, §15.4, Annex A — oracle coverage, and run provenance. Layer 2.

Two questions this module settles:

```text
does every corpus oracle derive its observation INDEPENDENTLY,
    where Annex A says it must?
does a runner-created BenchmarkRun carry REAL provenance,
    or placeholders that read like one?
```
"""

from __future__ import annotations

import platform
from pathlib import Path

import pytest

from benchmarks.executor import ReferenceExecutor, ReferenceVariant
from benchmarks.oracles import COLLECTORS, evaluate_submission
from benchmarks.runner import execute_task, resolve_workbench_sha, utc_now
from benchmarks.task import TaskDefinition, load_corpus
from benchmarks.vocabulary import OracleVerdict
from tests.benchmarks.conftest import cantools_available, valid_task_mapping
from tests.benchmarks.test_benchmark_workspace import _make_source_repo

pytestmark = pytest.mark.layer2

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "tasks"

#: Annex A's disposition. `True` means the oracle DERIVES its observation from pinned or
#: built material, so the submission is compared against something the harness produced.
#: `False` means Annex A declares a tracked deterministic definition, where the tracked
#: value IS the independent source of truth — A.2 permits this explicitly, and inventing
#: an external dependency to make the task look like the others would be worse.
DERIVES_INDEPENDENTLY = {
    "ai11-v1-can-dbc-decode": True,          # A.1 harness DBC decode
    "ai11-v1-uds-nrc-triage": False,         # A.2 tracked deterministic definition
    "ai11-v1-yara-rule-author": True,        # A.3 real scanner over held-out samples
    "ai11-v1-firmware-syn-ecu-inventory": True,   # A.4 built image, inspected
    "ai11-v1-reverse-arm64-triage": True,    # A.5 built binary, inspected and executed
    "ai11-v1-fuzzing-recovery-triage": True, # A.6 controlled re-run
}


@pytest.fixture(scope="module")
def tasks():
    return load_corpus(CORPUS_ROOT)


# ---------------------------------------------------------------------------
# C1 — every oracle is registered, and the vocabulary matches Annex A
# ---------------------------------------------------------------------------


def test_C1_every_corpus_oracle_has_a_collector(tasks) -> None:
    for task in tasks:
        assert task.oracle.oracle_id in COLLECTORS, task.task_id


def test_C2_the_collector_set_is_exactly_the_corpus(tasks) -> None:
    """No collector exists for a task that is not in the corpus, and none is missing."""
    assert set(COLLECTORS) == {task.oracle.oracle_id for task in tasks}


def test_C3_the_annex_a_disposition_is_complete(tasks) -> None:
    assert {task.task_id for task in tasks} == set(DERIVES_INDEPENDENTLY)


def test_C4_an_unregistered_oracle_is_refused_not_defaulted() -> None:
    """No identity fallback. A default would let a submission be its own observation."""
    from benchmarks.errors import OracleProtocolError
    from benchmarks.oracles import collect

    with pytest.raises(OracleProtocolError) as excinfo:
        collect("ai11-v1-nonexistent.oracle", {}, {}, control_dir=CORPUS_ROOT)
    assert "no collector is registered" in str(excinfo.value)


# ---------------------------------------------------------------------------
# C5 — CAN genuinely decodes in the harness
# ---------------------------------------------------------------------------


def _can_task(source_sha: str) -> TaskDefinition:
    mapping = valid_task_mapping(
        task_id="ai11-v1-can-dbc-decode",
        source_sha=source_sha,
        workspace_setup={
            "include": ["labs/vehicle/can-basic/demo.dbc", "task/frame.txt"],
            "exclude": ["control"],
            "generated": [],
        },
    )
    mapping["oracle"]["oracle_id"] = "ai11-v1-can-dbc-decode.oracle"
    return TaskDefinition.from_mapping(mapping)


def test_C5_can_decodes_independently_and_compares_the_submission(tmp_path: Path) -> None:
    """A.1. The observation is the HARNESS decode; the submission is compared to it."""
    repo, sha = _make_source_repo(tmp_path)
    material = tmp_path / "corpus" / "ai11-v1-can-dbc-decode"
    (material / "task").mkdir(parents=True)
    (material / "task" / "frame.txt").write_text("123#1122334455667788\n", encoding="utf-8")
    control = material / "control"
    control.mkdir()
    for name in ("truth.json", "known_good.json", "known_bad.json"):
        (control / name).write_text(
            (CORPUS_ROOT / "ai11-v1-can-dbc-decode" / "control" / name).read_text("utf-8"),
            encoding="utf-8",
        )

    outcome = execute_task(
        task=_can_task(sha),
        corpus_root=tmp_path / "corpus",
        source_root=repo,
        scratch_root=tmp_path / "scratch",
        run_id="run-0123456789abcdef",
    )
    expected = OracleVerdict.PASS if cantools_available() else OracleVerdict.BLOCKED
    assert outcome.run.task_status is expected, outcome.run.limitations
    assert outcome.run.task_status is not OracleVerdict.FAIL
    if cantools_available():
        # 8721 rpm and 174.59 km/h, decoded from the pinned DBC and the frozen frame.
        assert outcome.run.tests.planned == 2

    bad = execute_task(
        task=_can_task(sha),
        corpus_root=tmp_path / "corpus",
        source_root=repo,
        scratch_root=tmp_path / "scratch",
        run_id="run-fedcba9876543210",
        variant=ReferenceVariant.KNOWN_BAD,
    )
    assert bad.run.task_status is not OracleVerdict.PASS
    if cantools_available():
        assert bad.run.task_status is OracleVerdict.FAIL


def test_C6_a_can_oracle_that_disagrees_with_the_tracked_truth_is_unknown() -> None:
    """An oracle that has gone wrong is not a run that has gone wrong.

    A decoder disagreeing with the tracked truth has produced no usable observation, and
    reporting FAIL would blame the submission for the harness's defect.
    """
    from benchmarks.oracles import judge_submission

    judgement = judge_submission(
        "ai11-v1-can-dbc-decode.oracle",
        {
            "derived": {"EngineSpeed": 1.0, "VehicleSpeed": 2.0},
            "submitted": {"EngineSpeed": 1.0, "VehicleSpeed": 2.0},
        },
        {
            "expected": {"EngineSpeed": 8721.0, "VehicleSpeed": 174.59},
            "tolerance": {"EngineSpeed": 0.0, "VehicleSpeed": 0.01},
        },
    )
    assert judgement.verdict is OracleVerdict.UNKNOWN
    assert "ORACLE_DERIVATION_DISAGREES" in judgement.reason_code


# ---------------------------------------------------------------------------
# C7 — generated artifacts are consumed, not dead data
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "task_id",
    ["ai11-v1-firmware-syn-ecu-inventory", "ai11-v1-reverse-arm64-triage"],
)
def test_C7_a_task_that_declares_a_generated_artifact_has_an_oracle_that_reads_it(
    task_id: str, tasks
) -> None:
    """§6. The builder's output must reach the ORACLE, not just the workspace.

    The failure this refuses is: the artifact is built, a test proves it exists, and the
    oracle reads the fixture instead. That is an artifact nothing measures.
    """
    task = next(t for t in tasks if t.task_id == task_id)
    assert task.workspace_setup.generated, f"{task_id} declares no generated artifact"

    source = (Path(__file__).resolve().parents[2] / "benchmarks" / "oracles.py").read_text(
        "utf-8"
    )
    collector = source.split(f'"{task.oracle.oracle_id}": ')[1].split(",")[0]
    body = source.split(f"def {collector}(")[1].split("\ndef ")[0]
    assert "context.setup_dir" in body, (
        f"{collector} does not read the setup area, so it cannot be inspecting the "
        "artifact the builder produced"
    )
    assert "known_good" not in body, (
        f"{collector} mentions a control fixture; the observation must come from the "
        "built artifact"
    )


def test_C8_the_reverse_oracle_does_not_depend_on_symbol_addresses() -> None:
    """§A.5. `add: 0x1149` is a property of one toolchain build, not of the source."""
    source = (Path(__file__).resolve().parents[2] / "benchmarks" / "oracles.py").read_text(
        "utf-8"
    )
    body = source.split("def _collect_reverse(")[1].split("\ndef ")[0]
    for forbidden in ("0x1149", "0x1161", "symbol", "nm "):
        assert forbidden not in body


# ---------------------------------------------------------------------------
# C9 — run provenance is real
# ---------------------------------------------------------------------------


def test_C9_utc_now_is_the_contract_format() -> None:
    stamp = utc_now()
    assert stamp.endswith("Z")
    assert len(stamp) == 20, stamp          # YYYY-MM-DDTHH:MM:SSZ
    assert stamp[10] == "T"


def test_C10_the_workbench_sha_resolves_rather_than_defaulting() -> None:
    sha = resolve_workbench_sha()
    assert sha, "the Workbench revision could not be resolved"
    assert len(sha) == 40
    assert all(char in "0123456789abcdef" for char in sha)


def test_C11_a_runner_run_carries_real_provenance(tmp_path: Path) -> None:
    """§15.4. Every field a reader needs to reproduce the run is present and real."""
    repo, sha = _make_source_repo(tmp_path)
    material = tmp_path / "corpus" / "ai11-v1-can-dbc-decode"
    (material / "task").mkdir(parents=True)
    (material / "task" / "frame.txt").write_text("123#1122334455667788\n", encoding="utf-8")
    control = material / "control"
    control.mkdir()
    for name in ("truth.json", "known_good.json", "known_bad.json"):
        (control / name).write_text(
            (CORPUS_ROOT / "ai11-v1-can-dbc-decode" / "control" / name).read_text("utf-8"),
            encoding="utf-8",
        )

    outcome = execute_task(
        task=_can_task(sha),
        corpus_root=tmp_path / "corpus",
        source_root=repo,
        scratch_root=tmp_path / "scratch",
        run_id="run-0123456789abcdef",
    )
    run = outcome.run

    assert run.workbench_sha, "workbench_sha is empty"
    assert len(run.workbench_sha) == 40
    assert run.started_at.endswith("Z") and run.started_at
    assert run.finished_at.endswith("Z") and run.finished_at
    assert run.duration_ms >= 0
    assert run.source_sha == sha
    assert run.host.python == platform.python_version()
    assert run.host.workbench_sha == run.workbench_sha
    assert run.host.source_sha == sha


def test_C12_the_host_kernel_is_the_release_not_the_build_string(tmp_path: Path) -> None:
    """`platform.version()` is a build string; the contract asks for the release."""
    repo, sha = _make_source_repo(tmp_path)
    material = tmp_path / "corpus" / "ai11-v1-can-dbc-decode"
    (material / "task").mkdir(parents=True)
    (material / "task" / "frame.txt").write_text("123#1123456789abcdef\n", encoding="utf-8")
    control = material / "control"
    control.mkdir()
    for name in ("truth.json", "known_good.json", "known_bad.json"):
        (control / name).write_text(
            (CORPUS_ROOT / "ai11-v1-can-dbc-decode" / "control" / name).read_text("utf-8"),
            encoding="utf-8",
        )

    outcome = execute_task(
        task=_can_task(sha),
        corpus_root=tmp_path / "corpus",
        source_root=repo,
        scratch_root=tmp_path / "scratch",
        run_id="run-0123456789abcdef",
    )
    kernel = outcome.run.host.kernel
    assert kernel, "the kernel release is empty"
    assert kernel == platform.uname().release
    assert kernel != platform.version() or platform.version() == platform.uname().release


def test_C13_a_blocked_run_still_carries_its_provenance(tmp_path: Path) -> None:
    """A blocked run is still a BenchmarkRun, with real timestamps and a real sha."""
    repo, _ = _make_source_repo(tmp_path)
    outcome = execute_task(
        task=_can_task("0" * 40),
        corpus_root=tmp_path / "corpus",
        source_root=repo,
        scratch_root=tmp_path / "scratch",
        run_id="run-0123456789abcdef",
    )
    run = outcome.run
    assert run.task_status is OracleVerdict.BLOCKED
    assert run.workbench_sha
    assert run.started_at.endswith("Z")
    assert run.finished_at.endswith("Z")
    assert run.duration_ms >= 0
    assert run.host.kernel


def test_C14_an_unobtainable_tool_version_is_null_not_empty() -> None:
    """§9.4. A version that cannot be obtained is null, never an empty string."""
    from benchmarks.runner import _probe_version

    class NoTool:
        def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
            from benchmarks.oracle import ProcessResult

            return ProcessResult(exit_code=None)

    assert _probe_version("definitely-not-installed", NoTool()) is None


def test_C15_declared_programs_are_probed_and_recorded(tmp_path: Path) -> None:
    """`tool_versions` is not permanently empty: declared programs are probed."""
    from benchmarks.runner import _host_record

    class Versioned:
        def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
            from benchmarks.oracle import ProcessResult

            return ProcessResult(exit_code=0, stdout=f"{argv[0]} 1.2.3\n")

    task = TaskDefinition.from_mapping(
        valid_task_mapping(
            required_preconditions=[{"kind": "program", "name": "yara"}],
        )
    )
    host = _host_record(workbench_sha="a" * 40, source_sha="b" * 40, task=task, runner=Versioned())
    assert host.tool_versions["yara"] == "yara 1.2.3"


# ---------------------------------------------------------------------------
# C16 — nothing raw reaches the record
# ---------------------------------------------------------------------------


def test_C16_no_observation_content_reaches_the_run_record(tmp_path: Path) -> None:
    import json

    repo, sha = _make_source_repo(tmp_path)
    material = tmp_path / "corpus" / "ai11-v1-can-dbc-decode"
    (material / "task").mkdir(parents=True)
    (material / "task" / "frame.txt").write_text("123#1122334455667788\n", encoding="utf-8")
    control = material / "control"
    control.mkdir()
    for name in ("truth.json", "known_good.json", "known_bad.json"):
        (control / name).write_text(
            (CORPUS_ROOT / "ai11-v1-can-dbc-decode" / "control" / name).read_text("utf-8"),
            encoding="utf-8",
        )

    outcome = execute_task(
        task=_can_task(sha),
        corpus_root=tmp_path / "corpus",
        source_root=repo,
        scratch_root=tmp_path / "scratch",
        run_id="run-0123456789abcdef",
    )
    serialised = json.dumps(outcome.run.to_mapping())
    for forbidden in ("EngineSpeed", "SYNMALWARE", "UNDECLARED_SECRET", "123#"):
        assert forbidden not in serialised, (
            f"{forbidden!r} reached the run record; §18.2 forbids raw content and "
            "observation bodies"
        )


# ---------------------------------------------------------------------------
# C17 — A.1 uses cantools, and only cantools
# ---------------------------------------------------------------------------


class RecordingRunner:
    """Records argv, and answers from a declared result. Starts nothing."""

    def __init__(self, *, exit_code=0, stdout="", stderr="", timed_out=False):
        from benchmarks.oracle import ProcessResult

        self.result = ProcessResult(
            exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=timed_out
        )
        self.calls: list[list[str]] = []

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        self.calls.append(list(argv))
        return self.result


@pytest.fixture
def can_source(tmp_path: Path):
    """A real source root holding a real DBC. The collector resolves the path."""
    (tmp_path / "labs/vehicle/can-basic").mkdir(parents=True)
    (tmp_path / "labs/vehicle/can-basic/demo.dbc").write_text(
        "BO_ 291 EngineData: 8 ECU_TEST\n", encoding="utf-8"
    )
    return tmp_path, "labs/vehicle/can-basic/demo.dbc"


def test_C17_the_can_collector_invokes_cantools(can_source) -> None:
    """A.1 names cantools. The collector runs it, and there is no substitute decoder."""
    import json as _json

    from benchmarks.oracles import collect

    runner = RecordingRunner(
        stdout=_json.dumps(
            {"message": "EngineData", "values": {"EngineSpeed": 8721.0},
             "raw": {"EngineSpeed": 8721}, "units": {}}
        )
    )
    observation = collect(
        "ai11-v1-can-dbc-decode.oracle",
        {"answer": {"EngineSpeed": 1.0}},
        {"dbc": can_source[1], "frame": "123#1122334455667788",
         "expected": {"EngineSpeed": 8721.0}},
        control_dir=Path("."),
        source_root=can_source[0],
        runner=runner,
    )
    assert runner.calls, "the decoder was never invoked"
    argv = runner.calls[0]
    assert "cantools" in " ".join(argv), (
        "A.1's decoder is the harness's own cantools invocation; the argv does not "
        f"mention it: {argv}"
    )
    assert observation.values["derived"] == {"EngineSpeed": 8721.0}


def test_C18_an_unavailable_cantools_is_blocked_not_substituted(can_source) -> None:
    """A missing decoder is BLOCKED. A substitute would be a different oracle."""
    from benchmarks.oracles import collect

    runner = RecordingRunner(
        exit_code=1, stderr="ModuleNotFoundError: No module named 'cantools'"
    )
    observation = collect(
        "ai11-v1-can-dbc-decode.oracle",
        {"answer": {}},
        {"dbc": can_source[1], "frame": "123#1122334455667788", "expected": {}},
        control_dir=Path("."),
        source_root=can_source[0],
        runner=runner,
    )
    assert not observation.complete
    assert observation.reason_code == "CANTOOLS_UNAVAILABLE"


def test_C19_derived_is_not_the_submission(can_source) -> None:
    """The derived side comes from the decoder, not from the answer."""
    import json as _json

    from benchmarks.oracles import collect

    runner = RecordingRunner(
        stdout=_json.dumps(
            {"message": "m", "values": {"EngineSpeed": 8721.0}, "raw": {}, "units": {}}
        )
    )
    observation = collect(
        "ai11-v1-can-dbc-decode.oracle",
        {"answer": {"EngineSpeed": 1.0}},
        {"dbc": can_source[1], "frame": "123#1122334455667788",
         "expected": {"EngineSpeed": 8721.0}},
        control_dir=Path("."),
        source_root=can_source[0],
        runner=runner,
    )
    assert observation.values["derived"] != observation.values["submitted"]


# ---------------------------------------------------------------------------
# C20 — A.5 executes through the declared emulator
# ---------------------------------------------------------------------------


def test_C20_the_reverse_oracle_runs_the_binary_through_qemu(tmp_path: Path) -> None:
    """A.5 declares qemu-aarch64. An AArch64 binary is not executed on the host."""
    import benchmarks.oracles as oracles

    calls: list[list[str]] = []
    real_run_binary = oracles.run_binary
    real_inspect_elf = oracles.inspect_elf

    def spy(binary, *, launcher=(), argv=()):  # noqa: ANN001, ANN202
        calls.append([*launcher, str(binary)])
        return {"stdout": "ARM64 result = 42", "exit_code": 0}

    # A REAL file: the collector checks that the artefact exists before executing it,
    # so a fabricated path would make it refuse for a reason unrelated to the assertion.
    binary = tmp_path / "setup" / "hello_arm64"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"ELF fake aarch64\n")

    class SetupDir:
        def glob(self, pattern):  # noqa: ANN001, ANN202
            return [binary]

    oracles.run_binary = spy
    oracles.inspect_elf = lambda binary: {"architecture": "AArch64", "linkage": "static"}
    try:
        oracles.collect(
            "ai11-v1-reverse-arm64-triage.oracle",
            {"answer": {"architecture": "AArch64"}},
            {"expected": {"architecture": "AArch64"}},
            control_dir=Path("."),
            setup_dir=SetupDir(),
        )
    finally:
        oracles.run_binary = real_run_binary
        oracles.inspect_elf = real_inspect_elf

    assert calls, "the binary was never executed"
    assert calls[0][0] == "qemu-aarch64", (
        f"the binary was executed as {calls[0]}; A.5 requires qemu-aarch64"
    )
    assert calls[0][1] == str(binary), "the artefact is not the built binary"


# ---------------------------------------------------------------------------
# C21 — A.6 runs the tracked generator at a fixed seed
# ---------------------------------------------------------------------------


def _fuzz_truth() -> dict:
    return {
        "class_priority": ["KERNEL_ANOMALY", "ECU_CRASH", "STATE_CORRUPTION", "HANG",
                           "TRANSPORT_ERROR", "UDS_RESPONSE", "DISCARD", "NORMAL"],
        "rerun_seed": 12345,
        "expected": {"c1": {"class": "DISCARD", "kernel_oracle": "AVAILABLE", "kernel_events": 0}},
    }


class RerunRunner:
    """vcan0 answers; the generator answers with a declared classification."""

    def __init__(self, classification: str, kernel: str = "AVAILABLE", events=0) -> None:
        self.classification = classification
        self.kernel = kernel
        self.events = events
        self.calls: list[list[str]] = []

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        import json as _json

        from benchmarks.oracle import ProcessResult

        self.calls.append(list(argv))
        if argv[0] == "ip":
            return ProcessResult(exit_code=0, stdout="vcan0: <UP>")
        return ProcessResult(
            exit_code=0,
            stdout=_json.dumps({"cases": {"c1": {
                "class": self.classification,
                "kernel_oracle": self.kernel,
                "kernel_events": self.events,
            }}}),
        )


def _fuzz_source(tmp_path: Path):
    import benchmarks.oracles as oracles

    source = tmp_path / "source"
    (source / "labs/vehicle/can-tools/fuzz").mkdir(parents=True)
    (source / oracles.FUZZ_GENERATOR).write_text("# tracked generator\n", encoding="utf-8")
    return source


def test_C21_the_fuzz_collector_runs_the_tracked_generator(tmp_path: Path) -> None:
    """A.6 requires a controlled RE-RUN, not `derived = expected`."""
    import benchmarks.oracles as oracles

    source = _fuzz_source(tmp_path)
    runner = RerunRunner(classification="TRANSPORT_ERROR")
    observation = oracles.collect(
        "ai11-v1-fuzzing-recovery-triage.oracle",
        {"answer": {"c1": {"class": "DISCARD", "kernel_events": 0}}},
        _fuzz_truth(),
        control_dir=Path("."),
        source_root=source,
        runner=runner,
    )

    generator_calls = [call for call in runner.calls if call[0] != "ip"]
    assert generator_calls, "the tracked generator was never invoked"
    argv = generator_calls[0]
    assert any(a.endswith("isotp_fuzz.py") for a in argv), f"the generator is not in {argv}"
    assert "--seed" in argv and "12345" in argv, f"the re-run is not fixed-seed: {argv}"

    # THE assertion that fails if someone reverts to `derived = expected`: the generator
    # reported TRANSPORT_ERROR, the truth says DISCARD, and derived follows the GENERATOR.
    assert observation.values["derived"]["c1"]["class"] == "TRANSPORT_ERROR"
    assert (
        observation.values["derived"]["c1"]["class"]
        != _fuzz_truth()["expected"]["c1"]["class"]
    )


def test_C22_a_missing_vcan_is_blocked_not_a_pass(tmp_path: Path) -> None:
    import benchmarks.oracles as oracles
    from benchmarks.oracle import ProcessResult

    source = _fuzz_source(tmp_path)

    class NoVcan:
        def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
            return ProcessResult(exit_code=1, stderr="Device vcan0 does not exist")

    observation = oracles.collect(
        "ai11-v1-fuzzing-recovery-triage.oracle",
        {"answer": {}},
        _fuzz_truth(),
        control_dir=Path("."),
        source_root=source,
        runner=NoVcan(),
    )
    assert not observation.complete
    assert observation.reason_code == "FUZZ_VCAN0_UNAVAILABLE"


def test_C23_kernel_events_are_null_under_a_non_available_oracle(tmp_path: Path) -> None:
    """SecurityLab's own rule: null, never 0 and never an empty list."""
    import benchmarks.oracles as oracles

    source = _fuzz_source(tmp_path)
    # The generator reports 0 under an unavailable oracle; the collector must not pass
    # that through as if it were an observation.
    runner = RerunRunner(classification="DISCARD", kernel="UNAVAILABLE", events=0)
    observation = oracles.collect(
        "ai11-v1-fuzzing-recovery-triage.oracle",
        {"answer": {}},
        _fuzz_truth(),
        control_dir=Path("."),
        source_root=source,
        runner=runner,
    )
    assert observation.values["derived"]["c1"]["kernel_events"] is None


# ---------------------------------------------------------------------------
# C24 — YARA compile failure counts what actually ran
# ---------------------------------------------------------------------------


def test_C24_a_compile_failure_counts_one_executed_check_not_four(tasks) -> None:
    """One scanner invocation is not four. The record must say what happened."""
    from benchmarks.oracles import evaluate_submission

    class CompileFail:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
            from benchmarks.oracle import ProcessResult

            self.calls += 1
            return ProcessResult(exit_code=2, stderr="error: syntax error, unexpected '}'")

    task = next(t for t in tasks if t.task_id == "ai11-v1-yara-rule-author")
    executor = ReferenceExecutor(task, CORPUS_ROOT)
    counters = CompileFail()
    result = evaluate_submission(
        oracle_id=task.oracle.oracle_id,
        required=task.oracle.required,
        submission=executor.produce(ReferenceVariant.KNOWN_GOOD).payload,
        truth=executor.truth(),
        control_dir=executor.control,
        runner=counters,
    )

    assert counters.calls == 1, "the scanner ran more than once after refusing the rule"
    assert result.verdict is OracleVerdict.FAIL
    assert result.tests.planned == 4
    assert result.tests.executed == 1, "one invocation is one executed check"
    assert result.tests.failed == 1
    assert result.tests.skipped == 3
    assert result.tests.executed + result.tests.skipped == result.tests.planned
