"""Normalized invocation.

Implements AI-02 contract §7 (invocation contract), §5.8 (normalized response),
§5.9 (transport error reporting), §6.7 (capability gating) and §8 (truth model).

The boundary this module exists to create:

    caller
      |
      v
    InvocationRequest          provider-neutral
      |
      v
    model resolution  ->  capability gate  ->  credential resolution
      |
      v
    ProtocolAdapter            provider-specific, and only here
      |
      v
    Transport                  an interface; the tests supply a fake
      |
      v
    InvocationResult           provider-neutral

A caller never sees a provider's JSON shape, and never learns which provider
answered by inspecting a payload: attribution is carried explicitly.

Two rules are load-bearing:

**A capability that is not `VERIFIED` blocks the call before any provider
activity.** `UNKNOWN`, `NOT_VERIFIED`, `DECLARED` and `UNAVAILABLE` all refuse.
A `stream: true` request is refused rather than silently downgraded to
`false`, because a silent downgrade hides a broken capability.

**`status` is the only success signal.** A non-empty `text` on an `ERROR` or
`BLOCKED` result is partial output, not a success.

No retry, no fallback, no model selection. `attempts` is 1 because one call is
made; AI-02 implements no retry loop (§5.11, D-12).
"""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping, Sequence

from providers.credential import (
    CredentialConfigError,
    CredentialError,
    CredentialRef,
    resolve,
)
from providers.errors import ErrorClass, ErrorStage, ProviderError
from providers.model_profile import (
    CapabilityName,
    CapabilityStatus,
    ModelProfile,
    StructuredOutputMode,
)
from providers.model_registry import load_all_model_profiles
from providers.profile import ModelRef, ProfileError, ProviderProfile
from providers.protocol import (
    FinishState,
    ProtocolAdapter,
    ProviderCall,
    ProviderResponse,
    StructuredOutputSpec,
    Transport,
    adapter_for,
)
from providers.registry import load_all_providers
from providers.transport import TransportSettings

#: Capabilities that gate a request, and what triggers each gate (§7.1).
#: `structured_output` with mode `none` requests nothing, so it does not gate.
GATED_CAPABILITIES: tuple[CapabilityName, ...] = (
    CapabilityName.TOOL_CALLING,
    CapabilityName.STRUCTURED_OUTPUT,
    CapabilityName.STREAMING,
)


class InvocationError(ValueError):
    """The invocation request is malformed. A caller defect, not a status."""


