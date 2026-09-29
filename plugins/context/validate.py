"""Offline validation of the Context plugin.

Entry point for the CI validation step:

    python -m plugins.context.validate

Builds the context of this repository through the real pipeline and asserts the
invariants that must hold for **any** workspace, so a regression in the
classification or resolution path fails here rather than silently reaching a
consumer.

Everything checked here is structural. Nothing here asserts that any phase,
test, or capability of this repository has passed: that is a claim only an
executed check can make, and this module is not one.

Performs no network I/O and requires no credential. Read-only in git terms --
`SubprocessGitReader` refuses any command outside the frozen read set, so this
command cannot modify the repository it inspects.

Exit code 0 = all checks passed; 1 = at least one problem, printed to stderr.
"""

from __future__ import annotations

import sys
from pathlib import Path

from plugins.context.context import ContextResponse, build_context
from plugins.context.vocabulary import (
    ITEM_KIND_BY_SOURCE,
    ITEM_KIND_RANK,
    SOURCE_PRIORITY_ORDER,
    ContextStatus,
    ItemKind,
    SourcePriority,
    SourceReadStatus,
    StatusValue,
)
from plugins.context.workspace import is_inside

#: The AI-03 invariant that dominates the others: no code path may turn a
#: non-`PASS` declaration into a `PASS`. Checked by re-deriving it from the
#: response rather than by trusting the classifier.
TRUTH_STATES: frozenset[str] = frozenset({"PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN"})


def repository_root() -> Path:
    """The repository this package lives in."""
    return Path(__file__).resolve().parents[2]


def check_no_invented_pass(response: ContextResponse) -> list[str]:
    """A `PASS` truth state requires a literal `PASS` declaration."""
    problems: list[str] = []
    for item in response.items:
        if item.truth_state is StatusValue.PASS and item.declared_state != "PASS":
            problems.append(
                f"{item.subject}: truth_state PASS with declared_state "
                f"{item.declared_state!r}; a PASS may only be read, never derived"
            )
    return problems


def check_kinds_are_not_promoted(response: ContextResponse) -> list[str]:
    """Every item's kind matches its source's declared kind."""
    problems: list[str] = []
    for item in response.items:
        expected = ITEM_KIND_BY_SOURCE[item.source_kind]
        if item.item_kind is not expected:
            problems.append(
                f"{item.subject}: source {item.source_kind} implies {expected} but "
                f"the item is {item.item_kind}"
            )
    return problems


def check_facts_are_facts(response: ContextResponse) -> list[str]:
    """`facts` contains FACT items only, and no item is in two lists."""
    problems: list[str] = []
    for item in response.facts:
        if item.item_kind is not ItemKind.FACT:
            problems.append(f"{item.subject}: non-FACT item in facts")
    for name, items in (("history", response.history), ("plans", response.plans)):
        for item in items:
            if item.item_kind is ItemKind.FACT:
                problems.append(f"{item.subject}: FACT item in {name}")

    listed = len(response.facts) + len(response.history) + len(response.plans)
    if listed != len(response.items):
        problems.append("an item appears in more than one item list")
    return problems


def check_workspace_containment(response: ContextResponse) -> list[str]:
    """No source reached outside the workspace it was read for."""
    problems: list[str] = []
    root = Path(response.workspace.workspace_root)
    for record in response.sources:
        if record.workspace_id != response.workspace.workspace_id:
            problems.append(
                f"{record.source_identity}: source belongs to workspace "
                f"{record.workspace_id!r}, not {response.workspace.workspace_id!r}"
            )
        # Only path-shaped identities are checkable; git identities are not paths.
        if "/" in record.source_identity and not is_inside(root, root / record.source_identity):
            problems.append(
                f"{record.source_identity}: resolves outside {response.workspace.workspace_root}"
            )
    return problems


def check_single_workspace(response: ContextResponse) -> list[str]:
    """A response describes exactly one workspace identity (contract §6.4)."""
    identities = {response.workspace.workspace_id}
    identities.update(item.workspace_id for item in response.items)
    identities.update(record.workspace_id for record in response.sources)
    if len(identities) != 1:
        return [f"response spans {len(identities)} workspaces: {sorted(identities)}"]
    return []


