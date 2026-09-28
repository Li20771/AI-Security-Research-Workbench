"""Shared adapter for the `openai_compatible_chat` protocol family.

Both in-scope providers declare this family, so both use this adapter. They
keep separate provider profiles, because a shared protocol is not a shared
profile: endpoints, credentials, availability, and compatibility gaps all
differ, and metrics must attribute a request to a real provider (D-2).

URL composition is `base_url` + `path_template`, exactly. `/v1` is never
inserted and no shared prefix is assumed -- `deepseek` declares a base URL
without a version segment and `mimo` declares one with `/v1`, which is
precisely why the composition rule is strict (§5.2, D-4).
"""

from __future__ import annotations

import re
from typing import Any, ClassVar, Mapping

from providers.errors import ErrorClass, ErrorStage, ProviderError
from providers.profile import ModelRef, ProviderProfile
from providers.protocol.base import (
    FinishState,
    ProtocolAdapter,
    ProviderResponse,
    TransportFailureKind,
    TransportRequest,
    TransportResult,
)
from providers.redaction import redact

#: Statuses with an unambiguous meaning in this protocol family.
_STATUS_RULES: Mapping[int, ErrorClass] = {
    401: ErrorClass.AUTHENTICATION,
    403: ErrorClass.AUTHENTICATION,
    402: ErrorClass.QUOTA_EXHAUSTED,
    404: ErrorClass.INVALID_REQUEST,  # unknown model, or wrong path
    408: ErrorClass.TIMEOUT,
    409: ErrorClass.INVALID_REQUEST,
    413: ErrorClass.CONTEXT_OVERFLOW,  # payload too large
    422: ErrorClass.INVALID_REQUEST,
    429: ErrorClass.RATE_LIMIT,
}

#: Message signals that refine an otherwise-ambiguous status. Ordered: the
#: first match wins. Applied only to the statuses listed per rule, because
#: guessing from prose is less reliable than from a status code.
_MESSAGE_RULES: tuple[tuple[re.Pattern[str], frozenset[int], ErrorClass], ...] = (
    (
        re.compile(
            r"(?i)context\s+(length|window|limit)|maximum\s+context"
            r"|too\s+many\s+tokens|token[s]?\s+(limit|exceed)"
            r"|reduce\s+the\s+length|prompt\s+is\s+too\s+long"
        ),
        frozenset({400, 413}),
        ErrorClass.CONTEXT_OVERFLOW,
    ),
    (
        re.compile(
            r"(?i)content\s+(policy|filter)|moderation|flagged"
            r"|safety\s+system|responsible\s+ai"
        ),
        frozenset({400}),
        ErrorClass.CONTENT_FILTER,
    ),
)

#: Errors this adapter may receive from a transport. Anything else is a
#: programming error in the transport implementation.
_TRANSPORT_CLASSES: Mapping[TransportFailureKind, tuple[ErrorClass, ErrorStage]] = {
    TransportFailureKind.TIMEOUT: (ErrorClass.TIMEOUT, ErrorStage.RECEIVE),
    TransportFailureKind.TRANSPORT: (ErrorClass.TRANSPORT, ErrorStage.CONNECT),
    TransportFailureKind.CANCELLED: (ErrorClass.CANCELLED, ErrorStage.RECEIVE),
}


