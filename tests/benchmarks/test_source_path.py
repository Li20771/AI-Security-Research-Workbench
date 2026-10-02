"""AI-11 §5.3, §15.2 — the source path, and the rule that an invalid one is refused.

An earlier revision accepted any string as `--source`. An unusable path reached
`subprocess` as a `cwd` and raised `NotADirectoryError`, which is neither a
`BenchmarkError` nor a `CampaignError`, so it escaped both handlers as a bare traceback.

The process still exited non-zero, so it was never a fake success — but a refusal a
caller cannot catch is not the honest answer this repository gives anywhere else, and
`invalid source != successful campaign` should be structural rather than incidental.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.errors import WorkspaceDerivationError
from benchmarks.runner import execute_task
from benchmarks.run import new_run_id
from benchmarks.task import load_corpus
from benchmarks.vocabulary import OracleVerdict
from benchmarks.workspace import validate_source_root

pytestmark = pytest.mark.layer2

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "tasks"


@pytest.fixture(scope="module")
def can_task():
    return next(t for t in load_corpus(CORPUS_ROOT) if t.task_id == "ai11-v1-can-dbc-decode")


def _run(task, source_root: Path, tmp_path: Path):
    return execute_task(
        task=task,
        corpus_root=CORPUS_ROOT,
        source_root=source_root,
        scratch_root=tmp_path / "scratch",
        run_id=new_run_id("0123456789abcdef"),
    ).run


# ---------------------------------------------------------------------------
# P1 — what validate_source_root admits
# ---------------------------------------------------------------------------


def test_P1_a_real_directory_is_admitted(tmp_path: Path) -> None:
    assert validate_source_root(tmp_path) == tmp_path


def test_P2_a_posix_form_that_the_shell_already_converted_is_admitted(tmp_path: Path) -> None:
    """The form Git Bash hands to Python: `--source /d/SecurityLab` arrives as
    `D:/SecurityLab`, a normal Windows path. It must pass.

    This is the whole explanation of the earlier "exit 0" observation: MSYS2 rewrites a
    POSIX-looking ARGUMENT before Python sees it. Nothing swallowed an error and the run
    was real. A Python LITERAL `'/d/SecurityLab'` is a different string — see P5.
    """
    assert validate_source_root(str(tmp_path)) == tmp_path


def test_P3_a_nonexistent_path_is_refused(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        validate_source_root(tmp_path / "nope")
    assert "does not exist" in str(excinfo.value)


def test_P4_a_file_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "a-file"
    target.write_text("not a repository\n", encoding="utf-8")
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        validate_source_root(target)
    assert "not a directory" in str(excinfo.value)


def test_P5_the_unconverted_windows_form_is_refused(tmp_path: Path) -> None:
    """`/d/SecurityLab` as a PYTHON string is `\\d\\SecurityLab` on Windows.

    That is `D:\\d\\SecurityLab`, which is not the repository. From PowerShell or cmd,
    with no shell conversion, this is what reaches Python — and it must be refused by
    name rather than by an escaping `NotADirectoryError`.
    """
    candidate = Path("/d/SecurityLab")
    if candidate.is_dir():  # pragma: no cover - a host where that really is the repo
        pytest.skip("on this host /d/SecurityLab is a real directory")
    with pytest.raises(WorkspaceDerivationError) as excinfo:
        validate_source_root(candidate)
    assert "does not exist" in str(excinfo.value)


# ---------------------------------------------------------------------------
# P6 — an invalid source never produces a successful run
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["missing", "file", "unconverted"])
def test_P6_no_successful_run_from_an_invalid_source(
    can_task, tmp_path: Path, kind: str
) -> None:
    if kind == "missing":
        source = tmp_path / "nope"
    elif kind == "file":
        source = tmp_path / "a-file"
        source.write_text("x\n", encoding="utf-8")
    else:
        source = Path("/d/SecurityLab")
        if source.is_dir():  # pragma: no cover
            pytest.skip("on this host /d/SecurityLab is a real directory")

    run = _run(can_task, source, tmp_path)

    assert run.task_status is OracleVerdict.BLOCKED, (
        f"an invalid source ({kind}) produced {run.task_status}"
    )
    assert run.task_status is not OracleVerdict.PASS
    assert run.task_status is not OracleVerdict.FAIL
    assert any("PRECONDITION_UNMET:source_root" in entry for entry in run.limitations), (
        f"the refusal is not named: {run.limitations}"
    )
    assert run.workspace_identity == {}, "an invalid source still derived a workspace"


def test_P7_the_refusal_is_catchable(can_task, tmp_path: Path) -> None:
    """A caller can catch it, which a bare NotADirectoryError made impossible."""
    from benchmarks.errors import BenchmarkError

    with pytest.raises(BenchmarkError):
        validate_source_root(tmp_path / "nope")


# ---------------------------------------------------------------------------
# P8 — a child's stderr is not silently lost
# ---------------------------------------------------------------------------


def test_P8_non_utf8_child_output_does_not_kill_the_reader(tmp_path: Path) -> None:
    """A byte outside UTF-8 used to kill the reader THREAD.

    `subprocess.run` returned normally and the exception surfaced only as a stray
    "Exception in thread" line, so the output was silently truncated — and a child's
    only failure signal could be lost that way.
    """
    import sys

    from benchmarks.runner import LocalProcessRunner

    emitted = LocalProcessRunner().run(
        [sys.executable, "-c",
         "import sys; sys.stderr.buffer.write(b'\\xff\\xfe bad bytes'); sys.stderr.flush()"],
        cwd=str(tmp_path),
        timeout_seconds=60,
    )
    assert emitted.exit_code == 0
    assert emitted.stderr, "the child's stderr was lost to a dead reader thread"
