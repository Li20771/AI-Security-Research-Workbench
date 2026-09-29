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

### 9.1 Policy input boundary (Amendment 8)

Guard's evaluation input is frozen:

```text
Guard evaluation input = GuardRequest + exactly one externally supplied Policy snapshot
```

written as:

```text
Guard.evaluate(request, policy)
```

The policy is a **parameter**, not something Guard obtains. This is deliberate and it is not a gap
to be filled later:

```text
policy discovery   NOT Guard's responsibility
policy storage     NOT Guard's responsibility
policy selection   NOT Guard's responsibility
policy loading     NOT Guard's responsibility
```

Guard **verifies and evaluates** an externally supplied policy. It does not decide *which* policy
applies, because a component that both selects its own rules and applies them can authorize
anything by selecting a permissive rule set — and no amount of evaluation-time rigour would detect
it.

**There is no policy field on `GuardRequest`** (§4). A policy is not caller-supplied *data*; it is
a distinct, reviewed input to the call. Putting it in the request would make the policy
indistinguishable from the request's other fields, so a caller could vary it per request — which is
exactly the selection Guard must not perform.

Outcomes, matching §21:

```text
no policy supplied                -> BLOCKED
policy.workspace_id mismatch      -> DENY      (per §5; a determined negative)
invalid policy                    -> BLOCKED
policy digest mismatch            -> BLOCKED
```

### 9.2 Policy validation invariants (Amendment 9)

A policy is **valid** only if it satisfies every invariant below. Any violation makes the policy
invalid, and invalid is `BLOCKED` (§9.1, §21).

```text
schema version supported
every closed-vocabulary value is a listed value
rule_id is unique within the policy
every predicate is a listed predicate over a listed field, with a literal of the right type
declared digest matches the canonical form (§20.2)
```

**`rule_id` uniqueness is load-bearing, not hygiene.** §12.2.2's linearization chooses among
available rules by `rule_id`, and §20.3 sorts `policy.rules[]` by `rule_id` to compute the policy
digest. Both depend on the choice being a single rule. A duplicate therefore does not merely
"confuse" ordering — it makes the emitted sequence a function of something other than the rule set,
which is the failure mode §12 exists to eliminate.

A duplicate `rule_id` must **never** be resolved by:

```text
silently overwriting one of the rules
keeping the first or last occurrence
relying on dictionary-insertion order
falling back to policy file order
```

There is no defined behaviour for duplicate `rule_id`, because there is no defined behaviour: the
policy is invalid and the request is `BLOCKED`. Detecting the duplicate is Guard's job when it
verifies a supplied policy; it is not a condition the evaluator has to survive.

A policy that fails to parse, carries an unlisted value in a closed vocabulary, or whose declared
`digest` does not match its canonical form is **invalid**, and invalid is `BLOCKED`. A digest
mismatch is not a warning and not a re-computation: it means the snapshot being evaluated is not
the one that was reviewed, so it is refused.

> **Where a policy comes from is Q-1, and it stays a question.** Resolving it — a path convention,
> a reviewed file under `config/guard/`, an operator-supplied argument — does not change this
> boundary. Whoever supplies the policy is outside Guard, and Guard's contract is identical in
> every case: verify, then evaluate.

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

## 12. Rule ordering (Amendment 2 / B2, Amendment 4 / N1, Amendment 9)

Before normal policy-rule evaluation, immutable Guard safety invariants are checked (§15.1). Safety
invariants cannot be overridden by policy.

For normal policy rules, precedence is:

```text
1. immutable Guard safety invariants      checked first, never overridden
2. lower numeric priority value           priority 0 precedes priority 10
3. DENY before ALLOW                      at equal priority
4. deterministic specificity linearization
                                          at equal priority and equal effect
5. rule_id ascending                      among simultaneously available,
                                          mutually incomparable rules
```

Policy file order is **never** semantically meaningful — and §12.2 is how that is made true rather
than merely asserted.

### 12.0 Steps 4 and 5 are one procedure, not a comparator (Amendment 9)

Steps 1–3 are ordinary comparison keys. **Steps 4 and 5 are not, and must not be implemented as
one.**

The earlier text presented step 4 as "structural specificity" and step 5 as a "final total
tie-break", which reads as a single comparator:

```text
if the specificity relation decides, use it
otherwise, use rule_id ascending
```

That composite is **not transitive**, so it defines no total order and no sort can be
permutation-invariant. §12.2's former claim that "the chain is total because step 5 always applies"
was false. Amendment 9 (§24) records the defect and its minimal counterexample.

Steps 4 and 5 together are instead a **procedure**: a canonical topological linearization of the
specificity partial order, defined in §12.2. Replacing a partial order with a total one requires
choosing an extension; a comparator cannot do it, because a comparator only ever compares two
elements at a time and can be walked into a cycle.

