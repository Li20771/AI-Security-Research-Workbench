# tests/benchmarks

AI-11's tests. Offline: no network, no credential, no external tool, nothing spawned
except where a test deliberately drives `benchmarks.replay` or the Layer 0 script.

```text
test_task_schema.py          layer 1   TaskDefinition, its grammar and its refusals
test_run_schema.py           layer 1   BenchmarkRun, TestCounts, the tool-trace boundary
test_benchmark_boundaries.py layer 1   the architectural boundary, and the Layer 0 gate
test_oracle_verdict.py       layer 2   the six verdicts, the skip rule, the aggregates
test_corpus.py               layer 2   the v1 corpus and its non-vacuity
test_benchmark_workspace.py  layer 2   derivation, digests and the read-only rule
```

## The three tests that carry the most weight

```text
test_corpus.py::test_T6/T7      for EVERY task, the known-good submission is judged
                                PASS and the known-bad one is judged non-PASS.
                                Without this a corpus is a list of claims.

test_oracle_verdict.py::T3      exit code 0, no record, is UNKNOWN — not PASS.

test_benchmark_boundaries.py    the Layer 0 check is run against scratch trees carrying
  ::T23..T27                    each violation in turn, so it is shown to be able to
                                fail rather than assumed to be able to.
```

## Running them

```bash
python3 -m pytest tests/benchmarks -q
```

The whole suite is offline. `pytest.ini` deselects layer 4, and AI-11 adds no layer 4:
the benchmark layer reaches no network and starts no provider.
