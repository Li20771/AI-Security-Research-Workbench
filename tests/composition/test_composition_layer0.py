"""AI-14 §17, §19, §21.3 — the composition layer boundary, tested by making it fail.

A boundary check that cannot fail proves nothing. Every test below plants ONE
violation in a scratch tree and requires `check_ai14_composition_layer` to report
it, and the first test requires it to report NOTHING on the real repository — a
check that fires on a clean tree is equally useless.

ONE TEST BELOW IS A CONTROL RATHER THAN A VIOLATION:
`test_the_check_allows_the_authorized_evidence_import` plants the import AI-14
Amendment 2 authorized and requires the check to report NOTHING. The block is still
proven non-vacuous by the other planted violations — a foreign root, a forbidden
process root, an authority vocabulary, a forbidden callable, a layer importing the
composition — every one of which still fails.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.layer1

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSITION = REPO_ROOT / "composition"


def _layer0_module():
    path = REPO_ROOT / "scripts" / "ci" / "layer0_policy.py"
    spec = importlib.util.spec_from_file_location("ai14_layer0_policy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_LAYER0 = _layer0_module()


def _scratch(
    tmp_path: Path,
    *,
    extra_source: str | None = None,
    drop: str | None = None,
    add_init: bool = False,
    plant_layer_import: str | None = None,
) -> Path:
    """A minimal tree: the real `composition/`, plus whichever violation is asked for."""
    package = tmp_path / "composition"
    package.mkdir(parents=True)
    for module in COMPOSITION.glob("*.py"):
        if drop is not None and module.name == drop:
            continue
        shutil.copy(module, package / module.name)

    if extra_source is not None:
        (package / "zz_planted.py").write_text(extra_source, encoding="utf-8")
    if add_init:
        (package / "__init__.py").write_text("", encoding="utf-8")
    if plant_layer_import is not None:
        area = tmp_path / plant_layer_import
        area.mkdir(parents=True, exist_ok=True)
        (area / "zz_planted.py").write_text(
            "import composition\n", encoding="utf-8"
        )
    return tmp_path


def test_the_check_passes_on_the_real_repository() -> None:
    """The baseline: with no violation planted, the check reports none."""
    assert _LAYER0.check_ai14_composition_layer(REPO_ROOT) == []


def test_the_check_catches_a_missing_composition_module(tmp_path: Path) -> None:
    problems = _LAYER0.check_ai14_composition_layer(
        _scratch(tmp_path, drop="executor.py")
    )
    assert any("executor.py is absent" in problem for problem in problems), problems


def test_the_check_catches_a_package_init(tmp_path: Path) -> None:
    """A core layer here is a namespace package; an __init__ is an import side effect."""
    problems = _LAYER0.check_ai14_composition_layer(_scratch(tmp_path, add_init=True))
    assert any("__init__.py exists" in problem for problem in problems), problems


def test_the_check_catches_a_process_or_transport_reach(tmp_path: Path) -> None:
    """§18: no daemon, no scheduler, nothing held open between processes."""
    problems = _LAYER0.check_ai14_composition_layer(
        _scratch(tmp_path, extra_source="import socket\n")
    )
    assert any("socket" in problem for problem in problems), problems


def test_the_check_catches_a_foreign_root(tmp_path: Path) -> None:
    """The composition composes the layers THIS repository froze."""
    problems = _LAYER0.check_ai14_composition_layer(
        _scratch(tmp_path, extra_source="import numpy\n")
    )
    assert any("numpy" in problem for problem in problems), problems


def test_the_check_allows_the_authorized_evidence_import(tmp_path: Path) -> None:
    """AI-14 Amendment 2 AUTHORIZES `plugins.evidence`; the check no longer refuses it.

    THIS IS THE ONE TEST IN THIS FILE THAT PLANTS AN ALLOWED CHANGE rather than a
    violation, and it is the control for STEP 1's authorization: the rule stopped
    refusing this import, and the check must therefore report NOTHING here. It is
    also the guard against the opposite error — a rule re-widened by accident would
    be caught by the `numpy` and `socket` cases below, which still fail.

    THE AUTHORIZATION IS NARROW. It permits an IMPORT and says nothing about a CALL:
    no production code calls `admit` or `admit_to_store` anywhere in this repository,
    so B5 remains BLOCKED and the edge remains IMPLEMENTED BUT NOT CONNECTED (§5.1,
    §22.1 B5).
    """
    problems = _LAYER0.check_ai14_composition_layer(
        _scratch(tmp_path, extra_source="from plugins.evidence import admit\n")
    )
    assert problems == [], problems


@pytest.mark.parametrize(
    "identifier",
    [
        "Ed25519PrivateKey",
        "ApprovalRef",
        "ADMITTED_EVENTS",
        "DecisionRecord",
        "CredentialRef",
    ],
)
def test_the_check_catches_an_authority_vocabulary(
    identifier: str, tmp_path: Path
) -> None:
    """§4.2, §13, §14: the composition constructs no authority of its own."""
    problems = _LAYER0.check_ai14_composition_layer(
        _scratch(tmp_path, extra_source=f"{identifier} = object()\n")
    )
    assert any(identifier in problem for problem in problems), problems


@pytest.mark.parametrize("callable_name", ["Invoker", "escalate"])
def test_the_check_catches_a_network_client_or_a_fallback(
    callable_name: str, tmp_path: Path
) -> None:
    """§22.1 B2, §23: the composition builds no invoker and executes no fallback.

    The live HTTP transport is not named: AI-02's own confinement guard asserts
    that its name appears nowhere outside the live path, so naming it here would
    be that guard's violation rather than a second enforcement of it.
    """
    problems = _LAYER0.check_ai14_composition_layer(
        _scratch(tmp_path, extra_source=f"def {callable_name}(*a):\n    return a\n")
    )
    assert any(callable_name in problem for problem in problems), problems


@pytest.mark.parametrize("layer", ["workflows", "agents", "plugins"])
def test_the_check_catches_a_layer_that_imports_the_composition(
    layer: str, tmp_path: Path
) -> None:
    """One-way: the composition is a CALLER, never a dependency (§19).

    A layer that imported it would need the composition to run, which would make
    the composition the layer.
    """
    problems = _LAYER0.check_ai14_composition_layer(
        _scratch(tmp_path, plant_layer_import=layer)
    )
    assert any("imports 'composition'" in problem for problem in problems), problems


def test_a_reach_that_is_NOT_forbidden_is_left_alone(tmp_path: Path) -> None:
    """The control. A check that fired on every import would pass all of the above.

    A composition module may import a layer's public package and the inert parts
    of the standard library; only the roots the contract refuses are refused.
    """
    problems = _LAYER0.check_ai14_composition_layer(
        _scratch(
            tmp_path,
            extra_source=(
                "import math\n"
                "from dataclasses import dataclass\n"
                "from typing import Any\n"
                "from workflows.engine import advance\n"
                "from plugins.security_tools import invoke\n"
            ),
        )
    )
    assert problems == [], problems
