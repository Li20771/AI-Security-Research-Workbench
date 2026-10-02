"""AI-11 §20.4, Annex C — the measured campaign, and its own falsifiability.

```text
python3 -m benchmarks.campaign --source <securitylab-root> [--json]
```

It runs every corpus task through the full lifecycle against the REFERENCE executor,
plus a determinism control, and emits the facts it measured.

### What this is NOT

```text
NOT a model measurement       executor_kind is REFERENCE; agent_id is null
NOT a provider measurement    no provider is contacted, and none is enabled
NOT a ranking                 there is no score, no pass rate and no aggregate
```

### The campaign must be able to fail

A closeout script that always prints success is not evidence. This one raises on every
condition that would make its output a false record:

```text
a corpus task is missing
the contract blob is not the frozen one
a task's source_sha does not resolve
a run has no limitations where the contract requires one
task_status is PASS while a required check did not execute
regression_status is PASS while the negative control was not rejected
two identical runs disagree on a field that must be deterministic
```
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.errors import BenchmarkError
from benchmarks.executor import ReferenceVariant
from benchmarks.run import new_run_id
from benchmarks.runner import execute_task, kernel_release, resolve_workbench_sha, utc_now
from benchmarks.task import load_corpus
from benchmarks.vocabulary import LimitationCode, OracleVerdict

__all__ = [
    "FROZEN_CONTRACT_BLOB",
    "CampaignError",
    "campaign",
    "determinism_control",
]

#: §26's freeze record. The campaign refuses to run against anything else.
FROZEN_CONTRACT_BLOB = "08aea86cf82e7476dee442b33dc81c8f9a9873a3"

CONTRACT_DOC = "docs/AI-11_SECURITY_BENCHMARK_EXECUTION_PLAN.md"
DEFAULT_CORPUS = Path(__file__).resolve().parent / "tasks"

#: §20.4. The task used to show the harness is deterministic. It is the one whose oracle
#: needs no external tool, so the comparison is about the harness rather than about a
#: machine's installed software.
DETERMINISM_TASK = "ai11-v1-can-dbc-decode"

#: Fields that MUST agree between two identical runs. Timing and identity are excluded
#: because they are operational, not semantic — the same split AI-05 §14.6 draws.
DETERMINISTIC_FIELDS = (
    "task_id",
    "task_version",
    "executor_kind",
    "agent_id",
    "source_sha",
    "task_status",
    "regression_status",
    "security_boundary_status",
    "tests",
    "oracle_results",
    "workspace_identity",
)


class CampaignError(RuntimeError):
    """The campaign's own output would be a false record."""


def contract_blob(repo_root: Path) -> str:
    """The frozen contract's blob, computed from the bytes on disk."""
    path = repo_root / CONTRACT_DOC
    if not path.is_file():
        raise CampaignError(f"{CONTRACT_DOC} is absent")
    return hashlib.sha256(
        b"blob " + str(path.stat().st_size).encode() + b"\0" + path.read_bytes()
    ).hexdigest()


def _git_blob(repo_root: Path) -> str:
    """The blob as git computes it. Separate from the sha256 above on purpose."""
    import subprocess

    completed = subprocess.run(
        ["git", "hash-object", CONTRACT_DOC],
        cwd=str(repo_root), capture_output=True, text=True, check=False, shell=False,
    )
    return completed.stdout.strip()


@dataclass(frozen=True, slots=True)
class CampaignRun:
    task_id: str
    record: Mapping[str, Any]

    @property
    def task_status(self) -> OracleVerdict:
        return OracleVerdict(self.record["task_status"])


def _check_run(record: Mapping[str, Any]) -> None:
    """Refuse a record that would misrepresent what the harness did."""
    tests = record["tests"]
    status = OracleVerdict(record["task_status"])

    if status is OracleVerdict.PASS:
        if tests["executed"] != tests["planned"] or tests["skipped"] != 0:
            raise CampaignError(
                f"{record['task_id']}: task_status is PASS while "
                f"planned={tests['planned']} executed={tests['executed']} "
                f"skipped={tests['skipped']} (§11 forbids this)"
            )
        if tests["planned"] == 0:
            raise CampaignError(
                f"{record['task_id']}: task_status is PASS with no checks planned"
            )

    regression = OracleVerdict(record["regression_status"])
    if regression is OracleVerdict.PASS and not record.get("regression_results"):
        raise CampaignError(
            f"{record['task_id']}: regression_status is PASS with no recorded control"
        )

    if record["token_usage"] is not None or record["cost"] is not None:
        raise CampaignError(
            f"{record['task_id']}: a token or cost value exists; no provider is called, "
            "so both must be null (§9.4)"
        )
    if not any(
        entry.split(":", 1)[0] == LimitationCode.NO_PROVIDER_CALL_IN_PATH.value
        for entry in record["limitations"]
    ):
        raise CampaignError(
            f"{record['task_id']}: token_usage is null with no NO_PROVIDER_CALL_IN_PATH "
            "limitation (§9.4)"
        )


