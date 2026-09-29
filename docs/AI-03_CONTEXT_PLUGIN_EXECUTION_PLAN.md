# AI-03 — Context Plugin Execution Plan

> Status: **FROZEN** (AI-03-A, 2026-09-29)
> Phase: AI-03 — Context Plugin
> Sub-phase: **AI-03-A — Contract / Execution Plan / Freeze**
> Prerequisite: AI-00 architecture freeze + AI-01 DSH Baseline (COMPLETE) + AI-02 Model Layer (COMPLETE)
> Base branch: `main`
> Base SHA: `8c5df3e085e15e39f901e83f53f0e04f693cfb84`
> Rule: This document defines the contract. AI-03-B implements against it. Nothing in AI-03 may
> deviate from a frozen contract without amending this document first.

---

## 1. Status

| Item | Value |
| --- | --- |
| Phase | AI-03 — Context Plugin |
| Sub-phase | AI-03-A — Contract / Execution Plan / Freeze |
| Status | **COMPLETE — contract frozen** |
| Production code changed | **0** |
| Frozen on | 2026-09-29 |
| Freeze branch | `feature/ai-03-context-plugin` |

**What this sub-phase delivers:** a written, reviewable contract for the Workbench context layer —
the workspace identity boundary, the source adapter boundary, the FACT / HISTORY / PLAN
classification contract, the source priority and conflict-resolution rules, the cache boundary, the
freshness contract, and the phased plan for AI-03-B.

**What this sub-phase explicitly does not deliver:** any implementation. No source adapter, no
cache, no resolver, no router, no guard, no evidence engine, no security tool, no DSH/Codex
integration, no SecurityLab change.

### 1.1 Freeze semantics

```text
Frozen   = the shape and the rules below are binding for AI-03-B
Deferred = the value or the mechanism is declared but NOT implemented by AI-03
```

A frozen contract is a constraint on implementation. It is **not** a claim that anything listed
here has been executed. Every statement this plan makes about the repository is either read from
the repository at the base SHA (§2) or is a rule this phase imposes on AI-03-B.

> Frozen contracts and verified facts are different things. This document freezes the former and
> deliberately does not assert the latter.

---

## 2. Base SHA

Recorded at AI-03-A start, read from the repository — not assumed:

```text
branch            = main
HEAD              = 8c5df3e085e15e39f901e83f53f0e04f693cfb84
origin/main       = 8c5df3e085e15e39f901e83f53f0e04f693cfb84
working tree      = clean
remote            = https://github.com/Li20771/AI-Security-Research-Workbench.git
```

`HEAD == origin/main == 8c5df3e085e15e39f901e83f53f0e04f693cfb84`. The expected baseline in the
AI-03 brief is the same value, and it was confirmed against `git rev-parse` rather than accepted
from the brief.

### 2.1 Repository baseline observed at AI-03-A

Read directly from the working tree. Nothing below is inferred from directory names.

| Path | Actual content |
| --- | --- |
| `plugins/context/` | `README.md` only — a three-line "reserved" placeholder. No implementation. |
| `plugins/guard/`, `plugins/evidence/`, `plugins/security-tools/` | placeholders only; untouched by AI-03 |
| `routing/` | `README.md` only — Model Router unimplemented (AI-07) |
| `workspaces/` | `README.md` + `workspaces.example.yaml`; example declares one workspace (`securitylab`), `enabled: false` |
| `providers/` | AI-02 model layer, COMPLETE and frozen |
| `docs/PROJECT_STATUS.md` | declares AI-03 as the current stage, **NOT STARTED** |
| `tests/unit/` | 25 modules, every one carrying exactly one layer marker |
| `AGENTS.md`, `CLAUDE.md` | **absent** — the repository carries no agent-instruction file |

```text
Baseline test state (measured, not carried forward):
  956 passed, 5 deselected
  Layer 0 = PASS (12 checks)
  provider/config/model validation = PASS (2 providers, 3 models)
```

---

## 3. Scope

### 3.1 Architectural position

Context is one of the four runtime plugin layers (`Context`, `Guard`, `Evidence`, `Security
Tools`) in `docs/architecture/COMPONENT_MAP.md`. Its position in the frozen architecture, quoted
from AI-00 §5, is:

> ### Context Plugin
> 负责：Git state / project docs / roadmap / inventories / design freeze / exit reports / task context

AI-03 implements exactly that and nothing above it.

### 3.2 What the Context plugin is not

```text
Context Plugin  !=  Model Router          (AI-07, still DEFERRED)
Context Plugin  !=  Memory system
Context Plugin  !=  RAG pipeline
Context Plugin  !=  Security Guard        (AI-04)
Context Plugin  !=  Evidence engine       (AI-05)
Context Plugin  !=  Tool executor         (AI-06)
Context Plugin  !=  Git writer
Context Plugin  !=  SecurityLab integration layer
```

A Context plugin that selected a model, ranked sources semantically, wrote to git, or extended its
own reach into another workspace would be a different component wearing this one's name.

### 3.3 AI-03 deliverables

