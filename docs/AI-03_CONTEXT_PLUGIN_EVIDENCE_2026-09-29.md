# AI-03 — Context Plugin Evidence

> Status: **COMPLETE — C0–C8 all PASS; PR open, not merged**
> Phase: AI-03 — Context Plugin
> Sub-phases: AI-03-A (contract), AI-03-B1–B5 (implementation), AI-03-C (PR / CI)
> Date: 2026-09-29
> Base SHA: `8c5df3e085e15e39f901e83f53f0e04f693cfb84`
> Branch: `feature/ai-03-context-plugin`
> Validated implementation head: `7a29197f2b7eb09d0cd51c4dcd1332b6aaa2a011`
> Required CI: **SUCCESS** — run `36518367883`

> **CI status is a property of a commit, not of a document — including this one.**
>
> The head named above is the last commit containing production and test code;
> run `36518367883` is what validated it. Commits after it are documentation
> only. Writing a commit's SHA into a file *creates a new commit*, so any SHA
> written here is necessarily one commit behind the file that states it.
>
> The authoritative CI status for the current head is therefore **GitHub's check
> suite on PR #28**, never this paragraph. Nothing in AI-03 is `PASS` on the
> strength of a self-referential SHA, and a reader who needs the current state
> should read the PR rather than this record.
>
> Concretely: `7a29197` (code) was validated by run `36518367883`, and the
> documentation commit that carries this text is validated by its own run. Both
> are required; neither substitutes for the other.

This document records what AI-03 built, what was verified, and — with equal
weight — what was **not**.

**Two states, deliberately kept distinct.** The *validated* state below is
implementation head `7a29197` with CI run `36518367883` = SUCCESS. The
*repository* state is that PR #28 is **open and not merged**, so `main` does not
contain AI-03. CI having passed is not the same as a merge, and this document
does not conflate them.

```text
AI-03-A  = COMPLETE      contract / execution plan / freeze
AI-03-B1 = COMPLETE      workspace resolver
AI-03-B2 = COMPLETE      source adapters
AI-03-B3 = COMPLETE      semantic classification
AI-03-B4 = COMPLETE      cache boundary
AI-03-B5 = COMPLETE      integration and offline tests
AI-03-C  = COMPLETE      PR #28 opened, required CI SUCCESS
AI-03    = COMPLETE      C0-C8 all PASS

PR #28   = OPEN, MERGEABLE, NOT MERGED
main     = 8c5df3e; does NOT contain AI-03
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

### B.1 Branch HEAD — final HEAD SHA

The commit history on the branch, as read from `git log`:

```text
f604eb6   feat(ai-03): implement the context plugin
672f1d2   chore(ai-03): wire the context plugin into CI and record evidence
ee87433   docs(ai-03): note how to re-read the captured revision table
```

`ee87433d1871eb4eacbe2933b2df6dabeee63a6d` was HEAD when the pre-push audit in
§D was run.

**A note on reading this.** This document cannot record the final branch HEAD,
because committing it *creates* a new HEAD. The SHA above is the audit-time
value, and the document that records it is one commit later. The authoritative
final HEAD is whatever `git rev-parse HEAD` reports on the branch after the last
commit, and it is reported in the PR body — which is written after the last
commit and can therefore cite it without the circularity. Recording a SHA here
that claimed to be final would be recording something this file cannot know.

---

## C. What was built

| Path | Lines | Role |
| --- | --- | --- |
| `docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md` | 1 087 | the frozen contract (3 amendments) |
| `plugins/context/vocabulary.py` | 263 | frozen enums and tables (§5) |
| `plugins/context/workspace.py` | 364 | A1 — identity, read-only git access (§6, §7.4) |
| `plugins/context/sources.py` | 451 | A2 — adapters, read outcomes, manifest (§7) |
| `plugins/context/declarations.py` | 172 | the extraction grammar (§7.3) |
| `plugins/context/classification.py` | 218 | A3 — kinds, subjects, provenance (§8) |
| `plugins/context/cache.py` | 183 | A4 — four-part key and outcomes (§9) |
| `plugins/context/resolution.py` | 167 | conflict resolution (§11) |
| `plugins/context/context.py` | 373 | A5 — `ContextResponse` assembly (§10) |
| `plugins/context/validate.py` | 247 | offline self-check |
| `plugins/context/errors.py` | 72 | typed failure taxonomy |
| `tests/context/` (9 modules + conftest) | 3 329 | AI-03 unit and contract tests |
| `tests/integration/` (conftest + git-state tests) | 306 | tests against **real** git repositories |

Modified: `scripts/ci/layer0_policy.py` (+146), `.github/workflows/preflight.yml`,
`pytest.ini`, `tests/unit/test_repository_layout.sh`, `plugins/context/README.md`.

Counts are read from git at the validated head `7a29197` (`git show 7a29197:<path> | wc -l`),
not from a working tree that this document's own edits keep changing.

```text
33 files changed, +8346 / -15   (git diff --shortstat 8c5df3e..7a29197)
No file outside plugins/context/, tests/context/, tests/integration/, docs/, and
the four repository-policy files listed above.
```

---

## D. Tests executed

All commands below were executed on this host. Nothing in this section is
carried forward from another phase or inferred.

### D.1 Verification sequence (AI-03 brief §20)

At the validated head `7a29197`, run locally, offline, with both API-key
variables unset:

```text
1. targeted unit tests
   python -m pytest tests/context
   -> 338 passed

