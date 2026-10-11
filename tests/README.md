# Tests

Workbench validation, organised into the five layers defined in
[AI-02 §12](../docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md).

| Layer | What it checks | Where | In CI |
| --- | --- | --- | --- |
| **0** | repository policy — required files, layout, no secret files, shell syntax, no credential values in example config, and that the default workflow cannot reach a provider | `scripts/ci/layer0_policy.py` | yes |
| **1** | contract and schema — provider and model profiles, `model_ref` resolution, credential references, the capability truth model | `trust_harness.py regression -- pytest -m layer1` | yes |
| **2** | behaviour through a fake transport — normalization, finish states, error taxonomy, the capability gate, metrics, pricing | `pytest -m layer2` | yes |
| **3** | offline contract fixtures pinned by provenance | `pytest -m layer3`, `fixtures/` | yes |
| **4** | **live connectivity verification** | `tests/live/`, `scripts/live/` | **never** |

## Running the layers

```bash
python3 scripts/ci/layer0_policy.py    # layer 0
python -m providers.validate           # layer 1 (schema, outside pytest)
python tests/evidence/trust_harness.py regression -- python -m pytest -m layer1   # layer 1
python -m pytest -m layer2             # layer 2
python -m pytest -m layer3             # layer 3
python tests/evidence/trust_harness.py regression -- python -m pytest   # layers 1-3 together, still never 4
```

Layers 2 and 3 are unchanged: no test outside `tests/evidence/` calls
admission, so they run under plain `pytest` and need no launcher.

### Layer 1 runs through a launcher, and here is why

The evidence layer tests call `admit()` / `admit_to_store()`, and producer
authentication runs inside that path. Its reader reads the deployment's trust
configuration **once, when the module initializes**, and holds that state for
the life of the process — so the configuration has to reach a process that has
not started yet. A launcher supplies it to a child process at startup, which is
exactly what a deployment does; only the process boundary differs.

`tests/evidence/trust_harness.py` is that launcher, and it is also the single
place permitted to name the variable. **Running `pytest -m layer1` directly
does not fail because anything is broken**: with no configuration the reader is
`INVALID` by design, every submission reaching the authentication step is
`REJECTED` with `AUTHENTICATION_KEY_UNAVAILABLE`, and the cases that assert a
successful admission therefore fail. That is the contract's fail-closed
behaviour, and it means a bare `pytest -m layer1` **cannot be used to verify the
positive admission path**.

The launcher changes nothing else: same interpreter, same working directory,
same pytest arguments, same test selection.

Layers 1–3 need no credential, no network, and no provider access. They pass
with `DEEPSEEK_API_KEY` and `MIMO_API_KEY` unset, which is the condition CI
runs under.

### The producer-authentication acceptance matrix

`tests/evidence/test_producer_authentication.py` is **not** part of the plain
layer-1 run above: the launcher step excludes it
(`--ignore=tests/evidence/test_producer_authentication.py`). It is a
**multi-configuration** module — each case asserts the outcome that *its* trust
configuration must produce — and the configurations it needs (an absent
mapping, a mapping with no entry for the claimed token, §7.3.2's collision
shapes, and the distinct-key control) cannot all be in effect in one process,
because §7.3.11 reads the configuration once at the reader's initialization and
§31.3 makes that state final for the life of the process.

The formal acceptance for §7.3.7 therefore runs as **eight separate launcher
invocations**, in the `Layer 1 — producer authentication acceptance matrix
(8 configurations)` step of `.github/workflows/preflight.yml`. **Every group
must start its own `trust_harness.py`**: merging two groups into one process
would put one configuration's state behind the other group's name, and the
result would be reported for a configuration that was never in effect.

`collision_unregistered` and `collision_unregistered_b` are **different policy
scenarios** — §7.3.2's two policies for the one case they treat differently.
Both groups run `test_obligation_06c_reader_is_consistent`, and **their two
results are never merged**: under the A policy the tolerated mapping stays
usable (while §6.6 still refuses the record during construction), under the B
policy the whole mapping is refused. Each run is evidence only for its own
configuration, and the run that produced it is the only thing that says which
configuration that was.

`skip` is **not** a pass, and neither is an environment failure or a run that
produced no business verdict. A configuration group that fails fails the job; a
case that could not produce a verdict is reported as such rather than counted as
a refusal by the authentication logic.

## Layer 4 is never run by default

`pytest.ini` deselects it (`-m "not layer4"`), and the default workflow
contains no opt-in flag, no provider endpoint, no HTTP client, and no `-m
layer4`. `scripts/ci/layer0_policy.py` asserts all four against the workflow
files, so the exclusion is checked rather than promised.

The barrier is that CI never calls Layer 4. It is deliberately **not** "the
network happened to be unreachable" — an unreachable endpoint is not evidence
that a live check was never attempted.

Layer 4's absence is `NOT_RUN`, and `NOT_RUN != PASS`: a check that did not run
supports no capability claim.

### Running it

`.github/workflows/live-model-verification.yml` is `workflow_dispatch` only —
no push or pull request trigger — and is the only place a provider is
contacted. It additionally requires:

```text
WORKBENCH_LIVE_TESTS=1        explicit opt-in
+ provider in the allowlist   deepseek | mimo
+ a resolvable credential     from repository secrets
+ a registered model_ref
```

Locally:

```bash
WORKBENCH_LIVE_TESTS=1 python -m pytest -m layer4
```

Absent any precondition the run records `BLOCKED` or `NOT_RUN` and performs no
network activity, and the tests assert that rather than assuming it.

### What a live run produces

An **evidence artefact**, never a grant. `evidence/runs/` is gitignored, and
the workflow declares `permissions: contents: read`, so nothing can commit.
Each capability carries a *candidate* status for a human to review; applying it
to a profile is a separate, reviewed change.

A passing text completion promotes nothing. Tool calling, structured output,
streaming, reasoning, and prompt caching each need their own observation, and
the ones with no safe bounded probe — streaming, reasoning, prompt caching —
stay `UNKNOWN` with the reason recorded.

## Every module belongs to exactly one layer

Each test module declares one marker (`layer1`, `layer2`, or `layer3`). Layer 0
enforces that, so a module cannot end up belonging to no layer and be silently
skipped by every CI step.

## Directories

- `unit/` — the offline suite; modules are marked by layer, not by directory
- `fixtures/` — Layer 3 payloads and their provenance manifest
- `integration/`, `guard/`, `benchmarks/` — reserved for later phases
