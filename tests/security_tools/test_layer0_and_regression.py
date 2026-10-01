"""T46 — regression, T47 — the Layer 0 gate.

T47 is the interesting one: it asserts that the AI-06 Layer 0 check exists, runs,
and **bites**. A gate nobody has watched fail is a gate nobody knows works.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

pytestmark = pytest.mark.layer1

LAYER0 = pathlib.Path("scripts/ci/layer0_policy.py")


def _layer0_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("layer0_for_test", LAYER0)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestT47TheLayer0CheckExists:
    def test_the_check_is_defined(self):
        module = _layer0_module()

        assert hasattr(module, "check_security_tools_boundary")

    def test_the_check_is_wired_into_the_report(self):
        source = LAYER0.read_text(encoding="utf-8")

        assert '"security tools boundary and adapter families"' in source

    def test_the_check_passes_on_the_real_tree(self):
        module = _layer0_module()

        assert module.check_security_tools_boundary() == []

    def test_layer0_runs_green(self):
        completed = subprocess.run(
            [sys.executable, str(LAYER0)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "Layer 0 = PASS" in completed.stdout


class TestT47TheLayer0CheckBites:
    """Each mutation is applied to a copy and the check must find it.

    A check that only ever sees a clean tree is a check nobody has watched fail,
    and §33 requires the opposite: the fixture is mutated, and the gate has to
    notice.
    """

    @pytest.fixture
    def copied_tree(self, tmp_path):
        import shutil

        for name in ("plugins", "tools", "providers", "scripts"):
            shutil.copytree(name, tmp_path / name, dirs_exist_ok=True)
        (tmp_path / "pytest.ini").write_text(
            pathlib.Path("pytest.ini").read_text(encoding="utf-8"), encoding="utf-8"
        )
        return tmp_path

    def _check(self, root: pathlib.Path):
        """Run the real check against the copied tree, not the imported one.

        The check's behavioural half imports `plugins.security_tools` and
        `tools`. Those are already in `sys.modules` from the real tree by the
        time a test runs, so without this the check would inspect the clean
        package on every mutation and report a vacuous pass. The copy is put
        first on the path and the AI-06 modules are dropped, so what the check
        imports is what was mutated.
        """
        import importlib.util

        saved_path = list(sys.path)
        saved_modules = {
            name: module
            for name, module in sys.modules.items()
            if name.split(".")[0] in {"plugins", "tools"}
        }
        for name in saved_modules:
            del sys.modules[name]
        sys.path.insert(0, str(root.resolve()))
        try:
            spec = importlib.util.spec_from_file_location(
                "layer0_mutated", root / "scripts/ci/layer0_policy.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.ROOT = root.resolve()
            return module.check_security_tools_boundary()
        finally:
            sys.path[:] = saved_path
            for name in [n for n in sys.modules if n.split(".")[0] in {"plugins", "tools"}]:
                del sys.modules[name]
            sys.modules.update(saved_modules)

    def _mutate(self, root: pathlib.Path, relative: str, old: str, new: str) -> None:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        assert old in text, f"the mutation target moved in {relative}"
        path.write_text(text.replace(old, new), encoding="utf-8")

    def test_an_unmutated_copy_is_clean(self, copied_tree):
        assert self._check(copied_tree) == []

    def test_a_shell_is_caught(self, copied_tree):
        self._mutate(
            copied_tree,
            "plugins/security_tools/runner.py",
            "shell=False,  # stated rather than defaulted, and not parameterised",
            "shell=True,",
        )

        fired = self._check(copied_tree)

        assert any("shell" in problem for problem in fired), fired

    def test_a_git_write_operation_is_caught(self, copied_tree):
        self._mutate(copied_tree, "tools/git/__init__.py", 'name="log",', 'name="push",')

        fired = self._check(copied_tree)

        assert any("write operation" in problem for problem in fired), fired

    def test_a_ninth_family_is_caught(self, copied_tree):
        self._mutate(
            copied_tree,
            "plugins/security_tools/vocabulary.py",
            '    REVERSE_ENGINEERING = "reverse_engineering"',
            '    REVERSE_ENGINEERING = "reverse_engineering"\n    WIRESHARK = "wireshark"',
        )

        fired = self._check(copied_tree)

        assert any("eight" in problem for problem in fired), fired

    def test_a_network_operation_is_caught(self, copied_tree):
        self._mutate(
            copied_tree,
            "plugins/security_tools/descriptor.py",
            "    network: bool = False",
            "    network: bool = True",
        )

        fired = self._check(copied_tree)

        assert any("network-capable" in problem for problem in fired), fired

    def test_a_whole_environment_is_caught(self, copied_tree):
        self._mutate(
            copied_tree,
            "plugins/security_tools/adapter.py",
            "    environment.update(invocation.environment)",
            "    environment.update(invocation.environment)\n    environment = dict(os.environ)",
        )

        fired = self._check(copied_tree)

        assert any("parent environment" in problem for problem in fired), fired

    def test_securitylab_is_caught(self, copied_tree):
        path = copied_tree / "tools/git/__init__.py"
        path.write_text(
            path.read_text(encoding="utf-8") + '\nX = "Li20771/SecurityLab"\n',
            encoding="utf-8",
        )

        fired = self._check(copied_tree)

        assert any("SecurityLab" in problem for problem in fired), fired

    def test_subprocess_outside_the_runner_is_caught(self, copied_tree):
        path = copied_tree / "plugins/security_tools/dispatch.py"
        path.write_text(
            path.read_text(encoding="utf-8") + "\nimport subprocess\n", encoding="utf-8"
        )

        fired = self._check(copied_tree)

        assert any("subprocess" in problem for problem in fired), fired

    def test_a_real_vehicle_target_is_caught(self, copied_tree):
        """The behavioural half: a boundary that stopped refusing.

        The mutation removes the gate entirely rather than weakening one of its
        branches. Disabling a single check is correctly *not* detected, because
        the remaining checks still refuse a physical target — which is the
        defence in depth working, and a mutation that leaves the property intact
        should leave the gate silent.
        """
        self._mutate(
            copied_tree,
            "plugins/security_tools/guards.py",
            "def check_v1_target_boundary(request: ToolRequest, spec: Any) -> None:",
            "def check_v1_target_boundary(request: ToolRequest, spec: Any) -> None:\n    return  # mutated away",
        )

        fired = self._check(copied_tree)

        assert any("real vehicle target" in problem for problem in fired), fired


class TestT46Regression:
    def test_the_pre_existing_layers_are_untouched(self):
        """AI-02/03/04/05 are not AI-06's to modify."""
        changed = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()

        for path in changed:
            assert not path.startswith("providers/"), path
            assert not path.startswith("plugins/context/"), path
            assert not path.startswith("plugins/guard/"), path
            assert not path.startswith("plugins/evidence/"), path
            assert not path.startswith("tests/evidence/"), path
            assert not path.startswith("tests/guard/"), path
            assert not path.startswith("routing/"), path
            assert not path.startswith("SecurityLab/"), path

    def test_the_ai06_package_imports_without_the_adapters(self):
        """F-14's one-way dependency: the plugin stands alone."""
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import plugins.security_tools as s; print(len(s.__all__))",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr

    def test_no_module_in_the_plugin_reaches_the_adapters(self):
        for path in sorted(pathlib.Path("plugins/security_tools").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name.split(".")[0] != "tools", path.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] != "tools", path.name