2. AI-03 integration tests
   python -m pytest tests/integration
   -> 23 passed

3. existing regression tests (full suite)
   python -m pytest
   -> 1317 passed, 5 deselected
      baseline was 956 passed, 5 deselected
      delta: +361 tests, 0 regressions, 0 previously-passing tests removed

4. repository-required checks
   python scripts/ci/layer0_policy.py       -> Layer 0 = PASS (13 checks; was 12)
   python -m providers.validate             -> PASS (2 providers, 3 models)
   python -m plugins.context.validate       -> PASS
   python -m compileall -q providers plugins tests -> OK
```

### D.2 Layer partition

```text
layer1 =  488 passed, 834 deselected
layer2 =  764 passed, 558 deselected
layer3 =   65 passed, 1257 deselected
         ----
         1317          (= the full suite; the layers partition it)
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

### D.4 Required CI — what C8 rests on

```text
run 36518367883   head 7a29197f2b7eb09d0cd51c4dcd1332b6aaa2a011
event             pull_request
conclusion        SUCCESS

Layer 0 — repository policy ................. success (13 checks)
Layers 1-3 — offline model and context layers success
  Check Python syntax ....................... success
  Layer 1 — contract and schema ............. success   488 passed
  Layer 2 — fake-transport unit tests ....... success   764 passed
  Layer 3 — offline contract fixtures ....... success    64 passed, 1 skipped
  Layer 4 — live connectivity verification .. success (NOT_RUN, by design)
  Confirm the suite ran without credentials . success
```

`provider/config/model validation: PASS` and `context validation: PASS` both ran
inside Layer 1. No credential was present, and no network I/O occurred.

**This is the only evidence that satisfies C8.** The local runs in §D.1 are not
CI runs and were never counted as C8.

### D.5 One assertion is skipped in CI, not passed

```text
tests/context/test_repository_context.py
  TestTheRepositoryReadsAsItself::test_a_branch_item_matches_git_when_present
  -> SKIPPED under a detached HEAD
```

CI reports `64 passed, 1 skipped` for layer 3, and the skip is this test. It
compares the reported branch against `git symbolic-ref`, which has no answer
when HEAD is detached — and `actions/checkout` detaches HEAD on every
`pull_request` run.

Recorded as `NOT_RUN` rather than counted as a pass. It leaves no gap: the
attached-branch case is covered deterministically by
`tests/integration/test_context_git_state.py::TestT2CurrentGitState::test_the_branch_is_the_real_branch`,
which builds its own repository on branch `main` and does run in CI.

---

## E. Workspace identity, as observed

Captured by running the real pipeline over this repository, at the point this
document was finalised.

```text
workspace_id   = ws-8755bade6039ea66
workspace_root = D:/AI-Security-Research-Workbench
repository     = Li20771/AI-Security-Research-Workbench
branch         = feature/ai-03-context-plugin
commit         = 7a29197f2b7eb09d0cd51c4dcd1332b6aaa2a011   (the validated head)
detached       = False
working_tree   = DIRTY (this document's own amendments)
status         = FULL
freshness      = current 53, stale 0, unknown 0 — overall CURRENT
items          = 6 fact, 24 history, 23 plan
conflicts      = 2
```

**These numbers move, and that is the plugin working.** The dirty tree is the
doc-sync amendment this document is part of; the item and freshness counts shift
with it. `workspace_id` is stable — it derives from the canonical root and the
repository, not from HEAD or the tree — which is why it still reads
`ws-8755bade6039ea66` while `commit` has moved from the base SHA to the validated
head. `working_tree` reports what it observes rather than what is convenient: a
documentation update makes it `DIRTY` exactly as a code change would.

