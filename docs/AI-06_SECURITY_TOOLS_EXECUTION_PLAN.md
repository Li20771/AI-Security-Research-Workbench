# AI-06 — Security Research Tools Plugin Execution Plan

> Status: **FROZEN** (AI-06-A, 2026-10-01)
> Phase: AI-06 — Security Research Tools Plugin
> Sub-phase: **AI-06-A — Contract / Execution Plan / Freeze**
> Prerequisite: AI-00 architecture freeze + AI-01 DSH Baseline + AI-02 Model Layer + AI-03 Context Plugin + AI-04 Guard Plugin + AI-05 Evidence Plugin (all COMPLETE and merged)
> Base branch: `main`
> Base SHA: `8ba99efb8378853524d04ca0e9b7b62feb3cd780`
> Rule: This document defines the contract. AI-06-B implements against it. Nothing in AI-06 may
> deviate from a frozen contract without amending this document first (§18).

---

## 1. Purpose

AI-06 gives the Workbench one way to run a research tool and one way to describe what happened.

```text
Agent
  |
  v
AI-06 Tool API          build a ToolRequest; refuse one that is malformed
  |
  v
AI-04 Guard             ALLOW | DENY | BLOCKED | UNKNOWN     <- the authorization
  |
  v
AI-06 adapter           run the operation, under a declared boundary
  |
  v
ToolResult              what happened                          <- the execution fact
  |
  v
AI-05 Evidence          a normalized, attributable record      <- AI-06 projects, AI-05 records
```

**AI-06 does not authorize.** It asks Guard, and it obeys the answer. It is the only layer that
executes anything, and the reason it exists is so that execution happens in one auditable place
rather than in whatever code happened to need a subprocess.

### 1.1 Authority boundaries, stated once

```text
Tool is a capability.      It does not decide whether it may run.
Guard is the authorization. It decides; it never executes (AI-04 §1, §22).
Evidence is the record.     It records; it adjudicates nothing (AI-05 §26).
```

The three vocabularies stay distinct (§6.3, §9.2): a tool result is not an authorization, and an
authorization is not a result.

### 1.2 What AI-06-A delivers

```text
docs/AI-06_SECURITY_TOOLS_EXECUTION_PLAN.md   this document
```

No production code, no adapter, no registry, no test. AI-06-B implements against this.

---

## 2. Normative Language

```text
MUST       a requirement. AI-06-B that violates it is not conformant.
MUST NOT   a prohibition.
FROZEN     the rule is binding and changes only by amendment (§18).
DEFERRED   declared, and deliberately not decided here.
OPEN       named as unresolved, with a stated default.
```

A rule that is not enforced by code and not checked by a test is a comment. Every FROZEN rule in
this document is required to have one or the other in AI-06-B (§19, §20).

---

## 3. Scope

### 3.1 In scope

```text
the Tool API: identity, request, result, descriptor, registry, adapter boundary
the eight adapter families and their v1 operations
the Guard boundary: how a tool invocation is authorized
the Evidence boundary: how an execution becomes a record
the workspace boundary, the execution boundary, the vehicle boundary, the secret boundary
the repository layout AI-06 owns
the test matrix and the exit gates
```

### 3.2 Out of scope

```text
any tool's own functionality      AI-06 does not reimplement git, Ghidra, AFL++ or YARA
model routing                     AI-07 is DEFERRED; AI-06 builds no Router interface
SecurityLab integration           F-02, F-17: a separate workspace, and AI-06 does not read it
real vehicle control, real ECU, real CAN
a policy engine                   Guard owns authorization; AI-06 supplies the request
an evidence store                 AI-05 owns it; AI-06 projects and does not persist
credential management, MCP marketplace, remote shell platform
```

### 3.3 Non-goals, restated as the boundary

```text
AI-06 is NOT:
    a permission system
    a second Guard
    an evidence store
    a secret scanner
    a router
    a workflow engine
    a benchmark runner
    a remote execution platform
```

### 3.4 What already exists, and what this contract does with it

AI-06 is not written on a blank page. These already exist and are **transcribed or reconciled here,
never contradicted**:

```text
MASTER_ROADMAP.md §1.1 Tool boundary     the eight families, verbatim            (§5.3)
AI-00 §5, §6, §7, §8, §10                the plugin, the permission ladder, the vehicle
                                         rail, the git rules, the truth model    (§6.2, §12, §13.1, §15.4)
AI-00 F-08, F-09, F-14, F-15, F-17       the vehicle rail, the default-authority rule,
                                         the adapter/plugin split, durability    (§4.1, §12, §15)
AI-04 §4.1, §4.2, §9.1, §16, §21, D-11,
        D-12                             the request shape, the closed vocabularies,
                                         the policy-parameter rule, the real-target gate,
                                         the fail-closed matrix, the two permanent
                                         BLOCKED levels                         (§6.1, §6.2, §9)
AI-05 §6.5, §11.1, §26, §29.1            the two registered AI-06 events, the execution
                                         payload, the "claim with a producer" rule,
                                         the no-merged-status rule               (§8.2, §15)
tools/mcp/README.md                      "MCP connectivity is a capability only.
                                         Guard determines whether a server, resource,
                                         or action is eligible in the current context."
                                                                                 (§13.5)
tools/terminal/README.md                 the Guard-before-execution rule, and the
                                         "shell operations" wording reconciled in §13.4
workspaces/workspaces.example.yaml       SecurityLab declared but `enabled: false` and
                                         `access_profile: readonly`              (§10.2)
.github/pull_request_template.md         the per-PR safety checklist every AI-06 PR
                                         answers: no secrets, no direct main change,
                                         no history rewrite, no unauthorized system
                                         change, no real CAN/ECU/vehicle access
```

Two consequences worth stating plainly:

```text
AI-06 registers no new Evidence event. AI-05 §6.5 already carries both AI-06 rows, so a new
  event would be an amendment to AI-05's frozen registry and not an AI-06 decision (§15.7).

AI-06 does not resolve AI-00 §17's open questions. The tool schema's version, multi-workspace
  discovery and credential management are named there as open, and §10.2, §14.2 and §23 record
  what v1 does instead — which is to refuse rather than to decide.
```

---

## 4. Repository layout

### 4.1 The split is AI-00's, not AI-06's

**F-14 is already frozen**: *"Research tool adapters are separate from the Security Tools plugin."*
AI-06 therefore occupies two trees, and this is a transcription of F-14 rather than a new decision:

```text
plugins/security_tools/    the PLUGIN: the Tool API, the registry, the boundaries,
                           and the projections. No adapter lives here.
tools/<family>/            the ADAPTERS: one package per family. No policy,
                           no registry, no Guard call lives here.
```

