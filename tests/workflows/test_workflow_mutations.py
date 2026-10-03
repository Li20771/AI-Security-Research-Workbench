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
BOUNDARY = "tests/workflows/test_workflow_record_boundary.py"
APPROVAL = "tests/workflows/test_workflow_approval.py"


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
        # §21.3's control for this line was "let B accept an approval step — T22 must
        # fail". AI-13-C implements the approval point, so ACCEPTING the step is now the
        # required behaviour and that mutation cannot be a control: it is the thing the
        # contract asks for. What guards the same boundary now is the bound that makes
        # the accepted step finite — an approval step with no declared wait would be the
        # open-ended pending state §13.4 forbids, and it is refused in the same place
        # B's refusal used to be.
        control="an approval step must declare its wait",
        guard="§12, §13.4 an approval step is accepted only WITH the wait it declares; "
              "'no limit' and 'a limit nobody wrote down' are the same at run time",
        path="workflows/definition.py",
        old='                data.get("approval_seconds"), f"{where}.approval_seconds"',
        new='                data.get("approval_seconds", 1), f"{where}.approval_seconds"  # mutated',
        focused=(f"{CORE}::test_T22_an_approval_step_with_no_declared_wait_is_refused",),
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
        old="        timeout_seconds=plan.timeout_seconds,",
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
    Mutation(
        control="step deadline anchored before execution",
        guard="§8.3 the step deadline is anchored in phase ONE and written to the "
              "record a caller persists BEFORE the execution is entered",
        path="workflows/engine.py",
        old="    step_deadline = run.step_deadline or step_deadline_from(run, moment)",
        new="    step_deadline = run.step_deadline  # mutated: not anchored at phase one",
        focused=(
            f"{RUN}::test_begin_attempt_anchors_the_step_deadline_before_any_execution",
        ),
    ),
    Mutation(
        control="CANCELLED construction invariant",
        guard="§11.2 a record in state CANCELLED names WHO and WHY at the construction "
              "boundary, so no caller reaches around `cancel()`",
        path="workflows/run.py",
        old="        if cancelled and not named:",
        new="        if cancelled and not named and False:  # mutated: the invariant is off",
        focused=(
            f"{RUN}::test_a_CANCELLED_record_cannot_be_constructed_without_who_and_why",
        ),
    ),
    Mutation(
        control="exact checkpoint-count limit is terminal",
        guard="§12 reaching a limit is terminal — at the WRITE that reaches it, not at "
              "whatever asks the run to advance next",
        path="workflows/engine.py",
        old='    if spent_count >= run.declared_limit("max_checkpoints"):',
        new='    if spent_count > run.declared_limit("max_checkpoints"):  # mutated',
        focused=(
            f"{LIMITS}::test_the_checkpoint_count_bound_is_terminal_AT_the_write_that_reaches_it",
        ),
    ),
    Mutation(
        control="exact artifact limit is terminal",
        guard="§12 the artifact bound binds AT its declared value; a bound that only "
              "bit one byte later would be a limit of maximum plus one",
        path="workflows/engine.py",
        old='    if spent_artifacts >= run.declared_limit("max_artifact_bytes"):',
        new="    if spent_artifacts > definition.limits.max_artifact_bytes:  # mutated",
        focused=(
            f"{LIMITS}::test_the_artifact_bound_is_terminal_AT_the_declared_maximum",
        ),
    ),
    Mutation(
        control="successor cannot lower a counter",
        guard="§12, §15.1 a successor may not lower a counter a bound is enforced "
              "from, so the public successor API is not a budget reset",
        path="workflows/run.py",
        old="            if getattr(successor, name) < getattr(self, name):",
        new="            if getattr(successor, name) < getattr(self, name) and False:  # mutated",
        # The checkpoint counter, not the attempt counter: lowering
        # `consumed_total_attempts` is also caught by the reservation coupling, so a
        # control pointed at it would pass with THIS guard removed — the property would
        # still hold, by a second rule. This is the counter only this guard keeps.
        focused=(
            f"{BOUNDARY}::test_a_successor_cannot_lower_the_checkpoint_count",
            f"{BOUNDARY}::test_a_successor_cannot_restore_the_attempt_budget",
        ),
    ),
    Mutation(
        control="a run is bound to its own definition",
        guard="§5 a run is only ever read through the definition it was created under, "
              "by workflow_id, revision and definition_digest",
        path="workflows/engine.py",
        old="    if definition.definition_digest != run.definition_digest:",
        new="    if definition.definition_digest != run.definition_digest and False:  # mutated",
        focused=(
            f"{BOUNDARY}::test_checkpoint_for_refuses_a_definition_digest_mismatch",
        ),
    ),
    Mutation(
        control="step identity and order are the definition's",
        guard="§6.1 a workflow is an ordered sequence of declared steps, so a successor "
              "may not add, remove, rename or reorder one",
        path="workflows/run.py",
        old="        if [record.step_id for record in successor.steps] != [",
        new="        if False:  # mutated: the step sequence is not checked",
        focused=(f"{BOUNDARY}::test_a_successor_cannot_add_a_step",),
    ),
    Mutation(
        control="COMPLETED requires every step to have succeeded",
        guard="§14 COMPLETED is what a run IS when every declared step has succeeded, "
              "not a state a caller may assert",
        path="workflows/run.py",
        old="            elif successor.state is WorkflowState.COMPLETED:",
        new="            elif successor.state is WorkflowState.COMPLETED and False:  # mutated",
        focused=(f"{BOUNDARY}::test_a_successor_cannot_declare_a_run_completed",),
    ),
    Mutation(
        control="an attempt must have been reserved to be recorded",
        guard="§6.3 an attempt may only be RECORDED if the run RESERVED it, and its "
              "number is the reserved one",
        path="workflows/run.py",
        old="            if attempt.attempt_id.attempt_no != self.inflight_attempt_no:",
        new="            if attempt.attempt_id.attempt_no != self.inflight_attempt_no and False:  # mutated",
        focused=(
            f"{BOUNDARY}::test_a_successor_cannot_record_an_attempt_the_run_never_reserved",
        ),
    ),
    Mutation(
        control="attempt numbers come from the last recorded number",
        guard="§6.3 the next attempt number comes from the last RECORDED attempt and "
              "not from how many records there are, so a lineage that starts late does "
              "not hand its number out twice",
        path="workflows/run.py",
        old="            max((attempt.attempt_id.attempt_no for attempt in current.attempts), default=0)",
        new="            len(current.attempts)  # mutated: the COUNT, not the last number",
        focused=(
            f"{BOUNDARY}::test_an_attempt_number_is_not_reused_after_a_lineage_that_starts_late",
        ),
    ),
    Mutation(
        control="step deadline released only by its step succeeding",
        guard="§8.3 the step deadline is released by the step it BOUNDS succeeding, not "
              "by another step succeeding and not by this one merely moving",
        path="workflows/run.py",
        old="            if not moved or moved[0][1].state is not StepState.SUCCEEDED:",
        new="            if not moved or moved[0][1].state is not StepState.SUCCEEDED and False:  # mutated",
        focused=(
            f"{BOUNDARY}::test_the_step_deadline_is_released_only_by_its_step_SUCCEEDING",
        ),
    ),
    Mutation(
        control="one execution, one attempt",
        guard="§6.3 a retry lineage points each AttemptId at a DISTINCT ExecutionId, so "
              "a successor may not append an execution another attempt already produced",
        path="workflows/run.py",
        old="        if len(set(produced)) != len(produced):",
        new="        if False:  # mutated: the lineage is not checked for reuse",
        focused=(
            f"{BOUNDARY}::test_a_successor_cannot_point_two_attempts_at_one_execution",
        ),
    ),
    Mutation(
        control="a step's state is what its attempt did",
        guard="§15.2 an attempt that did NOT succeed cannot make its step SUCCEEDED — "
              "which also stops it releasing the step deadline",
        path="workflows/run.py",
        old="                if moved[0][1].state not in _STEP_STATES_BY_OUTCOME[outcome]:",
        new="                if moved[0][1].state not in _STEP_STATES_BY_OUTCOME[outcome] and False:  # mutated",
        focused=(
            f"{BOUNDARY}::test_a_failed_attempt_cannot_make_its_step_SUCCEEDED",
        ),
    ),
    Mutation(
        control="reached_bound must fit the terminal state",
        guard="§15.2 which bound a run reached is a FACT: a run that failed or finished "
              "reached none, and a bound named for the wrong terminal state is refused",
        path="workflows/run.py",
        old="            if bound not in _BOUNDS_BY_TERMINAL_STATE.get(successor.state, frozenset()):",
        new="            if False:  # mutated: any state may name any bound",
        focused=(
            f"{BOUNDARY}::test_a_completed_run_cannot_name_a_bound",
            f"{BOUNDARY}::test_a_run_that_reached_no_bound_cannot_name_one",
        ),
    ),
    Mutation(
        control="declared bounds are frozen, not merely un-assignable",
        guard="§15.2 `declared` is copied into a read-only mapping, so it cannot be "
              "edited in place behind the successor boundary and the digest",
        path="workflows/run.py",
        old="        object.__setattr__(\n"
            '            self, "declared", MappingProxyType(dict(self.declared))\n'
            "        )",
        new="        pass  # mutated: declared stays a mutable mapping",
        focused=(
            f"{BOUNDARY}::test_the_declared_bounds_cannot_be_edited_in_place",
        ),
    ),
    Mutation(
        control="the failure vocabulary is closed at construction",
        guard="§9.1 FailureClass is exactly the nine members; a constructed attempt may "
              "not carry a value outside them, and nothing is coerced into one",
        path="workflows/run.py",
        old="        if self.failure_class is not None and not isinstance(\n"
            "            self.failure_class, FailureClass\n"
            "        ):",
        new="        if False:  # mutated: the vocabulary is not checked",
        focused=(
            f"{BOUNDARY}::test_a_failure_class_outside_the_nine_cannot_be_constructed",
        ),
    ),
    Mutation(
        control="an attempt's instants are §8.3 instants",
        guard="§8.3 an attempt's started_at and ended_at are the phase's one timestamp "
              "shape, so a record cannot be written that from_mapping then refuses",
        path="workflows/run.py",
        old="            if not is_instant(getattr(self, name)):",
        new="            if False:  # mutated: the instant shape is not checked",
        focused=(f"{BOUNDARY}::test_an_attempt_instant_must_be_an_8_3_instant",),
    ),
    Mutation(
        control="an attempt cannot end before it began",
        guard="§15.2 the two instants recorded for an attempt are ordered",
        path="workflows/run.py",
        old="        if parse_instant(self.ended_at) < parse_instant(self.started_at):",
        new="        if False:  # mutated: the instants are not ordered",
        focused=(f"{BOUNDARY}::test_an_attempt_cannot_end_before_it_began",),
    ),
    Mutation(
        control="succeeded is a boolean, not a truthy value",
        guard="§15.2 whether an attempt succeeded is not decided by truthiness — "
              "`succeeded=1` and the non-empty string `true` are both refused",
        path="workflows/run.py",
        old="        if not isinstance(self.succeeded, bool):",
        new="        if False:  # mutated: truthiness decides the outcome",
        focused=(f"{BOUNDARY}::test_succeeded_must_be_a_boolean",),
    ),
    Mutation(
        control="artifact_refs are ArtifactRefs",
        guard="§7.2 an attempt's artifact_refs is a tuple of references, so a bare value "
              "cannot survive construction and fail at to_body()",
        path="workflows/run.py",
        old="        if not isinstance(self.artifact_refs, tuple) or not all(",
        new="        if False:  # mutated: any object may be an artifact reference",
        focused=(f"{BOUNDARY}::test_artifact_refs_must_be_a_tuple_of_ArtifactRef",),
    ),
    Mutation(
        control="execution_id is a non-empty string",
        guard="§6.3 an attempt records the ExecutionId it produced, and an attempt that "
              "produced none is not this record",
        path="workflows/run.py",
        old="        if not isinstance(self.execution_id, str) or not self.execution_id.strip():",
        new="        if False:  # mutated: any value may be an ExecutionId",
        focused=(f"{BOUNDARY}::test_execution_id_must_be_a_non_empty_string",),
    ),
    Mutation(
        control="the parser does not coerce a boolean",
        guard="§15.2 the parser reads `succeeded` strictly; `bool(value)` turns the "
              "non-empty string `true` into True — an illegal value converted into a "
              "legal one, which is the one thing both boundaries refuse to do",
        path="workflows/run.py",
        old="    if not isinstance(value, bool):\n"
            "        raise InvalidRecord(f\"{where} must be a boolean (§15.2)\")\n"
            "    return value",
        new="    return bool(value)  # mutated: an illegal value becomes a legal one",
        focused=(
            f"{BOUNDARY}::test_the_typed_constructor_and_the_parser_refuse_the_same_records",
        ),
    ),
    Mutation(
        control="the attempt admission gate",
        guard="§13.1.2 an attempt at a GATED step does not begin without an accepted "
              "approval covering ITS number — the gate Amendment 4 added",
        path="workflows/engine.py",
        old="    if definition.gating_step(step.step_id) is not None and not run.approval_covers(",
        new="    if False and definition.gating_step(step.step_id) is not None and not run.approval_covers(",
        focused=(f"{APPROVAL}::test_T26_a_gated_attempt_without_a_covering_approval_is_not_admitted",),
    ),
    Mutation(
        control="an approval covers ONE attempt number",
        guard="§13.2 `attempt_no` is one of the six, so an approval is matched on the "
              "EXACT number and never on 'an approval exists for this step'",
        path="workflows/run.py",
        old="            entry.step_id == step_id and entry.attempt_no == attempt_no",
        new="            entry.step_id == step_id  # mutated: any approval for the step",
        focused=(
            f"{APPROVAL}::test_the_scope_is_not_inherited_across_attempts",
            f"{APPROVAL}::test_T28_resume_with_only_the_previous_approval_cannot_start_the_next_attempt",
        ),
    ),
    Mutation(
        control="a crashed attempt's number is spent",
        guard="§6.3, §13.1.3 a process that died after reserving an attempt spent that "
              "number, so the next legal attempt is the NEXT one and no approval covers it",
        path="workflows/engine.py",
        old="    return max(recorded, run.inflight_attempt_no or 0) + 1",
        new="    return recorded + 1  # mutated: a crashed attempt's number is forgotten",
        focused=(
            f"{APPROVAL}::test_T28b_a_resume_reaches_the_next_attempt_only_through_a_fresh_approval",
        ),
    ),
    Mutation(
        control="a wait is not re-opened for an approved attempt",
        guard="§13.1.3 the re-entry is refused when the next legal attempt ALREADY has "
              "an accepted approval, so one attempt never draws two requests",
        path="workflows/run.py",
        old="    return not successor.approval_covers(gated.step_id, next_no)",
        new="    return True  # mutated: the wait is re-opened for an approved attempt",
        focused=(
            f"{APPROVAL}::test_a_successor_cannot_re_open_a_wait_for_an_already_approved_attempt",
        ),
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
