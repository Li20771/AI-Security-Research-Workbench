"""The §15.8 signing boundary, as eight negative tests and one round trip.

**AI-06's own tree, not AI-05's acceptance matrix** — no recorded count moves
there. Until these tests existed and ran, §15.8's boundary was "a rule and
not a demonstrated property" (docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md
:1228-1229); this module is the demonstration half of that, and the dormant
capability itself (``plugins/security_tools/signing.py``) is the other half.

```text
DORMANT CAPABILITY UNDER TEST. Nothing here wires a call site: the §7.3.13
approved set stays EMPTY, no production module calls the helper, and
composition/ is untouched. The signer every test uses is a TEST DOUBLE over
a fixed, publicly known 32-byte seed — obligation 8 (§15.8:1224-1225) — and
the designated variable's name appears nowhere in this module (§31.3: the
reader and the launcher are the only two files that may name it).
```

The eight lines of §15.8:1209-1226, mapped:

```text
1   payload != execution_payload_for(results)        SigningPayloadMismatch
2   same ToolResult + FORGED actor                   SigningActorMismatch
3   same ToolResult + FORGED workspace identity      SigningWorkspaceMismatch
4   FORGED producer token (signer speaks for ai-02)  SignerTokenMismatch
5   FORGED event kind / actor type vs the §6.5 row   SigningRegistryMismatch
6   caller-chosen field the contract does NOT assign SigningFieldUnmapped /
    to the caller — THE TEST NAMES THE FIELD            SigningPayloadMismatch
7   UNSIGNED submission at admission                  AUTHENTICATION_PROOF_MISSING
7b  absent capability at the helper (:1134-1139)      SignerUnavailable
8   no real key in the matrix — EXECUTED here as a    the scan + the fixed
    scan of plugins/ plus the fixed TEST seeds         seeds, asserted
R   helper-minted proof ACCEPTED by real admission    the round trip, in a
    (extra: not one of the eight; proves the mint      child process via the
    and verify sides agree byte-for-byte)              designated launcher
```

Tests 1-6 and 7b assert the refusal AT THE SOURCE — the signer's call
counter stays at zero, so the refusal is proven to happen BEFORE any
signature exists, not merely to fail verification downstream. Test 7 asserts
the DOWNSTREAM admission outcome, as §15.8:1222-1223 requires. Test R is
self-contained: it launches its own child through the designated launcher,
so it passes under CI's layer1 step and under a plain local run alike.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from plugins.evidence.admission import admit
from plugins.evidence.vocabulary import AdmissionOutcome
from plugins.security_tools.errors import (
    SignerTokenMismatch,
    SignerUnavailable,
    SigningActorMismatch,
    SigningFieldUnmapped,
    SigningPayloadMismatch,
    SigningRegistryMismatch,
    SigningWorkspaceMismatch,
)
from plugins.security_tools.evidence import execution_payload_for
from plugins.security_tools.result import ToolResult
from plugins.security_tools.signing import producer_proof_for
from plugins.security_tools.vocabulary import ToolOutcome

pytestmark = pytest.mark.layer1

_ROOT = Path(__file__).resolve().parents[2]

#: 32-byte TEST seeds — fixed, publicly known, authorizing nothing, the same
#: class of fake tests/evidence/trust_harness.py holds. The ai-06 seed MUST
#: be the one the "default" configuration maps for ai-06; test R proves that
#: pairing against the configuration itself before relying on it.
_AI06_TEST_SEED = bytes.fromhex("44" * 31 + "06")
_AI02_TEST_SEED = bytes.fromhex("11" * 31 + "02")

WS = "ws-1"
DECLARED_ACTOR = {"id": "ai-06", "type": "service"}
FORGED_ACTOR = {"id": "ai-02", "type": "service"}


class _FakeSigner:
    """A test double for the deployment-injected capability (§15.8).

    Holds a TEST key — never a real one (obligation 8) — and counts calls,
    so a refusal test can prove the refusal happened BEFORE the signer was
    reached rather than after a signature was made.
    """

    def __init__(self, token: str, seed: bytes) -> None:
        self.producer_token = token
        self.calls = 0
        self._key = Ed25519PrivateKey.from_private_bytes(seed)

    def sign(self, message: bytes) -> bytes:
        self.calls += 1
        return self._key.sign(message)


def _results() -> tuple[ToolResult, ...]:
    return (
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


def _execution_mapping(**overrides: Any) -> dict[str, Any]:
    """A well-formed ai-06 EXECUTION whose payload IS the projection.

    The payload is built THROUGH ``execution_payload_for`` — the one
    projection path — so a passing case is about the boundary, and a failing
    case fails because the test tampered with exactly one thing.
    """
    record: dict[str, Any] = {
        "schema_version": 1,
        "kind": "EXECUTION",
        "provenance": {
            "producer": "ai-06",
            "producer_version": "1.0.0",
            "producer_type": "service",
            "actor": dict(DECLARED_ACTOR),
            "workspace_id": WS,
        },
        "payload": execution_payload_for(_results()).to_mapping(),
    }
    record.update(overrides)
    return record


def _mint(
    mapping: Mapping[str, Any],
    *,
    signer: Any,
    actor: Mapping[str, str] = DECLARED_ACTOR,
    workspace_id: str = WS,
) -> dict[str, str]:
    return producer_proof_for(
        mapping,
        _results(),
        signer=signer,
        actor=actor,
        workspace_id=workspace_id,
    )


def _load_trust_harness() -> Any:
    """The designated launcher, loaded by path — invocation-independent.

    The name of the configuration variable appears in the launcher, never
    here (§31.3); loading by file path keeps that true under every way
    pytest can be started.
    """
    path = _ROOT / "tests" / "evidence" / "trust_harness.py"
    spec = importlib.util.spec_from_file_location("ai15_open1_trust_harness", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestProducerSigningBoundary:
    def test_0_the_helper_mints_the_closed_keyed_envelope(self) -> None:
        """The mint works when everything agrees — §7.3.3's exact envelope."""
        signer = _FakeSigner("ai-06", _AI06_TEST_SEED)
        proof = _mint(_execution_mapping(), signer=signer)
        assert set(proof) == {"message_b64u", "signature"}
        assert len(proof["signature"]) == 128
        assert proof["signature"] == proof["signature"].lower()
        assert proof["message_b64u"] and "=" not in proof["message_b64u"]
        assert signer.calls == 1

    def test_1_payload_not_the_projection_is_refused(self) -> None:
        """§15.8:1209-1210 — and produces NO proof."""
        signer = _FakeSigner("ai-06", _AI06_TEST_SEED)
        mapping = _execution_mapping()
        mapping["payload"]["tool_calls[]"][0]["what_ran"] = "git/log"
        with pytest.raises(SigningPayloadMismatch):
            _mint(mapping, signer=signer)
        mapping = _execution_mapping()
        mapping["payload"] = {"tool_calls[]": []}
        with pytest.raises(SigningPayloadMismatch):
            _mint(mapping, signer=signer)
        assert signer.calls == 0

    def test_2_forged_actor_is_refused_at_the_source(self) -> None:
        """§15.8:1211-1213 — refusal, not a downstream verification failure."""
        signer = _FakeSigner("ai-06", _AI06_TEST_SEED)
        mapping = _execution_mapping()
        mapping["provenance"]["actor"] = dict(FORGED_ACTOR)
        with pytest.raises(SigningActorMismatch):
            _mint(mapping, signer=signer)
        assert signer.calls == 0

    def test_3_forged_workspace_identity_is_refused_at_the_source(self) -> None:
        """§15.8:1214 — the record's scope and every foreign item with it."""
        signer = _FakeSigner("ai-06", _AI06_TEST_SEED)
        mapping = _execution_mapping()
        mapping["provenance"]["workspace_id"] = "ws-other"
        with pytest.raises(SigningWorkspaceMismatch):
            _mint(mapping, signer=signer)
        mapping = _execution_mapping()
        mapping["references"] = {"context": [{"workspace_id": "ws-other"}]}
        with pytest.raises(SigningWorkspaceMismatch):
            _mint(mapping, signer=signer)
        assert signer.calls == 0

    def test_4_forged_producer_token_is_refused_before_signing(self) -> None:
        """§15.8:1215-1217 — a signer for ai-02 cannot sign an ai-06 claim."""
        signer = _FakeSigner("ai-02", _AI02_TEST_SEED)
        with pytest.raises(SignerTokenMismatch):
            _mint(_execution_mapping(), signer=signer)
        assert signer.calls == 0

    def test_5_forged_event_kind_or_family_is_refused_against_the_registry_row(
        self,
    ) -> None:
        """§15.8:1218 — the §6.5 row decides kind, family and actor type."""
        signer = _FakeSigner("ai-06", _AI06_TEST_SEED)
        # DECISION is a registered event — for another producer (ai-04).
        with pytest.raises(SigningRegistryMismatch):
            _mint(_execution_mapping(kind="DECISION"), signer=signer)
        # OBSERVATION with no family has no row at all.
        with pytest.raises(SigningRegistryMismatch):
            _mint(_execution_mapping(kind="OBSERVATION"), signer=signer)
        # An actor type no ai-06 row admits — the row fixes actor.type.
        mapping = _execution_mapping()
        mapping["provenance"]["actor"] = {"id": "ai-06", "type": "human"}
        with pytest.raises(SigningRegistryMismatch):
            _mint(mapping, signer=signer, actor={"id": "ai-06", "type": "human"})
        assert signer.calls == 0

    def test_6_a_field_the_contract_does_not_assign_to_the_caller_is_refused(
        self,
    ) -> None:
        """§15.8:1219-1221 — the fields are NAMED, so the check is not vacuous.

        Only `ordinal` is caller-assigned. Everything else below is a field
        the caller chose anyway, and each is refused BEFORE signing.
        """
        signer = _FakeSigner("ai-06", _AI06_TEST_SEED)

        # NAMED FIELD: `provenance.submitter` — no source class; and the very
        # field the frozen contracts refuse to add to the record.
        mapping = _execution_mapping()
        mapping["provenance"]["submitter"] = "caller"
        with pytest.raises(SigningFieldUnmapped):
            _mint(mapping, signer=signer)

        # NAMED FIELD: `record.integrity` — AI-05 generates this, and
        # construction does NOT refuse a supplied block (it rebuilds it,
        # models.py:1577-1585), so the mint side must: the signature would
        # otherwise cover a block with no defined source.
        mapping = _execution_mapping()
        mapping["integrity"] = {"content_digest": "d" * 64}
        with pytest.raises(SigningFieldUnmapped):
            _mint(mapping, signer=signer)

        # NAMED FIELD: `record.identity` — same generated class, same refusal.
        mapping = _execution_mapping()
        mapping["identity"] = {"kind": "EXECUTION"}
        with pytest.raises(SigningFieldUnmapped):
            _mint(mapping, signer=signer)

        # NAMED FIELD: `record.evidence_id` — caller-forbidden at construction
        # and unmapped here.
        mapping = _execution_mapping()
        mapping["evidence_id"] = "00000000-0000-0000-0000-000000000000"
        with pytest.raises(SigningFieldUnmapped):
            _mint(mapping, signer=signer)

        # NAMED FIELD: `payload tool_calls[].status` — caller-chosen where the
        # contract assigns it to the ToolResult's projection.
        mapping = _execution_mapping()
        mapping["payload"]["tool_calls[]"][0]["status"] = "FAIL"
        with pytest.raises(SigningPayloadMismatch):
            _mint(mapping, signer=signer)

        assert signer.calls == 0

    def test_7_an_unsigned_submission_is_rejected_with_proof_missing(self) -> None:
        """§15.8:1222-1223 — the DOWNSTREAM admission outcome, not a source refusal.

        No trust configuration is involved: V1 refuses the absent proof before
        V3 would consult any mapping (producer_auth.py:406 before :410), and
        the mapping is rule-clean so step 7 does not answer first.
        """
        result = admit(_execution_mapping(), producer_proof=None)
        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "AUTHENTICATION_PROOF_MISSING"
        assert result.record is None

    def test_7b_the_absent_capability_is_refused_not_faked(self) -> None:
        """§15.8:1134-1139 — no placeholder, no empty proof, no 'ready'."""
        with pytest.raises(SignerUnavailable):
            _mint(_execution_mapping(), signer=None)

    def test_8_no_real_key_material_exists_in_the_matrix_or_the_packages(
        self,
    ) -> None:
        """§15.8:1224-1225 — executed, not merely asserted.

        (a) no private-key identifier or loader anywhere under plugins/ —
        the invariant has no Layer 0 gate of its own, so this test IS the
        gate; (b) every key this matrix holds is a fixed, publicly known
        TEST seed.
        """
        for path in sorted((_ROOT / "plugins").rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            assert "Ed25519PrivateKey" not in source, path
            assert "from_private_bytes" not in source, path
        assert _AI06_TEST_SEED == bytes.fromhex("44" * 31 + "06")
        assert _AI02_TEST_SEED == bytes.fromhex("11" * 31 + "02")
        assert len(_AI06_TEST_SEED) == 32 and len(_AI02_TEST_SEED) == 32

    def test_r_a_helper_minted_proof_is_accepted_by_real_admission(self) -> None:
        """The mint and the verify sides agree byte-for-byte — in a child.

        The designated mechanism's shape — the configuration handed to a
        child-process launch (§31.3, via the launcher's ``child_environment``)
        — supplies the trust configuration to a process that has not started
        yet (§7.3.11), which is what a deployment does; the child mints
        through the HELPER and runs AI-05's real ``admit()``. The pairing
        this depends on — the ai-06 TEST seed and the "default"
        configuration's public key for ai-06 — is PROVEN first, not assumed.
        """
        harness = _load_trust_harness()
        config = json.loads(harness.config_value("default"))
        public_hex = (
            Ed25519PrivateKey.from_private_bytes(_AI06_TEST_SEED)
            .public_key()
            .public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            .hex()
        )
        assert config["producer_keys"]["ai-06"] == public_hex

        child = Path(__file__).resolve().parent / "roundtrip_child.py"
        # stdin is DETACHED rather than inherited: under pytest's capture the
        # parent's stdin handle cannot be duplicated into a child on Windows
        # (WinError 6), and the child reads no input anyway. The designated
        # part — the environment for a not-yet-started process — is the
        # launcher's own child_environment, unchanged.
        completed = subprocess.run(
            [sys.executable, str(child)],
            env=harness.child_environment("default"),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert completed.returncode == 0, (completed.stdout, completed.stderr)
        assert "OUTCOME=ACCEPTED" in completed.stdout
