"""Opt-in live connectivity verification.

Contract §11 (live-test boundary) and §13 (AI-02-B6).

This is Layer 4: the only layer permitted to convert a `DECLARED` capability
into a dated observation. It is off by default, never invoked by the default
CI workflow, and never reachable from an ordinary pytest run.

The shape of a run:

    default / off
        no opt-in  -> NOT_RUN, no credential read, no network
        opt-in but a precondition fails -> BLOCKED, no network
        all preconditions hold -> probes execute

Two rules dominate:

**A live run produces evidence, never a grant.** A probe result is a dated
observation about one `model_ref` at one endpoint on one day. It cannot modify
a profile, and nothing here writes to Git. Promotion is a separate, reviewed
human action (§22).

**A probe proves only what it observed.** A successful text completion says
nothing about tool calling, structured output, streaming, reasoning, or prompt
caching. Each capability is probed separately or explicitly left alone, and
where no safe probe exists the capability stays `UNKNOWN` with the reason
recorded rather than being guessed at (§13).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping

from providers.credential import (
    CredentialConfigError,
    CredentialError,
    CredentialRef,
    resolve,
)
from providers.errors import PRECONDITION_CLASSES, ErrorClass
from providers.invocation import (
    BlockCode,
    InvocationContext,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    Invoker,
    Message,
    MessageRole,
    ProbeAuthorisation,
    RequestMetadata,
    StructuredOutputRequest,
    UsageStatus,
)
from providers.model_profile import (
    CapabilityName,
    CapabilityStatus,
    ModelProfile,
    StructuredOutputMode,
)
from providers.profile import ModelRef, ProviderProfile
from providers.redaction import redact
from providers.protocol import FinishState, Transport
from providers.transport import TransportSettings

#: Providers a live run may touch. `openai-compatible` is absent on purpose:
#: it is AI-09's reserved extension point and B6 must not implement a third
#: provider by pointing a probe at one (§8).
LIVE_PROVIDER_ALLOWLIST: frozenset[str] = frozenset({"deepseek", "mimo"})

#: The opt-in flag. Its presence with a truthy value is the first precondition;
#: nothing is read from the environment before this is satisfied.
LIVE_OPT_IN_ENV = "WORKBENCH_LIVE_TESTS"
LIVE_OPT_IN_VALUE = "1"

#: Fixed literal prompts. There is no user-supplied prompt path (§10): a probe
#: sends one of these or it does not send.
LIVE_TEXT_PROMPT = "Reply with exactly: WORKBENCH_LIVE_OK"
LIVE_TOOL_PROMPT = (
    "Call the provided tool exactly once with value \"ok\". "
    "Do not answer in prose."
)
LIVE_STRUCTURED_PROMPT = 'Return only a JSON object of the form {"status": "ok"}.'

#: One provider-agnostic tool schema. Deliberately trivial: the probe observes
#: whether the mechanism round-trips, not whether the model chooses well.
LIVE_TOOL_SCHEMA: Mapping[str, Any] = {
    "type": "function",
    "function": {
        "name": "workbench_probe",
        "description": "Records a fixed probe value.",
        "parameters": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    },
}

#: Bounded output. A probe that costs real money is a probe that will not be
#: run, and the contract requires live checks be low-cost (§11.4).
LIVE_MAX_OUTPUT = 64
LIVE_TIMEOUT_MS = 30_000

#: §11.4: no retry, so a failure is observed rather than retried into
#: ambiguity.
LIVE_MAX_RETRIES = 0


class LiveRunStatus(StrEnum):
    """The live-test status vocabulary (§11.2). Frozen."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"


class LiveBlockCode(StrEnum):
    """Machine-readable reason a live run did not execute (§11.3).

    An invocation-layer vocabulary, like `BlockCode`: none of these is a
    provider failure, because none of them reached a provider.
    """

    OPT_IN_ABSENT = "opt_in_absent"
    PROVIDER_NOT_ALLOWLISTED = "provider_not_allowlisted"
    UNKNOWN_PROVIDER = "unknown_provider"
    UNKNOWN_MODEL = "unknown_model"
    CREDENTIAL_MISSING = "credential_missing"
    CREDENTIAL_UNSUPPORTED = "credential_unsupported"
    CREDENTIAL_CONFIG_DEFECT = "credential_config_defect"
    #: The experiment id was not a valid identifier. Caller-supplied text
    #: that is not an identifier must not reach an evidence record.
    INVALID_EXPERIMENT_ID = "invalid_experiment_id"


