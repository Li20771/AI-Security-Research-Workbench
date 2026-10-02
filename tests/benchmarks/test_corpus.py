"""AI-11 §7.4, §17, §20.2, Annex A — the v1 corpus and its non-vacuity.

Layer 2: the judges run for real; nothing is spawned and no external tool is required.

The single most important test in this file is `test_T6`..`test_T8`: for EVERY task in
the corpus, the known-bad submission must be judged non-PASS and the known-good one must
be judged PASS. §20.2 makes that the condition a task must satisfy to be runnable, and
without it a corpus is a list of claims that each oracle works.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.executor import ReferenceExecutor, ReferenceVariant
from benchmarks.oracles import JUDGES, judge_submission
from benchmarks.task import load_corpus
from benchmarks.vocabulary import OracleVerdict, TaskFamily

pytestmark = pytest.mark.layer2

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "tasks"

#: §17.3. The v1 corpus, and the tier each task holds. Frozen by Annex A.
EXPECTED_TIERS = {
    "ai11-v1-can-dbc-decode": "A",
    "ai11-v1-uds-nrc-triage": "A",
    "ai11-v1-yara-rule-author": "A",
    "ai11-v1-firmware-syn-ecu-inventory": "A",
    "ai11-v1-reverse-arm64-triage": "A",
    "ai11-v1-fuzzing-recovery-triage": "B",
}

#: §17.3. The Tier B task, named so a later change to it is a deliberate one.
TIER_B_TASK = "ai11-v1-fuzzing-recovery-triage"


@pytest.fixture(scope="module")
def tasks():
    return load_corpus(CORPUS_ROOT)


# ---------------------------------------------------------------------------
# T1 — composition (§17.1, §17.3)
# ---------------------------------------------------------------------------


def test_T1_the_corpus_holds_the_six_annex_a_tasks(tasks) -> None:
    assert {t.task_id for t in tasks} == set(EXPECTED_TIERS)


def test_T2_every_task_family_is_covered(tasks) -> None:
    assert {t.task_family for t in tasks} == set(TaskFamily)


def test_T3_every_task_is_pinned_to_the_same_source_revision(tasks) -> None:
    shas = {t.source_sha for t in tasks}
    assert len(shas) == 1
    assert shas == {"efa836ff9225f6226ca8a76615f3f45c31110d58"}


def test_T4_every_task_declares_a_version_and_a_budget(tasks) -> None:
    for task in tasks:
        assert task.task_version >= 1
        assert task.time_budget_seconds > 0


def test_T5_no_task_carries_a_result(tasks) -> None:
    from benchmarks.task import FORBIDDEN_TASK_FIELDS

    for task in tasks:
        assert not (set(task.to_mapping()) & FORBIDDEN_TASK_FIELDS)


# ---------------------------------------------------------------------------
# T6 — non-vacuity, for every task (§7.4, §20.2)
# ---------------------------------------------------------------------------


def test_T6_every_known_good_submission_is_judged_pass(tasks) -> None:
    for task in tasks:
        executor = ReferenceExecutor(task, CORPUS_ROOT)
        judgement = judge_submission(
            task.oracle.oracle_id,
            executor.produce(ReferenceVariant.KNOWN_GOOD).payload,
            executor.truth(),
        )
        assert judgement.verdict is OracleVerdict.PASS, (
            f"{task.task_id}: the known-good submission was judged "
            f"{judgement.verdict} ({judgement.reason_code}); an oracle that cannot pass "
            "its own correct answer is not an oracle"
        )


def test_T7_every_known_bad_submission_is_judged_non_pass(tasks) -> None:
    for task in tasks:
        executor = ReferenceExecutor(task, CORPUS_ROOT)
        judgement = judge_submission(
            task.oracle.oracle_id,
            executor.produce(ReferenceVariant.KNOWN_BAD).payload,
            executor.truth(),
        )
        assert judgement.verdict is not OracleVerdict.PASS, (
            f"{task.task_id}: the known-bad submission was judged PASS; this oracle "
            "cannot fail and is therefore not an oracle (§7.4)"
        )


def test_T8_every_task_declares_a_discrimination_control(tasks) -> None:
    for task in tasks:
        control = task.oracle.expected_negative
        assert control.known_good and control.known_bad
        assert (CORPUS_ROOT / task.task_id / control.known_good).is_file()
        assert (CORPUS_ROOT / task.task_id / control.known_bad).is_file()


def test_T9_every_oracle_has_a_registered_judge(tasks) -> None:
    for task in tasks:
        assert task.oracle.oracle_id in JUDGES, (
            f"{task.task_id} names oracle_id {task.oracle.oracle_id!r}, which has no "
            "judge; a corpus entry that dispatches nowhere would look merely unusual"
        )


def test_T10_a_judge_that_checked_nothing_cannot_pass() -> None:
    """Driven directly, because it is the failure mode rather than a task's state."""
    from benchmarks.oracles import Judgement  # noqa: F401  (documented import)
    from benchmarks.oracle import apply_pass_rule
    from benchmarks.run import TestCounts

    verdict, _, reason = apply_pass_rule(TestCounts(planned=0, executed=0, passed=0))
    assert verdict is OracleVerdict.UNKNOWN
    assert reason == "ORACLE_PLANNED_NOTHING"


