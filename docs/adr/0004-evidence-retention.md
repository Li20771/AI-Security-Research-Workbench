# ADR 0004: Evidence Retention

## Status
Accepted

## Decision
Separate raw execution output from normalized durable Evidence.

## Rules
- normalized key Evidence is durable
- raw large logs may be artifact-only
- benchmark cases/results are versioned
- AI caches are disposable and rebuildable
- secrets are never stored in Evidence

## Rationale
This preserves auditability without requiring every raw tool output to live in Git.