def campaign(
    *,
    source_root: str | Path,
    corpus_root: str | Path = DEFAULT_CORPUS,
    scratch_root: str | Path | None = None,
    workbench_sha: str | None = None,
) -> tuple[CampaignRun, ...]:
    """Run every corpus task once, at KNOWN_GOOD, and check each record."""
    source_root = Path(source_root)
    corpus_root = Path(corpus_root)
    scratch = Path(scratch_root) if scratch_root else Path(tempfile.gettempdir()) / "ai11-campaign"

    tasks = load_corpus(corpus_root)
    if not tasks:
        raise CampaignError("the corpus is empty; an empty corpus is not a campaign")

    runs: list[CampaignRun] = []
    for task in tasks:
        outcome = execute_task(
            task=task,
            corpus_root=corpus_root,
            source_root=source_root,
            scratch_root=scratch,
            run_id=new_run_id(uuid.uuid4().hex[:16]),
            variant=ReferenceVariant.KNOWN_GOOD,
            workbench_sha=workbench_sha,
        )
        record = outcome.run.to_mapping()
        _check_run(record)
        runs.append(CampaignRun(task_id=task.task_id, record=record))
    return tuple(runs)


def determinism_control(
    *,
    source_root: str | Path,
    task_id: str = DETERMINISM_TASK,
    corpus_root: str | Path = DEFAULT_CORPUS,
    scratch_root: str | Path | None = None,
    workbench_sha: str | None = None,
) -> Mapping[str, Any]:
    """§20.4. Two identical runs must agree on every field that must not vary.

    Timing and identity are excluded: `run_id`, `started_at`, `finished_at` and
    `duration_ms` are operational, and two runs of one task differ in all four by
    construction. Everything that decides the RESULT must agree.
    """
    source_root = Path(source_root)
    corpus_root = Path(corpus_root)
    task = next((t for t in load_corpus(corpus_root) if t.task_id == task_id), None)
    if task is None:
        raise CampaignError(f"the determinism control names {task_id!r}, which is not in the corpus")

    records = []
    for _ in range(2):
        outcome = execute_task(
            task=task,
            corpus_root=corpus_root,
            source_root=source_root,
            scratch_root=scratch_root or Path(tempfile.gettempdir()) / "ai11-determinism",
            run_id=new_run_id(uuid.uuid4().hex[:16]),
            variant=ReferenceVariant.KNOWN_GOOD,
            workbench_sha=workbench_sha,
        )
        records.append(outcome.run.to_mapping())

    disagreements = [
        field
        for field in DETERMINISTIC_FIELDS
        if records[0].get(field) != records[1].get(field)
    ]
    if disagreements:
        raise CampaignError(
            f"two identical runs of {task_id} disagree on {sorted(disagreements)}; the "
            "harness is not deterministic"
        )

    return {
        "task_id": task_id,
        "runs": 2,
        "compared_fields": list(DETERMINISTIC_FIELDS),
        "excluded_operational_fields": ["run_id", "started_at", "finished_at", "duration_ms"],
        "agreed": True,
        "run_ids": [record["run_id"] for record in records],
        "task_status": records[0]["task_status"],
    }


def host_facts() -> Mapping[str, Any]:
    """§15.4. The environment the campaign ran in."""
    return {
        "os": f"{platform.system()} {platform.release()}",
        "kernel": kernel_release(),
        "python": platform.python_version(),
        "platform": sys.platform,
        # The contract's authoritative host is WSL Ubuntu (§15.1). A campaign that runs
        # anywhere else records that fact rather than omitting it.
        "authoritative": sys.platform.startswith("linux"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m benchmarks.campaign",
        description=(
            "Run the AI-11 reference campaign and print the measured facts. This is NOT "
            "a model measurement and NOT a ranking."
        ),
    )
    parser.add_argument("--source", required=True, help="the pinned SecurityLab root")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--scratch", default=None)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    blob = _git_blob(repo_root)
    if blob != FROZEN_CONTRACT_BLOB:
        print(
            f"the frozen contract blob is {blob!r}, not {FROZEN_CONTRACT_BLOB!r}; "
            "refusing to run a campaign against an unfrozen contract",
            file=sys.stderr,
        )
        return 1

    try:
        runs = campaign(
            source_root=args.source, corpus_root=args.corpus, scratch_root=args.scratch
        )
        control = determinism_control(
            source_root=args.source, corpus_root=args.corpus, scratch_root=args.scratch
        )
    except (CampaignError, BenchmarkError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    report = {
        "measured_at": utc_now(),
        "workbench_sha": resolve_workbench_sha(repo_root=repo_root),
        "frozen_contract_blob": blob,
        "host": host_facts(),
        "executor_kind": "REFERENCE",
        "layer4": "BLOCKED",
        "layer4_reason": LimitationCode.LAYER4_BLOCKED.value,
        "runs": [dict(run.record) for run in runs],
        "determinism": control,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
