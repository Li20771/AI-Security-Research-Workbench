"""AI-11 §7, §A.6 — the fuzzing/recovery oracle, as §27 freezes it. Layer 2.

The oracle for `ai11-v1-fuzzing-recovery-triage` re-runs the pinned generator at a fixed
seed and judges the submission against what THAT run observed. §27 (Amendment 1) exists
because the first implementation chose four things the generator does not support — an
`--json` flag it never had, a JSON record stdout never carries, case identifiers it never
emits, and "non-zero exit means the environment is broken" — so every one of those is
tested here as a REFUSAL rather than as a happy path.

### How these tests reach the run without the generator

The generator needs Linux, vcan0, the `can_isotp` module, python-can and can-isotp.
`StubGenerator` replaces it: it writes the same per-case files and the same summary,
prints the same shape of operational log, and returns an exit code the test chooses. It
evaluates nothing, so no test here can be satisfied by an evaluator that knows the
answer. Everything downstream of it — the collector, the kernel normalisation, the
counts, the judge, the regression observation — runs for real.

`vcan0_exclusivity_reason()` is the one seam opened by `_open_gate`, because §27.7 makes
it return a reason on EVERY host: no exclusivity mechanism is admitted, so a collection
cannot otherwise proceed. `test_F17`/`test_F18` exercise it closed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import benchmarks.oracles as oracles
from benchmarks.executor import ReferenceExecutor, ReferenceVariant
from benchmarks.oracle import ProcessResult
from benchmarks.oracles import (
    FUZZ_GENERATOR,
    FUZZ_RECOVERY_EXPECTED,
    FUZZ_RECOVERY_REQUEST,
    FUZZ_RERUN_SEED,
    collect,
    evaluate_ecu_recovery,
    evaluate_submission,
    run_fuzz_smoke,
)
from benchmarks.runner import evaluate_regression
from benchmarks.task import load_task
from benchmarks.vocabulary import OracleVerdict

pytestmark = pytest.mark.layer2

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "tasks"
TASK_ID = "ai11-v1-fuzzing-recovery-triage"
ORACLE_ID = f"{TASK_ID}.oracle"
CONTROL = CORPUS_ROOT / TASK_ID / "control"


def _case(
    case_id: str,
    klass: str = "DISCARD",
    *,
    kernel: str = "AVAILABLE",
    events: list | None = None,
    alive: bool = True,
    recovery: str = "PASS",
    response: str | None = FUZZ_RECOVERY_EXPECTED,
) -> dict:
    return {
        "case_id": case_id,
        "class": klass,
        "kernel_oracle": kernel,
        # The generator reports a LIST when AVAILABLE and null otherwise.
        "kernel_events": ([] if events is None else events) if kernel == "AVAILABLE" else None,
        "process_alive": alive,
        "recovery": recovery,
        "recovery_response": response,
        "recovery_request": FUZZ_RECOVERY_REQUEST,
        "recovery_expected": FUZZ_RECOVERY_EXPECTED,
    }


class StubGenerator:
    """The pinned generator's OUTPUT, without the generator. **It is NOT the tool.**

    It answers the three programs the A.6 code paths invoke — `ip`, `ps` and the
    generator itself — and nothing else, so a path that started shelling out to
    something new would fail here rather than quietly find it absent.
    """

    def __init__(
        self,
        cases: list[dict],
        *,
        exit_code: int = 0,
        stop_after: int | None = None,
        stdout: str = "",
        write_files: bool = True,
        summary_total: int | None = None,
        process_table: str = "",
        ps_exit: int = 0,
        ip_exit: int = 0,
    ) -> None:
        self.cases = cases
        self.exit_code = exit_code
        self.stop_after = stop_after
        self.stdout = stdout
        self.write_files = write_files
        self.summary_total = summary_total
        self.process_table = process_table
        self.ps_exit = ps_exit
        self.ip_exit = ip_exit
        self.calls: list[list[str]] = []

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        args = list(argv)
        self.calls.append(args)
        if args[0] == "ip":
            return ProcessResult(exit_code=self.ip_exit, stdout="vcan0: <UP>\n")
        if args[0] == "ps":
            return ProcessResult(exit_code=self.ps_exit, stdout=self.process_table)
        # The generator is run as `<python> <generator> ...`, so the script is argv[1].
        if not (len(args) > 1 and args[1].endswith(FUZZ_GENERATOR.rsplit("/", 1)[-1])):
            raise AssertionError(f"the A.6 code invoked an undeclared program: {args[0]!r}")

        executed = self.cases if self.stop_after is None else self.cases[: self.stop_after]
        out_dir = Path(args[args.index("--out") + 1])
        out_dir.mkdir(parents=True, exist_ok=True)
        if self.write_files:
            for case in executed:
                document = {
                    "case_id": case["case_id"],
                    "expected": {
                        "recovery_request": case["recovery_request"],
                        "recovery_expected": case["recovery_expected"],
                    },
                    "result": {k: v for k, v in case.items() if k != "case_id"},
                }
                (out_dir / f"{case['case_id']}.json").write_text(
                    json.dumps(document), encoding="utf-8"
                )
            (out_dir / "smoke-summary.json").write_text(
                json.dumps(
                    {
                        "master_seed": FUZZ_RERUN_SEED,
                        "total": self.summary_total
                        if self.summary_total is not None
                        else len(self.cases),
                        "summary": {},
                        "kernel_oracle": {},
                        "high_priority": [],
                    }
                ),
                encoding="utf-8",
            )
        return ProcessResult(exit_code=self.exit_code, stdout=self.stdout)


def _source_root(tmp_path: Path) -> Path:
    """A source tree holding the generator and the ECU script, by their pinned paths."""
    root = tmp_path / "source"
    (root / Path(FUZZ_GENERATOR).parent).mkdir(parents=True, exist_ok=True)
    (root / FUZZ_GENERATOR).write_text("# the pinned generator\n", encoding="utf-8")
    ecu = root / "labs/vehicle/uds-basic/ecu/ecu.py"
    ecu.parent.mkdir(parents=True, exist_ok=True)
    ecu.write_text("# the pinned ECU\n", encoding="utf-8")
    return root


def _open_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Open the one seam §27.7 closes on every current host."""
    monkeypatch.setattr(oracles, "vcan0_exclusivity_reason", lambda runner, timeout: "")


