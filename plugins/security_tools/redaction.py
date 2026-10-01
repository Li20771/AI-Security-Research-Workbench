"""The projection every result passes through before it is a `ToolResult`.

Contract §14.3, §14.4, §14.5.

### What this module claims, and what it does not

```text
IT DOES NOT CLAIM     that no secret can appear in a tool result.
                      A tool can print anything, and this is a bounded filter
                      rather than a proof.
IT DOES CLAIM         no credential is injected by AI-06 (§14.2)
                      the parent environment is never passed through (§11.2)
                      every result passes this projection (§14.3)
                      the projection is tested against known-shaped material
```

AI-06 is not a secret scanner and says so. This is AI-05 §14.1's discipline: a
guarantee nobody can test is worse than a smaller guarantee that holds.

### The residual, stated rather than hidden

A tool whose legitimate output happens to contain a long high-entropy run will be
masked, and that is the safe direction: over-redaction damages a result, while
under-redaction writes a credential into a durable record. The projection errs
toward the first.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

__all__ = ["MASK", "redact_text", "project"]

MASK = "[redacted]"

#: Known-shaped credential material. Each pattern is anchored on a form that is
#: a credential *as a form*, not on entropy alone — a rule that masked every
#: long token would destroy digests and revisions, which is the defect AI-05
#: §14.5 records about applying a redaction rule outside its domain.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Authorization / credential headers, in a header or a printed dict.
    re.compile(r"(?i)\b(authorization|proxy-authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    # Common key prefixes. `sk-` is the shape Layer 0 already watches for.
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}"),
    # `NAME=value` where the name says the value is a credential.
    re.compile(
        r"(?i)\b([A-Z0-9_]*(?:API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)"
        r"[A-Z0-9_]*)\s*[:=]\s*\S+"
    ),
    # PEM blocks, however they were printed.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    # A connection string with an inline password.
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
)


def redact_text(text: str) -> tuple[str, bool]:
    """Mask known-shaped credential material. Returns the text and whether it bit.

    The flag is returned rather than inferred by the caller: a result that says
    `redacted: true` is honest about having been altered, and one that quietly
    changed is a false record of what the tool said.
    """
    if not isinstance(text, str) or not text:
        return text, False
    redacted = text
    hit = False
    for pattern in _PATTERNS:
        redacted, count = pattern.subn(MASK, redacted)
        if count:
            hit = True
    return redacted, hit


def project(
    stdout: str, stderr: str, structured: Mapping[str, Any] | None = None
) -> tuple[str, str, dict[str, Any], bool]:
    """§14.3: everything a result carries passes through here, once.

    Returns `(stdout, stderr, structured, redacted)`.
    """
    clean_out, hit_out = redact_text(stdout)
    clean_err, hit_err = redact_text(stderr)
    clean_structured, hit_structured = _project_structured(structured or {})
    return clean_out, clean_err, clean_structured, (hit_out or hit_err or hit_structured)


def _project_structured(value: Any) -> tuple[Any, bool]:
    """Walk a structured payload, masking every string it contains.

    A structured result is a second way for the same bytes to leave the adapter,
    so leaving it unprojected would make §14.3 advisory for any adapter that
    chose to return its output as JSON instead of text.
    """
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        out: dict[Any, Any] = {}
        hit = False
        for key, entry in value.items():
            if isinstance(key, str):
                key_out, key_hit = redact_text(key)
                hit = hit or key_hit
            else:
                key_out = key
            entry_out, entry_hit = _project_structured(entry)
            hit = hit or entry_hit
            out[key_out] = entry_out
        return out, hit
    if isinstance(value, (list, tuple)):
        entries = []
        hit = False
        for entry in value:
            entry_out, entry_hit = _project_structured(entry)
            hit = hit or entry_hit
            entries.append(entry_out)
        return entries, hit
    return value, False
