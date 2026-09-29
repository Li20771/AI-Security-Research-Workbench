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
every candidate rule was reached by the §14.1 walk and evaluated, and
no reached candidate was UNAVAILABLE, and
no reached candidate was INDETERMINATE
```

"Evaluated" covers both halves of a candidate: its `match` (§14.0) and its `conditions` (§14.2). A
rule whose `match` could not be evaluated is an indeterminate candidate and counts here — it is
not a rule that "did not apply".

If any reached candidate is indeterminate — `BLOCKED` or `UNKNOWN` — the decision is that
indeterminate outcome, not `DENY`.

**A high-precedence indeterminate rule must never fall through to a lower-precedence generic
`ALLOW`.** §12 places a specific rule ahead of a generic one at equal priority and effect, so the
specific rule is reached first; that the rule cannot be evaluated is a reason to stop, not a
reason to consult a rule that never anticipated the case. This is the hazard §14 names, stated as
a rule.

---

## 14. Indeterminate matching (Amendment 7)

A rule that cannot be evaluated must **not** be silently ignored if doing so could expose a
lower-risk-looking `ALLOW` path.

Indeterminacy arises in two places — a rule's `match` and its `conditions` — and both are covered
here. Neither may be discarded.

### 14.0 `match` outcome and candidate status

A `match` evaluates to a `CheckResult` exactly as a condition does (§18.2). Its four outcomes map
to three candidate states:

```text
match SATISFIED      -> the rule is a candidate
match REJECTED       -> the rule is not a candidate
match UNAVAILABLE    -> the rule is an indeterminate candidate
match INDETERMINATE  -> the rule is an indeterminate candidate
```

> **A rule whose `match` predicates evaluate to `UNAVAILABLE` or `INDETERMINATE` is retained as an
> indeterminate candidate and participates in §14.1 resolution; it must never be silently
> discarded as a non-candidate.**

An indeterminate candidate is ordered by §12 like any other candidate, and it stops the evaluation
walk in §14.1 like any other indeterminate outcome. What it cannot do is decide: its `match` did
not hold, so it can produce neither `ALLOW` nor `DENY`. What it *can* do is prevent a silent
fall-through — which is the whole reason it is retained.

`match = REJECTED` is the only outcome that removes a rule from consideration, and it is a
**positive finding** that the rule's scope does not cover this request. A rule is never dropped
for being hard to evaluate.

> The gap this closes: before Amendment 7, §14.1 step 2 selected candidates "by match" with no
> defined outcome for an unevaluable `match`, so a specific rule whose scope depended on absent or
> unknown context could be discarded as a non-candidate and the request could fall through to a
> generic `ALLOW`. The rule that exists precisely because someone wanted that case governed would
> be the one silently skipped.

### 14.1 Evaluation order

```text
1. evaluate safety invariants (§15.1)
   any violation -> DENY, stop
2. select candidates by match (§14.0): SATISFIED and indeterminate rules are candidates,
   REJECTED rules are not
3. order candidates by §12, indeterminate candidates included
4. walk candidates in that order, recording each one's CheckResult:
     first candidate UNAVAILABLE     -> BLOCKED, stop
     first candidate INDETERMINATE   -> UNKNOWN, stop
     first candidate fully SATISFIED -> its effect decides, stop
     REJECTED                        -> continue