# ---------------------------------------------------------------------------
# T11 — oracle material is excluded (§7.2, §15.3)
# ---------------------------------------------------------------------------


def test_T11_every_oracle_declares_its_material_excluded(tasks) -> None:
    for task in tasks:
        assert task.oracle.material_excluded_from_workspace is True


def test_T12_every_task_withholds_its_control_directory(tasks) -> None:
    for task in tasks:
        assert "control" in task.workspace_setup.exclude, (
            f"{task.task_id} does not withhold control/; the truth and the expected "
            "answers would be reachable from the agent-visible tree"
        )


def test_T13_the_reverse_task_withholds_its_source() -> None:
    """§A.5. A task whose source sits beside its binary is a task whose answer is read."""
    task = next(t for t in load_corpus(CORPUS_ROOT) if t.task_id == "ai11-v1-reverse-arm64-triage")
    assert "labs/reverse/arm64/hello_arm64.c" in task.workspace_setup.exclude
    assert "labs/reverse/hello/hello.c" in task.workspace_setup.exclude


def test_T14_the_reverse_task_generates_its_binary() -> None:
    """§A.5, corrected at AI-11-A: no binary exists in the tracked source SHA."""
    task = next(t for t in load_corpus(CORPUS_ROOT) if t.task_id == "ai11-v1-reverse-arm64-triage")
    assert task.workspace_setup.generated, "the binary must be BUILT, not assumed"
    assert any("hello_arm64" in path for path in task.workspace_setup.generated)


def test_T15_the_firmware_task_generates_its_image() -> None:
    """§A.4, §5.4. build_fw.sh has no reproducible-time flag, so the image is built."""
    task = next(
        t for t in load_corpus(CORPUS_ROOT) if t.task_id == "ai11-v1-firmware-syn-ecu-inventory"
    )
    assert task.workspace_setup.generated
    assert any("squashfs" in path for path in task.workspace_setup.generated)


# ---------------------------------------------------------------------------
# T16 — the gitignored corpora are never truth (§7.5, §A.6)
# ---------------------------------------------------------------------------


def test_T16_the_fuzz_task_withholds_both_untracked_corpora() -> None:
    task = next(
        t for t in load_corpus(CORPUS_ROOT) if t.task_id == "ai11-v1-fuzzing-recovery-triage"
    )
    assert "labs/vehicle/can-tools/fuzz-out" in task.workspace_setup.exclude
    assert "labs/vehicle/fuzz-out" in task.workspace_setup.exclude


def test_T17_the_fuzz_truth_uses_the_frozen_class_priority() -> None:
    """§A.6. The classes are SecurityLab's tracked frozen tuple, not a new list."""
    executor = ReferenceExecutor(
        next(
            t for t in load_corpus(CORPUS_ROOT)
            if t.task_id == "ai11-v1-fuzzing-recovery-triage"
        ),
        CORPUS_ROOT,
    )
    truth = executor.truth()
    assert truth["class_priority"] == [
        "KERNEL_ANOMALY", "ECU_CRASH", "STATE_CORRUPTION", "HANG",
        "TRANSPORT_ERROR", "UDS_RESPONSE", "DISCARD", "NORMAL",
    ]