1. **Workspace Resolver** — a single, reliable answer to *which workspace is this, and what is its
   current git state*, with no discovery and no cross-workspace reach.
2. **Source Adapters** — one contract (`source_kind`, `source_identity`, `source_revision`,
   `retrieved_at`, `payload`) with git and document implementations.
3. **Semantic Classification** — deterministic FACT / HISTORY / PLAN assignment, with no model
   inference anywhere in the path.
4. **Cache** — a disposable, rebuildable, workspace-scoped store that can never become a source of
   truth.
5. **Integration** — `ContextResponse` assembly, freshness accounting, and the frozen conflict
   resolution of §11.

### 3.4 Explicitly out of AI-03 scope

```text
AI-04 Guard                            not implemented
AI-05 Evidence / Audit engine          not implemented
AI-06 Security Tools                   not implemented
AI-07 Model Router — DEFERRED          not implemented, not stubbed, no interface reserved
global memory / vector database        not implemented
RAG pipeline / semantic ranking        not implemented
LLM truth inference                    not implemented
automatic Git writes / commit / merge  not implemented
SecurityLab integration                not implemented
persistent on-disk context cache       not implemented (§9.5)
```

### 3.5 Router boundary — explicitly excluded

The Model Router (AI-07) is **DEFERRED** and is not implemented, referenced, or given a reserved
interface by AI-03. No file under `plugins/context/` imports from `routing/`, and `routing/`
remains a `README.md`-only placeholder after this phase.

### 3.6 SecurityLab boundary — no cross-workspace aggregation

`F-02` and `F-17` freeze SecurityLab as an independently versioned workspace that owns its own
research truth. AI-03 enforces this structurally rather than by convention (§6.3, §6.4):

- The resolver accepts exactly **one** workspace root. There is no workspace registry read, no
  parent-directory scan, no sibling scan, and no glob reaching outside the root.
- Every source path must resolve inside the workspace root or the source is refused (§7.5).
- Every item and every source record carries the `workspace_id` it was read under, and the
  assembler rejects a mismatch instead of merging it.

> **Global context aggregation is not implemented and is not an AI-03 deliverable.** A context
> response describes one workspace. Nothing in AI-03 reads `workspaces/workspaces.example.yaml`,
> and the presence of a `securitylab` entry in that file has no effect on any context build.

---

## 4. Non-goals

AI-03 does not:

- convert `BLOCKED` / `NOT_RUN` / `UNKNOWN` into `PASS`
- promote a PLAN into a FACT, an IMPLEMENTED, a COMPLETE, or a `PASS`
- treat a cache hit as evidence about the world
- infer a state from prose, from a model, from a confidence score, or from frequency
- write to git, to any workspace file, or to any remote
- read another workspace
- reach the network

---

## 5. Context vocabulary (frozen)

### 5.1 Item kind — FACT / HISTORY / PLAN

Every context item asserts something about **time**, and the three kinds are not interchangeable:

| Kind | Asserts | Typical source |
| --- | --- | --- |
| `FACT` | something about the **present** state of this workspace | live git state (P0) |
| `HISTORY` | something that **has already happened** | git history (P5), exit reports (P4) |
| `PLAN` | something **intended**, frozen, or declared but not executed | roadmap (P1), capability inventory (P2), design freeze (P3) |

Frozen rules:

- **HISTORY never overrides FACT.** A past commit, branch, or report describes the past. It is
  retained as HISTORY and never presented as the current state.
- **PLAN never becomes FACT.** No rule, no status word, and no later evidence promotes an item
  from one kind to another. Kinds are assigned once, by source class (§8.1), and are immutable.

### 5.2 Source kind

```text
git_current_state
master_roadmap
capability_inventory
design_freeze
exit_report
git_history
```

Exactly six. A seventh source kind is a contract amendment, not a configuration change.

### 5.3 Source priority (frozen)

Transcribed from AI-00 §11 / `MASTER_ROADMAP` AI-03 and frozen here. Lower rank = higher
precedence.

```text
P0  git_current_state       Git current state
P1  master_roadmap          Master Roadmap
P2  capability_inventory    Capability Inventory
P3  design_freeze           Design Freeze / Contracts
P4  exit_report             Exit Reports / Evidence Reports
P5  git_history             Git History / diff
P6  (cache)                 Disposable cache — never an item source (§9)
```

Rules:

- **No source is discarded for being low priority.** Priority decides who wins a conflict (§11);
  it never decides who is deleted. Every read source is represented in `sources`, and every item
  it produced is retained in its kind's list.
- **`P0 > historical > cache`**, as AI-03's brief states it, and the intermediate ranks are frozen
  above rather than left to implementation taste.
- **The cache has no item-level rank.** A cache entry is never an item's source; it is a
  short-circuit for re-reading a source at a revision that has been confirmed to match (§9.2).

### 5.4 Truth state — the five frozen values

Transcribed from AI-00 §10 and `docs/GIT_AND_SECURITY_BOUNDARY.md`, and frozen unchanged:

| State | Meaning |
| --- | --- |
| `PASS` | executed, with supporting evidence |
| `FAIL` | executed, and failed |
| `BLOCKED` | the required action or environment is unavailable |
| `NOT_RUN` | intentionally not executed |
| `UNKNOWN` | insufficient evidence |

Exactly five. `COMPLETE`, `NOT STARTED`, `DEFERRED`, `UNCHANGED`, `IMPLEMENTED` and every other
lifecycle word are **not** truth states. They are preserved verbatim as `declared_state` and their
truth state is `UNKNOWN` — never `PASS`.

> There is no code path in AI-03 that writes `PASS`. A `PASS` truth state can only be produced by
> reading the literal token `PASS` out of a source. This is asserted structurally in §12.2.

### 5.5 Freshness

| Value | Meaning |
| --- | --- |
| `CURRENT` | the source was read at the revision that is current now |
| `STALE` | a revision is held, and there is no evidence it is still the current one |
| `UNKNOWN` | freshness cannot be established |

### 5.6 Declared state and truth state — two axes, not one

Following the AI-02 §8.2 precedent, a declared state is recorded on two axes and the two are never
collapsed:

```text
declared_state   the exact token the source wrote, verbatim, never transformed
truth_state      the frozen §5.4 state, and only when declared_state is literally one of the five
```

The only transformation permitted anywhere in the path is stripping surrounding whitespace. Case is
preserved; internal punctuation is preserved; a compound declaration is **not** decomposed.

```text
declared "NOT_RUN"            -> truth_state NOT_RUN
declared "BLOCKED"            -> truth_state BLOCKED
declared "UNKNOWN"            -> truth_state UNKNOWN
declared "COMPLETE"           -> truth_state UNKNOWN       (a lifecycle word is not a truth state)
declared "BLOCKED / DEFERRED" -> truth_state UNKNOWN       (compound: NOT decomposed into BLOCKED)
declared nothing              -> truth_state UNKNOWN       (absent is not false)
```

> A plugin that picked `BLOCKED` out of `BLOCKED / DEFERRED` would be inferring. A plugin that
> turned `COMPLETE` into `PASS` would be laundering a claim into evidence.

### 5.7 Read status

Per source, the outcome of *reading* it — a different question from what it declared:

```text
READ        the source was read
MISSING     the declared source does not exist
UNREADABLE  the source exists but could not be read
REFUSED     the source was rejected by policy (path containment, §7.5)
BLOCKED     the environment cannot provide the source (not a repository, git absent)
```

**A source that was not read is never reported as read with an empty payload.** `MISSING` is not
an empty document, and it is not a `PASS`.

### 5.8 Context status

```text
FULL      every declared source was READ
PARTIAL   at least one source was not READ, and at least one was READ
UNKNOWN   no declared source was READ
```

The value is `FULL` and not `COMPLETE` (Amendment 1, §17.1). This field answers a
question about the *build*; `COMPLETE` is a lifecycle word describing a plan's progress.
Two different questions sharing one word is how a plan's `COMPLETE` ends up in a build's
status field.

---

## 6. Workspace identity contract

### 6.1 Identity fields

Every context response carries, and every item is bound to:

```text
workspace_id     stable identity of this workspace
workspace_root   canonical absolute path of the workspace root
repository       owner/name when the origin remote is a GitHub URL, else the raw URL or null
branch           current branch name, or null when detached
commit           current HEAD commit, or null
detached         true when HEAD is not on a branch
working_tree     CLEAN | DIRTY | UNKNOWN
```

`working_tree` is `UNKNOWN` — never `CLEAN` — when the state could not be established. An
unreadable working tree is not a clean one.

### 6.2 Derivation

`workspace_id` is derived deterministically from the canonical workspace root and the repository
identity, and from nothing else:

```text
workspace_id = "ws-" + sha256(canonical_root + NUL + (repository or "")).hexdigest()[:16]
```

Two different roots — or the same root under two different repositories — therefore have two
different ids. Time, host name, and process state are not inputs, so the id is stable across runs.

### 6.3 Containment

A source path resolves against the workspace root and must remain inside it after
`Path.resolve()`. A path that escapes — by `..`, by an absolute path, or by a symlink — is
`REFUSED` (§5.7), never followed.

### 6.4 No discovery

The resolver reads the root it is given and does not look for other workspaces. It does not read a
workspace registry, does not walk to a parent directory to find a repository, and does not scan
siblings. A workspace root that is not itself a git repository yields `working_tree: UNKNOWN` and
`branch`/`commit` of `null` — it does not cause a search upward.

---

## 7. Source adapter contract

### 7.1 The five required fields

Every source provides at least:

```text
source_kind        one of §5.2
source_identity    stable identity of the thing read, within the workspace
source_revision    the revision that was read, or null when none could be established
retrieved_at       ISO-8601 UTC timestamp of the read
payload            what was read, or null when nothing was read
```

`source_revision` identifies **what was read**, not when. It is:

```text
git sources        the commit SHA the read describes
document sources   the SHA-256 digest of the file content read
```

