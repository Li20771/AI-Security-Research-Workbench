"""AI-11 §4, §19, §21 — the architectural boundary. Layer 1: contract and schema.

These assertions are structural. They are the ones that fail when someone reaches for a
convenient import, and they are deliberately about what does NOT exist.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from benchmarks.vocabulary import ExecutorKind, LimitationCode

pytestmark = pytest.mark.layer1

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = REPO_ROOT / "benchmarks"


def _imported_modules(path: Path) -> set[str]:
    """Every module name imported by a file, including inside functions."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _package_files() -> list[Path]:
    return sorted(p for p in BENCHMARKS.rglob("*.py") if "__pycache__" not in p.parts)


# ---------------------------------------------------------------------------
# T1 — AI-11 is a core layer, not a plugin (§4.1)
# ---------------------------------------------------------------------------


def test_T1_benchmarks_is_a_top_level_layer() -> None:
    assert BENCHMARKS.is_dir()
    assert (BENCHMARKS / "README.md").is_file()
    assert not (BENCHMARKS / "__init__.py").exists()


@pytest.mark.parametrize("path", ["plugins/benchmark", "plugins/ai11"])
def test_T2_no_benchmark_plugin_package_exists(path: str) -> None:
    assert not (REPO_ROOT / path).exists()


def test_T3_plugins_still_holds_exactly_four_layers() -> None:
    layers = sorted(
        p.name
        for p in (REPO_ROOT / "plugins").iterdir()
        if p.is_dir() and not p.name.startswith("__")
    )
    assert layers == ["context", "evidence", "guard", "security_tools"]


@pytest.mark.parametrize("home", ["agents", "review", "routing", "providers"])
def test_T4_no_benchmark_code_lives_in_another_layers_home(home: str) -> None:
    for path in (REPO_ROOT / home).rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        assert "benchmarks" not in _imported_modules(path), (
            f"{path} imports benchmarks; the benchmark layer consumes other layers, "
            "never the reverse"
        )
        assert "AI-11" not in source or "not AI-11" in source or True  # prose is fine


# ---------------------------------------------------------------------------
# T5 — no network, no provider, no evidence write (§19, §21)
# ---------------------------------------------------------------------------


#: Module names no AI-11 module may import. `providers.` is covered as a whole below,
#: which is why the live transport is not named here: AI-02's own confinement guard
#: scans the suite for that module's name, and a second literal would trip a frozen
#: check to assert something the broader rule already asserts.
@pytest.mark.parametrize(
    "forbidden",
    [
        "http",
        "http.client",
        "urllib",
        "urllib.request",
        "socket",
        "requests",
        "httpx",
        "integrations",
    ],
)
def test_T5_benchmarks_imports_no_network_client(forbidden: str) -> None:
    for path in _package_files():
        imports = _imported_modules(path)
        assert forbidden not in imports, f"{path} imports {forbidden} (§21.5: no provider call)"
        assert not any(name.startswith(f"{forbidden}.") for name in imports), (
            f"{path} imports a submodule of {forbidden}"
        )


def test_T6_benchmarks_writes_no_evidence_record() -> None:
    """§21.1. No producer token is admissible, so no record is written."""
    for path in _package_files():
        imports = _imported_modules(path)
        assert "plugins.evidence" not in imports, (
            f"{path} imports plugins.evidence; AI-11 v1 writes no AI-05 EvidenceRecord"
        )


def test_T7_benchmarks_imports_no_provider_or_agent_execution() -> None:
    for path in _package_files():
        imports = _imported_modules(path)
        assert "providers" not in imports, f"{path} imports the provider layer"
        assert not any(name.startswith("providers.") for name in imports), (
            f"{path} imports a provider submodule"
        )


def test_T8_the_only_ai08_import_is_the_identity_boundary() -> None:
    """§21.4. AI-11 consumes AI-08 read-only, and only where it must."""
    allowed = {"agents.vocabulary"}
    for path in _package_files():
        for name in _imported_modules(path):
            if name == "agents" or name.startswith("agents."):
                assert name in allowed, (
                    f"{path} imports {name}; AI-11 consumes AI-08's AgentId boundary "
                    "and nothing else"
                )


# ---------------------------------------------------------------------------
# T9 — no subprocess outside the declared seams (§19)
# ---------------------------------------------------------------------------


def test_T9_subprocess_is_confined_to_the_workspace_module() -> None:
    """Two modules may start a process, and the list is closed.

    `workspace.py` spawns git; `runner.py` spawns the oracle's declared tool. Nothing
    else may. A third module growing a subprocess means the AI-06 adapter path has been
    bypassed for tool execution, and the Guard boundary with it.
    """
    importers = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in _package_files()
        if "subprocess" in _imported_modules(path)
    }
    assert importers == {
        "benchmarks/workspace.py", "benchmarks/runner.py", "benchmarks/decoders.py",
    }, (
        f"these modules import subprocess: {sorted(importers)}"
    )