The plugin defines the `ToolAdapter` protocol; the adapters implement it; the registry composes
them. The dependency runs one way:

```text
tools.<family>  ->  plugins.security_tools.adapter   (implements the protocol)
plugins.security_tools  ->  never imports tools.*    (so there is no cycle)
tools/__init__.py       ->  the default registry, which imports all eight families
```

### 4.2 FINDING: three scaffold directories cannot be Python packages

The AI-06 scaffolds were created as placeholders before any code existed, and three of their names
contain a hyphen. A hyphen is not valid in a Python identifier, so those directories **cannot be
imported** and cannot hold the modules this contract requires:

```text
plugins/security-tools          cannot be a package
tools/vehicle-network           cannot be a package
tools/reverse-engineering       cannot be a package
```

They are not merely inconvenient: `plugins/security_tools/__init__.py` is required by §4.1, and a
directory named `security-tools` cannot contain it.

**Resolution, frozen here.** The three are renamed to identifiers, and the two documents that name
them move in lockstep:

```text
plugins/security-tools     ->  plugins/security_tools
tools/vehicle-network      ->  tools/vehicle_network
tools/reverse-engineering  ->  tools/reverse_engineering
```

```text
tests/unit/test_repository_layout.sh   the required_dirs list
plugins/README.md                      the plugin-layer list
tools/README.md                        the family list
```

`tests/unit/test_repository_layout.sh` is executed by Layer 0
(`check_repository_layout`), so this rename changes a gate and MUST be done with the test updated
in the same commit. The other five family names (`git`, `github`, `tests`, `terminal`, `mcp`,
`firmware`) are already valid identifiers and MUST NOT be renamed.

This is a correction of AI-06's own placeholder, made in AI-06's own phase. It changes no frozen
architecture: F-14's split is preserved exactly, and only the spelling of three directory names
changes.

### 4.3 The plugin package

```text
plugins/security_tools/
    __init__.py        the public surface
    vocabulary.py      the closed vocabularies this contract owns
    identity.py        ToolIdentity, AdapterFamily
    descriptor.py      ToolDescriptor, OperationSpec
    request.py         ToolRequest
    result.py          ToolResult, ToolOutcome, the outcome projection
    adapter.py         the ToolAdapter protocol
    registry.py        ToolRegistry — description only, never authorization
    dispatch.py        invoke(): validate, ask Guard, obey, run, project
    evidence.py        the ToolResult -> AI-05 ToolCall projection
    redaction.py       the secret projection applied to every result
    errors.py          the refusal vocabulary
```

Exact module names are AI-06-B's to place; the responsibilities are frozen.

---

## 5. Tool identity

### 5.1 Three things, never one

```text
tool identity      what the tool IS             ToolIdentity
tool invocation    what is being asked for      ToolRequest
tool result        what happened                ToolResult
```

A shell string is none of these. **A `ToolRequest` MUST NOT be, and MUST NOT contain, a free-form
command line** (§11.4). An invocation names a declared operation and supplies arguments to it.

### 5.2 ToolIdentity

```yaml
tool_id:        string      # stable; identifies the tool, not a version of it
tool_version:   string      # the adapter's declared version
adapter_family: git|github|tests|terminal|mcp|vehicle_network|firmware|reverse_engineering
```

```text
tool_id        FROZEN: stable across versions. Two versions of one tool share a tool_id and
               differ in tool_version. It is NEVER an authorization input (§9.4).
tool_version   FROZEN: part of identity, so a result is attributable to a build.
adapter_family FROZEN: a closed vocabulary owned by AI-06 (§5.3).
```

### 5.3 AdapterFamily — FROZEN

```text
AdapterFamily — closed, owned by AI-06

    git
    github
    tests
    terminal
    mcp
    vehicle_network
    firmware
    reverse_engineering
```

Exactly these eight, and the set is a transcription rather than a choice. `docs/MASTER_ROADMAP.md`
§1.1 **Tool boundary** already freezes it:

> *"The first-class tool adapter families are Git, GitHub, Terminal, MCP, Tests, Vehicle Network,
> Firmware, and Reverse Engineering. The Security Tools plugin composes these adapters."*

The member spellings are lowercased and made into identifiers so that each one names exactly one
directory under `tools/` after §4.2 — `vehicle_network` and `reverse_engineering` carry the
underscore because the roadmap's "Vehicle Network" and "Reverse Engineering" do, and because a
hyphen cannot appear in an import. A ninth family requires an amendment (§18).

`terminal` is a family, not an escape hatch: §11.4 constrains it, and it is not the mechanism by
which the other seven do their work.

### 5.4 Capabilities

A tool declares the operations it supports as `OperationSpec` entries (§7.2). `capabilities` on a
descriptor is the set of declared operation names.

```text
FROZEN: a declared capability is a DESCRIPTION of what the adapter can do.
        It is not a grant, not a permission, and not evidence that anything ran.
```

---

## 6. ToolRequest

### 6.1 Shape — FROZEN

```yaml
schema_version: 1

workspace:
  workspace_id: string        # REQUIRED, non-empty
  root: string|null           # the declared root; NEVER discovered (§10.2)

tool:
  tool_id: string
  tool_version: string
  adapter_family: git|github|tests|terminal|mcp|vehicle_network|firmware|reverse_engineering

operation: string             # MUST be declared by the tool's descriptor (§7.2)

arguments: {}                 # validated against the operation's schema (§7.3)

actor:
  id: string
  type: human|agent|service|unknown

permission_level: read|analyze|test|modify|system-change|remote-change

target:
  kind: repository|filesystem|system|service|network|remote|can_bus|ecu|vehicle|actuator|provider|secret_material|unknown
  identifier: string|null
  environment: simulated|isolated|real|unknown|null
  interface: simulator|isolated_harness|vcan|can|can_fd|lin|ethernet|unknown|null
  is_real: bool|null
  sensitivity: public|internal|confidential|secret_material|unknown|null

execution:
  timeout_seconds: integer    # REQUIRED; there is no default and no "no timeout"
  environment: {}             # the child environment, stated explicitly (§11.3)

approval:
  status: VERIFIED|MISSING|INVALID|UNKNOWN
  scope_digest: string|null
  reference: string|null
```

Every closed vocabulary above is **AI-04's, imported and not restated** (AI-04 §4.2). AI-06 declares
no second permission vocabulary, no second target vocabulary and no second actor vocabulary. If
AI-04's sets change, AI-06's field changes with them, because it is the same type.

### 6.2 `permission_level` is supplied, never inferred — FROZEN