> **Implementation consequence.** Steps 4–5 must not be expressed as a `sort` with a comparison
> function. A comparator-shaped implementation of this rule is a defect, not a style choice, and it
> will pass small tests and fail on the counterexample in §12.2.

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

#### 12.2.1 The relation is a partial order, not a sort key (Amendment 9)

`⊏` is **partial**: two rules may be incomparable. It is transitive, but the composite
"specificity if comparable, otherwise `rule_id`" is **not** transitive, so it is not a total order
and cannot be used to sort. §12.0 states the implementation consequence; Amendment 9 (§24) records
the counterexample that forced this.

#### 12.2.2 Deterministic specificity linearization (Amendment 9)

Ordering is performed **within a bucket** — the rules sharing one `priority` **and** one `effect`
(§12 steps 2 and 3 having already grouped them).

Define a directed relation over the bucket:

```text
A -> B   iff   A is strictly more specific than B
```

`A -> B` means **A must be evaluated before B**.

Linearize by deterministic Kahn-style emission:

```text
remaining = every rule in the bucket

while remaining is not empty:

    available = rules in remaining with no remaining specificity predecessor
                (that is, no rule R still in `remaining` such that R -> this rule)

    choose the available rule with the lexicographically smallest rule_id
    emit it
    remove it from remaining
```

**Direction, stated explicitly.** `available` is the set of rules that nothing remaining is
required to precede — equivalently, the currently *most specific* remaining rules. A rule is
emittable exactly when no more-specific remaining rule must come before it. This document uses
"available" rather than "maximal" or "minimal" precisely because those two words are read in
opposite directions by different conventions, and the direction here is load-bearing.

Three properties follow, and each is required:

**1. Every declared specificity relation is preserved.**

```text
A ⊏ B   =>   A is emitted before B
```

If `B` were emitted first, `A` would still be in `remaining` with `A -> B`, so `B` would not have
been available — a contradiction. The linearization therefore *extends* `⊏`; it never overrides it.

**2. The order is unique.**

`⊏` is a partial order, hence acyclic, so `available` is non-empty at every step and the procedure
terminates. At each step the choice is a single rule, because `rule_id` is unique within a policy
(§9.2) — so the emitted sequence is a function of the bucket's contents alone.

**3. The order is independent of policy file order.**

The procedure reads only the rules and their `match` constraints. It never consults position, and
`remaining` is a set. Permuting `policy.rules[]` therefore cannot change the emitted sequence.

Incomparable rules are ordered by `rule_id` ascending **at the moment both are available**. That is
a local tie-break between simultaneously emittable rules, not a global lexical fallback — the
distinction is exactly what makes the procedure transitive where the comparator was not.

No rule may be ordered by which *appears* more specific, by policy file position, by a comment, by
dictionary iteration order, or by any property not defined above.

#### 12.2.3 Worked counterexample

Three rules, one bucket (same `priority`, same `effect`), with the counterexample from Amendment 9:

```text
X = match { a: eq 1, b: eq 2 }        rule_id r3
Y = match { a: eq 1 }                 rule_id r1
Z = match { b: eq 3 }                 rule_id r2

X ⊏ Y     X stricter at b, equal at a          -> X -> Y
Y ∥ Z     Y stricter at a, Z stricter at b     -> no edge
Z ∥ X     Z stricter at b, X stricter at a     -> no edge
```

The directed relation is `X -> Y` only; it is acyclic. Linearization:

```text
remaining = {X, Y, Z}
  predecessors within remaining:  X: none   Y: X   Z: none
  available = {X, Z}                        -> smaller rule_id is r2 = Z, emit Z
remaining = {X, Y}
  available = {X}                           -> emit X
remaining = {Y}
  available = {Y}                           -> emit Y

emitted order:  Z, X, Y
```

`X` is emitted before `Y`, as `X ⊏ Y` requires. `Z` precedes both only because it is incomparable
to them and has the smallest `rule_id` among what was available at that step. Every permutation of
`policy.rules[]` produces this same sequence.

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

A `match` evaluates to a `CheckResult` exactly as `conditions[]` does: its predicates are
aggregated by §14.2. Its four outcomes map to three candidate states:

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

### 14.2 Predicate aggregation (Amendment 8)

A `match` or a `conditions[]` is a **set of predicates**, and evaluating one predicate yields one
`CheckResult`. Combining several into the single `CheckResult` a candidate carries uses one frozen
precedence:

```text
UNAVAILABLE  >  INDETERMINATE  >  REJECTED  >  SATISFIED
```

The aggregate is the highest-precedence result present:

```text
if any predicate = UNAVAILABLE:      aggregate = UNAVAILABLE
elif any predicate = INDETERMINATE:  aggregate = INDETERMINATE
elif any predicate = REJECTED:       aggregate = REJECTED
else:                                aggregate = SATISFIED
```

