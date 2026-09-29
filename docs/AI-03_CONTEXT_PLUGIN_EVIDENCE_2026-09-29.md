# AI-03 — Context Plugin Evidence

> Status: **IMPLEMENTATION AND VERIFICATION COMPLETE — NOT CLOSED**
> Phase: AI-03 — Context Plugin
> Sub-phases: AI-03-A (contract), AI-03-B1–B5 (implementation), AI-03-C (pending)
> Date: 2026-09-29
> Base SHA: `8c5df3e085e15e39f901e83f53f0e04f693cfb84`
> Branch: `feature/ai-03-context-plugin`

This document records what AI-03 built, what was verified, and — with equal
weight — what was **not**. It is an implementation and verification record, not
a closeout: AI-03-C requires a reviewed and merged PR, and no PR exists yet.

```text
AI-03-A  = COMPLETE      contract / execution plan / freeze
AI-03-B1 = COMPLETE      workspace resolver
AI-03-B2 = COMPLETE      source adapters
AI-03-B3 = COMPLETE      semantic classification
AI-03-B4 = COMPLETE      cache boundary
AI-03-B5 = COMPLETE      integration and offline tests
AI-03-C  = NOT_RUN       closeout / PR / merge
AI-03    = PARTIAL       exit criterion C8 is NOT_RUN
```

---

## A. Baseline

Read from the repository, not assumed:

```text
expected baseline SHA (from the AI-03 brief) = 8c5df3e085e15e39f901e83f53f0e04f693cfb84
actual  HEAD                                 = 8c5df3e085e15e39f901e83f53f0e04f693cfb84
actual  origin/main                          = 8c5df3e085e15e39f901e83f53f0e04f693cfb84
working tree at start                        = clean
branch at start                              = main
remote                                       = https://github.com/Li20771/AI-Security-Research-Workbench.git
```

The brief's expected SHA was confirmed against `git rev-parse` rather than
accepted from the brief. `HEAD == origin/main` and the tree was clean, so
implementation proceeded on a task branch.

Baseline test state, measured before any change:

```text
956 passed, 5 deselected
Layer 0 = PASS (12 checks)
provider/config/model validation = PASS (2 providers, 3 models)
```

---

## B. Phase identity and branch discipline

```text
base branch        = main
base SHA           = 8c5df3e085e15e39f901e83f53f0e04f693cfb84
work branch        = feature/ai-03-context-plugin
main modified      = no
SecurityLab touched= no (it is a separate repository and was not read or written)
history rewritten  = no
force push         = none
remote push        = none as of this record
```

All changes are confined to the work branch. `main` was never checked out for
modification, never reset, and never rebased.

---

## C. What was built

| Path | Lines | Role |
| --- | --- | --- |
| `docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md` | 996 | the frozen contract |
| `plugins/context/vocabulary.py` | 263 | frozen enums and tables (§5) |
| `plugins/context/workspace.py` | 364 | A1 — identity, read-only git access (§6, §7.4) |
| `plugins/context/sources.py` | 451 | A2 — adapters, read outcomes, manifest (§7) |
| `plugins/context/declarations.py` | 172 | the extraction grammar (§7.3) |
| `plugins/context/classification.py` | 200 | A3 — kinds, subjects, provenance (§8) |
| `plugins/context/cache.py` | 183 | A4 — four-part key and outcomes (§9) |
| `plugins/context/resolution.py` | 167 | conflict resolution (§11) |
| `plugins/context/context.py` | 373 | A5 — `ContextResponse` assembly (§10) |
| `plugins/context/validate.py` | 247 | offline self-check |
| `plugins/context/errors.py` | 72 | typed failure taxonomy |
| `tests/context/` (10 modules) | 3 092 | AI-03 unit and contract tests |
| `tests/integration/test_context_git_state.py` + `conftest.py` | 303 | tests against **real** git repositories |

