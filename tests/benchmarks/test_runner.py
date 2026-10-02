"""AI-11 §6, §7, §15 — the runner: one task, the whole lifecycle, one run record.

Layer 2. These tests exist because `prepare_workspace()` had no caller: the workspace
layer could have been deleted and every other test would still have passed. A component
with no caller is not part of the system, and this is where it is wired in.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.executor import ReferenceVariant
from benchmarks.runner import execute_task
from benchmarks.task import TaskDefinition
from benchmarks.vocabulary import ExecutorKind, OracleVerdict, SecurityBoundaryStatus
from tests.benchmarks.conftest import cantools_available, valid_task_mapping
from tests.benchmarks.test_benchmark_workspace import _git, _make_source_repo

pytestmark = pytest.mark.layer2

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "tasks"


class NoYara:
    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        from benchmarks.oracle import ProcessResult

        return ProcessResult(exit_code=None)


def _reference_task(**overrides: object) -> TaskDefinition:
    """A task whose oracle needs no external tool and whose material is declared."""
    base = {
        "task_id": "ai11-v1-can-dbc-decode",
        "workspace_setup": {
            "include": ["labs/vehicle/can-basic/demo.dbc", "task/frame.txt"],
            "exclude": ["control"],
            "generated": [],
        },
    }
    base.update(overrides)
    mapping = valid_task_mapping(**base)
    # The fixture's oracle id must name a registered judge. A task whose oracle
    # dispatches nowhere would fail at run time rather than at load, which is exactly
    # the shape of defect the corpus test suite refuses at load.
    mapping["oracle"]["oracle_id"] = f"{mapping['task_id']}.oracle"
    mapping["oracle"]["reproduce_command"] = (
        f"python3 -m benchmarks.replay {mapping['task_id']} --variant known_good"
    )
    return TaskDefinition.from_mapping(mapping)


@pytest.fixture
def source_repo(tmp_path: Path) -> tuple[Path, str]:
    return _make_source_repo(tmp_path)


@pytest.fixture
def corpus_root(tmp_path: Path) -> Path:
    """A corpus holding the material the fixture task declares under `task/`."""
    root = tmp_path / "corpus"
    material = root / "ai11-v1-can-dbc-decode" / "task"
    material.mkdir(parents=True)
    (material / "frame.txt").write_text("123#1122334455667788\n", encoding="utf-8")
    control = root / "ai11-v1-can-dbc-decode" / "control"
    control.mkdir()
    # The can task's real control material, so the lifecycle exercises a real judge
    # rather than a placeholder that would pass for the wrong reason.
    source = CORPUS_ROOT / "ai11-v1-can-dbc-decode" / "control"
    for name in ("truth.json", "known_good.json", "known_bad.json"):
        (control / name).write_text((source / name).read_text("utf-8"), encoding="utf-8")
    return root


@pytest.fixture
def scratch_root(tmp_path: Path) -> Path:
    """Where the derivation writes. Outside both repositories, as §15.2 requires."""
    return tmp_path / "scratch"


def test_R1_the_lifecycle_runs_and_produces_one_run_record(corpus_root, source_repo, scratch_root) -> None:
    repo, sha = source_repo
    task = _reference_task(source_sha=sha)

    outcome = execute_task(
        task=task,
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
        workbench_sha="c1118551",
    )
    run = outcome.run

    assert run.run_id == "run-0123456789abcdef"
    assert run.task_id == task.task_id
    assert run.source_sha == sha


def test_R2_the_reference_run_names_no_agent(corpus_root, source_repo, scratch_root) -> None:
    """§6.1. `reference` is not an AI-08 AgentId, so agent_id is null."""
    repo, sha = source_repo
    outcome = execute_task(
        task=_reference_task(source_sha=sha),
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
    )
    assert outcome.run.executor_kind is ExecutorKind.REFERENCE
    assert outcome.run.agent_id is None
    assert outcome.run.execution_id is None


def test_R3_the_workspace_layer_is_actually_used(corpus_root, source_repo, scratch_root) -> None:
    """The assertion that would fail if `prepare_workspace()` had no caller."""
    repo, sha = source_repo
    outcome = execute_task(
        task=_reference_task(source_sha=sha),
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
    )

    assert outcome.workspace is not None, "the lifecycle did not derive a workspace"
    assert outcome.source_tree is not None
    workspace = outcome.workspace

    # It is the FILTERED tree, and the run carries its measured manifest.
    assert workspace.root == outcome.source_tree.workspace_dir
    assert outcome.run.workspace_identity["manifest_digest"] == workspace.manifest_digest
    from benchmarks.workspace import manifest_digest

    assert workspace.manifest_digest == manifest_digest(workspace.root)
    assert workspace.manifest_digest != manifest_digest(outcome.source_tree.root)

    # And the declarations were honoured.
    assert (workspace.root / "labs/vehicle/can-basic/demo.dbc").is_file()
    assert (workspace.root / "task/frame.txt").is_file()
    assert not (workspace.root / "control").exists()
    assert not (workspace.root / "UNDECLARED_SECRET.md").exists()


def test_R4_the_run_record_carries_every_required_field(corpus_root, source_repo, scratch_root) -> None:
    repo, sha = source_repo
    outcome = execute_task(
        task=_reference_task(source_sha=sha),
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
        workbench_sha="c1118551",
    )
    projected = outcome.run.to_mapping()

    for field in (
        "workspace_identity", "source_sha", "workbench_sha", "host", "tests",
        "oracle_results", "task_status", "regression_status",
        "security_boundary_status", "limitations",
    ):
        assert field in projected, f"the run record is missing {field}"

    assert projected["workspace_identity"]["manifest_digest"]
    assert projected["host"]["source_sha"] == sha
    assert projected["workbench_sha"] == "c1118551"
    assert projected["oracle_results"], "no oracle result was recorded"


def test_R5_task_status_comes_from_the_oracle_not_from_the_executor(
    corpus_root, source_repo, scratch_root
) -> None:
    """§6.3. COMPLETED is never written into task_status.

    The executor produced a submission, which is not an outcome at all; the verdict came
    from `evaluate_submission` and §11.
    """
    repo, sha = source_repo
    outcome = execute_task(
        task=_reference_task(source_sha=sha),
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
    )
    # A.1's decoder is cantools, and it is a declared dependency of this suite. Where it
    # is absent the oracle is BLOCKED — never PASS, and never FAIL: an answer the harness
    # could not decode is not an answer that was wrong.
    expected = OracleVerdict.PASS if cantools_available() else OracleVerdict.BLOCKED
    assert outcome.run.task_status is expected
    assert outcome.run.task_status is not OracleVerdict.FAIL
    assert "COMPLETED" not in outcome.run.to_mapping().values()

    # The same lifecycle on the declared WRONG answer does not pass.
    bad = execute_task(
        task=_reference_task(source_sha=sha),
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-fedcba9876543210",
        variant=ReferenceVariant.KNOWN_BAD,
    )
    assert bad.run.task_status is not OracleVerdict.PASS


def test_R6_an_unresolvable_source_sha_blocks_and_still_produces_one_record(
    corpus_root, source_repo, scratch_root
) -> None:
    """§5.3, and AI-08 §7.1.1's rule applied one layer up.

    "The derivation did not start" and "no record exists" are different facts, and only
    the first is true here.
    """
    repo, _ = source_repo
    outcome = execute_task(
        task=_reference_task(source_sha="0" * 40),
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
    )
    run = outcome.run
    assert run.task_status is OracleVerdict.BLOCKED
    assert run.workspace_identity == {}
    assert outcome.workspace is None
    assert any("SOURCE_SHA_UNRESOLVED" in entry for entry in run.limitations)


def test_R7_a_missing_include_blocks_rather_than_running_against_less(
    corpus_root, source_repo, scratch_root
) -> None:
    repo, sha = source_repo
    task = _reference_task(
        source_sha=sha,
        workspace_setup={
            "include": ["labs/vehicle/can-basic/demo.dbc", "task/absent.txt"],
            "exclude": ["control"],
            "generated": [],
        },
    )
    outcome = execute_task(
        task=task,
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
    )
    assert outcome.run.task_status is OracleVerdict.BLOCKED
    assert outcome.workspace is None


def test_R8_regression_is_its_own_axis_and_is_not_run(corpus_root, source_repo, scratch_root) -> None:
    """§12. The reference path does not execute the declared regression conditions.

    `NOT_RUN` is the honest value: it is not a pass and it is not a failure.
    """
    repo, sha = source_repo
    outcome = execute_task(
        task=_reference_task(source_sha=sha),
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
    )
    assert outcome.run.regression_status is OracleVerdict.NOT_RUN
    assert outcome.run.task_status is not OracleVerdict.FAIL, "the two axes are independent"


def test_R9_the_reference_executor_invokes_no_tool(corpus_root, source_repo, scratch_root) -> None:
    """So the security axis is NOT_RUN, not a vacuous NO_VIOLATION."""
    repo, sha = source_repo
    outcome = execute_task(
        task=_reference_task(source_sha=sha),
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
    )
    assert outcome.run.tool_trace == ()
    assert outcome.run.security_boundary_status is SecurityBoundaryStatus.NOT_RUN


def test_R10_a_yara_blocked_oracle_reaches_the_run_record(corpus_root, source_repo, scratch_root) -> None:
    """The YARA task, through the lifecycle, on a host with no scanner."""
    repo, sha = source_repo
    # The real corpus yara task pins SecurityLab at efa836f, which the fixture repo does
    # not contain, so the task is rebuilt against the fixture revision and the real
    # corpus oracle id is kept.
    from benchmarks.task import load_task

    real = load_task(CORPUS_ROOT / "ai11-v1-yara-rule-author" / "task.yaml")
    raw = real.to_mapping()
    raw["source_sha"] = sha
    raw["workspace_setup"] = {
        # The material the yara task actually ships. `task/frame.txt` belongs to the can
        # task, and naming it here made the DERIVATION fail before the oracle ran — which
        # is why this test asserts on the oracle's reason code and not merely on BLOCKED.
        "include": ["labs/yara-basic/rules", "task/answer.yar.template"],
        "exclude": ["control"],
        "generated": [],
    }
    task = TaskDefinition.from_mapping(raw)

    outcome = execute_task(
        task=task,
        corpus_root=CORPUS_ROOT,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
        oracle_runner=NoYara(),
    )
    run = outcome.run
    assert run.task_status is OracleVerdict.BLOCKED
    assert run.task_status is not OracleVerdict.PASS
    assert run.tests.executed == 0
    assert run.tests.skipped == run.tests.planned
    assert any("YARA_PROGRAM_UNAVAILABLE" in entry for entry in run.limitations)


def test_R11_no_raw_content_reaches_the_run_record(corpus_root, source_repo, scratch_root) -> None:
    """§18.2, through the real lifecycle rather than a hand-built record."""
    repo, sha = source_repo
    outcome = execute_task(
        task=_reference_task(source_sha=sha),
        corpus_root=corpus_root,
        source_root=repo,
        scratch_root=scratch_root,
        run_id="run-0123456789abcdef",
    )
    import json

    serialised = json.dumps(outcome.run.to_mapping())
    # The rule text, the sample contents and the fixture answers must not appear.
    assert "SYNMALWARE_C2_BEACON" not in serialised
    assert "UNDECLARED_SECRET" not in serialised
    assert str(outcome.source_tree.root) not in serialised
