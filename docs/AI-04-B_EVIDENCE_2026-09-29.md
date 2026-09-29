# AI-04-B — Guard Implementation Evidence

> Status: **IMPLEMENTATION COMPLETE — CI pending on this branch**
> Phase: AI-04 — Security Guard Plugin
> Sub-phase: **AI-04-B — Implementation**
> Date: 2026-09-29
> Base SHA: `8b1af38754681955615f7b1a228fb90c1215615c`
> Branch: `feature/ai-04-guard-implementation`

This document records what AI-04-B built, what was verified, and — with equal
weight — what was **not**. It is not a closeout: no PR exists at the time of
writing, so `C10` is `NOT_RUN`.

```text
AI-04-A = COMPLETE / MERGED      contract frozen at 8b1af38 (Amendment 9)
AI-04-B = COMPLETE               implementation + tests + evidence
AI-04-C = NOT_RUN                PR / CI / merge

C10 required CI checks = NOT_RUN
```

---

## A. Baseline

Read from the repository, not assumed:

```text
origin/main = 8b1af38754681955615f7b1a228fb90c1215615c
branch base = 8b1af38754681955615f7b1a228fb90c1215615c   (fast-forwarded, not rebased)
working tree at start = clean
Guard Python at start = 0 files
```

`feature/ai-04-guard-implementation` was created from `bb62f953` before Amendment
9 landed. It carried **zero commits**, so it was advanced to the new baseline by
`git merge --ff-only` — no rebase, no reset, no force push. The contract was
re-read from the branch after the fast-forward rather than from any earlier
record.

---

## B. What was built

```text
plugins/guard/
    __init__.py       public surface
    errors.py         failure taxonomy, each class carrying a reason code
    vocabulary.py     closed enums, aggregation precedence, frozen-type re-exports
    models.py         request normalisation, decision record, provenance
    policy.py         Policy / Rule / Predicate / FieldRef, §9.2 validation
    predicates.py     §6/§7/§8 resolution gates, predicate evaluation
    ordering.py       §12.2.2 structural specificity linearization
    digest.py         §20 canonicalization and the three digests
    evaluator.py      §14.1 walk, §15 boundaries, §16 target gate, entry point
```

```text
implementation = 3 244 lines across 9 modules
tests          = 1 874 lines across 9 modules (+ conftest)
```

The structure follows §28.3's advice not to build a single omnibus `guard.py`.
`ordering.py` and `digest.py` are separate because both encode a frozen property
(a total order; a canonical form) that is worth being able to point at.

---

## C. Test results

Every T item maps to at least one automated test (§28.4).

| T | Covers | Where | Result |
| --- | --- | --- | --- |
| T1 | Workspace isolation | `test_workspace_scope.py` | PASS |
| T2 | Missing policy | `test_policy.py::TestT2MissingPolicy` | PASS |
| T3 | Unknown context | `test_context.py::TestT3UnknownContext` | PASS |
| T4 | Stale context | `test_context.py::TestT4StaleContext` | PASS |
| T5 | Explicit `DENY` | `test_decisions.py::TestT5ExplicitDeny` | PASS |
| T6 | Explicit `ALLOW` | `test_decisions.py::TestT6ExplicitAllow` | PASS |
| T7 | Conflicting rules, incl. 7a–7g | `test_ordering.py` | PASS |
| T8 | Default no-rule `DENY` | `test_decisions.py::TestT8DefaultDeny` | PASS |
| T9 | Malformed request | `test_decisions.py::TestT9MalformedRequest` | PASS |
| T10 | Policy boundary, 10a–10g | `test_policy.py` | PASS |
| T11 | Provenance | `test_decisions.py::TestT11Provenance` | PASS |
| T12 | Truth / status preservation | `test_context.py::TestT12TruthPreservation` | PASS |
| T13 | Fail-closed matrix | `test_fail_closed.py` | PASS |
| T14 | Determinism | `test_determinism.py` | PASS |
| T15 | Regression | `test_determinism.py::TestT15Regression` | PASS |

