"""AI-13-B — T17, T23, T24: every DECLARED bound must have something that reaches it.

§12 declares six limits and refuses a workflow that omits any of them:

```text
maximum workflow runtime          maximum attempts per step
maximum step runtime              maximum total attempts for the run
maximum checkpoint count or       maximum artifact bytes referenced by a run
  total checkpoint bytes per run
```

```text
FROZEN: these are DECLARED, not defaulted. A workflow that declares no limit is refused
        at validation; "no limit" and "a limit nobody wrote down" are the same thing at
        run time, and only one of them is honest.
FROZEN: reaching any limit is a TERMINAL state with its own name (`RESOURCE_EXHAUSTED`),
        and never a silent stop.
```

### The property these tests exist for

A declared bound that NOTHING can reach satisfies every test that only checks a
definition is REFUSED for omitting it. Validation would pass, the counters would sit at
zero, and "maximum artifact bytes" would be a number in a tracked file that no run ever
touched — which is what the second clause above calls a silent stop arriving by a
different route.

So each test here drives a counter to its bound and requires the RUN to end, by name.
The last test in the module states the property directly rather than one bound at a time.
"""

from __future__ import annotations

import pytest

from workflows.definition import WorkflowDefinition
from workflows.engine import (
    advance,
    checkpoint_for,
    record_checkpoint,
    resume_run,
    start_run,
)
from workflows.policy import check_attempt_may_begin
from workflows.vocabulary import StepState, WorkflowState

from tests.workflows.conftest import (
    FAR,
    T0,
    T1,
    T2,
    AlwaysFailsExecutor,
    RecordingExecutor,
    limits,
    make_definition,
)

pytestmark = pytest.mark.layer2

#: Far enough out that only the bound under test can stop a run.
NO_DEADLINE_PRESSURE = "2030-01-01T00:00:00Z"


def _started(definition: WorkflowDefinition, **kwargs):  # noqa: ANN202
    return start_run(definition=definition, workspace_identity="ws-1", now=T0, **kwargs)


# ---------------------------------------------------------------------------
# T17 — the checkpoint bounds, which nothing reached before
# ---------------------------------------------------------------------------


def test_T17_a_reached_checkpoint_count_bound_ends_the_run() -> None:
    """§12. The count is a counter on the RECORD, so writing snapshots spends it."""
    definition = make_definition(limits=limits(max_checkpoints=1))
    run = _started(definition)
    run = advance(definition=definition, run=run, executor=RecordingExecutor(), now=T1)
    assert run.state is WorkflowState.RUNNING

    snapshot = checkpoint_for(definition=definition, run=run, now=T1)
    run = record_checkpoint(run=run, checkpoint=snapshot, now=T1)
    assert run.consumed_checkpoints == 1, "writing a checkpoint did not spend the budget"

    after = advance(definition=definition, run=run, executor=RecordingExecutor(), now=T2)
    assert after.state is WorkflowState.RESOURCE_EXHAUSTED
    assert after.reached_bound == "CHECKPOINT_COUNT_BOUND_REACHED"


def test_T17b_a_reached_checkpoint_byte_bound_ends_the_run() -> None:
    """§12's other half: "count OR total checkpoint bytes". Bytes accumulate on the
    record, so a run can exceed the total without any single checkpoint being too big."""
    definition = make_definition(
        limits=limits(max_checkpoints=100, max_checkpoint_bytes=1200)
    )
    run = _started(definition)
    snapshot = checkpoint_for(definition=definition, run=run, now=T1)
    assert run.consumed_checkpoint_bytes == 0

    refusal = None
    for _ in range(200):
        decision = check_attempt_may_begin(definition, run, "s1", T1)
        if not decision.allowed:
            refusal = decision
            break
        run = record_checkpoint(run=run, checkpoint=snapshot, now=T1)

    assert refusal is not None, "the byte bound was never reached, so it bounds nothing"
    assert refusal.reason_code == "CHECKPOINT_BYTES_BOUND_REACHED"
    assert refusal.terminal_state is WorkflowState.RESOURCE_EXHAUSTED


def test_T24c_discarding_checkpoints_does_not_restore_the_checkpoint_budget() -> None:
    """§15.1, for the checkpoint bound specifically.

    Two snapshots are written and then not kept — no reference survives. The record is
    unchanged, so the budget is still spent. A bound read from "the checkpoints I still
    have" would read zero here and let the run write forever.
    """
    definition = make_definition(limits=limits(max_checkpoints=2))
    run = _started(definition)

    for _ in range(2):
        snapshot = checkpoint_for(definition=definition, run=run, now=T1)
        run = record_checkpoint(run=run, checkpoint=snapshot, now=T1)
    del snapshot

    assert run.consumed_checkpoints == 2
    after = advance(definition=definition, run=run, executor=RecordingExecutor(), now=T2)
    assert after.state is WorkflowState.RESOURCE_EXHAUSTED
    assert after.reached_bound == "CHECKPOINT_COUNT_BOUND_REACHED"


