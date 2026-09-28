"""Provider-decoupled protocol adapter interface.

Implements AI-02 contract §5.8 (normalized response) and §5.9 (transport error
reporting). Together with a provider profile, an adapter produces the
normalized provider boundary:

    Provider profile + shared protocol adapter -> normalized provider boundary

Callers depend on this module's types, never on a provider's HTTP JSON shape.
DeepSeek and MiMo share one adapter (same protocol family) but keep separate
profiles, so attribution survives (D-2).

**No concrete network transport ships in AI-02-B1.** `Transport` is an
interface; the only implementation exercised anywhere is a fake transport in
the test suite. Nothing in this package can open a provider connection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar, Mapping

from providers.errors import ErrorClass, ErrorStage, ProviderError
from providers.profile import ModelRef, ProviderProfile
from providers.redaction import REDACTED, redact

#: Header names whose values are credentials. Never rendered.
SENSITIVE_HEADERS: frozenset[str] = frozenset({"authorization", "x-api-key", "api-key"})


class FinishState(StrEnum):
    """Why generation stopped (contract §7.3, carried on the §5.8 envelope).

    `LENGTH` is a truncation warning, not a success. `UNKNOWN` must never be
    treated as `STOP`.
    """

    STOP = "STOP"
    LENGTH = "LENGTH"
    TOOL_CALLS = "TOOL_CALLS"
    CONTENT_FILTER = "CONTENT_FILTER"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class TransportFailureKind(StrEnum):
    """Transport-level failures, before any provider semantics apply."""

    TIMEOUT = "TIMEOUT"
    TRANSPORT = "TRANSPORT"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class TransportRequest:
    """A fully-composed outbound request.

    `headers` may contain a credential. `__repr__` and `redacted_headers()`
    are safe to log; `headers` is not.
    """

    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: str | None = None
    timeout_connect_ms: int = 0
    timeout_total_ms: int = 0
    verify_tls: bool = True

    def redacted_headers(self) -> dict[str, str]:
        """Header names with credential values removed. Safe to log or store."""
        return {
            name: (REDACTED if name.lower() in SENSITIVE_HEADERS else value)
            for name, value in self.headers.items()
        }

    def __repr__(self) -> str:
        return (
            f"TransportRequest(method={self.method!r}, url={self.url!r}, "
            f"headers={self.redacted_headers()!r}, "
            f"body={'<redacted>' if self.body else None}, "
            f"timeout_connect_ms={self.timeout_connect_ms}, "
            f"timeout_total_ms={self.timeout_total_ms}, "
            f"verify_tls={self.verify_tls})"
        )


@dataclass(frozen=True, slots=True)
class TransportResult:
    """What a transport returns: an HTTP response, or a transport failure."""

    http_status: int | None = None
    payload: Any = None
    failure: TransportFailureKind | None = None
    stage: ErrorStage | None = None
    message: str | None = None

    @property
    def is_failure(self) -> bool:
        return self.failure is not None

    @property
    def is_http_success(self) -> bool:
        return (
            self.failure is None
            and self.http_status is not None
            and 200 <= self.http_status < 300
        )

    @classmethod
    def success(cls, http_status: int, payload: Any) -> "TransportResult":
        return cls(http_status=http_status, payload=payload)

    @classmethod
    def failed(
        cls,
        failure: TransportFailureKind,
        stage: ErrorStage,
        message: str | None = None,
    ) -> "TransportResult":
        return cls(failure=failure, stage=stage, message=redact(message))


class Transport(ABC):
    """Transport interface.

    Implementations perform I/O. AI-02-B1 ships none: implementing a real HTTP
    transport is deferred, because the phase forbids live provider calls. The
    test suite supplies a fake.
    """

    @abstractmethod
    def send(self, request: TransportRequest) -> TransportResult:
        """Perform one request. Must not raise; failures are returned."""


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Normalized provider envelope (contract §5.8).

    Identical across providers: a caller never sees a provider-specific
    payload. Absent fields are `None` or empty, never fabricated zeros --
    absence is not a measurement.

    AI-02-B1 constructs this envelope on the failure paths and validates shape
    on the success path. Populating the content fields (`text`, `tool_calls`,
    `structured_output`, `usage`) is AI-02-B3's normalized invocation, and the
    typed `usage` shape with its zero-vs-unknown rule is AI-02-B4's.
    """

    provider_id: str
    model_id: str
    text: str | None = None
    tool_calls: tuple[Mapping[str, Any], ...] = ()
    structured_output: Mapping[str, Any] | None = None
    reasoning: str | None = None
    usage: Mapping[str, Any] | None = None
    finish_state: FinishState = FinishState.UNKNOWN
    provider_request_id: str | None = None
    raw_response_ref: str | None = None
    error: ProviderError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "text": self.text,
            "tool_calls": [dict(call) for call in self.tool_calls],
            "structured_output": (
                dict(self.structured_output) if self.structured_output else None
            ),
            "reasoning": self.reasoning,
            "usage": dict(self.usage) if self.usage else None,
            "finish_state": str(self.finish_state),
            "provider_request_id": self.provider_request_id,
            "raw_response_ref": self.raw_response_ref,
            "error": self.error.to_dict() if self.error else None,
        }