A content digest is used for documents rather than the workspace commit, so that an uncommitted
edit invalidates a cached read and an unrelated commit does not.

### 7.2 Default source manifest

Reviewed like code, like the AI-02 provider profiles (D-1). Paths are relative to the workspace
root; a declared path that does not exist is `MISSING`, which is a recorded outcome rather than an
error.

| Priority | Source kind | Binding |
| --- | --- | --- |
| P0 | `git_current_state` | the workspace repository itself |
| P1 | `master_roadmap` | `docs/MASTER_ROADMAP.md` |
| P2 | `capability_inventory` | `docs/PROJECT_STATUS.md` |
| P3 | `design_freeze` | `docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md` |
| P4 | `exit_report` | every `docs/*_CLOSEOUT_*.md`, sorted |
| P5 | `git_history` | the workspace repository's recent commits, bounded |
| P6 | (cache) | not a reader; §9 |

The manifest is data, and a build may be given a different manifest. The **priority table of §5.3
is not data**: it is frozen, and a manifest cannot reorder it.

### 7.3 Document declared-state extraction

A document contributes items only where it declares a state **structurally**. The extraction rule
is fixed and deliberately narrow:

1. Only fenced blocks whose info string is `text` are scanned.
2. Only lines matching `key = VALUE` are considered, where `key` is at most 80 characters from
   `[A-Za-z0-9 ._#()/+-]` and `VALUE` is a whitespace- or slash-separated run of
   `[A-Z][A-Z0-9_]*` tokens.
3. `key` and `VALUE` are recorded; `VALUE` is `declared_state` verbatim.
4. **Every other line in the document is ignored.** Prose, headings, tables, and unparsed
   formatting produce no items.

Rule 2 exists because of a real line at the base SHA. `docs/AI-02_CLOSEOUT_2026-09-29.md` contains

```text
NOT_RUN != PASS
```

A looser key character class matches this as the declaration `key="NOT_RUN !", value="PASS"` and
manufactures a `PASS` out of a sentence asserting the opposite. The extracted key character class
excludes `!`, `=`, `<`, `>`, `*` and backticks specifically so that this line cannot match.

### 7.4 Git sources — read-only

Git sources invoke the `git` binary with read-only commands only. The permitted set is fixed:

```text
git rev-parse            git symbolic-ref        git status --porcelain
git log                  git remote get-url
```

**AI-03 contains no git write command.** No `commit`, `push`, `add`, `checkout`, `reset`,
`restore`, `clean`, `merge`, `rebase`, `tag`, `stash`, or `config --set`. This is checked
mechanically in Layer 0 (§12.1), not merely intended.

### 7.5 Refusal and failure

A source that cannot be read is recorded with the matching §5.7 status and its note. It is never
silently dropped, and it never causes the remaining sources to be dropped: a partial context is
more useful than none, provided it is labelled `PARTIAL` (§5.8).

---

## 8. Classification contract

### 8.1 Kind by source class

Kind is a property of the **source**, declared in the manifest and reviewed like code:

| Source kind | Item kind |
| --- | --- |
| `git_current_state` | `FACT` |
| `git_history` | `HISTORY` |
| `exit_report` | `HISTORY` |
| `master_roadmap` | `PLAN` |
| `design_freeze` | `PLAN` |
| `capability_inventory` | `PLAN` |

### 8.2 Ambiguity defaults to PLAN

Where a source's semantic class is genuinely ambiguous, it is classified as `PLAN`. This is the
fail-safe direction and it is deliberate:

```text
PLAN classified as PLAN        -> safe; a plan that never claims to be a fact
PLAN classified as FACT        -> unsafe; an intention presented as current reality
HISTORY classified as FACT     -> unsafe; a past state presented as the present one
```

`docs/PROJECT_STATUS.md` is bound as the P2 capability inventory and is therefore `PLAN`-class,
even though it contains lines such as `AI-02 overall = COMPLETE`. That classification is chosen,
not accidental: it guarantees that no line of a status document can be cited as a present fact,
while the actual execution record remains available as `HISTORY` from the P4 exit reports.

### 8.3 Stable subjects

An item's `subject` names **what the item is about**, and is what makes conflicts detectable. Two
sources making a claim about the same thing share a subject; two sources describing different
things do not.

```text
git.branch            git.head            git.working_tree
git.detached          git.repository     git.commit.<sha>   (one per historical commit)
declared.<normalised_key>                                     (a document declaration)
```

`<normalised_key>` lowercases the extracted key and collapses each run of non-alphanumeric
characters to a single `_`. So `Live provider execution` and `live-provider-execution` in two
different documents share the subject `declared.live_provider_execution`, which is what makes the
P2/P4 conflict of §11.3 detectable at all.

A **frozen three-entry alias table** maps three declaration keys onto the git subjects, so that a
document contradicting the live repository is a detectable conflict rather than an unconnected
item:

```text
head          -> git.head
branch        -> git.branch
working_tree  -> git.working_tree
```

The table is exactly these three. It is frozen, reviewed like code, and is not a heuristic.