A candidate's aggregate `CheckResult` then maps to the walk in §14.1 exactly as before:

```text
aggregate UNAVAILABLE     -> BLOCKED, stop
aggregate INDETERMINATE   -> UNKNOWN, stop
aggregate REJECTED        -> continue the walk
aggregate SATISFIED       -> the candidate decides
```

**The same rule governs both `match` and `conditions[]`.** They are two uses of one grammar (§11)
and one aggregation, differing only in role (whether the rule is a candidate at all, versus
whether a candidate is satisfied).

Four properties follow, and each is required:

**1. `conditions[]` is still a logical AND.** Aggregation is how an AND over a four-valued logic
resolves, not a replacement for it. `SATISFIED` is the only aggregate that means "all held"; every
other aggregate means at least one did not.

**2. `match` still uses the §11 grammar.** Aggregation introduces no predicate and no operator; it
combines the results of `eq`, `in` and `exists` and nothing else.

**3. Aggregation does not depend on serialization order.** The precedence is total, so it is
commutative and associative: any permutation of the same predicate results yields the same
aggregate. This is what makes the *set-semantic* serialization of `conditions[]` and `match`
entries in §20.3 safe — the collection is written sorted for a stable digest, and the result it
produces does not depend on that order or any other.

**4. The aggregate is uniquely determined.** A candidate's `CheckResult` is a function of its
predicate results alone. Two implementations that evaluate the same predicates to the same results
produce the same aggregate, and therefore the same walk, the same decision and the same
`evaluation_digest` (§20.7).

**Why `UNAVAILABLE` outranks `INDETERMINATE`.** Both stop the walk; the decision differs
(`BLOCKED` versus `UNKNOWN`), and the ordering picks the one that is actionable. `BLOCKED` says
something is missing or unsupported and can be supplied or fixed; `UNKNOWN` says an upstream truth
model reports the fact unknown and the caller must go and establish it. When a predicate set
exhibits both, the unsupported or missing case is the one worth reporting, because fixing it may
dissolve the unknown entirely.

> **Order-independence is the load-bearing property.** Without a frozen precedence, `[REJECTED,
> INDETERMINATE]` and `[INDETERMINATE, REJECTED]` could aggregate differently, and a policy would
> mean different things depending on the order its conditions happened to be written in — which is
> precisely the ambiguity §12.2's rule_id tie-break and §20.3's set-semantic serialization exist
> to eliminate elsewhere.

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

and to the decision. For a **set** of checks belonging to one candidate, the mapping is the
aggregation of §14.2 — the same precedence, stated once there and not restated here:

```text
aggregate UNAVAILABLE      -> BLOCKED
aggregate INDETERMINATE    -> UNKNOWN
aggregate SATISFIED        -> the rule is satisfied
aggregate REJECTED         -> this rule does not apply
```

§14.2's precedence (UNAVAILABLE > INDETERMINATE > REJECTED > SATISFIED) is the only rule that
combines check results. A `checks[]` entry records one predicate's `CheckResult`; the aggregate a
candidate carries is derived from those entries by §14.2, so the record and the walk cannot
disagree.

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

**Policy rule order is not a semantic input (Amendment 9).** Permuting `policy.rules[]` changes
nothing:

```text
policy.digest                   unchanged   (rules are set-semantic, §20.3)
decision                        unchanged
selected rule                   unchanged
ordered semantic evaluation trace  unchanged  (§12.2.2 produces it)
evaluation_digest               unchanged
```

The trace still records the canonical evaluation order §12.2.2 produces — it is not re-sorted to
match the digest's rule order, and it is not read from the policy file. §20.3 distinguishes the two
orders.

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
  policy.rules[]              sorted by rule_id ascending
  context_refs[]              sorted lexicographically
  capability_state.records[]  sorted by capability_id, then status
  conditions[]                sorted by (field, predicate, canonical value)
  match entries               sorted by field
