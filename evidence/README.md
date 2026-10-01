# Evidence

Structured research evidence and audit records.

- `schema/`
- `runs/`
- `staged/`
- `promoted/`

## The two evidence families here are not interchangeable

```text
runs/       AI-02 live-verification records, shaped by
            schema/live_verification.schema.yaml.
            Written by scripts/live/run_live_verification.py.
            Generated and gitignored.

staged/     AI-05 EvidenceRecords (§5 envelope), written by
            plugins/evidence/store.py.
            Local and discardable, per B2 decision D4/D5. Gitignored.

promoted/   AI-05 EvidenceRecords that a human has promoted.
            TRACKED. Durable via Git; AI-05 does not delete from here and has
            no operation that does.
```

An `EvidenceRecord` is never written to `runs/`, and an AI-02 live-verification
record is never written to `staged/`. They are different record families with
different schemas, and putting one where the other belongs would make the
directory's contents unreadable by whatever consumes it.

## Promotion

Promotion is a **human act** (§20.3). It copies the same bytes to the promoted
location; it does not create a record, does not change `evidence_id`,
`content_digest` or `record_digest`, and is deliberately **not automated** —
`plugins/evidence/store.py` has no promotion method.
