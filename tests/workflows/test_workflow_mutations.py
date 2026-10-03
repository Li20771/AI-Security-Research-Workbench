"""AI-13 §21.3 — the mutation controls, as a MECHANISM rather than a procedure.

```text
FROZEN: each test MUST fail when the guard it names is REMOVED, not merely pass while
        the guard exists. The review of AI-12-B found three defects that a
        coverage-shaped suite had passed, and AI-13 does not repeat that: the controls
        below are the ones that must be shown to fail.
```

### Why this is code and not a table in a document

The repository's previous phases recorded mutation controls as a transcription: a
reviewer edited a guard by hand, ran the focused test, saw it fail, reverted, and wrote a
row into an evidence document. `docs/AI-12-B_EVIDENCE_2026-10-03.md` records what that
cost — "**two survived on an earlier run**", because a procedure run by hand has nothing
that fails when it is skipped.

§21.3 is the clause that refuses to repeat it, so the controls here are executable. Each
one copies `workflows/` to a scratch tree, applies ONE source mutation that removes the
guard it names, and runs the focused test in a SUBPROCESS against that copy. The test
passes only when the focused test genuinely fails.

The subprocess is what makes the copy load-bearing rather than decorative: the mutation
is applied to a file the real package never reads, and the only reason the focused test
sees it is that the copy is first on `PYTHONPATH`.

### The two controls that keep the harness honest

A harness that reported "the focused test failed" unconditionally would pass every
mutation below and prove nothing. `test_the_unmutated_copy_passes` requires the copy to
pass when nothing is planted, and `test_the_scratch_copy_shadows_the_real_package`
requires a mutation to actually reach the test that reads it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.layer2

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / "workflows"

#: Every focused test these controls share, so a control names the test that must fail
#: rather than a module that would fail for any reason.
CORE = "tests/workflows/test_workflow_core.py"
RESUME = "tests/workflows/test_workflow_resume.py"
RUN = "tests/workflows/test_workflow_run.py"
LIMITS = "tests/workflows/test_workflow_limits.py"


@dataclass(frozen=True, slots=True)
class Mutation:
    """One control: a guard, its removal, and the focused test that must notice."""

    control: str
    guard: str
    path: str
    old: str
    new: str
    focused: tuple[str, ...]


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        control="checkpoint digest preimage",
        guard="§7.4 excludes the record's own digest field from the preimage, and "
              "NOTHING else",
        path="workflows/canonical.py",
        old="    body = {key: value for key, value in fields.items() if key != digest_field}",
        new="    body = dict(fields)  # mutated: the digest field joins its own preimage",
        focused=(f"{CORE}::test_canonical_body_excludes_the_digest_field",),
    ),
    Mutation(
        control="persisted runtime budget",
        guard="§8.3 the workflow deadline is read from the record and compared against "
              "the CURRENT time, never re-derived from the run's own clock",
        path="workflows/policy.py",
        old="    remaining_workflow = seconds_remaining(run.workflow_deadline, now)",
        new="    remaining_workflow = seconds_remaining(\n"
            "        run.workflow_deadline, run.created_at\n"
            "    )  # mutated: the budget is measured from creation, so it never runs out",
        # BOTH halves, because the property has two mechanisms and the contract asks
        # for both. `T23` catches a deadline that was recomputed; `T23b` catches one
        # that was not consulted BEFORE the attempt, which the post-attempt overrun
        # check would otherwise mask — an attempt that should never have begun would
        # still end TIMED_OUT, and only the assertion that it did not RUN notices.
        focused=(
            f"{RESUME}::test_T23_the_workflow_deadline_is_not_recomputed_on_resume",
            f"{RESUME}::test_T23b_a_run_whose_deadline_has_passed_does_not_resume",
        ),
    ),
    Mutation(
        control="resumed retry budget",
        guard="§8.3, §15.1 the attempt lineage and counter are read from the RUN RECORD "
              "on resume, never rebuilt from the checkpoint",
        path="workflows/engine.py",
        old="    return advance(definition=definition, run=run, executor=executor, now=moment)",
        new="    # mutated: rebuild the run from what the checkpoint remembers -- nothing\n"
            "    run = run.advance(\n"
            "        consumed_total_attempts=0,\n"
            "        steps=tuple(\n"
            "            StepRecord(step_id=record.step_id, state=record.state)\n"
            "            for record in run.steps\n"
            "        ),\n"
            "    )\n"
            "    return advance(definition=definition, run=run, executor=executor, now=moment)",
        focused=(f"{RESUME}::test_T23c_the_attempt_counter_is_not_rebuilt_from_a_checkpoint",),
    ),
    Mutation(
        control="RunRecord / Checkpoint separation",
        guard="§15.1 a bound is computed from the definition and the run record, so the "
              "bounds module cannot read a checkpoint at all",
        path="workflows/policy.py",
        old="from workflows.definition import WorkflowDefinition, WorkflowStep",
        new="from workflows.checkpoint import Checkpoint  # mutated: bounds may read a "
            "checkpoint\nfrom workflows.definition import WorkflowDefinition, WorkflowStep",
        focused=(f"{RUN}::test_T24b_the_bounds_module_cannot_read_a_checkpoint",),
    ),
    Mutation(
        control="B/C ownership boundary",
        guard="§18 AI-13-B refuses a definition declaring an approval step, by name",
        path="workflows/definition.py",
        old="        if kind is StepKind.APPROVAL:",
        new="        if kind is StepKind.APPROVAL and False:  # mutated: B accepts it",
        focused=(f"{CORE}::test_T22_an_approval_step_is_refused_by_name",),
    ),
    Mutation(
        control="unclassified failure stops",
        guard="§9.1 an unclassified failure is assigned NO class, stops, and is never "
              "retried",
        path="workflows/engine.py",
        old="        failure_class=None if outcome.succeeded else outcome.failure_class,",
        new="        failure_class=None\n"
            "        if outcome.succeeded\n"
            "        else (outcome.failure_class or FailureClass.TERMINAL_FAILURE),"
            "  # mutated: an absence becomes a class",
        focused=(f"{RUN}::test_T14_an_unclassified_failure_stops_and_is_never_retried",),
    ),
    Mutation(
        control="effective bound precedence (attempts)",
        guard="§10.3.1 where more than one attempts bound applies, the NARROWER governs",
        path="workflows/policy.py",
        old="    return min(candidates)",
        new="    return max(candidates)  # mutated: the wider bound governs",
        focused=(
            f"{RUN}::test_T12_the_attempt_bound_stops_a_run_whose_policy_would_retry",
        ),
    ),
    Mutation(
        control="effective bound precedence (deadlines)",
        guard="§10.3.1, §12 the workflow deadline governs, and the narrower bound is the "
              "one that stops an attempt beginning",
        path="workflows/policy.py",
        old="    if remaining_workflow <= 0:",
        new="    if remaining_workflow <= 0 and False:  # mutated: a wider bound governs",
        focused=(f"{RUN}::test_T25_an_attempt_at_or_after_the_workflow_deadline_does_not_begin",),
    ),
    Mutation(
        control="deadline computed at run creation",
        guard="§8.3, §12 the definition declares a RUNTIME and the run record holds the "
              "ABSOLUTE, computed once when the run is created",
        path="workflows/engine.py",
        old="        workflow_deadline=plus_seconds(created, definition.limits.workflow_seconds),",
        new="        workflow_deadline=created,  # mutated: the declared runtime is dropped",
        focused=(
            f"{RESUME}::test_the_workflow_deadline_is_computed_at_creation_from_the_declared_runtime",
        ),
    ),
    Mutation(
        control="retry budget is run-wide, not refreshed",
        guard="§8.3 the retry time bound is absolute for the run and shared by every "
              "retry, so a resume does not grant a fresh one",
        path="workflows/engine.py",
        old="    return advance(definition=definition, run=run, executor=executor, now=moment)",
        new="    # mutated: the retry budget is granted fresh on resume\n"
            "    if definition.retry_policy is not None:\n"
            "        run = run.advance(\n"
            "            retry_deadline=plus_seconds(\n"
            "                moment, definition.retry_policy.retry_seconds\n"
            "            )\n"
            "        )\n"
            "    return advance(definition=definition, run=run, executor=executor, now=moment)",
        focused=(
            f"{RESUME}::test_resume_reads_the_persisted_deadlines_and_creates_no_new_ones",
        ),
    ),
    Mutation(
        control="effective timeout reaches the execution seam",
        guard="§11.1 the composed outer bound is HANDED to the execution rather than "
              "computed and dropped, and it composes with AI-06's inner timeout",
        path="workflows/engine.py",
        old="        timeout_seconds=timeout_seconds,",
        new="        timeout_seconds=step.timeout_seconds,  # mutated: outer bounds dropped",
        focused=(f"{LIMITS}::test_the_effective_timeout_is_handed_to_the_execution",),
    ),
    Mutation(
        control="recorded timing is the execution's",
        guard="§15.2 an attempt's started_at and ended_at are what the EXECUTION "
              "reported, never the instant the engine dispatched it",
        path="workflows/engine.py",
        old="        # The EXECUTION's own timing, recorded rather than assumed (§15.2).\n"
            "        started_at=outcome.started_at,\n"
            "        ended_at=outcome.ended_at,",
        new="        started_at=moment,  # mutated: the dispatch instant, twice\n"
            "        ended_at=moment,",
        focused=(
            f"{LIMITS}::test_the_recorded_timing_is_the_executions_not_the_dispatch_instant",
        ),
    ),
    Mutation(
        control="cancellation provenance is persisted",
        guard="§11.2 a cancelled run records WHO cancelled and WHY, as declared "
              "references on the run record",
        path="workflows/engine.py",
        old="        cancelled_by=cancelled_by,\n        cancelled_reason=reason,",
        new="        cancelled_by=None,  # mutated: who and why are dropped\n"
            "        cancelled_reason=None,",
        focused=(f"{RUN}::test_cancellation_records_who_and_why_as_references",),
    ),
)

#: Named so a failure reads as "the harness cannot see the copy", not as an unrelated
#: guard being wrong.
SHADOW_MUTATION = Mutation(
    control="the harness itself",
    guard="the scratch copy is what the focused test imports",
    path="workflows/vocabulary.py",
    old='    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"',
    new='    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"\n'
        '    UNKNOWN = "UNKNOWN"  # mutated: a tenth member',
    focused=(f"{RUN}::test_T14b_no_UNKNOWN_member_exists_in_the_vocabulary",),
)


def _scratch(tmp_path: Path) -> Path:
    """A copy of the workflow package, alone, under a directory of its own."""
    root = tmp_path / "scratch"
    shutil.copytree(
        WORKFLOWS, root / "workflows", ignore=shutil.ignore_patterns("__pycache__")
    )
    return root


def _apply(root: Path, mutation: Mutation) -> None:
    target = root / mutation.path
    assert target.is_file(), f"the mutation target moved: {mutation.path}"
    text = target.read_text(encoding="utf-8")
    assert mutation.old in text, (
        f"the mutation target moved inside {mutation.path}; a control whose anchor no "
        f"longer matches silently stops testing anything"
    )
    target.write_text(text.replace(mutation.old, mutation.new, 1), encoding="utf-8")


def _run_focused(root: Path, focused: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    """Run the focused tests against `root`'s workflow package.

    TWO flags are load-bearing, and each fixes a different way the copy gets shadowed.
    Both were found by the shadow check below failing, which is the reason that check
    exists rather than being assumed:

    ```text
    -P                  `python -m` prepends the CURRENT DIRECTORY to sys.path, so
                        running from the repository root would import the real package
                        no matter what PYTHONPATH said.
    -o pythonpath=      pytest.ini sets `pythonpath = .`, and pytest's own plugin
                        inserts the rootdir at the FRONT of sys.path during early
                        conftest loading — after PYTHONPATH has been applied.
    ```

    With both, PYTHONPATH order decides, and the copy is first.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root), str(REPO_ROOT)])
    return subprocess.run(
        [
            sys.executable, "-P", "-m", "pytest", *focused,
            "-q", "--no-header", "-p", "no:cacheprovider", "-o", "pythonpath=",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_the_unmutated_copy_passes(tmp_path: Path) -> None:
    """The control for the controls: with nothing planted, the focused tests pass.

    Without this, a harness that always reported failure would satisfy every mutation
    below while proving nothing at all.
    """
    root = _scratch(tmp_path)
    focused = tuple(dict.fromkeys(t for m in MUTATIONS for t in m.focused))
    completed = _run_focused(root, focused)
    assert completed.returncode == 0, (
        f"the unmutated copy already fails {focused}, so no control below proves "
        f"anything:\n{completed.stdout[-2000:]}"
    )


def test_the_scratch_copy_shadows_the_real_package(tmp_path: Path) -> None:
    """A mutation only means something if the focused test reads the COPY.

    This plants a mutation whose effect is unmistakable, and requires the focused test
    to fail. If the copy ever stopped shadowing the real package, every other control in
    this module would pass while testing nothing — which is how this check earned its
    place: the first run of this harness had every control passing, because the copy was
    never being imported at all.
    """
    root = _scratch(tmp_path)
    baseline = _run_focused(root, SHADOW_MUTATION.focused)
    assert baseline.returncode == 0, (
        f"the shadow check is not measuring the copy:\n{baseline.stdout[-2000:]}"
    )

    _apply(root, SHADOW_MUTATION)
    mutated = _run_focused(root, SHADOW_MUTATION.focused)
    assert mutated.returncode != 0, (
        "a tenth failure class was added to the copy and the focused test still "
        "passed, so the copy is not what the test imports"
    )


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.control)
def test_every_control_fails_when_its_guard_is_removed(
    mutation: Mutation, tmp_path: Path
) -> None:
    """§21.3. Remove the guard, and the focused test MUST fail."""
    root = _scratch(tmp_path)
    _apply(root, mutation)

    completed = _run_focused(root, mutation.focused)
    assert completed.returncode != 0, (
        f"the guard for {mutation.control!r} was removed and {mutation.focused} still "
        f"passed.\n\nGuard: {mutation.guard}\n\n{completed.stdout[-2000:]}"
    )
