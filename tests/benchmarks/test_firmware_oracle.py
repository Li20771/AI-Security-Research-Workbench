"""AI-11 §7, §A.4 — the firmware oracle: the image is the observation. Layer 2.

The oracle for `ai11-v1-firmware-syn-ecu-inventory` does not read an answer out of a
fixture. The harness BUILDS an image, the oracle inspects THAT image with `binwalk` and
`unsquashfs`, and the submission is judged against what the image contains.

### The defect these tests exist for

`inspect_firmware()` read `version` from the extracted `config.ini`, and when the key was
absent it fell back to `/etc/banner`:

```python
version = values.get("version", "")
if not version:
    version = banner.read_text(encoding="utf-8").strip()
```

The pinned v1 image has no `version` key, and its banner is a BOOT banner:

```text
/etc/banner     "SYNTHETIC ECU boot banner - revision 1"
the program     "SYN-ECU v1.0"     compiled in, -DFW_VERSION_STR
tracked truth   "SYN-ECU v1.0"
```

So the oracle derived a value its own truth disagreed with, the self-check refused the
observation, and EVERY firmware run came back

```text
UNKNOWN / ORACLE_DERIVATION_DISAGREES:version
```

for the correct answer and for the incorrect one alike. An oracle that returns the same
verdict for both answers cannot discriminate, so the firmware task measured nothing. The
version now comes from the executable in the extracted image, which is where the build
put it.

### How these tests reach the image path without the toolchain

`binwalk`, `unsquashfs` and `mksquashfs` are external programs that are not on every
host, and the A.4 task does not declare them as anything but preconditions. The tests
below replace the SINGLE subprocess seam, `benchmarks.decoders._run`, with `StubTools`,
which reports the filesystem the test declares and stages the rootfs the test declares.
Everything downstream of that seam runs for real: the config read, the program-version
read, the collector, the self-check and the judge.

`test_F7` is the one that runs the REAL tools end to end, and it is NOT_RUN on a host
without them rather than passed.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import benchmarks.decoders as decoders
from benchmarks.decoders import InspectionUnavailable, inspect_firmware
from benchmarks.executor import ReferenceExecutor, ReferenceVariant
from benchmarks.oracles import collect, evaluate_submission, judge_submission
from benchmarks.task import load_task
from benchmarks.vocabulary import OracleVerdict

pytestmark = pytest.mark.layer2

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "tasks"
TASK_ID = "ai11-v1-firmware-syn-ecu-inventory"
ORACLE_ID = f"{TASK_ID}.oracle"

#: The pinned v1 boot banner. It is NOT the program version, and the whole point of the
#: defect is that the two were once treated as interchangeable.
V1_BANNER = "SYNTHETIC ECU boot banner - revision 1"

#: The program version the pinned `build_fw.sh` compiles into `usr/bin/ecu-demo` with
#: `-DFW_VERSION_STR`. Corroborated under `qemu-aarch64`: the program prints
#: `[SYN-ECU] boot: SYN-ECU v1.0`.
V1_PROGRAM_VERSION = "SYN-ECU v1.0"

V1_ADMIN_PASSWORD = "DemoPass!2024"


def _program(version: str) -> bytes:
    """A minimal ELF-shaped program carrying the version the build injects.

    The extraction rule under test is `ELF magic` + `a version string in the bytes`, so
    the fixture satisfies exactly that. A REAL compiled binary is exercised by `test_F7`
    against the real tools.
    """
    return b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 64 + f"[SYN-ECU] boot: {version}\n".encode()


def _rootfs(
    tmp_path: Path,
    *,
    program_version: str = V1_PROGRAM_VERSION,
    banner: str = V1_BANNER,
    config_version: str | None = None,
    with_program: bool = True,
) -> Path:
    """A rootfs with the pinned v1 shape: a program, a banner, and a config."""
    rootfs = tmp_path / "rootfs"
    (rootfs / "usr/bin").mkdir(parents=True)
    (rootfs / "etc/syn_ecu").mkdir(parents=True)
    if with_program:
        (rootfs / "usr/bin/ecu-demo").write_bytes(_program(program_version))
    (rootfs / "etc/banner").write_text(f"{banner}\n", encoding="utf-8")
    lines = [
        "# SYNTHETIC demo config - not real credentials",
        "device=syn-ecu-demo",
        "admin_user=admin",
        f"admin_password={V1_ADMIN_PASSWORD}",
    ]
    if config_version is not None:
        lines.append(f"version={config_version}")
    (rootfs / "etc/syn_ecu/config.ini").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rootfs


class StubTools:
    """The `_run` seam, replaced. **It is NOT binwalk and NOT unsquashfs.**

    It answers the two calls `inspect_firmware` makes and nothing else: `binwalk` reports
    a SquashFS/gzip image, and `unsquashfs` stages the rootfs the test declared. No other
    program is accepted, so a decoder that started shelling out to something new would
    fail here rather than quietly finding it absent.
    """

    def __init__(self, rootfs: Path) -> None:
        self.rootfs = rootfs
        self.calls: list[list[str]] = []

    def __call__(self, argv, *, timeout: int = 0):  # noqa: ANN001, ANN202
        args = list(argv)
        self.calls.append(args)
        if args[0] == "binwalk":
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    "DECIMAL       HEXADECIMAL     DESCRIPTION\n"
                    "0             0x0             Squashfs filesystem, little endian, "
                    "version 4.0, compression:gzip, size: 286720 bytes\n"
                ),
                stderr="",
            )
        if args[0] == "unsquashfs":
            # ["unsquashfs", "-f", "-d", <dir>, <image>]
            shutil.copytree(self.rootfs, Path(args[3]), dirs_exist_ok=True)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"the decoder invoked an undeclared program: {args[0]!r}")


def _stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rootfs: Path) -> Path:
    """A setup area holding one image, with the toolchain seam replaced."""
    setup = tmp_path / "setup"
    setup.mkdir(parents=True, exist_ok=True)
    (setup / "syn-ecu-v1.squashfs").write_bytes(b"staged by StubTools\n")
    monkeypatch.setattr(decoders, "_run", StubTools(rootfs))
    return setup


def _inspect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rootfs: Path):
    setup = _stage(tmp_path, monkeypatch, rootfs)
    return inspect_firmware(setup / "syn-ecu-v1.squashfs", extract_to=tmp_path / "extracted")


def _evaluate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rootfs: Path, variant):
    setup = _stage(tmp_path, monkeypatch, rootfs)
    task = load_task(CORPUS_ROOT / TASK_ID / "task.yaml")
    executor = ReferenceExecutor(task, CORPUS_ROOT)
    return evaluate_submission(
        oracle_id=task.oracle.oracle_id,
        required=task.oracle.required,
        submission=executor.produce(variant).payload,
        truth=executor.truth(),
        control_dir=executor.control,
        setup_dir=setup,
    )


def _assert_the_program_version_is_observed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rootfs: Path
) -> None:
    """The focused assertion. F5 reinstates the banner fallback and requires this to fail."""
    derived = _inspect(tmp_path, monkeypatch, rootfs)
    banner = (rootfs / "etc/banner").read_text(encoding="utf-8").strip()

    assert derived["version"] == V1_PROGRAM_VERSION
    assert derived["version"] != banner, (
        "the observed version is the boot banner. The banner is not the program "
        "version: the program is compiled with -DFW_VERSION_STR and the banner is a "
        "separate string written by the same script"
    )
    assert derived["filesystem"] == "squashfs"
    assert derived["compression"] == "gzip"
    assert derived["admin_password"] == V1_ADMIN_PASSWORD


# ---------------------------------------------------------------------------
# F1 — the banner is not the program version
# ---------------------------------------------------------------------------


def test_F1_the_version_comes_from_the_program_not_from_the_boot_banner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect itself, as one assertion.

    The image carries a banner reading `revision 1` and a program reporting
    `SYN-ECU v1.0`. Only one of those is the program version, and it is the one the
    tracked truth names.
    """
    _assert_the_program_version_is_observed(tmp_path, monkeypatch, _rootfs(tmp_path))


