"""AI-11 §6, §7, §15 — the benchmark runner: one task, one lifecycle, one run record.

```text
load TaskDefinition
    |
    v
source_sha existence check          -> BLOCKED when it does not resolve (§5.3)
    |
    v
derive_source_tree()                reads the source; writes to nothing
    |
    v
prepare_workspace()                 FILTER -> VERIFY -> MANIFEST
    |                               (builds the declared generated artifacts)
    v
executor                            REFERENCE, or an AI-08 Agent execution
    |
    v
oracle                              collect -> judge -> apply_pass_rule (§11)
    |
    v
BenchmarkRun
```

### Why this module exists

An earlier revision had a working workspace API and no caller. `prepare_workspace()`
could have been deleted and every test would still have passed, which is the definition
of a component that is not part of the system. The lifecycle above is the caller, and the
tests drive it end to end.

### COMPLETED is not PASS

Nothing here converts an executor's outcome into a `task_status`. The executor produces a
SUBMISSION; the oracle produces the verdict; §8.4's aggregate is the only path to `PASS`.
"""

from __future__ import annotations

import os
import platform
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from benchmarks.errors import BenchmarkError
from benchmarks.executor import ReferenceExecutor, ReferenceVariant, Submission
from benchmarks.oracle import (
    ProcessResult,
    aggregate_oracle_verdicts,
    aggregate_security_status,
)
from benchmarks.oracles import evaluate_submission
from benchmarks.run import BenchmarkRun, HostRecord, TestCounts, new_run_id
from benchmarks.task import TaskDefinition
from benchmarks.vocabulary import (
    ExecutorKind,
    LimitationCode,
    OracleVerdict,
    SecurityBoundaryStatus,
)
from benchmarks.workspace import (
    DerivedWorkspace,
    ScratchGit,
    GitRunner,
    SourceTree,
    derive_source_tree,
    prepare_workspace,
    resolve_source_sha,
)

__all__ = [
    "LocalProcessRunner",
    "RunOutcome",
    "execute_task",
]


