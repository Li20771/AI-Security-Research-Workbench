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
