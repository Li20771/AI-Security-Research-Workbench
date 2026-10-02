"""Shared fixtures and builders for the AI-10 tests.

Everything here is offline and deterministic: a temporary directory, AI-08's
real offline body, and no provider, no network and no credential anywhere.

The review layer has no transport to fake, and that is the point — there is
nothing to substitute because there is no path to substitute for. What these
tests must not do is fabricate Agent output, a `ToolResult` or a Guard decision
to make a path look complete: the material a test compares is material the test
declared, which is exactly what v1's ingress boundary accepts.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from agents.body import OfflineBody
from agents.independence import ExecutionRecord
from agents.request import AgentExecutionRequest
from agents.runtime import run_execution
from agents.vocabulary import AgentId

from review.claim import ReviewClaim, VerificationTarget
from review.material import ReviewMaterial

REVIEW_DIR = pathlib.Path("review")


def review_modules() -> list[pathlib.Path]:
    """Every module under review/, in a stable order."""
    return sorted(
        path for path in REVIEW_DIR.rglob("*.py") if "__pycache__" not in path.parts
    )


def module_names(path: pathlib.Path) -> set[str]:
    """Every module, call, attribute and argument name the code uses.

    AST-based on purpose: the review modules document their own prohibitions at
    length, so a substring search over the file matches the prose that *states*
    a rule and fails the test that checks it. Reading the AST reads the code.
    """
    names: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node, (ast.Name, ast.Attribute, ast.arg)):
            names.add(getattr(node, "id", None) or getattr(node, "attr", None) or node.arg)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
    return names


def string_literals(path: pathlib.Path) -> list[str]:
    """Every string constant that is **not** a docstring.

    A docstring is an `ast.Constant` like any other, so it is excluded by
    position rather than by hoping nobody writes one.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def sha256(char: str = "a") -> str:
    """A well-formed reference of the `sha256:` shape."""
    return "sha256:" + char * 64


def target(
    target_id: str = "t1",
    description: str = "run the parser against the fixture",
) -> VerificationTarget:
    return VerificationTarget(target_id=target_id, description=description)


def claim(
    claim_id: str = "c1",
    statement: str = "the parser rejects trailing bytes",
    *,
    evidence_refs: tuple[str, ...] = (),
    verification_targets: tuple[VerificationTarget, ...] = (),
) -> ReviewClaim:
    return ReviewClaim(
        claim_id=claim_id,
        statement=statement,
        evidence_refs=evidence_refs,
        verification_targets=verification_targets,
    )


@pytest.fixture
def workspace_root(tmp_path) -> str:
    """A real directory, so AI-03 resolves a real workspace identity."""
    return str(tmp_path)


def run_agent_execution(
    workspace_root: str,
    *,
    agent_id: AgentId = AgentId.DSH,
    task: str = "independent-review",
    input_digest: str = "sha256:" + "a" * 64,
) -> ExecutionRecord:
    """One real AI-08 execution of the offline body.

    It performs no inference and makes no provider call — AI-08 v1 cannot, and
    these tests must not pretend one happened.
    """
    return run_execution(
        AgentExecutionRequest(
            agent_id=agent_id,
            workspace_root=workspace_root,
            task=task,
            input_digest=input_digest,
        ),
        body=OfflineBody(agent_id=agent_id),
    )


def material_for(
    record: ExecutionRecord,
    material_id: str,
    claims: tuple[ReviewClaim, ...] = (),
    *,
    source_status=None,
) -> ReviewMaterial:
    """A material whose declaration agrees with the record it is attributed to."""
    return ReviewMaterial(
        material_id=material_id,
        agent_id=record.request.agent_id,
        execution_id=record.result.execution_id,
        workspace_id=record.result.workspace_id,
        input_digest=record.request.input_digest,
        source_status=source_status or record.result.outcome,
        claims=claims,
    )


@pytest.fixture
def pair(workspace_root):
    """Two executions, one per registered Agent, and two aligned materials."""
    left_record = run_agent_execution(workspace_root, agent_id=AgentId.DSH)
    right_record = run_agent_execution(
        workspace_root, agent_id=AgentId.CODEX, input_digest="sha256:" + "b" * 64
    )
    left = material_for(left_record, "m-left", (claim(),))
    right = material_for(right_record, "m-right", (claim(),))
    return left_record, right_record, left, right
