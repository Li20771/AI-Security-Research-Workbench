# AI-07 — Plugin 5: Model Router v1 Execution Plan

> Status: **FROZEN** (AI-07-A, 2026-10-01)
> Phase: AI-07 — Model Router v1
> Sub-phase: **AI-07-A — Contract / Execution Plan / Freeze**
> Prerequisite: AI-00 … AI-06 (all COMPLETE and merged)
> Base branch: `main`
> Base SHA: `3b1917ab596931ec89de8c17a02266b5902557a5`
> Rule: This document defines the contract. AI-07-B implements against it. Nothing in AI-07 may
> deviate from a frozen contract without amending this document first (§18).

---

## 1. Purpose

AI-07 selects which Agent / Provider / Model profile a task should run on, and records why.

```text
Task
  |
  v
AI-07 Router            selects an eligible Agent / Provider / Model profile
  |
  v
AI-04 Guard             authorizes protected execution        <- unchanged authority
  |
  v
AI-06 Tools             execute the capability
  |
  v
AI-05 Evidence          records admitted, verified facts
```

**Router selects. Guard authorizes. Evidence records.** The three are distinct and none of them
substitutes for another.

### 1.1 Architectural identity — FROZEN

```text
AI-07 is a Workbench CORE SERVICE.
AI-07 is NOT a DSH plugin.
Its planning identity is "Plugin 5", and that label does not make it a plugin.
```

This is not AI-07's decision. `routing/README.md` already states it, AI-00 **F-13** freezes it, and
`plugins/README.md` lists exactly four plugin layers — `context`, `guard`, `evidence`,
`security_tools` — none of which is Router.

```text
plugins/     four DSH plugin layers          AI-03 · AI-04 · AI-05 · AI-06
routing/     one Workbench core service      AI-07
providers/   the model layer                 AI-02
```

AI-07-B MUST NOT create `plugins/router/`, and MUST NOT add a fifth plugin layer.

### 1.2 What AI-07-A delivers

```text
docs/AI-07_MODEL_ROUTER_EXECUTION_PLAN.md   this document
```

No router, no rule engine, no config loader, no CLI, no test of behaviour. **AI-07
implementation = NOT STARTED.**

---

## 2. Normative Language

```text
MUST       a requirement. AI-07-B that violates it is not conformant.
MUST NOT   a prohibition.
FROZEN     binding, and changes only by amendment (§18).
DEFERRED   declared, and deliberately not decided here.
OPEN       named as unresolved, with a stated default.
```

---

## 3. What already exists, and what this contract does with it

AI-07 is not written on a blank page. Everything here is a **transcription or a reconciliation**,
never a contradiction.

```text
routing/README.md                the core-service identity, the four responsibilities,
                                 and "Model Router never grants permissions.
                                 Guard remains authoritative."          (§1.1, §9, §16)
AI-00 F-13                       "Model Router is a Workbench core service and never
                                 grants permissions."                   (§9)
AI-00 F-12                       "Model routing v2 must be built on real benchmark
                                 data."                                (§7.4)
MASTER_ROADMAP §1.1 Routing      the four example intents                 (§7.3)
AI-02 §6, model_profile.py       the five capability names, CapabilityStatus,
                                 modality, limits                        (§6)
AI-02 pricing.py                 dated pricing metadata, CostProjection   (§6.4)
AI-02 D-13, §5.7, §6.4           "No model is a default model"; the model list carries
                                 no ordering semantics                   (§3.3)
config/routing/README.md         "Configuration selects eligible Agent / Provider /
                                 Model profiles but does not grant permissions.
                                 Guard remains authoritative."            (§9, §12)
AI-02 D-13, §5.7, §6.4           "No model is a default model"; the model list carries
                                 no ordering semantics                   (§3.3)
config/routing/README.md         "Configuration selects eligible Agent / Provider /
                                 Model profiles but does not grant permissions.
                                 Guard remains authoritative."            (§9, §12)
AI-04 §4.1, D-11                 permission_level is first-class and never inferred
                                                                         (§8, §10)
AI-06 §1.1                       "Tool is a capability. Guard is the authorization.
                                 Evidence is the record."                (§16)
```

### 3.1 FINDING: `routing/` is a README and nothing else

```text
routing/README.md            the only file
config/routing/rules.example.yaml   an example shape, loaded by nothing
```

There is **no** router, no rule type, no config loader, no decision record, and no caller. The
directory is a declaration, not an implementation. AI-07-B starts from nothing, and this contract
does not assume otherwise.

### 3.2 FINDING: the example config names profiles that do not exist

`config/routing/rules.example.yaml` says:

```yaml
rules:
  - task_class: simple              -> model_profile: fast
  - task_class: complex-security    -> model_profile: strong
  - task_class: multimodal          -> model_profile: multimodal
  - task_class: independent-review  -> agent: codex
```