5. the walk ended with no decision   -> DENY (§13)
6. apply approval gating (§15.2) and target classification (§16) before returning ALLOW
```

The walk is total: every candidate is either indeterminate, satisfied, or rejected, and step 5
covers the case where all are rejected.

**Ordering is what makes this safe rather than merely cautious.** §12 places a specific rule ahead
of a generic one at equal priority and effect, so an indeterminate specific rule is reached first
and stops the walk before any generic `ALLOW` can be consulted. A `DENY` that §12 places ahead of
an indeterminate candidate still decides, because the walk stops when it reaches the `DENY` — an
explicit higher-precedence `DENY` remains authoritative, as §14 has always required.

Step 6 is a gate, not an override: it can turn an `ALLOW` into `BLOCKED`, never the reverse.

### 14.2 Condition outcome

For a candidate whose `match` held:

```text
any condition UNAVAILABLE     -> the candidate is UNAVAILABLE   -> BLOCKED
any condition INDETERMINATE   -> the candidate is INDETERMINATE -> UNKNOWN
any condition REJECTED        -> the candidate is REJECTED      -> continue the walk
every condition SATISFIED     -> the candidate decides
```

The evaluator must not convert an unresolved specific allow condition into a generic allow by
falling through.

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
candidate rule, match UNAVAILABLE       -> BLOCKED
candidate rule, match INDETERMINATE     -> UNKNOWN
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
closed vocabularies             match indeterminacy (§14.0)
test matrix T1-T15              exit gates C0-C10
```

requires a contract amendment **before** implementation proceeds.

A test may not be deleted, weakened, or re-scoped to make an implementation pass. If T-n or C-n is
wrong, it is amended here first, with the reason recorded in §24 — the same rule §23 applies to
every other frozen area.

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

**Amendment 7 — `match` indeterminacy (§14.0, §13.1, §14.1, §14.2, §21).** Amendment 3 closed the
fall-through hazard for a rule's *conditions*, but not for its *`match`*. §14.1 step 2 selected
candidates "by match" while §11 gave `match` the same grammar as `conditions` — a grammar whose
predicates can resolve to `UNAVAILABLE` or `INDETERMINATE`. With no defined outcome for those, the
only available reading was that such a rule is not a candidate, and it would be discarded.

That reopens the exact hazard §14 exists to close, one step earlier. A specific rule whose scope
depends on absent or unknown context — the rule someone wrote *because* they wanted that case
governed — would be dropped before evaluation, and the request could fall through to a generic
`ALLOW` that never anticipated the case.

§14.0 now freezes the mapping: `SATISFIED` is a candidate, `REJECTED` is not, and `UNAVAILABLE` or
`INDETERMINATE` is an **indeterminate candidate**, retained and ordered by §12 like any other and
able to stop the §14.1 walk. `REJECTED` is the only outcome that removes a rule, and it is a
positive finding that the rule's scope does not cover this request.

§13.1 and §21 were brought into line: default `DENY` now requires that every candidate reached by
the walk was evaluated in *both* halves — `match` and `conditions` — and §21 gained the two
indeterminate-match rows. No new decision value was introduced; the outcome is `BLOCKED` or
`UNKNOWN`, as §14 already required.

*Corrected in: §14 (rewritten, §14.0 and §14.2 new), §13.1, §14.1 (step 2 and the walk), §21.*

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

**D-13 — An unevaluable `match` retains the rule rather than discarding it** (§14.0). `REJECTED`
is the only match outcome that removes a rule, because it is the only one that is a *finding*:
the rule's scope positively does not cover this request. `UNAVAILABLE` and `INDETERMINATE` are
absences of a finding, and a rule dropped for absence of a finding is a rule skipped for being
hard to evaluate — which is the fall-through §14 exists to prevent, moved one step earlier.

**D-14 — No new decision value was added for indeterminate matching** (§14.0, §21). The outcome of
an indeterminate candidate is `BLOCKED` or `UNKNOWN`, reusing §2's vocabulary. Adding a fifth
value such as `INDETERMINATE_MATCH` would have made the decision vocabulary depend on *where* the
indeterminacy occurred, which is an implementation detail a caller should not have to know.

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

## 26. Test matrix — T1 to T15

The tests AI-04-B must implement. Each item names its purpose, its setup, the decision it expects,
the check result that matters, and the evidence a run must produce.

**Negative decisions are not test failures.** Several tests below expect `DENY` or `BLOCKED`. The
test passes when Guard produces the expected *decision*:

```text
test status    = PASS
guard decision = DENY
```

means the test successfully verified that Guard denied the request. §3 governs.