# ---------------------------------------------------------------------------
# T17 — the artifact bound, which nothing checked before
# ---------------------------------------------------------------------------


def test_T17c_a_reached_artifact_bound_ends_the_run() -> None:
    """§12. Bytes an attempt references are knowable only once it has run, so this bound
    is met after the attempt — and is still TERMINAL and NAMED rather than a silent stop."""
    definition = make_definition(limits=limits(max_artifact_bytes=1000))
    executor = RecordingExecutor(artifact_bytes=1001)
    run = advance(definition=definition, run=_started(definition), executor=executor, now=T1)

    assert run.state is WorkflowState.RESOURCE_EXHAUSTED
    assert run.reached_bound == "ARTIFACT_BOUND_REACHED"
    assert run.consumed_artifact_bytes == 1001
    assert len(run.attempts_for("s1")) == 1, "the attempt that reached the bound was dropped"


def test_T17d_an_attempt_under_the_artifact_bound_is_recorded_and_continues() -> None:
    """The control: the same path accepts an attempt that stays inside the bound."""
    definition = make_definition(limits=limits(max_artifact_bytes=1000))
    executor = RecordingExecutor(artifact_bytes=1000)
    run = advance(definition=definition, run=_started(definition), executor=executor, now=T1)

    assert run.state is WorkflowState.RUNNING
    assert run.reached_bound is None
    assert run.consumed_artifact_bytes == 1000


def test_T24d_the_artifact_bound_is_enforced_from_the_record_across_a_resume() -> None:
    """§8.3, §15.1. The spend is on the record, so a resume inherits it."""
    definition = make_definition(limits=limits(max_artifact_bytes=1500))
    run = _started(definition)
    run = advance(
        definition=definition,
        run=run,
        executor=RecordingExecutor(artifact_bytes=1000),
        now=T1,
    )
    assert run.consumed_artifact_bytes == 1000

    snapshot = checkpoint_for(definition=definition, run=run, now=T1)
    resumed = resume_run(
        definition=definition,
        run=run,
        checkpoint=snapshot,
        workspace_identity="ws-1",
        executor=RecordingExecutor(artifact_bytes=1000),
        now=T2,
    )

    assert resumed.state is WorkflowState.RESOURCE_EXHAUSTED, (
        "the resumed run was handed a fresh artifact budget"
    )
    assert resumed.consumed_artifact_bytes == 2000
    assert resumed.reached_bound == "ARTIFACT_BOUND_REACHED"


# ---------------------------------------------------------------------------
# T17, T23 — the STEP runtime bound
# ---------------------------------------------------------------------------


def test_T17e_a_reached_step_deadline_ends_the_run() -> None:
    """§11.1. The step's declared runtime is an absolute instant, and it governs."""
    definition = make_definition(
        limits=limits(step_seconds=30, attempts_per_step=5, attempts_total=10),
        retry_policy={
            "policy_id": "p",
            "applies_to": ["RETRYABLE_FAILURE"],
            "max_attempts": 5,
            "deadline": NO_DEADLINE_PRESSURE,
        },
    )
    run = _started(definition)
    run = advance(definition=definition, run=run, executor=AlwaysFailsExecutor(), now=T0)
    assert run.state is WorkflowState.RUNNING
    assert run.step_deadline == "2026-10-03T10:00:30Z"

    after = advance(definition=definition, run=run, executor=AlwaysFailsExecutor(), now="2026-10-03T10:00:30Z")
    assert after.state is WorkflowState.TIMED_OUT, (
        "the step's declared runtime was reached and the run continued"
    )
    assert after.reached_bound == "STEP_DEADLINE_REACHED"


def test_T23e_the_step_deadline_is_anchored_once_and_survives_a_resume() -> None:
    """§8.3. A per-attempt `now + step_seconds` would hand the resume a whole new step
    budget — so a step bounded at one minute could be resumed into an unbounded one."""
    definition = make_definition(
        limits=limits(step_seconds=60, attempts_per_step=5, attempts_total=10),
        retry_policy={
            "policy_id": "p",
            "applies_to": ["RETRYABLE_FAILURE"],
            "max_attempts": 5,
            "deadline": NO_DEADLINE_PRESSURE,
        },
    )
    run = _started(definition)
    run = advance(definition=definition, run=run, executor=AlwaysFailsExecutor(), now=T1)
    anchored = run.step_deadline
    assert anchored == "2026-10-03T10:01:10Z"

    snapshot = checkpoint_for(definition=definition, run=run, now=T1)
    resumed = resume_run(
        definition=definition,
        run=run,
        checkpoint=snapshot,
        workspace_identity="ws-1",
        executor=AlwaysFailsExecutor(),
        now="2026-10-03T10:00:40Z",
    )

    assert resumed.step_deadline == anchored, (
        "the resumed run was handed a new step deadline instead of inheriting the "
        "remaining step budget (§8.3)"
    )

    after = advance(
        definition=definition,
        run=resumed,
        executor=AlwaysFailsExecutor(),
        now="2026-10-03T10:01:10Z",
    )
    assert after.state is WorkflowState.TIMED_OUT