A capture of this table is a record of a moment, not a constant. Re-running
`python -m plugins.context.validate` after any edit will produce different counts
and should not be read as a discrepancy.

---

## F. Source list, and source revisions

The source list read from this repository through the real pipeline, with each
source's `source_revision`.

| Priority | Source kind | Identity | Read status | Items | Revision |
| --- | --- | --- | --- | --- | --- |
| P0 | `git_current_state` | `git` | READ | 6 | `7a29197f2b7eb09d0cd51c4dcd1332b6aaa2a011` |
| P1 | `master_roadmap` | `docs/MASTER_ROADMAP.md` | READ | 0 | `b14e1320cdfe1820…` |
| P2 | `capability_inventory` | `docs/PROJECT_STATUS.md` | READ | 23 | `c0063f34e7d6fe08…` |
| P3 | `design_freeze` | `docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md` | READ | 0 | `dd597793e620bd21…` |
| P4 | `exit_report` | `docs/AI-02_CLOSEOUT_2026-09-29.md` | READ | 4 | `c72d6fa5133c69bd…` |
| P5 | `git_history` | `git:history` | READ | 20 | `7a29197f2b7eb09d0cd51c4dcd1332b6aaa2a011` |

Document `source_revision` values are SHA-256 content digests (D-3); git
`source_revision` values are commit SHAs. Every source was `READ`; none was
`MISSING`, `REFUSED`, or `BLOCKED`. Each source's read outcome and item count are
recorded in the table above, and the full `sources` array — including
`retrieved_at`, `read_status`, `freshness`, `item_count` and `cache_hit` — is
produced by `python -m plugins.context.validate` and by
`ContextResponse.to_dict()`.

**On reproducing this table.** The two kinds of revision behave differently. A
document digest is a function of the document's bytes, so it changes whenever
that document is edited — including by this very amendment, which is why the P1
and P2 digests above differ from the ones an earlier revision of this record
carried. A git-derived revision is the commit that was HEAD *at capture time*.
Both are therefore records of a moment, and neither is expected to match a
capture taken after further edits.

The difference matters to the cache: the same four-part key shape is used for
both, but the probe is sound for different reasons. A content digest genuinely
identifies what was read. A commit SHA identifies the moment — which is why the
live git-state source is **not cached at all** (§I), since no commit SHA can
capture a working tree.

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
| `PASS` | `PASS` | 15 |
| `COMPLETE` | `UNKNOWN` | 4 |
| `NOT_RUN` | `NOT_RUN` | 3 |
| `BLOCKED / DEFERRED` | `UNKNOWN` | 1 |
| `DEFERRED / UNIMPLEMENTED` | `UNKNOWN` | 1 |
| `RESERVED / UNIMPLEMENTED` | `UNKNOWN` | 1 |
| `UNCHANGED` | `UNKNOWN` | 1 |
| `UNIMPLEMENTED / UNCHANGED` | `UNKNOWN` | 1 |

The rule the table demonstrates: **`PASS` is produced only where the source
literally wrote `PASS`.** Every `COMPLETE` became `UNKNOWN`, never `PASS` — which
is the whole point, because this phase's own status now declares AI-03
`COMPLETE`, and that declaration must not be readable as evidence of anything.
The four compound values were preserved whole and were **not** decomposed into
their parts: picking `BLOCKED` out of `BLOCKED / DEFERRED` would be inference
(D-6).

> **A `COMPLETE` that stays `UNKNOWN` is the guarantee working.** AI-03's own
> completion claim is a `PLAN`-class declaration from the capability inventory.
> The plugin reports it faithfully and refuses to promote it — including when the
> claim is about the plugin itself.

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

authoritative = exit_report:docs/AI-02_CLOSEOUT_2026-09-29.md@c72d6fa5… = NOT_RUN
evidenced     = the same
superseded    = capability_inventory:docs/PROJECT_STATUS.md@c0063f34… = NOT_RUN

subject = declared.provider_config_model_validation

P2  docs/PROJECT_STATUS.md            PLAN      declared PASS
P4  docs/AI-02_CLOSEOUT_2026-09-29.md HISTORY   declared PASS