```text
AI-06 MUST NOT infer permission_level from:
    the operation name
    the tool_id
    the adapter_family
    the target kind
    any string that looks dangerous
    any pattern match on arguments

permission_level is REQUIRED on every ToolRequest and is supplied by the caller.
```

This is AI-04 §4.1 applied one layer out, in AI-04's own words:

> *"An implementer must never infer the permission level from `action.id`. The level is a frozen
> architectural concept (AI-00 §6, F-09); encoding it in an opaque action identifier loses it,
> makes policy rules that key on it unwritable, and makes two requests that differ only in
> privilege indistinguishable to the evaluator."*

A guard that inferred the level would be deciding privilege from a name, which is exactly the
defect F-09 exists to prevent. An operation whose level is not obvious is a design smell, not an
invitation to guess.

### 6.3 The three result vocabularies stay distinct — FROZEN

```text
ToolOutcome       did the operation execute            AI-06 owns it   (§8.2)
GuardDecision     may the operation proceed           AI-04 owns it   (ALLOW|DENY|BLOCKED|UNKNOWN)
StatusValue       what is the state of this item      AI-03 owns it   (PASS|FAIL|BLOCKED|NOT_RUN|UNKNOWN)
```

They MUST NOT be merged into one enum, one string, or one field. `ToolOutcome` is projected into
`StatusValue` in exactly one place, for Evidence, by one function (§9.3); that projection is
one-way and total, and no code path converts a `StatusValue` back into a `ToolOutcome`.

The words `BLOCKED` and `UNKNOWN` appear in more than one of these vocabularies. That is a known
cost, recorded by AI-04 §3 as a defect AI-03 already paid for once. AI-06 does not merge the
vocabularies to remove it; it keeps the types distinct so that a reader can always tell which
question a value answers.

---

## 7. ToolDescriptor and the capability registry

### 7.1 What a descriptor answers

```yaml
tool_id: string
tool_version: string
adapter_family: <closed>
summary: string                 # what the tool is, bounded single-line text
operations: [OperationSpec]
```

### 7.2 OperationSpec — FROZEN

Every operation MUST declare:

```yaml
name: string
permission_level_floor: read|analyze|test|modify|system-change|remote-change
summary: string
arguments_schema: {}          # §7.3
target_kinds: [<TargetKind>]  # which targets the operation may name
environment_required:         # §11.2; what the operation needs in order to run at all
    filesystem: none|read|write
    subprocess: bool
    network: bool
    vehicle_interface: none|vcan|simulator|isolated_harness|physical
may_modify_workspace: bool
produces_artifacts: bool
```

`permission_level_floor` is a **description of the operation**, not a grant: it states the lowest
level at which the operation is meaningful, so that a caller cannot ask for `git.push` at `read`
without the mismatch being visible. It MUST NOT be used as the request's `permission_level`
(§6.2) and MUST NOT be used by AI-06 to authorize anything (§7.4).

### 7.3 The argument schema

```text
FROZEN: an operation's arguments are validated against its declared schema BEFORE Guard is asked.
        An argument the schema does not define is REFUSED, not ignored.
        A missing required argument is REFUSED.
```

A schema AI-06 cannot enforce is not a schema. AI-06-B MUST implement a bounded schema vocabulary
sufficient for its own operations — types, required/optional, bounds, enumerations — and MUST NOT
adopt a general-purpose validation framework for v1.

### 7.4 The registry describes; it does not authorize — FROZEN

```text
ToolRegistry MUST NOT:
    decide whether an operation may run
    hold, consult or imply a policy
    call Guard
    hold credentials or tokens per tool
    discover tools at runtime from an untrusted source
```

```text
ToolRegistry MAY:
    answer what tools exist
    answer what operations a tool declares
    answer what a tool needs in order to run
    hand back an adapter for a declared (tool_id, tool_version)
```

A registry that decided authorization would be the second permission system this contract exists to
prevent. If a rule about whether an operation may run cannot be expressed as an AI-04 policy over
the request, it does not belong in AI-06.

### 7.5 Registration is static

```text
FROZEN: the v1 registry is built from a fixed, in-repository declaration.
        No runtime discovery, no remote manifest, no dynamic plugin loading.
```

This is the boundary AI-01 §Q and the roadmap leave open about workspace discovery, and AI-06 does
not resolve it by inventing a loader.

---

## 8. ToolResult

### 8.1 Shape — FROZEN

```yaml
schema_version: 1

tool_id: string
tool_version: string
operation: string

outcome: COMPLETED|FAILED|BLOCKED|NOT_RUN|TIMED_OUT|UNKNOWN

reason_code: string           # a stable machine-readable label, never prose
started_at: string|null
duration_ms: integer|null     # null when unmeasured, NEVER 0
exit_code: integer|null       # null when no process ran

stdout: string                # sanitized and bounded (§14)
stderr: string                # sanitized and bounded (§14)
truncated: bool               # whether either stream was cut
structured: {}                # the operation's declared output shape, when it has one

guard:                        # the authorization this execution ran under
    decision: ALLOW|DENY|BLOCKED|UNKNOWN
    reason_code: string
    decision_id: string

target: {<TargetRef, as requested>}
workspace_id: string
```

### 8.2 ToolOutcome — FROZEN

```text
ToolOutcome — closed, owned by AI-06

    COMPLETED     the operation ran and the adapter reports it finished
    FAILED        the operation ran and the adapter reports it did not succeed
    BLOCKED       a precondition was unavailable, so nothing ran
    NOT_RUN       deliberately not executed
    TIMED_OUT     the operation exceeded its declared deadline and was stopped
    UNKNOWN       the operation's completion could not be established
```

**A ToolOutcome is a claim by the adapter about the OPERATION.** It is never a claim about the
research question, and never a claim about truth. AI-05 §26 states the rule AI-06 inherits:

> *"A tool's own claim of success is a claim with a producer. AI-05 records the claim and its
> producer. It adjudicates nothing."*

```text
FROZEN: a test runner's own result vocabulary — pytest's "N passed", a shell test's exit status,
        a fuzzer's crash count — is STRUCTURED OUTPUT. It MUST NOT be lifted into ToolOutcome.
        A pytest run that reports N passed produces ToolOutcome.COMPLETED and structured output
        saying so. It does not produce a research verdict (§9.2).
```

`TIMED_OUT` exists because a killed process is a different execution end-state from one that ran and
failed; folding it into `FAILED` would lose the fact that the operation was stopped (§9.3 records
what the projection costs).

### 8.3 The result is attributable

Every result carries `tool_id`, `tool_version`, `operation`, `workspace_id`, and the `guard` block
naming the decision it ran under. A result that cannot be attributed to a tool, a version, an
operation, a workspace and an authorization is not a result this contract produces.