### 8.4 No promotion

Classification is one-way. There is no function in AI-03 that takes an item and returns an item of
a different kind, and there is no status word that changes a kind. `PLAN -> IMPLEMENTED`,
`PLAN -> COMPLETE`, and `PLAN -> PASS` are not merely discouraged; they are unrepresentable,
because `IMPLEMENTED` and `COMPLETE` are not members of any AI-03 vocabulary (§5.4).

---

## 9. Cache boundary

### 9.1 Cache key

```text
CacheKey = workspace_id + source_kind + source_identity + source_revision
```

The key is a frozen four-part tuple. Three parts would let a stale read be served; dropping
`workspace_id` would let one workspace answer another.

A cache entry also records `retrieved_at`, so that a stale entry is *reportable* rather than merely
unusable.

### 9.2 Cache is never a source of truth

```text
cache != source of truth
```

- A cache entry is used only when **all four key parts match exactly**. The match includes the
  revision, so a hit is evidence that the revision was confirmed, not that the value is trusted.
- An item produced from a cache hit carries the **original** source kind and priority, because it
  *is* that source's content at the confirmed revision. A cache hit does not become a P6 item and
  does not become a seventh source.
- A cache entry whose revision does not match is `STALE` and produces **no items at all**. It is
  never used as a fallback, and never downgraded into an item.
- The context build is complete without the cache. The cache is an optimisation, and a build run
  with an empty cache produces the same items as a build run with a warm one.

### 9.3 Outcomes

```text
HIT    an entry exists for all four key parts
STALE  an entry exists for the same (workspace_id, source_kind, source_identity) at a DIFFERENT revision
MISS   nothing matches
```

`STALE` and `MISS` are distinguished because they mean different things: `STALE` says *this was
read before and the world has moved*; `MISS` says *this was never read here*.

### 9.4 Workspace scoping

Because `workspace_id` is part of the key, workspace A's entry **cannot be returned** for
workspace B. B's lookup is a `MISS` — not a `HIT`, and not even a `STALE`, because a different
workspace's entry is not a stale version of this one's.

### 9.5 Persistence

AI-03 ships an in-memory cache only. A persistent on-disk cache requires a storage location, a
retention rule, and a cleanup rule, none of which this phase owns. Deferred, recorded as such in
§16.2, and **not** a `PASS`.

---

## 10. Freshness contract

### 10.1 Assignment

Freshness is decided by comparing the revision a source was read at with the revision that is
current at the end of the build:

```text
read revision == current revision   -> CURRENT
read revision != current revision   -> STALE
revision cannot be established      -> UNKNOWN
```

### 10.2 `STALE != WRONG`

`STALE` asserts exactly one thing: *there is currently no evidence that this is still the newest
state.* It does not assert that the value was wrong, that the source was bad, or that the item
should be distrusted. A stale item is retained with its full provenance; it is simply not
presented as current.

### 10.3 Summary

`freshness` reports a count per value plus an overall value, which is the **most severe** of the
values present:

```text
CURRENT  <  STALE  <  UNKNOWN
```

The most-severe rule is deterministic and fail-safe: a response containing one unestablished item
does not report itself as wholly current.

---

## 11. Conflict resolution

### 11.1 What a conflict is

Two items conflict when they share a `subject` (§8.3) and come from different sources. Resolution
picks one authoritative item and **retains every loser**, marked with the winner's subject in
`superseded_by`.

No item is ever deleted by conflict resolution. Deleting the loser would destroy exactly the
disagreement that makes the context auditable.

### 11.2 Ordering

Frozen, total, and deterministic:

```text
1. epistemic class   FACT  <  HISTORY  <  PLAN      (§16 of the AI-03 brief: evidence wins)
2. source priority   P0 < P1 < P2 < P3 < P4 < P5    (§5.3, frozen)
3. source_identity   ascending                      (determinism)
4. source_revision   ascending                      (determinism)
```

**This resolves a real tension between two requirements of the AI-03 brief**, and the resolution is
recorded as a decision (D-8):

- §6 of the brief freezes a single source priority in which the Master Roadmap (P1) outranks exit
  reports (P4).
- §16 of the brief requires that evidence state wins and that a plan stays a plan.

Taken as one ordering, the two would let the roadmap override an exit report about the same
subject. They are therefore applied on two axes, in the order above: the frozen priority orders
sources **within** an epistemic class, and the epistemic class decides **across** classes. A plan
is not evidence, so it cannot win against evidence no matter which source it came from.

Nothing is broken by ties, because steps 3 and 4 are total: two items with the same subject, the
same class, and the same source priority cannot also share a source identity and a revision unless
they are the same read.

### 11.3 The four frozen cases

| Case | Rule | Implementation |
| --- | --- | --- |
| **Git vs History** | Git current wins; history is retained as HISTORY | `FACT`(0) beats `HISTORY`(1) |
| **Git vs Cache** | Git current wins; the old cache entry is marked `STALE` | a non-matching revision yields no items (§9.2) |
| **Evidence vs Plan** | The evidence state wins; the plan remains a PLAN | `HISTORY`(1) / `FACT`(0) beats `PLAN`(2) |
| **Unknown** | `UNKNOWN` remains `UNKNOWN` | no rule reads a truth state as input to another item's state |

