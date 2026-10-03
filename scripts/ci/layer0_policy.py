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
    "docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md",
    "docs/AI-04_GUARD_EXECUTION_PLAN.md",
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

#: AI-05 §1.2: what the Evidence package may never reach, wherever it is used.
#: AI-06 §16: what the Tool layer may never reach.
#: AI-07 §14: the Router selects and never executes.
ROUTING_FORBIDDEN_IMPORTS = (
    "socket",
    "http",
    "urllib",
    "urllib3",
    "requests",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
    "asyncio",
    "multiprocessing",
    "subprocess",
    "shutil",
    "tools",
)

#: The ONE module under `plugins` that routing/ may import.
#:
#: `routing/request.py` imports `ActorType` and `PermissionLevel` from
#: `plugins.guard.vocabulary`, because §5.1 makes `sensitivity` AI-04's own
#: `PermissionLevel` and redefining it in `routing/` would be a second definition
#: of one vocabulary. That is a **frozen-vocabulary import**, not a Guard
#: implementation dependency: the Router never calls `evaluate`, never reads a
#: `DecisionRecord`, and never consults a policy.
#:
#: Checking the full module path is what makes "vocabulary only" checkable. An
#: earlier revision listed `plugins.guard` in a top-level-root list, where it
#: could never match, so the boundary was stated and not enforced.
ROUTING_ALLOWED_PLUGIN_IMPORTS = ("plugins.guard.vocabulary",)

ROUTING_FORBIDDEN_BUILTINS = ("eval", "exec", "compile", "__import__", "open")

#: AI-07 §10.2: the other workspace is not reachable from the Router.
ROUTING_FORBIDDEN_LITERALS = ("SecurityLab/", "Li20771/SecurityLab", "/mnt/d/SecurityLab")


SECURITY_TOOLS_FORBIDDEN_IMPORTS = (
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
    "asyncio",
    "multiprocessing",
    "routing",
)

SECURITY_TOOLS_FORBIDDEN_BUILTINS = ("eval", "exec", "compile", "__import__")

#: AI-06 §10.2: the other workspace is not a special case here.
SECURITY_TOOLS_FORBIDDEN_LITERALS = (
    "SecurityLab/",
    "Li20771/SecurityLab",
    "/mnt/d/SecurityLab",
)

#: AI-06 §13.1: v1 registers no git write.
SECURITY_TOOLS_GIT_WRITE_VERBS = (
    "commit", "push", "merge", "reset", "checkout", "rebase", "tag",
    "fetch", "pull", "clean", "stash", "branch_create", "remote",
)

#: AI-08 §15: v1 reaches no network and starts no process of its own.
#:
#: `subprocess` and `shutil` are here for the second half of that claim. The
#: Agent layer calls AI-03's `build_context`, which uses its own read-only git
#: reader — that subprocess belongs to AI-03 and AI-03's gate already covers it.
#: What this list forbids is `agents/` spawning anything itself.
#:
#: `routing`, `tools` and `plugins.evidence` are checked separately below,
#: because each of them needs a different explanation than "no network".
AGENTS_FORBIDDEN_IMPORTS = (
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
)

AGENTS_FORBIDDEN_BUILTINS = ("eval", "exec", "compile", "__import__")

#: AI-08 §17: the other workspace is not reachable from the Agent layer.
AGENTS_FORBIDDEN_LITERALS = (
    "SecurityLab/",
    "Li20771/SecurityLab",
    "/mnt/d/SecurityLab",
)