```text
"fast", "strong" and "multimodal" are not model profiles.
The shipped profiles are deepseek/deepseek-flash, mimo/mimo-v2.6-flash and
mimo/mimo-v2.6-pro, and providers/model_registry.py is the only thing that
enumerates them.
```

The example is a sketch of an intent, and it is not usable as configuration. §12 freezes where
rules actually live and what a rule may name; AI-07-B MUST NOT implement against this example as
though it were a schema, and MUST NOT invent profiles to match it.

### 3.3 FINDING: order in AI-02 carries no selection semantics

`providers/model_registry.py::available_model_refs` documents its own ordering in a way the Router
must obey rather than exploit:

> *"Ordering here is for deterministic output only. It carries no selection semantics: there is no
> default, preferred, or primary model (section 6.4, D-13)."*

AI-02 **D-13** freezes it - *"No model is a default model"* - and `tests/unit/test_model_scope.py`
enforces it, asserting that `ModelProfile` has no `default`, `primary`, `preferred`, `priority`,
`weight` or `rank` field.

```text
FROZEN: AI-07 MUST NOT read any ordering, position or listing order as a
        preference, and MUST NOT introduce a preference into AI-02's metadata.
        Its own section 7.5 ordering is AI-07's, computed at evaluation time,
        and is never written back.
```

### 3.4 FINDING: nothing is enabled and nothing is priced

```text
config/providers/providers.example.yaml    every provider ships `enabled: false`
providers/pricing.py                       the default catalog is EMPTY, and no
                                           pricing YAML exists anywhere
```

So a constraint on cost has no data to satisfy it, and a rule gated on provider enablement finds
nothing enabled unless the caller supplied a config. Both are recorded here as facts v1 must live
with, and neither is a reason to invent a value.

### 3.5 `task_class` is AI-02's field, and using it is what AI-02 intended

AI-02 section 7.4:

> *"`task_class` is recorded for **later** routing analysis by AI-07 - recording it does not
> implement routing."*

`RequestMetadata`'s own docstring adds that AI-02 records metadata and *"No field here may drive
model selection"* - which binds **AI-02**, and is why AI-02 contains no router.

```text
FROZEN: AI-07 reading `task_class` is the use AI-02 recorded it for.
        AI-07 MUST NOT ask AI-02 to act on it, and MUST NOT move routing logic
        into providers/.
```

---

## 4. Scope

### 4.1 In scope

```text
the RouterRequest shape
which AI-02 profile fields the Router may consume, and which it may not
the routing rule model: priority, matching, tie-break, no-match, fallback
the RouterDecision and its explanation
failure semantics
the fallback boundary, the authorization boundary, the second-opinion boundary
the Evidence boundary
the configuration boundary
the test matrix and the exit gates
```

### 4.2 Out of scope

```text
any implementation                    AI-07-B
learning of any kind                  no reinforcement, no online, no self-selection
Agent execution                       AI-08 owns the independent path
Guard, or any part of authorization   AI-04 owns it and is not modified
Tool execution                        AI-06 owns it and is not modified
Evidence persistence                  AI-05 owns it and is not modified
provider or model behaviour           AI-02 owns it and is not modified
DSH integration                       not in v1
```

### 4.3 Non-goals, restated as the boundary

```text
AI-07 is NOT:
    an authorization engine
    a second Guard
    a capability verifier
    a benchmark
    a model-quality oracle
    a fallback-until-success engine
    an evidence store
    a DSH plugin
```

---

## 5. RouterRequest

### 5.1 Shape — FROZEN

```yaml
schema_version: 1

task:
  task_class: string          # a bounded token; the caller's own classification
  summary: string|null        # bounded, single-line, NEVER a prompt body

workspace:
  workspace_id: string        # REQUIRED; the same scope AI-03/AI-04 use

requested_capability: string|null   # one of AI-02's CapabilityName members (§6.2)

modality: string|null         # the input modality the task needs (§6.3)

constraints:
  max_cost_class: string|null       # AI-02's cost class (§6.4)
  max_latency_class: string|null    # AI-02's latency class, when one exists (§6.4)

sensitivity: read|analyze|test|modify|system-change|remote-change|null

require_independence: bool    # the "second opinion" requirement (§11)

actor:
  id: string
  type: human|agent|service|unknown

candidates:
  - model_ref: string         # "provider_id/model_id", AI-02's own composition
```

### 5.2 `sensitivity` is carried, never used to authorize — FROZEN

`sensitivity` is AI-04's `PermissionLevel`, imported and not restated. **It is an input to
eligibility, not a grant.**

