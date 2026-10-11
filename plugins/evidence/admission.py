"""The admission boundary — §30, composed onto B1.

AI-05-B1 owns every *field* rule: shape, `schema_version`, required fields, the
closed vocabularies, the §14.9 grammars, the §6.5 registry, the §6.6 cross-field
rules and both digests. **None of that is restated here.** This module adds the
one admission condition B1 does not hold — §18.1 workspace agreement — and
converts B1's exceptions into a §22.1 outcome.

### What this module implements, stated as §30 steps

```text
steps 1-4, 4b, 6, 8-13   B1, reached through EvidenceRecord.from_mapping and
                         assign_digests. Composed, not reimplemented.
step 5 (agreement half)  HERE — check_workspace_agreement
step 7 (rule set)        HERE — check_admission_rules, against §14.10
step 14 (uniqueness)     HERE — admit_to_store, against the Store's written ids
```

`admit()` runs steps 1-13 and stores nothing; `admit_to_store()` runs step 14 and
persists. Both run the whole pipeline, step 7 included.

### Why step 7 runs FIRST, before step 1 constructs the record

§30 numbers the steps, and step 7 is numbered after step 1. The order below is the
one the contract requires anyway, and the amendment that published the rule set
(§14.10, Amendment 3) records why:

```text
EvidenceRecord.from_mapping derives references.context[].value_digest from the
supplied `value` (§12.1). §14.6 R2 forbids computing a digest over a value that
was not admitted, and says so directly: rule-tripping content "is rejected before
hashing".
```

So the rule check reads the SUPPLIED values, while the context value is still a
string, and it therefore precedes construction. The one observable consequence is
which reason a record violating BOTH a shape rule and a published rule reports: it
reports the RULE. Both outcomes are `REJECTED`, nothing is stored, and no accepted
value, bound, digest or stored record differs by which reason comes first.

### What step 7 does not do

It does not sanitize, substitute, truncate or repair: §14.10 published a DETECTION
rule set and AI-05 holds no replacement for any rule (§14.4.1). It does not touch
Class 1 or Class 2 fields — a Class 1 digest or revision is a 32+ character run and
C1-R06 matches exactly that, so scanning one would reject every legitimate record.
And it is not retroactive: a record already written stays readable, and no
stored-form load re-runs admission over it (§14.10, §17).

### §18.1, mapped onto the record that actually exists

§18.1 lists seven agreement rows. The AI-05 record has fields for two of them,
and the other five are either the same field or have no counterpart:

```text
evidence.workspace_id    provenance.workspace_id — the record's own scope
producer.workspace_id    the same field. AI-05 has one workspace per record;
                         there is no second producer workspace to compare
source.workspace_id      WorkspaceBinding carries kind, identity and revision
                         and no workspace_id, so there is nothing to compare
context.workspace_id     references.context[].workspace_id   <- COMPARED HERE
guard.workspace_id       not a record field
experiment.workspace     experiment_id is a correlation identifier, not a scope
artifact.workspace       artifacts.items[].owner_workspace_id <- COMPARED HERE
```

The two comparisons that exist are the two that run. The other five are not
skipped out of convenience: they have no second value to disagree with, and
inventing a field to compare would be a schema change (contract §34.1).

### No filtering — the reason this is a rejection and not a cleanup

§18.3 records why: AI-04's contract said "never merged, filtered, or repaired"
for its whole frozen life and the implementation filtered anyway, so an
unconditional `ALLOW` rule succeeded on a request spanning two workspaces.

So a foreign item is **never dropped**. The record is rejected whole, and the
supplied mapping is not modified — there is no code path here that removes,
rewrites or repairs an element. `references.context` and `artifacts.items` are
read and compared; nothing is written back.
"""

from __future__ import annotations

from dataclasses import dataclass

from plugins.evidence.digests import assign_digests
from plugins.evidence.errors import (
    DuplicateEvidenceId,
    EvidenceError,
    WorkspaceAgreementViolation,
)
from plugins.evidence.models import EvidenceRecord
from plugins.evidence.producer_auth import authenticate
from plugins.evidence.rules import check_admission_rules
from plugins.evidence.vocabulary import AdmissionOutcome

__all__ = [
    "AdmissionResult",
    "admit",
    "admit_to_store",
    "check_admission_rules",
    "check_workspace_agreement",
]


