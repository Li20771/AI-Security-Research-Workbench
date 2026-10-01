# AI-05-B2 — Decision Record (pre-implementation)

> **Status: FROZEN for B2 implementation.** This document freezes design decisions.
> It is **not** a contract amendment, **not** an implementation, and **not** evidence
> that anything is built. It creates no Store, no record and no file under `evidence/`.

Baseline this record was authored against:

```text
main                = 63ed8759bd0a283ae68bf51b368f9a185f7e1511
origin/main         = 63ed8759bd0a283ae68bf51b368f9a185f7e1511
working tree        = clean
current contract    = docs/AI-05_EVIDENCE_EXECUTION_PLAN.md
current contract blob = dd062148938f902109b49a496bb6051c3331a349

AI-05-A  = COMPLETE / MERGED    contract frozen, 2 amendments
AI-05-B1 = COMPLETE / MERGED    offline logical core
AI-05-B2 = NOT STARTED          no branch, no rules.py, no Store, no storage backend
AI-05    = INCOMPLETE
```

Authority for **status** is `docs/PROJECT_STATUS.md`. The frozen contract keeps its
historical snapshot in §35.3 and the Status block; that snapshot is deliberately
**not** corrected by this record or by B2. Authority for **rules** is the contract.

Where this record and the contract disagree, the contract is correct and this
record is the defect.

---

## D1 — C-1 published admission rule set: remains DEFERRED

```text
C-1                        = DEFERRED        (contract §35.1)
T22a / T22b / T22c         = DEFERRED        (no published rule set exists)
T20c                       = DEFERRED        (already skipped in B1; status unchanged)
§30 step 7                 = NOT IMPLEMENTABLE in B2
```

§30 step 7 requires Class 3 and Class 4 fields to be checked against "the published
rules", while §14.2 states the published admission rule set is C-1 and remains
DEFERRED, so Class 4 is "structurally bounded and not rule-checked". §14.9's
`G-TEXT` row records the same: *admission rule-set obligation CONTRACT-REQUIRED and
DEFERRED with C-1*.

Frozen consequences:

```text
B2 MAY implement every other §30 admission boundary.
B2 MUST NOT invent, guess or import an admission rule set.
B2 MUST NOT write DEFERRED, NOT_RUN or BLOCKED as PASS.
A B2 completion statement MUST say that §30 step 7 is unimplemented,
  so "B2 complete" does not mean "§30 fully implemented".
```

**No Amendment 3 is written for this.** No new contract contradiction was found
during this review; the C-1 gap is already declared by the contract itself.

---

## D2 — Store backend: filesystem

```text
FROZEN    the Store backend is the filesystem.
NOT USED  SQLite · a YAML database · a JSONL append log · any third-party database
```

Minimal reasons, and no others are claimed:

```text
1  the repository has no Store / repository / persistence abstraction to reuse;
   this is a first decision, not a substitution
2  the filesystem is sufficient for the §20.4 durability contract D1–D5, D5', D5''
3  one record per file is the simplest structure in which write-once and
   append-only are properties of the medium rather than conventions of the code
4  it introduces no infrastructure the repository does not already require
```

Selecting a backend activates §20.5's requirement that location, retention and
cleanup be declared. They are declared in D4 and D5 — this is why those two
decisions are part of the freeze and not left to implementation time.

---

## D3 — Storage serialization: UTF-8 JSON, one record per file

```text
encoding    = UTF-8
format      = JSON
granularity = one EvidenceRecord per file
filename    = <evidence_id>.json     e.g. ev-3f2a9c41b7d05e88.json
```

Storage obligations, all frozen:

```text
stored bytes are written once
the Store never rewrites a canonical value
the Store never recomputes a digest
the Store never normalizes, repairs, trims, lowers or reorders a value
no sharding, no index file, no manifest is introduced
```

**JSON is physical carriage only.** Semantic canonicalization remains B1's
(`plugins/evidence/canonical.py`, §15.2). A storage format is not a second
canonical form, and two canonical forms would be one place for them to disagree.

The §17 round-trip requirement is the acceptance test for this decision:

```text
parse stored JSON
    -> stored-form loader (D7)
    -> canonicalize
    -> recompute record_digest
    == the record_digest of the original record
```

---

## D4 — Store locations

```text
evidence/runs/
    AI-02 raw / disposable run output.
    KEEPS ITS EXISTING PURPOSE. It is NOT repurposed as the AI-05 Store.

evidence/staged/
    AI-05 normalized staged Evidence. Local / workspace-scoped. GITIGNORED.

evidence/promoted/
    Human-controlled promoted Evidence. TRACKED. Durable via Git (D6 of §20.4).
```

`evidence/runs/` is shaped by `evidence/schema/live_verification.schema.yaml`, which
describes an AI-02 live-verification record — a different record family from an
`EvidenceRecord`. Writing AI-05 records there would conflate two families in one
directory, which is why the AI-05 tiers get their own locations.

```text
AI-05 does NOT promote automatically.
Promotion is a human copying the same stored bytes to the promoted location.
```

B2 implementation carries one obligation recorded here rather than performed here:
`.gitignore` currently ignores `evidence/runs/*` only, so `evidence/staged/*` must
be added (with a `.gitkeep` negation) when the directory is introduced.

---

## D5 — Retention and cleanup

