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

## K. Post-review verification — §15.1 execution-order fix

**This section is separate from §A–§J, which record the initial implementation
as it was. Nothing above has been rewritten.** In particular `C10` in §H is
still `NOT_RUN`: no PR existed when that section was written, and it was
correct then. The gate's current status is in §K.3.

### K.1 The defect

§15.1 of the frozen contract:

> Checked **before policy**, never overridden by any rule, priority, or approval

and §14.1:

> 1. evaluate safety invariants (§15.1) — any violation -> `DENY`, stop

`evaluator.evaluate()` ran the absolute-deny gate at step 5, **after** policy
presence, parsing and validation. Measured before the fix:

```text
secret_material + policy = None       -> BLOCKED / POLICY_MISSING
secret_material + invalid policy      -> BLOCKED / POLICY_INVALID
normal          + policy = None       -> BLOCKED / POLICY_MISSING
```

The first two rows are wrong. Both are non-`ALLOW`, which is why every existing
test passed and the defect survived a full test suite — the *decision* was
safe, and only the *reason* was wrong.

This is the more subtle half of a fail-closed boundary: `BLOCKED` says "supply a
policy and try again", which is precisely the instruction one should not give
someone reaching for a credential. The refusal has to be the answer, not a
precondition on the way to it.

### K.2 The fix

Minimal, and confined to `plugins/guard/evaluator.py`:

```text
before                              after
1. normalize                        1. normalize
2. policy presence / parsing        2. absolute safety invariants (§15.1)
3. workspace agreement              3. policy presence / parsing
4. policy validation                4. workspace agreement
5. absolute safety invariants       5. policy validation
6. ordering                         6. ordering
7. walk                             7. walk
8. approval / target gates          8. approval / target gates
9. assembly                         9. assembly
```

`check_absolute_deny()` itself is **unchanged**. Normalization still runs first
and still produces `DENY` for a malformed or unscoped request, because a request
must be readable enough to evaluate a boundary at all. A one-line helper,
`_policy_if_readable`, lets the gate name the policy in its provenance when one
happens to be readable without ever requiring one to parse — a malformed policy
must not be able to stop a security refusal, which is the entire point of moving
the gate.

Measured after:

```text
secret_material + policy = None       -> DENY    / SECRET_MATERIAL_ACCESS
secret_material + invalid policy      -> DENY    / SECRET_MATERIAL_ACCESS
normal          + policy = None       -> BLOCKED / POLICY_MISSING
```

### K.3 Regression tests

Added to `tests/guard/test_gates.py` as two classes, named for what they
actually test — precedence and execution order, not a single condition:

```text
TestAbsoluteDenyPrecedence                    8 tests
    case 1  secret material vs a missing policy
    case 2  secret material vs an invalid policy
    case 2b secret material vs a duplicate rule_id   (a second invalid path)
    case 3  secret material vs a workspace mismatch
    case 3b secret material vs a permissive ALLOW
    plus: no rule is blamed; a readable policy is still named;
          an unreadable policy cannot stop the deny

TestAbsoluteDenyPrecedenceDoesNotOverreach    5 tests
    the narrower regression: BLOCKED/POLICY_MISSING and BLOCKED/POLICY_INVALID
    still hold for ordinary requests, workspace mismatch is still DENY, and an
    ordinary ALLOW is unaffected
```

The second class exists because a precedence fix can overreach. Removing the
gate entirely would fail the first class; so would leaving it at the wrong point
in the sequence, which is the failure mode actually observed. The second class
pins the other direction.

No existing test was deleted, renamed or weakened to accommodate the fix.

### K.4 Post-review verification

```text
tests/guard      = 282 passed   (was 267; +15 precedence tests)
whole repository = 1599 passed, 5 deselected   (was 1584; no regressions)
Layer 0          = PASS (13 checks)
git diff --check = clean
security checks  = clean (AST-based; see §F)
```

Two `grep` hits were investigated and are false positives, recorded so a later
reader does not re-investigate them: `re.compile(` in `policy.py` is a regex
pattern constant, not the builtin `compile()`; and the `subprocess` hit is the
word in `__init__.py`'s docstring stating that Guard uses none. The `ast`-based
tests in `TestT15Regression` assert the real property and pass.

### K.5 Status at post-review

```text
C0-C9 = PASS
C10   = PASS   <- CI run 36576531723 @ 976a77f, before this fix
C10   = NOT_RUN at the new head until its own CI run completes
```

C10 is a property of a commit. The run above validated the pre-fix head; this
fix produces a new head whose checks had not run when this section was written.
The earlier `NOT_RUN` in §H is retained rather than edited, because it was
accurate for the moment it described.

### K.6 Scope of the fix

```text
contract changed      = NO
decision semantics    = unchanged (ALLOW / DENY / BLOCKED / UNKNOWN all mean
                        what they meant; one outcome moved to the right reason)
policy semantics      = unchanged
ordering              = unchanged
digest design         = unchanged
Guard API             = unchanged
files changed         = plugins/guard/evaluator.py, tests/guard/test_gates.py,
                        and this document
```

No contract amendment was required: the contract already said what the correct
order was, and the implementation did not follow it. That is a defect, not an
ambiguity.

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