class ProbeOutcome(StrEnum):
    """What one probe observed.

    `INCONCLUSIVE` is distinct from `FAIL`: a model that answers a tool prompt
    in prose has not demonstrated that tool calling is broken, only that this
    prompt did not elicit it. Collapsing the two would turn a weak probe into a
    false negative.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True, slots=True)
class ProbeDefinition:
    """What a capability probe does, and what its result would mean (§12).

    `available=False` means no safe, bounded, repeatable probe exists in this
    phase. The capability then stays `UNKNOWN` with the reason recorded, rather
    than being guessed at from documentation or from a passing text call.
    """

    probe_id: str
    capability: CapabilityName
    description: str
    expected_observation: str
    success_condition: str
    failure_condition: str
    available: bool = True
    unavailable_reason: str | None = None
    prompt: str | None = None

    def __post_init__(self) -> None:
        if not self.available and not self.unavailable_reason:
            raise ValueError(
                f"{self.probe_id}: an unavailable probe must record why; a "
                "capability is not left unverified without a reason (§13)"
            )
        if self.available and not self.prompt:
            raise ValueError(f"{self.probe_id}: an available probe needs a prompt")


#: The probe catalogue. Every capability is either probed or explicitly
#: declined with a reason -- there is no third state where a capability is
#: silently skipped.
PROBE_CATALOG: Mapping[CapabilityName, ProbeDefinition] = {
    CapabilityName.TOOL_CALLING: ProbeDefinition(
        probe_id="tool_call_round_trip",
        capability=CapabilityName.TOOL_CALLING,
        description=(
            "Send one provider-agnostic tool schema and a prompt that requires "
            "it, and normalize whatever comes back."
        ),
        expected_observation=(
            "finish_state TOOL_CALLS with at least one normalized tool call "
            "whose name matches the schema"
        ),
        success_condition=(
            "a tool call is returned and maps into tool_calls. Which tool the "
            "model chose is selection correctness (AI-11), not the mechanism "
            "this capability records"
        ),
        failure_condition=(
            "none observable: a provider error is inconclusive, and a call "
            "that cannot be normalized is refused as PROTOCOL rather than "
            "recorded as a negative observation"
        ),
        prompt=LIVE_TOOL_PROMPT,
    ),
    CapabilityName.STRUCTURED_OUTPUT: ProbeDefinition(
        probe_id="structured_output_json_object",
        capability=CapabilityName.STRUCTURED_OUTPUT,
        description=(
            "Request json_object mode and check the result is a JSON object. "
            "Deliberately json_object and not json_schema: the schema wrapper "
            "shape is unverified for both providers, and §6.7 forbids treating "
            "the two modes as equivalent."
        ),
        expected_observation=(
            "the provider accepts response_format json_object and returns "
            "parseable JSON"
        ),
        success_condition="the response is a JSON object",
        failure_condition="the provider rejects the request, or returns non-JSON",
        prompt=LIVE_STRUCTURED_PROMPT,
    ),
    CapabilityName.STREAMING: ProbeDefinition(
        probe_id="streaming_sse",
        capability=CapabilityName.STREAMING,
        description="Send stream=true and normalize the streamed response.",
        expected_observation="a streamed response normalized into the envelope",
        success_condition="the stream normalizes",
        failure_condition="the stream cannot be normalized",
        available=False,
        unavailable_reason=(
            "no transport supports streaming: the only shipped Transport "
            "performs single request/response, and ProviderResponse models no "
            "streamed chunks. Probing streaming would require implementing SSE "
            "handling, which is transport work this phase does not own. "
            "streaming therefore stays UNKNOWN."
        ),
    ),
    CapabilityName.REASONING: ProbeDefinition(
        probe_id="reasoning_separation",
        capability=CapabilityName.REASONING,
        description="Observe reasoning content in its own field.",
        expected_observation="a non-null reasoning field, with text uncontaminated",
        success_condition="reasoning is returned separately from text",
        failure_condition="reasoning appears inside text",
        available=False,
        unavailable_reason=(
            "no bounded, repeatable probe exists: whether a model emits "
            "reasoning content depends on the model and on the prompt, and a "
            "run that produces none is inconclusive rather than negative. A "
            "probe that cannot distinguish 'this model does not reason' from "
            "'this prompt did not trigger reasoning' proves nothing. "
            "reasoning therefore stays UNKNOWN."
        ),
    ),
    CapabilityName.PROMPT_CACHING: ProbeDefinition(
        probe_id="prompt_cache_reporting",
        capability=CapabilityName.PROMPT_CACHING,
        description="Observe cache read/write token reporting.",
        expected_observation="cache_read_tokens or cache_write_tokens reported",
        success_condition="the provider reports a cache token count",
        failure_condition="no cache count is reported",
        available=False,
        unavailable_reason=(
            "a cache hit requires a repeated prompt large enough to be cached, "
            "which contradicts §11.4's bounded, minimal, low-cost prompt "
            "requirement. A probe that must send bulk text to work is not a "
            "probe this phase may run. prompt_caching therefore stays UNKNOWN."
        ),
    ),
}

#: Endpoint hosts are recorded, not full URLs: a URL could carry a query or a
#: userinfo segment, and evidence needs the identity of the target, not its
#: traffic.
_HOST_RE = re.compile(r"^https?://(?P<host>[^/?#]+)", re.IGNORECASE)


def endpoint_host(url: str) -> str | None:
    """The host of an endpoint URL, or `None` if it is not a URL.

    Any userinfo is dropped: `https://user:pass@host/` would otherwise put a
    credential into evidence.
    """
    match = _HOST_RE.match(url or "")
    if match is None:
        return None
    host = match.group("host")
    return host.rsplit("@", 1)[-1].split(":", 1)[0].lower()


def new_run_id(provider_id: str) -> str:
    """A unique id for one live run.

    Keying a run only on its provider collides: same provider, same model,
    same day, run twice, and the evidence file for the second silently
    overwrites the first. A timestamp is not an identifier either -- two runs
    can share a second. The provider prefix is kept for readability only; the
    uniqueness comes from the uuid.
    """
    safe_provider = (
        provider_id if provider_id in LIVE_PROVIDER_ALLOWLIST else "provider"
    )
    return f"LV-{safe_provider}-{uuid.uuid4().hex[:12]}"


def split_model_ref(model_ref: str) -> tuple[str, str]:
    """Best-effort attribution split for a refusal record. Never raises.

    The gate refuses a malformed ref before anything reaches here, but the
    refusal still has to be attributable to something, and a record that
    raised on the way out would report a crash instead of a BLOCKED code.
    """
    provider_id, _, model_id = (model_ref or "").partition("/")
    return provider_id, model_id


#: Stands in for caller-supplied text that did not name a real model. A
#: refusal does not need the input to be actionable, and echoing it back would
#: carry whatever it happens to contain (§10).
REDACTED_MODEL_REF = "<invalid>"

#: The shape an experiment id must have to be recorded. An id is an
#: identifier, not free text: anything else is caller-supplied prose that
#: would end up in an evidence file.
EXPERIMENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def safe_caller_text(value: str | None, *, limit: int = 120) -> str:
    """Sanitize caller-supplied text before it reaches a record or a log.

    Two boundaries at once, using machinery that already exists rather than a
    bespoke filter: credential-shaped material is removed by the same
    `redact()` the provider error path uses, line breaks are flattened so a
    value cannot forge extra log lines, and the result is length-capped so an
    oversized input cannot flood an evidence file.
    """
    sanitized = redact(value) or ""
    sanitized = sanitized.replace("\r", " ").replace("\n", " ")
    if len(sanitized) > limit:
        sanitized = sanitized[:limit] + "..."
    return sanitized


def safe_model_ref_input(model_ref: str | None) -> str:
    """The model ref if it is well formed, otherwise a placeholder.

    A malformed ref is arbitrary caller text. Naming it back would put that
    text into the evidence record, and someone pasting the wrong thing into a
    dispatch field is exactly how a credential would arrive.
    """
    try:
        ModelRef.parse(model_ref)
    except Exception:
        return REDACTED_MODEL_REF
    return safe_caller_text(model_ref, limit=200)


def is_valid_experiment_id(value: str) -> bool:
    """An experiment id must be an identifier, not arbitrary text."""
    return bool(EXPERIMENT_ID_RE.match(value or ""))


@dataclass(frozen=True, slots=True)
class LiveGate:
    """The precondition decision (§11.3)."""

    allowed: bool
    status: LiveRunStatus
    code: LiveBlockCode | None = None
    detail: str | None = None

    @property
    def is_blocked(self) -> bool:
        return self.status is LiveRunStatus.BLOCKED

    @property
    def is_not_run(self) -> bool:
        return self.status is LiveRunStatus.NOT_RUN

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": str(self.status),
            "code": str(self.code) if self.code else None,
            "detail": self.detail,
        }


def evaluate_preconditions(
    *,
    provider_id: str,
    model_ref: str,
    providers: Mapping[str, ProviderProfile],
    models: Mapping[str, ModelProfile],
    environ: Mapping[str, str] | None,
    opt_in: str | None,
    experiment_id: str | None = None,
) -> LiveGate:
    """Decide whether a live run may proceed (§11.3).

    Ordered so the cheapest, safest refusal wins: the opt-in flag is checked
    before anything else, and no credential is read until the provider and
    model are known to exist and be allowed. A run that fails any check
    performs no network activity and no context is passed to a transport.
    """
    if opt_in != LIVE_OPT_IN_VALUE:
        # NOT_RUN rather than BLOCKED: nothing was attempted, and §11.2 keeps
        # those distinct. A skipped run is not a failure, and it is not a pass.
        return LiveGate(
            allowed=False,
            status=LiveRunStatus.NOT_RUN,
            code=LiveBlockCode.OPT_IN_ABSENT,
            detail=(
                f"{LIVE_OPT_IN_ENV} is not {LIVE_OPT_IN_VALUE!r}; live "
                "verification is opt-in and performs no network activity "
                "otherwise"
            ),
        )

    # Caller-supplied text that is not an identifier must not reach an
    # evidence record, so it is refused before anything else is consulted.
    if experiment_id is not None and not is_valid_experiment_id(experiment_id):
        return LiveGate(
            allowed=False,
            status=LiveRunStatus.BLOCKED,
            code=LiveBlockCode.INVALID_EXPERIMENT_ID,
            detail=(
                "experiment_id must match "
                f"{EXPERIMENT_ID_RE.pattern}; the supplied value was refused "
                "and is not echoed"
            ),
        )

    if provider_id not in LIVE_PROVIDER_ALLOWLIST:
        return LiveGate(
            allowed=False,
            status=LiveRunStatus.BLOCKED,
            code=LiveBlockCode.PROVIDER_NOT_ALLOWLISTED,
            detail=(
                f"{provider_id!r} is not in the live-test allowlist "
                f"{sorted(LIVE_PROVIDER_ALLOWLIST)}. This is a deliberate "
                "boundary, not a missing registration: an unlisted provider "
                "has no profile review behind it, and §8 forbids extending the "
                "allowlist by pointing a probe at one."
            ),
        )

    # Parsed before any registry lookup, and inside a guard: a malformed ref
    # must produce a refusal, not an exception. A refusal that raises is not a
    # refusal, and it would surface as a runner crash rather than a code.
    try:
        parsed_ref = ModelRef.parse(model_ref)
    except Exception as exc:
        return LiveGate(
            allowed=False,
            status=LiveRunStatus.BLOCKED,
            code=LiveBlockCode.UNKNOWN_MODEL,
            # The input is not echoed: it is caller text, and the refusal
            # is actionable without it.
            detail=(
                f"model_ref {safe_model_ref_input(model_ref)!r} is not a "
                "valid provider/model reference"
            ),
        )

    provider = providers.get(provider_id)
    if provider is None:
        return LiveGate(
            allowed=False,
            status=LiveRunStatus.BLOCKED,
            code=LiveBlockCode.UNKNOWN_PROVIDER,
            detail=f"provider {provider_id!r} is not registered",
        )

    if model_ref not in {ref for ref in models}:
        return LiveGate(
            allowed=False,
            status=LiveRunStatus.BLOCKED,
            code=LiveBlockCode.UNKNOWN_MODEL,
            detail=(
                f"model {safe_model_ref_input(model_ref)!r} is not registered; "
                "a live run verifies a "
                "registered model, never an arbitrary model id"
            ),
        )

    if parsed_ref.provider_id != provider_id:
        return LiveGate(
            allowed=False,
            status=LiveRunStatus.BLOCKED,
            code=LiveBlockCode.UNKNOWN_MODEL,
            detail=(
                f"model_ref {safe_model_ref_input(model_ref)!r} does not "
                f"belong to provider {safe_caller_text(provider_id)!r}"
                f"{provider_id!r}"
            ),
        )

    try:
        resolve(CredentialRef.parse(provider.credential.ref), environ=environ)
    except CredentialError as exc:
        code = (
            LiveBlockCode.CREDENTIAL_UNSUPPORTED
            if exc.error_class is ErrorClass.CREDENTIAL_UNSUPPORTED
            else LiveBlockCode.CREDENTIAL_MISSING
        )
        return LiveGate(
            allowed=False,
            status=LiveRunStatus.BLOCKED,
            code=code,
            detail=str(exc),
        )
    except CredentialConfigError as exc:
        return LiveGate(
            allowed=False,
            status=LiveRunStatus.BLOCKED,
            code=LiveBlockCode.CREDENTIAL_CONFIG_DEFECT,
            detail=str(exc),
        )

    return LiveGate(allowed=True, status=LiveRunStatus.PASS)


@dataclass(frozen=True, slots=True)
class CapabilityObservation:
    """One capability's result, with what it would and would not support."""

    capability: CapabilityName
    probe_id: str
    outcome: ProbeOutcome
    observed: str
    candidate_status: CapabilityStatus
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": str(self.capability),
            "probe_id": self.probe_id,
            "outcome": str(self.outcome),
            "observed": self.observed,
            "candidate_status": str(self.candidate_status),
            "reason": self.reason,
        }


