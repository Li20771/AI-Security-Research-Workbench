"""AI-03 — Context Plugin.

Turns the verifiable, traceable context of one workspace into a structured
`ContextResponse` for later Workbench components to consume.

The plugin reports what a source declared. It never decides what is true:

```text
Source -> Normalize -> Classify -> Attach provenance -> Structured Context
```

and never:

```text
Source -> LLM -> "current truth"
```

Nothing here selects a model, ranks a source semantically, writes to git,
executes a tool, adjudicates evidence, or reads a second workspace. Those are
other components (AI-04 Guard, AI-05 Evidence, AI-06 Security Tools, AI-07
Router), and AI-07 in particular is **DEFERRED**.

The package's entry points:

    build_context(root)       the whole pipeline, one workspace
    resolve_workspace(root)   identity and current git state alone
    validate                  offline self-check, `python -m plugins.context.validate`

Contract: `docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md`.
"""

from __future__ import annotations

from plugins.context.cache import (
    CacheEntry,
    CacheKey,
    CacheLookup,
    CacheOutcome,
    InMemoryContextCache,
)
from plugins.context.classification import ContextItem, ItemRef, RawItem, classify
from plugins.context.context import (
    ContextResponse,
    FreshnessSummary,
    SourceRecord,
    assert_same_workspace,
    build_context,
    utc_now,
)
from plugins.context.errors import (
    CacheError,
    ContainmentError,
    ContextError,
    DeclarationError,
    GitCommandRefused,
    ManifestError,
    WorkspaceError,
    WorkspaceMismatchError,
)
from plugins.context.resolution import (
    SubjectResolution,
    apply_resolution,
    resolve_conflicts,
)
from plugins.context.sources import (
    DocumentSource,
    GitCurrentStateSource,
    GitHistorySource,
    SourceAdapter,
    SourceRead,
    build_manifest,
)
from plugins.context.vocabulary import (
    ContextStatus,
    Freshness,
    ItemKind,
    SourceKind,
    SourcePriority,
    SourceReadStatus,
    StatusValue,
    WorkingTreeState,
    truth_state_for_declaration,
)
from plugins.context.workspace import (
    GitReader,
    GitResult,
    SubprocessGitReader,
    WorkspaceIdentity,
    is_inside,
    resolve_workspace,
)

__all__ = [
    "CacheEntry",
    "CacheError",
    "CacheKey",
    "CacheLookup",
    "CacheOutcome",
    "ContainmentError",
    "ContextError",
    "ContextItem",
    "ContextResponse",
    "ContextStatus",
    "DeclarationError",
    "DocumentSource",
    "Freshness",
    "FreshnessSummary",
    "GitCommandRefused",
    "GitCurrentStateSource",
    "GitHistorySource",
    "GitReader",
    "GitResult",
    "InMemoryContextCache",
    "ItemKind",
    "ItemRef",
    "ManifestError",
    "RawItem",
    "SourceAdapter",
    "SourceKind",
    "SourcePriority",
    "SourceRead",
    "SourceReadStatus",
    "SourceRecord",
    "StatusValue",
    "SubjectResolution",
    "SubprocessGitReader",
    "WorkspaceError",
    "WorkspaceIdentity",
    "WorkspaceMismatchError",
    "WorkingTreeState",
    "apply_resolution",
    "assert_same_workspace",
    "build_context",
    "build_manifest",
    "classify",
    "is_inside",
    "resolve_conflicts",
    "resolve_workspace",
    "truth_state_for_declaration",
    "utc_now",
]