```

Sorting a `match` or `conditions` collection is safe precisely because §11.1 fixes its meaning to
a logical AND **and** §14.2 fixes the aggregation of its results: the collection is a set of
constraints, its serialization order cannot matter, and the aggregate `CheckResult` it produces is
uniquely determined regardless of that order. A set-semantic collection with an order-dependent
result would be a latent determinism failure, which is why §14.2's precedence is frozen and total
rather than left to whichever predicate is evaluated first.

`policy.rules[]` is set-semantic for the same reason, and it is new in Amendment 9. §12 already
declared policy file order semantically meaningless, but the canonical form did not say so, which
left two policies with identical rules in a different order hashing to different digests — a
`policy.digest` that changes when nothing semantic did. Sorting by `rule_id` is well defined
precisely because §9.2 makes `rule_id` unique.

> **The policy digest and the evaluation trace are different orders, and must not be conflated.**
> `policy.digest` covers a *canonical representation*, so its rules are sorted by `rule_id` — an
> arbitrary but stable choice. The evaluation trace records the *semantic evaluation order* that
> §12.2.2's linearization produces, which is a different sequence and is **not** sorted by
> `rule_id`. Both are deterministic; neither is derived from the other.

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
duplicate rule_id in policy             -> BLOCKED
policy digest mismatch                  -> BLOCKED
policy workspace mismatch               -> DENY
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

### 21.2 When several rows apply at once

The matrix states one condition per row. A candidate rule can exhibit more than one at a time —
an unsupported predicate and an unknown context value, say, or two unsatisfiable preconditions of
different kinds. The rows are then resolved by the aggregation precedence of §14.2, not by which
row appears first:

```text
UNAVAILABLE > INDETERMINATE > REJECTED > SATISFIED
```

So a candidate whose predicates include both an unsupported field (`UNAVAILABLE`) and an unknown
context value (`INDETERMINATE`) is `BLOCKED`, not `UNKNOWN`. The matrix is a list of *how a
condition resolves*; §14.2 is *how resolutions combine*. Neither overrides the other, and the
combination is order-independent.

The rows divide by severity for the same reason `BLOCKED` and `UNKNOWN` do (§21.1): `BLOCKED` is
the actionable report, and reporting it when it is present is what lets a caller fix something.

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

**Amendment 8 — predicate aggregation and the policy input boundary (§14.2, §9.1).** Two
independent gaps found while completing the freeze. Both are cases where the contract described
parts and left the composition undefined.

(a) **Aggregation.** §14.2 listed four outcomes for "any condition" and "every condition" but never
said what happens when a `match` or `conditions[]` holds predicates with *differing* results. With
no frozen precedence the aggregate depended on evaluation order — and §20.3 declares those
collections set-semantic precisely because order cannot matter, so an order-dependent aggregate
would have been a latent determinism failure sitting underneath a determinism guarantee.

§14.2 now freezes one total precedence, `UNAVAILABLE > INDETERMINATE > REJECTED > SATISFIED`,
governing both `match` and `conditions[]` because they are two uses of one grammar. Total, hence
commutative and associative, hence permutation-invariant. §14.0, §13.1, §18.2 and §20.3 were
brought into line so the precedence is stated once and referenced everywhere else. No new decision
value: the aggregate maps to the walk through the existing four `CheckResult` values (D-15).

(b) **Policy input boundary.** §9 defined the policy *schema* while §4 defined the request, and
nothing said how the two meet — leaving Q-1 to imply that Guard might find its own policy. §9.1
now freezes the input as `Guard.evaluate(request, policy)`: exactly one externally supplied,
workspace-scoped, immutable, reviewed snapshot, with **no** discovery, storage, selection or
loading by Guard. Deliberately **no policy field is added to `GuardRequest`**: a policy in the
request would be caller-supplied data indistinguishable from `action` or `target`, so a caller
could vary it per call and Guard would be selecting policy in effect if not in name (D-16).

T10 was rewritten to match. It previously asserted a policy whose `revision` differs from "the one
the request was evaluated against" — a comparison against a field this contract does not define
and never did. The test now covers the boundary that exists: valid, digest mismatch, invalid, no
policy supplied, and workspace mismatch.

*Corrected in: §9.1 (new), §14.0, §14.2 (rewritten), §13.1, §18.2, §20.3, §21, §25 (D-15, D-16),
§26 (T10 rewritten), §27 (C0, C2, C3).*

**Amendment 9 — deterministic linearization of structural specificity (§12, §12.0, §12.2, §9.2,
§20, §21, §26, §27).**

Found while beginning AI-04-B, at the point where §12 had to become code. Two gaps, one of which
is a blocker: it made C2 unsatisfiable and it failed **open**.

**(a) The ordering was not a total order.**

§12 listed step 4 "structural specificity" and step 5 "canonical rule_id ascending — final total
tie-break", and §12.2 closed with:

> The chain is total because step 5 always applies and `rule_id` is unique within a policy.

That is false. §12.2 defines a **partial** order: two rules may be incomparable. Combining a
partial order with a total tie-break in the shape

```text
if the specificity relation decides, use it
otherwise, use rule_id ascending
```

produces a composite that is **not transitive**, so it is not a total order and no sort using it
can be permutation-invariant. Step 5 "always applying" is exactly what fails: a comparator that
falls back to `rule_id` for incomparable pairs can be walked into a cycle.

*Minimal counterexample.* Three rules in one bucket (equal `priority`, equal `effect`, so §12 step
3 does not pre-empt step 4):

```text
X = match { a: eq 1, b: eq 2 }        rule_id r3
Y = match { a: eq 1 }                 rule_id r1
Z = match { b: eq 3 }                 rule_id r2

