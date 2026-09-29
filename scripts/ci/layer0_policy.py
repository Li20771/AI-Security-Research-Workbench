"""Layer 0 — repository policy.

Contract §12.1. Checks the repository and the CI configuration itself, not
Python behaviour, which is why it is a script rather than a pytest module.

It is the only layer that can prove things about the CI configuration, so it is
where two guarantees live:

- **the default workflow cannot reach a provider.** No live-test invocation, no
  provider endpoint, no HTTP client, no opt-in flag. The barrier is that CI
  never calls Layer 4 — not that the network happens to be unreachable.
- **no test module escapes the layer partition.** Every test module carries
  exactly one layer marker, so nothing can silently belong to no layer and be
  skipped by every CI step.

Exit 0 = all checks passed; 1 = at least one failed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = (
    "README.md",
    "docs/MASTER_ROADMAP.md",
    "docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md",
    "docs/GIT_AND_SECURITY_BOUNDARY.md",
    "docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md",
    ".gitignore",
    ".env.example",
    "config/providers/providers.example.yaml",
    "pytest.ini",
)

SHELL_SCRIPTS = (
    "scripts/bootstrap/preflight.sh",
    "tests/unit/test_repository_layout.sh",
)

SECRET_FILE_GLOBS = ("*.pem", "*.key", "*.p12", "*.pfx")

#: Files that must never be committed, whatever else is true.
FORBIDDEN_TRACKED = (".env", "credentials.json")

#: Key-shaped strings. Nothing shipped may contain one.
CREDENTIAL_SHAPED = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}")

#: Provider endpoints. A workflow has no reason to name one, so a mention is
#: itself the finding -- there is no benign prose that needs to.
LIVE_ENDPOINT_HOSTS = ("api.deepseek.com", "api.xiaomimimo.com")

#: Opting into live verification means *assigning* the flag, not mentioning it.
#: A workflow is allowed to explain that the flag is absent.
LIVE_OPT_IN_ASSIGNMENT = re.compile(
    r"WORKBENCH_LIVE_TESTS\s*[:=]\s*(?P<value>\S*)"
)

#: Selecting layer 4 explicitly is the other way in.
LIVE_SELECTION = re.compile(r"-m\s*['\"]?layer4")

LIVE_HTTP_CLIENTS = ("curl ", "wget ", "Invoke-WebRequest", "requests.get", "httpx.")

#: Workflows that must never touch a provider. Held to the strict deny rules.
DEFAULT_WORKFLOWS = frozenset({"preflight.yml"})

#: Workflows permitted to contact a provider, under strict structural rules.
#: AI-02-B6 introduced the first one. Permission is granted by *satisfying
#: conditions*, never by a file merely existing -- a workflow that is not
#: classified here is a finding, not an allowance.
LIVE_WORKFLOWS = frozenset({"live-model-verification.yml"})

#: The only trigger a live workflow may declare. Stated positively: the
#: question is not "does this list a forbidden trigger" but "is
#: workflow_dispatch the only one", so a trigger nobody thought to deny
#: (workflow_call, repository_dispatch, merge_group, ...) is still a finding.
LIVE_ALLOWED_TRIGGERS = frozenset({"workflow_dispatch"})

#: Input names that would let a caller aim a probe at an arbitrary target or
#: supply a credential. The endpoint comes from the provider profile and the
#: credential from repository secrets; neither is a caller's to choose (§7).
FORBIDDEN_LIVE_INPUTS = (
    "base_url",
    "base-url",
    "endpoint",
    "api_url",
    "api-url",
    "host",
    "url",
    "api_key",
    "api-key",
    "apikey",
    "secret",
    "token",
    "password",
)


def _strip_full_line_comments(text: str) -> str:
    """Drop whole-line comments.

    A comment cannot execute, and a workflow should be free to document what it
    deliberately does *not* do without tripping its own guard. Trailing
    comments are left alone: stripping those reliably needs a YAML parser, and
    a false positive there is safer than a missed assignment.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )

WORKFLOW_DIR = ROOT / ".github" / "workflows"

LAYER_MARKER = re.compile(r"^pytestmark = pytest\.mark\.(layer[0-9]+)\s*$", re.MULTILINE)
#: Layers a test module may declare. layer4 is markable so that the live
#: entry point can exist; pytest.ini deselects it from every default run.
MARKABLE_LAYERS = {"layer1", "layer2", "layer3", "layer4"}


