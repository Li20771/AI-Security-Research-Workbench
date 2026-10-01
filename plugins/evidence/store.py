"""The filesystem Store — durable storage for admitted records.

Implements the storage decisions frozen in `docs/AI-05-B2_DECISIONS_2026-10-01.md`:

```text
D2  filesystem        no SQLite, no YAML database, no JSONL log, no third party
D3  UTF-8 JSON        one EvidenceRecord per file, <evidence_id>.json
D4  two directories   evidence/staged/ (gitignored) · evidence/promoted/ (tracked)
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

### The root is a parameter, and the tier is explicit

The Store never discovers a path. It is constructed with a root directory, so
tests point it at a temporary directory and nothing in this module needs to know
where the repository is. The tier is explicit because §19.2 and §20.2 make
`discard` legal for a staged record and FORBIDDEN for a promoted one:
`discard` refuses on a promoted Store rather than relying on nobody calling it.

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
query shape, the promotion API, and discard cleanup granularity. This class
provides the minimum the frozen decisions need and **does not freeze them**.
`read` returning an `EvidenceRecord` and `list_ids` returning a tuple of ids are
implementation choices, not contract surface, and they may change when D11 is
resolved. There is deliberately **no promotion method**: promotion is a human
act (§20.3), and inventing an API for it would freeze a design D11 left open.
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
    "EvidenceStore",
    "EvidenceTier",
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


class EvidenceStore:
    """One directory of stored records, at one tier.

    Constructed with a root; it creates that directory on first write and never
    looks outside it.
    """

    def __init__(self, root: str | os.PathLike[str], *, tier: EvidenceTier = EvidenceTier.STAGED) -> None:
        self._root = Path(root)
        self._tier = EvidenceTier(tier)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def tier(self) -> EvidenceTier:
        return self._tier

    # ------------------------------------------------------------------
    # paths
    # ------------------------------------------------------------------

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
    # write
    # ------------------------------------------------------------------

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
                f"{self._tier} tier"
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
        if self._tier is not EvidenceTier.STAGED:
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