### 11.4 Resolution record

Each contested subject produces a resolution record naming the authoritative item, the evidenced
item, and every superseded item. The record is derived from the retained items, so a resolution
can never disagree with the item lists it describes.

---

## 12. Testing strategy

Five layers, ordered by what they are allowed to assume. AI-03 **adds no layer 4**: the phase has
no network surface and no opt-in execution path, so there is nothing for a live layer to gate.

### 12.1 Layer 0 — repository policy (offline, exists)

Already in CI. AI-03 extends it with:

- `docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md` as a required file
- `plugins/context` and `tests/context` as required directories
- **a mechanical check that `plugins/context/` contains no git write command** — the permitted
  read-only command set of §7.4 is asserted by scanning the package, so the guarantee is checked
  rather than promised
- the existing checks continue to apply unchanged, including that every test module declares
  exactly one layer marker

### 12.2 Layer 1 — contract and vocabulary (offline)

Pure, no I/O:

- every §5 table is transcribed and asserted against the implementation, so a reordering of the
  priority table is a test failure
- `PASS` is a member of the truth-state vocabulary and is **not** reachable by any conversion:
  the module contains no mapping function and the tests assert that a lifecycle word maps to
  `UNKNOWN`
- the declared-state extractor's rules (§7.3), including the `NOT_RUN != PASS` line that must
  **not** match
- no item kind is reachable from another by any function in the package

### 12.3 Layer 2 — behaviour (offline, no network)

Exercised through fake sources, a stub git reader, and throwaway repositories created inside
`tmp_path`. Asserts:

- workspace A's context contains nothing from workspace B
- a cached entry from A is not returned for B, and is not even `STALE` for B
- a cached entry at a superseded revision is `STALE` and yields no items
- a plan cannot win a subject against evidence, and cannot appear in `facts`
- every §11.3 case resolves to the frozen outcome, and resolves the same way under input
  permutation
- `NOT_RUN`, `BLOCKED`, and `UNKNOWN` survive the full pipeline unchanged
- a source path escaping the workspace root is `REFUSED` and is not read
- a git read that changes between two builds changes the context, with no cached value masking it

### 12.4 Layer 3 — real repository context fixtures (offline)

The actual documents of this repository, read through the real extraction path, pinned by content
digest. Asserts that the real `docs/PROJECT_STATUS.md` and `docs/AI-02_CLOSEOUT_2026-09-29.md`
produce `NOT_RUN` for `Live provider execution` and that **no item anywhere in a real context
build has truth state `PASS` unless its source literally declared `PASS`**.

> **A fixture is not evidence about the world.** Layer 3 pins *our* extraction and classification
> against real repository text. It establishes nothing about any other workspace, and it cannot
> promote anything.

### 12.5 Layer 4 — not introduced

AI-03 defines no layer 4. `pytest.ini` continues to deselect `layer4`, and the live workflow is
untouched by this phase.

### 12.6 Layer rules

```text
CI runs layers 0-3. Never layer 4.
Layers 1-3 require no credential, no network, and no provider access.
Layer 2 requires git for the throwaway-repository tests; the repository already requires git.
NOT_RUN is a legitimate, expected state -- never a FAIL to be papered over, and never a PASS.
```

---

## 13. Implementation phases

```text
AI-03-A    Contract / Freeze                        <- this document. COMPLETE.
AI-03-B1   Workspace resolver
AI-03-B2   Source adapters
AI-03-B3   Semantic classification
AI-03-B4   Cache boundary
AI-03-B5   Integration and offline tests
AI-03-C    Closeout / Evidence
```

### AI-03-B1 — Workspace resolver

Deliver: `WorkspaceIdentity` per §6.1; deterministic id derivation per §6.2; read-only git access
per §7.4; a git-reader seam so the resolver can be exercised without a real repository.
Constraint: **no git write command**, no upward search, no registry read.
Exit: identity is stable across runs and distinct across roots; a non-repository root yields
`working_tree: UNKNOWN` rather than an exception or a false `CLEAN`.

### AI-03-B2 — Source adapters

Deliver: the §7.1 field contract; git current-state, git history, and document adapters; path
containment per §6.3; the default manifest of §7.2.
Constraint: no network, no write, no source outside the workspace root.
Exit: every non-read outcome of §5.7 is reachable and recorded; a refused path is never opened.

### AI-03-B3 — Semantic classification

Deliver: the §8.1 kind table; stable subjects per §8.3; the declared-state extractor of §7.3; the
frozen alias table.
Constraint: **no model inference, no confidence score, no prose parsing.** Classification reads
only the source class and the structurally extracted declaration.
Exit: FACT / HISTORY / PLAN are assigned and separated; no function converts between them; a
lifecycle word yields `UNKNOWN` and never `PASS`.

