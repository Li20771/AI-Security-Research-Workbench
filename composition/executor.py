"""AI-14-B / B3 — Workflow `StepExecutor` -> real Agent execution (§22.1, §5.2).

```text
workflows.engine.begin_attempt()/complete_attempt()
        |
        |  executor is a PARAMETER (workflows/engine.py:238 StepExecutor)
        v
composition.executor.AgentStepExecutor        <- lives OUTSIDE workflows/
        |
        v
agents.runtime.run_execution()                <- AI-08 owns execution
```

### What the engine keeps, and what this class gets

```text
the ENGINE owns                        this executor owns
    the attempt and its number             building the execution request
    the retry decision and its bounds      delegating it to AI-08
    every state transition                 reporting what the execution produced
    the step deadline and the timeouts
    the approval gate
```

The executor holds no workflow state, mints nothing and decides nothing about
the run. It is handed a composed outer bound and MUST NOT widen it: a plan whose
per-invocation timeout exceeds the bound the engine composed is REFUSED, because
"the narrower bound governs" is AI-13's rule and an executor that exceeded it
would be running something other than the attempt that was admitted.

### What it deliberately does NOT report

```text
decision_id      AI-13 records the decision the attempt rested ON; nothing here
                 minted one, and AI-13 §15.2 says the phase records what it is
                 told rather than inventing a value. Left empty.
artifact_refs    AI-08 v1 produces references to no artifact store this layer can
artifact_bytes   reach, so both are reported empty/zero rather than estimated.
```

### The bound, stated honestly

`timeout_seconds` is the composed outer bound. AI-08 v1 has no execution-level
deadline (`AgentExecutionRequest` defines no such field and AI-08's runtime takes
none), so the bound cannot be handed to the runtime as a whole. What this class
does instead is checkable and no more: it refuses a delegation whose declared
per-invocation timeouts exceed the bound. It MUST NOT claim to have enforced a
wall-clock deadline it cannot enforce, and it does not.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from plugins.context import resolve_workspace
from plugins.context.errors import WorkspaceError

from agents.body import AgentBody
from agents.request import AgentExecutionRequest
from agents.result import AgentExecutionOutcome, AgentResult
from agents.vocabulary import AgentId, resolve_agent
from agents.runtime import run_execution

from workflows.definition import StepKind, WorkflowDefinition, WorkflowStep
from workflows.engine import ExecutionOutcome
from workflows.instants import plus_seconds
from workflows.policy import attempt_request_digest
from workflows.run import AttemptId, RunRecord
from workflows.vocabulary import FailureClass

from composition.errors import ExecutionRefused, WorkspaceRefused

__all__ = ["AgentStepExecutor"]

#: The longest task descriptor AI-08 accepts. Declared here so the refusal comes
#: from this layer with a reason, rather than as a constructor error from AI-08's
#: own boundary.
_MAX_TASK_CHARS = 128


def _task_descriptor(definition: WorkflowDefinition, step: WorkflowStep) -> str:
    """What this execution is for, as a bounded single-line descriptor.

    A descriptor, never content: it names the workflow, its revision and the step,
    which is exactly what the execution's own record may say (§6 of §7.3's rule
    that a request carries descriptors only).
    """
    described = f"{definition.workflow_id}/{definition.revision}/{step.step_id}"
    if len(described) > _MAX_TASK_CHARS or "\n" in described:
        raise ExecutionRefused(
            "the workflow/step descriptor is longer than AI-08's task field admits; "
            "refused rather than truncated, because a truncated descriptor names a "
            "different step"
        )
    return described


def _plan_of(body: AgentBody) -> tuple[Any, ...]:
    """The body's declared tool plan, when it has one.

    Read for ONE purpose: checking that it does not exceed the composed bound.
    Nothing here composes, reorders or rewrites a plan.
    """
    plan = getattr(body, "plan", ())
    return tuple(plan) if isinstance(plan, Sequence) else ()


class AgentStepExecutor:
    """The production `StepExecutor`. One workflow attempt, one AI-08 execution.

    Constructed by the composition with the body it may run and the workspace root
    that body executes in. It is NOT constructed inside `workflows/`, and
    `workflows/` never learns which Agent ran: the engine sees an
    `ExecutionOutcome` and nothing else.
    """

    def __init__(
        self,
        *,
        body: AgentBody,
        agent_id: object,
        workspace_root: str,
        registry: Any = None,
        policy: Any = None,
        clock: Any = None,
    ) -> None:
        # The identity the request will carry, resolved through the registry like
        # every other candidate (§7). A body that declares a different identity is
        # refused HERE rather than mid-execution: AI-08's own bodies raise on a
        # mismatch, and an execution that starts only to fail is worse than a
        # delegation that never began.
        self._agent_id: AgentId = resolve_agent(agent_id)
        declared = getattr(body, "agent_id", None)
        if declared is not None and resolve_agent(declared) is not self._agent_id:
            raise ExecutionRefused(
                f"this executor is configured for {self._agent_id} and was handed a "
                f"body that serves {declared}; attribution must not be rewritable by "
                "the composition (§5.1)"
            )
        self._body = body
        self._workspace_root = workspace_root
        self._registry = registry
        self._policy = policy
        self._clock = clock

    # -- workflows.engine.StepExecutor -------------------------------------

    def execute(
        self,
        *,
        definition: WorkflowDefinition,
        step: WorkflowStep,
        attempt_id: AttemptId,
        run: RunRecord,
        now: str,
        timeout_seconds: int,
    ) -> ExecutionOutcome:
        """Delegate one admitted attempt to AI-08, and report what it produced."""
        if step.kind is not StepKind.AGENT_EXECUTION:
            raise ExecutionRefused(
                f"step {step.step_id!r} is {step.kind} and has no invocation to "
                "delegate; a wait is not an execution (§6.1)"
            )

        # §5, §15: a run executes in the workspace it was created under. The root
        # this executor was configured with must BE that workspace — resolving a
        # different one would run the attempt somewhere the run never named.
        try:
            identity = resolve_workspace(self._workspace_root)
        except WorkspaceError as exc:
            raise WorkspaceRefused(
                f"the configured workspace root could not be resolved: {exc}"
            ) from exc
        if identity.workspace_id != run.workspace_identity:
            raise WorkspaceRefused(
                f"this executor is configured for workspace "
                f"{identity.workspace_id} and was handed a run of workspace "
                f"{run.workspace_identity}; a run executes in the workspace it was "
                "created under and there is no re-derivation in v1 (§5)"
            )

        # §10.3.1: the narrower bound governs. A plan whose per-invocation timeout
        # exceeds the composed outer bound would be running a request the admitted
        # attempt does not permit.
        for invocation in _plan_of(self._body):
            declared = getattr(invocation, "timeout_seconds", None)
            if isinstance(declared, int) and declared > timeout_seconds:
                raise ExecutionRefused(
                    f"a declared tool invocation asks for {declared}s and the "
                    f"composed outer bound is {timeout_seconds}s; the narrower "
                    "bound governs, and an executor MUST NOT widen it (§10.3.1, "
                    "§11.1)"
                )

        request = AgentExecutionRequest(
            agent_id=self._agent_id,
            workspace_root=self._workspace_root,
            task=_task_descriptor(definition, step),
            # The digest of the request the DEFINITION declares — the same value
            # the engine checks the outcome against. Using it here is what makes
            # the reported `request_digest` a fact rather than a promise.
            input_digest=attempt_request_digest(definition, step, run),
        )

        record = run_execution(
            request,
            body=self._body,
            registry=self._registry,
            policy=self._policy,
            clock=self._clock,
        )
        return self._outcome(record.result, definition, step, run)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _outcome(
        result: AgentResult,
        definition: WorkflowDefinition,
        step: WorkflowStep,
        run: RunRecord,
    ) -> ExecutionOutcome:
        """Map AI-08's terminal result onto AI-13's execution outcome.

        The failure mapping is the part worth reading:

        ```text
        COMPLETED -> succeeded, no class
        BLOCKED   -> BLOCKED_PRECONDITION   AI-08 blocks when a PRECONDITION failed
                                            (workspace unavailable, context
                                            unavailable) — the class names exactly
                                            what happened
        FAILED    -> NO class (unclassified)  AI-08 does not classify retryability,
                                            and AI-13 §9.1 says an unclassified
                                            failure assigns NO class, stops, and is
                                            never retried. Inventing
                                            RETRYABLE_FAILURE here would be this
                                            layer deciding retryability, which §9
                                            makes an EXECUTION fact.
        ```
        """
        if result.outcome is AgentExecutionOutcome.COMPLETED:
            succeeded, failure = True, None
        elif result.outcome is AgentExecutionOutcome.BLOCKED:
            succeeded, failure = False, FailureClass.BLOCKED_PRECONDITION
        else:
            succeeded, failure = False, None

        # AI-08 reports when the execution began and how long it took. AI-13
        # records the EXECUTION's own timing (§15.2), so the end is derived from
        # those two rather than taken from this layer's clock.
        seconds = max(0, math.ceil(max(0, result.duration_ms) / 1000))
        ended_at = plus_seconds(result.started_at, seconds)

        return ExecutionOutcome(
            execution_id=result.execution_id,
            succeeded=succeeded,
            request_digest=attempt_request_digest(definition, step, run),
            started_at=result.started_at,
            ended_at=ended_at,
            reason_code=result.reason_code,
            failure_class=failure,
            artifact_refs=(),
            decision_id="",
            artifact_bytes=0,
        )
