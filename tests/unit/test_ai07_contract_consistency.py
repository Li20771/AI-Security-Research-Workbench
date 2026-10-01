"""AI-07-A contract consistency — T14b, T15, T16, T17, T20, T29 at contract level.

AI-07-A implements nothing, so its checks are contract/document consistency
checks. This module holds the ones that are about the **amended** rules, and
each is mutation-tested: a copy of the tree is altered back to the pre-amendment
wording and the gate must notice.

A gate that has only ever seen a consistent contract is a gate nobody has
watched fail. Amendment 1 exists because four rules were inconsistent with the
rest of the contract and with AI-02, and these tests are what keep them fixed.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.layer1

ROOT = pathlib.Path(".").resolve()
LAYER0 = ROOT / "scripts" / "ci" / "layer0_policy.py"
CONTRACT = ROOT / "docs" / "AI-07_MODEL_ROUTER_EXECUTION_PLAN.md"


def _layer0(path: pathlib.Path = LAYER0):
    spec = importlib.util.spec_from_file_location(f"layer0_{id(path)}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check(root: pathlib.Path) -> list[str]:
    """Run the AI-07 gate against `root`, importing what that root contains.

    The check's own module is loaded from `root` so a mutated copy is inspected
    rather than the tree the test process already imported.
    """
    module = _layer0(root / "scripts" / "ci" / "layer0_policy.py")
    module.ROOT = root.resolve()
    return module.check_ai07_router_contract()


# --------------------------------------------------------------------------
# the contract as it stands
# --------------------------------------------------------------------------


class TestTheFrozenContractIsConsistent:
    def test_the_gate_passes_on_the_real_tree(self):
        assert _check(ROOT) == []

    def test_layer0_runs_green(self):
        completed = subprocess.run(
            [sys.executable, str(LAYER0)], capture_output=True, text=True, check=False
        )

        assert completed.returncode == 0, completed.stdout + completed.stderr

    def test_amendment_1_is_recorded(self):
        text = CONTRACT.read_text(encoding="utf-8")

        assert "Amendment 1" in text
        assert "(none)" not in text.split("## 22. Amendment log")[1][:200]
        assert "Security / authority impact:  NONE." in text


class TestAmendment1ClausesAreInTheContract:
    """Each is a rule AI-07-B would otherwise have had to invent its way past."""

    @pytest.mark.parametrize(
        "clause",
        [
            # (a) sensitivity
            "`sensitivity` MUST NOT widen or narrow the candidate set in v1",
            "AI-07 v1 does NOT use it to change model eligibility",
            "`sensitivity` MUST NOT authorize",
            # (b) cost class
            "cost-class routing is DEFERRED",
            "AI-07 MUST NOT invent a cost class",
            "INVALID_REQUEST. It MUST NOT be silently ignored",
            # (c) fallback
            "AI-07 v1 has NO automatic fallback mechanism",
            "AI-07 does NOT retry a selected model",
            "carries no\n        `fallbacks`",
            # (d) independence
            "MUST NOT assert that the hint identifies a VERIFIED",
            "MUST NOT be read as",
        ],
    )
    def test_the_clause_is_frozen(self, clause):
        assert clause in CONTRACT.read_text(encoding="utf-8"), clause

    def test_the_live_request_schema_no_longer_declares_a_cost_class(self):
        """`max_cost_class` survives only in the two notes that correct it."""
        text = CONTRACT.read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if "max_cost_class" in line]

        assert len(lines) == 2, lines
        for line in lines:
            assert "earlier revision" in line or "§5.1 declared" in line, line

    def test_a_cost_class_constraint_is_represented_in_the_matrix(self):
        text = CONTRACT.read_text(encoding="utf-8")

        assert "T14b" in text
        assert "never silently ignored" in text


# --------------------------------------------------------------------------
# the gate bites
# --------------------------------------------------------------------------


class TestTheGateBites:
    @pytest.fixture
    def copied_tree(self, tmp_path):
        for name in ("routing", "docs", "scripts", "config"):
            source = ROOT / name
            if source.is_dir():
                shutil.copytree(source, tmp_path / name, dirs_exist_ok=True)
        return tmp_path

    def _contract_of(self, root: pathlib.Path) -> pathlib.Path:
        return root / "docs" / "AI-07_MODEL_ROUTER_EXECUTION_PLAN.md"

    def test_an_unmutated_copy_is_clean(self, copied_tree):
        assert _check(copied_tree) == []

    def test_restoring_the_sensitivity_narrowing_is_caught(self, copied_tree):
        """Amendment 1 (a): the rule that had no AI-02 source field."""
        path = self._contract_of(copied_tree)
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(
                "`sensitivity` MUST NOT widen or narrow the candidate set in v1",
                "`sensitivity` MAY narrow the candidate set",
            ),
            encoding="utf-8",
        )

        fired = _check(copied_tree)

        assert any("sensitivity" in problem for problem in fired), fired

    def test_reintroducing_an_invented_cost_class_is_caught(self, copied_tree):
        """Amendment 1 (b): a vocabulary AI-02 does not define."""
        path = self._contract_of(copied_tree)
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(
                "FROZEN: cost-class routing is DEFERRED in AI-07 v1, because AI-02 does not",
                "FROZEN: cost-class routing uses the classes cheap, medium and expensive; AI-02 does not",
            ),
            encoding="utf-8",
        )

        fired = _check(copied_tree)

        assert any("cost-class" in problem for problem in fired), fired

    def test_reintroducing_an_automatic_fallback_is_caught(self, copied_tree):
        """Amendment 1 (c): the retry the no-retry rule forbids.

        The phrase appears twice in the contract — once in the FROZEN block and
        once in the prose that explains the correction — so the mutation replaces
        both. Replacing one would leave the rule stated and the gate correctly
        silent, which would look like a passing test and prove nothing.
        """
        path = self._contract_of(copied_tree)
        text = path.read_text(encoding="utf-8")
        assert text.count("AI-07 v1 has NO automatic fallback mechanism") == 2
        path.write_text(
            text.replace(
                "AI-07 v1 has NO automatic fallback mechanism",
                "AI-07 retries with the next candidate automatically",
            ),
            encoding="utf-8",
        )

        fired = _check(copied_tree)

        assert any("fallback" in problem for problem in fired), fired


class TestTheIdentityHoldsAfterImplementation:
    """What AI-07-A asserted as absence, restated as a property.

    AI-07-A claimed `routing/` contained no Python. That was the honest claim for
    a contract-freeze phase, and AI-07-B supersedes it by implementing the router.
    The claims that survive are the structural ones, and they are the ones that
    mattered: the directory is a core service, not a plugin layer, and the
    roadmap's sketch is still not a schema.
    """

    def test_routing_is_still_not_a_plugin_package(self):
        assert not (ROOT / "routing" / "__init__.py").exists()
        assert not (ROOT / "plugins" / "router").exists()

    def test_the_router_exists_where_the_core_service_belongs(self):
        assert (ROOT / "routing" / "router.py").is_file()

    def test_the_config_example_is_still_not_a_schema(self):
        """§3.2: the sketch names profiles that do not exist.

        `rules.example.yaml` is intent, and nothing loads it. The tracked default
        rule set is a different file, and it is empty.
        """
        text = (ROOT / "config" / "routing" / "rules.example.yaml").read_text(
            encoding="utf-8"
        )

        assert "model_profile: fast" in text

    def test_no_invented_profile_was_created_to_match_the_sketch(self):
        from providers.model_registry import load_all_model_profiles

        for invented in ("fast", "strong", "multimodal"):
            assert invented not in load_all_model_profiles()
