"""AI-06's refusal vocabulary.

Contract §17. Each refusal carries a stable `reason_code` — never prose-as-code —
and **never an interpolated value**. AI-05's error doctrine records why: an error
message is a place a value escapes to a log, and a tool argument is a place a
credential can be. A message here names the field, the rule, and at most a shape
fact.

**These are not AI-04's errors and not AI-05's.** A guard refusal is already a
`GuardDecision` and travels as a `ToolResult` outcome (§9.2); it is not an
exception. What is here is AI-06 refusing its own input before Guard is asked.
"""

from __future__ import annotations


class ToolError(Exception):
    """Base class for every AI-06 refusal.

    `reason_code` is a stable, machine-readable label. It is not a message and
    it never contains a supplied value.
    """

    reason_code: str = "TOOL_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# --------------------------------------------------------------------------
# The request (§6.1) — refused before Guard is asked
# --------------------------------------------------------------------------


class ToolRequestMalformed(ToolError):
    """The request does not match §6.1.

    A field the contract does not define is refused rather than ignored, so a
    credential or a command string cannot ride along unremarked.
    """

    reason_code = "TOOL_REQUEST_MALFORMED"


class PermissionLevelMissing(ToolRequestMalformed):
    """`permission_level` is absent (contract §6.2).

    Distinct from a malformed request because the caller's repair is specific:
    supply the level, and do not let anyone guess it from a name.
    """

    reason_code = "PERMISSION_LEVEL_MISSING"


class TimeoutMissing(ToolRequestMalformed):
    """`execution.timeout_seconds` is absent (contract §11.3).

    There is no default and no "no timeout". A tool that hangs is a tool that
    has taken the session with it.
    """

    reason_code = "TIMEOUT_MISSING"


# --------------------------------------------------------------------------
# The registry (§7) — a declared capability that is absent
# --------------------------------------------------------------------------


class UnknownTool(ToolError):
    """No adapter is registered for this `tool_id` and `tool_version`."""

    reason_code = "UNKNOWN_TOOL"


class UnknownOperation(ToolError):
    """The tool declares no such operation."""

    reason_code = "UNKNOWN_OPERATION"


class ArgumentInvalid(ToolError):
    """An argument fails the operation's declared schema (contract §7.3).

    An argument the schema does not define is refused. A schema AI-06 cannot
    enforce is not a schema.
    """

    reason_code = "ARGUMENT_INVALID"


# --------------------------------------------------------------------------
# The workspace (§10)
# --------------------------------------------------------------------------


class WorkspaceUnresolvable(ToolError):
    """The declared root is absent, is not a directory, or cannot be reached."""

    reason_code = "WORKSPACE_UNRESOLVABLE"


class PathEscapesWorkspace(ToolError):
    """A path resolves outside the declared root (contract §10.3).

    Detected by resolution, not by string inspection: a symlink pointing out of
    the workspace resolves outside it and is refused with it.
    """

    reason_code = "PATH_ESCAPES_WORKSPACE"


# --------------------------------------------------------------------------
# The vehicle boundary (§12)
# --------------------------------------------------------------------------


class TargetRefused(ToolError):
    """The target is outside the v1 boundary (contract §12.3).

    This is AI-06's own gate, and it runs *before* Guard is asked. It is not a
    substitute for AI-04's gate: a request must pass both.
    """

    reason_code = "TARGET_REFUSED"


# --------------------------------------------------------------------------
# The execution boundary (§11)
# --------------------------------------------------------------------------


class ExecutionRefused(ToolError):
    """The operation cannot be executed within §11's boundary.

    Reached when an adapter would have to do something the boundary forbids —
    run outside its declared argv shape, inherit an environment it may not, or
    start a process the contract does not allow it to start.
    """

    reason_code = "EXECUTION_REFUSED"


class GuardUnavailable(ToolError):
    """No usable authorization could be obtained (contract §9.1, §9.2).

    Fail closed: an evaluator that raised is not an evaluator that allowed.
    This never becomes an execution.
    """

    reason_code = "GUARD_UNAVAILABLE"


