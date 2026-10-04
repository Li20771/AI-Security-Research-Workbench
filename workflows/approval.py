"""AI-13 §13 — the workflow approval: its identity, its scope, and what one IS.

```text
FROZEN: AI-13 defines a WORKFLOW APPROVAL RECORD: an approval a HUMAN actor produced
        for one step of one run, recorded as workflow execution state.
FROZEN: it binds to (workflow_id, revision, definition_digest, run_id, step_id,
        attempt_no) through a scope digest. An approval that does not name all six is
        not an approval for anything and MUST be refused.
```

### The shape of the boundary, and why it is this shape

```text
SignedApprovalArtifact   UNTRUSTED. Produced outside; any caller may hand one over.
        |
        |  verify_provenance()   -- Ed25519, against the DESIGNATED anchor
        v
Provenance               a value that cannot be obtained without BOTH checks having run:
                         the signature verifies AND the anchor it names is the one THIS
                         DEPLOYMENT designated
        |
        v
WorkflowApproval         verified. Only ever produced BY the verification.
```

### The anchor is checked, not merely recorded

§13.3 accepts an approval only from the DESIGNATED authority, and that is a claim about
WHICH key, not merely about whether some key's arithmetic worked out. So `Provenance`
does both things in the one place the cryptography already lived: `__post_init__` asks
the module that decides which anchor applies (`ingress.py`, the single reader of that
deployment fact), refuses an anchor that is not it, and then verifies the signature
against it.

Order and dependency both matter. A self-consistent `Provenance(artifact, anchor)` is
constructible for ANY keypair a caller generates — it is a valid signature under SOME
key — and a `WorkflowApproval` built on one would be indistinguishable, field for field,
from a real acceptance. That is what the ledger path would then accept, which is the
whole of the bypass. Self-verification proves the signature; only the designation proves
the AUTHORITY, and a verifier that never asks which anchor it is checking against proves
nothing about who spoke.

**The engine never accepts a `WorkflowApproval` from a caller.** Its input is the
artifact, and it runs the verification itself, every time. That is what makes §13.3's
"a caller-authored record ... is NOT proof" structural rather than a rule someone has to
remember: there is no API that takes a record's word for anything.

### There is no `verified` field, and that is the point

§13.3: "The verification is over PROVENANCE, never over the fields a record carries."
A boolean named `verified` would be a FIELD — a label — and §13.3 refuses a label as the
thing it labels. So nothing here carries one. `Provenance` is a value whose only
constructor is called by the verifier, after a signature check passes; the proof that an
approval was verified is that it EXISTS.

### What is deliberately absent

```text
ApprovalPointId      the scope IS the identity. A second identity could drift from it,
                     and §13.2's whole value is that identity is mechanically comparable.
status / approved    a field saying so is a label (§13.3).
ApprovalRef          that is AI-04's type, and §13.5 says this is NOT it.
scope_digest in
  the artifact's      the scope is the SIX fields; the digest is a property OF them and
  preimage            travels alongside them, never inside (§13.2).
```
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from workflows.canonical import digest_of
from workflows.errors import InvalidRecord
from workflows.instants import is_instant
from workflows.references import reference

#: Ed25519 public-key size, so a malformed anchor is refused as malformed.
_PUBLIC_KEY_BYTES = 32

__all__ = [
    "ActorKind",
    "ApprovalDecision",
    "ApprovalReference",
    "ApprovalRequest",
    "ApprovalScope",
    "Denial",
    "Provenance",
    "SCOPE_DIGEST_FIELD",
    "SCOPE_FIELDS",
    "SignedApprovalArtifact",
    "WorkflowApproval",
]

#: §13.2. The preimage is EXACTLY these six, and the order here is documentation only —
#: §7.4 orders object keys by code point, so a writer's field order never reaches the
#: bytes.
SCOPE_FIELDS = (
    "workflow_id",
    "revision",
    "definition_digest",
    "run_id",
    "step_id",
    "attempt_no",
)

#: The one field §7.4 excludes when a scope digest is computed. It is NOT one of the six
#: and never enters the preimage; see `ApprovalScope.digest`.
SCOPE_DIGEST_FIELD = "scope_digest"

_ARTIFACT_KEYS = frozenset(
    {"decision", "actor_kind", "actor_reference", "decided_at", "artifact_reference",
     SCOPE_DIGEST_FIELD, "signature"}
)


class ActorKind(StrEnum):
    """§13.3.1. What the approver IS, as far as a field can say.

    ```text
    FROZEN: the approver is a HUMAN actor. An Agent MUST NOT approve and a model MUST
            NOT approve — not through a tool, not through a body, not by emitting a
            record that looks like one.
    FROZEN: those checks are NECESSARY AND NOT SUFFICIENT.
    ```

    `HUMAN` is the only member an approval may carry, and carrying it proves nothing on
    its own — §13.3 makes the field a LABEL. It is checked because the contract says to
    check it, and it is worth exactly what a label is worth until the signature behind
    it verifies.
    """

    HUMAN = "HUMAN"
    AGENT = "AGENT"
    MODEL = "MODEL"
    SERVICE = "SERVICE"


class ApprovalDecision(StrEnum):
    """§13.4. What the human ANSWERED.

    This lives on the untrusted artifact, never on the verified approval: an artifact
    saying DENIED is a claim until its signature verifies, and a `WorkflowApproval` with
    a `decision` field would be an object that could say "approved" about itself.
    """

    APPROVED = "APPROVED"
    DENIED = "DENIED"


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidRecord(f"{where} must be a non-empty string")
    return value


def _instant(value: object, where: str) -> str:
    if not is_instant(value):
        raise InvalidRecord(
            f"{where} must be an ISO-8601 UTC instant with second resolution and a "
            "trailing Z (§8.3)"
        )
    return value  # type: ignore[return-value]


def _designated_anchor() -> str:
    """The anchor THIS DEPLOYMENT designates, from the module that decides it.

    `ingress.py` reads the deployment fact — the one reader, and the one place that
    answers "which anchor applies" — and this is the verifying module ASKING that
    question rather than a second place answering it. The environment is not read here,
    and this module has no way to name an anchor of its own.

    Deferred, because `ingress` imports the types defined here: a module-level import
    would be a cycle, and every construction of a `Provenance` happens long after both
    modules are loaded. Failure to obtain an anchor (none configured, or malformed) is
    `ApprovalRefused`, which is an `InvalidRecord` — so a deployment with no designated
    ingress refuses provenance of every kind, which is §13.3's fail-closed shape.
    """
    from workflows.ingress import designated_anchor

    return designated_anchor()


@dataclass(frozen=True, slots=True)
class ApprovalScope:
    """§13.2. The six fields an approval binds to — its identity, and nothing else.

    There is no `ApprovalPointId`. The scope IS the identity, and §13.2 makes the
    identity mechanically comparable: change any one of the six and the digest changes,
    so "an old approval must not silently grant a new scope" is arithmetic rather than
    careful reading.
    """

    workflow_id: str
    revision: str
    definition_digest: str
    run_id: str
    step_id: str
    attempt_no: int

    def __post_init__(self) -> None:
        for name in ("workflow_id", "revision", "definition_digest", "run_id", "step_id"):
            _text(getattr(self, name), f"scope.{name}")
        if isinstance(self.attempt_no, bool) or not isinstance(self.attempt_no, int):
            raise InvalidRecord("scope.attempt_no must be an integer (§6.3)")
        if self.attempt_no < 1:
            raise InvalidRecord(
                "scope.attempt_no must be >= 1; §6.3 starts an attempt count at 1"
            )

    def to_body(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in SCOPE_FIELDS}

    @property
    def digest(self) -> str:
        """§13.2. SHA-256 over §7.4's canonical JSON of EXACTLY the six fields.

        §7.4's preimage rule is "the record's fields EXCLUDING the record's own digest
        field", and a scope has no digest field of its own — so the exclusion has nothing
        to exclude. The scope digest is computed through a synthetic key named after the
        field, which satisfies the encoder's precondition and then never reaches the
        bytes. The preimage is the six fields and nothing else.

        The alternative — a second canonicaliser that skips the exclusion — would be a
        second definition of §7.4, and §7.4 is frozen precisely so that two of them
        cannot drift.
        """
        return digest_of(
            {**self.to_body(), SCOPE_DIGEST_FIELD: ""}, digest_field=SCOPE_DIGEST_FIELD
        )


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """engine → the designated ingress. What is being asked, and by when.

    It carries NO authority: holding one is not permission for anything, and it is not
    an approval. §13.4's "re-asking a human who has answered is pressure" implies a
    request exists as a thing that can be answered; this is it.

    It is NOT durable. §15.2 records approvals on the run ledger; a request that was
    never answered is a fact about a wait, not about what the run did.
    """

    scope: ApprovalScope
    approval_deadline: str

    def __post_init__(self) -> None:
        _instant(self.approval_deadline, "request.approval_deadline")

    @property
    def scope_digest(self) -> str:
        return self.scope.digest


@dataclass(frozen=True, slots=True)
class Provenance:
    """§13.3. Proof that an artifact was verified against the DESIGNATED anchor.

    IT VERIFIES ITSELF, AGAINST THE DEPLOYMENT'S ANCHOR. `__post_init__` asks the one
    module that decides which anchor applies, refuses any anchor that is not it, and only
    then runs the Ed25519 check over the artifact's signed bytes. So **a `Provenance`
    that does not verify, or that names an anchor this deployment did not designate,
    cannot be constructed** — by any caller, through any constructor path, including a
    hand-written dataclass call. (Reflection past a constructor is the
    adversary-who-controls-the-process case the ingress module documents as out of scope
    for every type in this phase, this one and `RunRecord` alike.)

    Both checks are required and they are not the same check. The signature check proves
    the holder of `anchor_public_key`'s private key signed these bytes; alone it is a
    signature under SOME key, and a caller who generates a keypair satisfies it for free.
    The designation check is what makes that key THE key — the difference between "a
    valid signature" and "the designated authority's signature", which is the only thing
    §13.3 accepts.

    That is deliberately stronger than "the constructor is private". A private
    constructor is a rule someone has to keep, and in this language anyone can reach past
    one; a check that IS the constructor has nothing to reach past. It is what lets the
    approval ledger insist on a VERIFIED VALUE rather than on a flag — and a flag is the
    one thing §13.3 refuses outright.

    There is no `verified=True` anywhere in this phase. A boolean saying so is a LABEL,
    and this type is instead the thing the label would have been about.
    """

    #: The signed artifact this rests on — the material, kept so the check can be run.
    artifact: SignedApprovalArtifact
    #: The anchor it verified against, lowercase hex. It must be the one THIS DEPLOYMENT
    #: designated — a caller may name the authority, and may not choose it.
    anchor_public_key: str

    def __post_init__(self) -> None:
        anchor = self.anchor_public_key
        if not isinstance(anchor, str) or len(anchor) != _PUBLIC_KEY_BYTES * 2:
            raise InvalidRecord(
                "provenance.anchor_public_key must be a 32-byte Ed25519 public key in "
                "lowercase hexadecimal"
            )
        try:
            key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(anchor))
            signature = bytes.fromhex(self.artifact.signature)
        except ValueError:
            raise InvalidRecord(
                "a provenance names an anchor and a signature that are not both "
                "hexadecimal key material"
            ) from None

        # §13.3. THE DESIGNATED-ANCHOR BINDING. Everything above is shape; this is
        # AUTHORITY. Without it the two checks below would verify a signature under a key
        # the CALLER chose, and a caller with a keypair can produce one of those for any
        # artifact they like — so the value would be self-consistent rather than
        # designated, and the ledger that insists on one would be insisting on nothing.
        # The question is asked of the one module entitled to answer it; this module
        # never reads the deployment fact itself.
        if anchor != _designated_anchor():
            raise InvalidRecord(
                "a provenance names an anchor this deployment did not designate; §13.3 "
                "accepts an approval only from the DESIGNATED ingress, and a signature "
                "that verifies under a key the caller selected is a signature under SOME "
                "key rather than provenance"
            )

        try:
            key.verify(signature, self.artifact.signed_bytes())
        except InvalidSignature:
            raise InvalidRecord(
                "a provenance whose signature does not verify against the anchor it "
                "names cannot exist; §13.3 accepts an approval only from the authority "
                "entitled to produce one, and a value that merely CLAIMS to be from it "
                "is the record §13.3 refuses, however well formed the rest of it is"
            ) from None

    @property
    def signature(self) -> str:
        """The signature that verified, lowercase hex."""
        return self.artifact.signature


@dataclass(frozen=True, slots=True)
class SignedApprovalArtifact:
    """The UNTRUSTED input: a human act, signed, produced outside the engine.

    Any caller may hand one of these over. Nothing in it is believed — every field is
    either checked against the run (`scope_digest`) or covered by the signature that
    `verify_provenance` checks against the designated anchor.

    ```text
    decision            what the human answered (§13.4)
    actor_kind          HUMAN/AGENT/MODEL/SERVICE — a NECESSARY check (§13.3.1)
    actor_reference     who, as a declared reference (§13.1)
    decided_at          when, as a §8.3 instant
    artifact_reference  whatever the human actually signed; its BYTES stay outside
                        every record AI-13 writes (§7.2, §13.1)
    scope_digest        the six-field scope this answers
    signature           Ed25519 over the canonical body of THIS object, signature
                        excluded — §7.4's rule, so there is one canonical form here too
    ```

    The signature covers every field above it, which is what makes the artifact's own
    `decision` and `actor_kind` mean anything: change one byte and the signature stops
    verifying.
    """

    decision: ApprovalDecision
    actor_kind: ActorKind
    actor_reference: str
    decided_at: str
    artifact_reference: str
    scope_digest: str
    signature: str

    def __post_init__(self) -> None:
        for name in ("decision", "actor_kind"):
            value = getattr(self, name)
            if not isinstance(value, (ApprovalDecision, ActorKind)):
                raise InvalidRecord(f"artifact.{name} must be a declared member")
        reference(self.actor_reference, "artifact.actor_reference")
        # §7.2. The same rule AI-13-B's `ArtifactRef.reference` uses, because it is the
        # same kind of field: a pointer to bytes stored OUTSIDE, whose shape this phase
        # does not own. Two rules for one idea is how two implementations come to
        # disagree about what an artifact reference is.
        _text(self.artifact_reference, "artifact.artifact_reference")
        _instant(self.decided_at, "artifact.decided_at")
        digest = self.scope_digest
        if not isinstance(digest, str) or not digest:
            raise InvalidRecord("artifact.scope_digest must be a non-empty hex string")
        if not isinstance(self.signature, str) or not self.signature:
            raise InvalidRecord("artifact.signature must be a non-empty hex string")

    @classmethod
    def from_mapping(cls, raw: object) -> "SignedApprovalArtifact":
        if not isinstance(raw, Mapping):
            raise InvalidRecord("an approval artifact must be an object")
        unknown = set(map(str, raw)) - _ARTIFACT_KEYS
        if unknown:
            raise InvalidRecord(
                "the approval artifact has field(s) the contract does not define: "
                f"{', '.join(sorted(map(str, unknown)))}"
            )

        def member(name: str, enum: type[StrEnum]) -> Any:
            try:
                return enum(raw.get(name))
            except ValueError:
                raise InvalidRecord(
                    f"artifact.{name} is not one of {', '.join(m.value for m in enum)}"
                ) from None

        return cls(
            decision=member("decision", ApprovalDecision),
            actor_kind=member("actor_kind", ActorKind),
            actor_reference=_text(raw.get("actor_reference"), "artifact.actor_reference"),
            decided_at=_instant(raw.get("decided_at"), "artifact.decided_at"),
            artifact_reference=_text(
                raw.get("artifact_reference"), "artifact.artifact_reference"
            ),
            scope_digest=_text(raw.get("scope_digest"), "artifact.scope_digest"),
            signature=_text(raw.get("signature"), "artifact.signature"),
        )

    def to_body(self) -> dict[str, Any]:
        """Everything the signature covers, with the signature field excluded (§7.4)."""
        return {
            "decision": str(self.decision),
            "actor_kind": str(self.actor_kind),
            "actor_reference": self.actor_reference,
            "decided_at": self.decided_at,
            "artifact_reference": self.artifact_reference,
            SCOPE_DIGEST_FIELD: self.scope_digest,
        }

    def signed_bytes(self) -> bytes:
        """The exact bytes an issuer signs and a verifier checks.

        §7.4's canonical form with the signature excluded, so an artifact has ONE byte
        form: a second encoder here would be a second thing to agree about.
        """
        from workflows.canonical import canonical_body

        return canonical_body(
            {**self.to_body(), "signature": self.signature}, digest_field="signature"
        )


@dataclass(frozen=True, slots=True)
class WorkflowApproval:
    """§13.1. An approval a human produced, whose provenance HAS BEEN verified.

    There is no `status`, no `approved`, no `verified` — see the module docstring. This
    type is produced by the verification and by nothing else, and the engine re-runs
    that verification on every artifact it is handed rather than accepting one of these
    from a caller.

    It is not an AI-04 `ApprovalRef` and must never be presented as one (§13.5).
    """

    scope_digest: str
    actor_reference: str
    decided_at: str
    artifact_reference: str
    provenance: Provenance

    def __post_init__(self) -> None:
        reference(self.actor_reference, "approval.actor_reference")
        _text(self.artifact_reference, "approval.artifact_reference")
        _instant(self.decided_at, "approval.decided_at")
        digest = self.scope_digest
        if not isinstance(digest, str) or not digest:
            raise InvalidRecord("approval.scope_digest must be a non-empty hex string")
        if not isinstance(self.provenance, Provenance):
            raise InvalidRecord(
                "a workflow approval carries the provenance it was accepted on; an "
                "approval without one is a record whose only claim is its own fields "
                "(§13.3)"
            )


@dataclass(frozen=True, slots=True)
class Denial:
    """§13.4. A human ANSWERED NO, and the answer itself verified.

    Distinct from a refusal: a refusal is input AI-13 would not accept as an answer at
    all, and it changes no state. A denial is an answer, and it ends the step.
    """

    scope_digest: str
    actor_reference: str
    decided_at: str
    provenance: Provenance

    def __post_init__(self) -> None:
        reference(self.actor_reference, "denial.actor_reference")
        _instant(self.decided_at, "denial.decided_at")


@dataclass(frozen=True, slots=True)
class ApprovalReference:
    """§15.2. What the RUN RECORD keeps about an accepted approval.

    ```text
    FROZEN: every approval: its scope_digest and its artifact reference.
    FROZEN: a run record MUST be sufficient for a reader to answer "... and who
            authorized it" WITHOUT asking the component that ran it.
    ```

    The first clause names two fields; the second demands the actor. Both are here, plus
    the two run-local parts of the scope (`step_id`, `attempt_no`) so that a record can
    CHECK that the digest belongs to it rather than taking it on trust: with those two
    and the run's own identity, the scope digest is recomputable — which is what makes
    "an approval from run A stored on run B" refusable.

    The artifact's BYTES are not here and never will be (§7.2), and neither is the
    provenance: it is the thing that made acceptance possible, and a stored proof is a
    thing that invites reuse. A reader who needs it follows the artifact reference.
    """

    step_id: str
    attempt_no: int
    scope_digest: str
    artifact_reference: str
    actor_reference: str
    decided_at: str

    def __post_init__(self) -> None:
        _text(self.step_id, "approval_reference.step_id")
        if isinstance(self.attempt_no, bool) or not isinstance(self.attempt_no, int):
            raise InvalidRecord("approval_reference.attempt_no must be an integer")
        if self.attempt_no < 1:
            raise InvalidRecord("approval_reference.attempt_no must be >= 1")
        if not isinstance(self.scope_digest, str) or not self.scope_digest:
            raise InvalidRecord("approval_reference.scope_digest must be non-empty")
        _text(self.artifact_reference, "approval_reference.artifact_reference")
        reference(self.actor_reference, "approval_reference.actor_reference")
        _instant(self.decided_at, "approval_reference.decided_at")

    def to_body(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "attempt_no": self.attempt_no,
            SCOPE_DIGEST_FIELD: self.scope_digest,
            "artifact_reference": self.artifact_reference,
            "actor_reference": self.actor_reference,
            "decided_at": self.decided_at,
        }
