"""The filesystem Store — durable storage for admitted records.

Implements the storage decisions frozen in `docs/AI-05-B2_DECISIONS_2026-10-01.md`:

```text
D2  filesystem        no SQLite, no YAML database, no JSONL log, no third party
D3  UTF-8 JSON        one EvidenceRecord per file, <evidence_id>.json
D4  two directories   evidence/staged/ (gitignored) · evidence/promoted/ (tracked)
```

### The two tiers are two types, not one type with a flag

```text
StagedEvidenceStore     write · read · contains · list_ids · discard
PromotedEvidenceStore   read · contains · list_ids · discard (refused)
```

**A promoted store has no `write`.** That is the whole of D9's promotion rule
expressed where it cannot be argued with: §20.3 makes promotion a human act —
same `evidence_id`, same `content_digest`, same `record_digest`, same bytes, a
new location and nothing else — so there is no operation by which AI-05 adds a
record to the promoted tier. A `write` that existed only to raise would still be
a method a caller could reach, catch and route around; an absent one is not.

This matters because the previous shape had exactly that hole. A single
`EvidenceStore(root, tier=PROMOTED)` accepted `write`, so
`admit_to_store(raw, store=promoted)` stored an ordinarily-admitted record
directly into the promoted tier — a programmatic promotion path that no
`promote()` method was needed to reach. The absence of a promotion API is not
evidence that promotion is impossible; the store accepting an unearned record
is evidence that it is not.

### Why `discard` is still present, and still refuses

`discard` is defined for both tiers and raises `PromotedRecordNotDiscardable`
on the promoted one. That asymmetry with `write` is deliberate:

```text
discard  §19.2 makes it a TIER-CONDITIONAL operation. "staged may be
         discarded; promoted MUST NOT be deleted" is one rule with two
         outcomes, so the operation exists and its legality depends on the
         tier. Naming the refusal is how the prohibition is stated.
write    is not tier-conditional. Creating a record is what the staged tier is
         for; the promoted tier receives records by human publication, which
         is not an AI-05 operation at all. There is nothing for a promoted
         `write` to do except refuse, and a method that exists only to refuse
         is a signpost rather than a boundary.
```

### What the Store is, and the four things it is not

```text
IT IS      a byte pipe for an already-built stored form.
           EvidenceRecord -> to_stored_mapping() -> UTF-8 JSON -> one file
IT IS NOT  a digest calculator      it never calls content_digest or
                                    record_digest, and it does not verify on
                                    write. Admission computed those (§30 step
                                    12) before this module saw the record.
IT IS NOT  a canonicalizer          it writes the mapping it is handed, in the
                                    order it is handed. §15 canonicalization is
                                    B1's and happened earlier.
IT IS NOT  a repairer               nothing here rewrites, normalizes or fixes a
                                    value, and no method returns a corrected
                                    record.
IT IS NOT  an admission authority   it reports a collision; the DECISION that a
                                    duplicate evidence_id is REJECTED is
                                    admission's (D8), and `admit_to_store` in
                                    `admission.py` is where the two meet.
```

### The root is a parameter

Neither type discovers a path. Each is constructed with a root directory, so
tests point it at a temporary directory and nothing here needs to know where the
repository is.

### Writing is atomic and never overwrites

A record is written to a temporary name in the same directory, flushed and
fsynced, then **linked** into place. `os.link` is atomic and fails if the
target exists, which gives two properties at once:

```text
no partial file is ever visible under the record's real name
an existing record is never silently replaced — a collision is an error,
  which is what makes §30 step 14 checkable at the filesystem boundary
```

The temporary name does not end in `.json`, so an interrupted write cannot be
mistaken for a record by `list_ids`.

### The Python surface here is provisional

D11 leaves four things undefined: the retrieval return shape, the `superseded_by`
query shape, the promotion API, and discard cleanup granularity. These types
provide the minimum the frozen decisions need and **do not freeze them**. `read`
returning an `EvidenceRecord` and `list_ids` returning a tuple of ids are
implementation choices, not contract surface, and they may change when D11 is
resolved. There is deliberately **no promotion method on either type**.
"""

from __future__ import annotations

import json
import os
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from plugins.evidence.errors import (
    DuplicateEvidenceId,
    PromotedRecordNotDiscardable,
    RecordNotFound,
    StoredBytesUnreadable,
)
from plugins.evidence.grammar import g_evidence_id
from plugins.evidence.models import EvidenceRecord
from plugins.evidence.stored import load_stored

__all__ = [
    "EvidenceTier",
    "PromotedEvidenceStore",
    "StagedEvidenceStore",
]

#: The suffix a stored record carries. `list_ids` matches on this, so a
#: temporary file from an interrupted write is not mistaken for a record.
SUFFIX = ".json"


class EvidenceTier(StrEnum):
    """The two durability tiers (§20.1).

    Not a lifecycle state — §20 separates *immutability* from *durability*, and
    these name the second one. Both tiers hold immutable records; only the
    staged tier's existence is not guaranteed.
    """

    STAGED = "staged"
    PROMOTED = "promoted"


