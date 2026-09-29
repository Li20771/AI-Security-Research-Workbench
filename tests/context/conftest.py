"""Shared fixtures for the AI-03 context tests.

Two seams make the suite offline and deterministic without weakening it:

* `FakeGitReader` answers git queries from a table, so workspace resolution,
  source reading and cache behaviour are exercised without a repository.
* `throwaway_repo` creates a **real** repository, so the one test that must show
  the resolver reads actual git state does so against actual git rather than
  against the fake that was written to agree with it.

No test requires a credential, a network, or a provider.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Sequence

import pytest

from plugins.context.sources import DocumentSource, HISTORY_COMMIT_LIMIT
from plugins.context.vocabulary import SourceKind
from plugins.context.workspace import GitResult

#: A syntactically valid commit-ish. Never a real SHA from any repository.
SAMPLE_SHA = "0" * 39 + "1"
OTHER_SHA = "0" * 39 + "2"


def ok(stdout: str = "") -> GitResult:
    return GitResult(returncode=0, stdout=stdout, stderr="")


def failed(stderr: str = "error", code: int = 128) -> GitResult:
    return GitResult(returncode=code, stdout="", stderr=stderr)


class FakeGitReader:
    """Answers git queries from a table. Never spawns a process.

    Overrides are keyed by `(root, args)`, so a single reader can describe two
    workspaces at once -- which is what the isolation tests need in order to
    prove that reading A cannot observe B.
    """

    def __init__(
        self,
        *,
        head: str | None = SAMPLE_SHA,
        branch: str | None = "main",
        porcelain: str = "",
        remote: str | None = "https://github.com/example/workspace.git",
        log: str = "",
        own_repository: bool = True,
    ) -> None:
        self.head = head
        self.branch = branch
        self.porcelain = porcelain
        self.remote = remote
        self.log = log
        #: When false, `--show-toplevel` reports a *different* directory, which
        #: is how git answers for a path inside someone else's repository.
        self.own_repository = own_repository
        self.overrides: dict[tuple[Path, tuple[str, ...]], GitResult] = {}
        self.calls: list[tuple[Path, tuple[str, ...]]] = []

    def set(self, root: Path, args: Sequence[str], result: GitResult) -> None:
        self.overrides[(Path(root), tuple(args))] = result

    def run(self, root: Path, args: Sequence[str]) -> GitResult:
        key = (Path(root), tuple(args))
        self.calls.append(key)
        if key in self.overrides:
            return self.overrides[key]

        command = args[0]
        if command == "rev-parse" and tuple(args) == ("rev-parse", "--show-toplevel"):
            # A real git reports the enclosing repository's top level, which for
            # a path inside a repository is not that path.
            if not self.own_repository:
                return ok(str(Path(root).parent))
            return ok(str(root))
        if command == "rev-parse":
            return ok(self.head) if self.head else failed("unknown revision")
        if command == "symbolic-ref":
            return ok(self.branch) if self.branch else failed("not a symbolic ref")
        if command == "status":
            return ok(self.porcelain)
        if command == "remote":
            return ok(self.remote) if self.remote else failed("no such remote")
        if command == "log":
            return ok(self.log)
        return failed(f"unhandled command {command!r}")

    @property
    def commands(self) -> list[str]:
        return [args[0] for _, args in self.calls]


def git_log_lines(entries: Iterable[tuple[str, str, str]]) -> str:
    """Render `(sha, committed_at, subject)` rows in the reader's log format."""
    return "\n".join("\x1f".join(entry) for entry in entries)


def declaration_document(*pairs: tuple[str, str], prose: str = "") -> str:
    """A document whose ```text block declares `key = VALUE` lines.

    Anything outside the fence is prose, and the extractor must ignore it --
    which is why the helper can add some.
    """
    body = "\n".join(f"{key} = {value}" for key, value in pairs)
    return f"# Fixture\n\n{prose}\n\n```text\n{body}\n```\n"


def write_document(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def document_manifest(*relative_paths: str, kind: SourceKind | str = SourceKind.EXIT_REPORT):
    """A manifest of document sources only — no git source, no network."""
    return tuple(
        DocumentSource(SourceKind(kind) if isinstance(kind, str) else kind, path)
        for path in relative_paths
    )


@pytest.fixture
def fake_git() -> FakeGitReader:
    return FakeGitReader()


@pytest.fixture
def workspace_a(tmp_path: Path) -> Path:
    """A workspace whose documents declare a distinctive state."""
    root = tmp_path / "workspace-a"
    root.mkdir()
    write_document(
        root,
        "docs/status.md",
        declaration_document(
            ("Working tree", "CLEAN"),
            ("Live provider execution", "NOT_RUN"),
        ),
    )
    return root


@pytest.fixture
def workspace_b(tmp_path: Path) -> Path:
    """A second workspace, distinct from A in content, path and identity."""
    root = tmp_path / "workspace-b"
    root.mkdir()
    write_document(
        root,
        "docs/status.md",
        declaration_document(
            ("Working tree", "DIRTY"),
            ("Live provider execution", "PASS"),
        ),
    )
    return root


def _git(args: Sequence[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
