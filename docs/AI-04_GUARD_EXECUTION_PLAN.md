# AI-04 — Security Guard Plugin Execution Plan

> Status: **FROZEN** (AI-04-A, 2026-09-29)
> Phase: AI-04 — Security Guard Plugin
> Sub-phase: **AI-04-A — Contract / Execution Plan / Freeze**
> Prerequisite: AI-00 architecture freeze + AI-01 DSH Baseline + AI-02 Model Layer + AI-03 Context Plugin (all COMPLETE and merged)
> Base branch: `main`
> Base SHA: `548bc041b31cc0fc9d01af55c527378ba2c42c48`
> Rule: This document defines the contract. AI-04-B implements against it. Nothing in AI-04 may
> deviate from a frozen contract without amending this document first (§23).

---

## 1. Purpose

Guard is the deterministic, rule-based, workspace-scoped authorization boundary of the Workbench.

Its job is to decide whether a normalized action may proceed under an explicit policy and verified
execution preconditions.

**Guard is authoritative for authorization.**

Guard is not:

```text
Context collection              Evidence persistence         Tool execution
Model routing                   Provider selection           Approval workflow
Security-tool implementation    LLM-based authorization      Policy generation
```

**Status:** `COMPLETE — contract frozen`. This sub-phase contains **no production code**.

**What this sub-phase delivers:** a frozen, reviewable contract for the Workbench authorization
boundary — decision vocabulary, request shape, workspace scope, context and capability and
approval preconditions, the policy and rule and predicate grammar, a total rule ordering, a
canonicalization and digest specification, the fail-closed matrix, and the phased plan for
AI-04-B.

**What this sub-phase explicitly does not deliver:** any implementation, any `plugins/guard/`
production code, any policy file, any approval mechanism.

### 1.1 Freeze semantics

```text
Frozen   = the shape and the rules below are binding for AI-04-B
Deferred = the value or the mechanism is declared but NOT implemented by AI-04
```

A frozen contract is a constraint on implementation. It is **not** a claim that Guard has been
implemented, that any policy exists, or that any action has been authorized.

> Frozen contracts and verified facts are different things. This document freezes the former and
> deliberately does not assert the latter.

### 1.2 Position in the frozen architecture

From `docs/architecture/COMPONENT_MAP.md` and AI-00 `F-07`, `F-13`:

```text
Router selects eligible Agent / Provider / Model profiles. It never grants permissions.
Guard decides whether a selected action may proceed. It never selects.
```

```text
Router != Guard
```

Guard consumes AI-03 Context and AI-02 capability state as **inputs**. It does not collect
context, does not probe providers, and does not persist evidence.

---

## 2. Decision vocabulary

Guard decisions are distinct from Workbench test/result status (§3) and from check results (§18.2).
The three vocabularies share no type.

### 2.1 Guard decision

```text
ALLOW
DENY
BLOCKED
UNKNOWN
```

### 2.2 Meaning

```text
ALLOW
    The request is explicitly authorized and all required safety and
    precondition checks were SATISFIED.

DENY
    The request is known to be prohibited, malformed, out of scope,
    explicitly denied, or rejected by default because no rule authorizes it.
    A completed negative policy decision.

BLOCKED
    Authorization cannot safely proceed because a required
    prerequisite, policy, approval, context, or capability is unavailable,
    invalid, or operationally indeterminate.

UNKNOWN
    An authorization-relevant fact is itself in a definite UNKNOWN truth
    state, carried from an upstream truth model, so the decision cannot be
    promoted to ALLOW.
```

All four values are non-equivalent:

```text
UNKNOWN != ALLOW
BLOCKED != ALLOW
DENY    != ALLOW
```

### 2.3 The scope of `UNKNOWN` (Amendment 1)

`UNKNOWN` is the decision when **an upstream source explicitly carries UNKNOWN truth** and this
contract does not say otherwise. It is a definite statement about a fact: *the fact is unknown*.
It is not a synonym for "we could not look" — that is `BLOCKED`.

A precondition that **this contract owns**, rather than inheriting from an upstream truth model,
may map UNKNOWN to `BLOCKED`. Exactly one precondition does, and §8 states why:

```text
context truth_state = UNKNOWN      -> decision may be UNKNOWN   (§6.3, §21)
capability status   = UNKNOWN      -> decision may be UNKNOWN   (§7, §21)
approval status     = UNKNOWN      -> BLOCKED                   (§8, §21)
```

> The distinction is not cosmetic. "The evidence says the capability is unknown" and "the approval
> record's state is unknown, and this contract is fail-closed about approval" are different
> findings, and a caller that cannot tell them apart cannot tell which one to go and fix.

### 2.4 Why these four and not more

There is no `PARTIAL`, no `CONDITIONAL`, and no `ALLOW_WITH_WARNINGS`. An authorization decision
that is not a clean yes is a no; a caller cannot act on a maybe. Anything that would have been a
qualified allow is expressed as `DENY` plus a `reason_code`, or as `BLOCKED` plus the check that
could not be satisfied.

---

## 3. Test-status vocabulary

Guard's **test suite** reports using the existing Workbench truth model, unchanged:

```text
PASS
FAIL
BLOCKED
NOT_RUN
UNKNOWN
```

This vocabulary describes *executed verification*, not authorization. A test may therefore be:

```text
test status   = PASS
guard decision = DENY
```

which means the test successfully verified that Guard denied the request.

> **`BLOCKED` appears in both §2 and §3.** They are different types with different meanings and are
> never compared, stored in one field, or converted into one another. §18.2 gives the decision
> record its own check vocabulary precisely so that a decision record never has to carry this
> word ambiguously — the collision that AI-03 hit with `ContextStatus.COMPLETE` is avoided by
> typing rather than by convention.

---

