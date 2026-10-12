"""Connection-change verification — AI-05 §7.3.13's baseline/candidate gate.

**WHAT THIS IS.** §7.3.13 splits its assertion over TWO trees. The BASELINE —
`origin/main` before the connecting change — must hold an EMPTY approved set
and an EMPTY observed set. The CANDIDATE — the tree that creates the call site
— must hold an observed set that EQUALS the approved set that change declares.
The baseline half "MUST BE RUN AS ITS OWN STEP", and the connecting change's
own report carries four recorded items: the ACTUAL base SHA, the baseline
call-site set, the ACTUAL head SHA, and the candidate set compared against the
declared approvals. A report that shows one tree has not shown two.

This module is that step. Given two tree roots it produces one report:

    the producer-authentication acceptance boundary, compared file by file
    the call-site identity change between the trees, by §7.3.13's six-field key
    the approved/unapproved difference — per tree, and across the delta

`PASS` means every check held. Everything else is a problem, and an unreadable
anything is a problem rather than a silence.

**WHAT THIS IS NOT — the limits are stated rather than overclaimed.**

```text
it is NOT a runtime barrier. It reads source text; no production path consults
  it, and it authorises nothing. §7.3.13 authorises no production caller, and
  the existence of this gate authorises none either.
it is NOT a git client. It compares TREES; the caller supplies them — typically
  a worktree of the base commit beside the candidate checkout — and supplies
  the commit ids the record carries. It cannot verify that a tree matches a
  commit, and it does not claim to; a recorded ref that is not a 40-hex commit
  shape is reported rather than believed.
it is NOT a completeness claim. It inherits callsite_identity's boundary:
  static scanning cannot establish the absence of arbitrary Python dynamic
  behaviour, and the blind-spot list there is transparency, not acceptance.
the boundary comparison is FILE IDENTITY, not semantics. Byte-identical is
  unchanged; different is REPORTED. Whether a boundary change is acceptable is
  the owners' judgement, not this gate's — which is why it fails loudly rather
  than silently absorbing one.
it adds NOTHING to §7.3.13's identity. The key is the six fields that section
  freezes — path, scope, entrypoint, callee, ast_path, fingerprint — compared
  through callsite_identity, never redefined here. `control_context` is an
  input to the fingerprint, `proof_kwarg` an independent acceptance condition,
  and `lineno` never part of the identity: all three stay exactly where that
  section puts them.
```

**WHY THE BOUNDARY IS COMPARED.** A connecting change creates a production call
site; it has no business touching the boundary that admits what the call site
submits. The files compared are the ones the frozen contract names as the
mechanism — the two entry points and the §30 step 7b call (`admission.py`),
the ONE designated reader (§7.3.11, `producer_auth.py`), §7.3.11's startup edge
(`plugins/evidence/__init__.py`) and §7.3.4's canonical signed input
(`signed_input.py`) — together with the two modules that enforce and execute
the acceptance itself: the §7.3.13 scanner (`callsite_identity.py`) and the
acceptance launcher (`trust_harness.py`). The approved-set declaration
(`test_producer_authentication.py`) is DELIBERATELY not in the set: the
connecting change edits it to declare its entries, and that diff IS the
approval artifact.

**WHICH CHANGE THIS GATES.** The default is §7.3.13's one-time gate: the
baseline must be pre-connection (empty, empty). The same section refuses "a
permanent emptiness requirement ... which would forbid the very connection the
obligation exists to permit", so a LATER change — one whose baseline is already
connected — runs with `require_pre_connection_baseline=False` and is still held
to per-tree equality and an exactly-declared delta. The flag is explicit at
every call site; nothing silently defaults a later change into the one-time
gate.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import pathlib
from dataclasses import dataclass

import callsite_identity
from callsite_identity import (
    CallSiteIdentity,
    ScanFailure,
    UnresolvedCall,
    findings,
    group_by_key,
    scan_tree,
)

__all__ = [
    "ACCEPTANCE_BOUNDARY_FILES",
    "APPROVED_DECLARATION_MODULE",
    "BoundaryFileState",
    "ConnectionChangeReport",
    "TreeState",
    "read_approved_keys",
    "verify_connection_change",
    "main",
]

#: §7.3.13's approved set is DECLARED in the acceptance module, and the diff
#: that adds an entry IS the approval artifact. Each tree's declaration is read
#: from this path — by reading and parsing, never by import, so a tree that
#: cannot be imported is still a tree that can be verified.
APPROVED_DECLARATION_MODULE = "tests/evidence/test_producer_authentication.py"

#: The producer-authentication acceptance boundary, as files. See the module
#: docstring for why each one is here and why the approved-set declaration is
#: not. A connecting change has no business touching any of these.
ACCEPTANCE_BOUNDARY_FILES: tuple[str, ...] = (
    "plugins/evidence/__init__.py",
    "plugins/evidence/admission.py",
    "plugins/evidence/producer_auth.py",
    "plugins/evidence/signed_input.py",
    "tests/evidence/callsite_identity.py",
    "tests/evidence/trust_harness.py",
)

#: §7.3.13's key is SIX string fields. An entry that is not six strings is not
#: an approval that can be read, and is reported rather than guessed at.
_KEY_FIELDS = 6

#: A full commit id, as §7.3.13's record requires ("the ACTUAL base SHA ... not
#: a branch name and not a remembered value"). This is a SHAPE check only: the
#: gate cannot verify that a tree matches a commit, and does not claim to.
_COMMIT_SHA_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class _ApprovedEntry:
    """A declared approval, viewed through the six fields of its key.

    `findings()` formats an approval it cannot observe from the VALUE's fields,
    so the shim carries the key's fields in the shape those messages use. It
    adds nothing to the identity and checks nothing: the approval IS the key.
    """

    path: str
    scope: str
    entrypoint: str
    callee: str
    ast_path: str
    fingerprint: str
    lineno: int = 0


@dataclass(frozen=True)
class TreeState:
    """One tree as the gate sees it: declared, observed, and its own problems.

    `observed` is the EFFECTIVE §7.3.13 set — the scanner's resolved production
    identities with the one pinned intra-package identity excluded from the
    delta view. Whether that exception legitimately applies AT ALL is
    `findings()`' decision and appears in `problems`, not in this set.
    """

    root: str
    ref: str | None
    observed: dict[tuple[str, str, str, str, str, str], CallSiteIdentity]
    unresolved: tuple[UnresolvedCall, ...]
    failures: tuple[ScanFailure, ...]
    approved: frozenset[tuple[str, str, str, str, str, str]]
    problems: tuple[str, ...]

    @property
    def pre_connection(self) -> bool:
        """§7.3.13's baseline shape: nothing approved, nothing observed."""
        return not self.approved and not self.observed