Modified: `scripts/ci/layer0_policy.py` (+146), `.github/workflows/preflight.yml`,
`pytest.ini`, `tests/unit/test_repository_layout.sh`, `plugins/context/README.md`.

```text
33 files changed
No file outside plugins/context/, tests/context/, tests/integration/, docs/, and
the four repository-policy files listed above.
```

---

## D. Tests executed

All commands below were executed on this host. Nothing in this section is
carried forward from another phase or inferred.

### D.1 Verification sequence (AI-03 brief §20)

```text
1. targeted unit tests
   python -m pytest tests/context
   -> 332 passed

2. AI-03 integration tests
   python -m pytest tests/integration
   -> 23 passed

3. existing regression tests (full suite)
   python -m pytest
   -> 1311 passed, 5 deselected
      baseline was 956 passed, 5 deselected
      delta: +355 tests, 0 regressions, 0 previously-passing tests removed

4. repository-required checks
   python scripts/ci/layer0_policy.py       -> Layer 0 = PASS (13 checks; was 12)
   python -m providers.validate             -> PASS (2 providers, 3 models)
   python -m plugins.context.validate       -> PASS
   python -m compileall -q providers plugins tests -> OK
```

### D.2 Layer partition

```text
layer1 =  488 passed, 828 deselected
layer2 =  761 passed, 555 deselected
layer3 =   62 passed, 1254 deselected
         ----
         1311          (= the full suite; the layers partition it)
```

The 5 deselected tests are the AI-02 `layer4` live entry point, still excluded
from every default run by `pytest.ini`. **AI-03 adds no layer 4**: the Context
plugin has no network surface and no opt-in execution path, so there is nothing
for a live layer to gate.

### D.3 The brief's T1–T12

| # | Requirement | Where | Result |
| --- | --- | --- | --- |
| T1 | Workspace isolation | `tests/context/test_isolation.py::TestT1WorkspaceIsolation` | PASS |
| T2 | Current git state | `tests/integration/test_context_git_state.py::TestT2CurrentGitState` | PASS |
| T3 | Fact / History / Plan | `test_classification.py::TestT3FactHistoryPlanSeparation` | PASS |
| T4 | History cannot override current | `test_resolution.py::TestT4HistoryCannotOverrideCurrent` | PASS |
| T5 | Plan cannot become fact | `test_classification.py::TestT5PlanCannotBecomeFact` | PASS |
| T6 | `UNKNOWN` preservation | `test_classification.py::TestT6T7T8StatePreservation` | PASS |
| T7 | `NOT_RUN` preservation | `test_classification.py::TestT6T7T8StatePreservation` | PASS |
| T8 | `BLOCKED` preservation | `test_classification.py::TestT6T7T8StatePreservation` | PASS |
| T9 | Cache workspace isolation | `test_cache.py::TestT9CacheWorkspaceIsolation` | PASS |
| T10 | Cache invalidation | `test_cache.py::TestT10CacheInvalidation` | PASS |
| T11 | Source priority | `test_resolution.py::TestT11SourcePriorityIsDeterministic` | PASS |
| T12 | Sibling-workspace isolation | `test_isolation.py::TestT12SiblingWorkspaceIsolation` | PASS |

T2 is the only category executed against **real** git repositories rather than a
canned reader. Every other category runs against fixtures, which is stated here
so the distinction is not lost.

---

## E. Workspace identity, as observed

Captured by running the real pipeline over this repository during verification.
The working tree is dirty because it *is* this phase's work, and `changed_files`
counts this phase's own files.

```text
workspace_id   = ws-8755bade6039ea66
workspace_root = D:/AI-Security-Research-Workbench
repository     = Li20771/AI-Security-Research-Workbench
branch         = feature/ai-03-context-plugin
commit         = 8c5df3e085e15e39f901e83f53f0e04f693cfb84   (the base SHA)
working_tree   = DIRTY (33 changed paths, being this phase's own work)
status         = FULL
freshness      = current 55, stale 0, unknown 0 — overall CURRENT
items          = 6 fact, 24 history, 25 plan
conflicts      = 2
```