class MessageRole(StrEnum):
    """Roles a normalized message may carry (§7.1)."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class InvocationStatus(StrEnum):
    """The only success signal (§7.2).

    `BLOCKED` means the call was refused before reaching a provider.
    `ERROR` means it was attempted and failed, or the provider refused.
    """

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"


class BlockCode(StrEnum):
    """Why a call was refused before any provider activity.

    An **invocation-layer** vocabulary, deliberately not part of the provider
    error taxonomy (§5.10). A capability gate refusal is not a provider
    failure: no provider was contacted, and nothing was sent. Folding it into
    the provider taxonomy would blur a pre-flight policy decision with
    something a provider did -- and would collide with the frozen rule that
    those classes describe provider-layer outcomes.

    So `error` stays empty for these refusals and `blocked` carries the
    complete, typed reason.
    """

    CAPABILITY_NOT_VERIFIED = "CAPABILITY_NOT_VERIFIED"
    UNKNOWN_PROVIDER = "UNKNOWN_PROVIDER"
    UNKNOWN_MODEL = "UNKNOWN_MODEL"
    #: The credential *reference* is malformed or is a literal value. A
    #: configuration defect (§5.3, §10.3), so it has no taxonomy class either.
    CREDENTIAL_CONFIG_DEFECT = "CREDENTIAL_CONFIG_DEFECT"


class UsageStatus(StrEnum):
    """Whether token counts were measured (§9.2).

    `ESTIMATED` is reserved for AI-02-B4 and is never produced here.
    """

    REPORTED = "REPORTED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


def new_request_id() -> str:
    """Generate a correlation id (§7.1).

    The contract writes `wb-<ulid>`. A UUID4 hex is used instead: it is a valid
    correlation id produced by the standard library, and introducing a ULID
    dependency for a formatting detail would be a poor trade.
    """
    return f"wb-{uuid.uuid4().hex}"


def _require_positive_ms(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvocationError(f"{name} must be a number of milliseconds")
    if not math.isfinite(value):
        raise InvocationError(f"{name} must be finite; there is no unbounded call")
    if value <= 0:
        raise InvocationError(
            f"{name} must be > 0; got {value}. A non-positive timeout is not "
            "an unbounded timeout"
        )
    return int(value)


def effective_transport_settings(
    request_timeout_ms: int, settings: TransportSettings
) -> TransportSettings:
    """Compose the invocation deadline with the runtime safety ceiling (§5.11).

    `InvocationRequest.timeout_ms` is an invocation-level deadline; runtime
    config is the operator's ceiling. The effective deadline is the stricter
    of the two, so a request can **tighten** a budget but never widen one --
    a caller cannot raise the configured limit by asking for a longer call.

    This returns a `TransportSettings`, which is the only deadline shape the
    transport accepts. There is no second timeout subsystem: the request
    deadline is folded into the one that already exists rather than tracked
    alongside it.
    """
    total_ms = min(request_timeout_ms, settings.timeout_total_ms)
    # Capped by the total so the two stay coherent: a connect deadline longer
    # than the whole call would never be reachable.
    connect_ms = min(settings.timeout_connect_ms, total_ms)
    return TransportSettings(
        timeout_connect_ms=connect_ms,
        timeout_total_ms=total_ms,
        max_retries=settings.max_retries,
        verify_tls=settings.verify_tls,
    )


@dataclass(frozen=True, slots=True)
class Message:
    """One normalized message (§7.1)."""

    role: MessageRole
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, MessageRole):
            raise InvocationError(
                f"role must be one of {[r.value for r in MessageRole]}; "
                f"got {self.role!r}"
            )
        if not isinstance(self.content, str):
            raise InvocationError(
                f"content must be a string, got {type(self.content).__name__}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"role": str(self.role), "content": self.content}


@dataclass(frozen=True, slots=True)
class StructuredOutputRequest:
    """A structured-output request (§7.1, §6.7).

    `json_schema` requires a schema. `json_object` guarantees JSON but **not**
    schema conformance, so the two are never interchangeable.
    """

    mode: StructuredOutputMode
    schema: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, StructuredOutputMode):
            raise InvocationError(
                f"mode must be one of {[m.value for m in StructuredOutputMode]}"
            )
        if self.mode is StructuredOutputMode.JSON_SCHEMA and self.schema is None:
            raise InvocationError("mode json_schema requires a schema")
        if self.mode is StructuredOutputMode.NONE and self.schema is not None:
            raise InvocationError("mode none must not carry a schema")

    @property
    def requires_capability(self) -> bool:
        """True when this request asks the provider to enforce structure."""
        return self.mode is not StructuredOutputMode.NONE

    def to_spec(self) -> StructuredOutputSpec | None:
        if not self.requires_capability:
            return None
        return StructuredOutputSpec(mode=str(self.mode), schema=self.schema)


@dataclass(frozen=True, slots=True)
class GenerationParameters:
    """Optional sampling parameters (§7.1).

    Absent values are `None` and are omitted from the outbound body, so a
    provider default applies rather than an explicit empty value.
    """

    temperature: float | None = None
    max_output: int | None = None
    stop: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.temperature is not None:
            if isinstance(self.temperature, bool) or not isinstance(
                self.temperature, (int, float)
            ):
                raise InvocationError("temperature must be a number")
            if not math.isfinite(self.temperature) or self.temperature < 0:
                raise InvocationError(
                    f"temperature must be finite and >= 0; got {self.temperature}"
                )
        if self.max_output is not None:
            if isinstance(self.max_output, bool) or not isinstance(self.max_output, int):
                raise InvocationError("max_output must be an integer")
            if self.max_output <= 0:
                raise InvocationError(
                    f"max_output must be > 0; got {self.max_output}"
                )
        if not isinstance(self.stop, tuple) or any(
            not isinstance(item, str) for item in self.stop
        ):
            raise InvocationError("stop must be a tuple of strings")


@dataclass(frozen=True, slots=True)
class RequestMetadata:
    """Workbench attribution metadata (§7.4).

    Recorded, never acted on. No field here may drive model selection, and none
    is sent to a provider: this is Workbench bookkeeping, not prompt content.
    It never carries secrets or prompt bodies.
    """

    experiment_id: str | None = None
    task_id: str | None = None
    task_class: str | None = None
    agent: str | None = None
    purpose: str | None = None

    def __post_init__(self) -> None:
        for name in ("experiment_id", "task_id", "task_class", "agent", "purpose"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise InvocationError(f"metadata.{name} must be a string or null")

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "task_id": self.task_id,
            "task_class": self.task_class,
            "agent": self.agent,
            "purpose": self.purpose,
        }


@dataclass(frozen=True, slots=True)
class InvocationRequest:
    """A provider-neutral call request (§7.1).

    Contains no credential, no endpoint, and no transport setting. The
    credential is resolved from the provider profile's *reference* at send
    time, and transport settings come from runtime config (§5.11) -- so a
    request object can be logged, stored, or passed around without carrying
    either.
    """

    model_ref: str
    messages: tuple[Message, ...]
    timeout_ms: int
    request_id: str = field(default_factory=new_request_id)
    tools: tuple[Mapping[str, Any], ...] = ()
    structured_output: StructuredOutputRequest | None = None
    generation: GenerationParameters = field(default_factory=GenerationParameters)
    stream: bool = False
    metadata: RequestMetadata = field(default_factory=RequestMetadata)

    def __post_init__(self) -> None:
        # A bare model id is rejected: it loses provider attribution (§7.1).
        ModelRef.parse(self.model_ref)
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise InvocationError("request_id must be a non-empty string")
        if not isinstance(self.messages, tuple) or not self.messages:
            raise InvocationError("messages must be a non-empty tuple of Message")
        for message in self.messages:
            if not isinstance(message, Message):
                raise InvocationError(
                    f"messages entries must be Message, got {type(message).__name__}"
                )
        if not isinstance(self.stream, bool):
            raise InvocationError(
                f"stream must be a bool; got {type(self.stream).__name__}"
            )
        if not isinstance(self.tools, tuple) or any(
            not isinstance(tool, Mapping) for tool in self.tools
        ):
            raise InvocationError("tools must be a tuple of mappings")
        # There is no unbounded call (§7.1). This is the request deadline;
        # the transport deadline is derived from runtime config.
        object.__setattr__(
            self, "timeout_ms", _require_positive_ms(self.timeout_ms, "timeout_ms")
        )

    @property
    def parsed_model_ref(self) -> ModelRef:
        return ModelRef.parse(self.model_ref)

    def to_dict(self) -> dict[str, Any]:
        """Serialize. Never contains a credential, because none is held."""
        return {
            "request_id": self.request_id,
            "model_ref": self.model_ref,
            "messages": [message.to_dict() for message in self.messages],
            "tools": [dict(tool) for tool in self.tools],
            "structured_output": (
                {
                    "mode": str(self.structured_output.mode),
                    # `is not None`, never truthiness: an empty schema `{}` is a
                    # valid schema and must round-trip as `{}`, not collapse to
                    # null and silently become "no schema supplied".
                    "schema": (
                        dict(self.structured_output.schema)
                        if self.structured_output.schema is not None
                        else None
                    ),
                }
                if self.structured_output is not None
                else None
            ),
            "generation": {
                "temperature": self.generation.temperature,
                "max_output": self.generation.max_output,
                "stop": list(self.generation.stop),
            },
            "stream": self.stream,
            "timeout_ms": self.timeout_ms,
            "metadata": self.metadata.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class Usage:
    """Normalized token counts (§9.2).

    An unreported count is `None`, never `0`. `usage_status: UNKNOWN` records
    that nothing was measured, so a consumer cannot mistake absence for a
    measurement of zero.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    usage_status: UsageStatus = UsageStatus.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "usage_status": str(self.usage_status),
        }


