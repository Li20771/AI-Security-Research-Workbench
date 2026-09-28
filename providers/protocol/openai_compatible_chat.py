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
    StructuredOutputSpec,
    TransportFailureKind,
    TransportRequest,
    TransportResult,
)
from providers.redaction import redact
from providers.transport import TransportSettings

#: Finish reasons this family defines, mapped to the frozen states (§7.3).
#:
#: Anything else -- including an absent reason and the legacy `function_call`
#: value -- maps to UNKNOWN. Guessing an unmapped reason into STOP would make a
#: truncated or unexpected stop look like a natural finish.
_FINISH_REASONS: Mapping[str, FinishState] = {
    "stop": FinishState.STOP,
    "length": FinishState.LENGTH,
    "tool_calls": FinishState.TOOL_CALLS,
    "content_filter": FinishState.CONTENT_FILTER,
}

#: Reasoning content field for this family. One field, deliberately: the
#: OpenAI-compatible convention for exposing reasoning separately. Adding more
#: names without evidence of what a provider actually returns would be
#: guessing (§10).
_REASONING_FIELD = "reasoning_content"


def _finish_state(raw: Any) -> FinishState:
    if not isinstance(raw, str):
        return FinishState.UNKNOWN
    return _FINISH_REASONS.get(raw, FinishState.UNKNOWN)


def _normalize_reasoning(message: Mapping[str, Any]) -> str | None:
    """Reasoning stays separate from text (§5.8, §6.7).

    The model's thinking and its answer have different evidentiary weight, so
    they are never concatenated.
    """
    value = message.get(_REASONING_FIELD)
    return value if isinstance(value, str) else None