def test_T18_a_kernel_observation_under_an_unavailable_oracle_is_refused() -> None:
    """§A.6. SecurityLab's own rule: an unavailable oracle records null, never zero."""
    executor = ReferenceExecutor(
        next(
            t for t in load_corpus(CORPUS_ROOT)
            if t.task_id == "ai11-v1-fuzzing-recovery-triage"
        ),
        CORPUS_ROOT,
    )
    truth = executor.truth()
    bad_truth = {
        "class_priority": truth["class_priority"],
        "expected": {
            "c": {"class": "DISCARD", "kernel_oracle": "UNAVAILABLE", "kernel_events": 0}
        },
    }
    from benchmarks.errors import OracleProtocolError

    with pytest.raises(OracleProtocolError):
        judge_submission(
            "ai11-v1-fuzzing-recovery-triage.oracle",
            {"answer": {"c": {"class": "DISCARD", "kernel_events": None}}},
            bad_truth,
        )


def test_T19_a_submission_claiming_events_under_an_unavailable_oracle_fails() -> None:
    executor = ReferenceExecutor(
        next(
            t for t in load_corpus(CORPUS_ROOT)
            if t.task_id == "ai11-v1-fuzzing-recovery-triage"
        ),
        CORPUS_ROOT,
    )
    truth = executor.truth()
    # case-03 has kernel_oracle UNAVAILABLE; the known-bad fixture reports events for it.
    judgement = judge_submission(
        "ai11-v1-fuzzing-recovery-triage.oracle",
        {"answer": {
            "smoke-case-01": {"class": "TRANSPORT_ERROR", "kernel_events": 0},
            "smoke-case-02": {"class": "DISCARD", "kernel_events": 0},
            "smoke-case-03": {"class": "NORMAL", "kernel_events": 0},
        }},
        truth,
    )
    assert judgement.verdict is not OracleVerdict.PASS


# ---------------------------------------------------------------------------
# T20 — Tier B is not silently promoted (§17.2)
# ---------------------------------------------------------------------------


def test_T20_the_fuzz_task_keeps_its_prerequisites(tasks) -> None:
    """§A.6, §17.2. It needs an exclusive vcan0 plus CAP_NET_ADMIN.

    It must NOT be promoted to Tier A to make the corpus look stronger. The marker of
    its tier is that its prerequisites are real and are declared.
    """
    task = next(t for t in tasks if t.task_id == TIER_B_TASK)
    kinds = {p.kind for p in task.required_preconditions}
    names = {p.name for p in task.required_preconditions}
    assert "kernel_module" in kinds
    assert "can_isotp" in names
    assert "vcan0-exclusive" in names


def test_T21_tier_b_is_the_only_task_needing_a_kernel_facility(tasks) -> None:
    for task in tasks:
        needs_kernel = any(p.kind == "kernel_module" for p in task.required_preconditions)
        assert needs_kernel == (task.task_id == TIER_B_TASK), (
            f"{task.task_id}: a kernel prerequisite would make this a Tier B task, and "
            "the tier assignment in §17.3 is frozen"
        )


def test_T22_the_shipped_tier_map_matches_the_frozen_one(tasks) -> None:
    """Recomputes the tier from declared prerequisites and compares to Annex A.

    The tier is not a label someone typed; it is a consequence of what the task needs.

    Tier A tasks do have prerequisites — `yara`, `binwalk`, a cross compiler — and those
    are ordinary programs an authoritative host installs. What separates Tier B (§A.6)
    is a KERNEL FACILITY or an EXCLUSIVE host resource: requiring `can_isotp` and
    sole use of `vcan0` is a different kind of demand from requiring a binary, and it is
    the kind a CI runner cannot satisfy at all rather than merely has not installed.
    """
    def declared_tier(task) -> str:
        needs_privileged_facility = any(
            precondition.kind in ("kernel_module", "environment")
            for precondition in task.required_preconditions
        )
        return "B" if needs_privileged_facility else "A"

    computed = {t.task_id: declared_tier(t) for t in tasks}
    assert computed == EXPECTED_TIERS


# ---------------------------------------------------------------------------
# T23 — every task names a runnable reproduce command
# ---------------------------------------------------------------------------


def test_T23_every_reproduce_command_names_the_replay_entry_point(tasks) -> None:
    for task in tasks:
        assert "benchmarks.replay" in task.oracle.reproduce_command
        assert task.task_id in task.oracle.reproduce_command


def test_T24_every_task_declares_forbidden_tools(tasks) -> None:
    """A task with nothing forbidden has not said what its boundary is."""
    for task in tasks:
        assert task.forbidden_tools, f"{task.task_id} forbids nothing"
        assert not ({p.what_ran for p in task.allowed_tools}
                    & {p.what_ran for p in task.forbidden_tools})