## 4. GuardRequest

Minimum semantic fields:

```yaml
schema_version: 1

actor:
  id: string
  type: human|agent|service|unknown

workspace:
  workspace_id: string
  repository: string|null
  branch: string|null
  commit: string|null
  detached: bool
  working_tree: CLEAN|DIRTY|UNKNOWN

action:
  id: string
  permission_level: read|analyze|test|modify|system-change|remote-change

capability:
  id: string|null

target:
  kind: repository|filesystem|system|service|network|remote|can_bus|ecu|vehicle|actuator|provider|secret_material|unknown
  identifier: string|null
  environment: simulated|isolated|real|unknown|null
  interface: simulator|isolated_harness|vcan|can|can_fd|lin|ethernet|unknown|null
  is_real: bool|null
  sensitivity: public|internal|confidential|secret_material|unknown|null

context:
  response: ContextResponse|null

capability_state:
  records:
    - capability_id: string
      status: VERIFIED|DECLARED|NOT_VERIFIED|UNAVAILABLE|UNKNOWN

approval:
  status: VERIFIED|MISSING|INVALID|UNKNOWN
  scope_digest: string|null
  reference: string|null
```

**No credential value, prompt body, provider secret, or raw sensitive payload may enter the Guard
request.** §17 governs.

### 4.1 `permission_level` is first-class (Amendment 5 / N2)

`action.permission_level` is a required, closed-vocabulary field corresponding exactly to the
permission model frozen in AI-00 §6:

```text
read  <  analyze  <  test  <  modify  <  system-change  <  remote-change
```

**An implementer must never infer the permission level from `action.id`.** The level is a frozen
architectural concept (AI-00 §6, `F-09`); encoding it in an opaque action identifier loses it,
makes policy rules that key on it unwritable, and makes two requests that differ only in
privilege indistinguishable to the evaluator.

### 4.2 Closed vocabularies (Amendment 6 / N6)

Every authorization-relevant enumerated type above is a **closed** set:

```text
actor.type              actor.kind is not an authorization input
target.kind
target.environment
target.interface
target.sensitivity
approval.status
capability_state.records[].status
workspace.working_tree
action.permission_level
```

A value outside its set is **not** silently treated as an ordinary value. It is unsupported, it is
fail-closed, and it can never produce `ALLOW` (§11.6, §21).

Open strings are permitted only for business identifiers, where the value is compared literally
and carries no authorization semantics of its own:

```text
actor.id        action.id        workspace.workspace_id     workspace.repository
workspace.branch  workspace.commit  target.identifier      target.kind is closed; identifier is not
capability.id   approval.reference  context subjects
```

### 4.3 The workspace block is a deliberate subset of AI-03's identity

AI-03's `WorkspaceIdentity` carries eight fields; this request carries six. The two omitted are
`workspace_root` and `changed_files`:

```text
workspace_root    a host filesystem path; carries no authorization meaning and leaks
                  machine layout into a digest
changed_files     a count; a rule that keyed on it would be authorizing on a number
                  that changes for reasons unrelated to the action
```

Their absence is a decision, not an oversight. The six that remain are exactly the fields an
authorization decision can legitimately depend on, and they are the six §20.5 hashes.

### 4.4 The request is not a Context store

`context.response` carries an AI-03 `ContextResponse` for precondition evaluation. It is an
**input to a decision**, and the decision record stores only references into it (§18, §19). Guard
does not collect, refresh, merge, or repair context.

---

## 5. Workspace scope

Every Guard evaluation is scoped to exactly one workspace. The following must agree:

```text
request.workspace.workspace_id
policy.workspace_id
context.workspace.workspace_id
all authorization-relevant ContextItem.workspace_id
```

A mismatch is **never** merged, filtered, or repaired. Workspace mismatch is a non-authorizing
security failure:

```text
workspace mismatch -> DENY
```

Guard never discovers, searches for, or aggregates another workspace. There is no cross-workspace
evaluation mode, and no policy may authorize one.

> AI-03 already enforces the item-level half of this: `assert_same_workspace` refuses to assemble a
> `ContextResponse` whose items and records do not all carry the response's `workspace_id`. Guard
> re-checks rather than assuming, because the request is a separate boundary.

---

## 6. Context authorization rule

AI-03 Context is an **input**, not an authorization source.

### 6.1 What may authorize

Only data satisfying **all** of the following may satisfy an authorization condition:

```text
item_kind    = FACT
freshness    = CURRENT
workspace_id = current workspace
```

### 6.2 What may never authorize (Amendment 3 / N3)

```text
PLAN        never directly authorizes
HISTORY     never directly authorizes
STALE       never authorizes
UNKNOWN     never authorizes
NOT_RUN     never authorizes
BLOCKED     never authorizes
```

**PLAN and HISTORY are never "weaker evidence".** They are not evidence at all. A PLAN is not a
fact that has been downgraded; it is a statement about what is intended. A HISTORY item is a
statement about what was true once.

A PLAN never becomes authorization merely because its content says:

```text
COMPLETE
PASS
APPROVED
DOCUMENTED
```

This is the §5.4 guarantee of AI-03 arriving intact at the authorization boundary: AI-03 reports
`COMPLETE` as truth state `UNKNOWN`, and Guard treats truth state `UNKNOWN` as non-authorizing.
Neither layer has to trust the other's prose.

### 6.3 Outcome when a required fact is not available (Amendment 3 / N3)

A rule that requires `context.<subject>` to be an authorizing FACT resolves as follows:

```text
FACT + CURRENT                                  -> the condition may be SATISFIED
FACT + STALE                                    -> BLOCKED
FACT + UNKNOWN                                  -> UNKNOWN
required FACT absent, but PLAN or HISTORY exists-> BLOCKED
required FACT absent entirely                   -> UNAVAILABLE -> BLOCKED
```

