"""Test R's child process: mint through the HELPER, accept through REAL admission.

Run as a SCRIPT by the round-trip test, via the designated launcher, which
supplies the trust configuration to this process BEFORE it starts — which is
what a deployment does and what §7.3.11's one-read rule requires. This module
is NOT a ``test_*.py`` module, so pytest collects nothing from it (the same
status ``tests/evidence/trust_harness.py`` records for itself).

The child holds a TEST key only (§15.8:1224-1225 — no test holds or generates
a real private key), mints the proof with ``producer_proof_for`` — the code
under test — and runs AI-05's real ``admit()``. The exit code carries the
verdict; the parent asserts on both the code and the printed outcome.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

from plugins.evidence.admission import admit  # noqa: E402
from plugins.evidence.vocabulary import AdmissionOutcome  # noqa: E402
from plugins.security_tools.evidence import execution_payload_for  # noqa: E402
from plugins.security_tools.result import ToolResult  # noqa: E402
from plugins.security_tools.signing import producer_proof_for  # noqa: E402
from plugins.security_tools.vocabulary import ToolOutcome  # noqa: E402

#: The SAME TEST seed trust_harness maps for ai-06 (``_SEEDS["ai-06"]`` in
#: tests/evidence/trust_harness.py, ``"44" * 31 + "06"``). A fake: publicly
#: known, and authorizing nothing. The parent test PROVES the pairing against
#: the "default" configuration before launching this child, so a drift in
#: either place fails loudly instead of silently signing under the wrong key.
_AI06_TEST_SEED = bytes.fromhex("44" * 31 + "06")

DECLARED_ACTOR = {"id": "ai-06", "type": "service"}
WS = "ws-1"

RESULTS = (
    ToolResult(
        tool_id="git",
        tool_version="1.0.0",
        operation="status",
        outcome=ToolOutcome.COMPLETED,
        reason_code="COMPLETED",
        workspace_id=WS,
        guard={"decision": "ALLOW"},
    ),
)


class _FakeSigner:
    """The deployment's capability, doubled: two members, nothing else (§15.8)."""

    def __init__(self) -> None:
        self.producer_token = "ai-06"
        self._key = Ed25519PrivateKey.from_private_bytes(_AI06_TEST_SEED)

    def sign(self, message: bytes) -> bytes:
        return self._key.sign(message)


def main() -> int:
    """One complete round trip: projection -> check-then-sign -> admit."""
    mapping = {
        "schema_version": 1,
        "kind": "EXECUTION",
        "provenance": {
            "producer": "ai-06",
            "producer_version": "1.0.0",
            "producer_type": "service",
            "actor": dict(DECLARED_ACTOR),
            "workspace_id": WS,
        },
        "payload": execution_payload_for(RESULTS).to_mapping(),
    }
    proof = producer_proof_for(
        mapping,
        RESULTS,
        signer=_FakeSigner(),
        actor=DECLARED_ACTOR,
        workspace_id=WS,
    )
    result = admit(mapping, producer_proof=proof)
    print(f"OUTCOME={result.outcome.value}")
    if result.reason_code is not None:
        print(f"REASON={result.reason_code}")
    return 0 if result.outcome is AdmissionOutcome.ACCEPTED else 1


if __name__ == "__main__":
    raise SystemExit(main())
