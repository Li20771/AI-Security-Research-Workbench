# AI-12-B — Policy Core — Evidence

> Phase: **AI-12 — Model Routing v2**
> Sub-phase: **AI-12-B — the policy core**
> Status: **IMPLEMENTATION COMPLETE / PR OPEN** — not merged, not CLOSED
> Date: 2026-10-03
> Baseline: `main` @ `60c630d83c576a013f828fa8ec5414f34fd9974c`
> Contract: [AI-12_MODEL_ROUTING_V2_EXECUTION_PLAN.md](AI-12_MODEL_ROUTING_V2_EXECUTION_PLAN.md) (`b6e3cc8b`)

---

## 1. What this sub-phase did, and what it did not

AI-12-A froze what AI-12 may consume and may claim. AI-12-B implements the artifact
that consumes it:

```text
AI-11 measured facts  ->  AI-12 declared policy  ->  a validated policy artifact
                                                         + an explainable
                                                           resolution
```

```text
IMPLEMENTED / OFFLINE VERIFIED
    the policy artifact and its validator           routing/policy.py
    the supplied-evidence input and its identity    routing/evidence.py
    the resolution, explainability and audit        routing/policy_eval.py
    the AI-12 Layer 0 boundary                      scripts/ci/layer0_policy.py
    focused tests, including mutation controls      tests/routing/test_policy_core.py
                                                    tests/routing/test_policy_layer0.py

NOT RUN
    live provider call                              none is made anywhere
    per-model measurement                           none exists (§6)
    AI-12-C, the campaign over policies             not started

BLOCKED
    the model-comparative prerequisite (§6)         unchanged by this sub-phase

UNKNOWN
    every input §5.1 marks NO: tool-call facts, cost, latency, per-model history
```

**Nothing here claims a model performs better than another model.** No model was
called, no model was measured, and no policy can select one today.

---

## 2. What was built

```text
routing/evidence.py      EvidenceClass · EvidenceRef · SuppliedRecord · supplied_records
routing/policy.py        Falsifier · DiscriminationControl · Rollback ·
                         FallbackDeclaration · EscalationDeclaration ·
                         PolicyRule · Policy · PolicyState
routing/policy_eval.py   resolve_policy · verify_resolution · PolicyResolution ·
                         PolicyOutcome · RuleDisposition · EvidenceDisposition
config/routing/policy.example.yaml
                         the tracked example: the mechanism, deliberately not tuned
```

The policy core lives under `routing/` beside AI-07's Router, because AI-12 supplies
the policy AI-07 is given. It is not a second router, not a plugin, and not a runtime.

### 2.1 The verdict vocabulary is AI-11's, imported and not redefined

```text
from benchmarks.vocabulary import OracleVerdict
```

One frozen vocabulary, one definition. AI-12's Layer 0 check permits exactly this
module and nothing else under `benchmarks/` from the policy core: a core that could
reach `benchmarks.runner` or `benchmarks.campaign` could re-run the benchmark, which
§4.1 forbids.

### 2.2 Evidence identity is the run, not the task

An `EvidenceRef` carries `run_id · task_id · source_sha · workbench_sha · verdict ·
reason_code · limitations · evidence_class`, and a `SuppliedRecord` adds a
`record_digest`. Two records claiming one `run_id` are refused rather than
tie-broken: a run is one measured run, and §5.3 makes that the identity.

An empty `reason_code` is accepted **only** under `PASS`, because AI-11 records
exactly that — there is no refusal for a PASS to name — while a non-PASS record with
no reason is one a reader cannot act on.

---

## 3. The five refusals this sub-phase exists for

```text
REFUSED                                          WHERE
a selecting rule justified by REFERENCE evidence  policy.py, §4.2 — and P6/P14 show
                                                  the honest DORMANT that results
a rule with no falsifier                          policy.py, §7 — a rule nothing
                                                  could contradict is not admitted
a rule with no discrimination control             policy.py, §7 — and equal halves
                                                  are refused: one input compared
                                                  with itself distinguishes nothing
an ACTIVE policy with no rollback metadata        policy.py, §8 — "activated with
                                                  no way back" is unrepresentable
a score / weight / confidence / ranking /         policy.py, §4.3 and §9 — refused
aggregate / prior field                           BY NAME, so the message says
                                                  which forbidden idea arrived
```

