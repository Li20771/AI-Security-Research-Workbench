"""Workspace containment (contract §10).

**There is no discovery here.** No upward search, no sibling scan, no `.git`
hunt, no registry lookup, no inference from the current working directory. A
root that was not declared does not exist as far as AI-06 is concerned (§10.2).

Containment is checked **by resolution, not by string inspection** (§10.3). The
resolution itself is AI-03's `is_inside`, reused rather than reimplemented: that
function already exists, already resolves symlinks before comparing, and is
already the Workbench's answer to this question. A second implementation would
be a second place for the answer to drift.
"""

from __future__ import annotations

from pathlib import Path

from plugins.context.workspace import canonical_root, is_inside

from plugins.security_tools.errors import PathEscapesWorkspace, WorkspaceUnresolvable

__all__ = ["resolve_root", "contained_path"]


def resolve_root(root: str | None) -> Path:
    """The declared root, or a refusal (contract §10.2).

    A missing root is refused rather than defaulted. There is no "the current
    directory will do": that is the inference §10.2 exists to forbid.
    """
    if root is None:
        raise WorkspaceUnresolvable(
            "this operation needs a workspace root and the request declared none "
            "(§10.2). The root is declared, never discovered"
        )
    try:
        canonical = canonical_root(root)
    except OSError:
        raise WorkspaceUnresolvable("the declared workspace root cannot be reached") from None
    if not canonical.is_dir():
        raise WorkspaceUnresolvable("the declared workspace root is not a directory")
    return canonical


def contained_path(root: Path, candidate: str) -> Path:
    """Resolve `candidate` under `root`, refusing anything that escapes.

    Relative paths resolve against the root. Absolute paths are permitted only
    when they resolve inside it. A path that escapes — by `..`, by an absolute
    form, or by a symlink — is refused, and the refusal happens here rather than
    after the operation has already read something.
    """
    if not isinstance(candidate, str) or not candidate:
        raise PathEscapesWorkspace("a path must be a non-empty string")
    raw = Path(candidate)
    joined = raw if raw.is_absolute() else root / raw
    try:
        resolved = joined.resolve()
    except OSError:
        raise PathEscapesWorkspace("the path cannot be resolved") from None
    if not is_inside(root, resolved):
        raise PathEscapesWorkspace(
            "a path in this operation resolves outside the declared workspace "
            "root (§10.3). Containment is checked by resolution, so a symlink "
            "pointing out of the workspace is refused with a `..`"
        )
    return resolved
