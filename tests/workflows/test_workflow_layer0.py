"""AI-13 §21.3 — the Layer 0 boundary for `workflows/`, tested by making it fail.

```text
FROZEN: AI-13-B MUST add a Layer 0 boundary for workflows/. The top-level workflows/
        directory is unchecked today — the only `workflows` Layer 0 knows about is
        .github/workflows — so a workflow module could reach a provider, write an
        Evidence record or start a process with nothing to stop it.
```

A boundary check that cannot fail proves nothing. Every test below plants ONE violation
in a scratch tree and requires `check_ai13_workflows` to report it, and the first test
requires it to report NOTHING on the real repository — a check that fires on a clean tree
is equally useless.

The violations are driven from the check's OWN constant tuples, so a root added to the
boundary is covered by a test the moment it is added rather than whenever someone
remembers to write one.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.layer1

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / "workflows"


def _layer0_module():
    path = REPO_ROOT / "scripts" / "ci" / "layer0_policy.py"
    spec = importlib.util.spec_from_file_location("ai13_layer0_policy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LAYER0 = _layer0_module()


def _scratch(
    tmp_path: Path,
    *,
    extra_source: str | None = None,
    extra_module: str = "zz_planted.py",
    drop: str | None = None,
    plugin_dir: str | None = None,
    add_init: bool = False,
) -> Path:
    """A minimal `workflows/` tree, plus whichever violation the caller wants."""
    workflows = tmp_path / "workflows"
    workflows.mkdir(parents=True)
    for module in WORKFLOWS.glob("*.py"):
        if drop is not None and module.name == drop:
            continue
        shutil.copy(module, workflows / module.name)

    if extra_source is not None:
        (workflows / extra_module).write_text(extra_source, encoding="utf-8")
    if plugin_dir is not None:
        (tmp_path / plugin_dir).mkdir(parents=True)
    if add_init:
        (workflows / "__init__.py").write_text("", encoding="utf-8")
    return tmp_path


def test_the_check_passes_on_the_real_repository() -> None:
    """The baseline: with no violation planted, the check reports none."""
    assert _LAYER0.check_ai13_workflows(REPO_ROOT) == []


def test_the_check_catches_a_missing_workflow_module(tmp_path: Path) -> None:
    module = _LAYER0
    problems = module.check_ai13_workflows(_scratch(tmp_path, drop="engine.py"))
    assert any("engine.py is absent" in problem for problem in problems), problems


def test_the_check_catches_a_package_init(tmp_path: Path) -> None:
    """A core layer here is a namespace package; an __init__ is an import side effect."""
    problems = _LAYER0.check_ai13_workflows(_scratch(tmp_path, add_init=True))
    assert any("__init__.py exists" in problem for problem in problems), problems


def test_the_check_catches_a_workflow_plugin(tmp_path: Path) -> None:
    problems = _LAYER0.check_ai13_workflows(_scratch(tmp_path, plugin_dir="plugins/workflows"))
    assert any("plugins/workflows" in problem for problem in problems), problems


@pytest.mark.parametrize("root_name", _LAYER0.AI13_FORBIDDEN_IMPORT_ROOTS)
def test_the_check_catches_every_forbidden_reach(root_name: str, tmp_path: Path) -> None:
    """One planted import per refused root, so a gap in the boundary names itself."""
    problems = _LAYER0.check_ai13_workflows(
        _scratch(tmp_path, extra_source=f"import {root_name}\n")
    )
    assert any(f"imports {root_name!r}" in problem for problem in problems), problems


@pytest.mark.parametrize("root_name", _LAYER0.AI13_FORBIDDEN_STDLIB_ROOTS)
def test_the_check_catches_every_forbidden_process_or_transport(
    root_name: str, tmp_path: Path
) -> None:
    problems = _LAYER0.check_ai13_workflows(
        _scratch(tmp_path, extra_source=f"import {root_name}\n")
    )
    assert any(f"imports {root_name!r}" in problem for problem in problems), problems


@pytest.mark.parametrize("callable_name", _LAYER0.AI13_FORBIDDEN_CALLABLES)
def test_the_check_catches_a_fallback_executor(callable_name: str, tmp_path: Path) -> None:
    """§10.4. AI-12 declares fallback as data; AI-13 must not execute it."""
    problems = _LAYER0.check_ai13_workflows(
        _scratch(tmp_path, extra_source=f"def {callable_name}():\n    return None\n")
    )
    assert any("defines" in problem for problem in problems), problems


def test_a_reach_that_is_NOT_forbidden_is_left_alone(tmp_path: Path) -> None:
    """The control. A check that fired on every import would pass all of the above.

    A workflow module may reach itself and the standard library's inert parts; only
    the roots the contract forbids are refused.
    """
    problems = _LAYER0.check_ai13_workflows(
        _scratch(
            tmp_path,
            extra_source="import hashlib\nimport json\nfrom workflows import canonical\n",
        )
    )
    assert problems == [], problems
# ---------------------------------------------------------------------------
# §13 — the approval point, one planted violation at a time
# ---------------------------------------------------------------------------


def _rewrite(root: Path, module: str, old: str, new: str) -> None:
    """Change one thing in a copied module, and fail if the anchor moved."""
    path = root / "workflows" / module
    text = path.read_text(encoding="utf-8")
    assert old in text, f"the planted edit moved inside {module}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_the_check_catches_a_second_verification_site(tmp_path: Path) -> None:
    """§13.3. One designated ingress, and a second site is a second thing to get wrong."""
    problems = _LAYER0.check_ai13_workflows(
        _scratch(
            tmp_path,
            extra_source=(
                "from cryptography.hazmat.primitives.asymmetric.ed25519 import "
                "Ed25519PublicKey\n"
            ),
        )
    )
    assert any("Ed25519" in problem for problem in problems), problems


def test_the_check_catches_a_caller_selected_trust_root(tmp_path: Path) -> None:
    """§13.3. A public function taking the key has a caller who selects it."""
    problems = _LAYER0.check_ai13_workflows(
        _scratch(
            tmp_path,
            extra_source="def verify_with(public_key):\n    return public_key\n",
        )
    )
    assert any("public_key" in problem for problem in problems), problems


def test_the_check_catches_a_verifier_that_does_not_bind_the_designated_anchor(
    tmp_path: Path,
) -> None:
    """§13.3. A `Provenance` whose anchor is checked against nothing but itself is
    constructible for any keypair the caller generates — a signature under SOME key —
    and the ledger path would accept what it produced. The binding must be PRESENT, so
    removing it is a finding rather than a refactor."""
    root = _scratch(tmp_path)
    _rewrite(
        root,
        "approval.py",
        "        if anchor != _designated_anchor():",
        "        if anchor != anchor:  # planted: the binding is gone",
    )
    problems = _LAYER0.check_ai13_workflows(root)
    assert any("does not bind" in problem for problem in problems), problems


def test_the_check_catches_a_second_module_consulting_the_designated_anchor(
    tmp_path: Path,
) -> None:
    """§13.3. The verifying module may consult the anchor ACCESSOR — that is the binding.
    Anywhere else it is a second place the phase decides what to trust."""
    problems = _LAYER0.check_ai13_workflows(
        _scratch(
            tmp_path,
            extra_source="from workflows.ingress import designated_anchor\n",
        )
    )
    assert any("trust anchor" in problem for problem in problems), problems


def test_the_check_catches_a_second_reader_of_the_anchor_environment_variable(
    tmp_path: Path,
) -> None:
    """§13.3. The deployment fact is READ in one module. A second `os.environ.get` of the
    same variable is a second place the trust root is decided, whether or not it calls
    the accessor."""
    problems = _LAYER0.check_ai13_workflows(
        _scratch(
            tmp_path,
            extra_source=(
                'APPROVAL_TRUST_ANCHOR_ENV = "WORKBENCH_APPROVAL_TRUST_ANCHOR"\n'
            ),
        )
    )
    assert any("environment variable" in problem for problem in problems), problems


def test_the_check_catches_an_approval_mint_factory(tmp_path: Path) -> None:
    """§13.3. "MUST NOT provide a constructor, a factory, a default or any other path"."""
    problems = _LAYER0.check_ai13_workflows(
        _scratch(
            tmp_path,
            extra_source="def make_approval(scope):\n    return scope\n",
        )
    )
    assert any("make_approval" in problem for problem in problems), problems


def test_the_check_catches_guards_approval_vocabulary(tmp_path: Path) -> None:
    """§13.5. A workflow approval is NOT an AI-04 ApprovalRef and is never VERIFIED."""
    problems = _LAYER0.check_ai13_workflows(
        _scratch(tmp_path, extra_source="ApprovalRef = object()\n")
    )
    assert any("ApprovalRef" in problem for problem in problems), problems


def test_the_check_catches_a_seventh_scope_field(tmp_path: Path) -> None:
    """§13.2. The preimage is exactly six, and a seventh changes every digest."""
    root = _scratch(tmp_path)
    _rewrite(
        root,
        "approval.py",
        '    "attempt_no",\n)',
        '    "attempt_no",\n    "approval_point_id",\n)',
    )
    problems = _LAYER0.check_ai13_workflows(root)
    assert any("SCOPE_FIELDS" in problem for problem in problems), problems


def test_the_check_catches_a_target_selector(tmp_path: Path) -> None:
    """§6.1. The gated step is the IMMEDIATELY following one, chosen by nobody."""
    problems = _LAYER0.check_ai13_workflows(
        _scratch(
            tmp_path,
            extra_source="def select_target(definition, stage_id):\n    return stage_id\n",
        )
    )
    assert any("select_target" in problem for problem in problems), problems


def test_the_check_catches_a_checkpoint_that_stopped_refusing_an_approval(tmp_path: Path) -> None:
    """§7.2. A snapshot that could carry an approval is a second authority for it."""
    root = _scratch(tmp_path)
    _rewrite(
        root,
        "checkpoint.py",
        '"provenance", "actor_reference", "decided_at", "artifact_reference",',
        "",
    )
    problems = _LAYER0.check_ai13_workflows(root)
    assert any("no longer refuses" in problem for problem in problems), problems


def test_the_check_catches_a_resume_that_reads_an_approval(tmp_path: Path) -> None:
    """§8.2. A resume inherits declared state, not authority."""
    root = _scratch(tmp_path)
    _rewrite(
        root,
        "resume.py",
        "    return InheritedState(",
        "    _ignored = (run.approvals, run.approval_deadline)\n    return InheritedState(",
    )
    problems = _LAYER0.check_ai13_workflows(root)
    assert any("approvals" in problem for problem in problems), problems