**A present-but-non-authorizing item is `BLOCKED`, not `DENY`.** The distinction matters to the
caller: `DENY` says "do not do this", while `BLOCKED` says "the evidence you need is not the kind
of thing that can authorize this, and you should go and produce a fact."

---

## 7. Capability rule (Amendment 1)

Guard consumes normalized capability state from an upstream component (AI-02). It does not probe
providers and does not execute capability tests.

```text
VERIFIED
DECLARED
NOT_VERIFIED
UNAVAILABLE
UNKNOWN
```

Only an explicitly required, verified capability state may satisfy a capability authorization
condition. The others are non-authorizing without exception:

```text
VERIFIED      may satisfy a required capability condition
DECLARED      never ALLOW
NOT_VERIFIED  never ALLOW
UNAVAILABLE   never ALLOW
UNKNOWN       never ALLOW; yields decision UNKNOWN (§2.3)
```

A policy may not be written to authorize on `DECLARED`. If one is, the rule's capability condition
can never be `SATISFIED`, and the rule cannot produce `ALLOW`.

> All five values are AI-02 `CapabilityStatus`, adopted unchanged. AI-04 adds no capability state
> and no promotion path between them.

---

## 8. Approval rule (Amendment 1)

Guard does not issue human approvals.

High-impact actions require an externally verified approval state:

```text
approval.status = VERIFIED
```

A plain caller-supplied boolean such as `approved = true` is **not** evidence of human approval
and is not part of this contract's request shape.

### 8.1 Why approval `UNKNOWN` is `BLOCKED` and not `UNKNOWN`

Unlike context and capability, approval is a precondition **this contract owns**. It is not an
upstream truth model reporting what it knows; it is a gate AI-04 defines and is responsible for
being fail-closed about. §2.3 permits such a precondition to map UNKNOWN to `BLOCKED`, and this
one does:

```text
approval.status = MISSING    -> BLOCKED
approval.status = INVALID    -> BLOCKED
approval.status = UNKNOWN    -> BLOCKED
approval.status = VERIFIED   -> may satisfy an approval-gated condition
```

An approval whose state cannot be established is not a weaker approval. It is no approval, and it
is treated as no approval.

### 8.2 Consequence, recorded deliberately

The verification and issuance mechanism is **outside AI-04**. Until a verified approval source
exists, **every approval-gated action in §15.2 is permanently `BLOCKED`.**

That is the intended fail-closed state, not a defect. It is recorded here for the same reason
AI-02 recorded that no capability is `VERIFIED`: so that it is read as a designed boundary rather
than discovered later as a bug.

> **AI-04 v1 cannot authorize `system-change` or `remote-change`.** It can only refuse them
> cleanly, with a reason code that names the missing approval.

---

## 9. Policy

A policy is an immutable, reviewed snapshot for exactly one workspace.

```yaml
version: 1
policy_id: string
revision: string
digest: string
workspace_id: string

rules:
  - rule_id: string
    priority: integer
    effect: ALLOW|DENY
    match: {}
    conditions: []
    reason_code: string
```

AI-04 v1 does not require a policy database, a distributed policy service, or automatic policy
discovery. A policy is a file, reviewed like code, in the same sense AI-02 provider profiles and
AI-03 source manifests are.

`digest` is computed over the canonical form defined in §20.2.

---

## 10. Rule

A Rule is a deterministic authorization statement:

```text
rule_id
priority
effect
match
conditions
reason_code
```

Effect is only:

```text
ALLOW
DENY
```

`BLOCKED` and `UNKNOWN` are **evaluation outcomes**, not policy effects. A policy cannot declare
"block this"; it can only allow it or deny it, and blocking arises from the evaluator being unable
to satisfy a precondition. This is what keeps §2's vocabulary honest: if `BLOCKED` were a policy
effect, a policy author could fabricate the appearance of an unsatisfied precondition.

`match` constrains which requests a rule is a candidate for, using the same grammar as
`conditions` (§11). `match` and `conditions` differ in role, not in language:

```text
match        decides whether the rule is a candidate at all
conditions   decides whether a candidate rule is satisfied
```

---

## 11. Condition grammar — frozen (Amendment 2 / B3)

Conditions are typed predicates over a **closed** field set. The grammar is frozen and complete.
There is no expression language and no extension point.

### 11.1 Predicates

Exactly three:

```text
eq       field == value
in       field ∈ {value, ...}      finite, non-empty
exists   field is present and not null
```

`conditions[]` is a **logical AND**. An empty list is `TRUE`.

**There is no `OR`, and none is added by nesting.** A disjunction is expressed by writing multiple
rules: the rule set is the disjunction, and §12 decides which of the matching rules wins. Adding
`OR` would make rule precedence depend on how a predicate was factored, which is exactly the kind
of ambiguity §12 exists to eliminate.

### 11.2 Field references (closed set)

```text
workspace.id
workspace.branch
workspace.working_tree

action.id
action.permission_level

capability.id
capability.status

target.kind
target.sensitivity
target.interface
target.is_real

context.<subject>.item_kind
context.<subject>.truth_state
context.<subject>.freshness

approval.status
approval.reference
```

`<subject>` is an AI-03 item subject (§8.3 of the AI-03 contract), e.g.
`context.git.head.item_kind` or `context.declared.live_provider_execution.truth_state`.

The field names are the policy-facing spelling and are resolved against the request as follows.
Nothing here is inferred; each name maps to exactly one request field.