X ⊏ Y     X stricter at b, equal at a
Y ∥ Z     Y stricter at a, Z stricter at b
Z ∥ X     Z stricter at b, X stricter at a
```

The composite comparator yields `X ≺ Y` (specificity), `Y ≺ Z` (rule_id r1 < r2, incomparable),
`Z ≺ X` (rule_id r2 < r3, incomparable) — **a cycle**, `X ≺ Y ≺ Z ≺ X`. Sorting the same three
rules under all six permutations produces **three distinct orderings**, where §20 and C2 require
one. With `X` indeterminate and `Y`, `Z` satisfied, the decision itself flips: `ALLOW` under two
file orders and `UNKNOWN` under a third.

That last point is why this was treated as a blocker rather than a wart. §14.1 is designed so an
indeterminate rule stops the walk before a generic allow is consulted — and the composite made
*whether that rule is reached at all* depend on policy file position, which §12 explicitly
forbids. A fail-open divergence under a determinism guarantee is a security defect.

**Resolution.** §12.2.2 now defines ordering as a **procedure**, not a comparator: a deterministic
Kahn-style topological linearization of the `⊏` partial order within each
`(priority, effect)` bucket, emitting at each step the available rule — one with no remaining
specificity predecessor — bearing the lexicographically smallest `rule_id`. The relation `⊏` is
unchanged and nothing is deleted from specificity.

Why it holds:

```text
A ⊏ B  =>  A is emitted before B
    if B were emitted first, A would remain with A -> B, so B was not available

the order is unique
    ⊏ is acyclic, so `available` is never empty and the procedure terminates;
    rule_id is unique, so each step emits exactly one rule

the order is independent of file order
    the procedure reads the rules and their match constraints only, and
    `remaining` is a set