---

## 9. Guard boundary

### 9.1 Every execution asks Guard — FROZEN

```text
FROZEN: no adapter, and no path through AI-06, executes anything without a Guard decision of
        ALLOW for the operation being invoked.

FROZEN: AI-06 does not cache, widen, or reuse an authorization. One decision authorizes one
        invocation, as stated in that invocation's request. A second invocation asks again.
```

`Guard.evaluate(request, policy)` is AI-04's frozen signature. AI-06 calls it; it does not wrap,
extend, reimplement or shadow it, and it does not evaluate a policy itself.

### 9.2 AI-06 obeys the decision — FROZEN

```text
ALLOW     the adapter MAY run, within the request it was granted
DENY      the adapter MUST NOT run; ToolOutcome is NOT_RUN with the reason carried
BLOCKED   the adapter MUST NOT run; ToolOutcome is BLOCKED with the reason carried
UNKNOWN   the adapter MUST NOT run; ToolOutcome is UNKNOWN with the reason carried
```

```text
FROZEN: DENY, BLOCKED and UNKNOWN are all refusals to execute. There is no ordering among them
        that permits execution, and no path converts one into an ALLOW. AI-04 §21's closing
        assertion — "No path converts one of the non-authorizing states into ALLOW" — applies
        to AI-06 unchanged.
```

A refused request produces a **ToolResult**, not an exception and not silence: the refusal is an
outcome, and §8 supplies the vocabulary for it.

`docs/GIT_AND_SECURITY_BOUNDARY.md` §Fail-closed already states the consequence for the Workbench
as a whole, and AI-06 is bound by it:

> *"尤其禁止：Guard 异常时自动放行 / Tool unavailable 时自动跳过限制 / Test unavailable 时自动标
> PASS."*

```text
AI-06 MUST NOT continue when Guard raises rather than returns a decision.
        An evaluator that failed is not an evaluator that allowed (§11 of AI-04 §21's matrix).
AI-06 MUST NOT skip a restriction because a tool is unavailable.
AI-06 MUST NOT mark anything PASS because a test could not be run.
```

That last line is §15.4 from the other side, and it is the failure mode this whole phase is
arranged to prevent.

### 9.3 Where the shapes meet

AI-06 builds the mapping and owns nothing else about it:

```text
ToolRequest.workspace        ->  GuardRequest.workspace
ToolRequest.actor            ->  GuardRequest.actor
ToolRequest.target           ->  GuardRequest.target
ToolRequest.permission_level ->  GuardRequest.action.permission_level
ToolRequest.approval         ->  GuardRequest.approval
ToolRequest.operation        ->  GuardRequest.action.id       (opaque; NOT the level, §6.2)
```

`GuardRequest` has **no field for the tool, the operation's arguments, or a command line**
(AI-04 §4). AI-06 MUST NOT add one, MUST NOT smuggle one through `action.id`, and MUST NOT put
tool arguments into any field AI-04 hashes — an argument set is not authorization input, and a
credential in `action.id` would reach the decision record (AI-04 §17, §18.3).

### 9.4 Guard is a parameter, as it is for every other caller

AI-06 does not discover, load, select or store a policy. It is handed an evaluator, exactly as
AI-04 requires of every caller (§9.1 of that contract). Q-1 — where policy files live — remains
AI-04's open question and AI-06 does not resolve it.

---

## 10. Workspace boundary

### 10.1 One workspace per invocation — FROZEN

```text
every ToolRequest names exactly one workspace_id
the execution is confined to that workspace's declared root
the Guard request carries the same workspace_id
the Evidence projection carries the same workspace_id
```

A result whose workspace disagrees with its request is a defect, not a value to reconcile.

### 10.2 No discovery — FROZEN

```text
AI-06 MUST NOT:
    walk to a parent directory looking for a repository root
    scan sibling directories for other repositories
    read, list or reference SecurityLab
    consult a workspace registry to guess which workspace was meant
    infer a workspace from the current working directory
```

F-02 and F-17 make SecurityLab a separate workspace that owns its own research truth. A tool layer
that could wander into it would make every boundary above it advisory.

The workspace root is **declared on the request** (`workspace.root`) or supplied by the caller when
the request is built. When it is absent, an operation that needs a filesystem MUST be refused
rather than defaulting to anything.

### 10.3 Path containment

```text
FROZEN: every filesystem path an operation touches MUST resolve inside the declared root.
        A path that escapes — by `..`, by an absolute path, by a symlink, or by a
        platform-specific form — is REFUSED before the operation runs.
```

This is checked by resolution, not by string inspection. AI-03 §7.4's precedent — a read-only git
reader that refuses writes by executing the guard rather than by describing it — is the standard:
the check runs, and a test proves it fires.

---

## 11. Execution boundary

### 11.1 argv, never a shell string — FROZEN

```text
FROZEN: AI-06 MUST NOT execute through a shell.
        No `shell=True`, no `sh -c`, no `cmd /c`, no string interpolation into a command line.
        An operation executes an argv vector, as a list, with no shell between AI-06 and the process.
```

A `shell=True` "universal adapter" is the single defect that would make everything else in this
contract decorative: it converts a declared operation with a validated schema into arbitrary
command execution, and it does so in the one layer whose entire purpose is to be auditable. The
`terminal` family (§13.4) is constrained by this rule, not exempted from it.

### 11.2 Declared environment, never inherited wholesale — FROZEN

```text
the child environment is built from `execution.environment` plus a minimal, declared baseline
the parent environment is NEVER passed through wholesale
```

`os.environ` contains API keys, tokens and session state. Passing it to a subprocess gives every
tool the Workbench's credentials, and putting it in a result leaks them into Evidence (§14).

### 11.3 Timeouts are required

```text
FROZEN: every operation declares a timeout; a request that omits one is REFUSED.
        There is no "no timeout" and no infinite default.
```

A tool that hangs is a tool that has taken the session with it. `TIMED_OUT` (§8.2) is the outcome,
and the process MUST be terminated rather than abandoned.

### 11.4 The terminal family is not a universal executor — FROZEN

```text
FROZEN: `terminal` runs a declared, allowlisted program with validated arguments.
        It does not accept a command string, a pipeline, a redirect, a subshell, a glob the
        program would not expand itself, or an environment assignment prefix.
```

An operation is a named program plus typed arguments. Anything a shell would interpret is refused
by the argument schema before it reaches a process.

### 11.5 Exit codes are facts, not verdicts