```text
tests/guard        = 267 passed
whole repository   = 1584 passed, 5 deselected
baseline           = 1317 passed, 5 deselected
delta              = +267 tests, 0 regressions
Layer 0            = PASS (13 checks)
git diff --check   = clean
```

---

## D. T7g — the Amendment 9 counterexample

The sub-case that would have caught the defect Amendment 9 fixed. Built on real
vocabulary values, with the contract's abstract `a`/`b` fields instantiated:

```text
X = { action.id: eq "1", target.kind: eq "repository" }   rule_id r3
Y = { action.id: eq "1" }                                 rule_id r1
Z = { target.kind: eq "service" }                         rule_id r2

X ⊏ Y      comparable
Y ∥ Z      incomparable
Z ∥ X      incomparable
```

Asserted:

```text
every input permutation emits the same order      PASS  (one order: Z, X, Y)
the documented order is Z, X, Y                   PASS  (§12.2.3)
specificity is preserved in every permutation     PASS  (X before Y, always)
no cycle is reported                              PASS
```

Sub-cases 7a–7f also pass, but they use rule sets a composite comparator orders
consistently — which is why they would not have caught the defect.

---

## E. Findings — discovered during implementation

Three defects were found by tests written against the frozen contract, not by
review. Two were in the implementation; one is a fact about the contract.

### E.1 `policy.digest` depended on predicate write order

**Found by** `test_determinism.py::test_predicate_permutation_leaves_the_aggregate_unchanged`.

§20.3 declares `match` and `conditions[]` **set-semantic** — "sorted canonically
before hashing". The implementation serialised them in declared order, so two
policies whose predicates differed only in written order produced different
`policy.digest` values and therefore different `evaluation_digest` values, for
identical semantics. This is the same class of defect as Amendment 9's
including one level down: a digest that moves when nothing semantic did.

Fixed: `Predicate.canonical_key` and the `Rule.canonical_match` /
`canonical_conditions` properties sort both collections, and `in` literals are
sorted because a set has no order.

### E.2 The request silently accepted unknown fields

**Found by** `test_gates.py::test_the_record_carries_no_field_for_a_credential_value`.

§4 requires that "no credential value, prompt body, provider secret, or raw
sensitive payload may enter the Guard request", but an unrecognised top-level
key was ignored rather than refused. Ignoring is safe in the narrow sense — the
field never reached the record — but it leaves the field in the caller's payload
with nothing recording that Guard declined to use it.

