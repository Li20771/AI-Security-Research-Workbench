"""The connection-change gate, tested as §7.3.13 defines it — two trees.

Every test except the last builds SYNTHETIC trees under `tmp_path`: a baseline
and a candidate, each carrying fixture copies of the acceptance boundary, an
optional planted production module, and a fixture approved-set declaration.
The planted calls live in the synthetic trees only — nothing here adds a call
site to the repository, and the repository's own approved set stays empty.

The last test runs the gate over the REAL repository against itself, in the
general mode, asserting only the invariants that hold on both sides of a
connection: an empty delta, an unchanged boundary, and per-tree equality. The
§7.3.13 one-time gate (an EMPTY, EMPTY baseline) is exercised on synthetic
trees, because the real tree stops being pre-connection the day the connection
lands and this module must not become a time bomb that fails it.
"""

from __future__ import annotations

import pathlib

import pytest

import callsite_identity
from callsite_identity import group_by_key, scan_tree

import connection_change_verification as ccv
from connection_change_verification import verify_connection_change

pytestmark = pytest.mark.layer1

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

SUBMIT_DIRECT = (
    "from plugins.evidence import admit_to_store\n"
    "\n"
    "\n"
    "def submit(record, proof):\n"
    "    return admit_to_store(record, producer_proof=proof)\n"
)

#: The SAME call — same scope, same arguments, same canonical entry point —
#: spelled through an alias. §7.3.13: two DIFFERENT call sites, and an approval
#: of one is not an approval of the other.
SUBMIT_ALIASED = (
    "from plugins.evidence import admit_to_store as persist\n"
    "\n"
    "\n"
    "def submit(record, proof):\n"
    "    return persist(record, producer_proof=proof)\n"
)

#: An unsupported acquisition carried forward onto the name it binds: the later
#: call is the finding (§7.3.13's scanner boundary).
SUBMIT_UNRESOLVED = (
    "import plugins.evidence as ev\n"
    "\n"
    "\n"
    "def submit(record, proof):\n"
    "    writer = getattr(ev, \"admit\")\n"
    "    return writer(record, producer_proof=proof)\n"
)

#: A resolved call without the explicit proof keyword: an approval alone does
#: not satisfy §7.3.13's independent proof_kwarg condition.
SUBMIT_NO_PROOF = (
    "from plugins.evidence import admit_to_store\n"
    "\n"
    "\n"
    "def submit(record):\n"
    "    return admit_to_store(record)\n"
)


def _declare(root, keys=()):
    """Write the fixture approved-set declaration.

    The diff that adds an entry IS the approval artifact, so the declaration
    is a plain dict literal of six-string keys — the same shape the real
    acceptance module declares and the gate reads back.
    """
    declaration = pathlib.Path(root) / ccv.APPROVED_DECLARATION_MODULE
    declaration.parent.mkdir(parents=True, exist_ok=True)
    entries = "".join(f"    {tuple(key)!r}: None,\n" for key in keys)
    declaration.write_text(
        "# fixture declaration module\n"
        "APPROVED_CALL_SITES = {\n"
        f"{entries}"
        "}\n",
        encoding="utf-8",
    )


def _write_tree(root, *, submit=None, approved=()):
    """One synthetic tree: fixture boundary files, an optional planted module,
    and a declaration.

    The boundary copies carry no admission calls, so nothing in a clean tree
    engages the intra-package exception.
    """
    root = pathlib.Path(root)
    for relative in ccv.ACCEPTANCE_BOUNDARY_FILES:
        boundary_file = root / relative
        boundary_file.parent.mkdir(parents=True, exist_ok=True)
        boundary_file.write_text(f"# fixture copy of {relative}\n", encoding="utf-8")
    if submit is not None:
        composition = root / "composition"
        composition.mkdir(parents=True, exist_ok=True)
        (composition / "submit.py").write_text(submit, encoding="utf-8")
    _declare(root, approved)
    return root


def _effective(root):
    """The tree's effective observed mapping — the §7.3.13 set, with the one
    pinned intra-package identity excluded, exactly as the gate computes it."""
    observed, unresolved, failures = scan_tree(pathlib.Path(root), skip_paths=("tests",))
    assert unresolved == [] and failures == []
    return {
        key: identity
        for key, identity in group_by_key(observed).items()
        if key != callsite_identity.INTRA_PACKAGE_CALL_SITE
    }