```text
exit_code is recorded as it was observed.
A non-zero exit is not an AI-06 failure and does not by itself make ToolOutcome FAILED:
some tools report a finding through their exit status.
The adapter decides ToolOutcome from the operation's declared semantics, and states that
mapping in the OperationSpec.
```

### 11.6 Processes AI-06 must not create

```text
FROZEN: no adapter spawns a process outside the declared operation it implements.
        no adapter starts a background, detached or daemon process.
        no adapter runs a second process to interpret the first (no `bash -c`, no `python -c`).
```

---

## 12. Vehicle-network boundary

This is the highest-consequence family in AI-06 and it is stated as a negative contract, following
AI-04 §16.

### 12.1 What v1 may reach — FROZEN

```text
vcan
simulator
isolated harness
```

### 12.2 What v1 must never reach — FROZEN

```text
real CAN interface
real ECU
real vehicle
unknown external CAN gateway
uncontrolled ECU flashing
physical actuation
```

AI-00 §7 is explicit that this is not a prompt-level convention:

> *"任何例外都不能通过'提示词约定'实现，而必须由可执行 Guard 控制。"*

### 12.3 Two checks, and they are not the same check — FROZEN

```text
AI-04's gate   authorizes, or does not, the target the request declares.
AI-06's check  refuses a request whose target cannot be expressed within the v1 boundary
               at all, before Guard is asked.
```

AI-06 MUST fail closed here. A target whose environment or interface is `unknown`, or whose
classification cannot be settled from the request, MUST be refused by the adapter — never treated
as a simulated one by default. AI-04 §16 blocks rather than assuming; AI-06 does the same, and does
not treat "the user probably meant vcan0" as a classification.

The adapter-level check is a **second gate, not a replacement**. Both must pass.

### 12.4 Physical interfaces are named, not pattern-matched

```text
FROZEN: the adapter decides from `target.interface` and `target.environment`, which are closed
        vocabularies, and from the resolved interface name where one exists.
        It MUST NOT decide by pattern-matching an identifier string.
```

An interface called `vcan0-test` is not physical and an interface called `can0` is not simulated;
the classification is a declared fact, not a guess about a name.

### 12.5 Real hardware is not unreachable by accident

A request naming a real interface is refused by AI-06 with `BLOCKED` and a reason code, and the
refusal is a `ToolResult`. It is not an exception, and it is not a silent downgrade to a simulated
target. AI-06 MUST NOT substitute a different interface to make an operation succeed.

---

## 13. v1 family scope

Each family's v1 operations are frozen as a **minimum**, not a maximum: AI-06-B may add operations
within a family by declaring them, and MUST NOT add a family without an amendment (§18).

### 13.1 git

```text
status              read
current_sha         read
current_branch      read
diff                read
log                 read
read_file           read
```

```text
FROZEN: no operation in v1 performs a write to git. There is no commit, no push, no merge,
        no reset, no checkout, no branch mutation, and no history rewrite.
```

AI-03 already freezes a read-only git reader and asserts the refusals by executing the guard
(AI-03 §7.4). AI-06's git adapter MUST NOT widen that. `permission_level_floor` for every v1 git
operation is `read`.

A git write, if it ever exists, is a higher-level operation, requires an approval source that AI-04
does not have (§8.2 of that contract), and is therefore `BLOCKED` today. AI-06-B MUST NOT implement
one to have something to test.

### 13.2 github

```text
FROZEN: v1 defines the adapter boundary and no networked operation.
        Every github operation requires network (§11.2) and is therefore refused by the
        execution boundary until a network-capable operation is declared and authorized.
```

The roadmap lists GitHub as a first-class family, and AI-06-A declines to open it. This is
deliberate (§14): AI-02 spent four sub-phases making live network access opt-in, gated and
manual, and an adapter that reached the network because "a tool exists" would undo that.

### 13.3 tests

```text
pytest              run a pytest selection inside the workspace root
shell_test          run a declared test script
repository_validation   run the repository's own validators
```

```text
the runner's own output is `structured` (§8.2) and is NOT lifted into ToolOutcome
the runner's PASS is NOT a research verdict and NOT an Evidence PASS (§9.2, §16)
```

### 13.4 terminal

```text
run                 a declared program with validated arguments, inside the root
```

Constrained by §11.1, §11.3 and §11.4. `terminal` is not the implementation of the other seven
families, and an operation that could be expressed in a family adapter MUST NOT be routed through
`terminal` to avoid declaring it.

**Reconciling an existing document.** `tools/terminal/README.md` already carries normative text:

> *"The adapter must check Guard policy before command execution and emit structured Evidence.
> High-impact shell operations require explicit Guard approval."*

Both sentences are consistent with this contract and neither is weakened: the first is §9.1 and
§15.2, and the second is §9.1 with the approval state carried by §6.1.

The phrase **"shell operations"** is read here as *"operations run through the terminal adapter"*,
not as *"operations that use a shell interpreter"*. §11.1 forbids the interpreter outright and
without exception; the README's sentence is about which operations need approval, which is a
different question. This reading is recorded rather than assumed, because a reader could take the
word the other way — so AI-06-B MUST tighten that README's wording when it updates the file for
§4.2, and the tightened wording MUST NOT change its meaning.

### 13.5 mcp

```text
FROZEN: v1 defines the adapter boundary only — one operation shape, one result shape,
        provenance preserved.
```

```text
out of scope, explicitly: MCP server discovery, a marketplace, a credential manager,
unbounded dynamic tool loading, and any operation that reaches a network without declaring it.
```

The boundary exists so that a later phase has somewhere to stand, and so that AI-06-B can test the
adapter protocol against a shape that is not git. It is not a platform.

### 13.6 vehicle_network

```text
vcan_can_send       can-utils send onto a vcan interface
vcan_can_dump       can-utils receive from a vcan interface
isotp_exchange      an ISO-TP exchange over vcan
uds_request         a UDS request over vcan
capture_start       begin a capture on a vcan interface
capture_stop        end a capture
replay              replay a captured frame set onto a vcan interface
```

Every operation is constrained by §12. The adapter MUST refuse a target that is not `vcan`,
`simulator` or `isolated_harness` (via `target.interface` and `target.environment`), and MUST NOT
be able to reach a physical interface even if one is present on the host.

### 13.7 firmware, and 13.8 reverse_engineering

```text
qemu                firmware      run an image under emulation
gdb                 firmware      a bounded debug session
afl_fuzz            reverse_engineering   a bounded fuzzing run
yara_scan           reverse_engineering   scan bytes against rules
firmware_unpack     firmware      a declared unpacking operation
```

