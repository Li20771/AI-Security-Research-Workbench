# dsh

The primary Agent (`AgentRole.PRIMARY`). See `body.py`.

**This is not DSH.** DSH is an external, GUI-only desktop platform baselined by
AI-01 — no CLI, no headless entry point. AI-08 does not reimplement, wrap or
drive it. What lives here is the Workbench-side execution shape: an identity
that resolves to `PRIMARY`, a body that runs inside one execution instance, and
a result attributed to `dsh` alone.

The v1 body is offline and performs no inference. It produces a provenance
reference, not a task result.
