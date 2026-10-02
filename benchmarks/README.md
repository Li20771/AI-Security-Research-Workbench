# benchmarks/ — AI-11, AI Security Benchmark

A Workbench **CORE layer**, reached as the top-level `benchmarks/` namespace package
exactly as `agents/`, `review/` and `routing/` are.

```text
FROZEN: AI-11's home is benchmarks/.
FROZEN: plugins/benchmark/ and plugins/ai11/ MUST NOT exist. plugins/ holds exactly
        four layers, owned by AI-03, AI-04, AI-05 and AI-06.
FROZEN: AI-11 MUST NOT add a fifth plugin layer.
```

Like every core layer a phase added (`routing/`, `agents/`, `integrations/`, `review/`),
this directory is a **namespace package**: there is no `benchmarks/__init__.py`, and
imports name the module (`from benchmarks.task import TaskDefinition`). The Layer 0 gate
asserts the absence, the same way it does for the other four.

## What it is

```text
fixed task
  + fixed source SHA
  + isolated workspace
  + independent oracle
  + auditable execution / tool / test / diff facts
  =  a repeatable benchmark measurement
```

Everything here is a consequence of one refusal:

```text
an Agent's own statement that it succeeded is NEVER the reason a task is recorded as
successful, and exit code == 0 is not PASS.
```

## Layout

```text
benchmarks/            the layer. vocabulary, schema, runner, oracle, workspace,
                       executor and the replay entry point
benchmarks/tasks/      the versioned task corpus. TRACKED and durable (§17.4)
benchmarks/results/    run data. GITIGNORED and disposable by default
```

### The modules

| module | what it holds |
| --- | --- |
| `vocabulary.py` | the six closed vocabularies AI-11 owns, and the reporting precedences |
| `errors.py` | the refusal taxonomy. A rejection is not a verdict |
| `task.py` | `TaskDefinition` — what a task IS. It never holds a result |
| `run.py` | `BenchmarkRun`, `TestCounts`, `ToolTraceEntry`, `HostRecord` |
| `oracle.py` | the oracle protocol, the §11 skip-aware PASS rule, the aggregates |
| `oracles.py` | the corpus judges. Pure decisions, so §7.4 is testable without tools |
| `workspace.py` | derivation, the manifest digest, and the read-only rule |
| `executor.py` | the deterministic **non-model** reference executor |
| `replay.py` | `python3 -m benchmarks.replay <task_id>` — the reproduction entry point |

### The corpus

```text
benchmarks/tasks/<task_id>/task.yaml        the TaskDefinition
benchmarks/tasks/<task_id>/control/         the oracle's material: truth, known_good,
                                            known_bad. NEVER in the agent-visible tree
benchmarks/tasks/<task_id>/task/            material the task itself ships
```

Six tasks, covering firmware, yara, can, uds, reverse and fuzzing-recovery. Five are
Tier A; `ai11-v1-fuzzing-recovery-triage` is Tier B because it needs an exclusive
`vcan0` and `CAP_NET_ADMIN`, which a CI runner cannot satisfy at all.

## What it does not do, and will not

```text
no provider call                 no model measurement in v1
no AI-05 EvidenceRecord          no producer token is admissible (AI-05 28, OPEN)
no durable model-output store    no stored model output of any kind
no ranking, no winner            no composite score across tasks
no retry, resume or workflow     those are AI-13's
no SecurityLab write             the source is read strictly
```

## Running it

```bash
python3 -m benchmarks.replay ai11-v1-can-dbc-decode
python3 -m benchmarks.replay ai11-v1-can-dbc-decode --variant known_bad
python3 -m pytest tests/benchmarks -q
python3 scripts/ci/layer0_policy.py
```

`benchmarks.replay` runs the **reference** executor. It measures no model, and a run it
produces MUST NOT be presented as a model result.

## Status

```text
AI-11-A   contract FROZEN   PR #62, blob 08aea86cf82e7476dee442b33dc81c8f9a9873a3
AI-11-B   this implementation
AI-11-C   NOT STARTED       the measured campaign
```