```text
FROZEN: v1 covers identity, declared capabilities, argument schemas, the execution boundary
        and a uniform result. It does not reimplement QEMU, GDB, Ghidra, AFL++, YARA or any
        firmware utility, and it does not embed one.
```

Ghidra is listed by the roadmap and is **NOT_RUN** in AI-06 v1: its integration is a JVM
headless-analyzer concern this phase does not take on. The family is declared; the operation is
not.

---

## 14. Secret boundary

### 14.1 What is forbidden — FROZEN

```text
AI-06 MUST NOT write into a ToolResult, and MUST NOT let reach Evidence:
    an API key or token
    an Authorization header or any credential header
    a private key or certificate material
    a session token, cookie or connection string
    a raw environment dump
    a resolved credential value of any kind
```

### 14.2 No credential ingress — FROZEN

```text
AI-06 does not manage, store, resolve, refresh or persist credentials.
A credential is not a tool argument, is not an environment key AI-06 adds, and is not a field
on any AI-06 type.
```

The credential question is AI-02's and remains open (AI-00 §17). AI-06 does not resolve it by
carrying one.

### 14.3 Every result is projected before it leaves the adapter — FROZEN

```text
stdout, stderr and structured output pass through an explicit projection before the ToolResult
is constructed. The projection is a named function, not a convention, and a test proves it runs.
```

### 14.4 What AI-06 claims, and what it does not

```text
AI-06 does NOT claim that no secret can appear in a tool result.
A tool can print anything, and a projection is a bounded filter rather than a proof.
AI-06 DOES claim:
    no credential is injected by AI-06 (§14.2)
    the parent environment is not passed through (§11.2)
    every result passes a named projection (§14.3)
    the projection is tested against known-shaped material
```

This is AI-05 §14.1's discipline: a guarantee nobody can test is worse than a smaller guarantee
that holds. AI-06 states the smaller one.

### 14.5 The residual, stated rather than hidden

A tool whose legitimate output happens to contain a long high-entropy string will be truncated or
masked by the projection, and that is the safe direction: over-redaction damages a result, while
under-redaction writes a credential into a durable record. The projection errs toward the first,
and this is recorded rather than left to be discovered.

---

## 15. Evidence boundary

### 15.1 AI-06 projects; AI-05 records — FROZEN

```text
FROZEN: AI-06 does not implement an evidence store, does not call admission, does not write a
        record, and does not define an Evidence schema. It produces a projection, and the caller
        submits it through AI-05's existing entry point.
```

Reimplementing admission would duplicate AI-05's §30 pipeline and its uniqueness rule, both of
which are frozen and tested there.

### 15.2 The projection — FROZEN

```text
one tool invocation
    -> one ToolResult
    -> one AI-05 ToolCall, for use in an ExecutionPayload
```

```yaml
# AI-06 produces, for one invocation:
ordinal:  integer          # assigned by the caller, as AI-05 §11.1 requires
what_ran: string           # "<tool_id>/<operation>" — bounded, single-line, no arguments
status:   StatusValue      # §15.3
```

```text
FROZEN: `what_ran` carries the tool and the operation, NOT the arguments and NOT the raw output.
        AI-05 §26 forbids storing raw tool output inside a record, and an argument set is a
        second place for a credential to reach a durable record.
```

### 15.3 The outcome projection — FROZEN

```text
ToolOutcome     ->  StatusValue (AI-05)
COMPLETED       ->  PASS
FAILED          ->  FAIL
TIMED_OUT       ->  FAIL
BLOCKED         ->  BLOCKED
NOT_RUN         ->  NOT_RUN
UNKNOWN         ->  UNKNOWN
```

The projection is **total** (every outcome maps), **one-way** (nothing maps back) and **the only
place the two vocabularies meet** (§6.3).

```text
The cost of the projection is recorded rather than hidden: StatusValue has no TIMED_OUT, so a
timed-out operation is recorded as FAIL and the fact that it was stopped is carried by the
ToolResult, which is not the record. The Evidence record keeps a normalized summary; the
distinction survives in the result and not in the record.
```

### 15.4 What the projection does not claim — FROZEN

```text
A `status` of PASS in a projected ToolCall means: this operation completed.
It does NOT mean:
    the test suite passed
    the research question was answered
    a capability is VERIFIED
    a Guard decision was ALLOW
    anyone may proceed with anything
```

AI-00 §10 is the authority: a PASS requires *executed and supported by evidence*, and the tool's
completion supplies the first half only. A tool's exit code is a fact about a process, not a
finding about the world.

### 15.5 Raw output is bounded because the record cannot hold it — FROZEN

AI-05 caps a text leaf at `MAX_TEXT_LENGTH = 512` and forbids storing raw tool output inside a
record (§26 of that contract). A tool's stdout is unbounded, so the two facts have one consequence
AI-06 freezes rather than discovers:

```text
the ToolResult carries a sanitized, bounded rendering of the output (§8.1, §14.3)
the Evidence projection carries neither the output nor the arguments (§15.2)
```

`ADR 0004` and `AI-00 F-15` supply the resolution for anything larger: *"raw large logs may be
artifact-only"*. AI-06 v1 does **not** implement an artifact store — offloading bytes and
submitting a reference is **DEFERRED** (§23), and until it exists a large result is truncated and
marked (`truncated: true`) rather than silently shortened. A truncated result is honest about
being truncated; a silently shortened one is a false record of what the tool said.

### 15.6 No new status vocabulary — FROZEN

```text
AI-06 MUST NOT define a `final_status`, a research verdict, a merged `status` field, or any
vocabulary that competes with StatusValue, GuardDecision or CapabilityStatus.
```

AI-05 §29.1 forbids exactly this in the record layer, and AI-06 does not reintroduce it one layer
down.

### 15.7 Both AI-06 registry rows are reachable

AI-05 §6.5 registers two v1 events, and both are real:

```text
AI-06 tool execution    EXECUTION   producer ai-06   actor.type agent
AI-06 test result       EXECUTION   producer ai-06   actor.type service
```

A tool invocation projects into the first; a test-runner invocation into the second. The
distinction is `actor.type`, which is AI-05's frozen registry and not AI-06's to change.

---

## 16. Network boundary

```text
FROZEN: an operation that can reach a network MUST declare `environment_required.network: true`.
        An operation that has not declared it MUST NOT be able to reach one.
FROZEN: no operation is network-capable in v1 (§13.2, §13.5).
```

AI-02 made live connectivity opt-in, allowlisted, manual and non-default across four sub-phases,
and its evidence records that **no provider call has ever been made**. AI-06 MUST NOT reopen that
by giving a tool adapter an HTTP client, and MUST NOT route a provider call through a tool.

---