```text
AI-07 MUST NOT:
    infer a permission level from a task class, a tool name, a repository name,
    a file path, task wording, model confidence, or a previous routing
    decide that a task is "safe enough" to skip an approval
    attach a permission level to a selection
    emit anything a caller could read as an authorization

AI-07 MAY:
    use `sensitivity` to narrow the candidate set, and MUST say so in the decision
```

A Router that could widen a permission would be the second permission system this contract exists
to prevent (§8, §10).

### 5.3 What a request must not carry — FROZEN

```text
no prompt body, no message content, no tool arguments, no credential, no token
```

AI-07 routes on **descriptors**, not on content. A request carrying content is refused, for the
same reason AI-04 §4 refuses one: a field nobody defined is a field a credential can ride in on.

---

## 6. What the Router consumes from AI-02

### 6.1 The rule

```text
FROZEN: AI-07 consumes AI-02's abstractions and defines none of its own.
        There is no Router-side model type, provider type, capability vocabulary
        or registry. providers/model_registry.py remains the only enumeration of
        the profiles that exist.
```

Two definitions of one vocabulary means one of them is eventually forgotten — the rule AI-05 §3 and
AI-06 §6.1 already apply, applied here.

### 6.2 Capabilities — the real vocabulary, and the finding that governs v1

AI-02 defines exactly five, and AI-07 restates none of them:

```text
CapabilityName      tool_calling · structured_output · streaming · reasoning · prompt_caching
CapabilityStatus    DECLARED · VERIFIED · NOT_VERIFIED · UNAVAILABLE · UNKNOWN
```

**FINDING: every capability on every shipped profile is `UNKNOWN`.**

```text
deepseek/deepseek-flash   tool_calling UNKNOWN · structured_output UNKNOWN ·
                          streaming UNKNOWN · reasoning UNKNOWN · prompt_caching UNKNOWN
mimo/mimo-v2.6-flash      the same five, all UNKNOWN
mimo/mimo-v2.6-pro        the same five, all UNKNOWN
```

No provider call has ever been made in this repository — AI-02's closeout records `Live
provider execution = NOT_RUN` and `Real provider API calls = 0` — so there is nothing to verify
against and nothing has been verified.

**This is the fact the v1 routing rule is built around:**

```text
FROZEN: `UNKNOWN` is NOT `available`.
        A capability-requiring rule MUST NOT match a profile whose status for that
        capability is UNKNOWN, DECLARED or NOT_VERIFIED.
        Only VERIFIED satisfies a capability requirement.
```

The consequence is deliberate and it is the honest one:

```text
in v1, a request that REQUIRES a capability has NO eligible candidate,
and the outcome is NO_ELIGIBLE_MODEL.
```

That is not a defect to route around. Reading `UNKNOWN` as "probably fine" would turn the Router
into a machine that selects on claims nobody tested, and would make the first model it picked look
verified by having been picked. AI-00 **F-10** — evidence outranks model confidence — is the
authority, and it is earlier than this document.

```text
FROZEN: AI-07 MUST NOT promote a capability status, and MUST NOT request a probe.
        Only AI-02's opt-in live verification path can move a status, and it is
        manual, opt-in and outside AI-07 entirely.
```

### 6.3 Modality

`ModelProfile` carries `modality` as a field **separate from capabilities**. It is the real input
for a multimodal requirement, because AI-02 defines no `multimodal` capability.

```text
a multimodal requirement matches on `modality`, not on a capability
```

### 6.4 Cost and latency

`providers/pricing.py` exists and is real: `PricingRecord`, `PricingRef`, `CostProjection`,
`PricingCatalog`, `project_cost`. Pricing is **dated metadata with no hardcoded price** — AI-02 §9
records that a price carries the date it was observed.

```text
FROZEN: AI-07 reads cost through AI-02's types and computes nothing itself.
FROZEN: a constraint on a cost or latency class that no shipped profile declares
        is UNSATISFIABLE, and the outcome is NO_ELIGIBLE_MODEL — not a guess.
DEFERRED: whether AI-02 exposes a latency CLASS. No such field exists today, and
        AI-07 does not invent one; a `max_latency_class` constraint is recorded
        as unsupported rather than silently ignored.
```

**In v1 both constraints are unsatisfiable, and that is the honest state.** The default
`PricingCatalog` is empty — no pricing YAML exists in the repository — and no profile carries a
latency class. A rule set that asks for either produces `NO_ELIGIBLE_MODEL`, which is a true
answer to a question the repository has no data for. AI-07 MUST NOT substitute a model to make
such a rule succeed (§9), and MUST NOT invent a price.

```text
FROZEN: a provider that ships `enabled: false` is not a candidate. AI-07 reads
        enablement through AI-02's ProviderConfig and does not decide it.