| FieldRef | resolves to |
| --- | --- |
| `workspace.id` | `request.workspace.workspace_id` |
| `workspace.branch` | `request.workspace.branch` |
| `workspace.working_tree` | `request.workspace.working_tree` |
| `action.id` | `request.action.id` |
| `action.permission_level` | `request.action.permission_level` |
| `capability.id` | `request.capability.id` |
| `capability.status` | the `status` of the record in `capability_state.records[]` whose `capability_id` equals `request.capability.id` |
| `target.*` | the corresponding `request.target` field |
| `context.<subject>.<facet>` | the named facet of the item whose subject is `<subject>` (§11.4) |
| `approval.status` | `request.approval.status` |
| `approval.reference` | `request.approval.reference` |

`capability.status` resolves only when `request.capability.id` is non-null and a matching record
exists. A null capability id, or no matching record, is `UNAVAILABLE` (§11.4's rule, applied to
capability): a policy that constrains a capability the request does not name has not been
satisfied, and has not been refuted either.

### 11.3 Field domains

Each field is typed against a frozen vocabulary. A comparison against a value outside the
vocabulary is unsupported, not false.

| Field | Domain | Frozen by |
| --- | --- | --- |
| `workspace.working_tree` | `CLEAN` `DIRTY` `UNKNOWN` | AI-03 `WorkingTreeState` |
| `action.permission_level` | `read` `analyze` `test` `modify` `system-change` `remote-change` | AI-00 §6 |
| `capability.status` | `VERIFIED` `DECLARED` `NOT_VERIFIED` `UNAVAILABLE` `UNKNOWN` | AI-02 `CapabilityStatus` |
| `target.kind` | §4 closed set | this contract |
| `target.sensitivity` | §4 closed set | this contract |
| `target.interface` | §4 closed set | this contract |
| `target.is_real` | boolean | this contract |
| `context.<subject>.item_kind` | `FACT` `HISTORY` `PLAN` | AI-03 `ItemKind` |
| `context.<subject>.truth_state` | `PASS` `FAIL` `BLOCKED` `NOT_RUN` `UNKNOWN` | AI-03 `StatusValue` |
| `context.<subject>.freshness` | `CURRENT` `STALE` `UNKNOWN` | AI-03 `Freshness` |
| `approval.status` | `VERIFIED` `MISSING` `INVALID` `UNKNOWN` | this contract |
| `workspace.id`, `action.id`, `capability.id`, `approval.reference`, `workspace.branch` | open strings, compared literally | — |

### 11.4 Resolving a context field

`context.<subject>.<facet>` resolves against the request's `ContextResponse`:

```text
subject present, facet defined      -> the facet's value
subject present, facet absent       -> UNAVAILABLE
subject absent from the context     -> UNAVAILABLE
no ContextResponse in the request   -> UNAVAILABLE (all context conditions)
```

**The absence of a subject is not evidence about it.** A missing subject is `UNAVAILABLE`, never
`REJECTED`, because "nothing was recorded" and "the recorded value is false" are different facts —
the same rule AI-03 applies when it refuses to read an absent limit as zero.

### 11.5 Prohibited

```text
eval
arbitrary scripts
shell commands
Python expressions
natural-language policy
LLM-generated executable predicates
regex, arithmetic, or any operator not in §11.1
any field not in §11.2
```

### 11.6 Fail-closed

An unsupported predicate, an unsupported field reference, a type-mismatched comparison, a
malformed literal, or an unlisted value from a closed vocabulary in §4.2 evaluates to
`UNAVAILABLE`, which is `BLOCKED` (§18.2, §21). It is never `REJECTED`, because a policy defect
must not present as a clean "the rule does not apply and something else may allow it".

---

## 12. Rule ordering (Amendment 2 / B2, Amendment 4 / N1)

Before normal policy-rule evaluation, immutable Guard safety invariants are checked (§15.1). Safety
invariants cannot be overridden by policy.

For normal policy rules, precedence is the following **total order**:

```text
1. immutable Guard safety invariants      checked first, never overridden
2. lower numeric priority value           priority 0 precedes priority 10
3. DENY before ALLOW                      at equal priority
4. structural specificity                 at equal priority and equal effect
5. canonical rule_id ascending            final total tie-break
```

Policy file order is **never** semantically meaningful.

### 12.1 Priority direction (Amendment 4 / N1)

```text
Lower numeric priority value has higher precedence.
```

`priority: 0` outranks `priority: 10`. This matches the convention AI-00 §11 and AI-03 §5.3 already
froze for source priority (`P0` is highest), so the Workbench has one direction for "higher
precedence" rather than two.

### 12.2 Structural specificity (Amendment 2 / B2)

"More specific" is **defined structurally**, not judged. The previous draft required "more specific
before generic" without defining specificity, which left the ordering — and therefore §20's
determinism guarantee — unsatisfiable.

Per field `f`, a constraint is one of:

```text
absent     no constraint; matches any value
exists     matches any value that is present and not null
in S       matches any value in the finite set S
eq v       matches exactly v; equivalent to in {v}
```

Per-field specificity, written `A_f ⊑ B_f` — "A is at least as specific as B at f":

```text
eq v   ⊑ eq v
eq v   ⊑ in S        iff  v ∈ S
eq v   ⊑ exists
in S1  ⊑ in S2       iff  S1 ⊆ S2
in S   ⊑ exists
X      ⊑ absent      for every constraint X
```

Rule `A` is **strictly more specific** than rule `B` iff:

```text
A_f ⊑ B_f   for every field f,   and   A_f ⊏ B_f   for at least one field f
```

This relation is a partial order, and it is **decidable**: §11 freezes the grammar to `eq`, `in`
and `exists` over a closed field set, so every per-field comparison is a finite set comparison —
never a general predicate-implication problem.

**Incomparable rules are never guessed at.** When neither `A ⊑ B` nor `B ⊑ A` holds, this step
does not decide and precedence falls through to step 5, `rule_id` ascending. The chain is total
because step 5 always applies and `rule_id` is unique within a policy.