class _EvidenceDirectory:
    """The surface both tiers share. Not exported, and not constructible as a tier.

    It holds the read path and the path rule. `write` is deliberately **not**
    here: it belongs to the tier that may receive records, and putting it on a
    common base is what produced a promoted store that accepted one.
    """

    #: Overridden by each tier; used for messages and for §19.2's rule.
    tier: EvidenceTier

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def _path(self, evidence_id: object) -> Path:
        """The one file this `evidence_id` may name.

        The id is validated with the contract's own `G-EVIDENCE-ID` before it
        touches a path. That is not decoration: the grammar is
        `^ev-[0-9a-f]{16}$`, so a value containing a separator, a drive letter
        or `..` is refused here rather than being joined into a path. Without
        this, `read("../../etc/passwd")` would be a traversal.
        """
        return self._root / (g_evidence_id(evidence_id, "evidence_id") + SUFFIX)

    # ------------------------------------------------------------------
    # read
    # ------------------------------------------------------------------

    def read(self, evidence_id: object) -> EvidenceRecord:
        """Read one record back, verified.

        The bytes are decoded and handed to `stored.load_stored`, which re-runs
        every B1 rule, the §18.1 workspace rule and both digest comparisons. A
        stored file whose digests do not describe it raises
        `StoredIntegrityFailure` rather than being returned.
        """
        path = self._path(evidence_id)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise RecordNotFound(
                f"no record is stored under this evidence_id in the "
                f"{self.tier} tier"
            ) from None
        return self._decode(raw)

    @staticmethod
    def _decode(raw: bytes) -> EvidenceRecord:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise StoredBytesUnreadable(
                "the stored file is not valid UTF-8, so no record can be read "
                "from it"
            ) from None
        try:
            mapping = json.loads(text)
        except json.JSONDecodeError:
            raise StoredBytesUnreadable(
                "the stored file is not valid JSON, so no record can be read "
                "from it"
            ) from None
        return load_stored(mapping)

    def contains(self, evidence_id: object) -> bool:
        """Whether a record with this id is already written.

        The mechanism the uniqueness rule needs (D8). What to do about a `True`
        is admission's decision, not this module's.
        """
        return self._path(evidence_id).is_file()

    def list_ids(self) -> tuple[str, ...]:
        """Every stored `evidence_id`, sorted.

        Provisional: D11 leaves the query surface undefined, and this is the
        minimum the tier needs. Only `*.json` is considered, so a temporary file
        left by an interrupted write is not listed as a record.
        """
        if not self._root.is_dir():
            return ()
        return tuple(sorted(path.stem for path in self._root.glob(f"*{SUFFIX}")))

    # ------------------------------------------------------------------
    # discard
    # ------------------------------------------------------------------

    def discard(self, evidence_id: object) -> None:
        """Remove one whole staged record. Refused on the promoted tier.

        §20.2: `discard` removes a record from a NON-durable tier, all or
        nothing, and is permitted only because that record's existence was
        never guaranteed. A promoted record's existence was guaranteed, so
        removing one is `delete`, which is forbidden unconditionally.

        There is no partial discard and no per-field removal: the operation
        removes a file or it raises.
        """
        if self.tier is not EvidenceTier.STAGED:
            raise PromotedRecordNotDiscardable(
                "discard is a staged-tier operation (§19.2, §20.2). A promoted "
                "record's existence was guaranteed, so AI-05 has no operation "
                "that removes one"
            )
        path = self._path(evidence_id)
        try:
            path.unlink()
        except FileNotFoundError:
            raise RecordNotFound(
                "no record is stored under this evidence_id in the staged tier"
            ) from None


class StagedEvidenceStore(_EvidenceDirectory):
    """The tier that receives records, and the only one that does.

    A record reaches this tier by admission (§30) and leaves it by `discard`.
    Nothing promotes out of it automatically: a human copies the bytes.
    """

    tier = EvidenceTier.STAGED

    def write(self, record: EvidenceRecord) -> None:
        """Persist one admitted record. Raises `DuplicateEvidenceId` on collision.

        Refuses a record that carries no digests: such a record is not one
        AI-05 has written (§30 step 12 has not run), so storing it would create
        a file that `load_stored` can never read back.

        The bytes written are exactly `to_stored_mapping()` encoded as UTF-8
        JSON. Nothing is added, reordered or recomputed.
        """
        if record.integrity.content_digest is None or record.integrity.record_digest is None:
            raise StoredBytesUnreadable(
                "this record carries no digests, so it is not one AI-05 has "
                "written (§30 step 12). Storing it would create a file that "
                "cannot be read back; assign its digests first"
            )

        path = self._path(record.evidence_id)
        payload = json.dumps(
            record.to_stored_mapping(), ensure_ascii=False, indent=2
        ).encode("utf-8")

        self._root.mkdir(parents=True, exist_ok=True)
        # Same directory as the target, so the link below cannot cross a
        # filesystem boundary. The name does not end in `.json`.
        temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid4().hex[:8]}")

        handle = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                raise DuplicateEvidenceId(
                    "a record with this evidence_id is already stored (§8.2, "
                    "§30 step 14). The existing record is left exactly as it "
                    "was: this is a collision, not an overwrite"
                ) from None
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:  # pragma: no cover - already gone
                pass


class PromotedEvidenceStore(_EvidenceDirectory):
    """The durable tier: read, and only read.

    **There is no `write`.** A promoted record arrives when a human copies the
    bytes of a staged record into this directory (§20.3), so there is no
    operation here by which AI-05 — or a caller of AI-05 — could add one. The
    absence is the enforcement, not a docstring: a method that existed only to
    refuse would still be a method a caller could reach.

    `read`, `contains` and `list_ids` are the same code the staged tier uses,
    and `discard` is inherited and refused (§19.2).
    """

    tier = EvidenceTier.PROMOTED
