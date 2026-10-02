"""AI-11 §7.3, §15, §20.4 — the reproduction entry point.

```text
python3 -m benchmarks.replay <task_id> --source <securitylab-root> [--variant ...]
```

Every task's `oracle.reproduce_command` names this module, so the command recorded in
the corpus is the command a person actually runs.

### It runs the WHOLE lifecycle

```text
source_sha check -> derive_source_tree -> prepare_workspace -> executor -> oracle
```

An earlier revision stopped at the executor and read the control fixtures directly. That
made the workspace layer a component with no caller: `prepare_workspace()` could have
been deleted and nothing would have noticed. Now a run that does not derive a workspace
does not happen, and `--source` is what makes the derivation possible.

`--source` is REQUIRED. Without a source repository there is no pinned revision to
derive from, and the honest answer is a `BLOCKED` record — not a shortcut that reads the
answer from the corpus.

### It is the REFERENCE path, and it says so

The run it produces is `executor_kind = REFERENCE` with `agent_id = null`. It measures
no model. Its purpose is the one §20.4 states: prove the task is solvable, prove the
oracle discriminates, and show the harness is deterministic.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from benchmarks.errors import BenchmarkError
from benchmarks.executor import ReferenceVariant
from benchmarks.oracle import ORACLE_RECORD_SENTINEL
from benchmarks.runner import execute_task
from benchmarks.task import load_task

__all__ = ["DEFAULT_CORPUS", "main", "run_task_record"]

#: The tracked corpus. Relative to this file, so the entry point works from any cwd.
DEFAULT_CORPUS = Path(__file__).resolve().parent / "tasks"


def run_task_record(
    task_id: str,
    *,
    source_root: str | Path,
    corpus_root: Path,
    variant: ReferenceVariant,
    scratch_root: str | Path | None = None,
    run_id: str | None = None,
) -> dict:
    """Run one reference task through the lifecycle and return its oracle record."""
    task = load_task(corpus_root / task_id / "task.yaml")
    scratch = Path(scratch_root) if scratch_root is not None else Path(tempfile.gettempdir()) / "ai11-bench"

    outcome = execute_task(
        task=task,
        corpus_root=corpus_root,
        source_root=source_root,
        scratch_root=scratch,
        run_id=run_id,
        variant=variant,
    )

    run = outcome.run
    first = run.oracle_results[0] if run.oracle_results else {}
    record = {
        "task_id": task.task_id,
        "variant": variant.value,
        "oracle_id": task.oracle.oracle_id,
        "verdict": str(run.task_status),
        "reason_code": first.get("reason_code", ""),
        "executor_kind": str(run.executor_kind),
        "agent_id": run.agent_id,
        "manifest_digest": run.workspace_identity.get("manifest_digest", ""),
        "limitations": list(run.limitations),
        **run.tests.to_mapping(),
    }
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m benchmarks.replay",
        description=(
            "Run one corpus task through the full benchmark lifecycle against the "
            "REFERENCE executor and report the oracle verdict. Not a model measurement."
        ),
    )
    parser.add_argument("task_id", help="a corpus task id, e.g. ai11-v1-can-dbc-decode")
    parser.add_argument(
        "--source",
        required=True,
        help=(
            "path to the pinned source repository (SecurityLab). Required: without it "
            "there is no revision to derive a workspace from, and the run is BLOCKED"
        ),
    )
    parser.add_argument(
        "--variant",
        choices=[v.value for v in ReferenceVariant],
        default=ReferenceVariant.KNOWN_GOOD.value,
        help="which declared control submission to run",
    )
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="the corpus root")
    parser.add_argument("--scratch", default=None, help="scratch root for the derivation")
    args = parser.parse_args(argv)

    try:
        record = run_task_record(
            args.task_id,
            source_root=args.source,
            corpus_root=Path(args.corpus),
            variant=ReferenceVariant(args.variant),
            scratch_root=args.scratch,
        )
    except BenchmarkError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(ORACLE_RECORD_SENTINEL + json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