@dataclass(frozen=True, slots=True)
class ProviderCall:
    """One provider call: profile + model reference + composed request."""

    profile: ProviderProfile
    model_ref: ModelRef
    request: TransportRequest


class ProtocolAdapter(ABC):
    """Interface covering request, response, error, and transport.

    Subclasses implement provider-family behaviour. They never expose a
    provider's raw payload shape to callers.
    """

    #: Wire protocol family this adapter serves (contract §5.4).
    family: ClassVar[str] = ""

    @abstractmethod
    def effective_url(self, profile: ProviderProfile) -> str:
        """Compose the request URL from the profile's endpoint declaration."""

    @abstractmethod
    def build_request(
        self,
        profile: ProviderProfile,
        model_ref: ModelRef,
        *,
        credential: str,
        body: str,
        method: str = "POST",
    ) -> TransportRequest:
        """Compose a transport request.

        `credential` is the revealed secret. Implementations must place it only
        in a request header and must never log, store, or return it.

        Request *body* construction from an invocation belongs to AI-02-B3;
        B1 accepts an already-serialized body.
        """

    @abstractmethod
    def classify_http_status(
        self, http_status: int | None, *, message: str | None = None
    ) -> ProviderError:
        """Map an HTTP status to a typed error (contract §5.10)."""

    @abstractmethod
    def classify_transport_failure(self, result: TransportResult) -> ProviderError:
        """Map a transport failure to a typed error."""

    @abstractmethod
    def parse_response(
        self, profile: ProviderProfile, model_ref: ModelRef, payload: Any
    ) -> ProviderResponse:
        """Turn a successful provider payload into the normalized envelope."""

    #: Provider error text is diagnostic, not payload. Cap what is retained.
    MAX_ERROR_MESSAGE_CHARS: ClassVar[int] = 2000

    def extract_error_message(self, payload: Any) -> str | None:
        """Best-effort extraction of a provider's error text from an error body.

        Providers report the reason in the response body, not in a
        transport-level message field, so `provider_message_sanitized` and the
        taxonomy's message refinement have nothing to read without this.

        Returns a redacted, length-capped string, or `None`. The default
        handles the shared OpenAI-compatible error shapes; a provider with its
        own shape overrides this.
        """
        message: str | None = None

        if isinstance(payload, Mapping):
            error = payload.get("error")
            if isinstance(error, Mapping):
                candidate = error.get("message")
                message = candidate if isinstance(candidate, str) else None
            elif isinstance(error, str):
                message = error
            if message is None:
                for key in ("message", "detail", "msg"):
                    candidate = payload.get(key)
                    if isinstance(candidate, str):
                        message = candidate
                        break
        elif isinstance(payload, str):
            message = payload

        if message is None:
            return None

        sanitized = redact(message)
        if sanitized is None:  # pragma: no cover - redact preserves str input
            return None
        return sanitized[: self.MAX_ERROR_MESSAGE_CHARS]

    def send(
        self,
        call: ProviderCall,
        transport: Transport,
    ) -> ProviderResponse:
        """Drive one call and return a normalized envelope.

        Every failure produces a typed error on the envelope rather than a
        raised exception, so a caller cannot silently treat a failure as
        content (contract §5.9).
        """
        result = transport.send(call.request)

        if result.is_failure:
            return self._error_response(
                call, self.classify_transport_failure(result)
            )

        if not result.is_http_success:
            message = result.message or self.extract_error_message(result.payload)
            return self._error_response(
                call, self.classify_http_status(result.http_status, message=message)
            )

        try:
            return self.parse_response(call.profile, call.model_ref, result.payload)
        except ProviderError as exc:
            return self._error_response(call, exc)

    def _error_response(
        self, call: ProviderCall, error: ProviderError
    ) -> ProviderResponse:
        return ProviderResponse(
            provider_id=call.profile.provider_id,
            model_id=call.model_ref.model_id,
            finish_state=FinishState.ERROR,
            error=error,
        )


__all__ = [
    "FinishState",
    "ProtocolAdapter",
    "ProviderCall",
    "ProviderResponse",
    "SENSITIVE_HEADERS",
    "Transport",
    "TransportFailureKind",
    "TransportRequest",
    "TransportResult",
]