| ID | Test | Decision |
| --- | --- | --- |
| T1 | Workspace isolation | `DENY` / `BLOCKED` |
| T2 | Missing policy | `BLOCKED` |
| T3 | Unknown context | `UNKNOWN` |
| T4 | Stale context | `BLOCKED` |
| T5 | Explicit `DENY` | `DENY` |
| T6 | Explicit `ALLOW` | `ALLOW` |
| T7 | Conflicting rules | deterministic |
| T8 | Default no-rule `DENY` | `DENY` |
| T9 | Malformed request | `DENY` |
| T10 | Policy revision / digest | `BLOCKED` on mismatch |
| T11 | Provenance | any |
| T12 | Truth / status preservation | non-authorizing |
| T13 | Fail-closed matrix | never `ALLOW` |
| T14 | Determinism | identical |
| T15 | Regression | unchanged |

### T1 — Workspace isolation

**Purpose.** Guard evaluates exactly one workspace and never merges, filters, or repairs a
mismatch (§5).

**Setup.** Four cases: (a) request, policy and context all name the same workspace; (b) request
and policy agree but a context item carries a foreign `workspace_id`; (c) request and context
agree but the policy names another workspace; (d) a request whose `workspace_id` cannot be
resolved.

**Expected decision.** (a) evaluated normally; (b) and (c) `DENY`; (d) `BLOCKED`.

**Expected CheckResult.** The workspace-agreement check is `REJECTED` for (b) and (c) — a
determined negative — and `UNAVAILABLE` for (d).

**Evidence required.** Both workspace ids in the decision record; the mismatching item's
`context_refs` entry; confirmation that no item from the foreign workspace influenced the result.

### T2 — Missing policy

**Purpose.** No policy means no authorization, and it is not the same as no matching rule (§21).

**Setup.** A well-formed request, a valid context, and no policy supplied for the workspace.

**Expected decision.** `BLOCKED`.

**Expected CheckResult.** The policy precondition is `UNAVAILABLE`.

**Evidence required.** `policy.policy_id`, `policy.revision` and `policy.digest` all null;
`reason_code` naming the missing policy; `rule_id` null.

### T3 — Unknown context

**Purpose.** An upstream truth model reporting `UNKNOWN` yields `UNKNOWN`, not `BLOCKED` (§2.3).

**Setup.** A rule requiring `context.<subject>.truth_state`; the context contains the subject with
`truth_state = UNKNOWN`.

**Expected decision.** `UNKNOWN`.

**Expected CheckResult.** That condition is `INDETERMINATE`.

**Evidence required.** The context reference; the condition's `CheckResult`; a `reason_code`
distinguishing this from T4.

### T4 — Stale context

**Purpose.** `STALE` is not `CURRENT` and never authorizes (§6.3).

**Setup.** A rule requiring an authorizing `FACT`; the context holds it with
`freshness = STALE`.

**Expected decision.** `BLOCKED`.

**Expected CheckResult.** The freshness condition is `UNAVAILABLE`.

**Evidence required.** The item's `freshness` in the reference; a `reason_code` that names
staleness rather than absence, so the caller knows to re-read rather than to produce a new fact.

### T5 — Explicit `DENY`

**Purpose.** A matching `DENY` rule decides, and the test passes *because* the decision is `DENY`.

**Setup.** A policy with a single rule: `match` satisfied, conditions satisfied, `effect: DENY`.

**Expected decision.** `DENY`.

**Expected CheckResult.** Every condition `SATISFIED`.

**Evidence required.** `rule_id` naming that rule; `reason_code`; confirmation the `DENY` was a
completed policy decision and not a default (§13).

### T6 — Explicit `ALLOW`

**Purpose.** The one path to `ALLOW`, and the preconditions it requires.

**Setup.** A policy with a rule whose `match` and conditions are all satisfied, `effect: ALLOW`,
no approval-gated level or target, all prerequisites `VERIFIED` where required.

**Expected decision.** `ALLOW`.

