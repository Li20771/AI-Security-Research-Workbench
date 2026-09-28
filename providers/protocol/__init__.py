"""Protocol adapters, keyed by wire protocol family (contract §5.4).

The family determines the adapter; the provider profile determines endpoint,
credential, and transport. One adapter can serve several providers, and does:
`deepseek` and `mimo` share `openai_compatible_chat` while keeping separate
profiles.
"""

from __future__ import annotations

from providers.protocol.base import (
    FinishState,
    ProtocolAdapter,
    ProviderCall,
    ProviderResponse,
    Transport,
    TransportFailureKind,
    TransportRequest,
    TransportResult,
)
from providers.protocol.openai_compatible_chat import OpenAICompatibleChatAdapter

#: Registered adapter instances, by protocol family.
_ADAPTERS: dict[str, ProtocolAdapter] = {
    OpenAICompatibleChatAdapter.family: OpenAICompatibleChatAdapter(),
}


class UnsupportedProtocolFamily(LookupError):
    """No adapter is registered for the requested protocol family."""


def adapter_for(family: str) -> ProtocolAdapter:
    """Return the adapter serving `family`.

    Raises rather than falling back to a default adapter: silently serving a
    protocol with the wrong adapter would corrupt every response downstream.
    """
    try:
        return _ADAPTERS[family]
    except KeyError:
        raise UnsupportedProtocolFamily(
            f"no adapter registered for protocol family {family!r} "
            f"(registered: {', '.join(sorted(_ADAPTERS)) or 'none'})"
        ) from None


def registered_families() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))


__all__ = [
    "FinishState",
    "OpenAICompatibleChatAdapter",
    "ProtocolAdapter",
    "ProviderCall",
    "ProviderResponse",
    "Transport",
    "TransportFailureKind",
    "TransportRequest",
    "TransportResult",
    "UnsupportedProtocolFamily",
    "adapter_for",
    "registered_families",
]
