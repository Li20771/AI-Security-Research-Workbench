"""AI-11 §5.4, §15.3, §16 — declared paths, and the boundary they must not cross.

A `workspace_setup` path is DECLARED MATERIAL. It is reviewed, but it is also data, and
data that names a location is data that can name the wrong one.

```text
include     resolves under the root it came from — the source tree, or the corpus
exclude     a pattern, matched inside the agent-visible tree
generated   resolves under the setup area, and is copied to a destination under the
            agent-visible tree
```

### Why this is a module and not four `startswith` calls

`startswith` compares STRINGS. `/scratch/ws-evil`.startswith(`/scratch/ws`) is True, and
so is `C:\\ws-other` against `C:\\ws`. Neither is inside the root, and both pass a string
test. The check has to compare RESOLVED PATHS:

```text
    candidate = (root / relative).resolve()
    candidate.relative_to(root.resolve())     # raises ValueError when outside
```

`resolve()` normalises `..`, follows symlinks and canonicalises case on Windows, so the
comparison is made on where the path actually LANDS rather than on how it is spelled.

### The two platform notations

Declared paths are POSIX-style and relative, on every host. A backslash is refused rather
than translated: on Windows `a\\..\\b` and on POSIX `a\\..\\b` are different strings, and
a validator that guessed which one the author meant would be a validator with two
behaviours. Absolute paths, drive letters and UNC prefixes are refused for the same
reason — there is no correct root for them to be relative to.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from benchmarks.errors import WorkspaceDerivationError

__all__ = [
    "WINDOWS_DRIVE_RE",
    "resolve_within",
    "validate_exclude_pattern",
    "validate_relative_path",
]

#: `C:`, `c:` and `C:/` — a drive-qualified path, refused on every platform.
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")

#: Characters that make a path a GLOB rather than a literal. An `exclude` entry may
#: contain them; an `include` or `generated` entry may not, because those name one
#: thing that must exist.
_GLOB_CHARS = "*?["

MAX_PATH_CHARS = 512


def validate_relative_path(relative: object, *, where: str) -> str:
    """A declared path, or a refusal that names what is wrong with it."""
    if not isinstance(relative, str) or not relative:
        raise WorkspaceDerivationError(f"{where} must be a non-empty string")
    if len(relative) > MAX_PATH_CHARS:
        raise WorkspaceDerivationError(f"{where} must be at most {MAX_PATH_CHARS} characters")

    if "\n" in relative or "\r" in relative:
        raise WorkspaceDerivationError(f"{where} must be a single line")
    if "\\" in relative:
        raise WorkspaceDerivationError(
            f"{where} {relative!r} contains a backslash. Declared paths are POSIX-style "
            "relative paths on every host; a backslash is refused rather than "
            "translated, because the two platforms do not agree on what it means"
        )
    if relative.startswith("/"):
        raise WorkspaceDerivationError(
            f"{where} {relative!r} is an absolute path; a declared path is relative to a "
            "root the harness supplies, and there is no correct root for an absolute one"
        )
    if relative.startswith("//"):
        raise WorkspaceDerivationError(f"{where} {relative!r} is a UNC path")
    if WINDOWS_DRIVE_RE.match(relative):
        raise WorkspaceDerivationError(
            f"{where} {relative!r} is drive-qualified; a declared path is relative"
        )

    parts = PurePosixPath(relative).parts
    if not parts:
        raise WorkspaceDerivationError(f"{where} {relative!r} names nothing")
    for part in parts:
        if part == "..":
            raise WorkspaceDerivationError(
                f"{where} {relative!r} contains a '..' segment. A declared path MUST NOT "
                "be able to leave the root it is resolved against (§15.3, §16)"
            )
        if part == ".":
            raise WorkspaceDerivationError(
                f"{where} {relative!r} contains a '.' segment; the path is already "
                "relative and the segment only makes it harder to read"
            )
        if part == "":
            raise WorkspaceDerivationError(f"{where} {relative!r} contains an empty segment")

    return PurePosixPath(relative).as_posix()


def validate_exclude_pattern(pattern: object, *, where: str) -> str:
    """An `exclude` entry. The same rules, plus glob characters are permitted.

    A glob is still a relative path: `../*` is refused, and so is `/etc/*`.
    """
    if not isinstance(pattern, str) or not pattern:
        raise WorkspaceDerivationError(f"{where} must be a non-empty string")
    if "\\" in pattern:
        raise WorkspaceDerivationError(f"{where} {pattern!r} contains a backslash")
    if pattern.startswith("/") or WINDOWS_DRIVE_RE.match(pattern):
        raise WorkspaceDerivationError(
            f"{where} {pattern!r} is absolute; an exclude entry is relative to the "
            "agent-visible tree"
        )
    for part in PurePosixPath(pattern).parts:
        if part == "..":
            raise WorkspaceDerivationError(
                f"{where} {pattern!r} contains a '..' segment; an exclude pattern MUST "
                "NOT be able to reach outside the workspace it is checked against"
            )
    return pattern


def resolve_within(root: str | Path, relative: str, *, where: str) -> Path:
    """Resolve a declared path and assert it LANDS inside `root`.

    ```text
    FROZEN: the comparison is made on resolved paths, never on string prefixes.
            `/scratch/ws-evil` shares a string prefix with `/scratch/ws` and is not
            inside it.
    ```

    A path that resolves outside its root is refused, not clamped. Clamping would run
    the task against material the definition did not name, which is the failure this
    check exists to prevent.
    """
    validated = validate_relative_path(relative, where=where)
    root_resolved = Path(root).resolve()
    candidate = (root_resolved / validated).resolve()

    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise WorkspaceDerivationError(
            f"{where} {relative!r} resolves to {candidate}, which is outside {root_resolved}. "
            "A declared path MUST NOT leave the root it is resolved against"
        ) from exc

    return candidate


def has_glob(pattern: str) -> bool:
    """Whether an entry is a pattern rather than a literal path."""
    return any(char in pattern for char in _GLOB_CHARS)