---

## 4. What a resolution says today

The one selecting rule this contract admits requires `MODEL_EXECUTION` evidence —
§4.2 forbids justifying a selection with a REFERENCE run — and no such measurement
exists. So the tracked example, and any policy over AI-11's six records, resolves:

```text
outcome               DORMANT
selected_model_ref    null
evidence              six records, each accounted for
                        five PASS     REJECTED_BY_EVIDENCE_CLASS
                        one BLOCKED   REJECTED_BY_VERDICT
missing_scope_tasks   ()
```

```text
FROZEN: BLOCKED, NOT_RUN, UNKNOWN and UNAVAILABLE are not promotable.
```

The `BLOCKED` record is not filtered, not zeroed and not neutralised: it appears in
the resolution with its own verdict, its own reason code
(`PRECONDITION_UNMET:environment:vcan0-exclusive`) and its own digest. Dropping it
does not make the policy look complete — it produces `INCOMPLETE_EVIDENCE` naming the
task, which is a visible defect rather than a silent one.

`DORMANT` is the honest answer here, not a gap to be filled with a default, a prior
or a weight.

---

## 5. The mutation controls

Six documented mutation controls, each taken from a WORKING artifact, mutated into
the shape under test, with the focused test required to notice. Run as a harness
against the real modules:

```text
M3  let a REFERENCE run justify a model selection (§4.2)        caught
M4  stop refusing score/weight fields (§4.3, §9)                caught
M6  activate without rollback metadata (§8)                     caught
P9  let any verdict satisfy a PASS requirement (§4.3)           caught
P10 stop reporting a task dropped from the scope (§4.4)         caught
P13 audit that cannot notice a tampered resolution (§8)         caught
```

Each of those tests fails if its check is removed, rather than only if the check was
never written. The rest of the file names its own mutations inline (`M1`, `M2`,
`M5`, `M7`, `M8`).

---

## 6. Verification

```text
tests/routing                                    204 passed
tests/routing/test_policy_core.py                 58 passed   (P1-P15, M1-M8)
tests/routing/test_policy_layer0.py               12 passed   (T40-T51)
full offline suite                             3412 passed, 5 skipped, 5 deselected
Layer 0                                         PASS (21 checks)
compileall                                      exit 0
providers.validate                              exit 0
plugins.context.validate                        exit 0
git diff --check                                clean
```

Layer 0 gained one check, `policy core boundary and scoring absence`, whose own tests
plant each violation in a scratch tree and require it to be caught — including the
baseline that it reports nothing on the real repository.

### 6.1 One historical assertion was corrected, not deleted

`tests/agents/test_layer_boundaries.py::test_no_tests_were_added_under_tests_routing`
asserted the exact file set under `tests/routing/`, which was a true proxy while AI-07
was the only phase with tests there. AI-12-B legitimately added the policy core's
tests. The assertion now says what it meant — no file under that directory is named
for the agent layer, and AI-07's suite is still present so an empty directory cannot
satisfy it vacuously.

---

## 7. What is NOT claimed

```text
NOT CLAIMED   AI-12 routing is proven better
NOT CLAIMED   a model was selected successfully
NOT CLAIMED   the benchmark validates a model choice
NOT CLAIMED   the model-comparative prerequisite is satisfied
NOT CLAIMED   AI-12 is CLOSED
```

```text
AI-12-A  = COMPLETE / MERGED          contract frozen (merge 60c630d8)
AI-12-B  = IMPLEMENTATION COMPLETE / PR OPEN
AI-12    = NOT CLOSED
AI-12-C  = BLOCKED / NOT STARTED      §6's prerequisite is unmet
```

The prerequisite is unchanged and is not satisfied by this sub-phase: implementing
the infrastructure does not produce a per-model measurement, and a policy schema that
validates cleanly is not evidence that any model outperforms another. Satisfying it
needs a separate contract defining the producer, attribution and measurement method
of a model execution.

```text
no provider call
no model measurement
no runtime fallback, retry or escalation
no score, weight, ranking, aggregate or composite value
no change to AI-07, AI-11 or AI-05
no SecurityLab write
```