# ---------------------------------------------------------------------------
# §15.2 — the record names the bound, and the decision the attempt rested on
# ---------------------------------------------------------------------------


def test_T17f_a_run_that_reached_no_bound_names_none() -> None:
    """§15.2. `reached_bound` is a fact, not a summary: a run stopped by an unclassified
    failure must not be attributed to a limit it never touched."""
    from workflows.vocabulary import FailureClass

    definition = make_definition()
    run = advance(
        definition=definition,
        run=_started(definition),
        executor=AlwaysFailsExecutor(failure=None),
        now=T1,
    )
    assert run.state is WorkflowState.FAILED
    assert run.reached_bound is None


def test_the_decision_a_failed_attempt_rested_on_is_recorded_as_a_reference() -> None:
    """§15.2. "the reason code and the decision id it rests on" — as a REFERENCE."""
    definition = make_definition()
    run = advance(
        definition=definition,
        run=_started(definition),
        executor=RecordingExecutor(outcomes=[False], decision_id="dec-1"),
        now=T1,
    )
    attempt = run.attempts_for("s1")[-1]
    assert attempt.decision_id == "dec-1"
    assert attempt.reason_code == "TRANSIENT"


def test_the_checkpoint_REFUSES_the_decision_id_the_record_carries() -> None:
    """§15.1, mechanically. The ledger is required to name the decision (§15.2); the
    disposable snapshot a resumed attempt reads is forbidden to (§7.2). One name, two
    records, opposite rules — which is the separation doing work rather than tidying."""
    from workflows.checkpoint import Checkpoint
    from workflows.errors import InvalidCheckpoint

    with pytest.raises(InvalidCheckpoint) as raised:
        Checkpoint.from_mapping(
            {
                "workflow_id": "w", "revision": "v1", "definition_digest": "d",
                "run_id": "r", "step_id": "s", "attempt_no": 1,
                "completed_steps": [], "created_at": T0,
                "decision_id": "dec-1", "checkpoint_digest": "x",
            }
        )
    assert raised.value.reason_code == "CHECKPOINT_CARRIES_FORBIDDEN_STATE"


def test_an_attempt_that_rested_on_nothing_carries_no_decision() -> None:
    """The control. A record that invented a decision id would be asserting an
    authorization nobody gave, which is the defect §13.3 exists to refuse."""
    definition = make_definition()
    run = advance(
        definition=definition, run=_started(definition), executor=RecordingExecutor(), now=T1
    )
    assert run.attempts_for("s1")[-1].decision_id is None


# ---------------------------------------------------------------------------
# The property, once, over every bound §12 declares
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "declared",
    [
        "workflow_deadline",
        "step_seconds",
        "attempts_per_step",
        "attempts_total",
        "max_checkpoints",
        "max_checkpoint_bytes",
        "max_artifact_bytes",
    ],
)
def test_every_declared_limit_is_named_where_it_is_enforced(declared: str) -> None:
    """§12. No bound is inert.

    Each of §12's limits must appear somewhere that can REACH it: the two absolute
    deadlines and the two attempt bounds in the bound check, the checkpoint bounds in the
    bound check and the write refusal, and the artifact bound in the bound check and the
    post-attempt spend. A limit that appears only in validation is a number nobody
    enforces, and this test is what stops one being added back.
    """
    import pathlib
    import re

    import workflows.engine as engine_module
    import workflows.policy as policy_module

    # Read from the modules that were IMPORTED, not from paths assembled out of the
    # working directory, so this holds for the code actually in use.
    policy_source = pathlib.Path(policy_module.__file__).read_text(encoding="utf-8")
    engine_source = pathlib.Path(engine_module.__file__).read_text(encoding="utf-8")

    # The two attempt bounds are consumed through EFFECTIVE bound arithmetic rather than
    # by name, so they are checked against the attribute they are read from.
    attribute = {
        "workflow_deadline": "run.workflow_deadline",
        "step_seconds": "step_deadline_from",
        "attempts_per_step": "definition.limits.attempts_per_step",
        "attempts_total": "definition.limits.attempts_total",
        "max_checkpoints": "definition.limits.max_checkpoints",
        "max_checkpoint_bytes": "definition.limits.max_checkpoint_bytes",
        "max_artifact_bytes": "definition.limits.max_artifact_bytes",
    }[declared]

    assert attribute in policy_source or attribute in engine_source, (
        f"{declared} is declared and validated but nothing enforces it, which is what "
        f"§12 refuses when it says a limit nobody wrote down and no limit are the same "
        f"thing at run time"
    )
    assert re.search(rf"\b{declared}\b", policy_source + engine_source), declared