```

### 6.5 Limits

`ModelProfile.limits` carries context and output limits. A requirement that exceeds every
candidate's limit is `NO_ELIGIBLE_MODEL`.

---

## 7. Routing rules

### 7.1 The rule model — FROZEN

```text
v1 is deterministic, explainable and configurable.
```

```text
MUST NOT be:   reinforcement learning · online learning · model self-selection ·
               an opaque score · an LLM-generated routing decision
```

The prohibition is not stylistic. AI-00 §13 records that the Workbench does not accept "the model
said so" as a result, and a routing decision produced by a model would be exactly that — a
judgement nobody can audit, made by the thing being selected.

### 7.2 A rule

```yaml
rule_id: string          # unique within a rule set; a duplicate is invalid (§12.4)
priority: integer        # lower runs first; ties broken by rule_id (§7.5)
match:                   # every present field must match; absent means "no constraint"
  task_class: string|null
  requested_capability: string|null
  modality: string|null
  require_independence: bool|null
select:
  model_ref: string|null
  agent: string|null     # a hint, not an execution path (§11)
reason_code: string      # a stable machine-readable label, never prose
```

### 7.3 The roadmap's intents are intent, not schema — FROZEN

MASTER_ROADMAP §1.1 sketches four:

```text
simple / high-frequency -> fast / low-cost model
complex repo / security -> stronger model
multimodal              -> multimodal-capable model
second opinion          -> independent Agent
```

```text
FROZEN: these are design INTENT. AI-07-B MUST NOT transcribe them into a rule set,
        and MUST NOT invent the profiles they name (§3.2).
```

The roadmap states a direction; this contract states a mechanism. A rule set is authored, reviewed
and configured, and the four intents are what an author has in mind while writing one.

### 7.4 v1's starting rule set

```text
FROZEN: AI-07 v1 ships the MECHANISM and an EMPTY or minimal default rule set.
        It does not ship a tuned one.

AI-00 F-12: "Model routing v2 must be built on real benchmark data."
AI-07 is v1. There is no benchmark, and this contract does not pretend a default
rule set is one.
```

### 7.5 Determinism — FROZEN

Two runs over the same request and the same rule set MUST produce the same decision. That requires
the tie-break to be stated rather than emergent:

```text
FROZEN: rules are ordered by (priority ascending, rule_id lexicographic ascending).
        The sort key is total: priority is an integer, rule_id is unique, so no
        two rules compare equal.

FROZEN: candidates are ordered by model_ref lexicographic ascending before any
        tie-break is applied, so a decision cannot depend on dict iteration order,
        file order, or the order the caller listed candidates in.
```

`rule_id` uniqueness (§12.4) is what makes the key total, which is why a duplicate invalidates the
rule set rather than being resolved silently.

### 7.6 No match — FROZEN

```text
FROZEN: a request that matches no rule produces NO_ELIGIBLE_MODEL.
        It MUST NOT fall back to a default model, and there is no implicit
        "otherwise" rule.
```

A default would be a rule nobody wrote, applying to every request the author did not think about —
which is the one class of request most likely to need a considered answer. It would also
contradict AI-02 **D-13** one layer up: AI-02 has no default model, and AI-07 does not supply
one on its behalf. It would also
contradict AI-02 **D-13** one layer up: AI-02 has no default model, and AI-07 does not supply one
on its behalf.

### 7.7 An unavailable model — FROZEN

```text
FROZEN: a candidate the rule selects that is not in the request's `candidates`,
        or that no longer resolves in AI-02's registry, is MODEL_UNAVAILABLE.
        The Router does not substitute a different model to make the request
        succeed (§10).
```

---

## 8. Authorization boundary

```text
Router NEVER grants permission.
Router NEVER replaces Guard.
Router NEVER decides whether a tool may execute.
Router NEVER turns model selection into authorization.
```

```text
FROZEN: selecting a stronger model does NOT grant stronger permissions.
FROZEN: selecting a cheaper or faster model does NOT reduce required authorization.
FROZEN: a selection does NOT authorize modify, system-change or remote-change.
FROZEN: a RouterDecision carries no permission, no approval and no grant, and
        nothing in routing/ may be read by AI-04 as an input to a decision.
```

AI-00 **F-09** keeps `main`, `system-change` and `remote-change` outside default Agent authority,
and AI-04 **D-12** records that with no approval source those levels are permanently `BLOCKED`.
A Router that could move a task into one of them by selecting a model would be exactly the bypass
those two decisions exist to close.

---

## 9. Fallback boundary

```text
fallback != authorization
fallback != evidence
fallback != retry-until-success
```

```text
FROZEN: a fallback is a second ROUTING decision over the remaining candidates, made
        by the same rule set, and recorded as its own decision. It is not a
        mutation of the first.
FROZEN: a fallback MUST NOT relax a capability requirement, a modality requirement,
        a cost or latency constraint, or a sensitivity.
FROZEN: a fallback MUST NOT bypass Guard, widen a permission, or reach a model the
        request's `candidates` did not name.
