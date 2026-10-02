"""AI-09 error taxonomy.

These are **integration-layer** errors, and they are deliberately not merged with
anything AI-02 already defines. `providers.errors.ErrorClass` describes what a
provider did; nothing here is a provider outcome.

Three of them are refusals that happen before, or instead of, a successful
model output — a binding that could not be constructed, a workspace that does not
match, an invocation that did not succeed. None of them is a `PASS`, and none of
them may be turned into a successful reference (contract §19.4).

`CodexBody` reports `COMPLETED` unconditionally, so a backend that cannot produce
a real output MUST raise: `agents/runtime.py` maps a raised body exception onto
`FAILED`. Returning a reference for a failed call would report `COMPLETED` for
something that did not complete.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CodexAgentMismatch",
    "CodexBindingError",
    "CodexIntegrationError",
    "CodexInvocationError",
    "CodexWorkspaceMismatch",
]


class CodexIntegrationError(Exception):
    """Base for every AI-09 integration failure."""


class CodexBindingError(CodexIntegrationError):
    """A backend could not be constructed from the requested binding.

    A construction-time refusal: malformed ref, unsupported ref, a provider that
    runtime config does not enable, a model the enabled provider does not permit,
    or a reserved provider. The backend is not built, so no invocation can occur.
    """


class CodexAgentMismatch(CodexIntegrationError):
    """This backend was asked to produce for an Agent it does not serve.

    `CodexBody` already refuses a mismatched request upstream, so reaching this is
    a caller defect rather than an expected path. It is checked here anyway: a
    concrete backend that quietly served whichever AgentId it was handed would
    let attribution drift, and the refusal must happen before any provider
    activity rather than after one.
    """


class CodexWorkspaceMismatch(CodexIntegrationError):
    """The execution's workspace and the resolved context are not the same.

    A refusal, never a warning (contract §12.4). Nothing is sent, and no
    reference is produced, because a reference over misaligned inputs would
    attribute one workspace's work to another.
    """


class CodexInvocationError(CodexIntegrationError):
    """The invocation did not produce a usable, complete model output.

    Covers every non-success outcome and a truncated success. The typed
    `InvocationResult` is carried so the distinction is not lost: a pre-flight
    `BLOCKED` and a provider `ERROR` both map onto AI-08's `FAILED`, and this is
    where the difference survives (contract §19.4).
    """

    def __init__(self, message: str, *, result: Any) -> None:
        super().__init__(message)
        self.result = result