def candidate_status(
    outcome: ProbeOutcome, prior: CapabilityStatus = CapabilityStatus.UNKNOWN
) -> CapabilityStatus:
    """The truth state a probe outcome would support (§8.1).

    A *candidate*: the profile is never modified by a live run. This is what a
    human reviewer would be entitled to record, and nothing more.
    """
    if outcome is ProbeOutcome.PASS:
        return CapabilityStatus.VERIFIED
    if outcome is ProbeOutcome.FAIL:
        return CapabilityStatus.UNAVAILABLE
    if outcome is ProbeOutcome.INCONCLUSIVE:
        return CapabilityStatus.NOT_VERIFIED
    # NOT_RUN leaves the record where it was: nothing was observed.
    return prior


@dataclass(frozen=True, slots=True)
class LiveProbeRecord:
    """The normalized, sanitized record of one probe (§11.5, §14).

    Carries no credential and no raw request or response body.
    """

    probe_id: str
    capability: CapabilityName | None
    status: LiveRunStatus
    provider_id: str
    model_id: str
    model_ref: str
    endpoint_host: str | None
    finish_state: FinishState | None
    usage_status: UsageStatus | None
    error_class: ErrorClass | None
    latency_ms: int | None
    request_id: str | None
    observed: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "capability": str(self.capability) if self.capability else None,
            "status": str(self.status),
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "model_ref": self.model_ref,
            "endpoint_host": self.endpoint_host,
            "finish_state": str(self.finish_state) if self.finish_state else None,
            "usage_status": str(self.usage_status) if self.usage_status else None,
            "error_class": str(self.error_class) if self.error_class else None,
            "latency_ms": self.latency_ms,
            "request_id": self.request_id,
            "observed": self.observed,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class LiveVerificationRecord:
    """One live verification run (§14).

    Dated and bound to provider, model, and endpoint host (§24): a result
    describes one model at one endpoint on one day, and propagates to nothing
    else.
    """

    run_id: str
    timestamp: str
    provider_id: str
    model_id: str
    model_ref: str
    endpoint_host: str | None
    status: LiveRunStatus
    gate: LiveGate
    probes: tuple[LiveProbeRecord, ...] = ()
    observations: tuple[CapabilityObservation, ...] = ()
    boundary: str = (
        "A live run produces evidence, not a grant. It cannot modify a profile "
        "and does not write to Git. Promotion is a separate reviewed action "
        "(§22)."
    )
    experiment_id: str | None = None

    @property
    def executed(self) -> bool:
        return self.status in (LiveRunStatus.PASS, LiveRunStatus.FAIL)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "model_ref": self.model_ref,
            "endpoint_host": self.endpoint_host,
            "status": str(self.status),
            "experiment_id": self.experiment_id,
            "gate": self.gate.to_dict(),
            "probes": [probe.to_dict() for probe in self.probes],
            "observations": [obs.to_dict() for obs in self.observations],
            "boundary": self.boundary,
        }


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class LiveVerifier:
    """Runs the opt-in live probes through the existing invocation path.

    Reuses `Invoker`, the protocol adapter, and the injected `Transport`. There
    is no second invocation API and no second metrics path: a probe is an
    ordinary invocation with a fixed prompt and a bounded output.
    """

    def __init__(
        self,
        context: InvocationContext,
        *,
        clock: Any = None,
    ) -> None:
        self._context = context
        kwargs = {} if clock is None else {"clock": clock}
        self._invoker = Invoker(context, **kwargs)

    def verify(
        self,
        *,
        provider_id: str,
        model_ref: str,
        opt_in: str | None = None,
        capabilities: tuple[CapabilityName, ...] | None = None,
        experiment_id: str | None = None,
    ) -> LiveVerificationRecord:
        """Evaluate preconditions, then probe. Never raises for a refusal."""
        # Shape is validated below on the raw value, but everything recorded
        # or forwarded uses this one. The two checks are different questions:
        # an id can be identifier-shaped *and* secret-shaped, because hyphens
        # are legal in both. Validation rejects text that is not an id;
        # redaction removes credential-shaped material from text that is.
        valid_experiment_id = (
            experiment_id
            if experiment_id is not None and is_valid_experiment_id(experiment_id)
            else None
        )
        safe_experiment_id = (
            None
            if valid_experiment_id is None
            else safe_caller_text(valid_experiment_id)
        )
        environ = self._context.environ
        gate = evaluate_preconditions(
            provider_id=provider_id,
            model_ref=model_ref,
            providers=self._context.providers,
            models=self._context.models,
            environ=environ,
            opt_in=environ.get(LIVE_OPT_IN_ENV) if opt_in is None and environ else opt_in,
            experiment_id=experiment_id,
        )
        # Never raises: the gate has already refused a malformed ref, and a
        # refusal record must still be attributable.
        _, ref_model_id = split_model_ref(model_ref)
        provider = self._context.providers.get(provider_id)
        host = (
            endpoint_host(provider.endpoint.effective_url) if provider else None
        )

        if not gate.allowed:
            return LiveVerificationRecord(
                run_id=new_run_id(provider_id),
                timestamp=_now(),
                provider_id=safe_caller_text(provider_id),
                model_id=safe_caller_text(ref_model_id),
                model_ref=safe_model_ref_input(model_ref),
                endpoint_host=host,
                status=gate.status,
                gate=gate,
                experiment_id=safe_experiment_id,
            )

        # `is not None`, not truthiness: an empty tuple means "probe no
        # capabilities", which is a legitimate request and must not silently
        # expand into probing all of them.
        selected = (
            self.selected_capabilities() if capabilities is None else capabilities
        )
        probes: list[LiveProbeRecord] = []
        observations: list[CapabilityObservation] = []

        baseline = self._probe_text(provider_id, model_ref, experiment_id)
        probes.append(baseline)

        if baseline.status is not LiveRunStatus.PASS:
            # A failed baseline makes every capability probe meaningless, and
            # running them anyway would multiply cost for no information.
            for capability in selected:
                definition = PROBE_CATALOG[capability]
                observations.append(
                    CapabilityObservation(
                        capability=capability,
                        probe_id=definition.probe_id,
                        outcome=ProbeOutcome.NOT_RUN,
                        observed="baseline probe did not succeed",
                        candidate_status=self._prior_status(model_ref, capability),
                        reason="not probed: the text baseline did not succeed",
                    )
                )
            return LiveVerificationRecord(
                run_id=new_run_id(provider_id),
                timestamp=_now(),
                provider_id=provider_id,
                model_id=ref_model_id,
                model_ref=model_ref,
                endpoint_host=host,
                status=baseline.status,
                gate=gate,
                probes=tuple(probes),
                observations=tuple(observations),
                experiment_id=safe_experiment_id,
            )

        for capability in selected:
            definition = PROBE_CATALOG[capability]
            if not definition.available:
                observations.append(
                    CapabilityObservation(
                        capability=capability,
                        probe_id=definition.probe_id,
                        outcome=ProbeOutcome.NOT_RUN,
                        observed="no probe executed",
                        candidate_status=self._prior_status(model_ref, capability),
                        reason=definition.unavailable_reason,
                    )
                )
                continue
            probe, observation = self._run_capability_probe(
                capability, definition, provider_id, model_ref, experiment_id
            )
            probes.append(probe)
            observations.append(observation)

        return LiveVerificationRecord(
            run_id=new_run_id(provider_id),
            timestamp=_now(),
            provider_id=provider_id,
            model_id=ref_model_id,
            model_ref=model_ref,
            endpoint_host=host,
            status=LiveRunStatus.PASS,
            gate=gate,
            probes=tuple(probes),
            observations=tuple(observations),
            experiment_id=safe_experiment_id,
        )

    def selected_capabilities(self) -> tuple[CapabilityName, ...]:
        """Every capability in the catalogue, probed or explicitly declined."""
        return tuple(PROBE_CATALOG)

    def _prior_status(
        self, model_ref: str, capability: CapabilityName
    ) -> CapabilityStatus:
        """The capability's current truth state, for a NOT_RUN candidate.

        A probe that did not run observed nothing, so it must leave the record
        where it was. Defaulting to UNKNOWN would erase a DECLARED entry a
        later phase is entitled to rely on, and would turn "we did not look"
        into "we looked and found nothing".
        """
        model = self._context.models.get(model_ref)
        if model is None:
            return CapabilityStatus.UNKNOWN
        return model.capability(capability).status

    # -- probes ----------------------------------------------------------

    def _request(
        self,
        model_ref: str,
        *,
        prompt: str,
        tools: tuple[Mapping[str, Any], ...] = (),
        structured_output: StructuredOutputRequest | None = None,
        experiment_id: str | None,
    ) -> InvocationRequest:
        return InvocationRequest(
            model_ref=model_ref,
            messages=(Message(MessageRole.USER, prompt),),
            timeout_ms=LIVE_TIMEOUT_MS,
            tools=tools,
            structured_output=structured_output,
            stream=False,
            generation=self._generation(),
            metadata=RequestMetadata(
                experiment_id=experiment_id,
                purpose="live_verification",
                agent="workbench",
            ),
        )

    @staticmethod
    def _generation():
        from providers.invocation import GenerationParameters

        return GenerationParameters(max_output=LIVE_MAX_OUTPUT)

    def _invoke(
        self,
        request: InvocationRequest,
        authorisation: ProbeAuthorisation | None = None,
    ) -> InvocationResult:
        """Run one invocation, optionally under a B6 probe authorisation.

        The authorisation covers exactly one capability on exactly one model
        (§7.1's B6 carve-out), so a fresh invoker is built per probe rather
        than one invoker carrying a standing allowance.
        """
        if authorisation is None:
            return self._invoker.invoke(request)
        invoker = Invoker(self._context, probe_authorisation=authorisation)
        return invoker.invoke(request)

    def _probe_text(
        self, provider_id: str, model_ref: str, experiment_id: str | None
    ) -> LiveProbeRecord:
        request = self._request(
            model_ref, prompt=LIVE_TEXT_PROMPT, experiment_id=experiment_id
        )
        result = self._invoke(request)
        provider = self._context.providers.get(provider_id)
        host = endpoint_host(provider.endpoint.effective_url) if provider else None

        if result.status is InvocationStatus.BLOCKED:
            status = LiveRunStatus.BLOCKED
        elif result.status is InvocationStatus.ERROR:
            status = LiveRunStatus.FAIL
        elif result.finish_state is FinishState.STOP:
            status = LiveRunStatus.PASS
        else:
            # §7.3: LENGTH is a truncation warning and UNKNOWN must not be read
            # as STOP. A baseline whose answer is incomplete has not shown a
            # clean round trip, so it is inconclusive rather than a pass --
            # and reporting it as FAIL would blame the provider for a
            # truncation that says nothing about connectivity.
            status = LiveRunStatus.UNKNOWN

        return LiveProbeRecord(
            probe_id="text_completion",
            capability=None,
            status=status,
            provider_id=result.provider_id,
            model_id=result.model_id,
            model_ref=result.model_ref,
            endpoint_host=host,
            finish_state=result.finish_state,
            usage_status=result.usage.usage_status if result.usage else None,
            error_class=result.error.error_class if result.error else None,
            latency_ms=result.latency.total_ms,
            request_id=result.request_id,
            observed=_describe(result),
            reason=(
                result.blocked.detail
                if result.blocked
                else (str(result.error) if result.error else None)
            ),
        )

    def _run_capability_probe(
        self,
        capability: CapabilityName,
        definition: ProbeDefinition,
        provider_id: str,
        model_ref: str,
        experiment_id: str | None,
    ) -> tuple[LiveProbeRecord, CapabilityObservation]:
        if capability is CapabilityName.TOOL_CALLING:
            request = self._request(
                model_ref,
                prompt=definition.prompt or LIVE_TOOL_PROMPT,
                tools=(LIVE_TOOL_SCHEMA,),
                experiment_id=experiment_id,
            )
        elif capability is CapabilityName.STRUCTURED_OUTPUT:
            request = self._request(
                model_ref,
                prompt=definition.prompt or LIVE_STRUCTURED_PROMPT,
                structured_output=StructuredOutputRequest(
                    StructuredOutputMode.JSON_OBJECT
                ),
                experiment_id=experiment_id,
            )
        else:  # pragma: no cover - catalogue only defines available probes above
            raise AssertionError(f"no probe runner for {capability}")

        authorisation = ProbeAuthorisation(
            capability=capability,
            model_ref=model_ref,
            authorised_by="AI-02-B6 live verification",
        )
        result = self._invoke(request, authorisation)
        provider = self._context.providers.get(provider_id)
        host = endpoint_host(provider.endpoint.effective_url) if provider else None

        outcome, observed, reason = self._judge(capability, result)

        probe = LiveProbeRecord(
            probe_id=definition.probe_id,
            capability=capability,
            status={
                ProbeOutcome.PASS: LiveRunStatus.PASS,
                ProbeOutcome.FAIL: LiveRunStatus.FAIL,
                ProbeOutcome.INCONCLUSIVE: LiveRunStatus.UNKNOWN,
                ProbeOutcome.NOT_RUN: LiveRunStatus.NOT_RUN,
            }[outcome],
            provider_id=result.provider_id,
            model_id=result.model_id,
            model_ref=result.model_ref,
            endpoint_host=host,
            finish_state=result.finish_state,
            usage_status=result.usage.usage_status if result.usage else None,
            error_class=result.error.error_class if result.error else None,
            latency_ms=result.latency.total_ms,
            request_id=result.request_id,
            observed=observed,
            reason=reason,
        )
        observation = CapabilityObservation(
            capability=capability,
            probe_id=definition.probe_id,
            outcome=outcome,
            observed=observed,
            candidate_status=candidate_status(outcome),
            reason=reason,
        )
        return probe, observation

    def _judge(
        self, capability: CapabilityName, result: InvocationResult
    ) -> tuple[ProbeOutcome, str, str | None]:
        if result.status is InvocationStatus.BLOCKED:
            return (
                ProbeOutcome.NOT_RUN,
                "the request was refused before reaching the provider",
                result.blocked.detail if result.blocked else "blocked",
            )
        if result.status is InvocationStatus.ERROR:
            # A provider, transport, or runtime failure proves nothing about
            # whether the capability exists. A TIMEOUT, a 429, a 500, an auth
            # failure, or a cancelled call are all failures of *this attempt*;
            # recording any of them as UNAVAILABLE would assert a negative
            # observation that was never made.
            #
            # A clean negative requires a successful response that contradicts
            # the capability -- the structured_output judgement below is the
            # one path that can produce one.
            error_class = result.error.error_class if result.error else "UNKNOWN"
            return (
                ProbeOutcome.INCONCLUSIVE,
                f"the probe could not complete: {error_class}",
                f"{error_class} is a failure of this attempt, not an "
                "observation that the capability is absent",
            )

        if capability is CapabilityName.TOOL_CALLING:
            if result.finish_state is not FinishState.TOOL_CALLS:
                # The mechanism shows up as the provider signalling a
                # tool-call turn. A response that did not signal it is not a
                # completed observation of the mechanism, however it reads.
                return (
                    ProbeOutcome.INCONCLUSIVE,
                    f"no tool-call turn was signalled "
                    f"(finish_state={result.finish_state})",
                    "the observation must agree with TOOL_CALLS semantics; "
                    "this response is not a completed tool-call turn",
                )
            if result.tool_calls:
                # §6.7: tool_calling records that the *mechanism* works --
                # tools are accepted, calls are returned, and calls map into
                # the normalized result. Which tool the model chose is
                # selection correctness, which AI-11 measures; asserting it
                # here would turn an AI-02 capability into an AI-11 benchmark.
                names = sorted({call.name for call in result.tool_calls})
                observed = (
                    f"finish_state={result.finish_state}, tool_calls={names}"
                )
                if "workbench_probe" not in names:
                    observed += (
                        "; the returned name differs from the schema sent, "
                        "which is tool-selection correctness (AI-11), not the "
                        "mechanism this capability records"
                    )
                return ProbeOutcome.PASS, observed, None
            # Answered in prose. Not evidence the mechanism is broken.
            return (
                ProbeOutcome.INCONCLUSIVE,
                f"no tool call was returned (finish_state={result.finish_state})",
                "the model answered without calling the tool; this prompt did "
                "not elicit a tool call and the probe cannot distinguish "
                "'unsupported' from 'not chosen'",
            )

        if capability is CapabilityName.STRUCTURED_OUTPUT:
            import json

            if result.finish_state is not FinishState.STOP:
                # Checked before the text is read. A truncated answer can still
                # contain parseable JSON, and accepting it would report a
                # partial response as a demonstrated capability.
                return (
                    ProbeOutcome.INCONCLUSIVE,
                    f"the answer was not completed "
                    f"(finish_state={result.finish_state})",
                    f"finish_state {result.finish_state} is not a completed "
                    "answer, so its content cannot demonstrate the capability",
                )

            if result.text is None:
                return (
                    ProbeOutcome.INCONCLUSIVE,
                    "no text was returned",
                    "nothing was returned to inspect",
                )
            try:
                parsed = json.loads(result.text)
            except json.JSONDecodeError:
                return (
                    ProbeOutcome.FAIL,
                    "the response was not parseable JSON",
                    "json_object mode was requested and the output was not JSON",
                )
            if not isinstance(parsed, dict):
                return (
                    ProbeOutcome.FAIL,
                    f"the response was JSON but not an object ({type(parsed).__name__})",
                    "json_object mode was requested and the output was not an object",
                )
            return (
                ProbeOutcome.PASS,
                "the provider accepted response_format json_object and returned "
                "a JSON object",
                None,
            )

        raise AssertionError(f"no judge for {capability}")  # pragma: no cover