def check_workspace_agreement(record: EvidenceRecord) -> None:
    """Every §18.1 agreement rule the AI-05 record can express.

    Raises `WorkspaceAgreementViolation` for the first disagreement found, or
    returns `None`. It reads only; it never writes to the record, and it never
    removes the item it objected to.

    Failure messages name the field path and the rule, and **never the supplied
    workspace value** — an error message is a place a value escapes to a log
    (`errors.py`), and §18.1 is a rule about identity, not a lookup service.
    """
    scope = record.provenance.workspace_id

    for index, ref in enumerate(record.references.context):
        if ref.workspace_id != scope:
            raise WorkspaceAgreementViolation(
                f"references.context[{index}].workspace_id does not agree with "
                "the record's workspace_id (§18.1). A record is scoped to "
                "exactly one workspace, and a foreign item is REJECTED whole — "
                "never filtered out, and never repaired to the record's scope"
            )

    for index, item in enumerate(record.artifacts.items):
        if item.external:
            # §18.1 exempts an artifact explicitly marked external with an owner,
            # and §18.4 states why that is not a second scope: it is a DECLARED
            # EXTERNAL DEPENDENCY carrying its owner. §13.6 has already required
            # the owner to be present and well-formed, so there is no equality
            # left to enforce here.
            continue
        if item.owner_workspace_id is not None and item.owner_workspace_id != scope:
            raise WorkspaceAgreementViolation(
                f"artifacts.items[{index}].owner_workspace_id does not agree "
                "with the record's workspace_id (§18.1). The §18.1 exemption "
                "covers only an artifact explicitly marked external with an "
                "owner; an internal artifact naming a foreign workspace is "
                "REJECTED"
            )


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    """The outcome of one admission attempt (§22.1).

    A `REJECTED` decision is a value, not an exception — `errors.py` states why:
    §22.1 defines three outcomes and an exception type is not one of them. The
    exceptions are the *reason*, and `reason_code` carries that reason across
    the boundary without prose parsing.

    `UNAVAILABLE` is producible only by `admit_to_store`, and only for a write
    failure. §22.3 separates INCOMPLETE CONTENT from WRITE FAILURE: the first is
    `REJECTED` and the caller is told which requirement failed, the second is
    `UNAVAILABLE` and the caller is told the write did not happen. `admit()`
    cannot produce it, because it touches no store.
    """

    outcome: AdmissionOutcome
    #: The `reason_code` of the `EvidenceError` that rejected the record, or
    #: `None` when accepted. Never a message and never a supplied value.
    reason_code: str | None = None
    #: The admitted record, carrying both digests. `None` when rejected, and
    #: `None` when `UNAVAILABLE` — nothing was stored, and §22.3 puts the
    #: failure in the return value rather than in a record.
    record: EvidenceRecord | None = None

    @property
    def accepted(self) -> bool:
        return self.outcome is AdmissionOutcome.ACCEPTED


def admit(raw: object, *, producer_proof=None, clock=None) -> AdmissionResult:
    """Run the implemented admission boundary over a supplied record (§30).

    Composes, in order:

    ```text
    check_admission_rules         §30 step 7 (§14.10) — over the SUPPLIED values,
                                  before construction hashes the context value
    authenticate                  §30 step 7b (§7.3, Amendment 5) — the producer
                                  claim, before any typed record exists
    EvidenceRecord.from_mapping   §30 steps 1-4, 4b, 6, 8-13 (B1)
    check_workspace_agreement     §30 step 5's agreement half (§18.1)
    assign_digests                §30 step 12 (B1)
    ```

    Returns `ACCEPTED` with the digested record, or `REJECTED` with the
    `reason_code` of the rule that refused it. Nothing is stored either way —
    this function takes no store, and §30's "stores nothing" is satisfied
    trivially rather than claimed.

    `producer_proof` is REQUIRED in the sense §7.3.3 means: omitting it, or
    passing `None`, is REJECTED with `AUTHENTICATION_PROOF_MISSING` rather than
    a `TypeError`. It is carried BESIDE the mapping and never becomes a field of
    the record — §7.3.3 makes the proof not part of the record, so no digest
    input, no stored form and no schema changes because of it.

    The submitted mapping is the signer's input: §7.3.4's signed input is the
    canonical serialization of the COMPLETE SUPPLIED MAPPING, so authentication
    must run on what the caller supplied and not on a parsed record. That is
    also why step 7b runs BEFORE construction — no typed record, and therefore
    no Evidence digest, may be derived from a claim that is not authenticated
    (§7.3.7).

    The supplied mapping is never modified. `from_mapping` builds new frozen
    objects, `check_admission_rules` only reads, `authenticate` only reads, and
    `assign_digests` returns a copy, so no code path here writes to the caller's
    input.
    """
    try:
        check_admission_rules(raw)
        authenticate(raw, producer_proof)
        record = EvidenceRecord.from_mapping(raw, clock=clock)
        check_workspace_agreement(record)
        record = assign_digests(record)
    except EvidenceError as exc:
        return AdmissionResult(
            outcome=AdmissionOutcome.REJECTED, reason_code=exc.reason_code
        )
    return AdmissionResult(outcome=AdmissionOutcome.ACCEPTED, record=record)