def test_F1b_a_banner_that_looks_like_a_version_is_still_not_the_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even a banner that spells a version is not the program's version.

    A synthetic image whose banner carries a version-looking string: the observed value
    must still come from the executable. A reader that preferred whichever string was
    found first would answer with the banner here.
    """
    rootfs = _rootfs(tmp_path, banner="SYN-ECU v9.9", program_version="SYN-ECU v1.0")
    derived = _inspect(tmp_path, monkeypatch, rootfs)
    assert derived["version"] == "SYN-ECU v1.0"


# ---------------------------------------------------------------------------
# F2 — the config has no version key, and needs none
# ---------------------------------------------------------------------------


def test_F2_no_version_key_in_the_config_is_not_an_obstacle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pinned v1 config really has no `version=` line, and the oracle needs none."""
    rootfs = _rootfs(tmp_path)
    config = (rootfs / "etc/syn_ecu/config.ini").read_text(encoding="utf-8")
    assert "version" not in config, "the fixture must have the pinned v1 shape"

    derived = _inspect(tmp_path, monkeypatch, rootfs)
    assert derived["version"] == V1_PROGRAM_VERSION


def test_F2b_a_config_version_does_not_override_the_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """There is ONE source for the version, and it is the program.

    A config that disagreed with the executable would otherwise be a second answer to
    the same question, and which one won would depend on the order of two reads.
    """
    rootfs = _rootfs(tmp_path, config_version="SYN-ECU v0.1-config")
    derived = _inspect(tmp_path, monkeypatch, rootfs)
    assert derived["version"] == V1_PROGRAM_VERSION


