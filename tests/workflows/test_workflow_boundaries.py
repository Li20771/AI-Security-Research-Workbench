"""AI-13-B — T19, T20, T21: what the workflow package must not reach.

These are the tests the contract assigns to AI-13-B for the boundaries the phase
inherits rather than invents:

```text
T19  AI-13 writes no AI-05 record and registers no producer
T20  AI-13 reads no AI-12 policy and executes no fallback
T21  AI-13 does not reopen a closed ReviewCase; a resumed run is not a review
     transition (AI-10 §5.3)
```

### Why these read IMPORTS and not words

A scan for `evidence` or `review` in the source finds them here and there already —
`workflows.checkpoint` refuses a field named `evidence_id`, and `workflows.definition`
says a definition is "reviewed and versioned in Git". Both are the boundary being
described, not crossed. A word search would either fail on the refusals or have to be
narrowed until it proved nothing.

So each boundary is asserted where crossing it would actually show: an IMPORT. The
workflow package reaches the execution seam through a Protocol (`StepExecutor`) rather
than an import, so it needs no foreign package at all — which makes the absence of every
root below a property of the design rather than a coincidence worth re-checking by hand.
"""

from __future__ import annotations

import pytest

from workflows.vocabulary import TERMINAL_STATES, FailureClass, WorkflowState

from tests.workflows.conftest import imported_modules, module_roots, workflow_sources

pytestmark = pytest.mark.layer1


def _imports() -> dict[str, set[str]]:
    return {str(path): imported_modules(path) for path in workflow_sources()}


def test_the_import_collector_is_not_vacuous() -> None:
    """The control all three boundaries below depend on.

    A collector that returned the empty set — a broken walker, a path that matched no
    files — would let T19, T20 and T21 pass while proving nothing. This pins it to an
    import that must exist: the engine builds on the definition.
    """
    sources = workflow_sources()
    assert sources, "no workflow modules were found to check"

    engine = imported_modules(next(path for path in sources if path.name == "engine.py"))
    assert "workflows.definition" in engine, (
        "the import collector is not seeing real imports, so every absence it reports "
        "below is worthless"
    )


# ---------------------------------------------------------------------------
# T19 — no AI-05 record, no producer
# ---------------------------------------------------------------------------


def test_T19_the_workflow_package_reaches_no_evidence_module() -> None:
    """§7.3, §13.5, §16. AI-13 writes no EvidenceRecord and registers no producer.

    The roots are refused outright rather than an allowlist being checked, because the
    workflow package imports NOTHING outside itself: there is no permitted evidence
    module for a narrower rule to permit.
    """
    offenders = {
        path: sorted(
            name for name in imports if module_roots({name}) & {"plugins", "evidence"}
        )
        for path, imports in _imports().items()
    }
    assert not {path: names for path, names in offenders.items() if names}, (
        f"a workflow module imports an evidence-side package; AI-13 registers no "
        f"producer and writes no record (§16): {offenders}"
    )


def test_T19b_a_checkpoint_is_not_shaped_like_an_evidence_record() -> None:
    """§7.3. Not written as one, and not RESHAPED into one.

    The structural half of the same rule: a checkpoint has no producer token and no
    evidence identity to be promoted under.
    """
    from workflows.checkpoint import Checkpoint

    fields = set(Checkpoint.__dataclass_fields__)
    assert not {name for name in fields if "evidence" in name or "producer" in name}


# ---------------------------------------------------------------------------
# T20 — no AI-12 policy, no fallback
# ---------------------------------------------------------------------------


def test_T20_the_workflow_package_reads_no_policy_module() -> None:
    """§10.4. AI-12 declares fallback and escalation as data and executes neither, and
    AI-13 MUST NOT become the executor AI-12 deliberately is not.

    `routing` carries both AI-07's router and AI-12's policy core. AI-13 submits nothing
    to either in v1 — an attempt reaches its routing through the execution seam — so the
    whole root is refused rather than one module of it.
    """
    offenders = {
        path: sorted(name for name in imports if module_roots({name}) & {"routing"})
        for path, imports in _imports().items()
    }
    assert not {path: names for path, names in offenders.items() if names}, (
        f"a workflow module reads routing/policy; AI-13 executes no AI-12 policy (§10.4): "
        f"{offenders}"
    )


def test_T20b_no_fallback_or_escalation_word_enters_the_vocabulary() -> None:
    """§14, §16. AI-08 T32 forbids this vocabulary for the same reason, and AI-13 is the
    phase it was deferred to — so it does not arrive here either."""
    forbidden = {"FALLBACK", "FALLBACKED", "ESCALATED", "ESCALATE", "RETRYING", "RETRIED"}
    assert not (forbidden & {member.value for member in FailureClass})
    assert not (forbidden & {member.value for member in WorkflowState})


# ---------------------------------------------------------------------------
# T21 — no reopened ReviewCase
# ---------------------------------------------------------------------------


def test_T21_the_workflow_package_reaches_no_review_module() -> None:
    """AI-10 §5.3, §13.6, §17. A workflow run is not a review case, and resuming a run
    must not be read as a transition of one."""
    offenders = {
        path: sorted(name for name in imports if module_roots({name}) & {"review"})
        for path, imports in _imports().items()
    }
    assert not {path: names for path, names in offenders.items() if names}, (
        f"a workflow module reaches AI-10's review package; a run is not a review case "
        f"(§13.6): {offenders}"
    )


def test_T21b_a_terminal_run_is_never_reopened() -> None:
    """The behavioural half: "resume of a closed case is not a transition".

    AI-13 has no word for reopening, so a terminal run has no state to be moved to. A
    resume is a RUN continuing, and the only states it can produce are the run states
    below — none of which names a review transition.
    """
    from tests.workflows.conftest import T0

    assert TERMINAL_STATES <= set(WorkflowState)
    assert not {state for state in WorkflowState if "REOPEN" in state.value or "REVIEW" in state.value}

    # A closed run does not move, whatever it is asked — including by a resume, which
    # §8.1 refuses on the strength of the same bindings a terminal run already failed.
    from workflows.definition import WorkflowDefinition
    from workflows.engine import advance, start_run

    from tests.workflows.conftest import RecordingExecutor, definition_body

    definition = WorkflowDefinition.from_mapping(definition_body())
    executor = RecordingExecutor()
    run = start_run(definition=definition, workspace_identity="ws-1", now=T0)
    run = advance(definition=definition, run=run, executor=executor, now=T0)
    run = advance(definition=definition, run=run, executor=executor, now=T0)
    assert run.state is WorkflowState.COMPLETED

    again = advance(
        definition=definition, run=run, executor=executor, now="2026-10-03T11:00:00Z"
    )
    assert again == run, "a terminal run was moved back into a running state"
    assert len(executor.calls) == 2
