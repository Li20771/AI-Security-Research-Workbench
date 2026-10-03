"""AI-13 §13.3 — the DESIGNATED HUMAN APPROVAL INGRESS, and its provenance check.

```text
FROZEN: a valid workflow approval MUST originate from the EXPLICITLY DESIGNATED HUMAN
        APPROVAL INGRESS — the one authority this phase permits to produce approvals.
FROZEN: that ingress MUST be EXTERNAL to Agent, model and service execution. No Agent
        body, no tool, no provider call, no workflow step and no run may reach it,
        invoke it, or stand in for it.
FROZEN: an approval is accepted only after AI-13-C has MACHINE-VERIFIED that it came
        from that ingress. The verification is over PROVENANCE, never over the fields a
        record carries.
FROZEN: AI-13-C MUST NOT provide a constructor, a factory, a default or any other path
        by which an Agent, a model or a service can manufacture an approval, or the
        provenance that would make one acceptable.
```

### The mechanism

```text
a human acts
    -> the act is SIGNED, outside this process, with an Ed25519 private key
    -> the signed artifact arrives as BYTES
    -> this module verifies it against the DEPLOYMENT'S DESIGNATED ANCHOR
```

An Ed25519 signature is used rather than a shared secret because a shared secret would
have to be present HERE to verify, and a verification key that can also MINT is a trust
root the engine — and therefore anything running in the engine's process — could use to
manufacture the very thing it is checking. With an asymmetric anchor, this module holds
what it takes to say YES OR NO and nothing it takes to say yes.

### Why there is no key parameter anywhere

§13.3 requires that "a caller cannot be it". A function that takes a public key has a
caller who selects the trust root, and a caller who selects the trust root can install
their own and mint approvals that verify. So the anchor is read from ONE place that is
not a parameter:

```text
APPROVAL_TRUST_ANCHOR_ENV     a deployment-level environment variable
```

Anyone who controls the deployed process controls that variable, and that is a fact
about deployments rather than a hole in this boundary — an in-process library cannot
defend its own address space. **Stated rather than implied:** the claim this module makes
is that no API PATH lets a caller choose the anchor, which is the level §13.3 is written
at ("a constructor, a factory, a default or any other path"). It does not claim to
survive an adversary who already controls the process. Nothing in-process could, and the
alternative — a separate authority process — is the daemon §16 forbids.

### What a caller may hand over, and what it may not

```text
MAY       a SignedApprovalArtifact, or the bytes of one
MAY NOT   a public key, a verifier, a trust store, a `trusted=True` flag,
          an already-"verified" value, or anything else that selects what is trusted
```

The engine re-verifies every artifact it is given. There is no way to hand it a verdict.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from workflows.approval import (
    ActorKind,
    ApprovalDecision,
    ApprovalScope,
    Denial,
    Provenance,
    SignedApprovalArtifact,
    WorkflowApproval,
)
from workflows.errors import InvalidRecord

__all__ = [
    "APPROVAL_TRUST_ANCHOR_ENV",
    "ApprovalRefused",
    "accept_approval",
    "designated_anchor",
    "ingress_is_designated",
    "verify_provenance",
]

#: The DEPLOYMENT's approval trust anchor: the Ed25519 public key, lowercase hex, that
#: this deployment accepts workflow approvals from. Read from the environment and from
#: nowhere else — see the module docstring for why this is not a parameter.
APPROVAL_TRUST_ANCHOR_ENV = "WORKBENCH_APPROVAL_TRUST_ANCHOR"

#: Ed25519 sizes, so a malformed value is refused as malformed rather than reaching the
#: library.
_PUBLIC_KEY_BYTES = 32
_SIGNATURE_BYTES = 64

#: §13.2. A scope digest is a SHA-256, lowercase hex.
_DIGEST_CHARS = 64


class ApprovalRefused(InvalidRecord):
    """§13.3, §13.4. Input that is NOT an answer: a refusal, not a decision.

    It is deliberately not `APPROVAL_DENIED`. A denial is a human saying no; this is
    input AI-13 will not accept as a human saying anything. Recording a forgery as a
    denial would turn it into a legitimate human decision in the ledger — which is the
    one place it must never reach.
    """

    reason_code = "APPROVAL_REFUSED"


def designated_anchor() -> str:
    """The deployment's designated verification anchor, lowercase hex.

    Reads `APPROVAL_TRUST_ANCHOR_ENV` and nothing else. There is deliberately no version
    of this function that takes the anchor as an argument: such a parameter is a
    caller-selected trust root, and a caller-selected trust root is a caller who can
    mint approvals that verify.

    A deployment with no anchor configured has NO valid ingress, and §13.3's fail-closed
    rule applies: every approval step stays BLOCKED, which is AI-04's own shape rather
    than a weaker one invented here.
    """
    value = os.environ.get(APPROVAL_TRUST_ANCHOR_ENV, "").strip()
    if not value:
        raise ApprovalRefused(
            "no approval trust anchor is designated for this deployment; without one no "
            "approval can be verified, and every approval step is BLOCKED (§13.3)"
        )
    if len(value) != _PUBLIC_KEY_BYTES * 2:
        raise ApprovalRefused(
            "the designated approval trust anchor is not a 32-byte Ed25519 public key "
            "in lowercase hex"
        )
    try:
        bytes.fromhex(value)
    except ValueError:
        raise ApprovalRefused(
            "the designated approval trust anchor is not hexadecimal"
        ) from None
    return value.lower()


def ingress_is_designated() -> bool:
    """Whether this deployment has a usable designated ingress at all.

    §13.3: "until AI-13-C designates an ingress and its provenance check, NO approval is
    valid, and every approval step is therefore BLOCKED."

    It answers by trying to read the anchor, so a deployment with a malformed anchor is
    "not designated" rather than "designated but broken" — both mean no approval can be
    verified, and §13.3's fail-closed shape does not distinguish them.

    A separate function from `designated_anchor` because the ENGINE asks this question
    while deciding whether a step can start, and raising there would be a refusal
    expressed as a crash rather than as a terminal state.
    """
    try:
        designated_anchor()
    except ApprovalRefused:
        return False
    return True


def _public_key(anchor: str) -> Ed25519PublicKey:
    try:
        return Ed25519PublicKey.from_public_bytes(bytes.fromhex(anchor))
    except ValueError:
        raise ApprovalRefused(
            "the designated approval trust anchor is not a usable Ed25519 public key"
        ) from None


def verify_provenance(artifact: SignedApprovalArtifact) -> Provenance:
    """§13.3. Machine-verify that `artifact` came from the DESIGNATED ingress.

    The check is over the SIGNATURE, never over what the artifact says about itself: an
    artifact that declares `actor_kind = HUMAN`, carries a well-formed timestamp and a
    valid-looking scope digest still fails here unless the bytes were signed by the
    holder of the designated key.

    ```
    FROZEN: a typed or mapping record whose only claim to humanity is `actor.type =
            human` MUST be REFUSED, however well-formed the rest of it is.
    ```
    """
    anchor = designated_anchor()
    key = _public_key(anchor)

    signature = artifact.signature
    if len(signature) != _SIGNATURE_BYTES * 2:
        raise ApprovalRefused(
            "the approval artifact's signature is not a 64-byte Ed25519 signature in "
            "hexadecimal; provenance is not a shape a record can claim (§13.3)"
        )
    try:
        raw = bytes.fromhex(signature)
    except ValueError:
        raise ApprovalRefused(
            "the approval artifact's signature is not hexadecimal (§13.3)"
        ) from None

    try:
        key.verify(raw, artifact.signed_bytes())
    except InvalidSignature:
        raise ApprovalRefused(
            "the approval artifact was not signed by the designated approval ingress; "
            "§13.3 accepts an approval only from the authority entitled to produce one"
        ) from None

    return Provenance(anchor_public_key=anchor, signature=signature.lower())


def accept_approval(
    *,
    artifact: SignedApprovalArtifact,
    scope: ApprovalScope,
    run_id: str,
) -> WorkflowApproval | Denial:
    """§13.2, §13.3, §13.3.1, §13.4. Everything that must be true before an answer counts.

    In order, because the order is the point:

    ```text
    1  PROVENANCE   the signature verifies against the designated anchor
    2  SCOPE        the artifact answers THIS scope, byte for byte
    3  ACTOR        the actor is HUMAN, and is not the run's own identity
    ```

    Step 3 is §13.3.1's NECESSARY AND NOT SUFFICIENT. On its own it proves a string. It
    is checked because the contract says to check it, and it means something only
    because step 1 already passed — a caller can write `actor_kind = HUMAN`, and cannot
    sign as the human's key.

    Refusals raise and record nothing. A verified `DENIED` returns a `Denial`, which is
    an ANSWER and ends the step (§13.4). Keeping those apart is what stops a forgery
    from being written into the ledger as a human decision.
    """
    provenance = verify_provenance(artifact)

    expected = scope.digest
    if artifact.scope_digest != expected:
        raise ApprovalRefused(
            "the approval artifact answers a different scope; §13.2 makes an approval "
            "bind to exactly six fields, and a digest that does not match is a "
            "different scope rather than a near miss"
        )

    if artifact.actor_kind is not ActorKind.HUMAN:
        raise ApprovalRefused(
            "the approval artifact's actor is not a human; §13.3.1 makes an Agent, a "
            "model and a service unable to approve"
        )
    if artifact.actor_reference == run_id:
        raise ApprovalRefused(
            "the approval artifact's actor is the run's own identity; §13.3.1 refuses "
            "an approval whose actor is the actor whose step is being approved"
        )

    if artifact.decision is ApprovalDecision.DENIED:
        return Denial(
            scope_digest=artifact.scope_digest,
            actor_reference=artifact.actor_reference,
            decided_at=artifact.decided_at,
            provenance=provenance,
        )

    return WorkflowApproval(
        scope_digest=artifact.scope_digest,
        actor_reference=artifact.actor_reference,
        decided_at=artifact.decided_at,
        artifact_reference=artifact.artifact_reference,
        provenance=provenance,
    )
