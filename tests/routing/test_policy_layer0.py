"""AI-12 §10 — the Layer 0 check for the policy core, tested by making it fail.

A boundary check that cannot fail proves nothing. Every test below plants one
violation in a scratch tree and requires `check_ai12_policy_core` to report it, and
the first test requires it to report NOTHING on the real repository — a check that
fires on a clean tree is equally useless.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.layer1

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTING = REPO_ROOT / "routing"


def _layer0_module():
    path = REPO_ROOT / "scripts" / "ci" / "layer0_policy.py"
    spec = importlib.util.spec_from_file_location("ai12_layer0_policy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch(tmp_path: Path, *, extra_source: str | None = None,
             extra_module: str = "policy_extra.py",
             drop: str | None = None,
             plugin_dir: str | None = None,
             example: str | None = None) -> Path:
    """A minimal routing/ tree, plus whichever violation the caller wants."""
    routing = tmp_path / "routing"
    routing.mkdir(parents=True)
    for module in ROUTING.glob("*.py"):
        if drop is not None and module.name == drop:
            continue
        shutil.copy(module, routing / module.name)

    config = tmp_path / "config" / "routing"
    config.mkdir(parents=True)
    source_example = REPO_ROOT / "config" / "routing" / "policy.example.yaml"
    (config / "policy.example.yaml").write_text(
        source_example.read_text(encoding="utf-8") if example is None else example,
        encoding="utf-8",
    )

    if extra_source is not None:
        (routing / extra_module).write_text(extra_source, encoding="utf-8")
    if plugin_dir is not None:
        (tmp_path / plugin_dir).mkdir(parents=True)
    return tmp_path


def test_T40_the_check_passes_on_the_real_repository() -> None:
    """The baseline: with no violation planted, the check reports none."""
    module = _layer0_module()
    assert module.check_ai12_policy_core(REPO_ROOT) == []


def test_T41_the_check_catches_a_fifth_plugin_layer(tmp_path: Path) -> None:
    module = _layer0_module()
    problems = module.check_ai12_policy_core(_scratch(tmp_path, plugin_dir="plugins/policy"))
    assert any("plugins/policy" in problem for problem in problems)


def test_T42_the_check_catches_a_policy_module_reaching_the_benchmark_runner(
    tmp_path: Path,
) -> None:
    """§4.1. A core that could import the runner could re-run AI-11."""
    module = _layer0_module()
    source = "from benchmarks.runner import execute_task\n\n\nVALUE = execute_task\n"
    problems = module.check_ai12_policy_core(_scratch(tmp_path, extra_source=source))
    assert any("benchmarks.runner" in problem for problem in problems)


def test_T43_the_check_catches_a_hidden_score(tmp_path: Path) -> None:
    """§4.3, §9. The name a hidden scoring system would acquire."""
    module = _layer0_module()
    source = "def verdict_score(verdict):\n    return 1.0\n"
    problems = module.check_ai12_policy_core(_scratch(tmp_path, extra_source=source))
    assert any("verdict_score" in problem for problem in problems)


def test_T44_the_check_catches_a_weight_table(tmp_path: Path) -> None:
    module = _layer0_module()
    source = "WEIGHTS = {}\n\n\ndef weight():\n    return WEIGHTS\n"
    problems = module.check_ai12_policy_core(_scratch(tmp_path, extra_source=source))
    assert any("weight" in problem.lower() for problem in problems)


def test_T45_the_check_catches_a_ranking(tmp_path: Path) -> None:
    module = _layer0_module()
    source = "def model_ranking(records):\n    return sorted(records)\n"
    problems = module.check_ai12_policy_core(_scratch(tmp_path, extra_source=source))
    assert any("model_ranking" in problem for problem in problems)


def test_T46_the_check_catches_a_runtime_fallback(tmp_path: Path) -> None:
    """§5.2. AI-12 declares a fallback; it does not execute one."""
    module = _layer0_module()
    source = "def execute_fallback(policy):\n    return policy\n"
    problems = module.check_ai12_policy_core(_scratch(tmp_path, extra_source=source))
    assert any("execute_fallback" in problem for problem in problems)


def test_T47_the_check_catches_a_retry(tmp_path: Path) -> None:
    module = _layer0_module()
    source = "def retry(model_ref):\n    return model_ref\n"
    problems = module.check_ai12_policy_core(_scratch(tmp_path, extra_source=source))
    assert any("retry" in problem for problem in problems)


def test_T48_the_check_catches_a_stray_process_import(tmp_path: Path) -> None:
    module = _layer0_module()
    source = "import subprocess\n\n\ndef go():\n    return subprocess.run(['true'])\n"
    problems = module.check_ai12_policy_core(_scratch(tmp_path, extra_source=source))
    assert any("subprocess" in problem for problem in problems)


def test_T49_the_check_catches_a_missing_policy_module(tmp_path: Path) -> None:
    module = _layer0_module()
    problems = module.check_ai12_policy_core(_scratch(tmp_path, drop="policy.py"))
    assert any("routing/policy.py is absent" in problem for problem in problems)


def test_T50_the_check_catches_an_example_that_no_longer_validates(tmp_path: Path) -> None:
    """A tracked artifact nothing checks is an artifact that drifts."""
    module = _layer0_module()
    broken = "version: 1\npolicy_id: broken\nrevision: v1\nevidence_scope: []\n"
    problems = module.check_ai12_policy_core(_scratch(tmp_path, example=broken))
    assert any("policy.example.yaml" in problem for problem in problems)


def test_T51_the_check_catches_an_absent_example(tmp_path: Path) -> None:
    module = _layer0_module()
    tree = _scratch(tmp_path)
    (tree / "config" / "routing" / "policy.example.yaml").unlink()
    problems = module.check_ai12_policy_core(tree)
    assert any("policy.example.yaml is absent" in problem for problem in problems)