@dataclass(frozen=True)
class BoundaryFileState:
    """One boundary file's identity on both sides. `None` means unreadable."""

    path: str
    baseline_digest: str | None
    candidate_digest: str | None

    @property
    def unchanged(self) -> bool:
        return (
            self.baseline_digest is not None
            and self.candidate_digest is not None
            and self.baseline_digest == self.candidate_digest
        )


@dataclass(frozen=True)
class ConnectionChangeReport:
    """The two-tree comparison §7.3.13 obliges, with its verdict."""

    baseline: TreeState
    candidate: TreeState
    boundary: tuple[BoundaryFileState, ...]
    added: tuple[tuple[str, str, str, str, str, str], ...]
    removed: tuple[tuple[str, str, str, str, str, str], ...]
    changed_pairs: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]
    approved_added: frozenset[tuple[str, str, str, str, str, str]]
    approved_removed: frozenset[tuple[str, str, str, str, str, str]]
    problems: tuple[str, ...]

    @property
    def verdict(self) -> str:
        return "PASS" if not self.problems else "FAIL"

    def record_lines(self) -> list[str]:
        """§7.3.13's record: base SHA, baseline set, head SHA, candidate set."""

        def ref(value: str | None) -> str:
            if value is None:
                return (
                    "NOT RECORDED — §7.3.13 requires the ACTUAL commit, "
                    "not a branch name and not a remembered value"
                )
            return value

        def as_set(keys) -> str:
            if not keys:
                return "EMPTY"
            return "; ".join(format_identity(key) for key in sorted(keys))

        candidate_equal = set(self.candidate.observed) == set(self.candidate.approved)
        changed_boundary = [state.path for state in self.boundary if not state.unchanged]
        return [
            f"base SHA (baseline tree): {ref(self.baseline.ref)}",
            f"baseline production call-site set: {as_set(self.baseline.observed)} "
            f"(declared approved: {as_set(self.baseline.approved)}) — "
            f"§7.3.13's baseline is EMPTY, EMPTY",
            f"head SHA (candidate tree): {ref(self.candidate.ref)}",
            f"candidate production call-site set: {as_set(self.candidate.observed)} "
            f"(declared approved: {as_set(self.candidate.approved)}) — "
            f"equal: {'yes' if candidate_equal else 'NO'}",
            "acceptance boundary: "
            + ("UNCHANGED" if not changed_boundary else "CHANGED: " + ", ".join(changed_boundary)),
            f"verdict: {self.verdict}"
            + (f" ({len(self.problems)} problems)" if self.problems else ""),
        ]


