"""AI-08 contract T1-T5, T26 — the Agent identity boundary.

§5.1 AgentId · §5.2 AgentRole · §5.2.1 a role is not a finding
§5.3 three questions, three fields · §5.4 registration, not discovery
§6.2 resolve_agent is the only identity boundary
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from plugins.guard.vocabulary import ActorType

from agents.independence import IndependenceFinding
from agents.request import AgentExecutionRequest
from agents.vocabulary import (
    ROLE_BY_AGENT,
    AgentId,
    AgentRole,
    UnknownAgent,
    resolve_agent,
    role_for,
)

from tests.agents.conftest import make_request, python_modules, string_literals

pytestmark = pytest.mark.layer1

VOCABULARY_SOURCE = pathlib.Path("agents/vocabulary.py")
INDEPENDENCE_SOURCE = pathlib.Path("agents/independence.py")


class TestAgentIdIsClosed:
    """T1 — §5.1."""

    def test_it_has_exactly_two_members(self):
        assert [m.value for m in AgentId] == ["dsh", "codex"]

    @pytest.mark.parametrize("value", ["human", "agent", "service", "unknown"])
    def test_actor_type_members_are_not_agent_ids(self, value):
        """The kind vocabulary is not the identity vocabulary (§5.3)."""
        with pytest.raises(ValueError):
            AgentId(value)

    def test_a_near_miss_string_is_not_a_member(self):
        """It is a `StrEnum`, so a value is a string — membership is still closed."""
        assert issubclass(AgentId, str)
        with pytest.raises(ValueError):
            AgentId("dsh ")


class TestResolveAgentRefusesRatherThanGuessing:
    """T2 — §5.4, §6.2."""

    @pytest.mark.parametrize("candidate", ["gpt", "DSH", "", "dsh ", "codex2", None, 7])
    def test_an_unregistered_candidate_is_refused(self, candidate):
        with pytest.raises(UnknownAgent):
            resolve_agent(candidate)

    def test_there_is_no_default_agent(self):
        """An unknown token is never answered with a real Agent."""
        for candidate in ("gpt", "unknown", "primary", "*"):
            with pytest.raises(UnknownAgent):
                resolve_agent(candidate)

    def test_a_registered_member_resolves(self):
        assert resolve_agent("dsh") is AgentId.DSH
        assert resolve_agent("codex") is AgentId.CODEX
        assert resolve_agent(AgentId.DSH) is AgentId.DSH

    def test_the_refusal_names_the_vocabulary(self):
        with pytest.raises(UnknownAgent) as excinfo:
            resolve_agent("gpt")
        assert "dsh" in str(excinfo.value) and "codex" in str(excinfo.value)
        assert UnknownAgent.reason_code == "UNKNOWN_AGENT"


class TestTheRegistrationIsTotalAndFixed:
    """T3 — §5.2."""

    def test_every_agent_has_a_role(self):
        assert set(ROLE_BY_AGENT) == set(AgentId)

    def test_the_pairing_is_the_frozen_one(self):
        assert role_for(AgentId.DSH) is AgentRole.PRIMARY
        assert role_for(AgentId.CODEX) is AgentRole.INDEPENDENT_SECOND

    def test_it_is_read_only(self):
        with pytest.raises(TypeError):
            ROLE_BY_AGENT[AgentId.DSH] = AgentRole.INDEPENDENT_SECOND  # type: ignore[index]


class TestAgentRoleIsNotActorType:
    """T4 — §5.3."""

    def test_the_two_vocabularies_do_not_overlap(self):
        assert not {m.value for m in AgentRole} & {m.value for m in ActorType}

    def test_actor_type_is_imported_not_redefined(self):
        """§5.3: AI-08 must not add a member to AI-04's vocabulary."""
        assert [m.value for m in ActorType] == ["human", "agent", "service", "unknown"]

    def test_vocabulary_does_not_define_a_second_actor_type(self):
        tree = ast.parse(VOCABULARY_SOURCE.read_text(encoding="utf-8"))
        defined = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }
        assert defined == {"AgentId", "AgentRole", "UnknownAgent"}