FROZEN: the Router does not retry. Attempting a model, observing a failure and
        trying another is execution, and AI-07 does not execute (§14).
```

```text
an unavailable model does NOT mean:
    lower the security requirement
    skip Guard
    enlarge the candidate set
```

`NO_ELIGIBLE_MODEL` after a fallback is a result (§10 of AI-06's shape: a fact, not a failure to
report).

---

## 10. Failure semantics

### 10.1 Outcome vocabulary — FROZEN

```text
RoutingOutcome — closed, owned by AI-07

    SELECTED            one eligible candidate was selected
    NO_ELIGIBLE_MODEL   no candidate satisfied the rules and constraints
    MODEL_UNAVAILABLE   a selected candidate is no longer resolvable
    INVALID_REQUEST     the request does not match §5.1
    INVALID_RULES       the rule set is not usable (§12.4)
    ROUTER_ERROR        the Router could not complete the evaluation
```

```text
FROZEN: this vocabulary is AI-07's own and is NOT merged with:
            GuardDecision       AI-04's   ALLOW|DENY|BLOCKED|UNKNOWN
            StatusValue         AI-03's   PASS|FAIL|BLOCKED|NOT_RUN|UNKNOWN
            ToolOutcome         AI-06's   COMPLETED|FAILED|...
        The words BLOCKED and UNKNOWN appear in more than one of those. That is a
        known cost, and AI-07 does not remove it by merging the types.
```

`POLICY_MISMATCH` is deliberately absent: AI-07 has no policy. A policy is AI-04's, it is a
parameter to `evaluate`, and a routing outcome named for one would imply the Router had consulted
it (§8).

### 10.2 What an outcome does not mean — FROZEN

```text
FROZEN: a successful selection is NOT a successful task.
        It is NOT evidence that the task succeeded, and it MUST NOT be recorded as
        one (§13).

FROZEN: no path converts NO_ELIGIBLE_MODEL, MODEL_UNAVAILABLE, INVALID_REQUEST,
        INVALID_RULES or ROUTER_ERROR into a selection.
```

---

## 11. Second opinion

MASTER_ROADMAP §1.1 reserves `second opinion -> independent Agent`, and AI-08 owns the independent
execution path.

```text
FROZEN: the Router expresses the REQUIREMENT and nothing more.

AI-07 owns:   `require_independence` on the request, and a selection that honours it
AI-08 owns:   the independent Agent, its context, its execution and its result
```

```text
FROZEN: AI-07 MUST NOT implement AI-08. No Codex adapter, no second execution path,
        no cross-agent comparison, no "the two agree so it passed".
DEFERRED: how an independent Agent is identified. `select.agent` exists as a hint
        and AI-07-B MUST NOT treat it as an execution path.
```

AI-00 §13 records the rule this protects: agreement between two agents is not verification.

---

## 12. Configuration

### 12.1 Where rules live — FROZEN

```text
default rule set   config/routing/default.rules.yaml, TRACKED, reviewed like code
workspace override config/routing/<workspace_id>.rules.yaml, TRACKED, reviewed
```

A rule set is a reviewed file in the same sense AI-02's provider profiles and AI-04's policies are
(Q-1). It is not generated, not fetched, and not discovered.

`config/routing/README.md` already states the same boundary, and this contract does not narrow
it:

> *"Configuration selects eligible Agent / Provider / Model profiles but does not grant
> permissions. Guard remains authoritative for execution permission."*

`config/routing/README.md` already states the same boundary and this contract does not narrow it:

> *"Configuration selects eligible Agent / Provider / Model profiles but does not grant permissions.
> Guard remains authoritative for execution permission."*

### 12.2 What a rule set may not be — FROZEN

```text
MUST NOT be discovered at runtime from a remote source
MUST NOT be modified at runtime
MUST NOT be written by AI-07
```

```text
OPEN: whether a rule set requires a Guard authorization to CHANGE.
      Default: changing a rule set is a `modify` and goes through the same
      review and branch discipline as any other tracked file; AI-07 itself
      neither requires nor performs that check.
```

AI-00 §17 leaves multi-workspace discovery open, and §12.1 does not resolve it: an override is
named by `workspace_id`, which the caller already supplies (§5.1). There is no discovery.

### 12.3 Revision

```text
FROZEN: every rule set declares `version` and `revision`.
FROZEN: the RouterDecision records the revision it used, so a decision can be
        attributed to the rules that produced it. §7.5's determinism claim is
        only checkable if the rules are identified.