authoritative = exit_report:docs/AI-02_CLOSEOUT_2026-09-29.md@c72d6fa5… = PASS
evidenced     = the same
superseded    = capability_inventory:docs/PROJECT_STATUS.md@c0063f34… = PASS
```

A reference renders as `<kind>:<identity>@<revision> = <value>`. The value is part of it because
a reference has to identify an *item*: two halves of a self-contradicting document share one
read, and a reference without the value could not tell them apart (Amendment 3, §J.3).

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

### I.1 SecurityLab isolation (T12)

`SecurityLab` is a **separate repository**, independently versioned (`F-02`,
`F-17`). It was not read, not written, and does not appear in any changed path.
The context layer additionally guarantees that it *could not* be mixed in
(contract §3.6):

```text
source path resolving outside the workspace root   -> REFUSED, never opened
absolute path, `..` escape, directory symlink/junction -> REFUSED (all three tested)
workspace registry (workspaces/workspaces.example.yaml,
  which names a `securitylab` entry)               -> not in the manifest, never read
sibling workspace scan                             -> none
items or records carrying a foreign workspace_id   -> raises, never merges
```

The tests build two adjacent workspaces — one containing a marker string that
exists nowhere else — and assert that the marker never reaches the other's
context, that every source path is inside its own root, and that the resolver
issues no git call against any directory but the root it was given.

> Isolation is about **sources**, not vocabulary. `docs/PROJECT_STATUS.md`
> contains the line `SecurityLab = UNCHANGED`, and the pipeline reports it —
> because it is *this* workspace's own statement, read from *this* workspace's
> file. Suppressing it would be censoring the workspace's record, not protecting
> it. The test asserts exactly that distinction rather than a blanket string ban.

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

### J.1 Git guard permitted a write

**Found by the new Layer 0 check.** The check refuses to accept a check it cannot
fail, and when first run it failed: `git remote add` is a write that rewrites
`.git/config`, while `git remote get-url` is a read. The guard had been checking
only the subcommand, so every `git remote ...` invocation — including the writes
— was permitted. The guard now examines the first argument for subcommands whose
read/write nature depends on it, and the Layer 0 check asserts **both**
directions: 38 write invocations must be refused, 7 read invocations must be
accepted. A guard that refused everything would fail the second half.

Recorded because it is a place where a green check would have been wrong, and
because "the test cannot fail" is a failure mode that review does not reliably
catch.

### J.2 A lifecycle word in a context enum

**Found by a layer-1 test.** `ContextStatus` was first defined with `COMPLETE` as
a member — a lifecycle word, sitting in an enum whose values are published in the
context response. One refactor away from the `PLAN -> COMPLETE` promotion this
phase forbids, and the same word already appears in `docs/PROJECT_STATUS.md` as a
phase declaration, so the collision was live rather than hypothetical. Renamed to
`FULL` and pinned by a test that fails if a lifecycle word returns to the enum.
Contract Amendment 1.

### J.3 A conflict loser was retained but not marked

**Found while writing the test that pins Amendment 2, and the most serious of the
three.** `ItemRef` was `(source_kind, source_identity, source_revision)`, and
`apply_resolution` decided who had lost by comparing references. For a
self-contradicting document both halves come from one read, so both carried the
same reference. The comparison concluded that each item was the winner and
**marked neither**:

```text
Gate = PASS          ->  superseded_by: None      (the winner)
Gate = FAIL          ->  superseded_by: None      (should be superseded)
```

The contradiction was recorded in the items and then silently unrecorded by the
resolution. This is exactly the failure §11.1 exists to prevent, and it was
invisible to every test that did not build a self-contradiction, because for two
*different* sources the references do differ and the comparison works.

`ItemRef` now carries the item's `value`, so a reference identifies an item
rather than a read. This is a production-code change (Amendment 3), unlike
Amendments 1 and 2. Pinned by three tests, including one that drives a real
contradicting document through the real extraction path.

> Two of these three findings were in code that already had passing tests. Both
> were found by asking what the guarantee *cannot* represent, rather than by
> re-reading the implementation — which is the argument for checks that are
> required to be able to fail.

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
| C8 | Required CI/tests PASS | **PASS** — run `36518367883` @ `7a29197`, SUCCESS |

```text
C8 = PASS
AI-03 = COMPLETE
```

C8 is satisfied by the required checks on the validated head, and by nothing
else:

```text
PR #28                      = OPEN, MERGEABLE, NOT MERGED
run 36518367883 @ 7a29197   = SUCCESS
  Layer 0 — repository policy ......... success (13 checks)
  Layers 1-3 — model and context ...... success