def _describe(result: InvocationResult) -> str:
    """A short, sanitized description of an invocation result.

    Never includes response text: evidence records what was observed about the
    mechanism, and provider output is not needed for that (§15 defaults to not
    storing raw responses).
    """
    if result.status is InvocationStatus.SUCCESS:
        return (
            f"finish_state={result.finish_state}, "
            f"text_returned={result.text is not None}, "
            f"usage_status={result.usage.usage_status if result.usage else None}"
        )
    if result.blocked is not None:
        return f"blocked by {result.blocked.code}"
    if result.error is not None:
        return f"error class={result.error.error_class} stage={result.error.stage}"
    return f"status={result.status}"


__all__ = [
    "LIVE_MAX_OUTPUT",
    "LIVE_MAX_RETRIES",
    "LIVE_OPT_IN_ENV",
    "LIVE_OPT_IN_VALUE",
    "LIVE_PROVIDER_ALLOWLIST",
    "LIVE_TEXT_PROMPT",
    "LIVE_TIMEOUT_MS",
    "LIVE_TOOL_SCHEMA",
    "PROBE_CATALOG",
    "CapabilityObservation",
    "LiveBlockCode",
    "LiveGate",
    "LiveProbeRecord",
    "LiveRunStatus",
    "LiveVerificationRecord",
    "LiveVerifier",
    "ProbeDefinition",
    "ProbeOutcome",
    "candidate_status",
    "endpoint_host",
    "EXPERIMENT_ID_RE",
    "REDACTED_MODEL_REF",
    "is_valid_experiment_id",
    "new_run_id",
    "safe_caller_text",
    "safe_model_ref_input",
    "split_model_ref",
    "evaluate_preconditions",
]