```text
STAGED
    retention   indefinite until an explicit discard
    TTL         none
    cleanup     none automatic

PROMOTED
    retention   held by Git
    deletion    AI-05 cannot delete a promoted record
```

Staged discard, frozen:

```text
whole-record discard ONLY
no partial deletion
no field mutation
no rewrite of a surviving record
```

No garbage collection, rotation or compaction is introduced. None is required by
the contract, and each would be a deletion mechanism the contract does not define.

---

## D6 — Admission / B1 composition boundary

```text
B1 OWNS (B2 MUST NOT re-implement any of it)
    model parsing                  schema version
    required fields                vocabularies
    the §14.9 grammars             the §6.5 producer registry
    the §6.6 cross-field rules     content_digest / record_digest computation

B2 ADMISSION ADDS, AND ONLY ADDS
    composition of B1
    + workspace agreement (§18.1 — see below)
    + admission outcome mapping (§22.1)
    + uniqueness decision (§30 step 14)
```

Explicitly forbidden in B2:

```text
rules.py                     C-1 remains DEFERRED (D1)
a second enum check          a second grammar check
a second digest path         a second producer registry
a second cross-field rule set
```

**§18.1 workspace agreement is the one genuinely absent validation.** B1 validates
that each `workspace_id` is present and non-empty but never compares them, so a
record whose `references.context[].workspace_id` differs from its
`provenance.workspace_id` is currently constructible. §30 step 5 requires the
agreement half, and §31's T13 requires a constructible two-workspace input. This is
B2's work and it is not a re-implementation of anything.

---

## D7 — Stored-form loader (new capability)

Two different parsers, deliberately kept apart:

```text
caller input parser     →  unchanged, keeps every R1 restriction
stored-form loader      →  parses an ALREADY-WRITTEN EvidenceRecord
```

The loader must be able to restore:

```text
evidence_id · recorded_at · content_digest · record_digest · ContextRef.value_digest
```

The loader must NOT:

```text
relax R1 (§14.6.1) in any way
accept a caller-supplied digest
re-introduce a raw ContextRef `value` into the schema (§12.4 forbids persisting it)
modify any value it reads
be reachable from the caller-input path
```

Without this, §17's round-trip is not expressible: `EvidenceRecord.from_mapping`
refuses `evidence_id`, `content_digest`, `record_digest` and `recorded_at`, and
`ContextRef.from_mapping` requires a raw `value` while refusing `value_digest`. Its
job is round-trip restoration and nothing else.

---

## D8 — Uniqueness boundary

```text
duplicate evidence_id       REJECTED
duplicate content_digest    ACCEPTED  → separate evidence_id
                                      → separate record_digest
                                      → both retained
```

```text
the RULE belongs to Admission (§30 step 14)
the Store provides physical collision / overwrite prevention
```

NOT created:

```text
duplicate_of · revision · merge · deduplication
```

Duplicate content is two events (§8.2). Collapsing them, or annotating either with a
`duplicate_of`, would be the mutation §19 and §21 forbid.

---

## D9 — Lifecycle boundary

**No state machine is implemented.** No lifecycle field is added to
`EvidenceRecord` — not `candidate`, `validated`, `stored`, `revoked` or `revision`.
§19.1 already excludes these; this decision restates that B2 does not reintroduce
them under other names.

```text
the only staged lifecycle operations are   write · read · discard
discard                                    staged ONLY
promoted                                   MUST NOT be deleted
```

Promotion, unchanged from §20.3:

```text
human-controlled · same evidence_id · same content_digest · same record_digest
same bytes · new location only
AI-05 does not perform it
```

---

## D10 — Layer 0 architecture check (recorded, not implemented here)

§31 states: *"Layer 0 gains a structural check for `plugins/evidence`, mirroring
`check_context_plugin_performs_no_git_write`."*

`scripts/ci/layer0_policy.py` contains the Context check and **no** evidence check.
B1's T35 boundary was verified as a one-off scan, not as a standing Layer 0 gate.

```text
B2 implementation MUST add the §31 Layer 0 structural check for plugins/evidence.
This record only freezes that obligation; no CI file is modified now.
```

---

## D11 — Unresolved, retained as UNDEFINED / DEFERRED

These are **not** resolved by choosing the filesystem backend, and MUST NOT be
extended by implication:

```text
retrieval API exact return shape          UNDEFINED
superseded_by query API shape             UNDEFINED  (§21.2: derived, never stored)
promotion API                             UNDEFINED  (AI-05 does not automate it)
discard cleanup granularity beyond
  whole-record discard                    UNDEFINED
C-1 published admission rule set          DEFERRED   (D1)
artifact availability as a query-time fact (§13.3)     shape UNDEFINED
```

Choosing filesystem decides **where bytes live**. It decides nothing about what a
query returns.

---

## What this record does not do

```text
no contract change                        blob dd06214… unmodified
no production code                        plugins/ unchanged
no test code                              tests/ unchanged
no CI change                              .github/ unchanged
no Store, no database, no storage backend created
no file written under evidence/
no Amendment 3
§35.3's historical "Implementation = NOT STARTED" snapshot is left as written
```

## Next step

```text
B2 implementation branch, beginning with the §18.1 workspace agreement rule (D6),
then the stored-form loader and the §17 round-trip proof (D7),
then admission outcome mapping, then the Store and uniqueness, then discard,
then the §31 Layer 0 check (D10).
```