No rule may be ordered by which *appears* more specific, by policy file position, by a comment, or
by any property not defined above.

---

## 13. Default

No applicable `ALLOW` rule exists:

```text
DENY
```

This is the default policy outcome.

Default `DENY` is distinct from `BLOCKED` and `UNKNOWN`, because those two describe an
unavailable or indeterminate *evaluation*, while default `DENY` is a **completed negative policy
decision**: the evaluator finished, and nothing authorized the request.

### 13.1 When default `DENY` applies (Amendment 3 / N3)

Default `DENY` applies only when **all** of the following hold:

```text
every candidate rule completed deterministic predicate evaluation, and
no candidate produced BLOCKED, and
no candidate produced UNKNOWN
```

If any candidate rule is indeterminate — `BLOCKED` or `UNKNOWN` — the decision is that
indeterminate outcome, not `DENY`.

**A high-priority indeterminate rule must never fall through to a lower-priority generic `ALLOW`.**
The specific rule exists because someone decided a specific condition should govern; that the
condition cannot be evaluated is a reason to stop, not a reason to consult a rule that never
anticipated the case. This is the hazard §14 names, stated as a rule.

---

## 14. Indeterminate matching

A rule with matching request and target scope but unresolved required conditions must **not** be
silently ignored if doing so could expose a lower-risk-looking `ALLOW` path.

```text
required condition = UNAVAILABLE     -> BLOCKED
required condition = INDETERMINATE   -> UNKNOWN
```

The evaluator must not convert an unresolved specific allow condition into a generic allow by
falling through. An explicit higher-precedence `DENY` remains authoritative.

### 14.1 Evaluation order

```text
1. evaluate safety invariants (§15.1)
   any violation -> DENY, stop
2. select candidate rules by match (§11)
3. order candidates by §12
4. evaluate candidates in that order, recording each condition's CheckResult
5. the first candidate whose conditions are all SATISFIED decides (ALLOW or DENY)
6. if no candidate is fully SATISFIED:
     any candidate UNAVAILABLE   -> BLOCKED
     else any candidate INDETERMINATE -> UNKNOWN
     else                        -> DENY  (§13)
7. apply approval gating (§15.2) and target classification (§16) before returning ALLOW
```

Step 7 is a gate, not an override: it can turn an `ALLOW` into `BLOCKED`, never the reverse.

---

## 15. Mandatory safety boundaries

### 15.1 Absolute deny

Checked before policy, never overridden by any rule, priority, or approval:

```text
direct secret-material exposure
Guard bypass
cross-workspace authorization
malformed or unscoped authorization request
```

These produce `DENY` (or `BLOCKED` where the request itself cannot be evaluated; §21).

### 15.2 Approval-gated

Require `approval.status = VERIFIED`. Without it:

```text
BLOCKED
```

never `ALLOW`:

```text
system-change
sudo
remote-change
main/master merge or protected-branch change
history rewrite
force push
destructive filesystem operations
real CAN
real ECU
real vehicle
physical actuation
uncontrolled remote execution
```

The list is keyed on `action.permission_level` and `target.kind`, both of which are first-class
closed-vocabulary fields (§4.1, §4.2) — never inferred from `action.id`.

### 15.3 Why these are absolute

`F-09` freezes main, system-change and remote-change as outside default agent authority. A guard
whose boundaries a policy can widen is not a boundary; it is a default. The absolute list is a
floor, not a ceiling: a policy may add restrictions, never remove these.

---

## 16. Real CAN / ECU / vehicle

Safe defaults:

```text
vcan
simulator
isolated harness
```

are eligible for normal policy evaluation.

Real-world targets require explicit approval (§15.2) and appropriate policy.

```text
target.environment = simulated | isolated   -> normal policy evaluation
target.environment = real                   -> approval-gated (§15.2)
target.environment = unknown                -> BLOCKED, where the distinction matters
target.interface   = unknown                -> BLOCKED, where the distinction matters
target.is_real     = null                   -> BLOCKED, where the distinction matters
```

**Never infer `unknown = simulator`.** An unclassified target is not a safe target.

> This is AI-03's "unknown is not false" applied where the consequence is physical. The prohibition
> is stated separately from the general rule because the failure mode is not a wrong report — it
> is a real vehicle being actuated because a field was absent and a default was convenient.

---

## 17. Secrets

Guard does not become a secret-scanning engine. It consumes normalized target sensitivity and
action identity.

Direct secret-material access is denied by the hard safety boundary (§15.1):
`target.kind = secret_material` or `target.sensitivity = secret_material` produces `DENY`.

Credential injection for provider operation is outside Guard's secret-value handling and must
remain runtime-only, as AI-02 §10 already freezes.

Guard never logs, stores, or emits:

```text
API keys        tokens          private keys
passwords       cookies         credential values
prompt bodies   raw payloads
```

A decision record contains references and reason codes, never content (§18.3).

---

## 18. Decision result (Amendment 5 / N5, Amendment 6 / N6)

Minimum machine-consumable result:

```yaml
schema_version: 1

decision_id: string
evaluated_at: string

decision: ALLOW|DENY|BLOCKED|UNKNOWN
reason_code: string
reasons:
  - string

workspace_id: string

actor:
  id: string
  type: string

action:
  id: string
  permission_level: string

capability: string|null

target:
  kind: string
  identifier: string|null

policy:
  policy_id: string|null
  revision: string|null
  digest: string|null

rule_id: string|null

checks:
  - check_id: string
    result: SATISFIED|REJECTED|UNAVAILABLE|INDETERMINATE
    source: string
    detail: string

context_refs:
  - string

approval_reference: string|null

request_digest: string
evaluation_digest: string

evidence_ref: string|null
```