---

## F. Sources read, and their revisions

Read from this repository through the real pipeline.

| Priority | Source kind | Identity | Read status | Items | Revision |
| --- | --- | --- | --- | --- | --- |
| P0 | `git_current_state` | `git` | READ | 6 | `8c5df3e085e15e39f901e83f53f0e04f693cfb84` |
| P1 | `master_roadmap` | `docs/MASTER_ROADMAP.md` | READ | 0 | `c5c06dcb72b31904…` |
| P2 | `capability_inventory` | `docs/PROJECT_STATUS.md` | READ | 25 | `514cd178e5118bde…` |
| P3 | `design_freeze` | `docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md` | READ | 0 | `dd597793e620bd21…` |
| P4 | `exit_report` | `docs/AI-02_CLOSEOUT_2026-09-29.md` | READ | 4 | `c72d6fa5133c69bd…` |
| P5 | `git_history` | `git:history` | READ | 20 | `8c5df3e085e15e39f901e83f53f0e04f693cfb84` |

Document revisions are SHA-256 content digests (D-3); git revisions are commit
SHAs. Every source was `READ`; none was `MISSING`, `REFUSED`, or `BLOCKED`.

**Observation, recorded rather than hidden.** The P1 `master_roadmap` and P3
`design_freeze` sources produced **no items**: neither document contains a
fenced ```` ```text ```` block with `key = VALUE` declarations, and the
extractor (§7.3) declines to read prose. Both sources were read and are present
in `sources` with their revisions, so the situation is visible rather than
silent — but a reader should not mistake "0 items" for "nothing to say". This is
a limitation of a deliberately narrow grammar, not a defect. It is listed again
in §K.

---

## G. State preservation, on real repository text

Every declared token found in this repository's own documents, and the truth
state it produced. Captured after the status documents were updated for this
phase, so the counts include AI-03's own declarations — the pipeline is reading
the record of its own phase, which is the intended use.

| Declared (verbatim) | Truth state | Count |
| --- | --- | --- |
| `PASS` | `PASS` | 14 |
| `NOT_RUN` | `NOT_RUN` | 5 |
| `COMPLETE` | `UNKNOWN` | 3 |
| `BLOCKED / DEFERRED` | `UNKNOWN` | 1 |
| `DEFERRED / UNIMPLEMENTED` | `UNKNOWN` | 1 |
| `RESERVED / UNIMPLEMENTED` | `UNKNOWN` | 1 |
| `UNIMPLEMENTED / UNCHANGED` | `UNKNOWN` | 1 |
| `UNCHANGED` | `UNKNOWN` | 2 |
| `PARTIAL` | `UNKNOWN` | 1 |

The rule the table demonstrates: **`PASS` is produced only where the source
literally wrote `PASS`.** `COMPLETE` and `PARTIAL` are lifecycle words and
became `UNKNOWN`, not `PASS`. The four compound values were preserved whole and
were **not** decomposed into their parts — picking `BLOCKED` out of
`BLOCKED / DEFERRED` would be inference (D-6).

> **These are declarations, not adjudications.** The plugin reports what the
> documents say. A `PASS` in this column means the document wrote `PASS`, and
> nothing more. Every item in this table comes from the P2 capability-inventory
> source, which is `PLAN`-class, so none of it can enter `facts`.

---

## H. The real conflicts, and how they resolved

Two contested subjects were found in this repository. Neither was constructed
for a test: both are disagreements between real documents written in different
phases, and one of them appeared only because this phase updated
`docs/PROJECT_STATUS.md` and the pipeline then read its own update.

```text
subject = declared.live_provider_execution

P2  docs/PROJECT_STATUS.md            PLAN      declared NOT_RUN
P4  docs/AI-02_CLOSEOUT_2026-09-29.md HISTORY   declared NOT_RUN

