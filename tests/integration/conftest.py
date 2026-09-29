"""Fixtures for the AI-03 integration tests.

These create **real** git repositories. Every other context test runs against a
table of canned git answers; these exist so that at least one module would still
fail if the production reader were wrong about how `git` actually behaves.

`-c user.email=... -c user.name=...` is passed per command rather than written
into a config file, so the tests do not read or write the host's git
configuration and do not depend on it being set.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

#: A placeholder identity. Never a real address, and never committed anywhere.
_GIT_IDENTITY = ("-c", "user.email=test@example.invalid", "-c", "user.name=Test")


def git(args: list[str], cwd: Path, *, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )
    return result.stdout


@pytest.fixture
def throwaway_repo(tmp_path: Path) -> Path:
    """A real repository with one empty commit, on branch `main`."""
    root = tmp_path / "real-repo"
    root.mkdir()
    git(["init", "-q", "-b", "main"], root)
    git([*_GIT_IDENTITY, "commit", "-q", "--allow-empty", "-m", "initial"], root)
    return root


@pytest.fixture
def commit_in(throwaway_repo: Path):
    """Commit into the throwaway repository. Returns the new HEAD."""

    def commit(
        message: str, *, filename: str | None = None, content: str = "x"
    ) -> str:
        if filename is None:
            args = [*_GIT_IDENTITY, "commit", "-q", "--allow-empty", "-m", message]
        else:
            (throwaway_repo / filename).write_text(content, encoding="utf-8")
            git(["add", filename], throwaway_repo)
            args = [*_GIT_IDENTITY, "commit", "-q", "-m", message]
        git(args, throwaway_repo)
        return git(["rev-parse", "HEAD"], throwaway_repo).strip()

    return commit


@pytest.fixture
def head_of(throwaway_repo: Path):
    """The repository's real HEAD, read with git rather than with our code."""

    def read(root: Path | None = None) -> str:
        target = throwaway_repo if root is None else root
        return git(["rev-parse", "HEAD"], target).strip()

    return read