def check_priority_table_is_frozen() -> list[str]:
    """The §5.3 priority table is the frozen one, in the frozen order."""
    problems: list[str] = []
    expected = [
        "git_current_state",
        "master_roadmap",
        "capability_inventory",
        "design_freeze",
        "exit_report",
        "git_history",
    ]
    actual = [str(kind) for kind in SOURCE_PRIORITY_ORDER]
    if actual != expected:
        problems.append(f"source priority order is {actual}, expected {expected}")

    for rank, kind in enumerate(SOURCE_PRIORITY_ORDER):
        priority = SourcePriority(rank)
        if kind.name != priority.name:
            problems.append(
                f"{kind} has rank {rank} but the enum member there is {priority.name}"
            )

    for kind, rank in ITEM_KIND_RANK.items():
        if rank not in (0, 1, 2):
            problems.append(f"{kind} has an out-of-range conflict rank {rank}")
    return problems


def check_read_statuses_are_honest(response: ContextResponse) -> list[str]:
    """A source that was not read carries no items and no revision."""
    problems: list[str] = []
    counts: dict[tuple[str, str], int] = {}
    for item in response.items:
        key = (str(item.source_kind), item.source_identity)
        counts[key] = counts.get(key, 0) + 1

    for record in response.sources:
        key = (str(record.source_kind), record.source_identity)
        if record.read_status is not SourceReadStatus.READ:
            if record.item_count:
                problems.append(
                    f"{record.source_identity}: {record.read_status} with "
                    f"{record.item_count} items; an unread source has no content"
                )
            if record.source_revision is not None:
                problems.append(
                    f"{record.source_identity}: {record.read_status} with a revision"
                )
        if counts.get(key, 0) != record.item_count:
            problems.append(
                f"{record.source_identity}: record says {record.item_count} items, "
                f"response holds {counts.get(key, 0)}"
            )
    return problems


def check_uncacheable_live_state(response: ContextResponse) -> list[str]:
    """The live-state source is never served from cache (D-14)."""
    problems: list[str] = []
    for record in response.sources:
        if record.source_kind.value == "git_current_state" and record.cache_hit:
            problems.append(
                "git_current_state was served from cache; it is uncacheable by "
                "design because no cheap probe captures the working tree"
            )
    return problems


def validate_all(root: Path | None = None) -> list[str]:
    """Run every check. Returns an empty list when all pass."""
    problems: list[str] = []
    target = repository_root() if root is None else root

    response = build_context(target)

    problems.extend(check_priority_table_is_frozen())
    problems.extend(check_no_invented_pass(response))
    problems.extend(check_kinds_are_not_promoted(response))
    problems.extend(check_facts_are_facts(response))
    problems.extend(check_workspace_containment(response))
    problems.extend(check_single_workspace(response))
    problems.extend(check_read_statuses_are_honest(response))
    problems.extend(check_uncacheable_live_state(response))

    if response.status is ContextStatus.UNKNOWN:
        problems.append(
            "no source could be read; the context is UNKNOWN rather than empty"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]) if argv else repository_root()
    problems = validate_all(root)

    if problems:
        print("context validation: FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    response = build_context(root)
    workspace = response.workspace
    print("context validation: PASS")
    print(f"  workspace: {workspace.workspace_id}")
    print(f"  branch: {workspace.branch}  head: {workspace.commit}")
    print(f"  working tree: {workspace.working_tree}")
    print(f"  status: {response.status}")
    print(
        f"  items: {len(response.facts)} fact, {len(response.history)} history, "
        f"{len(response.plans)} plan"
    )
    print(f"  conflicts: {len(response.conflicts)}")
    print(f"  sources: {len(response.sources)}")
    for record in response.sources:
        marker = " (cache)" if record.cache_hit else ""
        print(
            f"    - {record.source_kind}:{record.source_identity} "
            f"[{record.read_status}] {record.item_count} item(s){marker}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