### AI-03-B4 — Cache boundary

Deliver: the §9.1 key, the §9.3 outcomes, the in-memory cache, and workspace scoping.
Constraint: **cache is never a source of truth.** A non-matching revision yields no items.
Exit: T9 and T10 of the AI-03 brief pass; a full build with an empty cache equals a full build
with a warm cache.

### AI-03-B5 — Integration and offline tests

Deliver: `ContextResponse` per §4.1 of the brief plus the §11.4 resolution record; freshness
summary per §10.3; conflict resolution per §11.2; layers 0–3 wired into CI.
Constraint: no layer 4; no network; no credential.
Exit: validation and layers 0–3 pass with no credential present, and the full AI-03 test set of
the brief's §17 (T1–T12) is present and passing.

### AI-03-C — Closeout / Evidence

Deliver: AI-03 Evidence record; `PROJECT_STATUS.md` and `MASTER_ROADMAP.md` updated; PR reviewed
and merged; contract amendments, if any, folded back into this document.

---

## 14. Exit criteria

### 14.1 AI-03-A exit criteria

- [x] Current real base SHA recorded (§2)
- [x] Current working tree state recorded (§2)
- [x] AI-03 scope frozen (§3)
- [x] Router explicitly excluded (§3.5)
- [x] SecurityLab and cross-workspace aggregation explicitly excluded (§3.6)
- [x] Context vocabulary frozen (§5)
- [x] Source priority frozen (§5.3)
- [x] Workspace identity contract frozen (§6)
- [x] Source adapter contract frozen (§7)
- [x] Classification contract frozen (§8)
- [x] Cache boundary frozen (§9)
- [x] Freshness contract frozen (§10)
- [x] Conflict resolution frozen (§11)
- [x] Test layers defined (§12)
- [x] Execution plan committed
- [x] Contains no production implementation
- [x] Contains no real API key
- [x] Contains no real API call
- [x] Relevant CI passes

### 14.2 AI-03-B entry criteria

- [ ] AI-03-A merged
- [ ] The §5 vocabulary is implemented and asserted against this document
- [ ] The §7.2 manifest is decided before adapters are written

### 14.3 AI-03 (full phase) exit criteria

Only when every item below is satisfied:

- [ ] Context contract implemented
- [ ] Workspace isolation verified
- [ ] Current git state verified against a real repository
- [ ] FACT / HISTORY / PLAN separation verified
- [ ] Source priority conflict tests pass
- [ ] `UNKNOWN` / `NOT_RUN` / `BLOCKED` preservation verified
- [ ] Cache boundary and invalidation verified
- [ ] Evidence artifact complete
- [ ] Required CI and tests pass
- [ ] Router untouched and unimplemented
- [ ] Guard / Evidence / Security Tools plugins untouched and unimplemented
- [ ] No automatic git write anywhere in the phase
- [ ] SecurityLab untouched
- [ ] No secret in any tracked file, fixture, log, or Evidence record
- [ ] PR reviewed and merged, `PROJECT_STATUS.md` updated

```text
Context reports what a source declared. It never decides what is true.
```

---

## 15. Known external dependencies

| Dependency | Risk | Handling |
| --- | --- | --- |
| `git` binary availability | the git sources cannot be read | `BLOCKED` read status (§5.7); the repository already requires git |
| Git configuration (safe.directory, ownership) | reads may fail on some hosts | recorded as `BLOCKED` with a note; never converted to an empty read |
| Document layout change | declared-state extraction silently stops matching | Layer 3 pins the real documents by digest, so a layout change is a test failure rather than a silent zero |
| A workspace root outside a repository | no git identity | `working_tree: UNKNOWN`, `branch`/`commit` null — not an error and not a `CLEAN` |
| GitHub `main` branch protection | inherited `BLOCKED` from AI-00 | unchanged; not converted to `PASS` |

---

## 16. Decisions / open questions

### 16.1 Decisions made in AI-03-A

**D-1 — The source manifest is reviewed repository data, not configuration** (§7.2). The same rule
AI-02 applied to provider profiles: which documents constitute a workspace's context is a reviewed
decision, and a source that silently appears or disappears changes what the agent believes.

**D-2 — Ambiguous source classes are classified `PLAN`** (§8.2). The three misclassifications are
not equally bad. Classifying a plan as a plan costs nothing; classifying a plan or a history as a
fact presents something that is not current as current. The default is therefore chosen so that
the failure mode is the harmless one.

**D-3 — Source revision for documents is the content digest** (§7.1). The workspace commit would
make an uncommitted edit invisible to the cache and make an unrelated commit invalidate every
document at once. The digest answers the question the cache actually asks.

**D-4 — Declaration keys are normalised, not namespaced per document** (§8.3). Two documents
declaring `Live provider execution` must collide, because a conflict nobody can detect is a
conflict nobody can resolve. Per-document namespacing would make every subject unique and conflict
resolution unreachable.