Fixed: unknown top-level keys are refused. This follows AI-02's provider
registry, which rejects unknown profile fields for the same reason ("a profile
that carries them is rejected rather than silently ignored, so the layering
cannot drift back").

### E.3 §21's "ambiguous rule ordering" row is unreachable

Not a defect — a fact worth recording. §21 requires `BLOCKED` for an ambiguous
rule ordering, but §9.2 makes `rule_id` unique and §12.2.2's linearization is
total over a unique-id rule set, so no reachable rule set leaves the order
ambiguous. The row is defence-in-depth.

It is therefore **absent from T13's matrix** rather than given a fabricated case
that would not actually be ambiguous; the `OrderingCycle` guard that implements
it is exercised directly in `test_ordering.py::TestRunawayGuard`, by forcing the
relation into a cycle. It should be unreachable, but the alternative to detecting
it is an infinite loop in an authorization path.

---

## F. Security checks (§28.3)

```text
eval / exec / compile / __import__ in plugins/guard      = none
subprocess                                                = none
network imports (socket, ssl, http, urllib, requests)     = none
imports of routing/ or tools/                             = none
imports outside the frozen-type allow-list                = none
secret logging                                            = none
```

Asserted mechanically in `test_determinism.py::TestT15Regression` by parsing each
module with `ast` rather than by substring matching, so a renamed import is still
caught.

The allow-list test asserts Guard imports **only**:

```text
plugins.context.classification, .context, .vocabulary, .workspace
providers.model_profile
```

An allow-list rather than a deny-list, because a deny-list only catches the names
someone thought of. It also avoids naming AI-02's live-only transport, which
would itself trip that package's confinement guard — a check worth keeping rather
than relaxing.

---

## G. Types reused rather than restated (§28.2)

Asserted by identity, not by name, in `test_determinism.py`:

```text
CapabilityStatus   is providers.model_profile.CapabilityStatus
WorkingTreeState   is plugins.context.vocabulary.WorkingTreeState
ItemKind           is plugins.context.vocabulary.ItemKind
StatusValue        is plugins.context.vocabulary.StatusValue
Freshness          is plugins.context.vocabulary.Freshness
```

Guard defines no second copy of any of them. Two definitions in one repository
means two places to update and one of them is forgotten.

---

## H. Exit gates (contract §27)

| # | Gate | Status | Evidence |
| --- | --- | --- | --- |
| C0 | Contract frozen and internally consistent | PASS | §8b1af38, Amendment 9 applied |
| C1 | Workspace isolation | PASS | T1, `test_workspace_scope.py` |
| C2 | Deterministic evaluation | PASS | T7a–7g, T14 |
| C3 | Fail-closed behaviour | PASS | T13, 26 matrix rows |
| C4 | `DENY` / `ALLOW` semantics | PASS | T5, T6, T8 |
| C5 | `UNKNOWN` / `NOT_RUN` / `BLOCKED` preservation | PASS | T12, 6 parametrised cases |
| C6 | Context freshness | PASS | T4, plus `CURRENT != STALE` assertions |
| C7 | Provenance completeness | PASS | T11 |
| C8 | Regression safety | PASS | 1584 passed, 0 regressions |
| C9 | Evidence completeness | PASS | this document |
| C10 | Required CI checks | **NOT_RUN** | no PR exists at time of writing |

**C10 is `NOT_RUN`, so AI-04-B is not closed.** Local execution is not CI
execution.

---

## I. Recorded, not hidden

- **No approval source exists**, so every approval-gated action — `system-change`,
  `remote-change`, `real CAN/ECU/vehicle` — is permanently `BLOCKED` (§8.2,
  D-12). This is the intended fail-closed state, verified by test, not a defect.
- **Guard performs no policy discovery.** Where a policy comes from remains Q-1.
  Verified by construction: `evaluate` takes it as a parameter.
- **`evidence_ref` is always `null`.** AI-05 is not implemented and is not a
  prerequisite (C9).
- **The condition grammar is exactly `eq`, `in`, `exists`.** No `OR`, no regex,
  no arithmetic. Disjunction is expressed by multiple rules (§11.1).
- **A test file was renamed** from `test_workspace.py` to
  `test_workspace_scope.py` because the basename collided with AI-03's
  `tests/context/test_workspace.py` and pytest could not disambiguate them under
  its default import mode. AI-03's file was not touched.

---

## J. Provenance

```text
Phase              = AI-04 Security Guard Plugin
Sub-phase          = AI-04-B Implementation
Base SHA           = 8b1af38754681955615f7b1a228fb90c1215615c
Branch             = feature/ai-04-guard-implementation
Implementation     = plugins/guard/ (9 modules, 3 244 lines)
Tests              = tests/guard/ (9 modules, 1 874 lines)
Guard Python files = 9

Local verification (offline, no credential, no network):
  pytest          = 1584 passed, 5 deselected  (baseline 1317; +267)
  tests/guard     = 267 passed
  Layer 0         = PASS (13 checks)
  git diff --check = clean
  security checks = clean

CI execution       = NOT_RUN (no PR yet)
PR                 = NOT_RUN
Merge              = NOT_RUN
SecurityLab        = untouched
AI-02 / AI-03      = untouched
main               = unchanged (8b1af38)
```