class LocalProcessRunner:
    """The process seam, for oracles that must run a real tool.

    `shell=False` stated rather than defaulted, and a mandatory positive timeout — the
    same two properties AI-06's runner states for itself, for the same reasons.
    """

    def run(
        self, argv: list[str], *, cwd: str | None, timeout_seconds: int
    ) -> ProcessResult:
        try:
            completed = subprocess.run(  # noqa: S603 - argv, no shell
                list(argv),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
            )
        except FileNotFoundError:
            # Nothing ran. §8.2: BLOCKED, and the caller decides that from exit_code.
            return ProcessResult(exit_code=None)
        except subprocess.TimeoutExpired:
            return ProcessResult(exit_code=None, timed_out=True)
        return ProcessResult(
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """A completed lifecycle: the run record, and the workspace it was measured in."""

    run: BenchmarkRun
    workspace: DerivedWorkspace | None
    source_tree: SourceTree | None
    submission: Submission | None


def utc_now() -> str:
    """ISO-8601 UTC at second resolution with a trailing Z — AI-05's G-TIMESTAMP.

    The same shape `plugins/context/context.py::utc_now` emits, restated here rather than
    imported: importing the context plugin's clock would make the benchmark layer depend
    on a plugin for a timestamp format.
    """
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def kernel_release() -> str:
    """The kernel RELEASE — `uname -r`, not `platform.version()`.

    `platform.version()` returns the build string (`#1 SMP PREEMPT_DYNAMIC ...`), which
    is a different fact from the release and does not identify the environment a
    measurement was taken in. The contract asks for the release, so the release is what
    is recorded.
    """
    release = platform.uname().release
    if release:
        return release
    return os.uname().release if hasattr(os, "uname") else ""  # pragma: no cover


def _host_record(
    *, workbench_sha: str, source_sha: str, task: TaskDefinition | None = None,
    runner: Any = None,
) -> HostRecord:
    """§15.4. A measurement without its environment is not reproducible.

    Tool versions are PROBED for the tools the task declared it needs, and a version that
    cannot be obtained is `None` rather than an empty string. §9.4: an unobtainable value
    is null with a reason, never a placeholder that reads as a measurement.
    """
    versions: dict[str, str | None] = {}
    if task is not None:
        for precondition in task.required_preconditions:
            if precondition.kind != "program":
                continue
            versions[precondition.name] = _probe_version(precondition.name, runner)

    return HostRecord(
        os=_distribution(),
        kernel=kernel_release(),
        python=platform.python_version(),
        tool_versions=versions,
        workbench_sha=workbench_sha,
        source_sha=source_sha,
    )


def _distribution() -> str:
    """The host distribution and release, not merely the platform family.

    `platform.system()` collapses every Linux to `Linux`, which is the one fact a reader
    already has. `/etc/os-release` is where the distribution actually says what it is.
    """
    release_file = Path("/etc/os-release")
    if release_file.is_file():  # pragma: no cover - POSIX hosts
        for line in release_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    return f"{platform.system()} {platform.release()}"


def _probe_version(program: str, runner: Any) -> str | None:
    """One declared program's version, or None. Never an invented value."""
    probe = runner if runner is not None else LocalProcessRunner()
    for flag in ("--version", "-version", "-V"):
        result = probe.run([program, flag], cwd=None, timeout_seconds=30)
        if result.exit_code == 0:
            text = (result.stdout or result.stderr or "").strip().splitlines()
            if text:
                return text[0][:120]
    return None


def resolve_workbench_sha(*, repo_root: str | Path | None = None, git: Any = None) -> str:
    """The Workbench revision that is running the harness.

    §15.4 requires it, so it is RESOLVED rather than defaulted to an empty string. An
    empty `workbench_sha` would make every run record un-reproducible while looking
    complete, which is worse than refusing.

    Read-only: `rev-parse HEAD` writes nothing.
    """
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    runner = git if git is not None else ScratchGit()
    result = runner.run(["rev-parse", "HEAD"], cwd=str(root))
    return result.stdout.strip() if result.ok else ""


def _record(
    *,
    task: TaskDefinition,
    run_id: str,
    workbench_sha: str,
    started_at: str,
    finished_at: str,
    duration_ms: int,
    host: HostRecord,
    workspace_identity: Mapping[str, Any],
    tests: TestCounts,
    oracle_results: tuple[Mapping[str, Any], ...],
    task_status: OracleVerdict,
    limitations: tuple[str, ...],
) -> BenchmarkRun:
    """One construction site, so every path produces the same shape of record."""
    return BenchmarkRun(
        run_id=run_id,
        task_id=task.task_id,
        task_version=task.task_version,
        executor_kind=ExecutorKind.REFERENCE,
        agent_id=None,
        execution_id=None,
        workbench_sha=workbench_sha,
        source_sha=task.source_sha,
        workspace_identity=dict(workspace_identity),
        host=host,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        tool_trace=(),
        tests=tests,
        oracle_results=oracle_results,
        task_status=task_status,
        # §12: regression is its own axis, and the reference path does not execute the
        # declared regression conditions. NOT_RUN is the honest value; it is not a pass
        # and it is not a failure.
        regression_status=OracleVerdict.NOT_RUN,
        security_boundary_status=aggregate_security_status([]),
        limitations=limitations,
    )


def execute_task(
    *,
    task: TaskDefinition,
    corpus_root: str | Path,
    source_root: str | Path,
    scratch_root: str | Path,
    run_id: str | None = None,
    variant: ReferenceVariant = ReferenceVariant.KNOWN_GOOD,
    git: Any = None,
    builders: Mapping[str, Any] | None = None,
    oracle_runner: Any = None,
    workbench_sha: str | None = None,
    workbench_repo: str | Path | None = None,
) -> RunOutcome:
    """Run one task through the whole lifecycle and return its record."""
    run_id = run_id or new_run_id(uuid.uuid4().hex[:16])
    corpus_root = Path(corpus_root)
    oracle_runner = oracle_runner if oracle_runner is not None else LocalProcessRunner()
    git = git if git is not None else ScratchGit()

    # §15.4. Resolved, not defaulted. A caller may supply the authoritative revision, and
    # the replay path does; otherwise it is read from the repository read-only.
    if workbench_sha is None:
        workbench_sha = resolve_workbench_sha(repo_root=workbench_repo, git=git)

    started_at = utc_now()
    started_monotonic = time.monotonic()

    host = _host_record(
        workbench_sha=workbench_sha, source_sha=task.source_sha, task=task,
        runner=oracle_runner,
    )

    def blocked(reason_code: str, blocked_by: str) -> RunOutcome:
        finished_at = utc_now()
        duration_ms = max(0, int((time.monotonic() - started_monotonic) * 1000))
        return RunOutcome(
            run=_record(
                task=task,
                run_id=run_id,
                workbench_sha=workbench_sha,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                host=host,
                workspace_identity={},
                tests=TestCounts(),
                oracle_results=(),
                task_status=OracleVerdict.BLOCKED,
                limitations=(
                    LimitationCode.NO_PROVIDER_CALL_IN_PATH.value,
                    reason_code,
                ),
            ),
            workspace=None,
            source_tree=None,
            submission=None,
        )

    # (1) §5.3. Existence is a PRECONDITION, checked before anything is derived. A sha
    #     that does not resolve is BLOCKED, and there is no fallback to the working tree.
    if not resolve_source_sha(source_root, task.source_sha, git=git):
        return blocked(
            f"{LimitationCode.SOURCE_SHA_UNRESOLVED.value}:{task.source_sha}",
            "the pinned source_sha does not resolve in the source repository",
        )

    # (2) Derive, then (3) filter and build the agent-visible tree.
    try:
        source_tree = derive_source_tree(
            source_root=source_root,
            source_sha=task.source_sha,
            scratch_root=scratch_root,
            run_id=run_id,
            git=git,
        )
        workspace = prepare_workspace(
            task=task,
            source_tree=source_tree,
            task_material_root=corpus_root / task.task_id,
            builders=builders,
        )
    except BenchmarkError as exc:
        return blocked(
            f"{LimitationCode.ORACLE_MATERIAL_UNAVAILABLE.value}:{type(exc).__name__}",
            str(exc)[:200],
        )

    # (4) The executor produces a SUBMISSION. It does not produce a verdict.
    executor = ReferenceExecutor(task, corpus_root)
    submission = executor.produce(variant)

    # (5) The oracle produces the verdict, and only §11 can make it PASS. It reads the
    #     PINNED material and the BUILT artefacts — never the agent-visible tree, and
    #     never the submission as its own observation.
    result = evaluate_submission(
        oracle_id=task.oracle.oracle_id,
        required=task.oracle.required,
        submission=submission.payload,
        truth=executor.truth(),
        control_dir=executor.control,
        source_root=source_tree.root,
        setup_dir=source_tree.setup_dir,
        workspace_root=workspace.root,
        runner=oracle_runner,
    )

    finished_at = utc_now()
    duration_ms = max(0, int((time.monotonic() - started_monotonic) * 1000))

    run = _record(
        task=task,
        run_id=run_id,
        workbench_sha=workbench_sha,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        host=host,
        workspace_identity=workspace.identity(),
        tests=result.tests,
        oracle_results=(result.to_mapping(),),
        task_status=aggregate_oracle_verdicts([result]),
        limitations=tuple(
            dict.fromkeys(
                [LimitationCode.NO_PROVIDER_CALL_IN_PATH.value, *result.limitations]
            )
        ),
    )

    return RunOutcome(
        run=run, workspace=workspace, source_tree=source_tree, submission=submission
    )