# ---------------------------------------------------------------------------
# F3/F4 — the discrimination the defect destroyed
# ---------------------------------------------------------------------------


def test_F3_the_correct_answer_is_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`known_good` against a v1 image: PASS, with every required check executed.

    This is the result the defect made unreachable. It is asserted through
    `evaluate_submission` — the collector, the self-check and the judge — against the
    corpus's own truth and control, not a hand-built observation.
    """
    rootfs = _rootfs(tmp_path)
    result = _evaluate(tmp_path, monkeypatch, rootfs, ReferenceVariant.KNOWN_GOOD)

    assert result.verdict is OracleVerdict.PASS, result.reason_code
    assert result.tests.planned == 4
    assert result.tests.executed == result.tests.planned
    assert result.tests.passed == 4
    assert result.tests.failed == 0
    assert result.tests.skipped == 0


def test_F4_the_wrong_answer_is_fail_and_not_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`known_bad` against the SAME v1 image: FAIL — the oracle can discriminate again.

    The negative control is an ANSWER VARIANT, not a second image: it differs on
    `version` and `admin_password`, and both differences must be caught by comparing
    them against what the image actually contains.

    Before the fix this run was `UNKNOWN / ORACLE_DERIVATION_DISAGREES:version` — the
    same verdict as the correct answer, which is the definition of an oracle that cannot
    discriminate.
    """
    rootfs = _rootfs(tmp_path)
    result = _evaluate(tmp_path, monkeypatch, rootfs, ReferenceVariant.KNOWN_BAD)

    assert result.verdict is OracleVerdict.FAIL, result.reason_code
    assert result.verdict is not OracleVerdict.PASS
    assert result.verdict is not OracleVerdict.UNKNOWN
    assert "ORACLE_DERIVATION_DISAGREES" not in result.reason_code, (
        "the oracle's own derivation disagreed with its truth again; the observation "
        "is not usable and no submission was really judged"
    )
    assert result.tests.failed == 2, "the two fields the negative control differs on"
    assert result.tests.executed == result.tests.planned == 4


