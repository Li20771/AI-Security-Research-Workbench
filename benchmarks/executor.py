"""AI-11 §20.4 — the reference executor. **Not a model.**

```text
FROZEN: `reference` is a DECLARED DETERMINISTIC EXECUTOR. It is NOT A MODEL. It
        performs no inference, reaches no network, reads no credential.
FROZEN: a run whose executor_kind is REFERENCE MUST NOT be presented as a model
        measurement, MUST NOT be compared to a model, and MUST NOT enter any aggregate
        over models.
```

It exists for three jobs, and for nothing else:

```text
1  prove each task in the corpus is solvable
2  exercise each oracle's discrimination control end to end
3  show the harness is deterministic — two runs of one task agree
```

It does this by producing a submission from the task's own tracked control material.
That material is written by the task author and reviewed with the task; it is the
declared correct answer for `KNOWN_GOOD` and a declared incorrect one for `KNOWN_BAD`.

### Why this is not circular

The known-good submission is an *independent* answer to the task, held outside the
agent-visible tree, and the oracle compares the two. What the pair proves is exactly
what §20.4 claims for it: that a correct answer is reachable and that the oracle says
so, and that an incorrect answer is reachable and the oracle says *that*. Neither half
is a claim about any model, and neither is a claim about how hard the task is.

The word for what this is NOT is `agents/body.py`'s: `OfflineBody is NOT A MODEL`. The
same sentence, applied one layer up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from benchmarks.errors import CorpusError
from benchmarks.task import TaskDefinition

__all__ = [
    "CONTROL_DIR_NAME",
    "KNOWN_GOOD_FILE",
    "KNOWN_BAD_FILE",
    "TRUTH_FILE",
    "ReferenceExecutor",
    "ReferenceVariant",
    "Submission",
]

CONTROL_DIR_NAME = "control"
TRUTH_FILE = "truth.json"


class ReferenceVariant(StrEnum):
    """Which declared answer the reference executor produces.

    `KNOWN_BAD` is not a failure mode of the harness. It is the second half of §7.4's
    discrimination control, and running it is how the corpus proves its oracles can say
    no.

    The member VALUE is the variant name, and the file name is derived from it. The
    other order — value is the file name — leaks a storage detail into a CLI flag and
    into every record that carries the variant.
    """

    KNOWN_GOOD = "known_good"
    KNOWN_BAD = "known_bad"

    @property
    def file_name(self) -> str:
        return f"{self.value}.json"


KNOWN_GOOD_FILE = ReferenceVariant.KNOWN_GOOD.file_name
KNOWN_BAD_FILE = ReferenceVariant.KNOWN_BAD.file_name


@dataclass(frozen=True, slots=True)
class Submission:
    """What an executor produced, plus the provenance of how."""

    executor_kind: str
    variant: str
    payload: Mapping[str, Any]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "executor_kind": self.executor_kind,
            "variant": self.variant,
            "payload": dict(self.payload),
        }


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise CorpusError(f"{path} is missing")
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"{path} is not valid JSON: {type(exc).__name__}") from exc
    if not isinstance(decoded, Mapping):
        raise CorpusError(f"{path} must decode to an object")
    return decoded


def control_dir(task: TaskDefinition, corpus_root: str | Path) -> Path:
    """The task's control directory, derived from the task id.

    Derived rather than declared: the corpus layout already fixes
    `root/<task_id>/control/`, and a second declaration of the same path in the YAML is
    a second place for it to be wrong.
    """
    return Path(corpus_root) / task.task_id / CONTROL_DIR_NAME


class ReferenceExecutor:
    """The deterministic, non-model executor (§20.4).

    It reads the task's tracked control material and returns it. It does not compute an
    answer, does not call anything, and does not vary between runs — which is what makes
    it usable as the determinism control.
    """

    #: §6.1, §20.4. The value written into `executor_kind`, and the reason `agent_id`
    #: is `None` on these runs: `reference` is not an AI-08 AgentId.
    executor_kind = "REFERENCE"
    agent_id: None = None

    def __init__(self, task: TaskDefinition, corpus_root: str | Path) -> None:
        self._task = task
        self._control = control_dir(task, corpus_root)

    @property
    def control(self) -> Path:
        return self._control

    def produce(self, variant: ReferenceVariant = ReferenceVariant.KNOWN_GOOD) -> Submission:
        """Produce the declared answer for `variant`."""
        path = self._control / variant.file_name
        return Submission(
            executor_kind=self.executor_kind,
            variant=variant.value,
            payload=_read_json(path),
        )

    def truth(self) -> Mapping[str, Any]:
        """The tracked ground truth the oracle judges against.

        Held by the harness, never placed in the agent-visible tree (§7.2). A
        submission is judged against THIS, and the executor never sees it: an executor
        that could read the truth could produce a submission that matches it without
        solving anything.
        """
        return _read_json(self._control / TRUTH_FILE)

    def discrimination_control(self) -> tuple[Submission, Submission]:
        """§7.4. The known-good and known-bad pair, ready to be judged."""
        return self.produce(ReferenceVariant.KNOWN_GOOD), self.produce(ReferenceVariant.KNOWN_BAD)