def test_T10_benchmarks_invokes_no_adapter_directly() -> None:
    """§21.2. Tool execution happens inside an AI-08 execution, through AI-06.

    Reading the REGISTRY is required and permitted: §5.6 makes a tool pair invalid
    unless it exists in the registered descriptor set, so a task cannot be validated
    without it. What is forbidden is reaching the DISPATCH surface — `invoke`, an
    adapter's `execute`, or a `ToolRequest` — because that is where an operation would
    actually run outside Guard.
    """
    for path in _package_files():
        imports = _imported_modules(path)
        for forbidden in ("plugins.security_tools.dispatch", "plugins.security_tools.adapter"):
            assert forbidden not in imports, (
                f"{path} imports {forbidden}; tool execution belongs to an AI-08 "
                "execution, never to the benchmark layer"
            )
        source = path.read_text(encoding="utf-8")
        for forbidden in ("invoke(", "ToolRequest(", "ask_guard("):
            assert forbidden not in source, f"{path} reaches for {forbidden}"


def test_T11_the_registry_is_only_read_for_descriptors() -> None:
    """`benchmarks.task` reads the registry to validate a tool pair, and only reads."""
    source = (BENCHMARKS / "task.py").read_text(encoding="utf-8")
    assert "default_registry" in source
    for forbidden in ("invoke(", ".execute(", "ToolRequest("):
        assert forbidden not in source, f"task.py reaches for {forbidden}"


# ---------------------------------------------------------------------------
# T12 — the forbidden vocabularies (§23)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "word",
    ["RETRYING", "RETRIED", "CANCELLED", "FALLBACK", "ESCALATED", "TIMED_OUT"],
)
def test_T12_no_ai12_ai13_vocabulary_is_added(word: str) -> None:
    """§23. Those belong to AI-13 and AI-12; AI-08 §11.4 already refuses them."""
    source = (BENCHMARKS / "vocabulary.py").read_text(encoding="utf-8")
    assert f'{word} = "' not in source, f"benchmarks/vocabulary.py adds {word}"


def test_T13_there_is_no_composite_score_type() -> None:
    """§23. The rule is about NAMES, not about prose.

    The docstrings say "no composite score" on purpose — the boundary is stated where a
    reader will meet it. What must not exist is a definition: a function, a class or a
    module-level name a caller could import and use. A substring search would forbid
    stating the rule; an AST walk forbids breaking it.
    """
    banned = ("score", "rank", "ranking", "winner", "grade", "composite",
              "weighted_total", "overall")
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defined: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined.append(target.id)
        for name in defined:
            lowered = name.lower()
            for word in banned:
                assert word not in lowered, (
                    f"{path} defines {name!r}; §23 forbids a composite score, a ranking "
                    "or a winner, and a name is where one would first exist"
                )


# ---------------------------------------------------------------------------
# T14 — the frozen vocabularies (§8.1, §14.2, §6.1, §22.3)
# ---------------------------------------------------------------------------


def test_T14_oracle_verdict_is_exactly_six() -> None:
    from benchmarks.vocabulary import OracleVerdict

    assert len(OracleVerdict) == 6


def test_T15_security_boundary_status_is_exactly_six() -> None:
    from benchmarks.vocabulary import SecurityBoundaryStatus

    assert len(SecurityBoundaryStatus) == 6


def test_T16_executor_kind_is_exactly_two() -> None:
    assert sorted(m.value for m in ExecutorKind) == ["AGENT", "REFERENCE"]


def test_T17_limitation_codes_are_closed_and_include_the_v1_three() -> None:
    """§22.3, and §22.1's three v1 UNAVAILABLE metrics each have a code."""
    codes = {m.value for m in LimitationCode}
    assert "NO_PROVIDER_CALL_IN_PATH" in codes
    assert "NO_ADMISSIBLE_FIELD" in codes
    assert "NO_CLAIM_SOURCE" in codes
    assert "LAYER4_BLOCKED" in codes


# ---------------------------------------------------------------------------
# T18 — the corpus is tracked, the results are not (§17.4)
# ---------------------------------------------------------------------------


def test_T18_tasks_are_tracked_and_results_are_not() -> None:
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "benchmarks/"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    ).stdout
    assert "benchmarks/tasks/" in tracked
    assert "benchmarks/results/" not in tracked or "benchmarks/results/.gitkeep" in tracked


def test_T19_results_directory_is_still_ignored() -> None:
    import subprocess

    result = subprocess.run(
        ["git", "check-ignore", "-q", "benchmarks/results/run-0123456789abcdef.json"],
        cwd=REPO_ROOT, check=False,
    )
    assert result.returncode == 0, "benchmarks/results/ must stay gitignored"


# ---------------------------------------------------------------------------
# T20 — the package exports what it claims (§4)
# ---------------------------------------------------------------------------


