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

import subprocess
import sys
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


def _host_record(*, workbench_sha: str, source_sha: str) -> HostRecord:
    """§15.4. A measurement without its environment is not reproducible."""
    import platform

    return HostRecord(
        os=f"{platform.system()} {platform.release()}",
        kernel=platform.version(),
        python=platform.python_version(),
        tool_versions={},
        workbench_sha=workbench_sha,
        source_sha=source_sha,
    )


def _blocked_run(
    *,
    task: TaskDefinition,
    run_id: str,
    workbench_sha: str,
    reason_code: str,
    blocked_by: str,
) -> BenchmarkRun:
    """A run that never started.

    It still produces exactly one `BenchmarkRun`, for the same reason AI-08 §7.1.1 makes
    a `BLOCKED` execution produce exactly one `AgentResult`: "the body did not start" and
    "no record exists" are different facts, and only the first is true here.
    """
    return BenchmarkRun(
        run_id=run_id,
        task_id=task.task_id,
        task_version=task.task_version,
        executor_kind=ExecutorKind.REFERENCE,
        agent_id=None,
        execution_id=None,
        workbench_sha=workbench_sha,
        source_sha=task.source_sha,
        workspace_identity={},
        host=_host_record(workbench_sha=workbench_sha, source_sha=task.source_sha),
        started_at="",
        finished_at="",
        duration_ms=0,
        tests=TestCounts(),
        oracle_results=(),
        task_status=OracleVerdict.BLOCKED,
        regression_status=OracleVerdict.NOT_RUN,
        security_boundary_status=SecurityBoundaryStatus.NOT_RUN,
        limitations=(LimitationCode.NO_PROVIDER_CALL_IN_PATH.value, reason_code),
    )


def execute_task(
    *,
    task: TaskDefinition,
    corpus_root: str | Path,
    source_root: str | Path,
    scratch_root: str | Path,
    run_id: str | None = None,
    variant: ReferenceVariant = ReferenceVariant.KNOWN_GOOD,
    git: GitRunner | None = None,
    builders: Mapping[str, Any] | None = None,
    oracle_runner: Any = None,
    workbench_sha: str = "",
) -> RunOutcome:
    """Run one task through the whole lifecycle and return its record."""
    run_id = run_id or new_run_id(uuid.uuid4().hex[:16])
    corpus_root = Path(corpus_root)
    oracle_runner = oracle_runner if oracle_runner is not None else LocalProcessRunner()

    # (1) §5.3. Existence is a PRECONDITION, checked before anything is derived. A sha
    #     that does not resolve is BLOCKED, and there is no fallback to the working tree.
    from benchmarks.workspace import ScratchGit

    git = git if git is not None else ScratchGit()
    if not resolve_source_sha(source_root, task.source_sha, git=git):
        return RunOutcome(
            run=_blocked_run(
                task=task,
                run_id=run_id,
                workbench_sha=workbench_sha,
                reason_code=f"{LimitationCode.SOURCE_SHA_UNRESOLVED.value}:{task.source_sha}",
                blocked_by="the pinned source_sha does not resolve in the source repository",
            ),
            workspace=None,
            source_tree=None,
            submission=None,
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
        return RunOutcome(
            run=_blocked_run(
                task=task,
                run_id=run_id,
                workbench_sha=workbench_sha,
                reason_code=f"{LimitationCode.ORACLE_MATERIAL_UNAVAILABLE.value}:{type(exc).__name__}",
                blocked_by=str(exc)[:200],
            ),
            workspace=None,
            source_tree=None,
            submission=None,
        )

    # (4) The executor produces a SUBMISSION. It does not produce a verdict.
    executor = ReferenceExecutor(task, corpus_root)
    submission = executor.produce(variant)

    # (5) The oracle produces the verdict, and only §11 can make it PASS.
    result = evaluate_submission(
        oracle_id=task.oracle.oracle_id,
        required=task.oracle.required,
        submission=submission.payload,
        truth=executor.truth(),
        control_dir=executor.control,
        runner=oracle_runner,
    )

    task_status = aggregate_oracle_verdicts([result])
    limitations = [LimitationCode.NO_PROVIDER_CALL_IN_PATH.value, *result.limitations]

    run = BenchmarkRun(
        run_id=run_id,
        task_id=task.task_id,
        task_version=task.task_version,
        executor_kind=ExecutorKind.REFERENCE,
        agent_id=None,
        execution_id=None,
        workbench_sha=workbench_sha,
        source_sha=task.source_sha,
        workspace_identity=workspace.identity(),
        host=_host_record(workbench_sha=workbench_sha, source_sha=task.source_sha),
        started_at="",
        finished_at="",
        duration_ms=0,
        tool_trace=(),
        tests=result.tests,
        oracle_results=(result.to_mapping(),),
        task_status=task_status,
        # §12: regression is its own axis, and the reference path does not execute the
        # declared regression conditions. NOT_RUN is the honest value; it is not a pass
        # and it is not a failure.
        regression_status=OracleVerdict.NOT_RUN,
        security_boundary_status=aggregate_security_status([]),
        limitations=tuple(dict.fromkeys(limitations)),
    )

    return RunOutcome(
        run=run, workspace=workspace, source_tree=source_tree, submission=submission
    )