```

`rule_id` now breaks ties **locally, among simultaneously available incomparable rules**, rather
than acting as a global lexical fallback. That is precisely the change that restores transitivity.

Worked example in §12.2.3: the counterexample linearizes to `Z, X, Y`, with `X` before `Y` as
`X ⊏ Y` requires, identically under all six permutations.

**(b) `policy.rules[]` had no declared canonical form.**

§20.3 already declared `match` and `conditions` set-semantic, and §12 already declared policy file
order semantically meaningless — but the canonical form never said what `policy.rules[]` is. Two
policies with identical rules in a different order therefore hashed to different `policy.digest`s,
which is a digest that changes when nothing semantic did. `policy.rules[]` is now set-semantic,
sorted by `rule_id` before hashing.

This also forced a distinction the contract had left implicit: **`policy.digest` and the evaluation
trace are different orders.** The digest covers a canonical *representation* (rules sorted by
`rule_id`, an arbitrary but stable choice); the trace records the *semantic evaluation order*
§12.2.2 produces, which is not sorted by `rule_id`. Both are deterministic; neither derives from
the other, and §20.3 now says so.

**(c) `rule_id` uniqueness became a validation invariant.**

§12.2.2's linearization and §20.3's canonical sort both depend on `rule_id` selecting a single
rule, so uniqueness is load-bearing rather than hygiene. §9.2 now lists the policy validation
invariants and makes a duplicate `rule_id` an invalid policy — `BLOCKED` (§21), never resolved by
overwriting, by keeping first or last, by dictionary order, or by file order.

**(d) Tests.** T7 gained sub-case **7g**, which is the counterexample run under every input
permutation and is the test that would have caught this; 7a–7f all use rule sets a composite
comparator happens to order consistently. T10 gained **10f** (duplicate `rule_id`) and **10g**
(rule permutation leaves `policy.digest` and `evaluation_digest` unchanged), and its canonical
vectors now include the `policy.rules[]` permutation family. C2 was rewritten: steps 4–5 restated
as one procedure, pass criterion now names totality, determinism, transitivity,
permutation-invariance and specificity-preservation explicitly, and the forbidden list names
cycles, file-order dependence, undeclared comparators and composite comparators.

No decision value changed. No predicate, specificity relation, priority direction, or fail-closed
outcome changed.

*Corrected in: §12 (header and step list), §12.0 (new), §12.2.1–§12.2.3 (rewritten/new), §9.2
(new), §20.1, §20.3, §21, §25 (D-17), §26 (T7g, T10 10f/10g, vectors), §27 (C2), §29.*

> **Implementation consequence, restated because it is the whole point.** Steps 4–5 must not be
> implemented as a `sort` with a comparison function. An implementation that does will pass 7a–7f
> and fail 7g.

---

## 25. Decisions and open questions

### 25.1 Decisions made in AI-04-A

**D-1 — Guard does not execute, collect, persist, or route** (§1, §22). Authorization is a
decision, and a component that also acts on it cannot be audited separately from the action.

**D-2 — `BLOCKED` and `UNKNOWN` are never policy effects** (§10). If a policy could declare
"block", a policy author could fabricate the appearance of an unsatisfied precondition.

**D-3 — No `OR` in the condition grammar** (§11.1). OR would make rule precedence depend on how a
predicate was factored, which is what §12 exists to eliminate.

**D-4 — Specificity is a structural partial order, linearized rather than compared** (§12.2,
Amendment 9). Specificity is defined by set inclusion over a closed grammar, which is decidable;
"looks more specific" is not, and guessing would break §20.

Incomparable rules are a real and intended case, not a gap to be closed by a tie-break. They do not
override specificity, and they are not resolved by consulting a tie-break: the partial order is
extended to a total order by the deterministic topological linearization of §12.2.2, and `rule_id`
chooses only among rules that are *simultaneously available* — those with no remaining specificity
predecessor.

There is no specificity comparator, and no composite of the form "specificity if comparable,
otherwise `rule_id`". Policy file order never participates. `rule_id` is not a global lexical
fallback. It is the deterministic local choice within a linearization step, and that distinction is
what makes the ordering transitive (§12.0, §24 Amendment 9).

> **This decision was rewritten by Amendment 9.** Its previous wording described incomparable rules
> as falling through to the `rule_id` tie-break, which is the composite comparator §12.0 forbids and
> §24 Amendment 9 had to replace. The counterexample that forced the change is retained there as a
> record of why the earlier rule was wrong; it is not repeated here, because Decisions state what
> the contract requires, not what it previously required.

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

**D-15 — Predicate aggregation precedence is fixed, and it is order-independent** (§14.2).
Combining predicate results uses one total precedence:

```text
UNAVAILABLE > INDETERMINATE > REJECTED > SATISFIED
```

It governs both `match` and `conditions[]`, because they are two uses of one grammar (§11) and
differ only in role. Before it was frozen, a `match` or `conditions[]` holding predicates with
differing results had no defined aggregate, so the outcome depended on evaluation order — and
since §20.3 declares those collections set-semantic precisely because order cannot matter, an
order-dependent aggregate would have been a latent determinism failure sitting under a
determinism guarantee.

The precedence is total, therefore commutative and associative, therefore permutation-invariant.
`UNAVAILABLE` outranks `INDETERMINATE` because both stop the walk and the tie must be broken
toward the actionable report: an unsupported or missing input can be supplied or fixed, whereas an
unknown fact can only be established, and fixing the first frequently dissolves the second.

**D-16 — The policy is a call parameter, not a request field** (§9.1). Input is frozen as
`Guard.evaluate(request, policy)` with exactly one externally supplied, workspace-scoped,
immutable, reviewed snapshot. Guard performs no discovery, storage, selection, or loading.

Keeping the policy out of `GuardRequest` is the substance, not a style preference. A policy in the
request would be caller-supplied data indistinguishable from `action` or `target`, so a caller
could vary it per call — and Guard would then be selecting policy in effect, if not in name. A
component that both chooses its rules and applies them can authorize anything by choosing a
permissive rule set, and no amount of evaluation-time rigour would detect it. Where the policy
comes from remains Q-1; that it arrives from outside Guard does not.

**D-17 — Structural specificity is a partial order; rule evaluation uses deterministic topological
linearization rather than a composite comparator** (§12.0, §12.2.2). `⊏` is a partial order and
stays exactly as defined — incomparable rules are a real and intended case, not a defect to be
defined away. What changed is how it is *used*: ordering is a procedure that extends the partial
order to a total one, not a comparator that consults `rule_id` whenever specificity is silent.

The distinction is not stylistic. A comparator sees two elements at a time and cannot guarantee a
consistent global order; combined with a fallback it can be walked into a cycle, which is what
happened (§24, Amendment 9). A linearization sees the whole bucket and cannot. Concretely:
`A ⊏ B` implies `A` is emitted before `B`, whereas under the composite comparator that was only
true when no third rule happened to interfere.

`rule_id` is retained as a tie-break, demoted from a global lexical fallback to a **local choice
among simultaneously available incomparable rules** — which is what makes the result transitive and
a function of the rule set alone.

**D-18 — `policy.digest` and the evaluation trace are different orders** (§20.3). The digest
covers a canonical *representation*, with `policy.rules[]` sorted by `rule_id` — an arbitrary but
stable choice, since a digest must not depend on how a file was written. The evaluation trace
records the *semantic evaluation order* of §12.2.2, which is deliberately not that sequence.
Conflating them would either make the digest file-order-dependent or misreport the order rules were
actually evaluated in; both are failures the contract exists to prevent.

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

**Purpose.** §12 produces a total order, and the outcome does not depend on policy file order.
7g is the one that tests the total order actually holds rather than merely being asserted — see
§12.0 on why a composite comparator cannot deliver one.

**Setup.** Seven sub-cases:

```text
7a  same priority, DENY vs ALLOW          -> DENY wins (§12 step 3)
7b  different priority, ALLOW is lower    -> lower numeric priority wins (§12 step 2)
7c  same priority and effect, specific vs generic, both satisfied
                                          -> specific wins (§12 step 4)