```

### 12.4 An invalid rule set — FROZEN

```text
unsupported `version`              INVALID_RULES
duplicate `rule_id`                INVALID_RULES
a `match` field outside the schema INVALID_RULES
a `select` naming nothing          INVALID_RULES
a `model_ref` that does not resolve MODEL_UNAVAILABLE at evaluation, not INVALID_RULES
```

```text
FROZEN: an invalid rule set produces INVALID_RULES and NO selection. It MUST NOT
        be partially applied, silently repaired, or resolved by keeping the first
        or last duplicate — the same rule AI-04 §9.2 applies to a duplicate
        rule_id in a policy.
```

---

## 13. Evidence boundary

### 13.1 A routing decision is not research evidence — FROZEN

```text
routing fact != research fact
```

A RouterDecision says *which model was selected and why*. It says nothing about whether the task
succeeded, whether a claim is true, or whether a capability is verified.

### 13.2 What AI-07 does with a decision — FROZEN

```text
FROZEN: AI-07 produces an auditable ROUTER DECISION RECORD and nothing else.
        It does not write Evidence, does not call AI-05's admission, and defines
        no Evidence schema.
```

```text
FROZEN: AI-07 MUST NOT register a new AI-05 event.
```

AI-05 §6.5 registers **two** AI-06 events and **none** for AI-07. There is deliberately no "AI-07
routing decision" row: the AI-05 contract records that the routing arm is `DECISION` by §6.2, that
its outcome vocabulary is **not frozen**, and that it is therefore not representable in v1.
Adding a row would be an amendment to a frozen AI-05 registry, which is AI-05's to make and not
AI-07's.

```text
FROZEN: if a later phase wants routing decisions in Evidence, that is an AI-05
        amendment first. AI-07-B MUST NOT work around the absence by writing a
        record, by reusing an AI-06 event, or by emitting something that looks
        like one.
```

### 13.3 What a decision record carries — FROZEN

```text
decision_id · decided_at · outcome · reason_code
requested        the request's descriptors, never its content
matched_rule     rule_id, or null
candidates       the ordered candidate set considered
selected         model_ref and agent hint, or null
fallbacks        any second decision over the remaining candidates
rules_revision   the revision used (§12.3)
```

No prompt, no message, no tool arguments, no credential, no provider payload.

---

## 14. What AI-07 does not execute

```text
FROZEN: AI-07 does not call a provider, does not open a transport, does not run a
        tool, and does not start a process.
```

AI-02 owns provider calls and makes live connectivity opt-in, allowlisted, manual and non-default;
AI-06 owns tool execution and is the only layer that starts a process. A Router that called a model
to "see if it works" would be executing, and would also be probing — which AI-02 §13 makes a
human-started act.

---

## 15. No hidden inference

```text
FROZEN: AI-07 MUST NOT infer any of the following, from any of the following:

    a permission level        from a task class, a tool name, a tool family, a
                              repository name, a file path, task wording, model
                              confidence, a previous successful routing, or a
                              capability status
    a capability status       from a model's name, family, version, display name,
                              provider, or price
    an approval               from anything at all
    an authorization          from anything at all
```

```text
tool name · tool family · repository name · file path · task wording ·
model confidence · previous routing

  MAY influence  routing eligibility
  MUST NOT influence  authorization
```

This is AI-04 §4.1's rule — *"An implementer must never infer the permission level from
`action.id`"* — applied one layer out, and AI-06 §6.2's rule applied to a second component.

---

## 16. Relations to the other phases

```text
AI-02 Provider / Model       the profiles AI-07 selects from. Consumed, never redefined.
AI-03 Context               supplies project context. AI-07 does not read it in v1 and
                            MUST NOT infer anything from it (§15).
AI-04 Guard                 authorizes protected execution. Untouched. AI-07 supplies no
                            input to a Guard decision, and reads none of its output as
                            a routing input.
AI-05 Evidence              records admitted, verified facts. AI-07 does not write to it (§13.2).
AI-06 Security Tools        executes capabilities. AI-07 selects a model, not a tool, and
                            does not authorize one either.
AI-08 Codex                 the independent Agent. Not implemented here (§11).
```

```text
FORBIDDEN:
    Router -> Guard bypass
    Router -> Tool direct authorization
    Router -> Evidence PASS
    Router -> a second permission vocabulary
```

---

## 17. Repository layout

```text
routing/
    README.md              the identity and the four responsibilities (unchanged)
    vocabulary.py          RoutingOutcome
    request.py             RouterRequest
    profile.py             the AI-02 consumption surface — what may be read, and
                           the UNKNOWN rule of §6.2
    rules.py               Rule, RuleSet, ordering and matching (§7)
    decision.py            RouterDecision and the decision record (§13.3)
    router.py              evaluate(request, rule_set, registry) -> RouterDecision
    errors.py              the refusal vocabulary
config/routing/
    default.rules.yaml     the tracked default rule set (§12.1)
```

```text
FROZEN: routing/ is not a package under plugins/, and MUST NOT be given an
        __init__.py that makes it look like one.