def admit_to_store(
    raw: object, *, store, producer_proof=None, clock=None
) -> AdmissionResult:
    """The §30 pipeline through persistence. `admit()`, then steps 14 and store.

    ```text
    admit(raw, producer_proof=...)    §30 steps 1-13, authentication included
    store.contains(evidence_id)       §30 step 14
    store.write(record)               the write §30 exists to gate
    ```

    **The proof is passed THROUGH to `admit()` rather than verified a second
    time** (§7.3.3): one verification runs and one verdict is reached. A
    non-ACCEPTED result returns before the store is touched, so an
    authentication failure never contacts storage (§7.3.8).

    A duplicate `evidence_id` is `REJECTED` with
    `DUPLICATE_EVIDENCE_ID` and **the existing record is untouched**: the
    collision is detected before the write and enforced again by the Store, so
    there is no path on which a new record replaces an old one and is then
    reported as a failure.

    A duplicate `content_digest` is not a conflict. Two records making the same
    claim are two events (§8.2), they carry different `evidence_id`s and
    different `record_digest`s, and both are stored. `content_digest` is not a
    key of this store and is never used as one.

    A write that fails for a reason other than collision is `UNAVAILABLE` with
    `STORAGE_FAILURE` (§22.2, §22.3): the record was valid and storage did not
    complete. Nothing is stored, and no record describing the failure is
    written — the failure belongs in the return value.

    The rule that a duplicate identity is refused is admission's (D8). The
    Store supplies only the detection: `contains`, and a write that cannot
    overwrite. Neither module holds both halves.

    **Admission targets the staged tier, and only the staged tier.** A promoted
    store has no `write` at all, and this function refuses a store without one
    rather than letting the absence surface as an `AttributeError`:

    ```text
    TypeError   the store cannot accept a record, so it is not a staged store
    ```

    Without that refusal this function would itself be a programmatic promotion
    path — `admit_to_store(raw, store=promoted)` would store an ordinarily
    admitted record in the durable tier, and no `promote()` method would be
    needed to reach it. §20.3 makes promotion a human act, so the refusal is the
    boundary rather than a courtesy.
    """
    if not callable(getattr(store, "write", None)):
        raise TypeError(
            "admit_to_store persists a newly admitted record, so it requires a "
            "store that accepts one — a staged store. The store given has no "
            "write operation, which is what a promoted store is: promotion is a "
            "human act that copies the bytes of a staged record to a new "
            "location (§20.3), and AI-05 has no operation that puts a record "
            "there"
        )

    result = admit(raw, producer_proof=producer_proof, clock=clock)
    if result.outcome is not AdmissionOutcome.ACCEPTED:
        return result

    record = result.record
    try:
        if store.contains(record.evidence_id):
            return AdmissionResult(
                outcome=AdmissionOutcome.REJECTED,
                reason_code=DuplicateEvidenceId.reason_code,
            )
        store.write(record)
    except DuplicateEvidenceId as exc:
        return AdmissionResult(
            outcome=AdmissionOutcome.REJECTED, reason_code=exc.reason_code
        )
    except OSError:
        return AdmissionResult(
            outcome=AdmissionOutcome.UNAVAILABLE, reason_code="STORAGE_FAILURE"
        )
    return result