def _truth(cases: list[dict], priority: list[str] | None = None) -> dict:
    return {
        "class_priority": priority
        or [
            "KERNEL_ANOMALY", "ECU_CRASH", "STATE_CORRUPTION", "HANG",
            "TRANSPORT_ERROR", "UDS_RESPONSE", "DISCARD", "NORMAL",
        ],
        "expected": {
            case["case_id"]: {
                "class": case["class"],
                "kernel_oracle": case["kernel_oracle"],
                # The truth carries §27.4's COUNT. A case built with a list is counted;
                # a case built with a deliberately wrong shape is carried as-is so the
                # test is about the collector refusing it, not about the helper.
                "kernel_events": (
                    len(case["kernel_events"])
                    if isinstance(case["kernel_events"], list)
                    else case["kernel_events"]
                ),
            }
            for case in cases
        },
    }


def _collect(tmp_path: Path, generator: StubGenerator, truth: dict, submission: dict):
    root = _source_root(tmp_path)
    return collect(
        ORACLE_ID,
        submission,
        truth,
        control_dir=CONTROL,
        source_root=root,
        setup_dir=tmp_path / "setup",
        runner=generator,
    )


# ---------------------------------------------------------------------------
# F1/F2 — the invocation §27.1 freezes, and the flag it forbids
# ---------------------------------------------------------------------------