FROZEN: routing/ MUST NOT import from plugins.security_tools or tools/.
```

Exact module names are AI-07-B's to place; the responsibilities and the two prohibitions are
frozen.

---

## 18. Contract amendment rule

A frozen rule changes only through an explicit amendment recorded in §22.

An amendment is REQUIRED for any new or changed:

```text
RouterRequest field (§5.1)      RoutingOutcome member (§10.1)
Rule or RuleSet field (§7.2)    the ordering key (§7.5)
the capability rule (§6.2)      the configuration layout (§12.1)
the Evidence boundary (§13)     the repository layout (§17)
```

```text
FORBIDDEN:
    a capability status read as available to make a test pass
    a rule relaxed so that something has something to select
    a selection treated as an authorization
    a routing decision recorded as research evidence
    an LLM consulted for a routing decision
```

---

## 19. Test Matrix

Layers 1–3 only. **AI-07 adds no layer 4** — the Router reaches no network and starts no process
(§14).

Every test is offline, deterministic and repeatable. No test needs a credential, a provider call or
a network.

| # | Test | Purpose | Expected | Property |
| --- | --- | --- | --- | --- |
| T1 | a well-formed request parses | baseline | parsed | nothing is measurable without it |
| T2 | a malformed request is refused | shape | `INVALID_REQUEST` | a shape violation is never absorbed |
| T3 | a request carrying a prompt body is refused | §5.3 | refused | content never enters routing |
| T4 | determinism | §7.5 | the same request twice gives the same decision | an unenforced determinism claim is not one |
| T5 | candidate order does not matter | §7.5 | permuting `candidates` does not change the selection | no reliance on iteration order |
| T6 | rule order is total | §7.5 | priority then `rule_id`, always | no two rules compare equal |
| T7 | `UNKNOWN` does not satisfy a capability | §6.2 | `NO_ELIGIBLE_MODEL` | the central rule of v1 |
| T8 | `DECLARED` does not satisfy a capability | §6.2 | `NO_ELIGIBLE_MODEL` | as T7 |
| T9 | `VERIFIED` satisfies a capability | §6.2 | `SELECTED` | the control that proves T7/T8 are not a blanket refusal |
| T10 | a multimodal requirement matches on modality | §6.3 | matched on `modality` | no invented capability |
| T11 | no matching rule | §7.6 | `NO_ELIGIBLE_MODEL` | no implicit default |
| T12 | an unresolvable `model_ref` | §7.7 | `MODEL_UNAVAILABLE` | no substitution |
| T13 | a duplicate `rule_id` | §12.4 | `INVALID_RULES` | not resolved by keeping the first or last |
| T14 | an unsupported rule-set version | §12.4 | `INVALID_RULES` | as T13 |
| T15 | a fallback does not relax a constraint | §9 | the fallback fails too | fallback is not a loophole |
| T16 | a fallback does not widen the candidate set | §9 | refused | no reaching outside `candidates` |
| T17 | a fallback does not bypass Guard | §8, §9 | no authorization is produced | Router is not a gate |
| T18 | a selection carries no permission | §8 | no grant anywhere in the decision | selection ≠ authorization |
| T19 | a stronger model does not raise a level | §8 | unchanged | exactly the bypass F-09 closes |
| T20 | `sensitivity` narrows and never widens | §5.2 | the set shrinks or holds | carried, not granted |
| T21 | no inference from a tool name or path | §15 | the level is not derived | no name-based privilege |
| T22 | a capability is never promoted | §6.2 | statuses unchanged after routing | AI-07 does not probe |
| T23 | the Router makes no provider call | §14 | no transport is reachable | it selects, it does not execute |
| T24 | the Router starts no process | §14 | no subprocess is reachable | as T23 |
| T25 | a routing decision is not Evidence | §13.2 | no record, no admission call | routing fact ≠ research fact |
| T26 | no new AI-05 event is registered | §13.2 | the AI-05 registry is unchanged | a frozen registry is not AI-07's to edit |
| T27 | a decision record carries no content | §13.3 | no prompt, argument or credential | as T3 |
| T28 | the decision names the rules revision | §12.3 | the revision used is recorded | an unattributed decision is not auditable |
| T29 | `require_independence` is expressed, not executed | §11 | no second agent runs | AI-08 owns it |
| T30 | no rule set is written or fetched | §12.2 | the Router only reads | configuration is reviewed, not generated |
| T31 | the outcome vocabulary is AI-07's own | §10.1 | not merged with Guard, Status or Tool vocabularies | the three stay distinct |
| T32 | no outcome becomes a selection | §10.2 | every failure stays a failure | fail closed |
| T33 | `routing/` is not a plugin layer | §1.1, §17 | no `__init__.py`, not under `plugins/` | the identity is structural |
| T34 | `routing/` does not import the tool layer | §17 | no import | the boundary is checked |
| T35 | architecture boundary | §4.3, §16 | parsed with `ast`: no network client, no subprocess, no `eval`/`exec`/`compile`, no Guard or Evidence import, no secret logging | the boundary is checked, not promised |
| T36 | the contract and `routing/README.md` agree | §3 | the same identity and the same prohibition | a document that contradicts its own directory is a defect |
| T36b | AI-02's no-default invariant holds | §3.3 | `tests/unit/test_model_scope.py` still passes and no preference is written into `providers/` | AI-07 does not smuggle a default into the model layer |
| T37 | regression | non-regression | the pre-existing suite's pass count does not decrease | a phase never trades away existing guarantees |
| T38 | Layer 0 | §20 | the AI-07 check runs and passes | the gate exists and fires |

### 19.1 Notes

```text
T7 to T9 are one boundary in three parts, and T9 is the control. Without it, T7 and
  T8 are satisfied by a Router that never selects anything.