```

**The history of C8, retained rather than flattened.** C8 was `NOT_RUN` before
the branch was pushed, because no CI had run. It was then `BLOCKED`/`FAIL` for
head `0bffb60`, when CI run `36517922651` failed on a genuine defect in an AI-03
test (§D.4). It is `PASS` only for head `7a29197`, and only because that run
succeeded. **A later commit would reset C8 to `NOT_RUN` until its own CI ran** —
C8 is a property of a commit, not of a phase.

**What C8 does not mean.** It does not mean `main` contains AI-03. PR #28 is
open and unmerged, and this document was written before any merge.

No criterion is recorded as `PASS` on the strength of implementation existing,
and the one assertion CI skipped is recorded as skipped, not upgraded (§D.5).

---

## M.1 What remains

```text
1. push feature/ai-03-context-plugin        DONE (authorised, over SSH)
2. open the PR                              DONE - PR #28
3. CI run on the PR                         DONE - SUCCESS (36518367883)
4. human review and merge                   PENDING - a human decision, not an agent action
5. update PROJECT_STATUS.md / MASTER_ROADMAP.md   DONE
6. re-verify C8 against the actual CI result      DONE
```

The only open item is step 4. **The merge is deliberately not performed by this
work.** It is a human decision at the repository checkpoint, and whatever CI
reports, the agent that implemented the phase does not merge it.

---

## N. Pre-push state (historical — superseded)

**This section describes what was true when this document was first written, and
is retained as a record rather than deleted. It is not the current state.** The
current state is §M and §M.1.

At the time of first writing, no branch had been pushed and no PR existed:

```text
1. push feature/ai-03-context-plugin        REQUIRES EXPLICIT HUMAN AUTHORISATION
2. open the PR                              blocked on 1
3. CI run on the PR                         NOT_RUN
4. human review and merge                   NOT_RUN
5. update PROJECT_STATUS.md / MASTER_ROADMAP.md to COMPLETE
6. re-verify C8 against the actual CI result
```

Steps 1 and 2 were not performed then, because pushing is a `remote-change`
action that `docs/GIT_AND_SECURITY_BOUNDARY.md` requires explicit approval for,
and the AI-03 brief §22 requires the PR to wait until implementation, tests,
evidence, and final review are all complete. Both were subsequently authorised
and performed: the branch was pushed, PR #28 was opened, and CI passed.

**One item in that list remains open, and it is meant to:** step 4, the human
merge decision. It is a human action at a GitHub checkpoint and is deliberately
outside what any command in this phase does. Whatever CI reports, AI-03 is not
merged by the agent that implemented it.

---

## O. Provenance

```text
Phase:            AI-03 — Context Plugin
Base SHA:         8c5df3e085e15e39f901e83f53f0e04f693cfb84
Branch:           feature/ai-03-context-plugin
Validated head:   7a29197f2b7eb09d0cd51c4dcd1332b6aaa2a011
Workspace id:     ws-8755bade6039ea66

Contract:         3 amendments (see the plan's §17.1)
                    A1 ContextStatus.COMPLETE -> FULL       documentation
                    A2 ordering gained a fifth key          documentation
                    A3 ItemRef gained `value`               production code

Local verification (offline, both API key variables unset):
  Layer 0 = PASS (13 checks)
  provider/config/model validation = PASS
  context validation = PASS
  1317 passed, 5 deselected
    layer 1 = 488
    layer 2 = 764
    layer 3 =  65

Required CI on the validated head:
  run 36518367883 @ 7a29197 = SUCCESS
    Layer 0 — repository policy ......... success
    Layers 1-3 — model and context ...... success
      layer 1 = 488, layer 2 = 764, layer 3 = 64 passed + 1 skipped

Exit criteria:    C0-C8 all PASS
PR:               #28 OPEN, MERGEABLE, NOT MERGED
Merge:            not performed - a human decision, and not this work's to take
Secrets added:    none
SecurityLab:      untouched
AI-07 Router:     untouched
main:             untouched (8c5df3e) - does NOT contain AI-03
```

### O.1 CI history

Retained because a single "CI = SUCCESS" line would hide the run that failed and
the defect it exposed.

```text
run 36517922651 @ 0bffb60   FAILURE   Layer 3: test assumed an attached HEAD
                                      (actions/checkout is detached on PR runs)
                            -> C8 = BLOCKED/FAIL for that head
run 36518367883 @ 7a29197   SUCCESS   after the test was corrected
                            -> C8 = PASS for that head
```

The failure was real and the test was wrong, not the implementation. The fix was
verified against a genuinely detached checkout (`git worktree add --detach`)
rather than by re-running locally, where the condition does not occur.