7d  same priority and effect, incomparable specificity
                                          -> ordered by rule_id among available rules (§12 step 5)
7e  complete tie                          -> rule_id ascending, both orders
7f  every sub-case above re-run with the rules emitted in reverse order
                                          -> identical decision, rule and trace
7g  specificity partial-order counterexample  (below)
```

**7g — specificity partial-order counterexample.** Three rules in one bucket, constructed so that
a composite "specificity if comparable, else `rule_id`" comparator would contain a cycle:

```text
R1 = match { a: eq 1, b: eq 2 }     rule_id r3
R2 = match { a: eq 1 }              rule_id r1
R3 = match { b: eq 3 }              rule_id r2

R1 ⊏ R2      comparable
R2 ∥ R3      incomparable
R3 ∥ R1      incomparable
```

**Expected decision.** With R2 and R3 satisfied and R1 indeterminate: `ALLOW`, selected rule R2,
linearized order `R3, R1, R2` (§12.2.3).

**Expected CheckResult.** Per-candidate, in the linearized order.

**Evidence required.** Run the policy under **every permutation** of `policy.rules[]` — all six —
and assert all six produce:

```text
same ordered evaluation trace
same selected rule
same decision
same evaluation_digest
```

plus the specificity-preservation assertion:

```text
R1 ⊏ R2   =>   R1 appears before R2 in the emitted order, in every permutation
```

> **7g is the one that would have caught the defect.** 7a–7f all use rule sets whose specificity
> relation happens to be a chain or has only one incomparable pair, and a composite comparator
> orders those consistently. 7g is the minimal shape — two rules each more specific than a third
> at different fields — where the composite cycles, and it is the reason §12.2.2 is a procedure
> rather than a comparator.

**Evidence required (7a–7f).** The ordered rule trace for each sub-case, and an explicit assertion
that 7f's `evaluation_digest` equals the unreversed `evaluation_digest`.

> 7f remains load-bearing: a policy is a set of rules, and §12 says file order is never
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

### T10 — Policy input boundary, revision and digest

**Purpose.** Guard verifies and evaluates exactly one externally supplied policy snapshot, and
performs no discovery, storage, or selection (§9.1).

**Setup.** Five cases, all supplied as `Guard.evaluate(request, policy)` — never as a request
field:

```text
10a  a valid policy whose declared digest matches its canonical form
10b  a policy whose declared digest does NOT match its canonical form
10c  an invalid policy: unparseable, or an unlisted value in a closed vocabulary
10d  no policy supplied at all
10e  a policy naming a different workspace from the request
10f  a policy with a duplicate rule_id
10g  a policy whose rules are emitted in a different order but are otherwise identical
```

**Expected decision.**

```text
10a  evaluated normally -> ALLOW or DENY on its rules
10b  BLOCKED
10c  BLOCKED
10d  BLOCKED
10e  DENY
10f  BLOCKED   (invalid policy, section 9.2)
10g  identical to 10a in every field below
```

**Expected CheckResult.** The policy precondition is `UNAVAILABLE` for 10b, 10c and 10d — each an
unsupported or missing input, per §11.6 and §18.2. For 10e it is `REJECTED`: the policy was read
and evaluated, and it is positively the wrong one (§5).

**Evidence required.**

```text
for 10a: declared digest, computed digest, and that they agree
for 10b: declared digest and computed digest, both recorded, and that the mismatch
         was refused rather than tolerated or silently recomputed
for 10c: the specific defect that made the policy invalid
for 10d: policy_id, policy.revision and policy.digest all null in the record
for 10e: both workspace ids
for 10f: the duplicated rule_id, and confirmation the policy was rejected rather
         than one rule silently overwriting the other
for 10g: policy.digest, decision, selected rule, ordered trace and
         evaluation_digest, each asserted equal to 10a's

in every case: policy_id, policy.revision and policy.digest appear in the decision
               record (§19) and participate in evaluation_digest (§20.6), except
               where null because no policy was supplied