T15 to T17 are the fallback boundary. T17 is the one that matters: a fallback that
  reached an authorization would be the bypass §8 exists to prevent.
T18 to T21 are the authorization boundary. T19 is F-09 restated as a test.
T25 and T26 are the Evidence boundary, and T26 is asserted against AI-05's own
  registry rather than against a copy of it.
```

---

## 20. Exit Gates

AI-07 is complete only when every gate below passes.

| # | Gate | Condition |
| --- | --- | --- |
| C0 | Contract frozen | this document is frozen and its amendment log is open |
| C1 | Router implemented | request, rules, decision, evaluation — and it selects |
| C2 | Determinism verified | same input, same decision; ordering is total |
| C3 | Capability rule verified | UNKNOWN never satisfies; VERIFIED does |
| C4 | Authorization boundary verified | no selection grants, widens or bypasses anything |
| C5 | Fallback boundary verified | no relaxation, no widening, no bypass, no retry |
| C6 | Failure semantics verified | every outcome is distinct, and none becomes a selection |
| C7 | Configuration boundary verified | reviewed files only; no discovery, no runtime write |
| C8 | Evidence boundary verified | no record written, no event registered, no content carried |
| C9 | Layer 0 PASS | the AI-07 structural and behavioural check exists and passes |
| C10 | Full offline tests PASS | layers 1–3, with the counts recorded |
| C11 | Required CI PASS | CI green on the head the phase claims |
| C12 | Evidence artifact complete | `docs/AI-07_EVIDENCE_<date>.md` |
| C13 | Scope and diff audit clean | the diff is inside `routing/`, `config/routing/`, docs and tests |

---

## 21. AI-07-B — Implementation Execution Brief

```text
branch   feature/ai-07-router-v1, from the then-current real main
PR       exactly one, and AI-07 opens two in total: this contract, and that one
```

It MUST contain: the router, the rule engine, the decision record, the tracked default rule set,
tests for T1–T38, the AI-07 Layer 0 check, `docs/AI-07_EVIDENCE_<date>.md`, and the status sync.

It MUST NOT contain: a plugin layer, a provider call, a tool call, a Guard change, an Evidence
change, an AI-08 path, a learned or LLM-produced decision, or any default rule set presented as
tuned.

Any conflict between this contract and an existing implementation STOPS the work: locate it,
record it, amend this contract (§18), then continue.

---

## 22. Amendment log

```text
(none)
```

---

## 23. Freeze record

```text
AI-07-A   FROZEN    this document
base      main @ 3b1917ab596931ec89de8c17a02266b5902557a5
date      2026-10-01

Frozen here:
    the core-service identity, and that routing/ is not a plugin layer
    RouterRequest, and that it carries descriptors and never content
    the AI-02 consumption surface: five capabilities, modality, limits, pricing
    the rule that UNKNOWN is not available, and its consequence for v1
    the rule model: priority, matching, a total ordering, no default, no substitution
    RoutingOutcome, six members, not merged with any other vocabulary
    the fallback boundary, the authorization boundary, the second-opinion boundary
    the Evidence boundary: a decision record, and no AI-05 event
    the configuration boundary: reviewed tracked files, no discovery, no runtime write
    the no-hidden-inference rule

Not decided here:
    how an independent Agent is identified        AI-08's
    whether a rule set needs Guard to change      OPEN, default recorded (§12.2)
    whether AI-02 exposes a latency class         DEFERRED; none exists today (§6.4)
    routing decisions in Evidence                 an AI-05 amendment first (§13.2)
    multi-workspace discovery                     AI-00 §17; §12.1 does not resolve it
    the tuned rule set                            F-12: that is Router v2's, on benchmark data
```

```text
This document freezes a contract. No router exists, no rule has been evaluated, no model has been
selected, and this document is not evidence that any of it works.
```