**D-5 — The subject alias table has exactly three entries** (§8.3). `head`, `branch`, and
`working_tree` are the three subjects on which a document can contradict live git state, which is
the contradiction the brief's T4 requires to be detectable. A larger table would start guessing at
prose; a smaller one would make T4 untestable.

**D-6 — A compound declaration is not decomposed** (§5.6). `BLOCKED / DEFERRED` yields
`truth_state: UNKNOWN`. Choosing `BLOCKED` would be inference, and the brief forbids inference in
exactly this place. Recording the compound verbatim loses nothing, because `declared_state` keeps
it intact.

**D-7 — `freshness` reports the most severe value present** (§10.3). The alternative — reporting
`CURRENT` when some items are current — would let a response advertise freshness it does not have.

**D-8 — Epistemic class orders before source priority** (§11.2). This resolves a genuine tension
between §6 and §16 of the AI-03 brief, neither of which is wrong on its own. Priority is a
preference among sources; it is not a licence for a plan to outrank evidence.

**D-9 — AI-03 adds no layer 4** (§12.5). Layer 4 exists in AI-02 to gate live provider calls.
AI-03 has no network surface, so a live layer would have nothing to gate and would exist only to
look complete.

**D-10 — The cache is in-memory only** (§9.5). A persistent cache needs a location, a retention
rule, and a cleanup rule. Shipping one without those would ship a second, undeclared source of
truth — the exact failure F-11 forbids.

**D-11 — `ContextResponse` carries a `conflicts` member beyond the brief's seven** (§4.1 of the
brief, §11.4). The brief's model lists seven members and separately requires deterministic
conflict resolution. A resolution that is not recorded is not auditable, so the resolution is a
member rather than a derived convenience. Nothing in the seven is removed or renamed.

**D-12 — Read status is recorded per source** (§5.7). Without it, a document that failed to read
and a document that declared nothing are indistinguishable, and the second is a `PASS`-shaped
silence.

### 16.2 Open questions

Carried into AI-03-B. None changes a frozen boundary; each is an implementation choice.

| # | Question | Needed by | Default if unresolved |
| --- | --- | --- | --- |
| Q-1 | How many historical commits does `git_history` read? | B2 | 20, bounded and declared |
| Q-2 | Does `design_freeze` read one document or the frozen execution plans too? | B2 | one document; widening is a manifest change |
| Q-3 | Is `declared_state` stored for items that are not declarations? | B3 | no; git items carry no declared state |
| Q-4 | Should a `REFUSED` source abort the build or degrade to `PARTIAL`? | B2 | `PARTIAL`; a refusal is recorded, not fatal |
| Q-5 | Persistent cache location and retention | a later phase | §9.5 — not implemented |

### 16.3 Amendment rule

Any change to a frozen boundary in this document requires an amendment to this document **first**,
with the reason recorded in §17.1.

---

## 17. AI-03-A closeout record

```text
Phase              = AI-03 Context Plugin
Sub-phase          = AI-03-A Contract / Execution Plan / Freeze
Status             = COMPLETE
Base branch        = main
Base SHA           = 8c5df3e085e15e39f901e83f53f0e04f693cfb84
Working tree       = clean at start
Work branch        = feature/ai-03-context-plugin
Files changed      = docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md (new)
Production code    = 0 lines changed
Source adapter     = not written
Cache              = not written
Resolver           = not written
Router code        = not written
Guard code         = not written
Evidence code      = not written
SecurityLab        = untouched
Live API calls     = none
Secrets added      = none
```

### 17.1 Amendment log

**Amendment 1 — 2026-09-29 — `ContextStatus` must not use the word `COMPLETE`.**

A conflict was found between §5.8 and §5.4 during implementation. §5.8 defined the
context-build status as `COMPLETE / PARTIAL / UNKNOWN`, and §5.4 states that `COMPLETE`
is a lifecycle word that is *not* a truth state and must never be laundered into one.

Neither section is wrong alone. §5.8 is answering *did every declared source get read?*,
which is a question about the build; §5.4 is answering *is there a truth-model claim
here?*, which is a question about a declaration. The defect is that one word was serving
both. A build status spelled `COMPLETE` sits one refactor away from being read as a
phase's `COMPLETE`, which is precisely the promotion §5.4 forbids — and the same word
already appears in `docs/PROJECT_STATUS.md` as a phase declaration, so the collision is
live in this repository's own data rather than hypothetical.

§5.4 governs. §5.8 was the inconsistent side and is corrected: the value is `FULL`.

```text
FULL      every declared source was READ
PARTIAL   at least one source was not READ, and at least one was READ
UNKNOWN   no declared source was READ
```

Corrected in: §5.8 (values and rationale). Amendment 1 is additionally pinned by
`tests/context/test_vocabulary.py::TestOtherEnumsAreFrozen::test_context_status_avoids_the_lifecycle_vocabulary`,
so the word cannot return to the enum silently.

No boundary, scope, or deliverable changed. No other frozen semantics changed — not the
priority table, the truth model, the item kinds, the classification rule, the cache key,
the freshness rule, or the conflict ordering. Documentation only: zero production code
existed at the time of the amendment.
