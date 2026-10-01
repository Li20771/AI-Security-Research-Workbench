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
step 14 (uniqueness)     HERE — admit_to_store, against the Store's written ids
step 7                   NOT IMPLEMENTED. It requires the published admission
                         rule set, which is C-1 and remains DEFERRED. Nothing
                         here invents one.
```

`admit()` stops at step 13 and stores nothing; `admit_to_store()` runs step 14
and persists. **Neither implements step 7**, so an `ACCEPTED` from either is not
a full §30 admission. That is a property of B2's staging, and it is said here
rather than left for a reader to infer from a green test.

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
from plugins.evidence.vocabulary import AdmissionOutcome

__all__ = [
    "AdmissionResult",
    "admit",
    "admit_to_store",
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


def admit(raw: object, *, clock=None) -> AdmissionResult:
    """Run the implemented admission boundary over a supplied record (§30).

    Composes, in order:

    ```text
    EvidenceRecord.from_mapping   §30 steps 1-4, 4b, 6, 8-13 (B1)
    check_workspace_agreement     §30 step 5's agreement half (§18.1)
    assign_digests                §30 step 12 (B1)
    ```

    Returns `ACCEPTED` with the digested record, or `REJECTED` with the
    `reason_code` of the rule that refused it. Nothing is stored either way —
    this function takes no store, and §30's "stores nothing" is satisfied
    trivially rather than claimed.

    The supplied mapping is never modified. `from_mapping` builds new frozen
    objects and `assign_digests` returns a copy, so no code path here writes to
    the caller's input.
    """
    try:
        record = EvidenceRecord.from_mapping(raw, clock=clock)
        check_workspace_agreement(record)
        record = assign_digests(record)
    except EvidenceError as exc:
        return AdmissionResult(
            outcome=AdmissionOutcome.REJECTED, reason_code=exc.reason_code
        )
    return AdmissionResult(outcome=AdmissionOutcome.ACCEPTED, record=record)


def admit_to_store(
    raw: object, *, store, clock=None
) -> AdmissionResult:
    """The §30 pipeline through persistence. `admit()`, then steps 14 and store.

    ```text
    admit(raw)                        §30 steps 1-13, unchanged
    store.contains(evidence_id)       §30 step 14
    store.write(record)               the write §30 exists to gate
    ```

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
    """
    result = admit(raw, clock=clock)
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
