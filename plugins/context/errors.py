"""Context plugin error taxonomy.

Implements AI-03 contract §7.5. Every failure in this package is a typed,
inspectable condition rather than an escaping crash: a context build that
raised halfway through would tell its caller nothing about which source was
unreadable, and the caller would have no way to record the gap.

Two classes of failure are deliberately separated:

*Configuration and structure* -- a malformed manifest, a bad key, a workspace
mismatch. These are programming errors. They raise.

*A source that could not be read* -- missing, unreadable, refused, blocked.
These are **not** exceptions. They are recorded as a read status (contract
§5.7) and carried into the response, because a missing document is a fact
about the workspace, not a defect in the plugin.
"""

from __future__ import annotations


class ContextError(ValueError):
    """Base class for Context plugin failures."""


class WorkspaceError(ContextError):
    """A workspace could not be resolved."""


class ManifestError(ContextError):
    """A source manifest is malformed."""


class DeclarationError(ContextError):
    """A declaration could not be interpreted. Never raised for unparsed text."""


class CacheError(ContextError):
    """A cache key or entry is malformed."""


class ContainmentError(ContextError):
    """A source path escaped the workspace root (contract §6.3).

    Refusing the path is a recorded read status. Raising is reserved for a
    caller that asked for containment to be checked directly.
    """


class WorkspaceMismatchError(ContextError):
    """An item or source record belonged to a different workspace (contract §6).

    This is the one failure the plugin must never absorb. Merging two
    workspaces' context would produce a response that is wrong in a way no
    downstream consumer could detect, so it raises instead.
    """


class GitCommandRefused(ContextError):
    """A git command outside the frozen read-only set was attempted (§7.4)."""


__all__ = [
    "CacheError",
    "ContainmentError",
    "ContextError",
    "DeclarationError",
    "GitCommandRefused",
    "ManifestError",
    "WorkspaceError",
    "WorkspaceMismatchError",
]
