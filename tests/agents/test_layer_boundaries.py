"""AI-08 contract T8, T27, T28, T35, T37-T41 — the layer's boundaries.

§6.3  the Router does not execute, and the dependency does not run backwards
§10   AgentResult is its own type and restates nothing
§13.1 AI-08 writes no EvidenceRecord
§14   no cross-agent result injection
§15   no network, no subprocess, no provider binding
§17   agents/ is a core layer, not a plugin layer
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import subprocess
import sys

import pytest

from plugins.security_tools.vocabulary import ToolOutcome
from plugins.guard.vocabulary import GuardDecision

from agents.body import OfflineBody
from agents.request import AgentExecutionRequest
from agents.result import AgentExecutionOutcome, AgentResult
from agents.runtime import execute, run_execution
from agents.vocabulary import AgentId

from tests.agents.conftest import agent_modules, code_names, make_request

pytestmark = pytest.mark.layer1

AGENTS_DIR = pathlib.Path("agents")
INDEPENDENCE_MODULE = "agents.independence"
RUNTIME_MODULE = "agents.runtime"


class TestNoEvidenceIsWritten:
    """T35 — §13.1."""

    def test_no_agents_module_imports_the_evidence_plugin(self):
        for path in agent_modules():
            names = code_names(path)
            assert not any(n.startswith("plugins.evidence") for n in names), path

    def test_no_agents_module_names_an_evidence_type(self):
        for path in agent_modules():
            names = code_names(path)
            for forbidden in ("EvidenceRecord", "admit_to_store", "evidence_id", "StagedEvidenceStore"):
                assert forbidden not in names, f"{path}: {forbidden}"

    def test_an_execution_produces_no_durable_record(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        """The run's whole output is an in-memory AgentResult and nothing else.

        Asserted at the level the contract cares about: what the caller gets
        back is run data, and no admission pipeline ran.
        """
        from tests.agents.conftest import allow_policy

        record = run_execution(
            make_request(workspace_root),
            body=OfflineBody(agent_id=AgentId.DSH),
            registry=echo_registry,
            policy=allow_policy(workspace_id_of(workspace_root)),
        )
        assert isinstance(record.result, AgentResult)
        assert not hasattr(record.result, "evidence_id")
        assert not hasattr(record.result, "record_digest")

    def test_no_evidence_token_is_reused(self):
        """`ai-06` writes AI-06's records. AI-08 must not claim them."""
        for path in agent_modules():
            assert "ai-06" not in path.read_text(encoding="utf-8"), path


