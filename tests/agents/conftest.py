"""Shared fixtures for the AI-08 tests.

Everything here is offline and deterministic: a temporary directory, an
in-process adapter that runs no process, and a real AI-04 policy evaluated by
the real AI-04 evaluator. **Guard is not faked.** The one thing these tests must
not do is substitute an evaluator, because "the tool call reached Guard" is the
claim under test — a fake evaluator would make the suite green while proving
nothing about the boundary it exists to check.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from plugins.context import resolve_workspace
from plugins.guard import (
    FieldRef,
    PermissionLevel,
    Policy,
    Predicate,
    Rule,
    RuleEffect,
)
from plugins.security_tools import (
    AdapterFamily,
    AdapterOutcome,
    OperationSpec,
    ToolDescriptor,
    ToolIdentity,
    ToolOutcome,
    ToolRegistry,
)

from agents.request import AgentExecutionRequest
from agents.vocabulary import AgentId

ECHO_TOOL_ID = "echo"
ECHO_TOOL_VERSION = "1.0"

AGENTS_DIR = pathlib.Path("agents")


def code_names(*paths: pathlib.Path) -> set[str]:
    """Every module, call and attribute the code names — docstrings excluded.

    AST-based on purpose. The AI-08 modules document their own prohibitions at
    length, so a substring search over the file matches the prose that *states*
    the rule and fails the test that checks it. Reading the AST reads the code.
    """
    names: set[str] = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
    return names


def agent_modules() -> list[pathlib.Path]:
    return sorted(p for p in AGENTS_DIR.rglob("*.py") if "__pycache__" not in p.parts)


class EchoAdapter:
    """The smallest adapter that can run: it reports success and does nothing.

    It spawns no process, reads no file and reaches no network. `execute` is
    called only after Guard returned ALLOW, and the tests rely on that ordering
    rather than re-asserting it here.
    """

    @property
    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            identity=ToolIdentity(
                tool_id=ECHO_TOOL_ID,
                tool_version=ECHO_TOOL_VERSION,
                adapter_family=AdapterFamily.TERMINAL,
            ),
            summary="records that an invocation reached an authorized adapter",
            operations=(
                OperationSpec(
                    name="echo",
                    permission_level_floor=PermissionLevel.READ,
                    summary="echo an invocation",
                ),
            ),
        )

    def execute(self, invocation) -> AdapterOutcome:  # noqa: ANN001 - AI-06's Invocation
        return AdapterOutcome.of(ToolOutcome.COMPLETED, "ECHOED")


@pytest.fixture
def workspace_root(tmp_path) -> str:
    """A real directory, so `build_context` resolves a real workspace identity.

    Deliberately not a git repository: AI-03 answers a non-repository root with
    `working_tree: UNKNOWN` and no branch or commit, which is an answer rather
    than an error, and it keeps these tests from depending on this host's git
    configuration.
    """
    return str(tmp_path)


@pytest.fixture
def echo_registry() -> ToolRegistry:
    return ToolRegistry((EchoAdapter(),))


@pytest.fixture
def workspace_id_of():
    """The id AI-03 will derive for a root, so a policy can name the same scope.

    A policy is scoped to exactly one workspace, and Guard refuses a policy
    whose scope disagrees with the request's. Deriving the id the same way the
    runtime will is what makes the ALLOW cases real rather than accidental.
    """

    def _of(root: str) -> str:
        return resolve_workspace(root).workspace_id

    return _of


def allow_policy(workspace_id: str, *, level: PermissionLevel = PermissionLevel.READ) -> Policy:
    """A reviewed policy that permits one permission level in one workspace.

    It matches on `action.permission_level` and nothing else. It does **not**
    match on `actor` — AI-04's closed field-ref set has no actor field at all,
    which is exactly why AI-08 v1 cannot offer an Agent-specific permission
    ceiling (§12.1.1) and why these tests cannot accidentally imply one.
    """
    return Policy(
        policy_id="ai08-test-policy",
        revision="r1",
        workspace_id=workspace_id,
        rules=(
            Rule(
                rule_id="allow-declared-level",
                priority=1,
                effect=RuleEffect.ALLOW,
                reason_code="AI08_TEST_ALLOW",
                match=(
                    Predicate(
                        field=FieldRef(text="action.permission_level"),
                        op="eq",
                        value=str(level),
                    ),
                ),
            ),
        ),
    )


def make_request(
    workspace_root: str,
    *,
    agent_id: AgentId = AgentId.DSH,
    task: str = "independent-review",
    input_digest: str = "sha256:" + "a" * 64,
    context_descriptor: str | None = None,
) -> AgentExecutionRequest:
    return AgentExecutionRequest(
        agent_id=agent_id,
        workspace_root=workspace_root,
        task=task,
        input_digest=input_digest,
        context_descriptor=context_descriptor,
    )
