"""Shared builders and doubles for the AI-13 workflow-core tests.

The helpers build MINIMAL valid records so each test changes exactly the one thing it
is about. A test that had to assemble a whole valid definition inline to make one
assertion is a test whose failure is hard to read.

### The doubles

They are NOT AI-08, NOT a provider and NOT a tool. `RecordingExecutor` reports the
request digest the DEFINITION declares, which is what a faithful executor does; a test
that needs a widening attempt supplies `widening=True` and gets an executor that
reports a different one. A double that quietly did the right thing while the engine
failed to check it would make the engine's checks untestable.
"""

from __future__ import annotations

import ast
import pathlib
import uuid
from typing import Any

from workflows import vocabulary as _vocabulary
from workflows.canonical import digest_of
from workflows.checkpoint import ArtifactRef
from workflows.definition import WorkflowDefinition
from workflows.engine import ExecutionOutcome
from workflows.instants import plus_seconds
from workflows.policy import attempt_request_digest
from workflows.vocabulary import FailureClass

#: The instants these tests use. Fixed, so a bound is a fact rather than a race.
T0 = "2026-10-03T10:00:00Z"
T1 = "2026-10-03T10:00:10Z"
T2 = "2026-10-03T10:00:20Z"

#: The runtimes a definition may DECLARE. A definition carries a bound, never a date:
#: §8.3 puts the absolute instant on the run record, computed once at creation.
FAR_SECONDS = 365 * 24 * 3600
NEAR_SECONDS = 60
#: The per-invocation timeout a step declares — the INNER bound AI-06 requires.
STEP_TIMEOUT_SECONDS = 30

#: The package the boundary tests read, resolved from the module that was IMPORTED
#: rather than from the working directory.
#:
#: The two differ under the mutation harness, which runs these tests against a mutated
#: copy of the package: a path assembled from `Path("workflows")` would read the real
#: tree and report on code that is not the code under test. `workflows` itself is a
#: namespace package and has no `__file__`, so the directory comes from a real module.
WORKFLOWS_PACKAGE = pathlib.Path(_vocabulary.__file__).resolve().parent


def workflow_sources() -> list[pathlib.Path]:
    """Every module of the workflow package, in a stable order."""
    return sorted(
        path for path in WORKFLOWS_PACKAGE.rglob("*.py") if "__pycache__" not in path.parts
    )