def test_F4b_the_two_controls_do_not_receive_the_same_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§7.4, stated directly. An oracle that answers the same for both is not one."""
    good = _evaluate(tmp_path, monkeypatch, _rootfs(tmp_path / "g"), ReferenceVariant.KNOWN_GOOD)
    bad = _evaluate(tmp_path, monkeypatch, _rootfs(tmp_path / "b"), ReferenceVariant.KNOWN_BAD)

    assert good.verdict is not bad.verdict
    assert good.verdict is OracleVerdict.PASS
    assert bad.verdict is OracleVerdict.FAIL


# ---------------------------------------------------------------------------
# F5 — the banner fallback cannot come back unnoticed
# ---------------------------------------------------------------------------


def test_F5_the_banner_fallback_is_falsifiable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reinstate the defect and require the focused assertion to fail.

    `_program_version` is replaced with exactly what the decoder used to do — read
    `/etc/banner` — and the assertion F1 makes must break. If it still passed, F1 would
    be a test that cannot detect the defect it was written for.
    """
    rootfs = _rootfs(tmp_path)
    _assert_the_program_version_is_observed(tmp_path / "control-run", monkeypatch, rootfs)

    def banner_era(extracted: Path) -> str:
        banner = Path(extracted) / "etc/banner"
        return banner.read_text(encoding="utf-8").strip() if banner.is_file() else ""

    monkeypatch.setattr(decoders, "_program_version", banner_era)
    with pytest.raises(AssertionError):
        _assert_the_program_version_is_observed(tmp_path / "mutated", monkeypatch, rootfs)

    # And end to end: with the old reading back, the correct answer stops passing.
    result = _evaluate(tmp_path / "judged", monkeypatch, rootfs, ReferenceVariant.KNOWN_GOOD)
    assert result.verdict is OracleVerdict.UNKNOWN
    assert "ORACLE_DERIVATION_DISAGREES:version" in result.reason_code


# ---------------------------------------------------------------------------
# F6 — the observation never reads the truth
# ---------------------------------------------------------------------------