class OpenAICompatibleChatAdapter(ProtocolAdapter):
    """Adapter for OpenAI-compatible chat completions."""

    family: ClassVar[str] = "openai_compatible_chat"

    def effective_url(self, profile: ProviderProfile) -> str:
        return profile.endpoint.effective_url

    def build_request(
        self,
        profile: ProviderProfile,
        model_ref: ModelRef,
        *,
        credential: str,
        body: str,
        method: str = "POST",
    ) -> TransportRequest:
        """Compose the outbound request.

        The credential is placed only in the `Authorization` header. The
        returned request never renders it: `TransportRequest.__repr__` and
        `redacted_headers()` mask sensitive header values.
        """
        transport = profile.transport
        return TransportRequest(
            method=method,
            url=self.effective_url(profile),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {credential}",
            },
            body=body,
            timeout_connect_ms=transport.timeout_connect_ms,
            timeout_total_ms=transport.timeout_total_ms,
            verify_tls=transport.verify_tls,
        )

    def classify_http_status(
        self, http_status: int | None, *, message: str | None = None
    ) -> ProviderError:
        """Map an HTTP status to a typed error (contract §5.10).

        `RATE_LIMIT` and `QUOTA_EXHAUSTED` stay distinct: one is transient and
        retryable, the other is terminal and needs a human. `PROTOCOL` and
        `INVALID_REQUEST` stay distinct: one means the provider broke our
        contract, the other means we broke theirs.
        """
        sanitized = redact(message)

        if http_status is None:
            return ProviderError(
                error_class=ErrorClass.UNKNOWN,
                stage=ErrorStage.RECEIVE,
                provider_message_sanitized=sanitized,
            )

        for pattern, statuses, error_class in _MESSAGE_RULES:
            if http_status in statuses and sanitized and pattern.search(sanitized):
                return ProviderError(
                    error_class=error_class,
                    stage=ErrorStage.RECEIVE,
                    provider_message_sanitized=sanitized,
                    http_status=http_status,
                )

        if http_status in _STATUS_RULES:
            return ProviderError(
                error_class=_STATUS_RULES[http_status],
                stage=ErrorStage.RECEIVE,
                provider_message_sanitized=sanitized,
                http_status=http_status,
            )

        if http_status == 400:
            return ProviderError(
                error_class=ErrorClass.INVALID_REQUEST,
                stage=ErrorStage.RECEIVE,
                provider_message_sanitized=sanitized,
                http_status=http_status,
            )

        if 500 <= http_status < 600:
            return ProviderError(
                error_class=ErrorClass.SERVER,
                stage=ErrorStage.RECEIVE,
                provider_message_sanitized=sanitized,
                http_status=http_status,
            )

        return ProviderError(
            error_class=ErrorClass.UNKNOWN,
            stage=ErrorStage.RECEIVE,
            provider_message_sanitized=sanitized,
            http_status=http_status,
        )

    def classify_transport_failure(self, result: TransportResult) -> ProviderError:
        if result.failure is None:
            raise ValueError("classify_transport_failure called on a non-failure result")

        try:
            error_class, default_stage = _TRANSPORT_CLASSES[result.failure]
        except KeyError:  # pragma: no cover - defensive
            error_class, default_stage = ErrorClass.UNKNOWN, ErrorStage.RECEIVE

        return ProviderError(
            error_class=error_class,
            stage=result.stage or default_stage,
            provider_message_sanitized=redact(result.message),
        )

    def parse_response(
        self, profile: ProviderProfile, model_ref: ModelRef, payload: Any
    ) -> ProviderResponse:
        """Validate payload shape and build the envelope.

        **AI-02-B1 validates shape only.** Mapping `choices[0].message.content`
        into `text`, tool calls into `tool_calls`, usage into the typed usage
        shape, and `finish_reason` into `finish_state` is AI-02-B3's normalized
        invocation, with the usage zero-vs-unknown rule owned by AI-02-B4.

        Shape is still validated here, because a non-object payload is a
        provider breaking the declared protocol and must be classified as
        `PROTOCOL` rather than accepted as content.
        """
        if not isinstance(payload, Mapping):
            raise ProviderError(
                error_class=ErrorClass.PROTOCOL,
                stage=ErrorStage.PARSE,
                provider_message_sanitized=(
                    f"expected a JSON object, got {type(payload).__name__}"
                ),
            )

        return ProviderResponse(
            provider_id=profile.provider_id,
            model_id=model_ref.model_id,
            finish_state=FinishState.UNKNOWN,
            error=None,
        )


__all__ = ["OpenAICompatibleChatAdapter"]