def imported_modules(path: pathlib.Path) -> set[str]:
    """Every module `path` imports, at ANY depth — including inside a function.

    Function-level imports count. A boundary that only held at module scope would be a
    boundary an author steps around by moving one import into the body that uses it,
    which is exactly where a "reach the provider just this once" import goes.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def module_roots(names: set[str]) -> set[str]:
    """The top-level package each dotted name belongs to."""
    return {name.split(".")[0] for name in names}


def a_step(step_id: str = "s1", **overrides: Any) -> dict[str, Any]:
    """One declared step, with the per-invocation timeout §11.1 requires."""
    step = {
        "step_id": step_id,
        "kind": "AGENT_EXECUTION",
        "timeout_seconds": STEP_TIMEOUT_SECONDS,
    }
    step.update(overrides)
    return step


def limits(**overrides: Any) -> dict[str, Any]:
    """A complete declared limit set. §12 refuses a definition that omits one.

    Every time bound is a RUNTIME. The absolute deadline is computed at run creation
    and lives on the run record (§8.3), so no definition carries a date.
    """
    declared = {
        "workflow_seconds": FAR_SECONDS,
        "step_seconds": NEAR_SECONDS,
        "attempts_per_step": 2,
        "attempts_total": 4,
        "max_checkpoints": 8,
        "max_checkpoint_bytes": 65536,
        "max_artifact_bytes": 1048576,
    }
    declared.update(overrides)
    return declared


def a_retry_policy(**overrides: Any) -> dict[str, Any]:
    """A declared retry policy, with both bounds §10.3 requires."""
    policy = {
        "policy_id": "p",
        "applies_to": ["RETRYABLE_FAILURE"],
        "max_attempts": 2,
        "retry_seconds": FAR_SECONDS,
    }
    policy.update(overrides)
    return policy


def definition_body(**overrides: Any) -> dict[str, Any]:
    """A definition mapping that validates, with a CORRECT digest."""
    body: dict[str, Any] = {
        "workflow_id": "wf-demo",
        "revision": "v1",
        "steps": [a_step("s1"), a_step("s2")],
        "limits": limits(),
        "retry_policy": None,
    }
    body.update(overrides)
    body["definition_digest"] = digest_of(
        {**body, "definition_digest": ""}, digest_field="definition_digest"
    )
    return body


def make_definition(**overrides: Any) -> WorkflowDefinition:
    return WorkflowDefinition.from_mapping(definition_body(**overrides))


class _Executor:
    """Shared plumbing: timing, the ExecutionId, and the faithful request digest.

    `duration_seconds` is how a test says an execution TOOK TIME. It is reported as the
    execution's own `started_at`/`ended_at`, because the engine records what the seam
    reports — a double that always reported zero would make the step bound unreachable
    and every timing assertion vacuous.
    """

    def __init__(
        self,
        *,
        duration_seconds: int = 0,
        failure: FailureClass | None = None,
        cancelled_by: str = "attempt-owner",
        cancel_reason: str = "EXTERNAL_STOP",
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._duration_seconds = duration_seconds
        self.failure = failure
        self._cancelled_by = cancelled_by
        self._cancel_reason = cancel_reason
        self._token = uuid.uuid4().hex[:8]

    def _timing(self, now: str) -> tuple[str, str]:
        return now, plus_seconds(now, self._duration_seconds)

    def _cancellation(self) -> dict[str, str]:
        """§11.2. An execution that reports CANCELLED names WHO and WHY.

        AI-13 v1 cancels between attempts and never inside one, so a cancellation an
        outcome reports is the attempt owner's act — and `ExecutionOutcome` refuses the
        outcome outright if the owner does not name it.
        """
        if self.failure is not FailureClass.CANCELLED:
            return {}
        return {"cancelled_by": self._cancelled_by, "cancelled_reason": self._cancel_reason}

    def _record(self, step, attempt_id, run, now, timeout_seconds):  # noqa: ANN001
        self.calls.append(
            {
                "step_id": step.step_id,
                "attempt_id": attempt_id,
                "now": now,
                "run_id": run.run_id,
                # The composed OUTER bound the engine handed down (§11.1). Recorded so a
                # test can assert the bound actually reaches execution rather than
                # staying a value the engine computed and dropped.
                "timeout_seconds": timeout_seconds,
                # The STATE the execution was handed. Recorded because §8.3's rule is
                # about what a caller could have persisted BEFORE the execution ran, and
                # the only place that is visible is what the execution was given.
                "run": run,
            }
        )


class RecordingExecutor(_Executor):
    """The seam. It reports the request the DEFINITION declares."""

    def __init__(
        self,
        *,
        outcomes: list[bool] | None = None,
        decision_id: str = "",
        artifact_bytes: int = 0,
        artifact_refs: tuple[ArtifactRef, ...] = (),
        duration_seconds: int = 0,
    ) -> None:
        super().__init__(duration_seconds=duration_seconds)
        self._outcomes = list(outcomes or [])
        self._decision_id = decision_id
        self._artifact_bytes = artifact_bytes
        self._artifact_refs = artifact_refs

    def execute(self, *, definition, step, attempt_id, run, now, timeout_seconds):  # noqa: ANN001, ANN201
        self._record(step, attempt_id, run, now, timeout_seconds)
        started_at, ended_at = self._timing(now)
        succeeded = self._outcomes.pop(0) if self._outcomes else True
        return ExecutionOutcome(
            execution_id=f"exec-{self._token}-{len(self.calls)}",
            succeeded=succeeded,
            request_digest=attempt_request_digest(definition, step, run),
            started_at=started_at,
            ended_at=ended_at,
            failure_class=None if succeeded else FailureClass.RETRYABLE_FAILURE,
            reason_code="" if succeeded else "TRANSIENT",
            decision_id=self._decision_id,
            artifact_bytes=self._artifact_bytes,
            artifact_refs=self._artifact_refs,
        )


class WideningExecutor(_Executor):
    """An executor that reports a request the definition did NOT declare."""

    def __init__(self, *, widen_on_attempt: int = 1, duration_seconds: int = 0) -> None:
        super().__init__(duration_seconds=duration_seconds)
        self._widen_on = widen_on_attempt

    def execute(self, *, definition, step, attempt_id, run, now, timeout_seconds):  # noqa: ANN001, ANN201
        self._record(step, attempt_id, run, now, timeout_seconds)
        started_at, ended_at = self._timing(now)
        faithful = attempt_request_digest(definition, step, run)
        return ExecutionOutcome(
            execution_id=f"exec-widen-{self._token}-{len(self.calls)}",
            succeeded=True,
            request_digest="0" * 64 if len(self.calls) >= self._widen_on else faithful,
            started_at=started_at,
            ended_at=ended_at,
        )


class ReusingExecutor(_Executor):
    """An executor that hands back one ExecutionId for every attempt."""

    def execute(self, *, definition, step, attempt_id, run, now, timeout_seconds):  # noqa: ANN001, ANN201
        self._record(step, attempt_id, run, now, timeout_seconds)
        started_at, ended_at = self._timing(now)
        return ExecutionOutcome(
            execution_id="exec-shared",
            succeeded=True,
            request_digest=attempt_request_digest(definition, step, run),
            started_at=started_at,
            ended_at=ended_at,
        )


class FailOnceExecutor(_Executor):
    """Fails the first attempt, succeeds afterwards. For the retry path."""

    def __init__(
        self,
        failure: FailureClass | None = FailureClass.RETRYABLE_FAILURE,
        *,
        duration_seconds: int = 0,
        cancelled_by: str = "attempt-owner",
        cancel_reason: str = "EXTERNAL_STOP",
    ) -> None:
        super().__init__(
            duration_seconds=duration_seconds,
            failure=failure,
            cancelled_by=cancelled_by,
            cancel_reason=cancel_reason,
        )

    def execute(self, *, definition, step, attempt_id, run, now, timeout_seconds):  # noqa: ANN001, ANN201
        self._record(step, attempt_id, run, now, timeout_seconds)
        started_at, ended_at = self._timing(now)
        request = attempt_request_digest(definition, step, run)
        execution_id = f"exec-{self._token}-{len(self.calls)}"
        if len(self.calls) == 1:
            return ExecutionOutcome(
                execution_id=execution_id,
                succeeded=False,
                request_digest=request,
                started_at=started_at,
                ended_at=ended_at,
                failure_class=self.failure,
                reason_code="TRANSIENT",
                **self._cancellation(),
            )
        return ExecutionOutcome(
            execution_id=execution_id,
            succeeded=True,
            request_digest=request,
            started_at=started_at,
            ended_at=ended_at,
        )


class AlwaysFailsExecutor(_Executor):
    """Every attempt fails with the same class. For the bound paths."""

    def __init__(
        self,
        failure: FailureClass | None = FailureClass.RETRYABLE_FAILURE,
        *,
        duration_seconds: int = 0,
        cancelled_by: str = "attempt-owner",
        cancel_reason: str = "EXTERNAL_STOP",
    ) -> None:
        super().__init__(
            duration_seconds=duration_seconds,
            failure=failure,
            cancelled_by=cancelled_by,
            cancel_reason=cancel_reason,
        )

    def execute(self, *, definition, step, attempt_id, run, now, timeout_seconds):  # noqa: ANN001, ANN201
        self._record(step, attempt_id, run, now, timeout_seconds)
        started_at, ended_at = self._timing(now)
        return ExecutionOutcome(
            execution_id=f"exec-{self._token}-{len(self.calls)}",
            succeeded=False,
            request_digest=attempt_request_digest(definition, step, run),
            started_at=started_at,
            ended_at=ended_at,
            failure_class=self.failure,
            reason_code="AGAIN",
            **self._cancellation(),
        )
