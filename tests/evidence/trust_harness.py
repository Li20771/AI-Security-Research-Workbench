"""The producer-trust test launcher (§31.3, §7.3.11).

**This is the ONLY module outside the reader in which the designated variable's
name may appear**, and within it the name appears ONLY as a key in the
environment mapping handed to a child-process launch. §31.3 states that
exception and its three narrow dimensions — one module, one shape, one variable
— and records that it is not an exception for tests in general and not one for
any production module.

WHY A LAUNCHER AT ALL. §7.3.11 reads the configuration ONCE, during the
initialization of `plugins/evidence/producer_auth.py`, and the state that
produces is final for the process. **Changing the variable after initialization
is not a supported way to reload the trust root**, so a case that needs a
particular configuration cannot get one by setting the variable mid-test: it
would change nothing the reader consults. The case supplies the variable to a
process that has NOT started yet — which is exactly what a deployment does. Only
the process boundary differs.

WHAT IS NOT DONE HERE. This module does not mutate the running process's
environment (§31.3, NO MUTATION). It does not reload the reader. It does not
inject a mapping, a key, a verifier or a parsed state into the reader — §7.3.7
forbids a test-only bypass, and the process boundary is what makes one
unnecessary rather than merely disallowed. Every case it launches imports the
REAL reader and runs the ORDINARY admission and verification path.

THE KEYS ARE FIXED AND SHARED, and they are TEST KEYS. §7.3.7 requires a
DISTINCT keypair per producer token, and a child can only sign a proof if it
holds the same private key whose public half the parent put in the configuration
— so the keypairs are module constants rather than generated per test. They are
publicly known values in a public repository and authorise nothing.

THE FILE'S OWN IMPORTS ARE UNCONSTRAINED. `tests/` is reached by Layer 0 only
through `check_layer_markers`, which globs `test_*.py`; a support module is not
a test module and needs no layer marker, exactly as
`tests/integrations/support.py` does not.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import subprocess
import sys
from typing import Any, Mapping

#: Run as a SCRIPT (`python tests/evidence/trust_harness.py ...`) this file's own
#: directory goes on `sys.path` and the repository root does not, so `plugins` is
#: unimportable. Put the root back, so the launcher works in both shapes.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

from plugins.evidence.signed_input import signed_input  # noqa: E402

__all__ = [
    "ENV_NAME",
    "CONFIG_NAMES",
    "config_value",
    "child_environment",
    "proof_for",
    "run_isolated",
    "PRODUCER_TOKENS",
    "UNREGISTERED_TOKENS",
]

#: §7.3.11 — the designated variable. Named HERE and in the reader, and nowhere
#: else in this repository.
ENV_NAME = "WORKBENCH_EVIDENCE_PRODUCER_TRUST_CONFIG"

#: §6.5's four registered tokens. A key is configured for each, and each holds
#: its OWN key material (§7.3.2's one-key-per-recognized-token rule).
PRODUCER_TOKENS = ("ai-02", "ai-03", "ai-04", "ai-06")

#: Tokens §6.5 does NOT register. A key for one of these is permitted and INERT
#: (§7.3.11), and its PRESENCE is load-bearing because it participates in the
#: group rule.
UNREGISTERED_TOKENS = ("ai-98", "ai-99")

#: 32-byte Ed25519 seeds. Distinct per token, as §7.3.7 requires. TEST KEYS.
_SEEDS: dict[str, str] = {
    "ai-02": "11" * 31 + "02",
    "ai-03": "22" * 31 + "03",
    "ai-04": "33" * 31 + "04",
    "ai-06": "44" * 31 + "06",
    "ai-98": "55" * 31 + "98",
    "ai-99": "66" * 31 + "99",
    # A SECOND key for each recognized token, for the "distinct control" and for
    # building collision fixtures without disturbing the keys above.
    "ai-02#b": "71" * 31 + "02",
    "ai-03#b": "72" * 31 + "03",
    "ai-04#b": "73" * 31 + "04",
    "ai-06#b": "74" * 31 + "06",
    "ai-98#b": "75" * 31 + "98",
}


def _private(label: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(_SEEDS[label]))


def _public_hex(label: str) -> str:
    """§7.3.11 — 64 LOWERCASE hexadecimal characters."""
    return _private(label).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()


def _valid_default() -> dict[str, dict[str, str]]:
    return {token: _public_hex(token) for token in PRODUCER_TOKENS}


def _config(**overrides: Any) -> str:
    document = {"collision_policy": "A", "producer_keys": _valid_default()}
    document.update(overrides)
    return json.dumps(document)


def _named_document(name: str) -> dict[str, Any] | None:
    """The JSON document for a named case, or `None` when the variable must be
    ABSENT (a different state from an invalid one, though both fail closed)."""
    keys = _valid_default()
    shared_recognized = _public_hex("ai-02#b")
    shared_mixed = _public_hex("ai-03#b")
    shared_unregistered = _public_hex("ai-98#b")

    if name == "default":
        return {"collision_policy": "A", "producer_keys": keys}
    if name == "regression":
        # The configuration the EXISTING evidence suite runs under (CI's Layer 1
        # step). A fixed, valid mapping with a distinct key per producer token,
        # so the regression cases reach the behaviour they were written for.
        return {"collision_policy": "A", "producer_keys": keys}
    if name == "policy_b":
        return {"collision_policy": "B", "producer_keys": keys}
    if name == "absent":
        return None
    if name == "empty_keys":
        return {"collision_policy": "A", "producer_keys": {}}
    if name == "collision_recognized":
        # ONE PUBLIC KEY, TWO RECOGNIZED TOKENS: the whole mapping is refused
        # under BOTH policies (§7.3.2, §7.3.11).
        return {"collision_policy": "A",
                "producer_keys": {**keys, "ai-02": shared_recognized,
                                  "ai-03": shared_recognized}}
    if name == "collision_mixed":
        # ONE PUBLIC KEY, A RECOGNIZED TOKEN AND AN UNREGISTERED ONE: refused
        # under BOTH. Tolerating this would let the shared key's holder sign a
        # claim naming the RECOGNIZED token, which §6.6 admits.
        return {"collision_policy": "A",
                "producer_keys": {**keys, "ai-04": shared_mixed,
                                  "ai-98": shared_mixed}}
    if name == "collision_unregistered":
        # The ONE case the two policies treat differently.
        return {"collision_policy": "A",
                "producer_keys": {**keys, "ai-98": shared_unregistered,
                                  "ai-99": shared_unregistered}}
    if name == "collision_unregistered_b":
        return {"collision_policy": "B",
                "producer_keys": {**keys, "ai-98": shared_unregistered,
                                  "ai-99": shared_unregistered}}
    if name == "distinct_control":
        return {"collision_policy": "A",
                "producer_keys": {**keys, "ai-98": _public_hex("ai-98"),
                                  "ai-99": _public_hex("ai-99")}}
    if name == "unregistered_only":
        # A key for a token §6.5 does not register: INERT, and it admits nothing.
        return {"collision_policy": "A",
                "producer_keys": {**keys, "ai-98": _public_hex("ai-98")}}
    if name == "no_entry_for_token":
        return {"collision_policy": "A",
                "producer_keys": {t: k for t, k in keys.items() if t != "ai-03"}}
    if name == "uppercase_key":
        return {"collision_policy": "A",
                "producer_keys": {**keys, "ai-03": _public_hex("ai-03").upper()}}
    if name == "short_key":
        return {"collision_policy": "A",
                "producer_keys": {**keys, "ai-03": "ab" * 31}}
    if name == "unknown_member":
        return {"collision_policy": "A", "producer_keys": keys, "extra": 1}
    if name == "missing_member":
        return {"producer_keys": keys}
    if name == "bad_policy":
        return {"collision_policy": "C", "producer_keys": keys}
    if name == "policy_not_string":
        return {"collision_policy": 1, "producer_keys": keys}
    if name == "keys_not_object":
        return {"collision_policy": "A", "producer_keys": []}
    raise KeyError(f"no such test configuration: {name}")


#: Values supplied VERBATIM, because they are not well-formed documents and
#: cannot be produced by `json.dumps` of a Python object.
_RAW_VALUES: dict[str, str] = {
    "root_is_array": '[{"collision_policy": "A"}]',
    "root_is_string": '"A"',
    "root_is_null": "null",
    "empty_string": "",
    "invalid_json": "{not json",
    "trailing_content": '{"collision_policy":"A","producer_keys":{}} trailing',
    "duplicate_member": '{"collision_policy":"A","collision_policy":"B",'
                        '"producer_keys":{}}',
    "duplicate_in_keys": '{"collision_policy":"A","producer_keys":'
                         '{"ai-03":"' + "aa" * 32 + '","ai-03":"' + "bb" * 32 + '"}}',
    "nan_constant": '{"collision_policy":NaN,"producer_keys":{}}',
    "infinity_constant": '{"collision_policy":Infinity,"producer_keys":{}}',
    "unpaired_surrogate": '{"collision_policy":"A","producer_keys":'
                          '{"ai-03":"\\ud800' + "aa" * 30 + '"}}',
}


#: The names a case may ask for.
CONFIG_NAMES = tuple(
    sorted(
        [
            "default", "policy_b", "absent", "empty_keys",
            "collision_recognized", "collision_mixed",
            "collision_unregistered", "collision_unregistered_b",
            "distinct_control", "unregistered_only", "no_entry_for_token",
            "uppercase_key", "short_key", "unknown_member", "missing_member",
            "bad_policy", "policy_not_string", "keys_not_object",
            *_RAW_VALUES.keys(),
        ]
    )
)


def config_value(name: str) -> str | None:
    """The designated variable's value for `name`, or `None` for ABSENT.

    Built from the FIXED test keys, so the same public key the parent
    configures is the one whose private half a child signs with.
    """
    if name in _RAW_VALUES:
        return _RAW_VALUES[name]
    document = _named_document(name)
    if document is None:
        return None
    return json.dumps(document)


def child_environment(name: str) -> dict[str, str]:
    """The environment for a child launched to exercise configuration `name`.

    A COPY of this process's environment with the designated variable set for
    the child — never a write to this process's own environment. §31.3 permits
    the name to appear here, as a key in the mapping handed to a child-process
    launch, and nowhere else.
    """
    environment = dict(os.environ)
    value = config_value(name)
    if value is None:
        environment.pop(ENV_NAME, None)
    else:
        environment[ENV_NAME] = value
    return environment


def run_isolated(
    name: str, program: list[str], *, timeout: int = 600
) -> subprocess.CompletedProcess[str]:
    """Launch `program` in a child that sees configuration `name` from startup."""
    return subprocess.run(
        program,
        env=child_environment(name),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def proof_for(token: str, raw: Any) -> dict[str, str]:
    """A valid proof for `raw`, signed under `token`'s configured key (§7.3.3).

    It goes through the REAL construction — `signed_input` is the same function
    the verifier reconstructs with — so a case that signs here and verifies
    there exercises one protocol and not two.
    """
    message = signed_input(raw)
    signature = _private(token).sign(message)
    return {
        "message_b64u": base64.urlsafe_b64encode(message).rstrip(b"=").decode("ascii"),
        "signature": signature.hex(),
    }


def proof_for_record(raw: Mapping[str, Any], token: str | None = None) -> dict[str, str]:
    """A valid proof for `raw`, signed under the token `raw` itself names.

    The regression suite's entry point: every case that previously reached
    admission with a well-formed record now reaches it with a well-formed AND
    authenticated one, which is what keeps the case about the behaviour it was
    written for rather than about the new step. `token` is for the cross-producer
    cases, where the two must differ on purpose.
    """
    if token is None:
        provenance = raw.get("provenance") if isinstance(raw, Mapping) else None
        token = provenance.get("producer") if isinstance(provenance, Mapping) else None
        if not isinstance(token, str):
            # A case built around input §7.3.5 V2 cannot read a token from. The
            # proof is then IMMATERIAL to what the case asserts, and it has to be:
            # V2 reports an EXISTING shape reason and NO KEY LOOKUP occurs, so the
            # signature is never consulted. Signing under a default token keeps
            # such a case reaching the stage it is about, and it cannot turn a
            # shape refusal into an acceptance — the envelope is well formed and
            # the token it names is never reached.
            token = PRODUCER_TOKENS[0]
    return proof_for(token, raw)


def main(argv: list[str]) -> int:
    """`python tests/evidence/trust_harness.py <config> -- <command...>`"""
    if "--" not in argv or len(argv) < 3:
        print(
            "usage: trust_harness.py <config-name> -- <command...>\n"
            f"configs: {', '.join(CONFIG_NAMES)}",
            file=sys.stderr,
        )
        return 2
    split = argv.index("--")
    name = argv[split - 1] if split >= 1 else ""
    program = argv[split + 1:]
    completed = run_isolated(name, program)
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main(sys.argv[1:]))
