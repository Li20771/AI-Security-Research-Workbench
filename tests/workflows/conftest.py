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
from workflows.definition import WorkflowDefinition
from workflows.engine import ExecutionOutcome
from workflows.policy import attempt_request_digest
from workflows.vocabulary import FailureClass

#: The instants these tests use. Fixed, so a bound is a fact rather than a race.
T0 = "2026-10-03T10:00:00Z"
T1 = "2026-10-03T10:00:10Z"
T2 = "2026-10-03T10:00:20Z"
FAR = "2030-01-01T00:00:00Z"

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


def limits(**overrides: Any) -> dict[str, Any]:
    """A complete declared limit set. §12 refuses a definition that omits one."""
    declared = {
        "workflow_deadline": FAR,
        "step_seconds": 60,
        "attempts_per_step": 2,
        "attempts_total": 4,
        "max_checkpoints": 8,
        "max_checkpoint_bytes": 65536,
        "max_artifact_bytes": 1048576,
    }
    declared.update(overrides)
    return declared


def definition_body(**overrides: Any) -> dict[str, Any]:
    """A definition mapping that validates, with a CORRECT digest."""
    body: dict[str, Any] = {
        "workflow_id": "wf-demo",
        "revision": "v1",
        "steps": [
            {"step_id": "s1", "kind": "AGENT_EXECUTION"},
            {"step_id": "s2", "kind": "AGENT_EXECUTION"},
        ],
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


class RecordingExecutor:
    """The seam. It reports the request the DEFINITION declares."""

    def __init__(
        self,
        *,
        outcomes: list[bool] | None = None,
        decision_id: str = "",
        artifact_bytes: int = 0,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._outcomes = list(outcomes or [])
        self._counter = 0
        self._decision_id = decision_id
        self._artifact_bytes = artifact_bytes
        # Distinct per instance, because an ExecutionId is opaque and globally unique
        # (§6.3) and the engine refuses one that another attempt already produced.
        self._token = uuid.uuid4().hex[:8]

    def execute(self, *, definition, step, attempt_id, run, now):  # noqa: ANN001, ANN201
        self.calls.append(
            {"step_id": step.step_id, "attempt_id": attempt_id, "now": now, "run_id": run.run_id}
        )
        self._counter += 1
        succeeded = self._outcomes.pop(0) if self._outcomes else True
        return ExecutionOutcome(
            execution_id=f"exec-{self._token}-{self._counter}",
            succeeded=succeeded,
            request_digest=attempt_request_digest(definition, step, run),
            failure_class=None if succeeded else FailureClass.RETRYABLE_FAILURE,
            reason_code="" if succeeded else "TRANSIENT",
            decision_id=self._decision_id,
            artifact_bytes=self._artifact_bytes,
        )


class WideningExecutor:
    """An executor that reports a request the definition did NOT declare."""

    def __init__(self, *, widen_on_attempt: int = 1) -> None:
        self.calls: list[str] = []
        self._widen_on = widen_on_attempt

    def execute(self, *, definition, step, attempt_id, run, now):  # noqa: ANN001, ANN201
        self.calls.append(step.step_id)
        faithful = attempt_request_digest(definition, step, run)
        return ExecutionOutcome(
            execution_id=f"exec-widen-{len(self.calls)}",
            succeeded=True,
            request_digest="0" * 64 if len(self.calls) >= self._widen_on else faithful,
        )


class ReusingExecutor:
    """An executor that hands back one ExecutionId for every attempt."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(self, *, definition, step, attempt_id, run, now):  # noqa: ANN001, ANN201
        self.calls.append(step.step_id)
        return ExecutionOutcome(
            execution_id="exec-shared",
            succeeded=True,
            request_digest=attempt_request_digest(definition, step, run),
        )


class FailOnceExecutor:
    """Fails the first attempt, succeeds afterwards. For the retry path."""

    def __init__(self, failure: FailureClass | None = FailureClass.RETRYABLE_FAILURE) -> None:
        self.calls: list[str] = []
        self.failure = failure
        # Unique per INSTANCE, for the same reason RecordingExecutor's is: two instances
        # in one test are two executions, and an ExecutionId that repeats across them is
        # not a double being convenient — it is the §6.3 reuse guard firing on a collision
        # the test never meant to create, which makes an unrelated assertion fail for a
        # reason it does not name.
        self._token = uuid.uuid4().hex[:8]

    def execute(self, *, definition, step, attempt_id, run, now):  # noqa: ANN001, ANN201
        self.calls.append(step.step_id)
        request = attempt_request_digest(definition, step, run)
        execution_id = f"exec-{self._token}-{len(self.calls)}"
        if len(self.calls) == 1:
            return ExecutionOutcome(
                execution_id=execution_id,
                succeeded=False,
                request_digest=request,
                failure_class=self.failure,
                reason_code="TRANSIENT",
            )
        return ExecutionOutcome(
            execution_id=execution_id, succeeded=True, request_digest=request
        )


class AlwaysFailsExecutor:
    """Every attempt fails with the same class. For the bound paths."""

    def __init__(self, failure: FailureClass | None = FailureClass.RETRYABLE_FAILURE) -> None:
        self.calls: list[str] = []
        self.failure = failure
        self._token = uuid.uuid4().hex[:8]

    def execute(self, *, definition, step, attempt_id, run, now):  # noqa: ANN001, ANN201
        self.calls.append(step.step_id)
        return ExecutionOutcome(
            execution_id=f"exec-{self._token}-{len(self.calls)}",
            succeeded=False,
            request_digest=attempt_request_digest(definition, step, run),
            failure_class=self.failure,
            reason_code="AGAIN",
        )