def test_F1_the_invocation_is_the_one_section_27_freezes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--smoke --seed 12345 --out <scratch>`: no `--json`, no `--max-cases`.

    `--json` is not an argument the generator has, and `--max-cases` would truncate the
    case set that §27.2 defines the authoritative set to be.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1"), _case("b__y__2")]
    generator = StubGenerator(cases)

    _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    invocation = [call for call in generator.calls if call[0] != "ip"][0]
    assert "--smoke" in invocation
    assert invocation[invocation.index("--seed") + 1] == str(FUZZ_RERUN_SEED)
    assert invocation[invocation.index("--out") + 1].startswith(str(tmp_path))
    assert "--json" not in invocation, "§27.1: the generator has no such argument"
    assert "--max-cases" not in invocation, "§27.2: it truncates the authoritative set"


def test_F1b_a_run_directory_inside_the_source_tree_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.1: the run writes to the harness's scratch, never to the source tree.

    The generator's DEFAULT output directory is `labs/vehicle/can-tools/fuzz-out` inside
    the source tree — the directory §16 forbids writing to and §7.5 forbids reading.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1")]
    generator = StubGenerator(cases)

    _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    invocation = [call for call in generator.calls if call[0] != "ip"][0]
    out_dir = Path(invocation[invocation.index("--out") + 1])
    assert "fuzz-out" not in str(out_dir)
    assert tmp_path in out_dir.parents


# ---------------------------------------------------------------------------
# F3/F4 — the observation comes from the files, never from stdout
# ---------------------------------------------------------------------------


def test_F3_the_observation_comes_from_the_case_files_not_from_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.6. stdout is an operational log, and it is not parsed.

    The stub prints a JSON object on stdout that disagrees with its own files. A
    collector that read stdout would answer with it; the real answer is in the files.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", "TRANSPORT_ERROR"), _case("b__y__2", "DISCARD")]
    noisy = json.dumps(
        {"cases": {"a__x__1": {"class": "NORMAL"}, "b__y__2": {"class": "NORMAL"}}}
    )
    generator = StubGenerator(cases, stdout=noisy + "\n")

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert observation.values["derived"]["a__x__1"]["class"] == "TRANSPORT_ERROR"
    assert observation.values["derived"]["b__y__2"]["class"] == "DISCARD"


def test_F3b_a_run_whose_stdout_is_the_only_output_observes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No case files means no observation — however much the run printed."""
    _open_gate(monkeypatch)
    cases = [_case("a__x__1")]
    generator = StubGenerator(
        cases, write_files=False, stdout='{"cases": {"a__x__1": {"class": "DISCARD"}}}\n'
    )

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert not observation.complete
    assert observation.reason_code == "FUZZ_RERUN_OUTPUT_UNREADABLE"


# ---------------------------------------------------------------------------
# F5/F6/F7 — case identity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stale", ["smoke-case-01", "smoke-case-02", "smoke-case-03"])
def test_F5_a_stale_case_identifier_is_refused_not_mapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stale: str
) -> None:
    """§27.2. The names the previous truth carried are refused BY NAME.

    Nothing renames them, renumbers them, or maps them onto a generated case: no tracked
    mapping ever existed, and inventing one would be inventing an observation.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1")]
    truth = _truth(cases)
    truth["expected"][stale] = {
        "class": "NORMAL", "kernel_oracle": "AVAILABLE", "kernel_events": 0,
    }
    generator = StubGenerator(cases)

    observation = _collect(tmp_path, generator, truth, {"answer": {}})

    assert not observation.complete
    assert observation.reason_code == f"FUZZ_TRUTH_MATERIAL_STALE:{stale}"
    assert generator.calls == [], "the generator ran against refused material"


def test_F6_the_generators_own_case_ids_are_carried_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.2. Identity is `make_case_id()`. The Workbench invents nothing."""
    _open_gate(monkeypatch)
    identifiers = [
        "sn_skip_1_3__pci__pci-0x4x",
        "fc_bs_1__bs__bs-0",
        "baseline_sf_1001__pci__pci-0x4x",
    ]
    cases = [_case(case_id) for case_id in identifiers]
    generator = StubGenerator(cases)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert sorted(observation.values["derived"]) == sorted(identifiers)


def test_F7_a_truth_that_is_not_the_case_set_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.3. `truth.expected` must BE the authoritative case set.

    A material file that names fewer cases than the run produced is not this task's
    truth, and comparing against it would score the cases it happens to mention.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1"), _case("b__y__2")]
    generator = StubGenerator(cases)
    truth = _truth(cases[:1])

    observation = _collect(tmp_path, generator, truth, {"answer": {}})

    assert not observation.complete
    assert observation.reason_code == "FUZZ_TRUTH_CASE_IDS_NOT_AUTHORITATIVE:b__y__2"


# ---------------------------------------------------------------------------
# F8/F9/F10 — exit codes, §27.5
# ---------------------------------------------------------------------------


def test_F8_exit_zero_is_a_complete_candidate_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_gate(monkeypatch)
    cases = [_case("a__x__1"), _case("b__y__2")]
    generator = StubGenerator(cases, exit_code=0)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert observation.complete
    assert observation.planned == 2


def test_F9_an_early_stop_is_incomplete_and_never_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.5. Exit 1 is a COMPLETED run that stopped on a finding.

    It is not an environment failure — the run did its job and found something — and it
    is not a pass either: the cases that never ran were never observed.
    """
    _open_gate(monkeypatch)
    cases = [_case(f"case_{index}__dim__label") for index in range(5)]
    generator = StubGenerator(cases, exit_code=1, stop_after=2)
    executor = ReferenceExecutor(load_task(CORPUS_ROOT / TASK_ID / "task.yaml"), CORPUS_ROOT)

    result = evaluate_submission(
        oracle_id=ORACLE_ID,
        required=True,
        submission={"answer": {case["case_id"]: {"class": case["class"],
                                                 "kernel_events": 0} for case in cases}},
        truth=_truth(cases),
        control_dir=CONTROL,
        source_root=_source_root(tmp_path),
        setup_dir=tmp_path / "setup",
        runner=generator,
    )

    assert result.verdict is not OracleVerdict.PASS
    assert result.verdict is not OracleVerdict.BLOCKED, (
        "a completed run that found something is not an unavailable environment"
    )
    assert result.tests.planned == 5, "planned is what the generator CONSTRUCTED"
    assert result.tests.executed == 2, "executed is what it wrote a result for"
    assert result.tests.skipped == 3
    assert result.reason_code == "FUZZ_RERUN_STOPPED_EARLY"


def test_F10_an_invocation_defect_is_named_and_not_dressed_as_an_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.5. Exit 2 is the harness's own command line being rejected."""
    _open_gate(monkeypatch)
    cases = [_case("a__x__1")]
    generator = StubGenerator(cases, exit_code=2, write_files=False)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert not observation.complete
    assert observation.reason_code == "FUZZ_INVOCATION_DEFECT:2"
    assert observation.planned == 1


def test_F10b_a_generator_that_never_started_is_an_environment_fact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.1. Exit 1 with NO output is the interpreter's imports failing.

    The exit code alone does not tell these apart — that is why §27.5 says the run's own
    files are what distinguishes them.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1")]
    generator = StubGenerator(cases, exit_code=1, write_files=False)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert not observation.complete
    assert observation.reason_code == "FUZZ_GENERATOR_DEPENDENCY_UNAVAILABLE"


# ---------------------------------------------------------------------------
# F11/F12/F13 — the kernel oracle, §27.4
# ---------------------------------------------------------------------------


def test_F11_an_available_oracle_with_no_anomaly_records_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AVAILABLE + `[]` -> 0, because the oracle ran and found nothing."""
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", kernel="AVAILABLE", events=[])]
    generator = StubGenerator(cases)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert observation.values["derived"]["a__x__1"]["kernel_events"] == 0


def test_F11b_an_available_oracle_counts_the_lines_it_matched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recorded number is the COUNT of matching lines, not the lines themselves."""
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", kernel="AVAILABLE", events=["BUG: one", "BUG: two"])]
    generator = StubGenerator(cases)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert observation.values["derived"]["a__x__1"]["kernel_events"] == 2


@pytest.mark.parametrize("kernel", ["UNAVAILABLE", "ERROR"])
def test_F12_a_non_available_oracle_records_null_never_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kernel: str
) -> None:
    """§27.4, and SecurityLab's own rule: null, never 0, never an empty list."""
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", kernel=kernel)]
    truth = _truth(cases)
    truth["expected"]["a__x__1"]["kernel_events"] = None
    generator = StubGenerator(cases)

    observation = _collect(tmp_path, generator, truth, {"answer": {}})

    assert observation.values["derived"]["a__x__1"]["kernel_events"] is None
    assert observation.values["derived"]["a__x__1"]["kernel_oracle"] == kernel


def test_F13_an_empty_list_under_a_non_available_oracle_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one normalisation §27.4 forbids: `[]` becoming 0 without an AVAILABLE oracle.

    The stub is made to emit the forbidden shape directly, so this is the code path that
    would silently produce a zero if the two branches ever met.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", kernel="UNAVAILABLE", events=[])]
    cases[0]["kernel_events"] = []  # the forbidden shape, forced past the helper
    truth = _truth(cases)
    truth["expected"]["a__x__1"]["kernel_events"] = None
    generator = StubGenerator(cases)

    observation = _collect(tmp_path, generator, truth, {"answer": {}})

    assert not observation.complete
    assert observation.reason_code.startswith(
        "FUZZ_KERNEL_EVENTS_UNDER_UNAVAILABLE_ORACLE"
    )


def test_F13b_an_available_oracle_that_reports_no_list_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An AVAILABLE oracle reports a list. Anything else is a shape this oracle cannot
    read, and reading it as "no events" would invent a measurement."""
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", kernel="AVAILABLE", events=[])]
    cases[0]["kernel_events"] = 0  # not a list
    generator = StubGenerator(cases)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert not observation.complete
    assert observation.reason_code.startswith("FUZZ_KERNEL_EVENTS_NOT_A_LIST")


# ---------------------------------------------------------------------------
# F14/F15/F16 — provenance and counts
# ---------------------------------------------------------------------------


def test_F14_the_observation_is_not_read_back_out_of_the_truth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.3. A truth that disagrees with the run must not move the observation.

    The run says TRANSPORT_ERROR. A truth that says otherwise is material drift, and the
    derived value has to stay what the generator produced.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", "TRANSPORT_ERROR")]
    generator = StubGenerator(cases)
    truth = _truth(cases)
    truth["expected"]["a__x__1"]["class"] = "NORMAL"

    observation = _collect(tmp_path, generator, truth, {"answer": {}})

    assert observation.values["derived"]["a__x__1"]["class"] == "TRANSPORT_ERROR"
    assert observation.values["expected"]["a__x__1"]["class"] == "NORMAL"


def test_F15_a_case_that_did_not_execute_is_missing_not_invented(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A case file the run did not write is a case that did not run."""
    _open_gate(monkeypatch)
    cases = [_case(f"case_{index}__dim__label") for index in range(4)]
    generator = StubGenerator(cases, exit_code=1, stop_after=1)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert observation.complete, "an early stop is an observation, not a refusal"
    assert len(observation.values["derived"]) == 1
    assert observation.planned == 4


def test_F16_the_counts_come_from_the_run_not_from_the_truth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.9. `planned` is what the generator CONSTRUCTED, read from its own summary."""
    _open_gate(monkeypatch)
    cases = [_case(f"case_{index}__dim__label") for index in range(3)]
    generator = StubGenerator(cases, summary_total=9)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert observation.planned == 9, "the run's own summary, not len(truth.expected)"


# ---------------------------------------------------------------------------
# F17/F18 — vcan0 exclusivity, §27.7
# ---------------------------------------------------------------------------


def test_F17_an_up_vcan0_is_not_proof_of_exclusive_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.7, with the real gate and a host where the interface IS up.

    `ip link show vcan0` exits 0 and proves only that the interface exists. No mechanism
    admitted by §27.7 can show that nobody else is on it, so the honest verdict is
    BLOCKED — and the generator is never invoked.
    """
    cases = [_case("a__x__1")]
    generator = StubGenerator(cases, ip_exit=0)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert not observation.complete
    assert observation.reason_code == "PRECONDITION_UNMET:environment:vcan0-exclusive"
    assert [call[0] for call in generator.calls] == ["ip"], (
        "the generator ran although the precondition could not be established"
    )


def test_F18_an_unprovable_precondition_is_blocked_and_never_pass_or_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = [_case("a__x__1")]
    generator = StubGenerator(cases, ip_exit=0)
    submission = {"answer": {"a__x__1": {"class": "DISCARD", "kernel_events": 0}}}

    result = evaluate_submission(
        oracle_id=ORACLE_ID, required=True, submission=submission, truth=_truth(cases),
        control_dir=CONTROL, source_root=_source_root(tmp_path),
        setup_dir=tmp_path / "setup", runner=generator,
    )

    assert result.verdict is OracleVerdict.BLOCKED
    assert result.verdict is not OracleVerdict.PASS
    assert result.verdict is not OracleVerdict.FAIL
    assert result.verdict is not OracleVerdict.NOT_RUN
    assert result.tests.executed == 0
    assert result.tests.skipped == result.tests.planned
    assert "PRECONDITION_UNMET:environment:vcan0-exclusive" in " ".join(result.limitations)


def test_F18b_a_host_without_vcan0_is_blocked_the_same_way_and_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A probe that cannot run is not exclusivity either. The verdict is the same and
    the reason is the same code, because §27.7 makes them the same fact."""
    cases = [_case("a__x__1")]
    generator = StubGenerator(cases, ip_exit=1)

    observation = _collect(tmp_path, generator, _truth(cases), {"answer": {}})

    assert not observation.complete
    assert observation.reason_code == "PRECONDITION_UNMET:environment:vcan0-exclusive"


# ---------------------------------------------------------------------------
# F19/F20/F21 — recovery, the regression axis, and discrimination
# ---------------------------------------------------------------------------


def _recovery(tmp_path: Path, generator: StubGenerator):
    return evaluate_ecu_recovery(
        source_root=_source_root(tmp_path),
        setup_dir=tmp_path / "setup",
        runner=generator,
        timeout_seconds=60,
    )


def test_F19_the_recovery_observation_comes_from_the_controlled_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.8. Survived + probe answered, read from the run the generator performed."""
    _open_gate(monkeypatch)
    cases = [_case("a__x__1"), _case("b__y__2")]
    verdict, reason = _recovery(tmp_path, StubGenerator(cases))
    assert verdict is OracleVerdict.PASS
    assert reason == "ECU_SURVIVED_AND_RECOVERED"


def test_F19b_an_ecu_that_did_not_survive_is_a_failed_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", alive=False, klass="ECU_CRASH")]
    verdict, reason = _recovery(tmp_path, StubGenerator(cases))
    assert verdict is OracleVerdict.FAIL
    assert reason == "ECU_DID_NOT_SURVIVE:a__x__1"


def test_F19c_an_unanswered_probe_is_a_failed_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", recovery="FAIL", response=None)]
    verdict, reason = _recovery(tmp_path, StubGenerator(cases))
    assert verdict is OracleVerdict.FAIL
    assert reason == "ECU_DID_NOT_RECOVER:a__x__1"


def test_F19d_a_residual_ecu_process_is_a_failed_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The post-execution observation §12 assigns to the harness."""
    _open_gate(monkeypatch)
    cases = [_case("a__x__1")]
    table = f" 1234 /usr/bin/python3 -u {tmp_path}/source/labs/vehicle/uds-basic/ecu/ecu.py\n"
    verdict, reason = _recovery(tmp_path, StubGenerator(cases, process_table=table))
    assert verdict is OracleVerdict.FAIL
    assert reason == "ECU_PROCESS_RESIDUAL"


def test_F19e_a_process_state_that_cannot_be_read_is_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An observation that was not made is not a satisfied one."""
    _open_gate(monkeypatch)
    cases = [_case("a__x_1".replace("_1", "1"))]
    verdict, reason = _recovery(tmp_path, StubGenerator(cases, ps_exit=1))
    assert verdict is OracleVerdict.BLOCKED
    assert reason == "FUZZ_REGRESSION_PROCESS_STATE_UNOBSERVABLE"


def test_F20_the_negative_control_is_not_a_recovery_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27.8. The two axes answer different questions, and one cannot stand in for the
    other.

    The ECU does NOT recover here. The known_bad answer would still be rejected by the
    classification oracle — the discrimination control still works — and the regression
    axis must nevertheless report the failed recovery rather than a pass inherited from
    that rejection.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1", recovery="FAIL", response=None)]
    generator = StubGenerator(cases)
    task = load_task(CORPUS_ROOT / TASK_ID / "task.yaml")
    executor = ReferenceExecutor(task, CORPUS_ROOT)

    verdict, reason, results = evaluate_regression(
        task=task,
        corpus_root=CORPUS_ROOT,
        source_root=_source_root(tmp_path),
        setup_dir=tmp_path / "setup",
        workspace_root=None,
        oracle_runner=generator,
    )

    assert verdict is OracleVerdict.FAIL
    assert reason == "REGRESSION_NOT_SATISFIED"
    assert results[0]["reason_code"] == "ECU_DID_NOT_RECOVER:a__x__1"
    assert "NEGATIVE_CONTROL" not in json.dumps(results), (
        "the recovery condition consulted the negative control"
    )


def test_F20b_the_aggregate_reason_does_not_claim_a_control_was_judged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A true verdict with a false explanation attached is still a false record.

    The subject-side condition never judges a negative control, so the aggregate may not
    report that one was rejected and found wanting.
    """
    _open_gate(monkeypatch)
    cases = [_case("a__x__1"), _case("b__y__2")]
    task = load_task(CORPUS_ROOT / TASK_ID / "task.yaml")

    verdict, reason, results = evaluate_regression(
        task=task, corpus_root=CORPUS_ROOT,
        source_root=_source_root(tmp_path), setup_dir=tmp_path / "setup",
        workspace_root=None, oracle_runner=StubGenerator(cases),
    )

    assert verdict is OracleVerdict.PASS
    assert reason == "REGRESSION_CONDITIONS_SATISFIED"
    assert results[0]["reason_code"] == "ECU_SURVIVED_AND_RECOVERED"


def test_F21_the_two_controls_are_discriminated_and_the_run_agrees_with_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§7.4, on the REAL corpus material and a run that reproduces it.

    The stub replays the tracked truth's own case set and classes, so this is the
    end-to-end statement: the correct answer passes, and the answer that reclassifies
    one case does not.
    """
    _open_gate(monkeypatch)
    task = load_task(CORPUS_ROOT / TASK_ID / "task.yaml")
    executor = ReferenceExecutor(task, CORPUS_ROOT)
    truth = executor.truth()
    cases = [
        _case(case_id, entry["class"], kernel=entry["kernel_oracle"],
              events=[] if entry["kernel_events"] == 0 else None)
        for case_id, entry in sorted(truth["expected"].items())
    ]

    def judged(variant):
        return evaluate_submission(
            oracle_id=ORACLE_ID, required=True,
            submission=executor.produce(variant).payload, truth=truth,
            control_dir=CONTROL, source_root=_source_root(tmp_path / variant.value),
            setup_dir=tmp_path / variant.value / "setup",
            runner=StubGenerator(cases),
        )

    good = judged(ReferenceVariant.KNOWN_GOOD)
    bad = judged(ReferenceVariant.KNOWN_BAD)

    assert good.verdict is OracleVerdict.PASS, good.reason_code
    assert good.tests.planned == good.tests.executed == 30
    assert good.tests.skipped == 0

    assert bad.verdict is OracleVerdict.FAIL, bad.reason_code
    assert bad.tests.failed == 1, "exactly the one reclassified case"
    assert bad.reason_code.startswith("FUZZ_CLASSIFICATION_MISMATCH")


def test_F22_the_tracked_material_carries_no_stale_identifier() -> None:
    """§27.2. `smoke-case-*` must not appear in the A.6 material at all."""
    for name in ("truth.json", "known_good.json", "known_bad.json"):
        text = (CONTROL / name).read_text(encoding="utf-8")
        assert "smoke-case" not in text, f"{name} still carries a stale case identifier"


def test_F22b_the_tracked_material_records_only_what_section_27_allows() -> None:
    """§27.3. No per-run capture became expected truth."""
    truth = json.loads((CONTROL / "truth.json").read_text(encoding="utf-8"))
    forbidden = {"timestamp", "duration_ms", "errno", "process_returncode",
                 "ecu_log_tail", "kernel_delta_lines", "response", "hung"}
    for case_id, entry in truth["expected"].items():
        assert not (set(entry) & forbidden), f"{case_id} carries a per-run capture"
        assert set(entry) == {"class", "kernel_oracle", "kernel_events"}
    assert truth["rerun"]["source_sha"] == "efa836ff9225f6226ca8a76615f3f45c31110d58"


def test_F22c_the_reproduction_alone_decides_the_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`run_fuzz_smoke` reads the run's files and nothing else.

    Called directly, with a run whose case set is unrelated to the corpus, it returns
    that run's cases — the corpus is not reachable from it.
    """
    cases = [_case("only__case__here", "NORMAL")]
    generator = StubGenerator(cases)
    reproduction = run_fuzz_smoke(
        runner=generator,
        source_root=_source_root(tmp_path),
        out_dir=tmp_path / "cases",
        timeout_seconds=60,
    )
    assert [case.case_id for case in reproduction.cases] == ["only__case__here"]
    assert reproduction.planned == 1
    assert reproduction.exit_code == 0
    assert reproduction.early_stop is False