# --------------------------------------------------------------------------
# The signing boundary (§15.8) — the capability is injected, and what it
# covers is checked before anything is signed
# --------------------------------------------------------------------------


class SignerUnavailable(ToolError):
    """No usable signing capability was injected (contract §15.8).

    The capability is the deployment's to inject and this repository's only
    to consume. An absent capability is REFUSED, not faked: no placeholder
    proof, no empty proof, no proof signed by anything else, and no
    submission asserted to be ready. A submission that was not signed is a
    submission with no proof, and AI-05 §7.3.8 already makes that REJECTED
    with AUTHENTICATION_PROOF_MISSING — a different phase's outcome, never
    this one's exception.
    """

    reason_code = "SIGNER_UNAVAILABLE"


class SignerTokenMismatch(ToolError):
    """The injected signer does not speak for the mapping's claimed producer.

    The mint-side token binding (§15.8): a signer speaking for another token
    cannot produce a proof for this claim, so the operation fails BEFORE the
    signer is asked to sign anything.
    """

    reason_code = "SIGNER_TOKEN_MISMATCH"


class SigningFieldUnmapped(ToolError):
    """A key, or a container shape, outside the closed field-source map.

    §15.8 fixes exactly three source classes for every field the signature
    covers, and a field with no defined source is REFUSED BEFORE SIGNING.
    This is also the refusal for the fields AI-05 itself generates
    (`evidence_id`, the digest fields, the `integrity` and `identity`
    blocks, `recorded_at`): a caller supplying one is choosing a field the
    contract does not assign to the caller.
    """

    reason_code = "SIGNING_FIELD_UNMAPPED"


class SigningPayloadMismatch(ToolError):
    """The mapping's execution payload is not the projection of the results.

    §15.2's projection is the ONLY way a ToolResult becomes record content,
    and a proof over content that is not the canonical projection would
    authenticate a claim about facts that were never projected — worse than
    no proof at all.
    """

    reason_code = "SIGNING_PAYLOAD_MISMATCH"


class SigningActorMismatch(ToolError):
    """The mapping's actor is not the owning phase's declared actor.

    The actor is a runtime fact of the execution, declared by the phase that
    ran it. A caller choosing a different one is signing a claim about an
    act somebody else performed.
    """

    reason_code = "SIGNING_ACTOR_MISMATCH"


class SigningWorkspaceMismatch(ToolError):
    """The mapping's workspace identity is not the single source's value.

    The workspace identity has one source (AI-15 §12.2), and the helper is
    given that source's value; a mapping naming another workspace is refused
    at the source rather than discovered downstream.
    """

    reason_code = "SIGNING_WORKSPACE_MISMATCH"


class SigningRegistryMismatch(ToolError):
    """The event is not consistent with the §6.5 registry row for the token.

    Kind, family, actor type and producer type are row-derived, not free
    declaration; a forged event kind or family is refused against the row
    before a signature exists.
    """

    reason_code = "SIGNING_REGISTRY_MISMATCH"


class SignerSignatureMalformed(ToolError):
    """The signer returned something that is not a 64-byte signature.

    The interface (§15.8) returns the signature over EXACTLY those bytes as
    64 raw bytes; a signer returning an encoding of them is unusable, and
    the failure is the helper's to make rather than the verifier's to
    discover.
    """

    reason_code = "SIGNER_SIGNATURE_MALFORMED"


__all__ = [
    "ArgumentInvalid",
    "ExecutionRefused",
    "GuardUnavailable",
    "PathEscapesWorkspace",
    "PermissionLevelMissing",
    "SignerSignatureMalformed",
    "SignerTokenMismatch",
    "SignerUnavailable",
    "SigningActorMismatch",
    "SigningFieldUnmapped",
    "SigningPayloadMismatch",
    "SigningRegistryMismatch",
    "SigningWorkspaceMismatch",
    "TargetRefused",
    "TimeoutMissing",
    "ToolError",
    "ToolRequestMalformed",
    "UnknownOperation",
    "UnknownTool",
    "WorkspaceUnresolvable",
]