def format_identity(key: tuple[str, ...]) -> str:
    """One identity, all six fields, on one line."""
    return (
        f"{key[0]} | scope={key[1]} | {key[2]} | callee={key[3]} "
        f"| ast_path={key[4]} | fingerprint={key[5]}"
    )


def read_approved_keys(root) -> tuple[frozenset, list[str]]:
    """The approved set a tree DECLARES, read from the declaration module.

    Fail-closed throughout: a declaration that cannot be read, cannot be found,
    is ambiguous, is not a dict literal, or carries an entry that is not a
    six-string key is a PROBLEM, never an empty set. An unreadable approval is
    an UNKNOWN approval, and unknown is not none.
    """
    path = pathlib.Path(root) / pathlib.Path(APPROVED_DECLARATION_MODULE)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return frozenset(), [
            f"APPROVED SET UNREADABLE: {APPROVED_DECLARATION_MODULE} — "
            f"{type(exc).__name__}: {exc}. A tree whose declaration cannot be "
            f"read has an UNKNOWN approved set, and unknown is not none"
        ]
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return frozenset(), [
            f"APPROVED SET UNREADABLE: {APPROVED_DECLARATION_MODULE} does not "
            f"parse — {type(exc).__name__}: {exc}"
        ]

    assignments: list[ast.expr] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target] if node.target is not None else []
            value = node.value
        else:
            continue
        if value is not None and any(
            isinstance(target, ast.Name) and target.id == "APPROVED_CALL_SITES"
            for target in targets
        ):
            assignments.append(value)

    if not assignments:
        return frozenset(), [
            f"APPROVED SET UNREADABLE: no module-level APPROVED_CALL_SITES "
            f"assignment in {APPROVED_DECLARATION_MODULE}. §7.3.13's approved "
            f"set is DECLARED, and a tree with no readable declaration has an "
            f"UNKNOWN approved set"
        ]
    if len(assignments) > 1:
        return frozenset(), [
            f"APPROVED SET UNREADABLE: {len(assignments)} module-level "
            f"APPROVED_CALL_SITES assignments in {APPROVED_DECLARATION_MODULE}; "
            f"which one governs cannot be determined"
        ]

    value = assignments[0]
    if not isinstance(value, ast.Dict):
        return frozenset(), [
            "APPROVED SET UNREADABLE: the APPROVED_CALL_SITES value is not a "
            "dict literal. An approval that must be computed cannot be read "
            "as an approval"
        ]

    keys: list[tuple[str, ...]] = []
    problems: list[str] = []
    for index, key_node in enumerate(value.keys):
        if key_node is None:
            problems.append(
                f"APPROVED ENTRY MALFORMED: entry {index} uses ** unpacking, "
                f"which is not a readable approval"
            )
            continue
        try:
            key = ast.literal_eval(key_node)
        except (ValueError, TypeError, SyntaxError) as exc:
            problems.append(
                f"APPROVED ENTRY MALFORMED: entry {index} is not a literal — "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        if not (
            isinstance(key, tuple)
            and len(key) == _KEY_FIELDS
            and all(isinstance(part, str) for part in key)
        ):
            problems.append(
                f"APPROVED ENTRY MALFORMED: entry {index} is not a "
                f"{_KEY_FIELDS}-string key — §7.3.13's key is (path, scope, "
                f"entrypoint, callee, ast_path, fingerprint)"
            )
            continue
        keys.append(key)
    return frozenset(keys), problems


def _digest(path: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _boundary(
    baseline_root: pathlib.Path, candidate_root: pathlib.Path
) -> tuple[tuple[BoundaryFileState, ...], list[str]]:
    states: list[BoundaryFileState] = []
    problems: list[str] = []
    for relative in ACCEPTANCE_BOUNDARY_FILES:
        baseline_digest = _digest(baseline_root / relative)
        candidate_digest = _digest(candidate_root / relative)
        states.append(BoundaryFileState(relative, baseline_digest, candidate_digest))
        if baseline_digest is None:
            problems.append(
                f"ACCEPTANCE BOUNDARY FILE MISSING: {relative} is unreadable "
                f"in the BASELINE tree"
            )
        if candidate_digest is None:
            problems.append(
                f"ACCEPTANCE BOUNDARY FILE MISSING: {relative} is unreadable "
                f"in the CANDIDATE tree"
            )
        if (
            baseline_digest is not None
            and candidate_digest is not None
            and baseline_digest != candidate_digest
        ):
            problems.append(
                f"ACCEPTANCE BOUNDARY CHANGED: {relative} (baseline sha256 "
                f"{baseline_digest[:16]}…, candidate sha256 "
                f"{candidate_digest[:16]}…). A connecting change has no "
                f"business touching the boundary that admits what it submits; "
                f"whether a change to it is acceptable is the owners' "
                f"judgement, not this gate's"
            )
    return tuple(states), problems


def _is_commit_sha(value: str) -> bool:
    return len(value) == 40 and all(char in _COMMIT_SHA_HEX for char in value.lower())


def _tree_state(root: pathlib.Path, ref: str | None) -> TreeState:
    """One tree's full §7.3.13 state: declaration, scan, per-tree assertion."""
    problems: list[str] = []
    approved, declaration_problems = read_approved_keys(root)
    problems.extend(declaration_problems)

    observed_calls, unresolved, failures = scan_tree(root, skip_paths=("tests",))
    approved_mapping = {key: _ApprovedEntry(*key) for key in approved}
    problems.extend(findings(observed_calls, approved_mapping, unresolved, failures))

    effective = {
        key: identity
        for key, identity in group_by_key(observed_calls).items()
        if key != callsite_identity.INTRA_PACKAGE_CALL_SITE
    }
    return TreeState(
        root=str(root),
        ref=ref,
        observed=effective,
        unresolved=tuple(unresolved),
        failures=tuple(failures),
        approved=approved,
        problems=tuple(problems),
    )


def verify_connection_change(
    baseline_root,
    candidate_root,
    *,
    baseline_ref: str | None = None,
    candidate_ref: str | None = None,
    require_pre_connection_baseline: bool = True,
) -> ConnectionChangeReport:
    """Compare a baseline tree against a candidate tree under §7.3.13.

    `baseline_root` and `candidate_root` are two trees — typically a worktree
    of the base commit and the candidate checkout; this function reads files
    and runs no git command. `baseline_ref` / `candidate_ref` are recorded
    verbatim in the report and must be full commit ids; a ref that is not one
    is a problem, because §7.3.13's record carries the ACTUAL commit and not a
    branch name.

    `require_pre_connection_baseline` is §7.3.13's one-time gate: the baseline
    must hold an EMPTY approved set and an EMPTY observed set. A LATER change,
    whose baseline is already connected, passes False — the section itself
    refuses a permanent emptiness requirement — and is still held to per-tree
    equality and an exactly-declared delta.
    """
    baseline_root = pathlib.Path(baseline_root)
    candidate_root = pathlib.Path(candidate_root)
    baseline = _tree_state(baseline_root, baseline_ref)
    candidate = _tree_state(candidate_root, candidate_ref)

    problems: list[str] = []
    problems.extend(f"BASELINE TREE: {problem}" for problem in baseline.problems)
    problems.extend(f"CANDIDATE TREE: {problem}" for problem in candidate.problems)

    for label, ref in (("baseline", baseline_ref), ("candidate", candidate_ref)):
        if ref is not None and not _is_commit_sha(ref):
            problems.append(
                f"RECORDED {label} REF IS NOT A COMMIT SHA: {ref!r}. §7.3.13's "
                f"record carries the ACTUAL commit — not a branch name and not "
                f"a remembered value"
            )

    boundary, boundary_problems = _boundary(baseline_root, candidate_root)
    problems.extend(boundary_problems)

    if require_pre_connection_baseline and not baseline.pre_connection:
        if baseline.approved:
            problems.append(
                f"BASELINE NOT PRE-CONNECTION: the baseline declares "
                f"{len(baseline.approved)} approved call site(s); §7.3.13's "
                f"baseline set is EMPTY"
            )
        if baseline.observed:
            problems.append(
                f"BASELINE NOT PRE-CONNECTION: {len(baseline.observed)} "
                f"production call site(s) observed on the baseline; §7.3.13's "
                f"baseline set is EMPTY"
            )

    added = tuple(sorted(set(candidate.observed) - set(baseline.observed)))
    removed = tuple(sorted(set(baseline.observed) - set(candidate.observed)))
    approved_added = frozenset(candidate.approved - baseline.approved)
    approved_removed = frozenset(baseline.approved - candidate.approved)

    def location(key: tuple[str, ...]) -> tuple[str, str, str]:
        return (key[0], key[1], key[2])

    changed_pairs = tuple(
        (old, new)
        for old in removed
        for new in added
        if location(old) == location(new)
    )

    if set(added) != set(approved_added):
        problems.append(
            f"DECLARED DELTA MISMATCH: {len(added)} call site(s) added, "
            f"{len(approved_added)} approval(s) added. Every new call site "
            f"must be declared, and every new declaration must name an "
            f"observed call site"
        )
    if set(removed) != set(approved_removed):
        problems.append(
            f"DECLARED DELTA MISMATCH: {len(removed)} call site(s) removed, "
            f"{len(approved_removed)} approval(s) removed. A call site that "
            f"disappears takes its approval with it, and an approval that "
            f"disappears takes a call site with it"
        )

    return ConnectionChangeReport(
        baseline=baseline,
        candidate=candidate,
        boundary=boundary,
        added=added,
        removed=removed,
        changed_pairs=changed_pairs,
        approved_added=approved_added,
        approved_removed=approved_removed,
        problems=tuple(problems),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the gate from the command line. 0 is PASS, 1 is FAIL, 2 is usage."""
    parser = argparse.ArgumentParser(
        prog="connection_change_verification",
        description=(
            "AI-05 §7.3.13 connection-change verification: compare a baseline "
            "tree against a candidate tree. The trees are supplied by the "
            "caller — typically a worktree of the base commit beside the "
            "candidate checkout; this tool reads files and runs no git command."
        ),
    )
    parser.add_argument(
        "baseline_root", type=pathlib.Path, help="the pre-change tree (§7.3.13's baseline)"
    )
    parser.add_argument(
        "candidate_root", type=pathlib.Path, help="the tree that carries the change"
    )
    parser.add_argument(
        "--baseline-ref", help="the ACTUAL base commit id, recorded verbatim in the report"
    )
    parser.add_argument(
        "--candidate-ref", help="the ACTUAL head commit id, recorded verbatim in the report"
    )
    parser.add_argument(
        "--allow-connected-baseline",
        action="store_true",
        help=(
            "for a LATER change whose baseline is already connected (§7.3.13 "
            "refuses a permanent emptiness requirement); per-tree equality "
            "and the declared-delta check still apply"
        ),
    )
    args = parser.parse_args(argv)

    report = verify_connection_change(
        args.baseline_root,
        args.candidate_root,
        baseline_ref=args.baseline_ref,
        candidate_ref=args.candidate_ref,
        require_pre_connection_baseline=not args.allow_connected_baseline,
    )
    for line in report.record_lines():
        print(line)
    if report.problems:
        print()
        print(f"{len(report.problems)} PROBLEM(S):")
        for problem in report.problems:
            print(f"  - {problem}")
    return 0 if report.verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