def _only_key(root):
    effective = _effective(root)
    assert len(effective) == 1, f"the fixture must plant exactly one call site: {sorted(effective)}"
    return next(iter(effective))


def _key_for(root, path):
    effective = _effective(root)
    matches = [key for key in effective if key[0] == path]
    assert len(matches) == 1, f"expected exactly one call site in {path}: {matches}"
    return matches[0]


def test_identical_pre_connection_trees_pass(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand")
    report = verify_connection_change(
        baseline, candidate, baseline_ref="a" * 40, candidate_ref="b" * 40
    )
    assert report.verdict == "PASS", report.problems
    assert report.added == () and report.removed == ()
    assert report.changed_pairs == ()
    assert report.approved_added == frozenset()
    assert report.baseline.pre_connection is True
    assert all(state.unchanged for state in report.boundary)
    # §7.3.13's four recorded items are the report's first four lines.
    lines = report.record_lines()
    assert lines[0].startswith("base SHA (baseline tree): aaaa")
    assert "baseline production call-site set: EMPTY" in lines[1]
    assert lines[2].startswith("head SHA (candidate tree): bbbb")
    assert "candidate production call-site set: EMPTY" in lines[3]


def test_a_call_site_the_candidate_does_not_declare_fails(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand", submit=SUBMIT_DIRECT)
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any("CANDIDATE TREE: UNAPPROVED call site" in p for p in report.problems)
    assert any("DECLARED DELTA MISMATCH" in p for p in report.problems)
    assert len(report.added) == 1
    assert report.approved_added == frozenset()


def test_a_call_site_the_candidate_declares_passes(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand", submit=SUBMIT_DIRECT)
    key = _only_key(candidate)
    _declare(candidate, (key,))
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "PASS", report.problems
    assert report.added == (key,)
    assert report.approved_added == {key}
    assert report.baseline.pre_connection is True
    assert all(state.unchanged for state in report.boundary)


def test_a_declaration_without_a_call_site_fails(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    phantom = (
        "composition/submit.py",
        "submit",
        "admit_to_store",
        "Name(id='admit_to_store', ctx=Load())",
        "body[1].body[0].value",
        "0" * 64,
    )
    candidate = _write_tree(tmp_path / "cand", approved=(phantom,))
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any("CANDIDATE TREE: APPROVED call site NOT FOUND" in p for p in report.problems)


def test_an_approval_does_not_excuse_a_missing_proof_keyword(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand", submit=SUBMIT_NO_PROOF)
    key = _only_key(candidate)
    _declare(candidate, (key,))
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any(
        "CANDIDATE TREE: MISSING producer_proof KEYWORD" in p for p in report.problems
    )
    # the approval itself matches — the failure is the independent condition
    assert not any("UNAPPROVED call site" in p for p in report.problems)
    assert not any("APPROVED call site NOT FOUND" in p for p in report.problems)


def test_a_baseline_that_already_has_a_call_site_is_not_pre_connection(tmp_path):
    baseline = _write_tree(tmp_path / "base", submit=SUBMIT_DIRECT)
    candidate = _write_tree(tmp_path / "cand", submit=SUBMIT_DIRECT)
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any("BASELINE NOT PRE-CONNECTION" in p for p in report.problems)
    assert any("BASELINE TREE: UNAPPROVED call site" in p for p in report.problems)


def test_a_connected_baseline_is_the_later_changes_shape(tmp_path):
    """§7.3.13 refuses a permanent emptiness requirement. Once main is
    connected, a LATER change runs in general mode and is still held to
    per-tree equality and an exactly-declared delta."""
    baseline = _write_tree(tmp_path / "base", submit=SUBMIT_DIRECT)
    first = _only_key(baseline)
    _declare(baseline, (first,))

    candidate = _write_tree(tmp_path / "cand", submit=SUBMIT_DIRECT)
    second_module = SUBMIT_DIRECT.replace("def submit(", "def submit_again(")
    (candidate / "composition" / "again.py").write_text(second_module, encoding="utf-8")
    second = _key_for(candidate, "composition/again.py")
    _declare(candidate, (first, second))

    strict = verify_connection_change(baseline, candidate)
    assert strict.verdict == "FAIL"
    assert any("BASELINE NOT PRE-CONNECTION" in p for p in strict.problems)

    general = verify_connection_change(
        baseline, candidate, require_pre_connection_baseline=False
    )
    assert general.verdict == "PASS", general.problems
    assert general.added == (second,)
    assert general.approved_added == {second}


def test_a_changed_callee_form_is_a_new_identity(tmp_path):
    """§7.3.13's substitution rule, across two trees: when the callee's syntax
    form changes, the old approval MUST NOT match, and the new form MUST be
    approved again."""
    baseline = _write_tree(tmp_path / "base", submit=SUBMIT_DIRECT)
    direct = _only_key(baseline)
    _declare(baseline, (direct,))

    candidate = _write_tree(tmp_path / "cand", submit=SUBMIT_ALIASED, approved=(direct,))
    aliased = _only_key(candidate)
    assert aliased != direct, "an aliased callee is a different call site"
    assert aliased[:3] == direct[:3], "same path, scope and entrypoint — the substitution case"

    undeclared = verify_connection_change(
        baseline, candidate, require_pre_connection_baseline=False
    )
    assert undeclared.verdict == "FAIL"
    assert any("CANDIDATE TREE: UNAPPROVED call site" in p for p in undeclared.problems)
    assert any(
        "CANDIDATE TREE: APPROVED call site NOT FOUND" in p for p in undeclared.problems
    )
    assert undeclared.changed_pairs == ((direct, aliased),)

    _declare(candidate, (aliased,))
    declared = verify_connection_change(
        baseline, candidate, require_pre_connection_baseline=False
    )
    assert declared.verdict == "PASS", declared.problems
    assert declared.changed_pairs == ((direct, aliased),)


def test_an_unresolvable_form_in_the_candidate_fails(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand", submit=SUBMIT_UNRESOLVED)
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any(
        "CANDIDATE TREE: UNRESOLVED production call form" in p for p in report.problems
    )


def test_an_unreadable_module_in_the_candidate_fails(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand")
    broken = candidate / "composition" / "broken.py"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("def (:\n", encoding="utf-8")
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any(
        "CANDIDATE TREE: UNREADABLE production module" in p for p in report.problems
    )


def test_a_changed_boundary_file_fails_the_gate(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand")
    (candidate / "plugins" / "evidence" / "admission.py").write_text(
        "# fixture copy — EDITED\n", encoding="utf-8"
    )
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any(
        "ACCEPTANCE BOUNDARY CHANGED: plugins/evidence/admission.py" in p
        for p in report.problems
    )


def test_a_missing_boundary_file_fails_the_gate(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand")
    (candidate / "plugins" / "evidence" / "producer_auth.py").unlink()
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any(
        "ACCEPTANCE BOUNDARY FILE MISSING: plugins/evidence/producer_auth.py" in p
        for p in report.problems
    )


def test_an_unreadable_approved_declaration_fails(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand")
    (candidate / ccv.APPROVED_DECLARATION_MODULE).unlink()
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any(
        "CANDIDATE TREE: APPROVED SET UNREADABLE" in p for p in report.problems
    )


def test_a_malformed_approved_entry_fails(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand")
    (candidate / ccv.APPROVED_DECLARATION_MODULE).write_text(
        "APPROVED_CALL_SITES = {('a', 'b', 'c', 'd', 'e'): None}\n", encoding="utf-8"
    )
    report = verify_connection_change(baseline, candidate)
    assert report.verdict == "FAIL"
    assert any(
        "CANDIDATE TREE: APPROVED ENTRY MALFORMED" in p for p in report.problems
    )


def test_a_recorded_ref_that_is_not_a_commit_sha_fails(tmp_path):
    baseline = _write_tree(tmp_path / "base")
    candidate = _write_tree(tmp_path / "cand")
    report = verify_connection_change(baseline, candidate, baseline_ref="main")
    assert report.verdict == "FAIL"
    assert any(
        "RECORDED baseline REF IS NOT A COMMIT SHA: 'main'" in p for p in report.problems
    )


def test_the_real_repository_against_itself_in_general_mode():
    """The one REAL-tree check. General mode, and only the invariants that
    hold on both sides of a connection — see the module docstring for why the
    one-time empty-baseline gate is asserted on synthetic trees instead."""
    report = verify_connection_change(
        REPO_ROOT, REPO_ROOT, require_pre_connection_baseline=False
    )
    assert report.verdict == "PASS", report.problems
    assert report.added == () and report.removed == ()
    assert all(state.unchanged for state in report.boundary)
