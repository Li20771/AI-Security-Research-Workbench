"""Credential redaction for outbound provider text.

Contract §10.3: `provider_message_sanitized` is sanitized **at capture time**,
not at display time -- anything stored unsanitized is already a leak.

Providers echo request material into error bodies, so any text that leaves the
transport must pass through `redact()` before it is stored, logged, or placed
in an error object.

Two layers:

1. Pattern rules for credential-shaped text (headers, key=value parameters,
   vendor-prefixed key formats, long opaque tokens).
2. Exact-value replacement for secrets the caller already holds. This layer
   matters more than the first: `SecretValue.reveal()` output can be scrubbed
   literally, so redaction does not depend on guessing a key's shape.
"""

from __future__ import annotations

import re
from typing import Iterable

REDACTED = "[REDACTED]"

_PATTERN_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    # Authorization headers, with or without a scheme token.
    (
        re.compile(r"(?i)\bauthorization\b\s*[:=]\s*\S+"),
        f"authorization: {REDACTED}",
    ),
    # key=value style credential parameters.
    (
        re.compile(
            r"(?i)\b("
            r"api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|auth[_-]?token"
            r"|bearer|token|secret|password|passwd|pwd"
            r")\b\s*[:=]\s*[\"']?([^\s\"',;}\]]+)"
        ),
        rf"\1={REDACTED}",
    ),
    # Vendor-prefixed key formats.
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), REDACTED),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}"), REDACTED),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"), REDACTED),
    # Long opaque tokens. Deliberately aggressive: over-redacting provider
    # error text is safe, under-redacting is not.
    (re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"), REDACTED),
)


def redact(text: str | None, *, extra_secrets: Iterable[str] = ()) -> str | None:
    """Return `text` with credential-shaped and known-secret content removed.

    `extra_secrets` are exact values the caller already holds (typically a
    revealed `SecretValue`). They are replaced literally, so a secret is
    scrubbed even when its shape matches no pattern rule.

    Returns `None` for `None` input so callers can pass optional fields
    straight through.
    """
    if text is None:
        return None

    result = text
    # Exact values first: they are the strongest signal, and running the
    # pattern rules afterwards cannot re-introduce them.
    for secret in extra_secrets:
        if secret:
            result = result.replace(secret, REDACTED)
    for pattern, replacement in _PATTERN_RULES:
        result = pattern.sub(replacement, result)
    return result
