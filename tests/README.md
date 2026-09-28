# Tests

Workbench validation, organised into the five layers defined in
[AI-02 §12](../docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md).

| Layer | What it checks | Where | In CI |
| --- | --- | --- | --- |
| **0** | repository policy — required files, layout, no secret files, shell syntax, no credential values in example config, and that the default workflow cannot reach a provider | `scripts/ci/layer0_policy.py` | yes |
| **1** | contract and schema — provider and model profiles, `model_ref` resolution, credential references, the capability truth model | `pytest -m layer1` | yes |
| **2** | behaviour through a fake transport — normalization, finish states, error taxonomy, the capability gate, metrics, pricing | `pytest -m layer2` | yes |
| **3** | offline contract fixtures pinned by provenance | `pytest -m layer3`, `fixtures/` | yes |
| **4** | **live connectivity verification** | `tests/live/`, `scripts/live/` | **never** |

## Running the layers

```bash
python3 scripts/ci/layer0_policy.py    # layer 0
python -m providers.validate           # layer 1 (schema, outside pytest)
python -m pytest -m layer1             # layer 1
python -m pytest -m layer2             # layer 2
python -m pytest -m layer3             # layer 3
python -m pytest                       # layers 1-3 together, still never 4
```

Layers 1–3 need no credential, no network, and no provider access. They pass
with `DEEPSEEK_API_KEY` and `MIMO_API_KEY` unset, which is the condition CI
runs under.

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
