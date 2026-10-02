"""AI-11 §7.3, §15 — the reproduction entry point for the in-process oracles.

```text
python3 -m benchmarks.replay <task_id> [--variant known_good|known_bad] [--corpus DIR]
```

Every task's `oracle.reproduce_command` names this module, so the command recorded in
the corpus is the command a person actually runs. A `reproduce_command` that no one can
run is a comment.

### Why it speaks the process protocol

It prints the same `AI11-ORACLE:` line an out-of-process oracle prints, and it exits 0
when it produced a record. That is not decoration: it means the in-process judges and
the process judges travel through one protocol, and a test can drive either through
`run_oracle_command` without a second parser existing for the second kind.

### It is the REFERENCE path, and it says so

`--variant` selects the declared control submission, and the run is a REFERENCE run.
It measures no model. Its purpose is the one §20.4 states: prove the task is solvable,
prove the oracle discriminates, and show the harness is deterministic.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from benchmarks.errors import BenchmarkError
from benchmarks.executor import ReferenceExecutor, ReferenceVariant
from benchmarks.oracle import ORACLE_RECORD_SENTINEL, judge_observation, OracleProcessOutcome
from benchmarks.oracles import judge_submission
from benchmarks.task import load_task

__all__ = ["DEFAULT_CORPUS", "build_record", "main"]

#: The tracked corpus. Relative to this file, so the entry point works from any cwd.
DEFAULT_CORPUS = Path(__file__).resolve().parent / "tasks"


def build_record(task_id: str, variant: ReferenceVariant, corpus_root: Path) -> dict:
    """Run one reference task and return the oracle record as a mapping.

    The record is built by `judge_observation` rather than assembled here, so the
    in-process path is judged by the SAME skip-aware rule as the process path. A second
    assembly site is a second place for the rule to be forgotten.
    """
    task_dir = corpus_root / task_id
    task = load_task(task_dir / "task.yaml")

    executor = ReferenceExecutor(task, corpus_root)
    submission = executor.produce(variant)
    truth = executor.truth()

    judgement = judge_submission(task.oracle.oracle_id, submission.payload, truth)

    # Through the rule, not around it: the judgement's counts and verdict are re-entered
    # as if they had arrived from a process, so §11 is applied exactly once and in one
    # place for both paths.
    record = {
        "oracle_id": task.oracle.oracle_id,
        "verdict": str(judgement.verdict),
        "reason_code": judgement.reason_code,
        "skip_class": "NONE",
        **judgement.tests.to_mapping(),
    }

    verdict, counts, reason = judge_observation(record, OracleProcessOutcome(exit_code=0))
    return {
        "oracle_id": task.oracle.oracle_id,
        "task_id": task.task_id,
        "variant": str(variant.value),
        "verdict": str(verdict),
        "reason_code": reason,
        **counts.to_mapping(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m benchmarks.replay",
        description=(
            "Run one corpus task against the REFERENCE executor and report the oracle "
            "verdict. Not a model measurement."
        ),
    )
    parser.add_argument("task_id", help="a corpus task id, e.g. ai11-v1-can-dbc-decode")
    parser.add_argument(
        "--variant",
        choices=[v.value for v in ReferenceVariant],
        default=ReferenceVariant.KNOWN_GOOD.value,
        help="which declared control submission to run",
    )
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="the corpus root")
    args = parser.parse_args(argv)

    try:
        record = build_record(args.task_id, ReferenceVariant(args.variant), Path(args.corpus))
    except BenchmarkError as exc:
        # A refusal is reported as a refusal, with its reason code, and the exit status
        # is non-zero so a caller cannot mistake it for a verdict.
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(ORACLE_RECORD_SENTINEL + json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