def _normalize_tool_calls(raw: Any) -> tuple[Mapping[str, Any], ...]:
    """Flatten provider tool calls into a provider-independent shape (§11).

    The provider nests the callable under `function`; callers should not have
    to know that. The normalized entry is `{id, name, arguments}`.

    `arguments` is kept as the raw JSON string the provider sent. Parsing it
    here would invent a success the provider never confirmed -- a malformed
    argument string would become a silently different object.

    A malformed entry raises `PROTOCOL` rather than being dropped: discarding a
    tool call would lose the model's actual intent while still reporting
    success.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ProviderError(
            error_class=ErrorClass.PROTOCOL,
            stage=ErrorStage.PARSE,
            provider_message_sanitized=(
                f"tool_calls must be a list, got {type(raw).__name__}"
            ),
        )

    normalized: list[Mapping[str, Any]] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, Mapping):
            raise ProviderError(
                error_class=ErrorClass.PROTOCOL,
                stage=ErrorStage.PARSE,
                provider_message_sanitized=(
                    f"tool_calls[{index}] must be an object, got "
                    f"{type(entry).__name__}"
                ),
            )
        function = entry.get("function")
        if not isinstance(function, Mapping):
            raise ProviderError(
                error_class=ErrorClass.PROTOCOL,
                stage=ErrorStage.PARSE,
                provider_message_sanitized=(
                    f"tool_calls[{index}].function must be an object"
                ),
            )
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise ProviderError(
                error_class=ErrorClass.PROTOCOL,
                stage=ErrorStage.PARSE,
                provider_message_sanitized=(
                    f"tool_calls[{index}].function.name must be a non-empty string"
                ),
            )
        call_id = entry.get("id")
        arguments = function.get("arguments")
        normalized.append(
            {
                "id": call_id if isinstance(call_id, str) else None,
                "name": name,
                "arguments": arguments if isinstance(arguments, str) else None,
            }
        )

    return tuple(normalized)


def _normalize_usage(raw: Any) -> Mapping[str, Any] | None:
    """Map provider token counts into the normalized usage shape (§9.2).

    A count the provider did not report is `None`, never `0`. Zero is a
    measurement; absence is not, and reporting an unmeasured count as zero
    under-reports every downstream total.

    Cache-token extraction is provider-specific and belongs to AI-02-B4, so the
    cache fields are `None` here rather than guessed from a field name this
    protocol family does not fix.
    """
    if not isinstance(raw, Mapping):
        return None

    def _count(key: str) -> int | None:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value

    input_tokens = _count("prompt_tokens")
    output_tokens = _count("completion_tokens")
    total_tokens = _count("total_tokens")

    reported = any(
        value is not None for value in (input_tokens, output_tokens, total_tokens)
    )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "usage_status": "REPORTED" if reported else "UNKNOWN",
    }


def _response_format(spec: StructuredOutputSpec) -> Mapping[str, Any]:
    """Serialize a structured-output request (§6.7).

    The wrapper shape for `json_schema` is **unverified** for both in-scope
    providers. It is written here so the request is representable, and the
    capability gate refuses to send it: structured output is UNKNOWN on every
    model profile, so no call reaches this code path today. Confirming the
    shape is AI-02-B6 work.
    """
    if spec.mode == "json_object":
        return {"type": "json_object"}
    if spec.mode == "json_schema":
        body: dict[str, Any] = {"type": "json_schema"}
        if spec.schema is not None:
            body["json_schema"] = {"schema": dict(spec.schema)}
        return body
    return {"type": spec.mode}

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
        transport_settings: TransportSettings,
        method: str = "POST",
    ) -> TransportRequest:
        """Compose the outbound request.

        The credential is placed only in the `Authorization` header. The
        returned request never renders it: `TransportRequest.__repr__` and
        `redacted_headers()` mask sensitive header values.

        Timeouts and TLS verification come from `transport_settings`, which the
        caller supplies from runtime config. Nothing is read off the profile:
        transport settings are runtime config, not profile data (§5.11).
        """
        return TransportRequest(
            method=method,
            url=self.effective_url(profile),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {credential}",
            },
            body=body,
            timeout_connect_ms=transport_settings.timeout_connect_ms,
            timeout_total_ms=transport_settings.timeout_total_ms,
            verify_tls=transport_settings.verify_tls,
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

    def build_payload(
        self,
        *,
        model_id: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]] = (),
        structured_output: StructuredOutputSpec | None = None,
        temperature: float | None = None,
        max_output: int | None = None,
        stop: Sequence[str] = (),
        stream: bool = False,
    ) -> Mapping[str, Any]:
        """Serialize normalized fields into a chat-completions body (§21).

        `model` is the API model id and nothing else. A display name would be a
        different string entirely and is never sent (§6.3), and Workbench
        metadata is internal attribution, not prompt content (§7.4).

        Only fields the protocol defines are emitted. Absent optional values
        are omitted rather than sent as null, so a provider default is used
        instead of an explicit empty value.
        """
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [dict(message) for message in messages],
            "stream": bool(stream),
        }

        if tools:
            payload["tools"] = [dict(tool) for tool in tools]
        if temperature is not None:
            payload["temperature"] = temperature
        if max_output is not None:
            # `max_tokens` is the field this protocol family defines. It is not
            # a normalized name, so it is set here and only here.
            payload["max_tokens"] = max_output
        if stop:
            payload["stop"] = list(stop)
        if structured_output is not None and structured_output.mode != "none":
            payload["response_format"] = _response_format(structured_output)

        return payload

    def parse_response(
        self, profile: ProviderProfile, model_ref: ModelRef, payload: Any
    ) -> ProviderResponse:
        """Map a provider payload into the normalized envelope (§5.8, §9-§13).

        Two rules govern this mapping:

        **Nothing is inferred.** Reasoning is read from its own field and never
        concatenated into `text`; tool calls never leak into `text`; and
        `structured_output` stays `None` because this protocol defines no
        structured-result field. A JSON-looking string is not evidence of
        schema-enforced output, and guessing would be the exact false
        confidence the contract forbids.

        **A shape we do not understand is refused, not absorbed.** A payload
        that is not an object, has no choices, or carries a non-text content
        shape raises `PROTOCOL` rather than yielding a successful result with
        silently missing content.
        """
        if not isinstance(payload, Mapping):
            raise self._protocol_error(
                f"expected a JSON object, got {type(payload).__name__}"
            )

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise self._protocol_error("response carries no choices")

        first = choices[0]
        if not isinstance(first, Mapping):
            raise self._protocol_error(
                f"choices[0] must be an object, got {type(first).__name__}"
            )

        message = first.get("message")
        if not isinstance(message, Mapping):
            raise self._protocol_error(
                f"choices[0].message must be an object, got {type(message).__name__}"
            )

        text = message.get("content")
        if text is not None and not isinstance(text, str):
            # v1 declares text output only. A non-text content shape is not
            # silently dropped: an empty success would lose the answer.
            raise self._protocol_error(
                f"choices[0].message.content must be a string or null, got "
                f"{type(text).__name__}; this adapter serves text output only"
            )

        return ProviderResponse(
            provider_id=profile.provider_id,
            model_id=model_ref.model_id,
            text=text,
            tool_calls=_normalize_tool_calls(message.get("tool_calls")),
            # No provider field defines a structured result, so this stays None.
            # Parsing `text` as JSON here would assert schema conformance the
            # provider never claimed (§12).
            structured_output=None,
            reasoning=_normalize_reasoning(message),
            usage=_normalize_usage(payload.get("usage")),
            finish_state=_finish_state(first.get("finish_reason")),
            provider_request_id=(
                payload.get("id") if isinstance(payload.get("id"), str) else None
            ),
            raw_response_ref=None,
            error=None,
        )

    def _protocol_error(self, message: str) -> ProviderError:
        """The provider's response violated the declared protocol (§5.10)."""
        return ProviderError(
            error_class=ErrorClass.PROTOCOL,
            stage=ErrorStage.PARSE,
            provider_message_sanitized=redact(message),
        )


__all__ = ["OpenAICompatibleChatAdapter"]
