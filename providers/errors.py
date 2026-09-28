"""Typed provider error taxonomy.

Implements AI-02 contract §5.9 (error reporting) and §5.10 (classification
taxonomy), frozen in `docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md`.

The taxonomy is deliberately fine-grained. Three pairs must never be merged
(§5.10, decisions D-6 and D-16):

    RATE_LIMIT          != QUOTA_EXHAUSTED        transient vs terminal
    PROTOCOL            != INVALID_REQUEST        provider broke our contract
                                                  vs we broke theirs
    CREDENTIAL_MISSING  != CREDENTIAL_UNSUPPORTED no credential supplied vs
                                                  mechanism not implemented

`retryable` is a hint for a later phase only. AI-02 implements no retry loop
(§5.11, D-12); the value exists so AI-13 can consume it without redefining it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class ErrorClass(StrEnum):
    """Frozen error classes (contract §5.10)."""

    CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
    CREDENTIAL_UNSUPPORTED = "CREDENTIAL_UNSUPPORTED"
    AUTHENTICATION = "AUTHENTICATION"
    RATE_LIMIT = "RATE_LIMIT"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    TRANSPORT = "TRANSPORT"
    SERVER = "SERVER"
    INVALID_REQUEST = "INVALID_REQUEST"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    CONTENT_FILTER = "CONTENT_FILTER"
    PROTOCOL = "PROTOCOL"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class ErrorStage(StrEnum):
    """Where a failure occurred (contract §5.9).

    Distinguishes a network fault from a provider fault, which a bare error
    class cannot express.
    """

    RESOLVE = "resolve"
    CONNECT = "connect"
    TLS = "tls"
    SEND = "send"
    RECEIVE = "receive"
    PARSE = "parse"
    VALIDATE = "validate"


#: Frozen default retryability per class (contract §5.10).
#: A hint only -- AI-02 implements no retry loop.
DEFAULT_RETRYABLE: Mapping[ErrorClass, bool] = MappingProxyType(
    {
        ErrorClass.CREDENTIAL_MISSING: False,
        ErrorClass.CREDENTIAL_UNSUPPORTED: False,
        ErrorClass.AUTHENTICATION: False,
        ErrorClass.RATE_LIMIT: True,
        ErrorClass.QUOTA_EXHAUSTED: False,
        ErrorClass.TIMEOUT: True,
        ErrorClass.TRANSPORT: True,
        ErrorClass.SERVER: True,
        ErrorClass.INVALID_REQUEST: False,
        ErrorClass.CONTEXT_OVERFLOW: False,
        ErrorClass.CONTENT_FILTER: False,
        ErrorClass.PROTOCOL: False,
        ErrorClass.CANCELLED: False,
        ErrorClass.UNKNOWN: False,
    }
)

#: Classes that are precondition failures raised before any network attempt.
PRECONDITION_CLASSES: frozenset[ErrorClass] = frozenset(
    {ErrorClass.CREDENTIAL_MISSING, ErrorClass.CREDENTIAL_UNSUPPORTED}
)


@dataclass(frozen=True, slots=True)
class ProviderError(Exception):
    """A typed provider failure (contract §5.9).

    Also an exception, so an adapter can raise it on a path that cannot return
    an envelope without inventing a second error type. It is never raised
    across a public boundary: `ProtocolAdapter.send` converts it back into a
    `ProviderResponse` carrying this object, so callers still receive failures
    as typed values rather than exceptions.

    `provider_message_sanitized` must already have passed through
    `providers.redaction.redact` at capture time -- the field name is a
    contract, not a suggestion (§10.3).
    """

    error_class: ErrorClass
    stage: ErrorStage | None = None
    provider_code: str | None = None
    provider_message_sanitized: str | None = None
    http_status: int | None = None
    retryable_override: bool | None = None

    def __str__(self) -> str:
        location = f" at {self.stage}" if self.stage is not None else ""
        detail = (
            f": {self.provider_message_sanitized}"
            if self.provider_message_sanitized
            else ""
        )
        return f"{self.error_class}{location}{detail}"

    @property
    def retryable(self) -> bool:
        """Default retryability for this class, unless explicitly overridden."""
        if self.retryable_override is not None:
            return self.retryable_override
        return DEFAULT_RETRYABLE[self.error_class]

    @property
    def is_precondition(self) -> bool:
        """True when this failure was raised before any network attempt."""
        return self.error_class in PRECONDITION_CLASSES

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the contract §5.9 shape.

        Emits `class` rather than `error_class`, matching the frozen wire
        shape. `class` is a Python keyword, so the attribute is renamed here
        and only here.
        """
        return {
            "class": str(self.error_class),
            "stage": str(self.stage) if self.stage is not None else None,
            "provider_code": self.provider_code,
            "provider_message_sanitized": self.provider_message_sanitized,
            "retryable": self.retryable,
            "http_status": self.http_status,
        }