def _display(path: Path) -> str:
    """A short label for a path, inside the repository or not.

    `relative_to` raises for a path outside ROOT, and a checker that crashes on
    an unexpected layout reports nothing useful about it.
    """
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, name: str, problems: list[str]) -> None:
        self.checks += 1
        if problems:
            self.failures.extend(f"{name}: {problem}" for problem in problems)
            print(f"  FAIL  {name}")
        else:
            print(f"  ok    {name}")


def check_required_files() -> list[str]:
    return [f"missing {name}" for name in REQUIRED_FILES if not (ROOT / name).is_file()]


def check_repository_layout() -> list[str]:
    # Relative posix path with cwd set: a Windows-style absolute path loses its
    # backslashes when handed to bash, which then cannot find the file.
    result = subprocess.run(
        ["bash", "tests/unit/test_repository_layout.sh"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return [(result.stdout + result.stderr).strip() or "layout check failed"]
    return []


def check_no_secret_files() -> list[str]:
    problems = []
    for name in FORBIDDEN_TRACKED:
        if (ROOT / name).exists():
            problems.append(f"{name} is present")
    for pattern in SECRET_FILE_GLOBS:
        for path in ROOT.rglob(pattern):
            if ".git" not in path.parts:
                problems.append(f"{path.relative_to(ROOT)} is present")
    return problems


def check_env_not_tracked() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        return [".env is tracked by git"]
    return []


def check_shell_syntax() -> list[str]:
    problems = []
    for name in SHELL_SCRIPTS:
        result = subprocess.run(
            ["bash", "-n", name],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            problems.append(f"{name}: {(result.stderr or '').strip()}")
    return problems


def check_example_configs_have_no_credentials() -> list[str]:
    """§12.1: example configs contain no credential *values*."""
    problems = []
    config_dir = ROOT / "config"
    for path in sorted(config_dir.rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for match in CREDENTIAL_SHAPED.findall(text):
            problems.append(
                f"{path.relative_to(ROOT)} contains a credential-shaped value "
                f"{match!r}; example configs carry references, never values"
            )
    return problems


def check_workflow_cannot_reach_a_provider() -> list[str]:
    """The default workflow must not be able to run Layer 4.

    Asserted against the workflow files rather than against network
    reachability: a firewall is not a policy, and "the endpoint was
    unreachable" is not evidence that a live test was never attempted.
    """
    problems = []
    workflows = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    if not workflows:
        return ["no workflow files found"]

    # Every workflow is classified before it is checked. An unclassified file
    # would otherwise be scanned under no rules at all, which is how a live
    # invocation could slip into the default pipeline unnoticed.
    for path in workflows:
        if path.name not in DEFAULT_WORKFLOWS | LIVE_WORKFLOWS:
            problems.append(
                f"{_display(path)} is not classified as a default or live "
                "workflow; declare it in DEFAULT_WORKFLOWS or LIVE_WORKFLOWS "
                "so it is checked under the right rules"
            )

    for path in workflows:
        if path.name not in DEFAULT_WORKFLOWS:
            continue
        text = _strip_full_line_comments(path.read_text(encoding="utf-8"))
        name = _display(path)

        for host in LIVE_ENDPOINT_HOSTS:
            if host in text:
                problems.append(
                    f"{name} names the provider endpoint {host!r}; CI performs "
                    "no network I/O (§11.1)"
                )

        # Assigning the flag is what opts in. Mentioning it is not.
        for match in LIVE_OPT_IN_ASSIGNMENT.finditer(text):
            if match.group("value").strip() not in ("", '""', "''"):
                problems.append(
                    f"{name} sets WORKBENCH_LIVE_TESTS; the default workflow "
                    "must not opt into live verification (§11.3)"
                )

        if LIVE_SELECTION.search(text):
            problems.append(
                f"{name} selects layer 4 explicitly; live checks are opt-in and "
                "never part of the default gate (§12.6)"
            )

        for client in LIVE_HTTP_CLIENTS:
            if client in text:
                problems.append(
                    f"{name} uses an HTTP client ({client!r}); CI performs no "
                    "network I/O"
                )

        # An API key may only ever be assigned the empty string.
        for var in ("DEEPSEEK_API_KEY", "MIMO_API_KEY"):
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith(f"{var}:"):
                    value = stripped.split(":", 1)[1].strip()
                    if value not in ('""', "''", ""):
                        problems.append(
                            f"{name} assigns a non-empty {var}; CI must require "
                            "no credential"
                        )
    return problems


def _trigger_keys(text: str) -> list[str]:
    """The direct children of the `on:` block, or [] when there is none.

    A scalar or flow-style trigger (`on: push`, `on: [push]`) has no block, so
    it yields nothing -- which the caller reads as "not dispatch-only" rather
    than as "no triggers".
    """
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.rstrip() == "on:"), None
    )
    if start is None:
        return []
    base: int | None = None
    keys: list[str] = []
    for line in lines[start + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            break
        if base is None:
            base = indent
        if indent != base:
            continue
        keys.append(line.strip().split(":", 1)[0].strip())
    return keys


def check_workflow_opt_in_flags() -> list[str]:
    """The opt-in flag exists in exactly the live workflows.

    Both directions matter: a default workflow that set it would turn the
    default pipeline live, and a live workflow that did not set it would not be
    opt-in at all.
    """
    problems = []
    for path in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        text = _strip_full_line_comments(path.read_text(encoding="utf-8"))
        name = _display(path)
        assigned = any(
            match.group("value").strip() not in ("", '""', "''")
            for match in LIVE_OPT_IN_ASSIGNMENT.finditer(text)
        )
        if path.name in DEFAULT_WORKFLOWS and assigned:
            problems.append(
                f"{name} sets WORKBENCH_LIVE_TESTS; a default workflow must "
                "never enable live verification (§11.4)"
            )
        if path.name in LIVE_WORKFLOWS and not assigned:
            problems.append(
                f"{name} does not set WORKBENCH_LIVE_TESTS; the live workflow "
                "is the opt-in boundary and must enable it explicitly"
            )
    return problems


def check_live_workflow_is_manual_and_bounded() -> list[str]:
    """A live workflow is permitted only under strict structural conditions.

    Permission comes from satisfying these, not from the file existing. The
    alternative -- "a workflow that mentions a live API is allowed" -- would
    let any workflow reach a provider by naming one.
    """
    problems = []
    for path in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        if path.name not in LIVE_WORKFLOWS:
            continue
        name = _display(path)
        text = _strip_full_line_comments(path.read_text(encoding="utf-8"))

        triggers = _trigger_keys(text)
        if "workflow_dispatch" not in triggers:
            problems.append(
                f"{name} does not declare workflow_dispatch; live verification "
                "is started by a human"
            )
        extra = sorted(set(triggers) - LIVE_ALLOWED_TRIGGERS)
        if extra:
            problems.append(
                f"{name} declares trigger(s) {', '.join(extra)}; a live "
                "workflow is workflow_dispatch ONLY, because any other trigger "
                "lets it contact a provider without a human starting it"
            )

        for host in LIVE_ENDPOINT_HOSTS:
            if host in text:
                problems.append(
                    f"{name} names the provider endpoint {host!r}; the "
                    "endpoint comes from the provider profile and is never "
                    "written into a workflow (§7)"
                )

        for forbidden in FORBIDDEN_LIVE_INPUTS:
            if re.search(
                rf"^\s+{re.escape(forbidden)}\s*:", text, re.MULTILINE
            ):
                problems.append(
                    f"{name} accepts an input named {forbidden!r}; a caller "
                    "may not choose a probe's target or supply a credential (§7)"
                )

        if "contents: read" not in text:
            problems.append(
                f"{name} does not declare read-only permissions; a live run "
                "must be unable to write to the repository"
            )

        for writer in ("git commit", "git push", "git add "):
            if writer in text:
                problems.append(
                    f"{name} runs {writer!r}; a live run produces an artefact "
                    "and promotion is a reviewed human action (§22)"
                )
    return problems


def _run_block_lines(text: str) -> list[tuple[int, str]]:
    """Lines inside `run:` blocks, with 1-based line numbers.

    A `${{ ... }}` in an `env:` value is correct and safe: GitHub resolves it
    to a string before the shell ever sees it. The same expression interpolated
    into a `run:` block becomes shell syntax, which is the difference between
    passing an argument and executing one.
    """
    lines = text.splitlines()
    collected: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        # A step key is written either as  or as a list item ,
        # and a check that only matches the first form silently inspects
        # nothing while still reporting success.
        stripped = line.strip()
        if stripped.startswith("- "):
            stripped = stripped[2:].lstrip()
        if stripped.startswith("run:"):
            indent = len(line) - len(line.lstrip())
            index += 1
            while index < len(lines):
                nxt = lines[index]
                if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= indent:
                    break
                collected.append((index + 1, nxt))
                index += 1
            continue
        index += 1
    return collected


def check_live_workflow_inputs_cannot_become_shell() -> list[str]:
    """A dispatch input reaches the shell as a quoted variable, never as text.

    Also checks the two adjacent boundaries: a credential is scoped to the step
    that needs it, and an unexpected runner failure is not absorbed.
    """
    problems = []
    for path in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        if path.name not in LIVE_WORKFLOWS:
            continue
        name = _display(path)
        text = _strip_full_line_comments(path.read_text(encoding="utf-8"))

        for number, line in _run_block_lines(text):
            if "${{" in line:
                problems.append(
                    f"{name}:{number} interpolates a GitHub expression directly "
                    "into a run command; dispatch inputs must reach the shell "
                    "as quoted environment variables"
                )

        if "continue-on-error" in text:
            problems.append(
                f"{name} uses continue-on-error; an unexpected runner failure "
                "must fail the job rather than be absorbed"
            )

        lines = text.splitlines()
        steps_at = next(
            (i for i, line in enumerate(lines) if line.strip().startswith("steps:")),
            None,
        )
        if steps_at is None:
            continue
        for marker in ("_API_KEY", "API_TOKEN", "SECRET"):
            for i, line in enumerate(lines):
                if marker in line and i < steps_at:
                    problems.append(
                        f"{name}:{i + 1} references {marker!r} before any step; a "
                        "credential must be scoped to the step that uses it, "
                        "not the job"
                    )
    return problems


def check_layer_markers() -> list[str]:
    """Every test module belongs to exactly one layer.

    Without this, a module with no marker would run in no layer step and its
    tests would be silently skipped by every CI invocation.
    """
    problems = []
    modules = sorted((ROOT / "tests").rglob("test_*.py"))
    if not modules:
        return ["no test modules found"]

    for path in modules:
        text = path.read_text(encoding="utf-8")
        markers = LAYER_MARKER.findall(text)
        name = _display(path)
        if not markers:
            problems.append(f"{name} declares no layer marker")
        elif len(markers) > 1:
            problems.append(f"{name} declares {len(markers)} layer markers")
        elif markers[0] not in MARKABLE_LAYERS:
            problems.append(
                f"{name} declares {markers[0]!r}; layers 1-3 are markable here"
            )
    return problems


def check_pytest_excludes_layer4() -> list[str]:
    problems = []
    config = ROOT / "pytest.ini"
    text = config.read_text(encoding="utf-8")
    if "not layer4" not in text:
        problems.append(
            "pytest.ini does not deselect layer4, so a live test would run by "
            "default if one were ever added"
        )
    for layer in sorted(MARKABLE_LAYERS):
        if f"{layer}:" not in text:
            problems.append(f"pytest.ini does not register the {layer} marker")
    return problems


def main() -> int:
    print("Layer 0 - repository policy")
    report = Report()
    report.check("required files", check_required_files())
    report.check("repository layout", check_repository_layout())
    report.check("no secret files", check_no_secret_files())
    report.check(".env not tracked", check_env_not_tracked())
    report.check("shell syntax", check_shell_syntax())
    report.check(
        "example configs carry no credential values",
        check_example_configs_have_no_credentials(),
    )
    report.check(
        "default workflows cannot reach a provider",
        check_workflow_cannot_reach_a_provider(),
    )
    report.check("workflow opt-in flags", check_workflow_opt_in_flags())
    report.check(
        "live workflow is manual and bounded",
        check_live_workflow_is_manual_and_bounded(),
    )
    report.check(
        "live inputs cannot become shell, secrets are step-scoped",
        check_live_workflow_inputs_cannot_become_shell(),
    )
    report.check("pytest excludes layer 4", check_pytest_excludes_layer4())
    report.check("every test module declares one layer", check_layer_markers())

    if report.failures:
        print("\nLayer 0 = FAIL", file=sys.stderr)
        for failure in report.failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"\nLayer 0 = PASS ({report.checks} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