authoritative = exit_report:docs/AI-02_CLOSEOUT_2026-09-29.md@c72d6fa5…
evidenced     = the same
superseded    = capability_inventory:docs/PROJECT_STATUS.md@514cd178…

subject = declared.provider_config_model_validation

P2  docs/PROJECT_STATUS.md            PLAN      declared PASS
P4  docs/AI-02_CLOSEOUT_2026-09-29.md HISTORY   declared PASS

authoritative = exit_report:docs/AI-02_CLOSEOUT_2026-09-29.md@c72d6fa5…
superseded    = capability_inventory:docs/PROJECT_STATUS.md@514cd178…
```

In both cases the exit report won even though the frozen priority table (§5.3)
ranks the capability inventory **above** it (P2 < P4). That is D-8 working: the
epistemic class orders before the source priority, because a plan is not
evidence however highly its source ranks. Both items were retained in each
case; each loser is marked `superseded_by`, not deleted.

> This is a statement about the context pipeline, not about the underlying
> claims. In both cases the two documents agree, and the pipeline reports their
> shared value. It promotes nothing.

---

## I. Cache boundary and workspace isolation

```text
T9  workspace A's entry is never returned for workspace B
    - B's lookup is MISS, not HIT and not STALE
    - tested with byte-identical documents in both workspaces, so the
      isolation holds on workspace_id alone and cannot be attributed to a
      convenient difference in content

T10 a superseded revision is STALE and produces no items
    - a changed document yields a new revision; the old entry is reported
      STALE with entry=None
    - a rebuild reflects the new content, with cache_hit=False
    - a HEAD move invalidates git history

    a warm cache produces the same items as a cold one
    - asserted field by field, with cache_hit excluded as the one field a
      cache is allowed to change
```

The live git-state source is **never cached** (D-14): its payload includes the
working tree, which changes without HEAD changing, so every cheap probe for it
would serve a `CLEAN` tree after the tree became `DIRTY`. Asserted at three
levels — the probe returns `None`, three consecutive builds never report a hit,
and the validator flags a `git_current_state` record carrying `cache_hit: true`.

---

## J. Security boundary

```text
network access from plugins/context        = none
credential required                        = none
secret in any tracked file, test, or this record = none
git write command in plugins/context       = none (asserted by Layer 0, both directions)
git write command at runtime               = refused before a subprocess exists
source path outside the workspace root     = REFUSED, not followed
workspace registry read                    = no
second workspace read                      = no
model inference anywhere in the pipeline    = none
automatic commit / push / merge            = none
```

**A defect found and fixed by the new Layer 0 check.** The check refuses to
accept a check it cannot fail, and when first run it failed: `git remote add`
is a write that rewrites `.git/config`, while `git remote get-url` is a read.
The guard had been checking only the subcommand, so every `git remote ...`
invocation — including the writes — was permitted. The guard now examines the
first argument for subcommands whose read/write nature depends on it, and the
Layer 0 check asserts **both** directions: 38 write invocations must be refused,
7 read invocations must be accepted. A guard that refused everything would fail
the second half.

This is recorded because it is the one place where a green check would have been
wrong, and because "the test cannot fail" is a failure mode that review does not
reliably catch.

---

## K. Known limitations and deferred items

These are real, and none is presented as a `PASS`.

1. **Two sources yield no items on this repository.** `docs/MASTER_ROADMAP.md`
   and `docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md` contain no structurally
   declared states, and the extractor does not read prose. Both are read and
   recorded with their revisions; neither contributes a context item. Widening
   the grammar is a deliberate non-goal, because every widening trades a false
   negative for a possible false positive and a false `PASS` is the worst
   output this component can produce.

2. **The cache is in-memory only** (D-10). A persistent cache needs a storage
   location, a retention rule, and a cleanup rule; shipping one without those
   would ship a second, undeclared source of truth. Recorded as Q-5, deferred.

3. **`design_freeze` reads one document** (Q-2). The frozen execution plans are
   not read as design-freeze sources. Widening is a manifest change, deferred.

4. **The subject alias table has exactly three entries** (D-5). A document can
   contradict live git on `head`, `branch`, or `working_tree` and nowhere else.
   A larger table would start guessing at prose.

5. **Layer 3 pins extraction, not the world.** `test_repository_context.py`
   reads this repository's own documents. It establishes nothing about any other
   workspace, and it cannot promote anything.

---

## L. What AI-03 deliberately did not build

Recorded so the boundary is auditable rather than inferred from absence:

```text
Model Router (AI-07)              DEFERRED; not implemented, not stubbed,
                                  no interface reserved