**Expected CheckResult.** Every check `SATISFIED`, recorded individually.

**Evidence required.** Full provenance (§19); `evaluation_digest`; explicit confirmation that no
gate in §14.1 step 6 turned the `ALLOW` into `BLOCKED`.

### T7 — Conflicting rules

**Purpose.** §12 is a total order, and the outcome does not depend on policy file order.

**Setup.** Six sub-cases:

```text
7a  same priority, DENY vs ALLOW          -> DENY wins (§12 step 3)
7b  different priority, ALLOW is lower    -> lower numeric priority wins (§12 step 2)
7c  same priority and effect, specific vs generic, both satisfied
                                          -> specific wins (§12 step 4)
7d  same priority and effect, incomparable specificity
                                          -> falls through to rule_id ascending (§12 step 5)
7e  complete tie                          -> rule_id ascending, both orders
7f  every sub-case above re-run with the rules emitted in reverse order
                                          -> identical decision, rule and trace
```

**Expected decision.** As listed; 7f must equal its unreversed counterpart in every field.

**Expected CheckResult.** Per-candidate, in the §12 order, with the ordered trace preserved.

**Evidence required.** The ordered rule trace for each sub-case, and an explicit assertion that
7f's `evaluation_digest` equals the unreversed `evaluation_digest`.

> 7f is the load-bearing one: a policy is a set of rules, and §12 says file order is never
> semantically meaningful. Reversing the file must not change the answer.

### T8 — Default no-rule `DENY`

**Purpose.** Default `DENY` is a completed decision, distinct from `BLOCKED` and `UNKNOWN` (§13).

**Setup.** A valid policy whose rules are all `REJECTED` at `match` — none applies — with no
unsupported predicate, no indeterminate match, and no unavailable prerequisite anywhere.

**Expected decision.** `DENY`.

**Expected CheckResult.** Every candidate `REJECTED`; **no** `UNAVAILABLE` and **no**
`INDETERMINATE` anywhere in the trace.

**Evidence required.** `rule_id` null; a `reason_code` distinguishing default `DENY` from an
explicit `DENY`; the full ordered trace showing every candidate was evaluated and rejected.

### T9 — Malformed request

**Purpose.** A malformed or unscoped request is an absolute `DENY` (§15.1), evaluated before
policy.

**Setup.** Cases: unknown `schema_version`; missing `action.permission_level`; a
`permission_level` outside the closed set; a target field outside its closed set; a missing
`actor`.

**Expected decision.** `DENY` for each.

**Expected CheckResult.** The safety invariant is `REJECTED`; no policy rule is evaluated.

**Evidence required.** The failing invariant; confirmation the policy was never consulted, so no
rule can be blamed for the outcome.

### T10 — Policy revision and digest

**Purpose.** A policy is an immutable reviewed snapshot; a digest that does not match its content
is not that policy (§9, §20.2).

**Setup.** Valid policy; then a policy whose declared `digest` does not match its canonical form;
then a policy whose `revision` differs from the one the request was evaluated against.

**Expected decision.** `ALLOW`/`DENY` normally; `BLOCKED` on digest mismatch.

**Expected CheckResult.** The policy precondition is `UNAVAILABLE` on mismatch.

**Evidence required.** Declared digest, computed digest, and confirmation that the mismatch was
detected rather than tolerated.

### T11 — Provenance

**Purpose.** §19's list is answerable from the record alone.

**Setup.** Any evaluated request; assert every §19 question has an answer in the record.

**Expected decision.** Any.

**Expected CheckResult.** Any; the trace is present regardless of outcome.

**Evidence required.** A record where each §19 field is populated or explicitly null, and where
`context_refs` identify consulted items without carrying raw payload (§18.3).

### T12 — Truth / status preservation

**Purpose.** `UNKNOWN`, `NOT_RUN`, `BLOCKED`, `STALE`, `PLAN` and `HISTORY` are never converted
into authorization (§6.2, §21).