@dataclass(frozen=True, slots=True)
class Latency:
    """Observed call latency. Unmeasured values are `None` (§7.2)."""

    total_ms: int | None = None
    ttfb_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"total_ms": self.total_ms, "ttfb_ms": self.ttfb_ms}


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A normalized tool call (§11).

    Provider-independent: the provider's `function` wrapper is gone, and a
    caller never needs to know which provider produced it.

    `arguments` remains the raw JSON string the provider sent. Parsing it here
    would assert a well-formedness the provider never confirmed.
    """

    name: str
    arguments: str | None = None
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass(frozen=True, slots=True)
class BlockReason:
    """A typed pre-flight refusal (§6 of the AI-02-B3 task).

    Carries the required capability and the status actually recorded, so a
    caller can act on the refusal without parsing prose.
    """

    code: BlockCode
    detail: str
    required_capability: CapabilityName | None = None
    actual_status: CapabilityStatus | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": str(self.code),
            "detail": self.detail,
            "required_capability": (
                str(self.required_capability) if self.required_capability else None
            ),
            "actual_status": str(self.actual_status) if self.actual_status else None,
        }


@dataclass(frozen=True, slots=True)
class InvocationResult:
    """A provider-neutral call result (§7.2).

    `status` is the only success signal. `provider_id`, `model_id` and
    `model_ref` are always recorded, so a result is attributable without
    consulting any registry.

    `error` carries the §5.9 shape when a provider-layer failure occurred, or
    when a credential precondition was refused (both have real taxonomy
    classes). `blocked` carries an invocation-layer refusal, which has no
    provider taxonomy class by design -- see `BlockCode`.
    """

    request_id: str
    provider_id: str
    model_id: str
    model_ref: str
    status: InvocationStatus
    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    structured_output: Mapping[str, Any] | None = None
    reasoning: str | None = None
    #: Present on `SUCCESS`, where counts may be `None` with
    #: `usage_status: UNKNOWN`. `None` on `ERROR`/`BLOCKED`, where no
    #: measurement was taken.
    usage: Usage | None = None
    #: Why generation stopped. `ERROR` means the *provider* signalled failure
    #: (§7.3); a pre-flight refusal reached no provider and therefore has no
    #: finish reason, so it is `UNKNOWN`. `CONTENT_FILTER` is the provider
    #: stopping on policy grounds, which is an error rather than a success.
    finish_state: FinishState = FinishState.UNKNOWN
    latency: Latency = field(default_factory=Latency)
    error: ProviderError | None = None
    attempts: int = 1
    raw_response_ref: str | None = None
    blocked: BlockReason | None = None

    @property
    def ok(self) -> bool:
        """True only for `SUCCESS`. Nothing else is a success (§14)."""
        return self.status is InvocationStatus.SUCCESS

    @property
    def is_truncated(self) -> bool:
        """True when the answer is incomplete and must not be used as final."""
        return self.finish_state is FinishState.LENGTH

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "model_ref": self.model_ref,
            "status": str(self.status),
            "text": self.text,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "structured_output": (
                dict(self.structured_output) if self.structured_output else None
            ),
            "reasoning": self.reasoning,
            "usage": self.usage.to_dict() if self.usage else None,
            "finish_state": str(self.finish_state),
            "latency": self.latency.to_dict(),
            "error": self.error.to_dict() if self.error else None,
            "attempts": self.attempts,
            "raw_response_ref": self.raw_response_ref,
            "blocked": self.blocked.to_dict() if self.blocked else None,
        }


@dataclass(frozen=True, slots=True)
class InvocationContext:
    """Everything an invocation needs that is not the request itself."""

    providers: Mapping[str, ProviderProfile]
    models: Mapping[str, ModelProfile]
    transport: Transport
    transport_settings_for: Callable[[str], TransportSettings]
    environ: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class ProbeAuthorisation:
    """Authorises exercising one unverified capability, for observation only.

    Contract §7.1 refuses a request needing an unverified capability "rather
    than attempted optimistically. `status: NOT_VERIFIED` does not authorise a
    live attempt **outside AI-02-B6**." This is that carve-out, and it is
    deliberately narrow:

    - one capability, named explicitly
    - one model, named explicitly -- it does not travel to another model
    - it grants nothing. A probe can produce evidence; it cannot change a
      profile, and nothing consumes this to widen a gate later.

    The alternative was worse: a live probe that cannot exercise the
    capability it is meant to observe verifies nothing, and weakening the gate
    for everyone would defeat its purpose.
    """

    capability: CapabilityName
    model_ref: str
    authorised_by: str

    def covers(self, capability: CapabilityName, model_ref: str) -> bool:
        return self.capability is capability and self.model_ref == model_ref


def _check_capabilities(
    request: InvocationRequest,
    model: ModelProfile,
    authorisation: ProbeAuthorisation | None = None,
) -> BlockReason | None:
    """Refuse a request whose capability requirement is not VERIFIED (§6.7).

    Runs before any transport activity. Only `VERIFIED` authorises a gated
    call: `DECLARED` is a vendor claim, `NOT_VERIFIED` is an inconclusive
    attempt, `UNAVAILABLE` is a negative observation, and `UNKNOWN` is nobody
    knowing. None of them is evidence that the mechanism works.
    """
    required: list[tuple[CapabilityName, str]] = []

    if request.tools:
        required.append(
            (CapabilityName.TOOL_CALLING, f"request carries {len(request.tools)} tool(s)")
        )

    structured = request.structured_output
    if structured is not None and structured.requires_capability:
        required.append(
            (
                CapabilityName.STRUCTURED_OUTPUT,
                f"request asks for structured_output mode {structured.mode!s}",
            )
        )

    if request.stream:
        required.append((CapabilityName.STREAMING, "request asks for stream=true"))

    for capability, detail in required:
        entry = model.capability(capability)
        if entry.status is CapabilityStatus.VERIFIED:
            continue
        if authorisation is not None and authorisation.covers(
            capability, model.model_ref
        ):
            # AI-02-B6 probe allowance (§7.1). The capability is still not
            # VERIFIED; the call is authorised to observe, not to succeed.
            continue
        if entry.status is not CapabilityStatus.VERIFIED:
            return BlockReason(
                code=BlockCode.CAPABILITY_NOT_VERIFIED,
                detail=(
                    f"{detail}; {capability.value} is {entry.status.value}, and only "
                    "VERIFIED authorises this call"
                ),
                required_capability=capability,
                actual_status=entry.status,
            )

    return None


def _lift_usage(raw: Mapping[str, Any] | None) -> Usage:
    """Lift the adapter's usage mapping into the typed shape (§9.2).

    Always returns an object. A provider that reported nothing yields counts of
    `None` with `usage_status: UNKNOWN`, which is the state §9.2 defines for
    exactly this case. Returning `None` instead would leave a consumer
    distinguishing two kinds of absence, and would make the UNKNOWN status
    unreachable.
    """
    if raw is None:
        return Usage(usage_status=UsageStatus.UNKNOWN)
    try:
        status = UsageStatus(raw.get("usage_status", UsageStatus.UNKNOWN))
    except ValueError:
        status = UsageStatus.UNKNOWN
    return Usage(
        input_tokens=raw.get("input_tokens"),
        output_tokens=raw.get("output_tokens"),
        total_tokens=raw.get("total_tokens"),
        cache_read_tokens=raw.get("cache_read_tokens"),
        cache_write_tokens=raw.get("cache_write_tokens"),
        usage_status=status,
    )


def _lift_tool_calls(raw: Sequence[Mapping[str, Any]]) -> tuple[ToolCall, ...]:
    return tuple(
        ToolCall(
            name=str(call.get("name", "")),
            arguments=call.get("arguments"),
            id=call.get("id"),
        )
        for call in raw
    )


class Invoker:
    """The normalized invocation boundary.

    Resolves a model, gates on capability, resolves the credential, drives the
    protocol adapter, and returns a normalized result.
    """

    def __init__(
        self,
        context: InvocationContext,
        *,
        clock: Callable[[], float] = time.monotonic,
        probe_authorisation: ProbeAuthorisation | None = None,
    ) -> None:
        self._context = context
        self._clock = clock
        #: Set only by AI-02-B6 live verification. Nothing else constructs one.
        self._probe_authorisation = probe_authorisation

    @classmethod
    def from_registry(
        cls,
        *,
        transport: Transport,
        transport_settings_for: Callable[[str], TransportSettings],
        environ: Mapping[str, str] | None = None,
        clock: Callable[[], float] = time.monotonic,
        root: Any = None,
    ) -> "Invoker":
        """Build an invoker from the registered profiles and no runtime config."""
        return cls(
            InvocationContext(
                providers=load_all_providers(root),
                models=load_all_model_profiles(root),
                transport=transport,
                transport_settings_for=transport_settings_for,
                environ=environ,
            ),
            clock=clock,
        )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        """Perform one invocation. Never raises for a provider or policy
        outcome; failures come back as a typed result."""
        parsed = request.parsed_model_ref
        provider = self._context.providers.get(parsed.provider_id)
        if provider is None:
            return self._blocked(
                request,
                BlockCode.UNKNOWN_PROVIDER,
                f"provider {parsed.provider_id!r} is not registered",
            )

        model = self._context.models.get(request.model_ref)
        if model is None:
            return self._blocked(
                request,
                BlockCode.UNKNOWN_MODEL,
                f"model {request.model_ref!r} is not registered",
            )

        # Capability gate: before the credential is touched and before any
        # transport activity, so a refused call cannot reach a provider.
        block = _check_capabilities(request, model, self._probe_authorisation)
        if block is not None:
            return InvocationResult(
                request_id=request.request_id,
                provider_id=provider.provider_id,
                model_id=parsed.model_id,
                model_ref=request.model_ref,
                status=InvocationStatus.BLOCKED,
                finish_state=FinishState.UNKNOWN,
                blocked=block,
            )

        try:
            secret = resolve(
                CredentialRef.parse(provider.credential.ref),
                environ=self._context.environ,
            )
        except CredentialError as exc:
            # A real taxonomy class, and a precondition: nothing was sent.
            return InvocationResult(
                request_id=request.request_id,
                provider_id=provider.provider_id,
                model_id=parsed.model_id,
                model_ref=request.model_ref,
                status=InvocationStatus.BLOCKED,
                finish_state=FinishState.UNKNOWN,
                error=exc.to_provider_error(),
            )
        except CredentialConfigError as exc:
            # A configuration defect, not an error class (§10.3). Fail closed:
            # a malformed reference must never look like a missing credential,
            # because the two have different remedies.
            return InvocationResult(
                request_id=request.request_id,
                provider_id=provider.provider_id,
                model_id=parsed.model_id,
                model_ref=request.model_ref,
                status=InvocationStatus.BLOCKED,
                finish_state=FinishState.UNKNOWN,
                blocked=BlockReason(
                    code=BlockCode.CREDENTIAL_CONFIG_DEFECT,
                    detail=f"credential reference is a configuration defect: {exc}",
                ),
            )

        adapter = adapter_for(provider.protocol.family)
        payload = adapter.build_payload(
            model_id=parsed.model_id,
            messages=[message.to_dict() for message in request.messages],
            tools=request.tools,
            structured_output=(
                request.structured_output.to_spec()
                if request.structured_output
                else None
            ),
            temperature=request.generation.temperature,
            max_output=request.generation.max_output,
            stop=request.generation.stop,
            stream=request.stream,
        )

        transport_request = adapter.build_request(
            provider,
            parsed,
            credential=secret.reveal(),
            body=json.dumps(payload),
            transport_settings=effective_transport_settings(
                request.timeout_ms,
                self._context.transport_settings_for(provider.provider_id),
            ),
        )
        call = ProviderCall(profile=provider, model_ref=parsed, request=transport_request)

        started = self._clock()
        response = adapter.send(call, self._context.transport)
        elapsed_ms = int(round((self._clock() - started) * 1000))

        return self._to_result(request, model, response, elapsed_ms)

    # -- helpers ---------------------------------------------------------

    def _blocked(
        self, request: InvocationRequest, code: BlockCode, detail: str
    ) -> InvocationResult:
        parsed = request.parsed_model_ref
        return InvocationResult(
            request_id=request.request_id,
            provider_id=parsed.provider_id,
            model_id=parsed.model_id,
            model_ref=request.model_ref,
            status=InvocationStatus.BLOCKED,
            finish_state=FinishState.UNKNOWN,
            blocked=BlockReason(code=code, detail=detail),
        )

    def _to_result(
        self,
        request: InvocationRequest,
        model: ModelProfile,
        response: ProviderResponse,
        elapsed_ms: int,
    ) -> InvocationResult:
        latency = Latency(total_ms=elapsed_ms)
        common: dict[str, Any] = {
            "request_id": request.request_id,
            "provider_id": response.provider_id,
            "model_id": response.model_id,
            "model_ref": f"{response.provider_id}/{response.model_id}",
            "finish_state": response.finish_state,
            "latency": latency,
            "attempts": 1,
        }

        if response.error is not None:
            # A provider-layer failure. Even if partial text came back, this is
            # not a success (§7.2, §14).
            return InvocationResult(
                status=InvocationStatus.ERROR,
                text=response.text,
                error=response.error,
                **common,
            )

        if response.finish_state is FinishState.CONTENT_FILTER:
            # The provider refused on policy grounds: a response, but not a
            # successful answer (§7.3).
            return InvocationResult(
                status=InvocationStatus.ERROR,
                error=ProviderError(
                    error_class=ErrorClass.CONTENT_FILTER,
                    stage=ErrorStage.RECEIVE,
                    provider_message_sanitized=(
                        "provider stopped on content policy grounds"
                    ),
                ),
                **common,
            )

        return InvocationResult(
            status=InvocationStatus.SUCCESS,
            text=response.text,
            tool_calls=_lift_tool_calls(response.tool_calls),
            structured_output=response.structured_output,
            reasoning=response.reasoning,
            usage=_lift_usage(response.usage),
            raw_response_ref=response.raw_response_ref,
            **common,
        )


__all__ = [
    "BlockCode",
    "BlockReason",
    "GATED_CAPABILITIES",
    "GenerationParameters",
    "InvocationContext",
    "InvocationError",
    "InvocationRequest",
    "InvocationResult",
    "InvocationStatus",
    "Invoker",
    "Latency",
    "Message",
    "MessageRole",
    "ProbeAuthorisation",
    "RequestMetadata",
    "StructuredOutputRequest",
    "ToolCall",
    "Usage",
    "UsageStatus",
    "new_request_id",
]