Guard plugin (AI-04)              not implemented
Evidence / Audit plugin (AI-05)   not implemented
Security Tools plugin (AI-06)     not implemented
global memory                     not implemented
vector database                   not implemented
RAG pipeline / semantic ranking   not implemented
LLM truth inference               not implemented
automatic Git writes              not implemented
SecurityLab integration           not implemented
cross-workspace aggregation       not implemented
```

`routing/`, `plugins/guard/`, `plugins/evidence/`, and `plugins/security-tools/`
remain placeholders. `security-tools` is not even a Python package name, and was
left alone.

---

## M. Exit criteria (AI-03 brief §23)

| # | Criterion | Status |
| --- | --- | --- |
| C0 | Contract implemented | **PASS** |
| C1 | Workspace isolation verified | **PASS** |
| C2 | Current Git state verified | **PASS** |
| C3 | Fact / History / Plan separation verified | **PASS** |
| C4 | Source priority conflict tests pass | **PASS** |
| C5 | `UNKNOWN` / `NOT_RUN` / `BLOCKED` preservation verified | **PASS** |
| C6 | Cache boundary and invalidation verified | **PASS** |
| C7 | Evidence artifact complete | **PASS** — this document |
| C8 | Required CI/tests PASS | **NOT_RUN** |

**C8 is `NOT_RUN`, so AI-03 is not COMPLETE.** The required checks were executed
locally and passed (§D.1). The GitHub Actions workflow has never run for this
branch, because no branch has been pushed and no PR exists. Local execution is
not CI execution, and the brief's §23 makes the difference decisive.

```text
C8 = NOT_RUN
AI-03 = PARTIAL
```

No criterion is recorded as `PASS` on the strength of implementation existing.
`COMPLETE` is a lifecycle word; per this phase's own contract §5.4, it is not a
truth state, and this document does not use it as one.

---

## N. What remains for AI-03-C

```text
1. push feature/ai-03-context-plugin        REQUIRES EXPLICIT HUMAN AUTHORISATION
2. open the PR                              blocked on 1
3. CI run on the PR                         NOT_RUN
4. human review and merge                   NOT_RUN
5. update PROJECT_STATUS.md / MASTER_ROADMAP.md to COMPLETE
6. re-verify C8 against the actual CI result
```

Steps 1 and 2 were not performed. Pushing is a `remote-change` action, which
`docs/GIT_AND_SECURITY_BOUNDARY.md` requires explicit approval for, and the AI-03
brief §22 requires the PR to wait until implementation, tests, evidence, and
final review are all complete. The work is committed to the task branch and
stops there.

---

## O. Provenance

```text
Phase:            AI-03 — Context Plugin
Base SHA:         8c5df3e085e15e39f901e83f53f0e04f693cfb84
Branch:           feature/ai-03-context-plugin
Workspace id:     ws-8755bade6039ea66

Local verification (offline, both API key variables unset):
  Layer 0 = PASS (13 checks)
  provider/config/model validation = PASS
  context validation = PASS
  1311 passed, 5 deselected
    layer 1 = 488
    layer 2 = 761
    layer 3 =  62

CI execution:     NOT_RUN
PR:               NOT_RUN
Merge:            NOT_RUN
Secrets added:    none
SecurityLab:      untouched
main:             untouched
```