def _referenced_names(path: pathlib.Path) -> set[str]:
    """Every module, call and attribute the code names — docstrings excluded.

    AST-based on purpose: a substring search over the file would match the prose
    that *documents* the prohibition, which is how a "reads nothing" test ends up
    failing on its own explanation.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


class TestIdentityIsNotDiscovered:
    """T5 — §5.4."""

    @pytest.mark.parametrize(
        "forbidden",
        ["os", "glob", "importlib", "pathlib", "environ", "getenv", "open", "iterdir"],
    )
    def test_the_vocabulary_reaches_no_discovery_mechanism(self, forbidden):
        assert forbidden not in _referenced_names(VOCABULARY_SOURCE), forbidden

    def test_resolution_is_a_pure_function_of_the_candidate(self):
        """Same candidate, same answer, whatever the process looks like."""
        assert resolve_agent("codex") is resolve_agent("codex") is AgentId.CODEX

    def test_the_example_configs_are_not_an_identity_source(self):
        """§5.4: they are documentation, and no code reads them.

        The check ranges over **string literals that are not docstrings**, in
        every first-party Python module. A raw text search would match the prose
        in `agents/vocabulary.py` and in this file that states the rule — which
        is exactly how this assertion failed the first time it ran against
        tracked files, having passed while they were still untracked.

        This guard names the paths it guards, so it exempts itself, the way
        `tests/unit/test_live_verification.py` already does for its own subject.
        """
        for path in ("config/dsh/config.example.yaml", "config/codex/config.example.yaml"):
            assert pathlib.Path(path).is_file()

        needles = ("config/dsh", "config/codex")
        # Compared resolved: `python_modules()` yields repository-relative
        # paths and `__file__` is absolute, so comparing them as written never
        # exempts the guard and the guard flags itself.
        exemption = pathlib.Path(__file__).resolve()
        offenders = []
        for module in python_modules():
            if module.resolve() == exemption:
                continue
            for literal in string_literals(module):
                if any(needle in literal for needle in needles):
                    offenders.append(f"{module.as_posix()}: {literal!r}")
        assert offenders == [], offenders


class TestARoleIsNotAnIndependenceFinding:
    """T26 — §5.2.1."""

    def test_the_role_is_fixed_independently_of_any_execution(self):
        assert role_for(AgentId.CODEX) is AgentRole.INDEPENDENT_SECOND

    def test_the_finding_carries_only_condition_labels(self):
        """A finding is computed, never read off the registration table."""
        fields = {f.name for f in dataclasses.fields(IndependenceFinding)}
        assert fields == {"satisfied", "violated"}

    def test_the_predicate_does_not_consult_the_role_vocabulary(self):
        """The predicate must not be able to answer from a role name."""
        tree = ast.parse(INDEPENDENCE_SOURCE.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.update(alias.name for alias in node.names)
        assert "AgentRole" not in imported
        assert "role_for" not in imported


class TestTheConstructorIsTheIdentityBoundary:
    """Amendment-review regression — §6.2 at the REAL boundary.

    The defect this class exists for: `resolve_agent` was correct, and the
    request constructor bypassed it. A dataclass does not check annotations, so
    `AgentExecutionRequest(agent_id="not-registered", ...)` constructed happily
    and two things followed — a BLOCKED result attributed to no registered
    Agent, and a `ValueError` escaping `execute()` on the happy path.

    Testing `resolve_agent("gpt")` would not have caught either. These go
    through the constructor and the runtime.
    """

    def test_a_registered_candidate_becomes_an_agent_id(self, workspace_root):
        for candidate, expected in (("dsh", AgentId.DSH), ("codex", AgentId.CODEX)):
            request = AgentExecutionRequest(
                agent_id=candidate,
                workspace_root=workspace_root,
                task="t",
                input_digest="sha256:" + "a" * 64,
            )
            assert request.agent_id is expected
            assert isinstance(request.agent_id, AgentId)

    def test_an_agent_id_member_passes_through_unchanged(self, workspace_root):
        request = AgentExecutionRequest(
            agent_id=AgentId.DSH,
            workspace_root=workspace_root,
            task="t",
            input_digest="sha256:" + "a" * 64,
        )
        assert request.agent_id is AgentId.DSH

    @pytest.mark.parametrize("candidate", ["not-registered", "gpt", "", "DSH", None, 7])
    def test_an_unregistered_candidate_is_refused_at_construction(
        self, candidate, workspace_root
    ):
        with pytest.raises(UnknownAgent):
            AgentExecutionRequest(
                agent_id=candidate,
                workspace_root=workspace_root,
                task="t",
                input_digest="sha256:" + "a" * 64,
            )

    def test_the_raw_boundary_uses_the_same_one(self, workspace_root):
        with pytest.raises(UnknownAgent):
            AgentExecutionRequest.from_mapping(
                {
                    "schema_version": 1,
                    "agent_id": "not-registered",
                    "workspace": {"root": workspace_root},
                    "task": "t",
                    "input": "x",
                }
            )

    def test_a_blocked_execution_cannot_carry_an_unregistered_identity(self, workspace_root):
        """The path that used to expose it: BLOCKED returns before the gateway."""
        with pytest.raises(UnknownAgent):
            AgentExecutionRequest(
                agent_id="not-registered",
                workspace_root=workspace_root + "-absent",
                task="t",
                input_digest="sha256:" + "a" * 64,
            )
        # And no execution can be started from one, so no BLOCKED AgentResult
        # with a non-registered declared identity can exist.
        assert True

    def test_a_normal_execution_cannot_carry_one_either(self, workspace_root):
        """The other path: a ValueError used to escape execute() entirely."""
        with pytest.raises(UnknownAgent):
            AgentExecutionRequest(
                agent_id="not-registered",
                workspace_root=workspace_root,
                task="t",
                input_digest="sha256:" + "a" * 64,
            )


class TestAgentResultIdentityIsAnAgentId:
    """Amendment-review regression — §10 `AgentResult.agent_id = an AgentId`."""

    def test_a_result_carries_a_real_agent_id(self, workspace_root):
        from agents.body import OfflineBody
        from agents.runtime import run_execution

        record = run_execution(
            make_request(workspace_root), body=OfflineBody(agent_id=AgentId.DSH)
        )
        assert isinstance(record.result.agent_id, AgentId)
        assert record.result.agent_id is AgentId.DSH

    @pytest.mark.parametrize("candidate", ["gpt", "not-registered", "", None])
    def test_a_result_refuses_an_unregistered_identity(self, candidate):
        from agents.result import AgentExecutionOutcome, AgentResult

        with pytest.raises(UnknownAgent):
            AgentResult(
                agent_id=candidate,
                execution_id="ex-1",
                workspace_id="ws-1",
                input_digest="sha256:" + "a" * 64,
                outcome=AgentExecutionOutcome.COMPLETED,
                result="sha256:" + "b" * 64,
            )

    def test_a_result_cannot_be_forged_into_another_identity(self):
        import dataclasses

        from agents.result import AgentExecutionOutcome, AgentResult

        original = AgentResult(
            agent_id=AgentId.DSH,
            execution_id="ex-1",
            workspace_id="ws-1",
            input_digest="sha256:" + "a" * 64,
            outcome=AgentExecutionOutcome.COMPLETED,
            result="sha256:" + "b" * 64,
        )
        with pytest.raises(UnknownAgent):
            dataclasses.replace(original, agent_id="gpt")
        assert isinstance(dataclasses.replace(original, agent_id="codex").agent_id, AgentId)