## 17. Error and refusal vocabulary

```text
FROZEN: AI-06 defines its own refusals, and does not reuse AI-04's or AI-05's error types for
        AI-06 conditions.
```

Each refusal carries a stable `reason_code`, never prose-as-code, and never an interpolated value:
AI-05's error doctrine (§errors) records why — an error message is a place a value escapes to a
log, and an argument is a place a credential can be.

Minimum refusal classes:

```text
ToolRequestMalformed        the request does not match §6.1
UnknownTool                 no such tool_version is registered
UnknownOperation            the tool declares no such operation
ArgumentInvalid             an argument fails the operation's schema
WorkspaceUnresolvable       the declared root is absent or is not a directory
PathEscapesWorkspace        a path resolves outside the declared root
PermissionLevelMissing      permission_level is absent (§6.2)
TargetRefused               the target is outside the v1 boundary (§12.3)
GuardRefused                Guard returned DENY, BLOCKED or UNKNOWN (§9.2)
TimeoutExpired              the declared deadline elapsed (§11.3)
```

A refusal produces a `ToolResult`, not an exception escaping the API. The exception is the
mechanism; the result is the contract.

---

## 18. Contract amendment rule

A frozen rule changes only through an explicit amendment recorded in §22.

An amendment is REQUIRED for any new or changed:

```text
AdapterFamily member            (§5.3)
ToolRequest field               (§6.1)
ToolOutcome member              (§8.2)
OperationSpec field             (§7.2)
the outcome projection          (§15.3)
the repository layout           (§4)
the vehicle boundary            (§12)
the network boundary            (§16)
```

```text
FORBIDDEN:
    a security boundary relaxed so that a test passes
    an operation added to the registry so that something has something to run
    a family added without an amendment
    a second permission, status or target vocabulary
    inference of permission_level from a name
```

---

## 19. Test Matrix

Layers 1–3 only. **AI-06 adds no layer 4** — the plugin has no opt-in live path, and §16 makes
every network operation refused.

No test in this matrix may require: a real network, a real CAN interface, a real vehicle, a
credential, or a provider. Every execution test uses a fake adapter, a fake subprocess runner, a
temporary workspace, or simulated vcan.

| # | Test | Purpose | Expected | Security property |
| --- | --- | --- | --- | --- |
| T1 | well-formed request | baseline | validated | nothing is measurable without it |
| T2 | malformed request refused | shape | refused | a shape violation is never absorbed |
| T3 | unknown tool refused | registry | refused | an unlisted tool is never ordinary |
| T4 | unknown operation refused | registry | refused | as T3 |
| T5 | argument schema enforced | validation | refused | an undeclared argument is never ignored |
| T6 | `permission_level` required | §6.2 | refused when absent | privilege is supplied, never inferred |
| T7 | permission is not inferred | §6.2 | a `read` request for a `modify`-floor operation is not silently upgraded | no name-based privilege |
| T8 | Guard ALLOW executes | §9.2 | the adapter runs | the authorized path works |
| T9 | Guard DENY does not execute | §9.2 | NOT_RUN, adapter not called | refusal is real |
| T10 | Guard BLOCKED does not execute | §9.2 | BLOCKED, adapter not called | as T9 |
| T11 | Guard UNKNOWN does not execute | §9.2 | UNKNOWN, adapter not called | as T9 |
| T12 | no execution without Guard | §9.1 | a missing evaluator refuses rather than runs | fail closed |
| T13 | one decision, one invocation | §9.1 | a second invocation asks again | no cached authorization |
| T14 | workspace confinement | §10.3 | a path escaping the root is refused | containment is checked, not assumed |
| T15 | `..` traversal refused | §10.3 | refused | as T14 |
| T16 | absolute path refused | §10.3 | refused | as T14 |
| T17 | symlink escape refused | §10.3 | refused | as T14 |
| T18 | no parent-directory discovery | §10.2 | no root is inferred | the root is declared |
| T19 | SecurityLab unreachable | §10.2 | no code path names it | the other workspace is untouched |
| T20 | argv, never a shell | §11.1 | no `shell=True` is reachable | no universal executor |
| T21 | shell metacharacters are data | §11.4 | `;`, `\|`, `$( )` reach the program as arguments and are not interpreted | no injection |
| T22 | environment is not inherited | §11.2 | a parent-only variable does not reach the child | no credential passthrough |
| T23 | timeout required | §11.3 | a request without one is refused | no unbounded execution |
| T24 | timeout terminates | §11.3 | TIMED_OUT and the process is stopped | no abandoned process |
| T25 | non-zero exit is not automatically FAILED | §11.5 | the declared mapping decides | an exit code is a fact |
| T26 | stdout/stderr bounded | §8.1 | truncation is marked | output cannot grow without limit |
| T27 | exit code recorded as observed | §8.1 | the value matches | a fact is not normalized away |
| T28 | secret projection runs | §14.3 | a known-shaped key does not appear in the result | results are projected |
| T29 | environment is not dumped | §14.1 | no full environment in any result | as T22 |
| T30 | arguments do not reach Evidence | §15.2 | `what_ran` carries no argument | no credential path into a record |
| T31 | outcome projection is total | §15.3 | every ToolOutcome maps | no unmapped outcome |
| T32 | projection is one-way | §15.3 | no reverse mapping exists | the vocabularies do not merge |
| T33 | runner PASS is not promoted | §8.2, §15.4 | a passing pytest run yields COMPLETED, not a research verdict | exit 0 is not a finding |
| T34 | real CAN refused | §12.2 | BLOCKED, adapter not called | the vehicle boundary holds |
| T35 | real ECU refused | §12.2 | BLOCKED | as T34 |
| T36 | real vehicle refused | §12.2 | BLOCKED | as T34 |
| T37 | unknown interface refused | §12.3 | BLOCKED, never treated as simulated | fail closed |
| T38 | no substitution of a target | §12.5 | a refused interface is not swapped for vcan | no silent downgrade |
| T39 | vcan accepted | §12.1 | the simulated path works | the boundary is not a blanket refusal |
| T40 | git write absent | §13.1 | no write operation is registered | a read-only family stays read-only |
| T41 | no git subprocess for a write verb | §13.1 | refused before a process exists | as T40 |
| T42 | registry does not authorize | §7.4 | the registry has no policy input and calls no Guard | no second permission system |
| T43 | no family is a ninth | §5.3 | the vocabulary is exactly eight | closed means closed |
| T44 | adapter protocol is uniform | §8 | every family returns the same shape | one API, eight families |
| T45 | architecture boundary | §3.3 | parsed with `ast`: no network client, no `shell=True`, no `eval`/`exec`/`compile`, no routing import, no secret logging, no environment dump | the boundary is checked, not promised |
| T46 | regression | non-regression | the pre-existing suite's pass count does not decrease | a phase never trades away existing guarantees |
| T47 | Layer 0 evidence | §20 | the AI-06 Layer 0 check runs and passes | the gate exists and fires |