**Setup.** For each value: a policy rule that would authorize if the value were satisfied; the
context carries that value.

**Expected decision.** `BLOCKED` or `UNKNOWN`; never `ALLOW`.

**Expected CheckResult.** Non-`SATISFIED`, and specifically not silently `REJECTED`.

**Evidence required.** The declared value preserved verbatim in the reference; a `reason_code`
that reports the value rather than a generic failure.

> A test that passed by treating `PLAN` as "not a fact, so the rule does not apply, so default
> `DENY`" would be a **failure** of this test. The required outcome is `BLOCKED`, because the
> caller must learn that the evidence cannot authorize (§6.3).

### T13 — Fail-closed matrix

**Purpose.** §21 in full: no listed condition may produce `ALLOW`.

**Setup.** One case per row, including every row below:

```text
missing policy              invalid policy              unknown workspace
workspace mismatch          missing context             context UNKNOWN
context STALE               required FACT absent, PLAN present
required FACT absent, HISTORY present                   FACT absent entirely
missing capability          capability UNKNOWN          capability DECLARED
capability NOT_VERIFIED     capability UNAVAILABLE      missing approval
approval INVALID            approval UNKNOWN            unsupported predicate
unsupported field           closed-vocabulary unknown value
ambiguous rule ordering     candidate rule, match UNAVAILABLE
candidate rule, match INDETERMINATE
malformed request           no matching rule
```

The last five rows are the ones Amendment 7 added or that §21 carries beyond the obvious: an
`UNSUPPORTED` predicate is `BLOCKED` rather than `REJECTED` (§11.6), an ambiguous ordering is
`BLOCKED`, and an unevaluable `match` is retained as an indeterminate candidate rather than
discarded (§14.0). **This list is §21's, one case per row** — the two must not drift apart, and
the test asserts the mapping rather than restating it.

**Expected decision.** Exactly the §21 value for each row.

**Expected CheckResult.** As §21 implies — `UNAVAILABLE` for `BLOCKED` rows, `INDETERMINATE` for
`UNKNOWN` rows, `REJECTED` for `DENY` rows.

**Evidence required.** A table of case → decision → `reason_code`. **The assertion that matters is
negative and must be stated explicitly:**

> None of these cases may produce `ALLOW`.

### T14 — Determinism

**Purpose.** §20's guarantee, verified by re-evaluation.

**Setup.** Two parts.

Part one — identical semantic input, run twice:

```text
same decision
same selected rule
same ordered trace
same context refs
same evaluation_digest
```

Part two — vary only runtime fields, one at a time:

```text
retrieved_at changes     -> semantic digest unchanged
evaluated_at changes     -> semantic digest unchanged
decision_id changes      -> semantic digest unchanged
cache_hit changes        -> semantic digest unchanged
```

**Expected decision.** Identical across every run in both parts.

**Expected CheckResult.** Identical `CheckResult` sequences in part one.

**Evidence required.** Both digests printed for each run, with an explicit assertion that part two
changes the record while leaving `request_digest` and `evaluation_digest` byte-identical.

> Part two is what makes §20.4 real. If a digest moved because a read happened at a different
> time, the contract's determinism claim would be unsatisfiable in practice.

### T15 — Regression

**Purpose.** AI-04 does not disturb what already exists.

**Setup.** The full repository suite plus a Guard-specific check that:

```text
plugins/context is unchanged by AI-04-B
providers/ is unchanged by AI-04-B
Guard imports AI-02 and AI-03 types rather than redefining them
plugins/guard contains no network client, no subprocess, and no eval
no secret value is logged by any Guard code path
```

**Expected decision.** Not applicable.

**Expected CheckResult.** Not applicable.

**Evidence required.** Layer 0 result, the pre-existing suite's pass count, and an explicit
statement that no previously-passing test regressed.

---

## 27. Exit gates — C0 to C10

AI-04 is complete only when every gate below passes. Each gate names its condition, the evidence
it requires, its pass criterion, and the state that forbids it.

