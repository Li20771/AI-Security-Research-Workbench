"""The reference a successful backend returns (contract §19.2.1).

One form, and only one::

    sha256:<64 lowercase hex>

It is a **provenance / content digest reference**, not a retrievable artifact
locator. It does not assert that a durable artifact exists, that anything can be
downloaded by presenting it, or that the bytes survive the process. AI-09 v1
creates no artifact store, and nothing may present this value as one.

The digest is taken over AI-02's **already-normalized** values. That is the point:
a digest over a raw provider payload would depend on a wire shape AI-02 exists to
hide, and two providers that normalize to the same result would disagree.

JSON canonicalization is fixed so two conforming implementations produce the same
bytes for the same normalized value::

    UTF-8, ensure_ascii=false, sort_keys=true, separators=(",", ":")

Never hashed: pretty-printed JSON, the raw provider payload, HTTP headers, a
credential, the endpoint URL, or any part of a `ContextResponse`.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from providers.invocation import InvocationResult, InvocationStatus, ToolCall

from integrations.codex.errors import CodexInvocationError

__all__ = [
    "REFERENCE_RE",
    "canonical_json",
    "reference_for",
    "select_digest_input",
]

#: The one reference shape. `AgentResult.result` accepts this form, and a
#: lowercase-only digest keeps two spellings of the same digest from differing.
REFERENCE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

#: Digest-input form, by the invocation's normalized shape. The form is a
#: property of the result, never a caller's choice — a caller able to pick would
#: be able to make one result look like another.
FORM_TOOL_CALLS = "tool_calls"
FORM_STRUCTURED_OUTPUT = "structured_output"
FORM_TEXT = "text"


def canonical_json(value: Any) -> str:
    """The canonical JSON representation (contract §19.2.1).

    Deliberately not `json.dumps` defaults: a space after a separator would make
    the digest depend on a formatting choice rather than on the value.
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def select_digest_input(result: InvocationResult) -> tuple[str, bytes]:
    """Choose the canonical digest input for a normalized result.

    Precedence follows what the response *is*: a response carrying tool calls is
    a tool-call response even if it also carries text, because the calls are the
    part a consumer must act on and the part that must not be silently dropped.
    """
    if result.tool_calls:
        envelope = {
            "tool_calls": [_tool_call_entry(call) for call in result.tool_calls]
        }
        return FORM_TOOL_CALLS, canonical_json(envelope).encode("utf-8")

    if result.structured_output is not None:
        return FORM_STRUCTURED_OUTPUT, canonical_json(
            dict(result.structured_output)
        ).encode("utf-8")

    # An empty success digests the empty string rather than failing: the
    # invocation succeeded, and a digest of nothing is a fact about it.
    return FORM_TEXT, (result.text or "").encode("utf-8")


def _tool_call_entry(call: ToolCall) -> Mapping[str, Any]:
    """One normalized tool call, in a shape that sorts deterministically.

    `arguments` stays the raw JSON string the provider sent. Parsing it here
    would assert a well-formedness the provider never confirmed, and would make
    the digest depend on a parse this layer does not own.
    """
    return {"arguments": call.arguments, "id": call.id, "name": call.name}


def _digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def reference_for(result: InvocationResult) -> str:
    """The reference for a successful invocation, or a typed refusal.

    `status` is the only success signal (AI-02 §7.2), and `LENGTH` on a success
    means the answer is **truncated**, not complete. With no durable artifact
    store, a truncated reference would be indistinguishable downstream from a
    complete one, so it is refused rather than returned (contract §19.4).
    """
    if result.status is not InvocationStatus.SUCCESS:
        raise CodexInvocationError(
            f"invocation did not succeed: status={result.status} "
            f"blocked={_block_code(result)}",
            result=result,
        )

    if result.is_truncated:
        raise CodexInvocationError(
            "invocation succeeded but the answer is truncated "
            f"(finish_state={result.finish_state}); a truncated answer is not "
            "final output and produces no reference",
            result=result,
        )

    _, data = select_digest_input(result)
    return _digest(data)


def _block_code(result: InvocationResult) -> str | None:
    blocked: Sequence[Any] | None = getattr(result, "blocked", None)
    if blocked is None:
        return None
    return str(getattr(blocked, "code", blocked))