### 18.1 No `deterministic` field (Amendment 5a / N4)

The earlier draft carried `deterministic: true`. It is **removed**.

A field that can hold exactly one value carries no information; it asserts a property of the
contract as though it were a runtime observation. Determinism is a **contract guarantee** (§20),
verified by re-evaluation, not a value a decision record reports about itself. This is the same
reasoning AI-03 applied when it refused a model-confidence field in favour of a status.

### 18.2 Typed check result (Amendment 5b / N5)

`checks[].result` is a **`CheckResult`**, a distinct type from `GuardDecision`:

```text
GuardDecision   ALLOW | DENY | BLOCKED | UNKNOWN
CheckResult     SATISFIED | REJECTED | UNAVAILABLE | INDETERMINATE
```

They are never represented by a shared untyped `status` string. The mapping is fixed:

```text
SATISFIED      the precondition was evaluated and holds
REJECTED       the precondition was evaluated and does not hold
UNAVAILABLE    the precondition could not be obtained or is unsupported
INDETERMINATE  the precondition's truth is UNKNOWN
```

and to the decision:

```text
any check UNAVAILABLE      -> BLOCKED
any check INDETERMINATE    -> UNKNOWN
every check SATISFIED      -> the rule is satisfied
a REJECTED check           -> this rule does not apply
```

### 18.3 What must not appear

No raw context payload, secret, prompt, credential, or tool output belongs in this record. Context
appears only as references (`context_refs`), which are AI-03 `ItemRef` renderings
(`<source_kind>:<source_identity>@<source_revision> = <value>`) and carry no payload beyond the
claim they identify.

---

## 19. Provenance requirements

Every decision must make it possible to answer:

```text
Who requested?                  actor.id, actor.type
What action?                    action.id, action.permission_level
Which workspace?                workspace_id
Which target?                   target.kind, target.identifier
Which capability?               capability
Which policy?                   policy.policy_id
Which policy revision?          policy.revision
Which policy digest?            policy.digest
Which rule?                     rule_id
Which context references?       context_refs
What freshness?                 via the referenced items' freshness
Which approval reference?       approval_reference
What final decision?            decision, reason_code, reasons
Why?                            checks[] with per-check result and source
```

The provenance record **describes** the decision. It is not the Evidence Engine: AI-05 owns
durable experiment records, and `evidence_ref` is a pointer that AI-04 leaves `null` until such a
store exists.

---

## 20. Determinism and canonicalization (Amendment 2 / B4)

### 20.1 The guarantee

For identical semantic inputs:

```text
workspace
policy
policy revision and digest
request
target
context inputs
capability state
approval state
```

the following must be identical:

```text
decision
reason_code
selected rule
ordered rule evaluation outcome
used context references
evaluation digest
```

Generated event identifiers and timestamps may vary.

### 20.2 Canonical form

All digests are computed over a canonical serialization:

```text
encoding          UTF-8, no BOM
form              canonical JSON
object keys       sorted lexicographically by Unicode code point
whitespace        no insignificant whitespace
enums             canonical string form (the value as written in this contract)
nulls             a field in the projection whose value is not established is null,
                  never omitted; omission is not a second way to say null
absent field      a field outside the projection is not serialized at all
digest            SHA-256 over the canonical bytes
representation    lowercase hexadecimal
```

### 20.3 Array ordering

Arrays are either order-semantic or set-semantic, and the distinction is frozen per array:

```text
order-semantic (serialized in contract order, never sorted)
  checks[]                    the §14.1 evaluation trace
  the ordered rule trace      §20.5

set-semantic (sorted canonically before hashing)
  context_refs[]              sorted lexicographically
  capability_state.records[]  sorted by capability_id, then status
  conditions[]                sorted by (field, predicate, canonical value)
  match entries               sorted by field
```

Sorting a `match` or `conditions` collection is safe precisely because §11.1 fixes its meaning to
a logical AND: the collection is a set of constraints, so its serialization order cannot matter.

### 20.4 Runtime-only fields excluded from every digest

The following never enter `request_digest` or `evaluation_digest`:

```text
decision_id
evaluated_at
retrieved_at
cache_hit
generated runtime identifiers
generated timestamps
```

> **AI-03 `ContextItem.retrieved_at` does not participate in the semantic digest.** It records
> *when a read happened*, not *what was read*; two evaluations over the same context read at
> different times have the same semantic inputs and must produce the same digest. The same applies
> to `ContextResponse.retrieved_at` and to the `cache_hit` flag, which records how a read was
> served rather than what it said.

### 20.5 `request_digest`

Covers the **semantic request projection** only:

```text
schema_version
actor.id, actor.type
workspace.workspace_id, workspace.repository, workspace.branch,
  workspace.commit, workspace.detached, workspace.working_tree
action.id, action.permission_level
capability.id
target.kind, target.identifier, target.environment, target.interface,
  target.is_real, target.sensitivity
context: the semantic context projection (below)
capability_state.records[]
approval.status, approval.scope_digest, approval.reference
```

The **semantic context projection** of a `ContextResponse` is:

```text
workspace.workspace_id
per item, sorted by (subject, source_kind, source_identity, source_revision, value):
  subject, item_kind, value, truth_state, freshness,
  source_kind, source_identity, source_revision, superseded_by
```

excluding `retrieved_at` and `cache_hit` per §20.4.

### 20.6 `evaluation_digest`

Covers:

```text
request_digest
policy.policy_id, policy.revision, policy_digest
the ordered rule and check trace (order-semantic, §14.1 order)
context_refs[] (set-semantic)
capability state (semantic)
approval state (semantic)
decision, reason_code, rule_id
```

### 20.7 Verification

Determinism is verified by **re-evaluation**, not by a field:

```text
same semantic inputs -> same decision
                     -> same selected rule
                     -> same ordered checks
                     -> same context refs
                     -> same evaluation_digest
```

---

## 21. Fail-closed matrix (Amendments 1, 3)

```text
missing policy                          -> BLOCKED
invalid policy                          -> BLOCKED
unknown workspace                       -> BLOCKED
workspace mismatch                      -> DENY
missing context                         -> BLOCKED
context truth_state UNKNOWN             -> UNKNOWN
context STALE                           -> BLOCKED
required FACT absent, PLAN present      -> BLOCKED
required FACT absent, HISTORY present   -> BLOCKED
required FACT absent entirely           -> BLOCKED

missing capability                      -> BLOCKED
capability UNKNOWN                      -> UNKNOWN
capability DECLARED                     -> BLOCKED
capability NOT_VERIFIED                 -> BLOCKED
capability UNAVAILABLE                  -> BLOCKED

missing approval                        -> BLOCKED
invalid approval                        -> BLOCKED
approval UNKNOWN                        -> BLOCKED

ambiguous rule ordering                 -> BLOCKED
unsupported predicate or field          -> BLOCKED
unlisted value in a closed vocabulary   -> BLOCKED
malformed request                       -> DENY
no matching rule                        -> DENY
explicit DENY                           -> DENY

explicit ALLOW + every required precondition SATISFIED
                                        -> ALLOW
```

**No path converts one of the non-authorizing states into `ALLOW`.**

### 21.1 Reading the matrix

```text
BLOCKED   the evaluator could not complete: something it needed was missing,
          unsupported, invalid, or operationally indeterminate
UNKNOWN   the evaluator completed, and an upstream truth model says the fact
          is unknown
DENY      the evaluator completed and the answer is no
```

`unknown workspace -> BLOCKED` and `workspace mismatch -> DENY` differ for this reason: an
*unresolvable* workspace leaves the evaluator unable to proceed, while a *mismatched* workspace is
a determined, definite negative finding.

---

## 22. Non-goals

AI-04 does not implement:

```text
AI-03 Context                   AI-05 Evidence              AI-06 Security Tools
AI-07 Router                    approval workflow           policy database
distributed policy server       LLM authorization           automatic policy generation
real CAN tooling                real ECU tooling            real vehicle integration
secret scanner engine           SecurityLab integration     MCP or Terminal tool execution
```

Guard decides. It does not execute, collect, persist, route, approve, or scan.

---

## 23. Contract amendment rule

Any change to:

```text
decision vocabulary             rule ordering
default policy                  workspace scope
context authorization rules     mandatory safety boundary
fail-closed semantics           provenance requirements
predicate grammar               canonicalization and digest rules
closed vocabularies
```

requires a contract amendment **before** implementation proceeds.

Implementation must never silently diverge from this contract.

---

## 24. Amendment log

This contract was frozen at AI-04-A with six amendments applied before freeze, resolving four
blocking findings and six pinning findings raised in review. No implementation existed at the time
of any amendment.

**Amendment 1 — `UNKNOWN` semantics (§2.3, §6.3, §7, §8.1).** The draft contradicted itself: §2
defined `UNKNOWN` as "a required source explicitly carries UNKNOWN truth", §21 mapped
context-UNKNOWN and capability-UNKNOWN to `UNKNOWN`, and then mapped approval-UNKNOWN to
`BLOCKED`. The same word produced two outcomes.

§2 governs, and was made precise: `UNKNOWN` is a definite statement about an upstream truth model.
A precondition **this contract owns** may map UNKNOWN to `BLOCKED`, and exactly one does —
approval, which AI-04 defines and is responsible for being fail-closed about (§8.1). Context and
capability inherit their truth models and therefore yield `UNKNOWN`.

*Corrected in: §2.2, §2.3 (new), §6.3, §7, §8.1, §21.*

**Amendment 2 — rule ordering and predicate grammar (§11, §12, §20).** The draft required "more
specific before generic" without defining specificity, while asserting the ordering was total and
requiring in §20 that the ordered rule evaluation be identical for identical inputs. Those cannot
all hold.

§12 was corrected to a five-step total order with `rule_id` ascending as a guaranteed final
tie-break, and **structural specificity** was defined as a decidable partial order over the
predicate grammar (§12.2). Separately, the condition language was absent altogether: §11 named
domains and prohibited dynamic evaluation but fixed no predicates. It is now frozen to `eq`, `in`,
`exists` over a closed field set, with `conditions[]` fixed as logical AND and OR expressed by
multiple rules.

*Corrected in: §10 (match vs conditions), §11 (rewritten), §12 (ordering and specificity), §20
(canonicalization, new).*

**Amendment 3 — `PLAN` / `HISTORY` outcomes and default `DENY` (§6.2, §6.3, §13.1, §14, §21).**
The draft listed PLAN and HISTORY as "non-authorizing", which is not one of the four decision
values, and left the outcome undefined when a rule required a `FACT` and only a `PLAN` existed —
§13 pointed to `DENY` and §14 pointed to `BLOCKED`.

Both are now pinned: a present-but-non-authorizing item is `BLOCKED`, because `DENY` would tell
the caller "do not do this" when the truth is "the evidence you need cannot authorize this". And
default `DENY` now applies only after every candidate rule has completed deterministic evaluation
with no `BLOCKED` or `UNKNOWN` candidate, so an indeterminate specific rule can never fall through
to a generic `ALLOW`.

*Corrected in: §6.2, §6.3, §13.1 (new), §14, §21.*

**Amendment 4 — priority direction (§12.1).** The draft said "higher priority first" with
`priority: integer` and never said which direction the integer ran. AI-00 §11 and AI-03 §5.3
already froze the opposite convention for source priority, where `P0` is highest. Left unstated,
an implementer following the house convention would have produced the reverse of one following the
draft's wording.