| ID | Gate | Blocking |
| --- | --- | --- |
| C0 | Contract frozen and internally consistent | yes |
| C1 | Workspace isolation | yes |
| C2 | Deterministic evaluation | yes |
| C3 | Fail-closed behaviour | yes |
| C4 | `DENY` / `ALLOW` semantics | yes |
| C5 | `UNKNOWN` / `NOT_RUN` / `BLOCKED` preservation | yes |
| C6 | Context freshness | yes |
| C7 | Provenance completeness | yes |
| C8 | Regression safety | yes |
| C9 | Evidence completeness | yes |
| C10 | Required CI checks | yes |

### C0 — Contract frozen and internally consistent

**Condition.** Every one of the following is frozen in this document, and no two of them
contradict each other:

```text
decision vocabulary            request shape              workspace scope
context semantics              capability semantics       approval semantics
policy schema                  rule schema                predicate grammar
rule precedence                default DENY               fail-closed semantics
safety boundaries              result and provenance      canonicalization
digest rules                   closed vocabularies        match indeterminacy (§14.0)
```

**Required evidence.** This document at its frozen revision; the §24 amendment log; a cross-check
that every §21 row is consistent with §13.1, §14 and §18.2.

**Pass criterion.** Every listed area has a frozen definition, and the §21 matrix, §13.1, §14 and
§18.2 agree with each other.

**Forbidden state.** Any listed area undefined; any two sections disagreeing on the same word or
outcome; an ordering asserted to be total without a guaranteed final tie-break.

### C1 — Workspace isolation

**Condition.** Exactly one workspace per evaluation; no merge, filter, or repair of a mismatch.

**Required evidence.** T1's four cases.

**Pass criterion.** Mismatch yields `DENY`; unresolvable yields `BLOCKED`; no foreign item
influences any decision.

**Forbidden state.** Any cross-workspace evaluation; any mismatch silently dropped; any policy
able to authorize across workspaces.

### C2 — Deterministic evaluation

**Condition.** §12 is a total order, applied end to end:

```text
safety invariant
  -> lower numeric priority
  -> DENY before ALLOW
  -> structural specificity
  -> rule_id ascending
```

**Required evidence.** T7 sub-cases 7a–7f, including the reversal case; T14 both parts.

**Pass criterion.** Identical semantic inputs produce an identical decision, selected rule,
ordered trace, context refs and evaluation digest — including when the policy's rules are emitted
in a different order.

**Forbidden state.** Any tie broken by file order, by specificity when rules are incomparable
without falling through, or by anything not in the §12 chain.

### C3 — Fail-closed behaviour

**Condition.** No missing, unknown, unsupported, or indeterminate prerequisite becomes `ALLOW`.

**Required evidence.** T13's full case list, including each `UNSUPPORTED` case and the §14.0
indeterminate-match cases.

**Pass criterion.** Every case produces its §21 outcome.

**Forbidden state.**

```text
no missing prerequisite      -> ALLOW
no unknown prerequisite      -> ALLOW
no unsupported predicate     -> ALLOW
no unsupported field         -> ALLOW
no indeterminate match       -> ALLOW
no indeterminate condition   -> ALLOW
```

### C4 — `DENY` / `ALLOW` semantics

**Condition.** `DENY` and `ALLOW` mean what §2.2 says, and default `DENY` is distinguishable from
explicit `DENY`.

**Required evidence.** T5, T6, T8.

**Pass criterion.** `ALLOW` only where every required precondition was `SATISFIED`; `DENY` for
explicit denial, malformed request, no matching rule, and workspace mismatch; the three `DENY`
kinds carry distinct `reason_code`s.

**Forbidden state.** `ALLOW` from any path other than T6's; `BLOCKED` or `UNKNOWN` reported as
`DENY`, or `DENY` reported as either.

### C5 — `UNKNOWN` / `NOT_RUN` / `BLOCKED` preservation

**Condition.** None of the following is converted into an authorizing `ALLOW`:

```text
UNKNOWN        NOT_RUN        BLOCKED        STALE        PLAN        HISTORY
```

**Required evidence.** T12, one case per value, plus the T3/T4 distinction.

**Pass criterion.** Each value is reported as itself; each yields `BLOCKED` or `UNKNOWN`; a value
is never silently normalised into a neighbouring one.

**Forbidden state.** `UNKNOWN -> ALLOW`; `NOT_RUN -> ALLOW`; `BLOCKED -> ALLOW`;
`PLAN -> ALLOW` because its text says `COMPLETE`, `PASS` or `APPROVED`; a compound or unrecognised
declared value decomposed into a satisfying one.

### C6 — Context freshness

**Condition.** Freshness is honoured as §6.1 requires, and the three values are distinct.

**Required evidence.** T4 plus explicit assertions that:

```text
CURRENT != STALE
STALE   != UNKNOWN
unknown freshness never becomes CURRENT
```

**Pass criterion.** Only `CURRENT` participates in authorization; `STALE` is `BLOCKED`;
unestablished freshness is never treated as current.

**Forbidden state.** A `STALE` or freshness-`UNKNOWN` item satisfying an authorization condition;
`STALE` reported as `WRONG` rather than as "no evidence it is still current".

### C7 — Provenance completeness

**Condition.** Every decision answers every §19 question.

**Required evidence.** T11.

**Pass criterion.** `actor`, `action`, `workspace_id`, `target`, `capability`, `policy` identity
and revision and digest, `rule_id`, `context_refs`, `approval_reference`, `decision`,
`reason_code` and `checks[]` are each populated or explicitly null, and the record carries no raw
payload.

**Forbidden state.** An `ALLOW` whose selected rule is unidentifiable; a decision whose
`evaluation_digest` cannot be recomputed from the record; any secret, prompt or raw context
payload in the record.

### C8 — Regression safety

**Condition.** AI-04 adds Guard without disturbing anything already frozen.

**Required evidence.** T15: Layer 0, the pre-existing suite, and the Guard-specific checks.

**Pass criterion.** The pre-existing suite's pass count does not decrease; Layer 0 passes; AI-02
and AI-03 implementations are unmodified; `plugins/guard/` contains no network client, no
subprocess, and no `eval`.

**Forbidden state.** Any previously-passing test failing; AI-02 or AI-03 behaviour changed; Guard
reimplementing capability, context, or routing types instead of importing them.

### C9 — Evidence completeness

**Condition.** AI-04's own evidence record is complete, and **only** that.

**Required evidence.** An AI-04 evidence document recording the freeze revision, base SHA,
implementation head, the T1–T15 results with the commands that produced them, the C0–C10 verdicts,
and every `NOT_RUN` / `BLOCKED` / `UNKNOWN` item explicitly.

**Pass criterion.** Every gate above is traceable to executed evidence, and every unexecuted item
is labelled as unexecuted.

**Forbidden state.** A gate marked `PASS` on the strength of implementation existing; a `NOT_RUN`
recorded as `PASS`; a test count carried forward from another phase.

> **This gate does not require an Evidence Engine.** AI-05 is not implemented and is not a
> prerequisite. C9 requires that Guard's decision evidence and provenance are *defined and
> produced* — §18, §19, §20 — not that a durable evidence store exists. `evidence_ref` stays
> `null` until AI-05 exists, and a null `evidence_ref` is not a C9 failure.

### C10 — Required CI checks

**Condition.** The repository's required checks pass on the head that carries the work.

**Required evidence.** A CI run on the pull request, with its run id and conclusion.

**Pass criterion.**

```text
required CI checks = PASS
```

**Forbidden state.**

```text
NOT_RUN     cannot be counted as complete
BLOCKED     cannot be counted as complete
UNKNOWN     cannot be counted as complete
```

Local execution is not CI execution. A green local run does not satisfy C10, and a criterion may
not be marked complete because CI "would" pass.

---

## 28. AI-04-B — Guard Implementation Execution Brief