#: AI-09 §10.3: the integration layer composes two layers that must not know about
#: each other, and reaches a provider only through AI-02's invocation boundary.
#:
#: `os` is here for the second half of the enablement claim. Runtime enablement
#: comes from a parsed `ProviderConfig` the caller hands in, and a credential
#: comes from the provider layer's resolver — so the layer has no reason to read
#: the process environment at all, and forbidding the module is stronger than
#: forbidding the calls.
AI09_FORBIDDEN_IMPORTS = (
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

#: The only provider modules the integration layer may reach — an **allowlist**,
#: not a denylist. The live-only HTTP transport is therefore unreachable by
#: omission, exactly as AI-05's boundary treats it, and a module nobody thought
#: to list cannot be reached either.
AI09_ALLOWED_PROVIDER_IMPORTS = (
    "providers.config",
    "providers.invocation",
    "providers.model_profile",
    "providers.profile",
    "providers.protocol",
    "providers.transport",
)

#: The only plugin package it may reach. AI-03's context layer supplies the
#: `ContextResponse` and the canonical workspace primitive.
AI09_ALLOWED_PLUGIN_IMPORTS = ("plugins.context",)

#: Names that would mean the layer had taken over a job that is not its own:
#: resolving a credential, or reading the environment.
#:
#: AI-09 §13: the credential is resolved by the provider layer, and the
#: integration layer never sees it, holds it, or passes it.
#:
#: The credential *environment mapping* is the credential source, so holding it
#: is holding the credential even if nothing here reads a key. There is therefore
#: **no module of this layer that may bind it**: §10.1 makes `integrations/codex/`
#: the AI-09 boundary in its entirety, so a composition root placed inside it
#: would still be the integration layer holding the credential. The
#: credential-bearing context is assembled OUTSIDE this package and handed in as
#: an already-built `Invoker`, which is why `environ` is forbidden everywhere
#: here rather than excepted somewhere.
AI09_FORBIDDEN_NAMES = (
    "CredentialRef",
    "SecretValue",
    "environ",
    "environ.get",
    "getenv",
    "resolve",
)

AI09_FORBIDDEN_BUILTINS = ("eval", "exec", "compile", "__import__")

#: AI-09 §17: the other workspace is not reachable from the integration layer.
AI09_FORBIDDEN_LITERALS = (
    "SecurityLab/",
    "Li20771/SecurityLab",
    "/mnt/d/SecurityLab",
)

EVIDENCE_FORBIDDEN_IMPORTS = (
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
    "subprocess",
    "multiprocessing",
    "routing",
    "tools",
)

#: The only provider modules the Evidence package may reach — an **allowlist**,
#: not a denylist. AI-05 legitimately imports AI-02's frozen identity and status
#: types (§3: imported, not restated), and nothing else. Stating what is
#: permitted rather than what is forbidden is both tighter and honest about the
#: dependency: it cannot be defeated by a module nobody thought to list, and it
#: keeps the live-only transport out of AI-05 without this file having to name
#: the thing AI-02's own confinement guard reserves.
EVIDENCE_ALLOWED_PROVIDER_IMPORTS = (
    "providers.profile",
    "providers.model_profile",
    "providers.live_verification",
)

#: The modules that touch a filesystem. Everything else in `plugins/evidence`
#: is pure, which is what let B1's evidence record claim "no file I/O anywhere
#: in the package" and what keeps that claim true for eight of nine modules.
EVIDENCE_IO_MODULES = ("store.py",)

EVIDENCE_FILESYSTEM_IMPORTS = (
    "json",
    "os",
    "io",
    "pathlib",
    "shutil",
    "tempfile",
    "sqlite3",
    "pickle",
    "shelve",
    "dbm",
    "yaml",
)

EVIDENCE_FORBIDDEN_BUILTINS = ("eval", "exec", "compile", "__import__")

#: Strings the Store may not contain. AI-05 records what happened; it does not
#: write to the repository's contracts, its status documents, or its other
#: packages.
EVIDENCE_STORE_FORBIDDEN_LITERALS = ("docs/", "docs\\", "plugins/context", "plugins/guard")

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


#: The frozen read-only git command set, transcribed from AI-03 contract §7.4.
#: The plugin declares its own copy; this check asserts the declaration, so a
#: widening of the plugin's set is a CI failure rather than a quiet grant.
CONTEXT_GIT_READ_ONLY = frozenset(
    {"rev-parse", "symbolic-ref", "status", "log", "remote"}
)

#: Git invocations the reader must refuse. Bare subcommand names, plus the
#: argument forms of a subcommand that is read-only in one shape and a write in
#: another -- `git remote get-url` reads, `git remote add` rewrites
#: `.git/config`, and a guard that checks only the subcommand permits the
#: second.
GIT_WRITE_INVOCATIONS: tuple[tuple[str, ...], ...] = (
    ("add",),
    ("am",),
    ("apply",),
    ("branch",),
    ("checkout",),
    ("cherry-pick",),
    ("clean",),
    ("clone",),
    ("commit",),
    ("commit-tree",),
    ("config",),
    ("fetch",),
    ("filter-branch",),
    ("gc",),
    ("init",),
    ("merge",),
    ("mv",),
    ("prune",),
    ("pull",),
    ("push",),
    ("rebase",),
    ("reflog",),
    ("reset",),
    ("restore",),
    ("revert",),
    ("rm",),
    ("stash",),
    ("submodule",),
    ("switch",),
    ("tag",),
    ("update-index",),
    ("update-ref",),
    ("worktree",),
    ("write-tree",),
    ("remote", "add", "origin", "https://example.invalid/x.git"),
    ("remote", "remove", "origin"),
    ("remote", "set-url", "origin", "https://example.invalid/y.git"),
    ("remote", "prune"),
    ("remote", "update"),
    ("remote",),
)

#: Git invocations the reader must accept. The other direction matters as much:
#: a guard that refused everything would pass a refuse-only check while making
#: the plugin useless.
GIT_READ_INVOCATIONS: tuple[tuple[str, ...], ...] = (
    ("rev-parse", "HEAD"),
    ("rev-parse", "--show-toplevel"),
    ("symbolic-ref", "--short", "-q", "HEAD"),
    ("status", "--porcelain"),
    ("log", "--max-count=1"),
    ("remote", "get-url", "origin"),
    ("remote", "show"),
)


def check_context_plugin_performs_no_git_write() -> list[str]:
    """AI-03 contract §7.4: the Context plugin writes nothing to git.

    Checked by **executing the guard**, not by grepping for suspicious text.
    "We would never call `git commit`" is exactly the kind of guarantee that
    survives review and not a refactor, so the question this answers is the
    behavioural one: hand the reader every write verb and confirm each is
    refused before a process could exist.

    Two things are asserted: the plugin's declared read-only set is the frozen
    one, and every write verb is refused by the real reader.
    """
    package = ROOT / "plugins" / "context"
    if not package.is_dir():
        return []  # AI-03 not present yet; the required-files check owns that

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    try:
        from plugins.context.errors import GitCommandRefused
        from plugins.context.workspace import (
            READ_ONLY_GIT_COMMANDS,
            SubprocessGitReader,
        )
    except ImportError as exc:  # pragma: no cover - surfaced as a failure
        return [f"plugins/context could not be imported: {exc}"]

    problems: list[str] = []

    if set(READ_ONLY_GIT_COMMANDS) != set(CONTEXT_GIT_READ_ONLY):
        problems.append(
            f"the plugin's read-only git set is {sorted(READ_ONLY_GIT_COMMANDS)}, "
            f"but AI-03 §7.4 freezes {sorted(CONTEXT_GIT_READ_ONLY)}"
        )

    reader = SubprocessGitReader()

    for invocation in GIT_WRITE_INVOCATIONS:
        try:
            # Refusal must come before any subprocess could be created. An
            # invocation that reached the process boundary would either be
            # refused by git itself or, worse, not refused at all.
            reader.run(ROOT, invocation)
        except GitCommandRefused:
            continue
        except Exception as exc:  # noqa: BLE001 - any other outcome is a finding
            problems.append(
                f"git {' '.join(invocation)!r} raised {type(exc).__name__} "
                "instead of being refused"
            )
            continue
        problems.append(
            f"git {' '.join(invocation)!r} was not refused by the read-only "
            "guard (§7.4)"
        )

    for invocation in GIT_READ_INVOCATIONS:
        try:
            reader.run(ROOT, invocation)
        except GitCommandRefused as exc:
            problems.append(
                f"git {' '.join(invocation)!r} is read-only but was refused: {exc}"
            )
        except Exception:  # noqa: BLE001 - a read that fails for another reason is fine
            # The command is permitted; whether it succeeds against this
            # directory is not what this check is about.
            pass

    return problems


def check_evidence_plugin_boundary() -> list[str]:
    """AI-05 §1.2, §13.4 and §31: the shape of the Evidence package, as a gate.

    §31 requires a Layer 0 structural check for `plugins/evidence`, mirroring
    `check_context_plugin_performs_no_git_write`. That one executes the guard;
    this one parses the package, because what it has to establish is an absence
    — and an absence that is only asserted in a document is the kind that
    survives review and not a refactor.

    Five things are checked, each of which was a real decision rather than a
    preference:

    ```text
    1  no network, no subprocess, no routing or tool import, anywhere
    2  filesystem imports only in store.py. Before B2-P3 the whole package was
       pure; the Store is the one module allowed to break that, and this is
       what keeps it to one.
    3  store.py — the module that does have file I/O — cannot reach the
       contract, the decision record or the rest of the repository by path.
       AI-05 has no business writing to docs/.
    4  the two durability tiers are laid out as D4 says: staged is ignored by
       git, promoted is not.
    5  no credential-shaped literal is shipped in the package.
    ```

    Parsed with `ast`, not matched as text. A grep would flag the documentation
    in these modules — which names every one of these hazards while explaining
    why it is absent — and a check that fires on its own rationale is a check
    that gets disabled.
    """
    import ast

    package = ROOT / "plugins" / "evidence"
    if not package.is_dir():
        return []  # AI-05 not present yet; the required-files check owns that

    problems: list[str] = []

    # (1) and (2), per module.
    for path in sorted(package.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - surfaced as a failure
            problems.append(f"{_display(path)} does not parse: {exc}")
            continue

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module)

        roots = {name.split(".")[0] for name in imported}
        for banned in EVIDENCE_FORBIDDEN_IMPORTS:
            if banned.split(".")[0] in roots and (
                "." not in banned or any(i.startswith(banned) for i in imported)
            ):
                problems.append(
                    f"{_display(path)} imports {banned!r}; AI-05 reaches no "
                    "network, spawns no process and routes nothing (§1.2)"
                )

        if path.name not in EVIDENCE_IO_MODULES:
            for io_root in EVIDENCE_FILESYSTEM_IMPORTS:
                if io_root in roots:
                    problems.append(
                        f"{_display(path)} imports {io_root!r}; only "
                        f"{', '.join(EVIDENCE_IO_MODULES)} may touch a "
                        "filesystem, and this module is not one of them"
                    )

        for name in sorted(imported):
            if name == "providers" or name.startswith("providers."):
                if not any(
                    name == allowed or name.startswith(f"{allowed}.")
                    for allowed in EVIDENCE_ALLOWED_PROVIDER_IMPORTS
                ):
                    problems.append(
                        f"{_display(path)} imports {name!r}; the Evidence package "
                        "may reach only "
                        f"{', '.join(EVIDENCE_ALLOWED_PROVIDER_IMPORTS)}, so a "
                        "transport or a provider client cannot be reached from "
                        "any default path (§1.2)"
                    )

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in EVIDENCE_FORBIDDEN_BUILTINS:
                    problems.append(
                        f"{_display(path)}:{node.lineno} calls {node.func.id}()"
                    )
                if node.func.id == "open" and path.name not in EVIDENCE_IO_MODULES:
                    problems.append(
                        f"{_display(path)}:{node.lineno} calls open(); the Store "
                        "owns the package's file I/O"
                    )

    # (3) the Store cannot name the repository's documents **in code**.
    #
    # Docstrings are excluded, and that exclusion is the point rather than a
    # convenience: these modules document the hazards they avoid, so `store.py`
    # names `docs/AI-05-B2_DECISIONS_2026-10-01.md` while explaining which
    # decisions it implements. A check that fired on its own rationale is a
    # check that gets turned off. Only a string a statement could *use* counts.
    store_source = (package / "store.py").read_text(encoding="utf-8")
    store_tree = ast.parse(store_source, filename="store.py")
    docstrings = {
        id(statement.value)
        for node in ast.walk(store_tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef))
        for statement in getattr(node, "body", [])[:1]
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    }
    for node in ast.walk(store_tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            for forbidden in EVIDENCE_STORE_FORBIDDEN_LITERALS:
                if forbidden in node.value:
                    problems.append(
                        f"plugins/evidence/store.py:{node.lineno} names "
                        f"{forbidden!r}; the Store writes under its root and "
                        "nowhere else, and never to the repository's documents"
                    )

    # (4) the D4 layout, as .gitignore actually declares it.
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    lines = {line.strip() for line in ignore.splitlines() if line.strip()}
    if "evidence/staged/*" not in lines:
        problems.append(
            "evidence/staged/* is not gitignored; D4 makes a staged record "
            "local and discardable, so it must not be committed"
        )
    if "!evidence/staged/.gitkeep" not in lines:
        problems.append(
            "evidence/staged/.gitkeep is not kept, so the tier directory "
            "cannot exist in a clone"
        )
    for pattern in ("evidence/promoted", "evidence/promoted/*"):
        if pattern in lines:
            problems.append(
                f".gitignore ignores {pattern!r}; a promoted record is durable "
                "via Git (D4, §20.4 D6) and must be tracked"
            )

    # (5) no credential-shaped literal.
    for path in sorted(package.glob("*.py")):
        match = CREDENTIAL_SHAPED.search(path.read_text(encoding="utf-8"))
        if match:
            problems.append(f"{_display(path)} contains a credential-shaped literal")

    return problems


def check_security_tools_boundary() -> list[str]:
    """AI-06 §3.2, §7.4, §9, §11, §12, §16: the Tool layer, as a gate.

    Parsed with `ast` **and** exercised, because the two catch different
    regressions:

    ```text
    structural   a `shell=True` that a reviewer would have to notice
    behavioural  a registry that stopped agreeing with the frozen vocabulary,
                 or a vehicle adapter that started accepting a real target
    ```

    A check that only read the source would pass a package whose registry had
    silently gained a write operation, and one that only ran behaviour would miss
    a shell path no test happens to take. Both run.
    """
    import ast

    package = ROOT / "plugins" / "security_tools"
    adapters = ROOT / "tools"
    if not package.is_dir():
        return ["plugins/security_tools is absent; AI-06 is not implemented"]

    problems: list[str] = []

    # (1) Structural: what the source can do.
    for path in sorted(package.glob("*.py")) + sorted(adapters.rglob("*.py")):
        if "__pycache__" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - surfaced as a failure
            problems.append(f"{_display(path)} does not parse: {exc}")
            continue

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        roots = {name.split(".")[0] for name in imported}
        for banned in SECURITY_TOOLS_FORBIDDEN_IMPORTS:
            if banned in roots:
                problems.append(
                    f"{_display(path)} imports {banned!r}; the Tool layer reaches "
                    "no network and routes nothing (§16)"
                )

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "shell":
                        is_false = (
                            isinstance(keyword.value, ast.Constant)
                            and keyword.value.value is False
                        )
                        if not is_false:
                            problems.append(
                                f"{_display(path)}:{node.lineno} passes a truthy "
                                "`shell`; §11.1 forbids a shell interpreter "
                                "outright and without exception"
                            )
                if isinstance(node.func, ast.Name) and node.func.id in SECURITY_TOOLS_FORBIDDEN_BUILTINS:
                    problems.append(
                        f"{_display(path)}:{node.lineno} calls {node.func.id}()"
                    )

        source = path.read_text(encoding="utf-8")
        if "import subprocess" in source and path.name != "runner.py":
            problems.append(
                f"{_display(path)} imports subprocess; runner.py is the one "
                "module in AI-06 that starts a process (§11)"
            )
        if "os.environ.copy()" in source or "dict(os.environ)" in source:
            problems.append(
                f"{_display(path)} passes the whole parent environment; §11.2 "
                "forbids it and §14.1 makes it a credential leak"
            )
        for needle in SECURITY_TOOLS_FORBIDDEN_LITERALS:
            if needle in source:
                problems.append(
                    f"{_display(path)} names {needle!r}; the other workspace is "
                    "not a special case and is not reachable from here (§10.2)"
                )

    # (2) Behavioural: what the registry and the adapters actually do.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    try:
        import tools as tools_package

        from plugins.security_tools import AdapterFamily
        from plugins.security_tools.vocabulary import V1_PERMITTED_VEHICLE_INTERFACES
    except ImportError as exc:  # pragma: no cover - surfaced as a failure
        return problems + [f"the AI-06 package could not be imported: {exc}"]

    registry = tools_package.default_registry()

    if len(AdapterFamily) != 8:
        problems.append(
            f"AdapterFamily has {len(AdapterFamily)} members; §5.3 freezes eight"
        )
    if registry.families != frozenset(AdapterFamily):
        missing = sorted(f.value for f in frozenset(AdapterFamily) - registry.families)
        problems.append(
            f"the default registry does not represent every family; missing: {missing}"
        )

    git_identity = next(
        (i for i in registry.identities if i.adapter_family is AdapterFamily.GIT), None
    )
    if git_identity is not None:
        declared = set(registry.capability_names(git_identity))
        writes = declared & set(SECURITY_TOOLS_GIT_WRITE_VERBS)
        if writes:
            problems.append(
                f"the git family registers write operation(s) {sorted(writes)}; "
                "§13.1 freezes v1 as read-only"
            )

    for descriptor in registry.descriptors():
        if descriptor.needs_network:
            problems.append(
                f"{descriptor.identity.tool_id} declares a network-capable "
                "operation; §16 forbids one in v1"
            )
        for spec in descriptor.operations:
            interface = spec.environment.vehicle_interface
            if interface not in {None, *V1_PERMITTED_VEHICLE_INTERFACES} and str(
                interface
            ) != "none":
                problems.append(
                    f"{descriptor.identity.tool_id}.{spec.name} declares vehicle "
                    f"interface {interface}; §12.1 permits vcan, simulator and "
                    "isolated_harness only"
                )

    # The vehicle adapter must refuse a real target, and a real target must not
    # be reachable by any declared operation.
    try:
        from plugins.security_tools.request import ToolRequest

        vehicle = next(
            (
                d
                for d in registry.descriptors()
                if d.identity.adapter_family is AdapterFamily.VEHICLE_NETWORK
            ),
            None,
        )
        if vehicle is not None:
            probe = ToolRequest.from_mapping(
                {
                    "schema_version": 1,
                    "workspace": {"workspace_id": "probe", "root": None},
                    "tool": vehicle.identity.to_mapping(),
                    "operation": vehicle.operations[0].name,
                    "arguments": {"interface": "can0", "frame": "1#2"},
                    "actor": {"id": "probe", "type": "service"},
                    "permission_level": "test",
                    "target": {
                        "kind": "vehicle",
                        "identifier": "can0",
                        "environment": "real",
                        "interface": "can",
                        "is_real": True,
                        "sensitivity": "internal",
                    },
                    "execution": {"timeout_seconds": 1, "environment": {}},
                }
            )
            from plugins.security_tools.guards import check_v1_target_boundary

            try:
                check_v1_target_boundary(probe, vehicle.operations[0])
            except Exception:  # noqa: BLE001 - a refusal is the expected outcome
                pass
            else:
                problems.append(
                    "the v1 target boundary accepted a real vehicle target; "
                    "§12.2 forbids it and this is the check that must fail first"
                )
    except Exception as exc:  # noqa: BLE001 - surfaced as a failure
        problems.append(f"the vehicle probe could not run: {exc}")

    return problems


def check_ai07_router_contract() -> list[str]:
    """AI-07 §1.1, §8, §13.2, §14, §16, §17: the Router, as a gate.

    Upgraded by AI-07-B from the contract-freeze absence check to an
    implementation boundary gate. Two halves, and they catch different
    regressions:

    ```text
    structural   what routing/ can reach -- no network, no subprocess, no Guard,
                 no Evidence, no tools, and no plugin packaging
    behavioural  what the Router actually does -- UNKNOWN does not satisfy a
                 capability, no rule set selects a default, and the tracked
                 default rule set carries no rule that was never authored
    ```

    What it must never become is a check that passes because there is nothing to
    check. During AI-07-A it asserted `routing/` contained no Python, which was
    the honest claim then; now it asserts what the Python may do.
    """
    import ast

    problems: list[str] = []

    routing = ROOT / "routing"
    plugins = ROOT / "plugins"

    if not routing.is_dir():
        return ["routing/ is absent; AI-07's declared home does not exist"]

    # (1) Identity: a core service, not a plugin layer (§1.1, §17).
    if (plugins / "router").exists():
        problems.append(
            "plugins/router/ exists; AI-07 is a Workbench core service and not a "
            "DSH plugin (§1.1, F-13)"
        )
    if (routing / "__init__.py").exists():
        problems.append(
            "routing/__init__.py exists; routing/ is a core-service directory and "
            "not a plugin package (§17)"
        )

    # (2) Structural: what routing/ may reach (§14, §30).
    for path in sorted(routing.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - surfaced as a failure
            problems.append(f"{_display(path)} does not parse: {exc}")
            continue

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        roots = {name.split(".")[0] for name in imported}
        for banned in ROUTING_FORBIDDEN_IMPORTS:
            if banned in roots:
                problems.append(
                    f"{_display(path)} imports {banned!r}; the Router selects and "
                    "does not execute (§14), and it authorizes nothing (§8)"
                )

        # The full module path, not the root: `plugins.guard.vocabulary` is
        # allowed and every other `plugins.*` module is not. Checking the root
        # alone would make the allowlist unenforceable, which is how the earlier
        # revision came to state a boundary it did not check.
        for name in sorted(imported):
            if not name.startswith("plugins."):
                continue
            if any(
                name == allowed or name.startswith(f"{allowed}.")
                for allowed in ROUTING_ALLOWED_PLUGIN_IMPORTS
            ):
                continue
            problems.append(
                f"{_display(path)} imports {name!r}; routing/ may import "
                f"{', '.join(ROUTING_ALLOWED_PLUGIN_IMPORTS)} and nothing else under "
                "plugins/. A frozen vocabulary import is not a Guard implementation "
                "dependency, and the Router never invokes Guard or Evidence (§8, §13)"
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "shell":
                        problems.append(
                            f"{_display(path)}:{node.lineno} passes a `shell` "
                            "keyword; AI-07 starts no process at all (§14)"
                        )
                if isinstance(node.func, ast.Name) and node.func.id in ROUTING_FORBIDDEN_BUILTINS:
                    problems.append(
                        f"{_display(path)}:{node.lineno} calls {node.func.id}()"
                    )

        source = path.read_text(encoding="utf-8")
        for needle in ROUTING_FORBIDDEN_LITERALS:
            if needle in source:
                problems.append(
                    f"{_display(path)} names {needle!r}; the other workspace is not "
                    "a special case and is not reachable from here"
                )

    # (3) The contract is still frozen as AI-07-A left it.
    contract = ROOT / "docs" / "AI-07_MODEL_ROUTER_EXECUTION_PLAN.md"
    if not contract.is_file():
        problems.append("docs/AI-07_MODEL_ROUTER_EXECUTION_PLAN.md is absent")
    else:
        frozen = contract.read_text(encoding="utf-8")
        # Amendment 1's four clauses plus the two v1 rules they sit beside.
        # Each is a rule AI-07-B would otherwise have had to invent its way past,
        # so each is checked rather than trusted.
        for phrase in (
            "Router NEVER grants permission",
            "AI-07 MUST NOT register a new AI-05 event",
            "UNKNOWN` is NOT `available",
            "`sensitivity` MUST NOT widen or narrow the candidate set in v1",
            "AI-07 v1 does NOT use it to change model eligibility",
            "cost-class routing is DEFERRED",
            "AI-07 MUST NOT invent a cost class",
            "AI-07 v1 has NO automatic fallback mechanism",
            "AI-07 does NOT retry a selected model",
            "and no nested decision",
            "MUST NOT assert that the hint identifies a VERIFIED",
        ):
            if phrase not in frozen:
                problems.append(
                    f"the AI-07 contract no longer freezes {phrase!r}; §6.2, §8 and "
                    "§13.2 are load-bearing and this check is what keeps them"
                )

    # (4) Behavioural: what the Router actually does.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from providers.model_registry import load_all_model_profiles

        from routing.profile import capability_is_available
        from routing.request import RouterRequest
        from routing.router import evaluate
        from routing.rules import RuleSet
        from routing.vocabulary import RoutingOutcome
    except ImportError as exc:  # pragma: no cover - surfaced as a failure
        return problems + [f"the AI-07 package could not be imported: {exc}"]

    profiles = load_all_model_profiles()

    # §6.2: UNKNOWN is not available. Asserted against every shipped profile,
    # so the rule is checked against the repository rather than a copy of it.
    try:
        from providers.model_profile import CapabilityName

        for ref, profile in profiles.items():
            for name in CapabilityName:
                if capability_is_available(profile, name):
                    problems.append(
                        f"{ref} reports {name} as VERIFIED and no provider call has "
                        "ever been made; §6.2 makes UNKNOWN unavailable, and a "
                        "VERIFIED status is a dated observation AI-02 owns"
                    )
    except Exception as exc:  # noqa: BLE001 - surfaced as a failure
        problems.append(f"the capability probe could not run: {exc}")

    # A capability requirement must not select, and a missing rule must not
    # produce an implicit default (§7.6).
    try:
        base = {
            "schema_version": 1,
            "task": {"task_class": "probe"},
            "workspace": {"workspace_id": "probe"},
            "actor": {"id": "probe", "type": "service"},
            "candidates": [{"model_ref": ref} for ref in sorted(profiles)],
        }
        empty = RuleSet.empty()
        plain = evaluate(RouterRequest.from_mapping(base), empty, profiles=profiles)
        if plain.outcome is not RoutingOutcome.NO_ELIGIBLE_MODEL:
            problems.append(
                "an empty rule set selected a model; §7.6 makes no matching rule "
                "NO_ELIGIBLE_MODEL and there is no implicit default"
            )

        first_ref = sorted(profiles)[0]
        one_rule = RuleSet.from_mapping(
            {
                "version": 1,
                "revision": "probe",
                "rules": [
                    {
                        "rule_id": "probe",
                        "priority": 0,
                        "reason_code": "PROBE",
                        "select": {"model_ref": first_ref},
                    }
                ],
            }
        )
        requiring = RouterRequest.from_mapping(
            {**base, "requested_capability": "tool_calling"}
        )
        outcome = evaluate(requiring, one_rule, profiles=profiles).outcome
        if outcome is RoutingOutcome.SELECTED:
            problems.append(
                "a capability requirement selected a model whose capability is "
                "UNKNOWN; §6.2 makes UNKNOWN unavailable"
            )
    except Exception as exc:  # noqa: BLE001 - surfaced as a failure
        problems.append(f"the routing probe could not run: {exc}")

    # (5) The tracked default rule set exists and carries no invented rule.
    default_rules = ROOT / "config" / "routing" / "default.rules.yaml"
    if not default_rules.is_file():
        problems.append("config/routing/default.rules.yaml is absent (§12.1)")
    else:
        text = default_rules.read_text(encoding="utf-8")
        try:
            import yaml

            parsed = yaml.safe_load(text) or {}
            if parsed.get("version") != 1:
                problems.append("the default rule set does not declare version 1")
            if not parsed.get("revision"):
                problems.append("the default rule set declares no revision (§12.3)")
            for entry in parsed.get("rules", []) or []:
                if "model_profile" in entry:
                    problems.append(
                        "the default rule set names a `model_profile`, which is the "
                        "roadmap's sketch rather than a model reference (§3.2)"
                    )
                select = entry.get("select", {}) or {}
                ref = select.get("model_ref")
                if ref is not None and ref not in profiles:
                    problems.append(
                        f"the default rule set selects {ref!r}, which AI-02 does not "
                        "register; §3.2 forbids inventing a profile to match the sketch"
                    )
        except Exception as exc:  # noqa: BLE001 - surfaced as a failure
            problems.append(f"the default rule set could not be read: {exc}")

    return problems


def check_ai08_agent_layer() -> list[str]:
    """AI-08 §17, §12, §13.1, §15: the Agent layer, as a gate.

    Two halves, and they catch different regressions:

    ```text
    structural   what agents/ can reach -- no network, no process, no Router,
                 no tool adapter package, and no AI-05 Evidence import
    identity     what agents/ is -- a core layer, not a plugin package
    ```

    What it must never become is a check that passes because there is nothing to
    check. During AI-08-A `agents/` held three placeholder READMEs, and the
    honest claim then was that a core layer existed; now it holds an execution
    runtime, and the check asserts what that runtime may do.
    """
    import ast

    problems: list[str] = []

    agents = ROOT / "agents"
    plugins = ROOT / "plugins"

    if not agents.is_dir():
        return ["agents/ is absent; AI-08's declared home does not exist"]

    # (1) Identity: a core layer, not a plugin layer (§17).
    for forbidden in ("agent", "codex", "dsh"):
        if (plugins / forbidden).exists():
            problems.append(
                f"plugins/{forbidden}/ exists; AI-08 is a Workbench core Agent "
                "layer and not a DSH plugin layer (§17). plugins/ holds exactly "
                "four layers, owned by AI-03, AI-04, AI-05 and AI-06"
            )
    if (agents / "__init__.py").exists():
        problems.append(
            "agents/__init__.py exists; agents/ is a core-layer directory reached "
            "as a namespace package, exactly as routing/ and tests/ are (§17)"
        )

    # (2) Structural: what agents/ may reach (§12, §13.1, §15).
    for path in sorted(agents.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - surfaced as a failure
            problems.append(f"{_display(path)} does not parse: {exc}")
            continue

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        for name in sorted(imported):
            root = name.split(".")[0]
            if root in AGENTS_FORBIDDEN_IMPORTS:
                problems.append(
                    f"{_display(path)} imports {name!r}; AI-08 v1 makes no network "
                    "call and starts no process of its own (§15)"
                )
            elif name == "routing" or name.startswith("routing."):
                problems.append(
                    f"{_display(path)} imports {name!r}; the Router selects and "
                    "AI-08 executes, and the dependency does not run backwards "
                    "(§6.3). An agent_hint stays a hint"
                )
            elif name == "tools" or name.startswith("tools."):
                problems.append(
                    f"{_display(path)} imports {name!r}; AI-08 reaches tools "
                    "through AI-06's dispatch, which asks Guard, rather than "
                    "through an adapter family directly (§12)"
                )
            elif name == "plugins.evidence" or name.startswith("plugins.evidence."):
                problems.append(
                    f"{_display(path)} imports {name!r}; AI-08 v1 writes no "
                    "EvidenceRecord, and the only producer token admissible for "
                    "an EXECUTION record is ai-06's (§13.1)"
                )

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "shell":
                        problems.append(
                            f"{_display(path)}:{node.lineno} passes a `shell` "
                            "keyword; AI-08 starts no process of its own (§15)"
                        )
                if isinstance(node.func, ast.Name) and node.func.id in AGENTS_FORBIDDEN_BUILTINS:
                    problems.append(
                        f"{_display(path)}:{node.lineno} calls {node.func.id}()"
                    )

        source = path.read_text(encoding="utf-8")
        for needle in AGENTS_FORBIDDEN_LITERALS:
            if needle in source:
                problems.append(
                    f"{_display(path)} names {needle!r}; the other workspace is "
                    "not reachable from the Agent layer (§17)"
                )

    # (3) Behavioural: the vocabulary is closed and the registration is fixed.
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from agents.independence import INDEPENDENCE_CONDITIONS
        from agents.result import AgentExecutionOutcome
        from agents.vocabulary import ROLE_BY_AGENT, AgentId, AgentRole

        if sorted(m.value for m in AgentId) != ["codex", "dsh"]:
            problems.append(
                f"AgentId is {sorted(m.value for m in AgentId)}; §5.1 closes it "
                "at exactly dsh and codex"
            )
        if sorted(m.value for m in AgentRole) != ["INDEPENDENT_SECOND", "PRIMARY"]:
            problems.append(
                f"AgentRole is {sorted(m.value for m in AgentRole)}; §5.2 closes "
                "it at exactly PRIMARY and INDEPENDENT_SECOND"
            )
        if sorted(m.value for m in AgentExecutionOutcome) != [
            "BLOCKED",
            "COMPLETED",
            "FAILED",
        ]:
            problems.append(
                f"AgentExecutionOutcome is "
                f"{sorted(m.value for m in AgentExecutionOutcome)}; §11 closes it "
                "at exactly three members, and TIMED_OUT / CANCELLED / RETRYING / "
                "FALLBACK / ESCALATED belong to AI-12 and AI-13 (§11.4)"
            )
        if set(ROLE_BY_AGENT) != set(AgentId):
            problems.append(
                "the Agent registration is not total over AgentId; §5.2 fixes it "
                "as dsh -> PRIMARY and codex -> INDEPENDENT_SECOND"
            )
        if len(INDEPENDENCE_CONDITIONS) != 8:
            problems.append(
                f"§9.1 defines eight independence conditions and "
                f"{len(INDEPENDENCE_CONDITIONS)} are present"
            )
    except Exception as exc:  # noqa: BLE001 - surfaced as a failure
        problems.append(f"agents/ could not be imported: {exc}")

    return problems


def check_ai09_integration_layer() -> list[str]:
    """AI-09 §10.3, §17: the Codex integration layer, as a gate.

    AI-09's whole job is to compose two layers that are forbidden to know about
    each other. That makes this boundary unusually load-bearing: the layer can
    reach a provider only through AI-02's invocation boundary, and it may not
    reimplement any part of it.

    ```text
    structural   what integrations/ can reach -- no network, no process, no
                 environment, no Router, no tool layer, no Evidence, and no
                 provider module outside an explicit allowlist
    identity     what integrations/ is -- a core layer, not a plugin, and not a
                 second provider implementation
    one-way      neither agents/ nor providers/ may depend on it
    ```
    """
    import ast

    problems: list[str] = []

    integrations = ROOT / "integrations"
    if not integrations.is_dir():
        return [
            "integrations/ is absent; AI-09's declared home does not exist "
            "(contract §10.1)"
        ]

    if not (integrations / "codex").is_dir():
        problems.append(
            "integrations/codex/ is absent; AI-09 v1's single composition "
            "boundary does not exist (contract §10.1)"
        )

    # (1) Identity: a core layer, not a plugin, and never a second provider.
    if (integrations / "__init__.py").exists():
        problems.append(
            "integrations/__init__.py exists; integrations/ is a core-layer "
            "directory reached as a namespace package, exactly as routing/ and "
            "agents/ are (contract §10.1)"
        )
    for forbidden in ("plugins/codex", "plugins/integrations", "providers/codex"):
        if (ROOT / forbidden).exists():
            problems.append(
                f"{forbidden} exists; AI-09 is a core integration layer, not a "
                "plugin layer and not a second provider (contract §10.1, §5.2)"
            )

    # (2) A provider-side implementation under integrations/ would mean the
    #     layer had stopped composing and started owning a provider.
    for path in sorted(integrations.rglob("*")):
        if path.is_file() and path.suffix in {".yaml", ".yml"}:
            problems.append(
                f"{_display(path)} is provider-side data; profiles are repository "
                "data under providers/, and config is runtime config (contract §10.2)"
            )

    # (3) Structural: what integrations/ may reach.
    for path in sorted(integrations.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - surfaced as a failure
            problems.append(f"{_display(path)} does not parse: {exc}")
            continue

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        for name in sorted(imported):
            root = name.split(".")[0]
            if root in AI09_FORBIDDEN_IMPORTS:
                problems.append(
                    f"{_display(path)} imports {name!r}; AI-09 reaches a provider "
                    "only through AI-02's invocation boundary (contract §8, §9)"
                )
            elif root == "providers" and not _matches_prefix(
                name, AI09_ALLOWED_PROVIDER_IMPORTS
            ):
                problems.append(
                    f"{_display(path)} imports {name!r}, which is outside AI-09's "
                    f"provider allowlist {AI09_ALLOWED_PROVIDER_IMPORTS}"
                )
            elif root == "plugins" and not _matches_prefix(
                name, AI09_ALLOWED_PLUGIN_IMPORTS
            ):
                problems.append(
                    f"{_display(path)} imports {name!r}; only AI-03's context "
                    "layer is reachable from the integration layer (contract §10.3)"
                )

        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
            elif isinstance(node, ast.ClassDef):
                names.add(node.name)
            elif isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "shell":
                        problems.append(
                            f"{_display(path)}:{node.lineno} passes a `shell` "
                            "keyword; the integration layer starts no process (§10.3)"
                        )
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in AI09_FORBIDDEN_BUILTINS
                ):
                    problems.append(f"{_display(path)}:{node.lineno} calls {node.func.id}()")

        for name in AI09_FORBIDDEN_NAMES:
            if name in names:
                problems.append(
                    f"{_display(path)} names {name!r}; the credential source is "
                    "assembled outside this package and the provider layer "
                    "resolves it, so this layer never sees, holds or passes it "
                    "(contract §5.3, §13)"
                )

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith(
                ("Adapter", "Transport")
            ):
                problems.append(
                    f"{_display(path)}:{node.lineno} defines {node.name}; a "
                    "protocol adapter and a transport are AI-02's, and AI-09 "
                    "composes them rather than replacing them (contract §7, §20.4)"
                )

        source = path.read_text(encoding="utf-8")
        for needle in AI09_FORBIDDEN_LITERALS:
            if needle in source:
                problems.append(f"{_display(path)} names {needle!r}")

    # (4) One-way: the dependency runs into the integration layer, never out of it.
    for owner, label in ((ROOT / "agents", "Agent"), (ROOT / "providers", "provider")):
        for path in sorted(owner.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:  # pragma: no cover - other checks report this
                continue
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "integrations" or alias.name.startswith(
                            "integrations."
                        ):
                            module = alias.name
                if module and (
                    module == "integrations" or module.startswith("integrations.")
                ):
                    problems.append(
                        f"{_display(path)} imports {module!r}; the {label} layer "
                        "must not depend on the integration layer (contract §10.3)"
                    )

    return problems


# --------------------------------------------------------------------------
# AI-10 — the review layer (contract §16, §17, §18)
# --------------------------------------------------------------------------

#: AI-10 §16: review/ reads agents/ and AI-06's public surface, and reaches
#: nothing else. `providers` is first for the second half of the claim — a
#: review layer with a model path could generate the content it is supposed to
#: compare — and `routing`, `tools`, `plugins.guard` and `plugins.evidence` are
#: excluded by the same rule. The filesystem modules are here because review/
#: persists nothing: no store, no archive, no log of material content.
AI10_FORBIDDEN_IMPORTS = (
    "providers",
    "routing",
    "tools",
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
    "pathlib",
    "io",
    "tempfile",
    "sqlite3",
    "random",
)

#: The only plugin packages review/ may reach — an **allowlist**, not a denylist.
#: `plugins.guard` and `plugins.evidence` are unreachable by omission, which is
#: stronger than naming them: a module nobody thought to list cannot be reached
#: either. AI-06's public vocabulary is what a review observation is allowed to
#: name; the invocation itself belongs to the controlled verification caller.
AI10_ALLOWED_PLUGIN_IMPORTS = (
    "plugins.security_tools",
    "plugins.context",
)

#: Names that would mean the layer had taken over a job that is not its own:
#: resolving a credential, authorizing, composing a tool request.
AI10_FORBIDDEN_NAMES = (
    "CredentialRef",
    "SecretValue",
    "environ",
    "getenv",
    "evaluator",
    "policy",
    "registry",
    "ToolRequest",
)

AI10_FORBIDDEN_BUILTINS = ("eval", "exec", "compile", "__import__", "open")

AI10_FORBIDDEN_LITERALS = (
    "SecurityLab/",
    "Li20771/SecurityLab",
    "/mnt/d/SecurityLab",
)

#: Verdict tokens that must never appear as an identifier or a literal in
#: review/. A review layer that can spell one can eventually be asked to
#: produce one, and AI-00 §13 forbids exactly that.
AI10_FORBIDDEN_TOKENS = (
    "PASS",
    "FAIL",
    "CORRECT",
    "INCORRECT",
    "VERIFIED",
    "WINNER",
    "BEST_AGENT",
    "HIGHER_CONFIDENCE",
    "CONFIDENCE",
    "PROBABILITY",
    "SCORE",
    "RANK",
)


def check_ai10_review_layer() -> list[str]:
    """AI-10 §16, §17, §18: the review layer, as a gate.

    ```text
    identity     what review/ is -- a core layer, not a plugin, not a fifth one
    structural   what review/ may reach -- no provider, no router, no tool
                 adapter, no Guard, no Evidence, no network, no process, no
                 filesystem, no credential, and no verdict vocabulary
    one-way      neither agents/ nor providers/ nor routing/ nor integrations/
                 may depend on it
    behavioural  the three frozen vocabularies are exactly their frozen sizes,
                 and no record type carries a forbidden field
    ```

    What it must never become is a check that passes because there is nothing to
    check: the non-vacuity is proven by the test suite, which runs this function
    against a scratch tree carrying each violation in turn.
    """
    import ast

    problems: list[str] = []

    review = ROOT / "review"
    if not review.is_dir():
        return [
            "review/ is absent; AI-10's declared home does not exist (contract §17)"
        ]

    # (1) Identity: a core layer, and not a fifth plugin (§17).
    for forbidden in (
        "plugins/review",
        "agents/review",
        "routing/review",
        "integrations/review",
    ):
        if (ROOT / forbidden).exists():
            problems.append(
                f"{forbidden} exists; AI-10 is a Workbench core service under "
                "review/, not a plugin layer and not a subpackage of another "
                "layer (contract §17)"
            )
    if (review / "__init__.py").exists():
        problems.append(
            "review/__init__.py exists; review/ is a core-layer directory reached "
            "as a namespace package, exactly as routing/, agents/ and "
            "integrations/ are (contract §17)"
        )

    # (2) Structural: what review/ may reach, and what it may say.
    for path in sorted(review.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - surfaced as a failure
            problems.append(f"{_display(path)} does not parse: {exc}")
            continue

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        for name in sorted(imported):
            root = name.split(".")[0]
            if root in AI10_FORBIDDEN_IMPORTS:
                problems.append(
                    f"{_display(path)} imports {name!r}; AI-10 reaches the "
                    "Agent layer read-only and executes nothing of its own "
                    "(contract §16)"
                )
            elif root == "plugins" and not _matches_prefix(
                name, AI10_ALLOWED_PLUGIN_IMPORTS
            ):
                problems.append(
                    f"{_display(path)} imports {name!r}; only AI-06's public "
                    "surface and AI-03's read-only context layer are reachable "
                    "from review/, and Guard is not (contract §16)"
                )

        names: set[str] = set()
        literals: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                names.add(node.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.append(node.value)
            elif isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "shell":
                        problems.append(
                            f"{_display(path)}:{node.lineno} passes a `shell` "
                            "keyword; the review layer starts no process (§15)"
                        )
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in AI10_FORBIDDEN_BUILTINS
                ):
                    problems.append(
                        f"{_display(path)}:{node.lineno} calls {node.func.id}()"
                    )

        for name in AI10_FORBIDDEN_NAMES:
            if name in names:
                problems.append(
                    f"{_display(path)} names {name!r}; AI-10 holds no policy, no "
                    "evaluator, no registry and no credential, and composes no "
                    "ToolRequest (contract §11.2, §16)"
                )

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith(
                ("Adapter", "Transport")
            ):
                problems.append(
                    f"{_display(path)}:{node.lineno} defines {node.name}; AI-10 "
                    "implements no adapter and no transport (contract §16)"
                )

        source = path.read_text(encoding="utf-8")
        for needle in AI10_FORBIDDEN_LITERALS:
            if needle in source:
                problems.append(f"{_display(path)} names {needle!r}")

        for token in AI10_FORBIDDEN_TOKENS:
            if any(token in name for name in names) or any(
                token in literal for literal in literals
            ):
                problems.append(
                    f"{_display(path)} spells {token!r}; a finding is a structural "
                    "observation and the review layer produces no verdict "
                    "(contract §9.5)"
                )

    # (3) One-way: the dependency runs into review/, never out of it.
    for owner, label in (
        (ROOT / "agents", "Agent"),
        (ROOT / "providers", "provider"),
        (ROOT / "routing", "routing"),
        (ROOT / "integrations", "integration"),
    ):
        if not owner.is_dir():
            continue
        for path in sorted(owner.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:  # pragma: no cover - other checks report this
                continue
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "review" or alias.name.startswith("review."):
                            module = alias.name
                if module and (module == "review" or module.startswith("review.")):
                    problems.append(
                        f"{_display(path)} imports {module!r}; the {label} layer "
                        "must not depend on the review layer (contract §16)"
                    )

    # (4) Behavioural: the frozen vocabularies, and the fields that must not exist.
    try:
        import dataclasses as _dataclasses

        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))

        from review.case import ReviewCase
        from review.claim import ReviewClaim
        from review.decision import HumanDecision
        from review.finding import ReviewFinding
        from review.material import ReviewMaterial
        from review.vocabulary import (
            FORBIDDEN_CLAIM_FIELDS,
            FORBIDDEN_MATERIAL_FIELDS,
            HumanDecisionKind,
            IndependenceObservationStatus,
            ReviewCaseState,
            ReviewFindingKind,
        )

        expected_states = [
            "BLOCKED",
            "CLOSED",
            "COMPARISON_RECORDED",
            "CREATED",
            "HUMAN_DECISION_RECORDED",
            "INDEPENDENCE_OBSERVED",
            "MATERIALS_SUPPLIED",
            "NOT_RUN",
            "UNRESOLVED",
            "VERIFICATION_OBSERVED",
            "VERIFICATION_REQUESTED",
        ]
        if sorted(member.value for member in ReviewCaseState) != expected_states:
            problems.append(
                "ReviewCaseState is "
                f"{sorted(member.value for member in ReviewCaseState)}; contract "
                "§5.2 closes it at exactly eleven members"
            )

        expected_findings = [
            "CLAIM_OVERLAP",
            "CLAIM_UNIQUE_TO_LEFT",
            "CLAIM_UNIQUE_TO_RIGHT",
            "EVIDENCE_REFERENCE_DIFFERENCE",
            "IDENTICAL_MATERIAL",
            "MATERIAL_DIFFERENCE",
            "UNRESOLVED",
            "VERIFICATION_REQUIRED",
        ]
        if sorted(member.value for member in ReviewFindingKind) != expected_findings:
            problems.append(
                "ReviewFindingKind is "
                f"{sorted(member.value for member in ReviewFindingKind)}; contract "
                "§9.2 closes it at exactly eight structural observations"
            )

        expected_decisions = ["ACCEPTED", "DEFERRED", "REJECTED"]
        if sorted(member.value for member in HumanDecisionKind) != expected_decisions:
            problems.append(
                "HumanDecisionKind is "
                f"{sorted(member.value for member in HumanDecisionKind)}; contract "
                "§12.2 closes it at exactly three members"
            )

        expected_status = ["NOT_APPLICABLE", "OBSERVED", "UNCHECKED"]
        if sorted(member.value for member in IndependenceObservationStatus) != expected_status:
            problems.append(
                "IndependenceObservationStatus is "
                f"{sorted(member.value for member in IndependenceObservationStatus)}; "
                "contract §5.4 closes it at exactly three members, and no member may "
                "describe a pair as independent, non-independent or failed"
            )
        if {member.value for member in IndependenceObservationStatus} & {
            member.value for member in ReviewCaseState
        }:
            problems.append(
                "IndependenceObservationStatus and ReviewCaseState share a member; "
                "§5.4 makes them two orthogonal axes, and neither may absorb the other"
            )

        case_fields = {field.name for field in _dataclasses.fields(ReviewCase)}
        if "independence_status" not in case_fields:
            problems.append(
                "ReviewCase has no `independence_status`; §5.1 requires it, and §6.4 "
                "requires the case to record UNCHECKED when no ExecutionRecord is "
                "supplied"
            )

        forbidden_fields = FORBIDDEN_CLAIM_FIELDS | FORBIDDEN_MATERIAL_FIELDS
        for record in (ReviewMaterial, ReviewClaim, ReviewFinding, HumanDecision):
            fields = {field.name for field in _dataclasses.fields(record)}
            hits = sorted(
                name
                for name in fields
                if name in forbidden_fields or name.startswith("recommended")
            )
            if hits:
                problems.append(
                    f"{record.__name__} carries {hits}; a review record has no "
                    "confidence, no rank and no recommendation (contract §7.3)"
                )
    except Exception as exc:  # noqa: BLE001 - surfaced as a failure
        problems.append(f"review/ could not be imported: {exc}")

    return problems


def _matches_prefix(name: str, allowed: tuple[str, ...]) -> bool:
    """Whether `name` is one of `allowed`, or a submodule of one."""
    return any(name == entry or name.startswith(entry + ".") for entry in allowed)


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


#: AI-12's policy modules. The policy core lives under `routing/` beside AI-07's
#: Router, because AI-12 supplies the policy AI-07 is given and is not a second
#: router, not a plugin, and not a runtime.
AI12_POLICY_MODULES = ("evidence.py", "policy.py", "policy_eval.py")

#: The ONE module under `benchmarks` the policy core may import. The verdict
#: vocabulary is AI-11's and AI-12 does not redefine it; everything else under
#: `benchmarks` is out of reach, because a policy core that could reach
#: `benchmarks.runner` or `benchmarks.campaign` could re-run the benchmark, which
#: the AI-12 contract forbids (§4.1).
AI12_ALLOWED_BENCHMARK_IMPORTS = ("benchmarks.vocabulary",)

#: Identifiers the policy core MUST NOT define. These are the names a hidden
#: scoring system would acquire, and §4.3 and §9 forbid one existing at all.
#: Checked as AST identifiers and never as raw text: the refusal list itself names
#: these words as strings so the refusal can say what it refused, and a text scan
#: would flag the guard.
AI12_FORBIDDEN_IDENTIFIERS = (
    "score",
    "weight",
    "weights",
    "confidence",
    "ranking",
    "aggregate",
    "effective_score",
    "model_score",
    "success_rate",
)

#: Callables that would mean AI-12 had become a runtime. AI-12 declares fallback
#: and escalation as data; it performs neither, retries no model, and creates no
#: hidden second decision (§5.2).
AI12_FORBIDDEN_CALLABLES = (
    "execute_fallback",
    "apply_fallback",
    "retry",
    "rerun",
    "escalate",
)


def check_ai12_policy_core(root: "Path | None" = None) -> list[str]:
    """AI-12 §4, §6, §8, §9: the policy core, as a gate.

    ```text
    identity     the policy core is under routing/, not a plugin and not a second
                 router
    reach        the policy modules import ONE module under benchmarks -- the
                 verdict vocabulary -- and nothing else of AI-11's (§4.1)
    no execution no provider, no subprocess, no socket, no file write (§8)
    no scoring   no identifier a hidden score, weight or ranking would acquire
                 (§4.3, §9)
    no runtime   no callable that would execute a fallback, a retry or an
                 escalation; AI-12 declares those as data (§5.2)
    ```

    `root` defaults to the repository, and is a parameter so the test suite can run
    this check against a scratch tree carrying a violation: a check that cannot fail
    proves nothing, and the only way to show this one CAN fail is to make it fail on
    purpose.
    """
    import ast

    base = ROOT if root is None else root
    problems: list[str] = []

    # (1) Identity: a core service under routing/, not a plugin, not a second Router.
    for forbidden in ("plugins/policy", "plugins/ai12", "plugins/benchmark_policy"):
        if (base / forbidden).exists():
            problems.append(
                f"{forbidden}/ exists; AI-12 is part of the routing core service and "
                "not a DSH plugin (contract §3.2)"
            )

    routing = base / "routing"
    if not routing.is_dir():
        return problems + ["routing/ is absent; the policy core has no home"]

    for name in AI12_POLICY_MODULES:
        if not (routing / name).is_file():
            problems.append(f"routing/{name} is absent; the policy core is incomplete")

    for path in sorted(routing.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - surfaced as a failure
            problems.append(f"{_display(path)} does not parse: {exc}")
            continue

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        # (2) Reach: only the verdict vocabulary is importable from benchmarks.
        for name in sorted(imported):
            if not name.startswith("benchmarks"):
                continue
            if any(
                name == allowed or name.startswith(f"{allowed}.")
                for allowed in AI12_ALLOWED_BENCHMARK_IMPORTS
            ):
                continue
            problems.append(
                f"{_display(path)} imports {name!r}; the policy core may import "
                f"{', '.join(AI12_ALLOWED_BENCHMARK_IMPORTS)} and nothing else under "
                "benchmarks/. A core that could reach the runner or the campaign "
                "could re-run AI-11, which the contract forbids (§4.1)"
            )

        # (3) No execution. routing/ is checked globally in the AI-07 gate; this
        # names the AI-12 rule so a policy module cannot acquire one quietly.
        roots = {name.split(".")[0] for name in imported}
        for banned in ROUTING_FORBIDDEN_IMPORTS:
            if banned in roots:
                problems.append(
                    f"{_display(path)} imports {banned!r}; AI-12 describes policy and "
                    "executes nothing (contract §5.2, §8)"
                )

        # (4) No scoring vocabulary as CODE. String constants are excluded on
        # purpose: the refusal list names these words so a refusal can say what it
        # refused, and the guard must not flag itself.
        defined: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Name):
                defined.add(node.id)
            elif isinstance(node, ast.Attribute):
                defined.add(node.attr)
            elif isinstance(node, ast.arg):
                defined.add(node.arg)

        for identifier in sorted(defined):
            lowered = identifier.lower()
            for forbidden in AI12_FORBIDDEN_IDENTIFIERS:
                if lowered == forbidden or lowered.endswith(f"_{forbidden}"):
                    problems.append(
                        f"{_display(path)} defines {identifier!r}; an AI-11 verdict is "
                        "a fact consumed by policy and not a numeric quantity, and "
                        "AI-12 derives no score, weight, confidence, ranking or "
                        "aggregate from one (contract §4.3, §9)"
                    )
            for callable_name in AI12_FORBIDDEN_CALLABLES:
                if lowered == callable_name:
                    problems.append(
                        f"{_display(path)} defines {identifier!r}; AI-12 declares "
                        "fallback and escalation as data and performs neither, and it "
                        "retries no model and creates no hidden second decision "
                        "(contract §5.2)"
                    )

    # (5) The tracked example policy validates through the REAL model. A tracked
    # artifact nothing checks is an artifact that drifts.
    example = base / "config" / "routing" / "policy.example.yaml"
    if not example.is_file():
        problems.append(
            "config/routing/policy.example.yaml is absent; AI-12 ships the mechanism "
            "and an example, as AI-07 ships a default rule set"
        )
    else:
        try:
            import yaml

            from routing.policy import Policy

            Policy.from_mapping(yaml.safe_load(example.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 - any failure is the finding
            problems.append(
                "config/routing/policy.example.yaml does not validate through the "
                f"policy model: {type(exc).__name__}"
            )

    return problems


def check_ai11_benchmark_layer(root: "Path | None" = None) -> list[str]:
    """AI-11 §4, §7.4, §17, §19: the benchmark layer, as a gate.

    ```text
    identity     benchmarks/ is a core layer -- a namespace package, not a plugin,
                 and not a fifth one
    structural   what benchmarks/ may reach -- no network, no provider, no Evidence
                 write, no adapter dispatch, and no subprocess outside workspace.py
    corpus       every TaskDefinition validates through the REAL loader, declares a
                 discrimination control, and withholds its oracle material
    vocabulary   the frozen closed sets are exactly their frozen sizes
    ```

    `root` defaults to the repository. It is a parameter so the test suite can run this
    check against a scratch tree carrying a violation: a check that cannot fail is a
    check that proves nothing, and the only way to show this one CAN fail is to make it
    fail on purpose.
    """
    import ast
    import subprocess

    base = ROOT if root is None else root
    problems: list[str] = []

    benchmarks = base / "benchmarks"
    if not benchmarks.is_dir():
        return ["benchmarks/ is absent; AI-11's declared home does not exist (contract 4.1)"]

    # (1) Identity (4.1). A core layer, and not a fifth plugin.
    for forbidden in (
        "plugins/benchmark",
        "plugins/ai11",
        "agents/benchmark",
        "review/benchmark",
        "routing/benchmark",
    ):
        if (base / forbidden).exists():
            problems.append(
                f"{forbidden} exists; AI-11 is a Workbench core layer under benchmarks/, "
                "not a plugin layer and not a subpackage of another layer (contract 4.1)"
            )

    # A namespace package, like routing/, agents/, integrations/ and review/.
    if (benchmarks / "__init__.py").exists():
        problems.append(
            "benchmarks/__init__.py exists; benchmarks/ is a core-layer directory reached "
            "as a namespace package, exactly as routing/, agents/, integrations/ and "
            "review/ are (contract 4.1)"
        )

    package_files = sorted(p for p in benchmarks.rglob("*.py") if "__pycache__" not in p.parts)

    # (2) Structural (19, 21).
    network_modules = {
        "http", "http.client", "urllib", "urllib.request", "socket", "requests", "httpx",
    }
    for path in package_files:
        rel = path.relative_to(base).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            problems.append(f"{rel} does not parse: {exc}")
            continue

        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module)

        for name in imports:
            head = name.split(".")[0]
            if head in network_modules:
                problems.append(f"{rel} imports {name}; no AI-11 module may reach the network")
            if head == "plugins" and name.startswith("plugins.evidence"):
                problems.append(
                    f"{rel} imports {name}; AI-11 v1 writes no AI-05 EvidenceRecord "
                    "(contract 21.1)"
                )
            if head == "integrations":
                problems.append(
                    f"{rel} imports {name}; AI-11 makes no provider call (contract 21.5)"
                )
            if head == "providers":
                problems.append(f"{rel} imports {name}; AI-11 makes no provider call")
            if name in ("plugins.security_tools.dispatch", "plugins.security_tools.adapter"):
                problems.append(
                    f"{rel} imports {name}; tool execution belongs to an AI-08 execution "
                    "(contract 21.2)"
                )

        if "subprocess" in imports and rel not in (
            "benchmarks/workspace.py",
            "benchmarks/runner.py",
            "benchmarks/decoders.py",
            "benchmarks/campaign.py",
        ):
            problems.append(
                f"{rel} imports subprocess; only benchmarks/workspace.py (git) and "
                "benchmarks/runner.py (declared oracle tools) may spawn a process "
                "(contract 19)"
            )

    # (3) The corpus (7.4, 17, 19). Validated through the REAL loader, in a subprocess
    # with the repository root as cwd, so the gate cannot drift from the schema by
    # re-implementing it here.
    tasks_dir = benchmarks / "tasks"
    if not tasks_dir.is_dir():
        problems.append("benchmarks/tasks/ is absent; the corpus has no home (contract 17.4)")
    else:
        probe = (
            "import json\n"
            "from benchmarks.task import load_corpus\n"
            "tasks = load_corpus('benchmarks/tasks')\n"
            "out = []\n"
            "for t in tasks:\n"
            "    control = t.oracle.expected_negative\n"
            "    out.append({\n"
            "        'task_id': t.task_id,\n"
            "        'control': bool(control.known_good and control.known_bad),\n"
            "        'excluded': bool(t.oracle.material_excluded_from_workspace),\n"
            "        'withholds_control': 'control' in t.workspace_setup.exclude,\n"
            "    })\n"
            "print(json.dumps(out))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=str(base),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip().splitlines()
            problems.append(
                "the corpus does not validate through benchmarks.task.load_corpus: "
                f"{detail[-1] if detail else 'no output'}"
            )
        else:
            import json as _json

            try:
                loaded = _json.loads(completed.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                problems.append("the corpus probe returned no readable result")
                loaded = []
            if not loaded:
                problems.append("the corpus is empty; an empty corpus is not a corpus")
            for entry in loaded:
                if not entry["control"]:
                    problems.append(
                        f"{entry['task_id']} declares no discrimination control; an "
                        "oracle that cannot fail is not an oracle (contract 7.4)"
                    )
                if not entry["excluded"]:
                    problems.append(
                        f"{entry['task_id']} does not declare "
                        "material_excluded_from_workspace = true (contract 7.2)"
                    )
                if not entry["withholds_control"]:
                    problems.append(
                        f"{entry['task_id']} does not withhold control/ from the "
                        "agent-visible tree (contract 15.3)"
                    )

    # (4) Vocabulary (8.1, 6.1, 14.2, 23).
    vocab = benchmarks / "vocabulary.py"
    if not vocab.is_file():
        problems.append("benchmarks/vocabulary.py is absent")
    else:
        source = vocab.read_text(encoding="utf-8")
        for member in ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN", "UNAVAILABLE"):
            if f'{member} = "{member}"' not in source:
                problems.append(
                    f"benchmarks/vocabulary.py does not declare {member}; the six-member "
                    "OracleVerdict is frozen (contract 8.1)"
                )
        for forbidden in ("RETRYING", "RETRIED", "CANCELLED", "FALLBACK", "ESCALATED"):
            if f'{forbidden} = "' in source:
                problems.append(
                    f"benchmarks/vocabulary.py declares {forbidden}; those belong to "
                    "AI-12 and AI-13 (contract 23)"
                )

    # (5) The results directory stays disposable (17.4).
    if not (benchmarks / "results").is_dir():
        problems.append("benchmarks/results/ is absent; run data needs a home (contract 4.2)")

    return problems


#: AI-13's own top-level package. NOT `.github/workflows` -- that is
#: WORKFLOW_DIR above, and the two are unrelated despite the shared word.
AI13_WORKFLOWS_DIR = "workflows"

#: The modules AI-13-B ships. A package missing one of these is incomplete rather
#: than merely smaller.
AI13_WORKFLOW_MODULES = (
    "canonical.py",
    "checkpoint.py",
    "definition.py",
    "engine.py",
    "errors.py",
    "instants.py",
    "policy.py",
    "resume.py",
    "run.py",
    "vocabulary.py",
)

#: The import roots a workflow module MUST NOT reach.
#:
#: The top-level `workflows/` directory was unchecked before AI-13: the only
#: `workflows` Layer 0 knew about was `.github/workflows`, so a module here could
#: have reached a provider, written an Evidence record or started a process with
#: nothing to stop it (AI-13 §21.3).
#:
#: Every root below is refused outright rather than allowlisted down to one
#: permitted module, because the workflow package imports NOTHING outside itself:
#: it reaches the execution seam through the `StepExecutor` Protocol its caller
#: supplies, not through an import. There is therefore no permitted foreign module
#: for a narrower rule to permit, and the absence is a property of the design
#: rather than a coincidence.
AI13_FORBIDDEN_IMPORT_ROOTS = (
    "agents",        # AI-08 -- an attempt IS an execution, composed not imported
    "benchmarks",    # AI-11 -- measurement, untouched
    "evidence",      # AI-05 -- AI-13 writes no record
    "integrations",  # AI-09 -- the provider composition layer
    "plugins",       # guard (AI-04), evidence (AI-05), security_tools (AI-06)
    "providers",     # AI-02, AI-09 -- AI-13 reaches no provider
    "review",        # AI-10 -- a run is not a review case
    "routing",       # AI-07's Router and AI-12's policy core
    "tools",         # AI-06 -- the single tool-invocation path
)

#: Standard-library roots that would mean the package had acquired an execution,
#: a transport or a second process. AI-13 v1 starts no daemon, holds no execution
#: open between process lifetimes, and reaches nothing over a network (§12, §16).
AI13_FORBIDDEN_STDLIB_ROOTS = (
    "asyncio",
    "ctypes",
    "http",
    "multiprocessing",
    "requests",
    "selectors",
    "shutil",
    "signal",
    "socket",
    "subprocess",
    "threading",
    "urllib",
)

#: Callables that would mean AI-13 had become the executor AI-12 deliberately is
#: not. AI-12 declares fallback and escalation as DATA and AI-13 executes none of
#: it (§10.4, §16).
AI13_FORBIDDEN_CALLABLES = (
    "apply_fallback",
    "escalate",
    "execute_fallback",
    "fallback_to",
)


def check_ai13_workflows(root: "Path | None" = None) -> list[str]:
    """AI-13 §4, §12, §16, §21.3: the workflow layer, as a gate.

    ```text
    identity   a top-level package, not a plugin and not a second execution engine
    reach      no provider, no tool, no Evidence, no Router or policy core, no review
               and no benchmark -- the execution seam is a Protocol, not an import
    no process no subprocess, no socket, no thread, no signal, no transport
    no fallback no callable that would execute AI-12's declared fallback or escalation
    ```

    `root` defaults to the repository, and is a parameter so the test suite can run
    this check against a scratch tree carrying a violation: a check that cannot fail
    proves nothing, and the only way to show this one CAN fail is to make it fail on
    purpose.
    """
    import ast

    base = ROOT if root is None else root
    problems: list[str] = []

    # (1) Identity: a top-level package, not a plugin and not a second engine.
    for forbidden in ("plugins/workflows", "plugins/workflow", "plugins/ai13"):
        if (base / forbidden).exists():
            problems.append(
                f"{forbidden}/ exists; AI-13 is a top-level layer and not a DSH plugin "
                "(contract §3.1, §4)"
            )

    workflows = base / AI13_WORKFLOWS_DIR
    if not workflows.is_dir():
        return problems + [
            f"{AI13_WORKFLOWS_DIR}/ is absent; the workflow layer has no home"
        ]

    if (workflows / "__init__.py").exists():
        problems.append(
            f"{AI13_WORKFLOWS_DIR}/__init__.py exists; this repository's core layers "
            "are namespace packages and a package __init__ is how a layer acquires an "
            "import side effect (contract §4)"
        )

    for name in AI13_WORKFLOW_MODULES:
        if not (workflows / name).is_file():
            problems.append(
                f"{AI13_WORKFLOWS_DIR}/{name} is absent; the workflow core is incomplete"
            )

    for path in sorted(workflows.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - surfaced as a failure
            problems.append(f"{_display(path)} does not parse: {exc}")
            continue

        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        # (2) Reach. Every foreign root is refused, and the message names which
        # ownership rule the import would have crossed rather than only the root.
        reach_reason = {
            "providers": "AI-13 reaches no provider (§4, §16)",
            "integrations": "AI-13 reaches no provider (§4, §16)",
            "tools": "tool invocation stays on AI-06's single path (§4, §17)",
            "plugins": (
                "AI-13 writes no Evidence record, asks Guard nothing directly and "
                "invokes no tool (§4, §16)"
            ),
            "evidence": "AI-13 writes no AI-05 EvidenceRecord and registers no "
                        "producer (§7.3, §16)",
            "routing": "AI-13 executes no AI-12 policy and reuses no RouterDecision "
                       "(§10.2, §10.4)",
            "review": "a workflow run is not a review case and resuming one is not a "
                      "review transition (§13.6, AI-10 §5.3)",
            "benchmarks": "AI-11 measurement is untouched (§4, §16)",
            "agents": "an attempt IS an AI-08 execution, composed through the "
                      "StepExecutor seam rather than imported (§6.3, §17)",
        }
        roots = {name.split(".")[0] for name in imported}
        for banned in AI13_FORBIDDEN_IMPORT_ROOTS:
            if banned in roots:
                problems.append(
                    f"{_display(path)} imports {banned!r}; {reach_reason[banned]}"
                )

        # (3) No process, no transport, no second thread.
        for banned in AI13_FORBIDDEN_STDLIB_ROOTS:
            if banned in roots:
                problems.append(
                    f"{_display(path)} imports {banned!r}; AI-13 v1 starts no process, "
                    "holds no execution open between process lifetimes and reaches "
                    "nothing over a network (§12, §16)"
                )

        # (4) No fallback execution, as CODE. AI-12 declares fallback and escalation
        # as data and performs neither; AI-13 must not become its executor (§10.4).
        defined: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Name):
                defined.add(node.id)
            elif isinstance(node, ast.Attribute):
                defined.add(node.attr)
            elif isinstance(node, ast.arg):
                defined.add(node.arg)

        for identifier in sorted(defined):
            if identifier.lower() in AI13_FORBIDDEN_CALLABLES:
                problems.append(
                    f"{_display(path)} defines {identifier!r}; AI-13 executes no AI-12 "
                    "policy and performs no model fallback or escalation (§10.4, §16)"
                )

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
    report.check(
        "context plugin performs no git write",
        check_context_plugin_performs_no_git_write(),
    )
    report.check(
        "evidence plugin boundary and durability tiers",
        check_evidence_plugin_boundary(),
    )
    report.check(
        "security tools boundary and adapter families",
        check_security_tools_boundary(),
    )
    report.check(
        "model router identity and contract freeze",
        check_ai07_router_contract(),
    )
    report.check(
        "agent layer identity and execution boundary",
        check_ai08_agent_layer(),
    )
    report.check(
        "integration layer composition boundary",
        check_ai09_integration_layer(),
    )
    report.check(
        "review layer core-service boundary",
        check_ai10_review_layer(),
    )
    report.check(
        "benchmark layer core-service boundary and corpus",
        check_ai11_benchmark_layer(),
    )
    report.check(
        "policy core boundary and scoring absence",
        check_ai12_policy_core(),
    )
    report.check(
        "workflow layer boundary and execution absence",
        check_ai13_workflows(),
    )

    if report.failures:
        print("\nLayer 0 = FAIL", file=sys.stderr)
        for failure in report.failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"\nLayer 0 = PASS ({report.checks} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