Lower numeric value now has higher precedence, matching the Workbench's existing convention.

*Corrected in: §12 (step 2), §12.1 (new).*

**Amendment 5 — `permission_level`, `deterministic`, and typed check results (§4.1, §18.1,
§18.2).** Three separate corrections to the request and result shapes.

(a) AI-00 §6 froze a six-level permission model, and §15 approval-gated actions by naming two of
its levels, but the request carried nowhere to put the level — it would have had to be inferred
from `action.id`. `action.permission_level` is now a required first-class closed-vocabulary field.

(b) `deterministic: true` was removed. A field that can hold one value carries no information and
asserts a contract guarantee as though it were a runtime observation.

(c) `checks[].status` reused a bare `status` string shared with the decision vocabulary, so
`BLOCKED` appeared twice in one record with two meanings. `CheckResult` is now a distinct type.

*Corrected in: §4, §4.1 (new), §18, §18.1–§18.3.*

**Amendment 6 — closed vocabularies (§4.2, §11.3, §18, §21).** `actor.type`, `target.kind`,
`target.sensitivity`, `approval.status` and the capability record were unspecified or open, while
§11 required typed predicates over normalized inputs — which cannot be written against an open
set.

All authorization-relevant enumerations are now closed, with their frozen sources named in
§11.3. An unlisted value is unsupported and fail-closed, never silently treated as an ordinary
value. Open strings survive only for business identifiers, which carry no authorization semantics.

*Corrected in: §4, §4.2 (new), §11.3 (new), §18, §21.*

---

## 25. Decisions and open questions

### 25.1 Decisions made in AI-04-A

**D-1 — Guard does not execute, collect, persist, or route** (§1, §22). Authorization is a
decision, and a component that also acts on it cannot be audited separately from the action.

**D-2 — `BLOCKED` and `UNKNOWN` are never policy effects** (§10). If a policy could declare
"block", a policy author could fabricate the appearance of an unsatisfied precondition.

**D-3 — No `OR` in the condition grammar** (§11.1). OR would make rule precedence depend on how a
predicate was factored, which is what §12 exists to eliminate.

**D-4 — Specificity is structural, and incomparable rules fall through** (§12.2). A relation
defined by set inclusion over a closed grammar is decidable; "looks more specific" is not, and
guessing would break §20.

**D-5 — Approval UNKNOWN is `BLOCKED`, not `UNKNOWN`** (§8.1). Approval is a precondition this
contract owns and is fail-closed about; context and capability are truth models this contract
inherits.

**D-6 — A present-but-non-authorizing context item is `BLOCKED`** (§6.3). `DENY` would tell the
caller not to act; the truth is that the evidence cannot authorize, and the caller should produce
a fact.

**D-7 — Determinism is a contract guarantee, not a field** (§18.1, §20.7). Verified by
re-evaluation.

**D-8 — Decision and check vocabularies are distinct types** (§18.2). Two meanings for one word in
one record is the collision AI-03 already paid for once.

**D-9 — `retrieved_at` and `cache_hit` are excluded from every digest** (§20.4). They record how
and when a read happened, not what it said; including them would make §20 unsatisfiable, since two
evaluations over the same context at different times have identical semantic inputs.

**D-10 — Unsupported input is `UNAVAILABLE`, never `REJECTED`** (§11.6). A policy defect must not
present as a clean "this rule does not apply and something else may allow it".

**D-11 — The permission level is first-class** (§4.1). AI-00 froze it; inferring it from an
opaque action id loses a frozen concept and makes rules that key on privilege unwritable.

**D-12 — AI-04 v1 cannot authorize system-change or remote-change** (§8.2). With no approval
source in scope, every approval-gated action is permanently `BLOCKED`. Recorded so it is read as a
designed boundary, not discovered as a bug.

### 25.2 Open questions

Carried into AI-04-B. None changes a frozen boundary.

| # | Question | Needed by | Default if unresolved |
| --- | --- | --- | --- |
| Q-1 | Where do policy files live, and how is one selected for a workspace? | B1 | a reviewed file under `config/guard/`; no discovery (§9) |
| Q-2 | Is a policy digest computed at load time or declared in the file? | B1 | computed at load, declared value verified against it |
| Q-3 | How is `approval.scope_digest` computed and what does it bind? | a later phase | out of scope; approval remains `MISSING` and gated actions `BLOCKED` |
| Q-4 | Does `context_refs` carry every item, or only those consulted? | B2 | only items a condition resolved against |
| Q-5 | Is `reasons[]` ordered, and is it order-semantic for the digest? | B2 | ordered; included in the digest in trace order |

---

## 26. AI-04-A freeze record

```text
Phase              = AI-04 Security Guard Plugin
Sub-phase          = AI-04-A Contract / Execution Plan / Freeze
Status             = COMPLETE - contract frozen
Base branch        = main
Base SHA           = 548bc041b31cc0fc9d01af55c527378ba2c42c48
Working tree       = clean at start
Work branch        = feature/ai-04-guard-contract
Amendments         = 6 applied before freeze
Production code    = 0 lines changed
Guard code         = not written
Policy files       = none
Approval mechanism = not implemented
Context / Model    = not modified
SecurityLab        = untouched
Live API calls     = none
Secrets added      = none

Deferred, and NOT PASS:
  Guard implementation            AI-04-B
  approval issuance/verification  outside AI-04 (D-12)
  policy storage and selection    Q-1
  canonicalization test vectors   AI-04-B
```

### 26.1 AI-04-B entry criteria

- [ ] AI-04-A merged
- [ ] The §2, §11, §12, §18 and §20 vocabularies are implemented as typed values, not strings
- [ ] Canonicalization produces byte-identical output for a fixed vector set