The next sub-phase. This section constrains that work; it contains no implementation.

### 28.1 Scope

AI-04-B implements **`plugins/guard/`** and its directly associated unit tests. Nothing else.

```text
in scope      plugins/guard/*.py
              tests/guard/
              config/guard/ policy files, only if Q-1 is resolved
out of scope  everything else in the repository
```

### 28.2 Must consume, not duplicate

Guard **imports** these; it does not restate them.

| Source | What is consumed |
| --- | --- |
| AI-02 | `CapabilityStatus` |
| AI-03 | `ContextResponse`, `ContextItem`, `ItemRef`, `ItemKind`, `StatusValue`, `Freshness` |
| AI-03 | `WorkspaceIdentity` and its `WorkingTreeState` |
| AI-00 | the permission model's six levels |

**Redefining any of these is a defect**, not a convenience. Two definitions of `CapabilityStatus`
in one repository means two places to update and one of them will be forgotten.

Forbidden:

```text
Context collection             Capability probing          Evidence persistence
Model routing                  Tool execution              Approval issuance
SecurityLab integration        Provider calls
```

### 28.3 Implementation constraints

```text
typed enums, not string literals
typed request and result structures
the closed predicate grammar of §11, and no other
deterministic evaluation per §12 and §14
canonical digest per §20
fail-closed per §21
workspace scoped per §5
no eval, no exec, no arbitrary code execution
no LLM authorization
no network calls
no secret logging
```

`CheckResult` and `GuardDecision` are distinct types (§18.2), not one enum and not one string.

### 28.4 Test-first expectation

AI-04-B implements **T1–T15 before the final evaluation logic** is considered done. Every T item
maps to at least one automated test, and the mapping is recorded rather than implied.

```text
T1-T15  ->  tests/guard/, one module group per test
```

A T item with no corresponding automated test is an incomplete sub-phase, not a deferred one.

### 28.5 No policy database, no approval service

AI-04-B does not implement:

```text
policy database                distributed policy service
approval issuance              human approval workflow
policy generation
```

Per **D-12**, `system-change` and `remote-change` continue to be `BLOCKED` for as long as no
verified approval source exists. AI-04-B must not invent one, must not accept a caller-supplied
boolean as a substitute (§8), and must not weaken the gate to make its own tests pass.

> A test that needs an approval-gated action to be `ALLOW` is testing something AI-04 v1 cannot
> do. Such a test is wrong, and the correct outcome is `BLOCKED`.

### 28.6 AI-04-B entry criteria

- [ ] AI-04-A merged
- [ ] The §2, §11, §12, §18 and §20 vocabularies are implemented as typed values, not strings
- [ ] Canonicalization produces byte-identical output for a fixed vector set
- [ ] §14.0's indeterminate-candidate rule is implemented, with a test proving an unevaluable
      `match` is retained rather than discarded

---

## 29. AI-04-A freeze record

```text
Phase              = AI-04 Security Guard Plugin
Sub-phase          = AI-04-A Contract / Execution Plan / Freeze
Status             = COMPLETE - contract frozen
Base branch        = main
Base SHA           = 548bc041b31cc0fc9d01af55c527378ba2c42c48
Working tree       = clean at start
Work branch        = feature/ai-04-guard-contract
Amendments         = 7 applied before freeze
Production code    = 0 lines changed
Guard code         = not written
Policy files       = none
Approval mechanism = not implemented
Context / Model    = not modified
SecurityLab        = untouched
Live API calls     = none
Secrets added      = none

Test matrix        = T1-T15 defined (section 26)
Exit gates         = C0-C10 defined (section 27)
Next sub-phase     = AI-04-B, constrained by section 28

Deferred, and NOT PASS:
  Guard implementation            AI-04-B
  approval issuance/verification  outside AI-04 (D-12)
  policy storage and selection    Q-1
  canonicalization test vectors   AI-04-B
  AI-05 evidence store            not implemented; evidence_ref stays null (C9)
```

---