class TestNoCrossAgentResultInjection:
    """T37 — §14."""

    def test_the_request_has_no_field_for_another_result(self):
        fields = {f.name for f in dataclasses.fields(AgentExecutionRequest)}
        for forbidden in ("agent_result", "result", "prior_result", "other_result"):
            assert forbidden not in fields

    def test_no_agents_module_accepts_two_records_to_combine(self):
        """The one place two records meet returns a finding and injects nothing."""
        source = pathlib.Path("agents/independence.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        # Module level only: a nested closure is not an API.
        functions = [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        assert functions == ["structural_independence"]

    def test_the_runtime_takes_exactly_one_request(self):
        import inspect

        signature = inspect.signature(execute)
        request_parameters = [
            name
            for name in signature.parameters
            if not name.startswith("_")
        ]
        assert request_parameters[0] == "request"
        assert "other" not in signature.parameters
        assert "results" not in signature.parameters

    def test_two_executions_never_see_each_other(self, workspace_root):
        left = run_execution(
            make_request(workspace_root, agent_id=AgentId.DSH),
            body=OfflineBody(agent_id=AgentId.DSH),
        )
        right = run_execution(
            make_request(workspace_root, agent_id=AgentId.CODEX),
            body=OfflineBody(agent_id=AgentId.CODEX),
        )
        for record, other in ((left, right), (right, left)):
            blob = str(record.result.to_mapping())
            assert other.result.execution_id not in blob
            assert other.result.result not in blob


class TestNoNetworkNoSubprocessNoProvider:
    """T38, T39 — §15."""

    @pytest.mark.parametrize(
        "forbidden",
        [
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
        ],
    )
    def test_no_agents_module_imports_it(self, forbidden):
        for path in agent_modules():
            imported = {
                name.split(".")[0] for name in code_names(path) if "." not in name or True
            }
            roots = {name.split(".")[0] for name in code_names(path)}
            assert forbidden not in roots, f"{path}: {forbidden}"

    def test_no_provider_or_model_binding(self):
        for path in agent_modules():
            names = code_names(path)
            for forbidden in (
                "Invoker",
                "InvocationRequest",
                "ModelProfile",
                "CapabilityName",
                "CredentialRef",
                "base_url",
                "endpoint",
            ):
                assert forbidden not in names, f"{path}: {forbidden}"

    def test_no_transport_of_any_kind_is_referenced(self):
        """§15: AI-08 v1 has no transport.

        Asserted by substring rather than by naming AI-02's transport class:
        `tests/unit/test_live_verification.py` forbids that symbol outside the
        live path, and this guard does not need to spell it to make the claim.
        """
        for path in agent_modules():
            for name in code_names(path):
                assert "transport" not in name.lower(), f"{path}: {name}"

    def test_no_credential_is_read(self):
        for path in agent_modules():
            names = code_names(path)
            for forbidden in ("environ", "getenv", "CredentialRef", "SecretValue"):
                assert forbidden not in names, f"{path}: {forbidden}"

    def test_the_offline_backend_declares_itself_offline(self):
        """§15: the Codex seam exists, and v1 fills it with no network."""
        names = code_names(pathlib.Path("agents/codex/body.py"))
        assert "CodexBackend" in names
        assert "OfflineCodexBackend" in names


class TestTheRouterBoundary:
    """T8 — §6.3."""

    def test_routing_does_not_import_the_agent_layer(self):
        for path in sorted(pathlib.Path("routing").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert not any(a.name.startswith("agents") for a in node.names), path
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("agents"), path

    def test_the_agent_layer_does_not_import_the_router(self):
        for path in agent_modules():
            names = code_names(path)
            assert not any(n == "routing" or n.startswith("routing.") for n in names), path

    def test_a_router_decision_carries_no_agent_result(self):
        """AI-07 §11: a hint is a hint, and a decision is not an execution."""
        from routing.decision import RouterDecision

        fields = {f.name for f in dataclasses.fields(RouterDecision)}
        assert "agent_hint" in fields
        annotations = "".join(str(h) for h in RouterDecision.__annotations__.values())
        assert "AgentResult" not in annotations
        assert "findings" not in fields

    def test_a_hint_still_needs_the_identity_boundary(self):
        """§6.2: a hint becomes an identity only through resolve_agent."""
        from agents.vocabulary import UnknownAgent, resolve_agent

        with pytest.raises(UnknownAgent):
            resolve_agent("the-hint-string")


class TestAgentResultIsItsOwnType:
    """T27, T28 — §10."""

    def test_it_is_not_any_other_result_type(self):
        from plugins.context import ContextResponse
        from plugins.evidence import EvidenceRecord
        from plugins.guard import DecisionRecord
        from plugins.security_tools import ToolResult
        from providers.invocation import InvocationResult
        from routing.decision import RouterDecision

        for other in (
            InvocationResult,
            ToolResult,
            RouterDecision,
            ContextResponse,
            DecisionRecord,
            EvidenceRecord,
        ):
            assert not issubclass(AgentResult, other), other
            assert AgentResult is not other

    def test_attribution_is_two_fields_and_no_producer(self):
        """§10.1: `agent_id` + `execution_id`, and no AI-05 producer field."""
        fields = {f.name for f in dataclasses.fields(AgentResult)}
        assert "agent_id" in fields
        assert "execution_id" in fields
        assert "producer" not in fields
        assert "producer_type" not in fields
        assert "actor" not in fields

    def test_it_carries_no_raw_content_field(self):
        fields = {f.name for f in dataclasses.fields(AgentResult)}
        for forbidden in ("text", "output", "prompt", "stdout", "stderr", "content", "messages"):
            assert forbidden not in fields

    def test_it_borrows_the_other_vocabularies_rather_than_restating_them(self):
        """§10: the outcome and the decision are AI-06's and AI-04's own members."""
        call_fields = {f.name: f.type for f in dataclasses.fields(__import__(
            "agents.result", fromlist=["ToolCallRef"]
        ).ToolCallRef)}
        assert "ToolOutcome" in str(call_fields["outcome"])
        assert "GuardDecision" in str(call_fields["guard_decision"])
        assert ToolOutcome.COMPLETED is not AgentExecutionOutcome.COMPLETED
        assert GuardDecision.ALLOW is not AgentExecutionOutcome.COMPLETED


class TestTheLayerIsACoreLayer:
    """T41 — §17."""

    def test_agents_is_a_directory_at_the_root(self):
        assert AGENTS_DIR.is_dir()
        assert pathlib.Path("agents/dsh").is_dir()
        assert pathlib.Path("agents/codex").is_dir()

    def test_it_is_not_a_plugin_package(self):
        assert not pathlib.Path("plugins/agent").exists()
        assert not pathlib.Path("plugins/codex").exists()
        assert not pathlib.Path("plugins/dsh").exists()

    def test_it_is_reached_as_a_namespace_package(self):
        """§17: exactly as routing/ and tests/ are."""
        assert not (AGENTS_DIR / "__init__.py").exists()
        assert not pathlib.Path("routing/__init__.py").exists()

    def test_no_agent_execution_lives_in_routing(self):
        for path in sorted(pathlib.Path("routing").rglob("*.py")):
            assert "execute" not in {
                node.name
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(node, ast.FunctionDef)
            }, path

    def test_no_agent_tests_were_added_under_tests_routing(self):
        """§17. `tests/routing/` is the ROUTING layer's test home.

        This asserted an exact file set, which was a true proxy while AI-07 was the
        only phase with tests there. AI-12 legitimately added the policy core's
        tests, so the file set is no longer the claim — the claim is that nothing
        under this directory belongs to the AGENT layer. An agent, Codex or DSH test
        living in the routing layer's home would mean the boundary this class exists
        for had been crossed, and that is what is asserted now.

        The routing suite itself is still required to be there: a directory that
        satisfies this by being empty would satisfy it vacuously.
        """
        directory = pathlib.Path("tests/routing")
        assert (directory / "test_router.py").is_file(), (
            "AI-07's suite is gone; an empty home would pass the check below for the "
            "wrong reason"
        )
        for path in sorted(directory.glob("test_*.py")):
            lowered = path.name.lower()
            for forbidden in ("agent", "codex", "dsh"):
                assert forbidden not in lowered, (
                    f"{path} is named for the agent layer; tests/routing/ is the "
                    "routing layer's home"
                )


class TestTheLayerZeroGate:
    """T40 — §17. The gate exists, and it fails closed."""

    def test_the_ai08_check_is_registered(self):
        source = pathlib.Path("scripts/ci/layer0_policy.py").read_text(encoding="utf-8")
        assert "def check_ai08_agent_layer()" in source
        assert '"agent layer identity and execution boundary"' in source

    def test_the_gate_runs_green(self):
        completed = subprocess.run(
            [sys.executable, "scripts/ci/layer0_policy.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "Layer 0 = PASS" in completed.stdout
        assert "agent layer identity and execution boundary" in completed.stdout

    def test_the_gate_is_not_vacuous(self, tmp_path):
        """A synthetic violation must be caught, or the gate proves nothing.

        The check is imported and run against a scratch tree, so the assertion
        is that the rule fires — not that the repository happens to be clean.
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "layer0_policy_under_test", "scripts/ci/layer0_policy.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        scratch = tmp_path / "repo"
        (scratch / "agents" / "codex").mkdir(parents=True)
        (scratch / "plugins").mkdir()
        # A forbidden import, a forbidden literal and a fifth plugin layer, all
        # at once.
        (scratch / "agents" / "leaky.py").write_text(
            "import socket\nimport subprocess\nX = 'SecurityLab/'\n", encoding="utf-8"
        )
        (scratch / "plugins" / "codex").mkdir()

        original = module.ROOT
        module.ROOT = scratch
        try:
            problems = module.check_ai08_agent_layer()
        finally:
            module.ROOT = original

        assert problems, "the AI-08 gate reported nothing for a violated tree"
        joined = " ".join(problems)
        assert "socket" in joined
        assert "subprocess" in joined
        assert "SecurityLab/" in joined
        assert "plugins/codex/" in joined