### 19.1 Notes on the matrix

```text
T8–T13 are the Guard boundary and are the point of the phase. A Tool layer that executes without
  an authorization is the defect this contract exists to prevent; T12 is the one that catches a
  missing evaluator rather than a refusing one.
T20, T21, T22 are one boundary in three parts. T20 alone is satisfied by a shell that happens to
  quote correctly; T21 is the injection test and T22 is the credential test.
T34–T38 are the vehicle boundary. T39 is the control that proves the boundary is a boundary and
  not a refusal of everything — without it, T34–T38 are satisfied by an adapter that never runs.
T33 is the test the whole Evidence boundary turns on. Without it, a tool that exits 0 is one
  refactor away from being recorded as a research PASS.
T45 MUST parse with `ast` and MUST NOT grep. AI-06's own documentation names every hazard it
  avoids, so a text match would fire on its rationale; AI-05's Layer 0 check records the same
  lesson.
```

---

## 20. Exit Gates

AI-06 is complete only when every gate below passes.

| # | Gate | Condition |
| --- | --- | --- |
| C0 | Contract frozen | this document is frozen and its amendment log is open |
| C1 | Tool API implemented | identity, request, result, descriptor, registry, adapter protocol |
| C2 | Adapters implemented | the v1 operations of §13, each returning the uniform result |
| C3 | Guard boundary verified | no execution without ALLOW; DENY/BLOCKED/UNKNOWN refuse |
| C4 | Workspace isolation verified | containment, no discovery, SecurityLab unreachable |
| C5 | Vehicle boundary verified | vcan only; real hardware refused; no substitution |
| C6 | Execution boundary verified | argv only, no shell, declared environment, required timeout |
| C7 | Secret handling verified | projection runs; no credential ingress; no environment dump |
| C8 | Evidence integration verified | the projection is total and one-way; runner output is not promoted |
| C9 | Layer 0 PASS | the AI-06 structural and behavioural check exists and passes |
| C10 | Full offline tests PASS | layers 1–3, with the counts recorded |
| C11 | Required CI PASS | CI green on the head the phase claims |
| C12 | Evidence artifact complete | `docs/AI-06_EVIDENCE_<date>.md` |
| C13 | Scope and diff audit clean | the diff is inside AI-06's paths; AI-02/03/04/05 unmodified |

### 20.1 What is proved / required evidence / forbidden state

```text
C3 — Guard boundary
  Proved     no path executes without an ALLOW for that invocation
  Evidence   T8–T13; the absence of a Guard call is itself a failing test
  Forbidden  an adapter reachable without a decision; a cached authorization; a decision
             widened to cover a second invocation

C5 — Vehicle boundary
  Proved     only vcan, simulator and isolated harness are reachable
  Evidence   T34–T39; a constructed real-target request
  Forbidden  a real interface reachable; an unknown classification treated as simulated;
             a refused target silently substituted

C6 — Execution boundary
  Proved     no shell, no inherited environment, no unbounded process
  Evidence   T20–T25; the AST check in T45
  Forbidden  `shell=True`; a command string; `os.environ` passed through; a request without
             a timeout

C7 — Secret handling
  Proved     the §14.3 projections run, and AI-06 injects no credential
  Evidence   T28, T29; the projection's own tests
  Forbidden  a credential on any AI-06 type; a raw environment in a result; a claim of
             detector completeness

C8 — Evidence integration
  Proved     the projection is total and one-way, and promotes no runner verdict
  Evidence   T30–T33
  Forbidden  a research verdict derived from an exit code; arguments or raw output in a
             record; a second status vocabulary

C9 — Layer 0
  Proved     the AI-06 check is a real gate over the real package
  Evidence   the check runs in Layer 0 and is mutation-tested
  Forbidden  a check that passes on a mutated copy; a text match that fires on documentation
```

---

## 21. AI-06-B — Implementation Execution Brief

```text
branch          feature/ai-06-security-tools-v1, from the then-current real main
PR              exactly one. AI-06 opens two PRs in total and this is the second.
```

The PR MUST contain, in one piece:

```text
the plugin package (§4.3)
the eight adapter family packages under tools/
the registry and the default wiring
the Guard boundary and the dispatch path
the Evidence projection
the redaction projection
the AI-06 Layer 0 check
tests for T1–T47
docs/AI-06_EVIDENCE_<date>.md
docs/PROJECT_STATUS.md and docs/MASTER_ROADMAP.md
```

It MUST NOT contain: a third PR, a Router interface, a SecurityLab integration, a credential
manager, a policy loader, a workflow engine, or a real-hardware path.

Any conflict between this contract and an existing implementation STOPS the work: locate it,
record it, amend this contract (§18), then continue. A test is never made to pass by widening a
schema or lowering a boundary.

---

## 22. Amendment log

```text
(none)
```

---

## 23. Freeze record

```text
AI-06-A   FROZEN    this document
base      main @ 8ba99efb8378853524d04ca0e9b7b62feb3cd780
date      2026-10-01

Frozen here:
    the Tool API shape: identity, request, result, descriptor, registry, adapter protocol
    AdapterFamily, exactly eight
    ToolOutcome, exactly six
    the outcome projection into AI-05's StatusValue, total and one-way
    the Guard boundary: one ALLOW, one invocation, no inference of permission_level
    the Evidence boundary: AI-06 projects, AI-05 records, no new status vocabulary
    the workspace boundary: declared root, no discovery, checked containment
    the execution boundary: argv, declared environment, required timeout
    the vehicle boundary: vcan, simulator, isolated harness only
    the secret boundary, stated as what is claimed and what is not
    the repository layout, including the correction of three hyphenated scaffold names

Not decided here:
    where policy files live            Q-1, AI-04's open question
    the tool schema's final version    AI-00 §17 lists it as open; v1 is version 1
    multi-workspace discovery          AI-00 §17; §10.2 forbids it in v1
    credential handling                AI-00 §17; §14.2 refuses ingress
    artifact offload for large output  DEFERRED; v1 bounds and truncates (§8.1)
    Ghidra integration                 declared as a family, NOT_RUN in v1 (§13.8)
    GitHub operations                  boundary declared, no operation (§13.2)
```

```text
This document freezes a contract. No adapter exists, no registry exists, no tool has run, and
this document is not evidence that any of it works.
```