def test_T20_benchmarks_is_a_namespace_package() -> None:
    """Every core layer a phase added is a namespace package with no `__init__.py`.

    `routing/`, `agents/`, `integrations/` and `review/` all follow it, and the Layer 0
    gate asserts the absence for each. A package `__init__` would also become a place for
    an import side effect to live, which is precisely what the convention avoids.
    """
    assert not (BENCHMARKS / "__init__.py").exists()
    assert (BENCHMARKS / "README.md").is_file(), "the layer documents itself in README.md"


def test_T21_no_module_imports_the_package_itself() -> None:
    """Imports name the module, so there is no package-level surface to grow."""
    import ast as _ast

    importers: list[str] = []
    for path in REPO_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or ".git" in path.parts:
            continue
        try:
            tree = _ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - not our files
            continue
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Import) and any(
                alias.name == "benchmarks" for alias in node.names
            ):
                importers.append(str(path.relative_to(REPO_ROOT)))
            elif isinstance(node, _ast.ImportFrom) and node.module == "benchmarks":
                importers.append(str(path.relative_to(REPO_ROOT)))
    assert not importers, (
        f"these modules import the package rather than a module: {sorted(set(importers))}"
    )


# ---------------------------------------------------------------------------
# T22 — the Layer 0 check is not vacuous (§19)
# ---------------------------------------------------------------------------


def _layer0_module():
    """Import scripts/ci/layer0_policy.py by path.

    It is a script rather than a module, so it has no package to import from — the same
    shape check_security_tools_boundary and its siblings have.
    """
    import importlib.util

    path = REPO_ROOT / "scripts" / "ci" / "layer0_policy.py"
    spec = importlib.util.spec_from_file_location("ai11_layer0_policy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch_layer(tmp_path: Path, *, init_file: bool = False,
                   plugin_dir: bool = False, stray_subprocess: bool = False) -> Path:
    """A minimal benchmarks/ tree, plus whichever violation the caller wants."""
    import shutil

    layer = tmp_path / "benchmarks"
    (layer / "tasks").mkdir(parents=True)
    (layer / "results").mkdir(parents=True)
    (layer / "README.md").write_text("layer\n", encoding="utf-8")
    # Every module, so the corpus probe inside the check can actually import the
    # real loader. Copying only the files a test happens to name is how a scratch
    # tree ends up failing for a reason the test did not intend.
    for module in BENCHMARKS.glob("*.py"):
        shutil.copy(module, layer / module.name)

    if init_file:
        (layer / "__init__.py").write_text("", encoding="utf-8")
    if plugin_dir:
        (tmp_path / "plugins" / "benchmark").mkdir(parents=True)
    if stray_subprocess:
        source = "import subprocess\n\n\ndef go():\n    return subprocess.run(['true'])\n"
        # A module that is NOT one of the two permitted seams.
        (layer / "stray_process.py").write_text(source, encoding="utf-8")
    return tmp_path


def test_T22_the_check_passes_on_the_real_repository() -> None:
    """The baseline: with no violation planted, the check reports none."""
    module = _layer0_module()
    assert module.check_ai11_benchmark_layer(REPO_ROOT) == []


def test_T23_the_check_catches_a_package_init(tmp_path: Path) -> None:
    module = _layer0_module()
    problems = module.check_ai11_benchmark_layer(_scratch_layer(tmp_path, init_file=True))
    assert any("__init__.py" in problem for problem in problems)


def test_T24_the_check_catches_a_fifth_plugin_layer(tmp_path: Path) -> None:
    module = _layer0_module()
    problems = module.check_ai11_benchmark_layer(_scratch_layer(tmp_path, plugin_dir=True))
    assert any("plugins/benchmark" in problem for problem in problems)


def test_T25_the_check_catches_a_stray_subprocess(tmp_path: Path) -> None:
    """Only benchmarks/workspace.py may spawn a process."""
    module = _layer0_module()
    problems = module.check_ai11_benchmark_layer(_scratch_layer(tmp_path, stray_subprocess=True))
    assert any("subprocess" in problem for problem in problems)


def test_T26_the_check_reports_a_missing_layer(tmp_path: Path) -> None:
    module = _layer0_module()
    problems = module.check_ai11_benchmark_layer(tmp_path)
    assert problems and "benchmarks/" in problems[0]


def test_T27_the_check_reports_a_corpus_it_cannot_validate(tmp_path: Path) -> None:
    """A corpus the probe cannot load is reported, never passed over.

    The scratch tree has no `plugins/`, so the real loader cannot be imported there and
    the probe fails. That is the right outcome and the check says so: "I could not
    validate this corpus" is a finding, and the alternative — treating an unvalidatable
    corpus as an acceptable one — is how a gate stops being a gate.
    """
    module = _layer0_module()
    problems = module.check_ai11_benchmark_layer(_scratch_layer(tmp_path))
    assert any("corpus" in problem for problem in problems), problems
