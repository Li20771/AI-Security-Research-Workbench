# Context Plugin

Implements **AI-03**. Turns one workspace's verifiable, traceable context into a
structured `ContextResponse` for later Workbench components to consume.

Contract: [docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md](../../docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md).

## What it does

```text
Source -> Normalize -> Classify -> Attach provenance -> Structured Context
```

and never:

```text
Source -> LLM -> "current truth"
```

```python
from plugins.context import build_context

response = build_context("/path/to/workspace")

response.workspace   # identity: workspace_id, root, repository, branch, commit, tree
response.facts       # what is true now
response.history     # what has already happened
response.plans       # what is intended, frozen, or declared but not executed
response.sources     # what was read, and at which revision
response.freshness   # CURRENT / STALE / UNKNOWN, with counts
response.status      # FULL / PARTIAL / UNKNOWN — could the declared sources be read?
response.conflicts   # every contested subject, resolved
```

Self-check, offline, no credential, read-only:

```bash
python -m plugins.context.validate
```

## What it is not

```text
Model Router (AI-07, DEFERRED)   not implemented, not stubbed, no interface reserved
Guard (AI-04)                    not implemented
Evidence engine (AI-05)          not implemented
Security Tools (AI-06)           not implemented
global memory / vector db / RAG  not implemented
automatic Git writes             not implemented
SecurityLab integration          not implemented
```

## The five rules that shape the code

**Kinds are assigned, never promoted.** `FACT`, `HISTORY` and `PLAN` come from
the source class (§8.1). No function converts one into another, and there is no
`promote_*` anywhere in the package — so `PLAN -> COMPLETE` is not forbidden, it
is unrepresentable.

**Declared is not true.** `truth_state` is produced only by a literal
membership test on the token the source wrote. `COMPLETE` is `UNKNOWN`, never
`PASS`. `BLOCKED / DEFERRED` stays whole; picking `BLOCKED` out of it would be
inference.

**The cache is never a source of truth.** A hit requires all four key parts,
revision included. A stale entry yields *no items at all* — not a fallback, not
a downgrade. The live git-state source is deliberately **uncached**, because no
cheap probe captures the working tree, and a cache that is wrong about the
working tree is worse than no cache.

**One workspace, and only one.** The resolver reads the root it is given: no
registry, no upward search, no sibling scan. Every source path must resolve
inside the root or it is `REFUSED`. Items and source records carry their
`workspace_id`, and a mismatch raises rather than merging.

**Git is read-only, structurally.** `SubprocessGitReader` refuses any command
outside the frozen read set *before a subprocess exists*, and looks one token
further for subcommands that are read-only in one shape and a write in another
(`git remote get-url` reads; `git remote add` rewrites `.git/config`). Layer 0
asserts both directions.

## Layout

| Module | Role |
| --- | --- |
| `vocabulary.py` | the frozen enums and tables (§5) |
| `workspace.py` | A1 — identity, read-only git access (§6, §7.4) |
| `sources.py` | A2 — adapters, read outcomes, the default manifest (§7) |
| `declarations.py` | the structural extraction grammar (§7.3) |
| `classification.py` | A3 — kinds, subjects, provenance (§8) |
| `cache.py` | A4 — the four-part key and its outcomes (§9) |
| `resolution.py` | deterministic conflict resolution (§11) |
| `context.py` | A5 — `ContextResponse` assembly (§10, §11.4) |
| `validate.py` | offline self-check |

## Tests

`tests/context/` (layers 1–3) and `tests/integration/test_context_git_state.py`,
which runs against **real** git repositories rather than the fake reader every
other test uses. `tests/context/test_repository_context.py` is layer 3: it reads
this repository's own documents through the real pipeline.

No test requires a credential, a network, or a provider.