def test_F6_the_derived_version_ignores_the_truth_it_is_judged_against(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A truth that disagrees with the image must not move the observation.

    The classification for this defect was ORACLE_DEFECT, not TRUTH_DEFECT, and this is
    what separates the two: the derived value is what the image contains. A decoder that
    read the truth would return `SYN-ECU v9.9` here, agree with itself, and pass.
    """
    rootfs = _rootfs(tmp_path)
    setup = _stage(tmp_path, monkeypatch, rootfs)

    task = load_task(CORPUS_ROOT / TASK_ID / "task.yaml")
    executor = ReferenceExecutor(task, CORPUS_ROOT)
    doctored = {
        "expected": {
            "filesystem": "squashfs",
            "compression": "gzip",
            "version": "SYN-ECU v9.9",
            "admin_password": V1_ADMIN_PASSWORD,
        }
    }

    observation = collect(
        ORACLE_ID,
        executor.produce(ReferenceVariant.KNOWN_GOOD).payload,
        doctored,
        control_dir=executor.control,
        setup_dir=setup,
    )
    assert observation.values["derived"]["version"] == V1_PROGRAM_VERSION

    judgement = judge_submission(ORACLE_ID, observation.values, doctored)
    assert judgement.verdict is OracleVerdict.UNKNOWN, (
        "a derivation that agreed with a doctored truth would mean the decoder read it"
    )
    assert "version" in judgement.reason_code


def test_F6b_no_path_in_the_decoder_can_reach_a_banner_or_a_truth_file() -> None:
    """The prohibition, as a property of the paths the module can name.

    A fallback needs somewhere to read from, and reading from somewhere means naming a
    path: `/etc/banner`, or a `truth.json` under the control directory. Docstrings and
    diagnostic prose are excluded — explaining what is refused is not doing it, and this
    module's own failure messages say so on purpose, to tell an operator what NOT to
    substitute.

    So the check is on PATH-shaped literals only: any literal containing a separator.
    """
    source = Path(decoders.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body[0].value.value = ""  # a docstring is not a path the code can open

    paths = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and ("/" in node.value or "\\" in node.value)
    ]
    for forbidden in ("banner", "truth", "known_good", "known_bad"):
        offenders = [text for text in paths if forbidden in text.lower()]
        assert not offenders, (
            f"decoders.py names a path containing {forbidden!r}: {offenders}. The "
            "version comes from a program in the image, and nothing else"
        )


# ---------------------------------------------------------------------------
# F7 — the honest failure path, and the real toolchain
# ---------------------------------------------------------------------------


def test_F7a_an_image_with_no_program_version_is_unavailable_not_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No program version means no observation — never `""`, never the banner.

    `InspectionUnavailable` is §8.2's "we could not look": the collector turns it into
    BLOCKED. A fabricated value would instead be compared against the truth and produce
    a FAIL, blaming a submission for something the image did not contain.
    """
    rootfs = _rootfs(tmp_path, with_program=False)
    with pytest.raises(InspectionUnavailable) as raised:
        _inspect(tmp_path, monkeypatch, rootfs)
    assert raised.value.reason_code == "PROGRAM_VERSION_ABSENT"

    # And through the production path: BLOCKED, never PASS and never FAIL.
    result = _evaluate(
        tmp_path / "blocked", monkeypatch, _rootfs(tmp_path / "blocked" / "m", with_program=False),
        ReferenceVariant.KNOWN_GOOD,
    )
    assert result.verdict is OracleVerdict.BLOCKED, result.reason_code
    assert result.verdict is not OracleVerdict.PASS
    assert result.verdict is not OracleVerdict.FAIL


def test_F7b_two_programs_disagreeing_about_the_version_are_not_rounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two versions is not a fact to pick from. The observation is refused."""
    rootfs = _rootfs(tmp_path)
    (rootfs / "usr/bin/other-tool").write_bytes(_program("SYN-ECU v2.0"))

    with pytest.raises(InspectionUnavailable) as raised:
        _inspect(tmp_path, monkeypatch, rootfs)
    assert raised.value.reason_code == "PROGRAM_VERSION_AMBIGUOUS"


def _squashfs_tools_available() -> bool:
    return all(shutil.which(tool) for tool in ("mksquashfs", "unsquashfs", "binwalk"))


@pytest.mark.skipif(
    not _squashfs_tools_available(),
    reason=(
        "mksquashfs/unsquashfs/binwalk are not on PATH. The stubs above exercise the "
        "machinery; this test is the one that settles whether a REAL squashfs image "
        "round-trips the program version, and it is NOT_RUN here rather than passed"
    ),
)
def test_F7c_the_real_toolchain_round_trips_the_program_version(tmp_path: Path) -> None:
    """The only test here that runs the real tools over a real image.

    A real SquashFS image is built from the same rootfs shape the pinned `build_fw.sh`
    produces, then inspected by the real `binwalk` and `unsquashfs` through the real
    decoder. It needs no source checkout, so the image-inspection architecture is
    verified on its own terms.
    """
    rootfs = _rootfs(tmp_path)
    image = tmp_path / "syn-ecu-v1.squashfs"
    subprocess.run(  # noqa: S603 - argv, no shell
        ["mksquashfs", str(rootfs), str(image), "-noappend", "-no-progress", "-comp", "gzip"],
        capture_output=True, text=True, check=True,
    )

    derived = inspect_firmware(image, extract_to=tmp_path / "extracted-real")
    assert derived["filesystem"] == "squashfs"
    assert derived["compression"] == "gzip"
    assert derived["version"] == V1_PROGRAM_VERSION
    assert derived["admin_password"] == V1_ADMIN_PASSWORD
