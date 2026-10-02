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
from tests.benchmarks.conftest import valid_task_mapping
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
    assert outcome.run.task_status is OracleVerdict.PASS, outcome.run.limitations
    # 8721 rpm and 174.59 km/h, derived from the pinned DBC and the frozen frame.
    assert outcome.run.tests.planned == 2

    bad = execute_task(
        task=_can_task(sha),
        corpus_root=tmp_path / "corpus",
        source_root=repo,
        scratch_root=tmp_path / "scratch",
        run_id="run-fedcba9876543210",
        variant=ReferenceVariant.KNOWN_BAD,
    )
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
