"""AI-14-B — the refusals the composition issues.

Every refusal here is a STOP. None of them selects again, retries, falls back,
escalates or substitutes a default, because the composition is not a decision
layer: §4's authority matrix has exactly one authorizing entry and no selecting
entry at all.
"""

from __future__ import annotations

__all__ = [
    "CompositionError",
    "ExecutionRefused",
    "ProviderRefused",
    "SelectionRefused",
    "VerificationRefused",
    "WorkspaceRefused",
]


class CompositionError(Exception):
    """The base of every refusal this package issues.

    A `CompositionError` is never a terminal workflow state and never a failure
    CLASS: it is the composition declining to connect something, and the layer
    that owns the semantics decides what happens next.
    """


class SelectionRefused(CompositionError):
    """The Router did not SELECT, so there is nothing to execute.

    `NO_ELIGIBLE_MODEL` is a STOP (§22.1 B1). Trying the next candidate, dropping
    a constraint or reaching for a default would each be a fallback this phase
    does not have.
    """


class ProviderRefused(CompositionError):
    """A provider binding could not be built from the declared configuration.

    Raised where a binding is not runtime-enabled, names an unsupported model
    ref, or is handed an invoker the composition may not construct.
    """


class WorkspaceRefused(CompositionError):
    """The declared workspace root is not the workspace the run belongs to.

    A run executes in the workspace it was created under (§5, §15). This is a
    refusal rather than a substitution: resolving a different root would execute
    the attempt somewhere the run never named.
    """


class VerificationRefused(CompositionError):
    """A verification request could not be turned into an invocation.

    The controlled verification caller maps DECLARED targets to tool requests
    (AI-10 §11.2). A target with no declared plan, a target declared twice, or a
    plan that names something the request did not ask for is refused rather than
    guessed at.
    """


class ExecutionRefused(CompositionError):
    """An attempt cannot be delegated to an execution as asked.

    Raised before anything runs: a non-execution step, a workspace that is not
    the run's, a body that serves a different Agent, or a tool plan whose
    per-invocation timeout exceeds the composed outer bound.
    """

