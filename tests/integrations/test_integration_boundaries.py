"""The integration layer's composition boundary (contract §10.3, §17).

Layer 1: structural assertions and the Layer 0 gate. No transport.

AI-09 composes two layers that are forbidden to know about each other, so this
boundary carries more weight than most. The tests here are the fast local
version of `check_ai09_integration_layer()`; the gate itself is what CI runs.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

pytestmark = pytest.mark.layer1

INTEGRATIONS = pathlib.Path("integrations")

#: Reached only through AI-02's invocation boundary, never directly.
FORBIDDEN_IMPORTS = (
    "socket",
    "http",
    "urllib",
    "urllib3",
    "requests",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
    "telnetlib",
    "ssl",
    "asyncio",
    "multiprocessing",
    "subprocess",
    "shutil",
    "os",
    "routing",
    "tools",
)

ALLOWED_PROVIDER_IMPORTS = (
    "providers.config",
    "providers.invocation",
    "providers.model_profile",
    "providers.profile",
    "providers.protocol",
    "providers.transport",
)

ALLOWED_PLUGIN_IMPORTS = ("plugins.context",)


def _integration_modules() -> list[pathlib.Path]:
    return sorted(
        path for path in INTEGRATIONS.rglob("*.py") if "__pycache__" not in path.parts
    )


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class TestTheLayerIsACoreLayer:
    def test_integrations_is_a_namespace_package(self):
        assert INTEGRATIONS.is_dir()
        assert not (INTEGRATIONS / "__init__.py").exists()

    def test_the_codex_boundary_exists(self):
        assert (INTEGRATIONS / "codex").is_dir()

    def test_it_is_not_a_plugin_and_not_a_provider(self):
        assert not pathlib.Path("plugins/codex").exists()
        assert not pathlib.Path("plugins/integrations").exists()
        assert not pathlib.Path("providers/codex").exists()

    def test_it_carries_no_provider_side_data(self):
        assert not list(INTEGRATIONS.rglob("*.yaml"))
        assert not list(INTEGRATIONS.rglob("provider.yaml"))


class TestTheReachOfTheLayer:
    @pytest.mark.parametrize("forbidden", FORBIDDEN_IMPORTS)
    def test_no_module_imports_it(self, forbidden):
        for path in _integration_modules():
            roots = {name.split(".")[0] for name in _imports(path)}
            assert forbidden not in roots, f"{path}: {forbidden}"

    def test_only_allowlisted_provider_modules_are_reached(self):
        for path in _integration_modules():
            for name in _imports(path):
                if name.split(".")[0] != "providers":
                    continue
                assert any(
                    name == entry or name.startswith(entry + ".")
                    for entry in ALLOWED_PROVIDER_IMPORTS
                ), f"{path}: {name}"

    def test_no_module_reaches_a_concrete_transport(self):
        """AI-09's half of AI-02's confinement property.

        AI-02's own guard ranges over `providers/`, `tests/` and `scripts/`, so a
        new top-level package escapes it. The allowlist in
        `check_ai09_integration_layer()` is what closes that for `integrations/`,
        and `TestTheLayerZeroGate` proves that gate is not vacuous. What is
        asserted here is the same property from inside the package: nothing under
        `integrations/` imports a transport implementation, so the only transport
        a backend can use is the one its caller injected.
        """
        for path in _integration_modules():
            for name in _imports(path):
                if name.split(".")[0] != "providers":
                    continue
                assert name in (
                    "providers.config",
                    "providers.invocation",
                    "providers.model_profile",
                    "providers.profile",
                    "providers.protocol",
                    "providers.transport",
                ), f"{path}: {name}"

    def test_only_the_context_plugin_is_reached(self):
        for path in _integration_modules():
            for name in _imports(path):
                if name.split(".")[0] != "plugins":
                    continue
                assert any(
                    name == entry or name.startswith(entry + ".")
                    for entry in ALLOWED_PLUGIN_IMPORTS
                ), f"{path}: {name}"

    def test_no_credential_is_resolved_here(self):
        for path in _integration_modules():
            names = {
                node.id
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(node, ast.Name)
            }
            assert "CredentialRef" not in names, path
            assert "SecretValue" not in names, path


class TestTheDependencyIsOneWay:
    @pytest.mark.parametrize("owner", ["agents", "providers"])
    def test_the_other_layer_does_not_import_integrations(self, owner):
        for path in sorted(pathlib.Path(owner).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for name in _imports(path):
                assert not (
                    name == "integrations" or name.startswith("integrations.")
                ), f"{path}: {name}"


class TestTheLayerZeroGate:
    """The gate exists, runs green, and is not vacuous."""

    def test_the_ai09_check_is_registered(self):
        source = pathlib.Path("scripts/ci/layer0_policy.py").read_text(encoding="utf-8")
        assert "def check_ai09_integration_layer()" in source
        assert '"integration layer composition boundary"' in source

    def test_the_gate_runs_green(self):
        completed = subprocess.run(
            [sys.executable, "scripts/ci/layer0_policy.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "Layer 0 = PASS" in completed.stdout
        assert "integration layer composition boundary" in completed.stdout

    def test_the_gate_is_not_vacuous(self, tmp_path):
        """A synthetic violation must be caught, or the gate proves nothing."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "layer0_policy_under_test", "scripts/ci/layer0_policy.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        scratch = tmp_path / "repo"
        (scratch / "integrations" / "codex").mkdir(parents=True)
        (scratch / "agents").mkdir()
        (scratch / "providers").mkdir()
        # A forbidden network import, a provider module outside the allowlist, a
        # Router import, a forbidden literal, a reimplemented transport, a
        # credential source held outside the composition root, and a reverse
        # dependency.
        (scratch / "integrations" / "codex" / "leaky.py").write_text(
            "import urllib.request\n"
            "from providers.metrics import MetricAggregator\n"
            "from routing.router import evaluate\n"
            "X = 'SecurityLab/'\n"
            "class MyTransport:\n"
            "    pass\n"
            "def hold(environ=None):\n"
            "    return environ\n",
            encoding="utf-8",
        )
        (scratch / "agents" / "reverse.py").write_text(
            "from integrations.codex.backend import MimoCodexBackend\n",
            encoding="utf-8",
        )

        original = module.ROOT
        module.ROOT = scratch
        try:
            problems = module.check_ai09_integration_layer()
        finally:
            module.ROOT = original

        assert problems, "the AI-09 gate reported nothing for a violated tree"
        joined = " ".join(problems)
        assert "urllib.request" in joined
        assert "providers.metrics" in joined
        assert "routing.router" in joined
        assert "SecurityLab/" in joined
        assert "MyTransport" in joined
        assert "environ" in joined
        assert "reverse.py" in joined

    def test_the_gate_reports_a_missing_layer(self, tmp_path):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "layer0_policy_under_test_missing", "scripts/ci/layer0_policy.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        scratch = tmp_path / "empty"
        scratch.mkdir()
        original = module.ROOT
        module.ROOT = scratch
        try:
            problems = module.check_ai09_integration_layer()
        finally:
            module.ROOT = original

        assert problems
        assert any("integrations/ is absent" in problem for problem in problems)