```

**10g is a canonicalization test, not an ordering test.** It asserts that
`policy.rules[]` is set-semantic (§20.3): the same rules in `[R1,R2,R3]`, `[R3,R1,R2]` and
`[R2,R3,R1]` order must produce the same `policy.digest`. The evaluation trace is **not** compared
against the rule order — it is the §12.2.2 order, which is a different sequence by design (§20.3).

The canonicalization vectors T14 requires therefore include, as one family:

```text
semantic input : policy.rules = [R1, R2, R3]  and every permutation
canonical form : rules sorted by rule_id
expected       : one SHA-256, identical across all permutations
```

**Not tested here.** Whether a policy's `revision` matches some prior revision. AI-04 has no
concept of a previously-seen revision, and the request carries no expected-revision field; a test
asserting one would be testing a field this contract does not define. Revision is recorded for
provenance (§19) and hashed into `evaluation_digest` (§20.6); comparing it against history is a
caller's concern, not Guard's.

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
predicate aggregation (§14.2)  policy input boundary (§9.1)
```

**Required evidence.** This document at its frozen revision; the §24 amendment log; a cross-check
that every §21 row is consistent with §13.1, §14 and §18.2.

**Pass criterion.** Every listed area has a frozen definition, and the §21 matrix, §13.1, §14 and
§18.2 agree with each other.

**Forbidden state.** Any listed area undefined; any two sections disagreeing on the same word or
outcome; an ordering asserted to be total without a *procedure* that makes it so — a claim of
totality backed only by a tie-break is what Amendment 9 had to correct, and asserting totality is
not the same as having it.

### C1 — Workspace isolation

**Condition.** Exactly one workspace per evaluation; no merge, filter, or repair of a mismatch.

**Required evidence.** T1's four cases.

**Pass criterion.** Mismatch yields `DENY`; unresolvable yields `BLOCKED`; no foreign item
influences any decision.

**Forbidden state.** Any cross-workspace evaluation; any mismatch silently dropped; any policy
able to authorize across workspaces.

### C2 — Deterministic evaluation

**Condition.** Determinism holds at two levels, and both must be total.

Rule selection — §12, applied end to end:

```text
immutable safety invariant
  -> lower numeric priority
  -> DENY before ALLOW
  -> deterministic topological linearization
     of the structural specificity partial order
  -> rule_id ascending among currently available,
     mutually incomparable rules
```

Note the shape: steps 4 and 5 are **one procedure**, not a composite comparator (§12.0). The
linearization replaces a partial order with a total one by choosing an extension; a comparator
cannot do this, and a comparator-shaped implementation is a defect.

Predicate aggregation — §14.2, a total precedence over a set of predicate results:

```text
UNAVAILABLE > INDETERMINATE > REJECTED > SATISFIED
```

Total, therefore commutative and associative, therefore permutation-invariant: the aggregate
`CheckResult` of a `match` or `conditions[]` does not depend on the order its predicates are
evaluated or serialized in. This is what allows §20.3 to declare those collections set-semantic
without introducing an order-dependent result underneath a determinism guarantee.

**Required evidence.** T7 sub-cases 7a–7g, including the reversal case **and** 7g's
partial-order counterexample run under every input permutation; T14 both parts; a case that
permutes predicates within one `match` and within one `conditions[]`; and a case asserting that
permuting `policy.rules[]` leaves `policy.digest` and `evaluation_digest` unchanged (§20.1).

**Pass criterion.** Identical semantic inputs produce an identical decision, selected rule,
ordered trace, context refs and evaluation digest, and the ordering is:

```text
1. total                    every pair of rules is ordered
2. deterministic            a function of the rule set alone
3. transitive               no cycle exists
4. permutation-invariant    policy file order never participates
5. specificity-preserving   A ⊏ B implies A is evaluated before B
```

**Forbidden state.**

```text
a cycle in the ordering
policy file order, or dictionary-iteration order, affecting the result
an undeclared comparator
an implicit tie-break
a composite "specificity else rule_id" comparator
any aggregate that varies with predicate order
```

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
no order-dependent aggregation
    discarding an UNAVAILABLE or INDETERMINATE result -> ALLOW
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
Amendments         = 9 applied before freeze (9 added after AI-04-B began)
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
Input boundary     = Guard.evaluate(request, policy) - frozen (section 9.1, D-16)
Aggregation        = UNAVAILABLE > INDETERMINATE > REJECTED > SATISFIED - frozen (section 14.2)
Rule ordering      = deterministic topological linearization of the specificity
                     partial order - frozen (section 12.2.2, D-17)
Policy rules array = set-semantic, sorted by rule_id for the digest - frozen (section 20.3, D-18)
Policy validity    = duplicate rule_id makes a policy invalid - frozen (section 9.2)

Deferred, and NOT PASS:
  Guard implementation            AI-04-B
  approval issuance/verification  outside AI-04 (D-12)
  policy origin (discovery/storage/selection)  Q-1 - the *boundary* is frozen,
                                  the *origin* is not; Guard never performs it
  canonicalization test vectors   AI-04-B
  AI-05 evidence store            not implemented; evidence_ref stays null (C9)
```

---
