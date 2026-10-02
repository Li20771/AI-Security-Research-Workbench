"""AI-08 contract T20, T21, T33, T34, T36 — the Guard boundary.

§12    one fresh GuardRequest and one fresh GuardDecision per invocation
§9.1.1 request_digest is not an identity, and is not required to be unique
§12.1.1 no Agent-specific permission ceiling exists, is claimed, or is inferred
§13.4  execution-level permission records, not a durable EvidenceRecord

Guard is not faked here. Every assertion below is made against a real AI-04
evaluation with a real AI-04 policy, because "the call reached Guard" is the
claim under test and a stub evaluator would satisfy it without Guard running.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from plugins.guard import PermissionLevel, TargetKind, TargetRef
from plugins.guard.policy import FIXED_FIELD_REFS
from plugins.guard.vocabulary import GuardDecision
from plugins.security_tools import AdapterFamily, ToolOutcome

from agents.body import OfflineBody
from agents.result import AgentExecutionOutcome
from agents.runtime import run_execution
from agents.toolcall import ToolGateway, ToolInvocation
from agents.vocabulary import AgentId

from tests.agents.conftest import (
    ECHO_TOOL_ID,
    ECHO_TOOL_VERSION,
    agent_modules,
    allow_policy,
    code_names,
    make_request,
)

pytestmark = pytest.mark.layer1

AGENTS_DIR = pathlib.Path("agents")


def _invocation(level: PermissionLevel = PermissionLevel.READ) -> ToolInvocation:
    return ToolInvocation(
        tool_id=ECHO_TOOL_ID,
        tool_version=ECHO_TOOL_VERSION,
        adapter_family=AdapterFamily.TERMINAL,
        operation="echo",
        permission_level=level,
        target=TargetRef(kind=TargetKind.REPOSITORY),
        timeout_seconds=5,
    )


class TestFreshAuthorizationPerInvocation:
    """T20 — §12."""

    def test_two_invocations_get_two_real_evaluations(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        """Both reach Guard, both are refused by policy, and neither decision is
        the other's."""
        gateway = ToolGateway(
            agent_id=AgentId.DSH,
            workspace_id=workspace_id_of(workspace_root),
            workspace_root=workspace_root,
            registry=echo_registry,
            policy=None,  # no policy: Guard refuses, and refuses by evaluating
        )
        first = gateway.invoke(_invocation())
        second = gateway.invoke(_invocation())

        assert first.outcome is ToolOutcome.BLOCKED
        assert second.outcome is ToolOutcome.BLOCKED
        assert first.guard_reason_code == "POLICY_MISSING"

        # An evaluation happened, so it has an id — the refusal came from Guard
        # and not from a boundary that never reached it.
        assert first.guard_decision_id
        assert second.guard_decision_id
        assert first.guard_decision_id != second.guard_decision_id

    def test_every_invocation_of_one_execution_carries_its_own_decision(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        plan = (_invocation(), _invocation(), _invocation())
        record = run_execution(
            make_request(workspace_root),
            body=OfflineBody(agent_id=AgentId.DSH, plan=plan),
            registry=echo_registry,
            policy=allow_policy(workspace_id_of(workspace_root)),
        )

        calls = record.result.tool_calls
        assert len(calls) == 3
        assert [c.ordinal for c in calls] == [0, 1, 2]
        assert len({c.guard_decision_id for c in calls}) == 3
        assert all(c.guard_decision is GuardDecision.ALLOW for c in calls)
        assert all(c.outcome is ToolOutcome.COMPLETED for c in calls)

    def test_no_decision_is_reused_across_executions(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        policy = allow_policy(workspace_id_of(workspace_root))
        request = make_request(workspace_root)
        first = run_execution(
            request,
            body=OfflineBody(agent_id=AgentId.DSH, plan=(_invocation(),)),
            registry=echo_registry,
            policy=policy,
        )
        second = run_execution(
            request,
            body=OfflineBody(agent_id=AgentId.DSH, plan=(_invocation(),)),
            registry=echo_registry,
            policy=policy,
        )
        ids = set(first.result.tool_call_ids()) | set(second.result.tool_call_ids())
        assert len(ids) == 2

    def test_the_gateway_holds_no_decision_store(self):
        """No attribute, field or call names a decision store."""
        names = {name.lower() for name in code_names(pathlib.Path("agents/toolcall.py"))}
        for forbidden in ("cache", "reuse", "decisions", "store", "memo"):
            assert not any(forbidden in name for name in names), forbidden


class TestRequestDigestIsNotAnIdentity:
    """T21 — §9.1.1."""

    def test_no_agents_module_depends_on_request_digest(self):
        for path in agent_modules():
            assert "request_digest" not in code_names(path), path

    def test_two_identical_executions_are_not_required_to_differ(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        """§9.1.1: I5 is fresh objects, not distinct digest values.

        Two executions of one identical request by two Agents are structurally
        independent. Nothing about their Guard requests has to differ for that
        to hold, and nothing here asserts that it does.
        """
        from agents.independence import structural_independence

        policy = allow_policy(workspace_id_of(workspace_root))
        # The SAME declared task, input and workspace for both — only the Agent
        # differs. Two identical Guard requests would produce equal
        # `request_digest`s, and §9.1.1 says that is not a violation.
        left = run_execution(
            make_request(workspace_root, agent_id=AgentId.DSH),
            body=OfflineBody(agent_id=AgentId.DSH, plan=(_invocation(),)),
            registry=echo_registry,
            policy=policy,
        )
        right = run_execution(
            make_request(workspace_root, agent_id=AgentId.CODEX),
            body=OfflineBody(agent_id=AgentId.CODEX, plan=(_invocation(),)),
            registry=echo_registry,
            policy=policy,
        )

        finding = structural_independence(left, right)
        assert finding.violated == ()
        assert finding.independent

    def test_no_nonce_or_make_work_field_is_added(self):
        """The correction §9.1.1 records: nothing exists to force a digest apart."""
        names = {name.lower() for name in code_names(pathlib.Path("agents/toolcall.py"))}
        for forbidden in ("nonce", "uuid", "random", "counter", "salt"):
            assert not any(forbidden in name for name in names), forbidden


class TestNoAgentSpecificPermissionCeiling:
    """T34 — §12.1.1."""

    def test_the_permission_level_is_required_and_never_defaulted(self):
        fields = {f.name: f for f in dataclasses.fields(ToolInvocation)}
        level = fields["permission_level"]
        assert level.default is dataclasses.MISSING
        assert level.default_factory is dataclasses.MISSING

    def test_the_level_is_not_derived_from_identity(self):
        """The gateway binds the Agent to the ACTOR and to nothing else."""
        names = code_names(pathlib.Path("agents/toolcall.py"))
        assert "AgentRole" not in names
        assert "role_for" not in names
        lowered = {name.lower() for name in names}
        for forbidden in ("ceiling", "max_level", "read_only_agent"):
            assert not any(forbidden in name for name in lowered), forbidden

    def test_the_same_invocation_decides_the_same_way_for_either_agent(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        """No ceiling is applied, because none exists: identity changes the
        attribution, not the decision."""
        workspace_id = workspace_id_of(workspace_root)
        policy = allow_policy(workspace_id)

        decisions = []
        for agent in (AgentId.DSH, AgentId.CODEX):
            gateway = ToolGateway(
                agent_id=agent,
                workspace_id=workspace_id,
                workspace_root=workspace_root,
                registry=echo_registry,
                policy=policy,
            )
            reference = gateway.invoke(_invocation(PermissionLevel.MODIFY))
            decisions.append(
                (reference.guard_decision, reference.outcome, reference.guard_reason_code)
            )

        assert decisions[0] == decisions[1]

    def test_guard_cannot_match_on_an_actor(self):
        """The invariant that makes a ceiling unimplementable without an AI-04
        amendment — which is exactly why AI-08 does not claim one."""
        assert not any("actor" in ref for ref in FIXED_FIELD_REFS)


class TestGuardItselfIsUnchanged:
    """T33 — §12."""

    def test_agents_does_not_import_guards_internals(self):
        """AI-08 passes AI-04's frozen entry point to AI-06. It reads no policy,
        builds no predicate and reimplements no gate."""
        forbidden = {
            "plugins.guard.policy",
            "plugins.guard.evaluator",
            "plugins.guard.digest",
            "plugins.guard.predicates",
            "plugins.guard.ordering",
        }
        for path in agent_modules():
            assert not (code_names(path) & forbidden), path

    def test_agents_does_not_evaluate_a_policy(self):
        forbidden = {"Policy", "validate_policy", "Predicate", "Rule", "ActionRef"}
        for path in agent_modules():
            names = code_names(path)
            # `ActionRef` is constructed by AI-06, not by AI-08: the gateway
            # hands AI-06 a ToolRequest and AI-06 builds the Guard request.
            assert not (names & forbidden), (path, names & forbidden)

    def test_the_decision_record_type_is_not_redefined(self):
        """AI-08 references AI-04's decisions; it does not restate the type."""
        tree = ast.parse(pathlib.Path("agents/result.py").read_text(encoding="utf-8"))
        defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
        assert "DecisionRecord" not in defined
        assert "GuardDecision" not in defined


class TestPermissionRecordsAreExecutionLevel:
    """T36 — §13.4."""

    def test_each_invocation_records_the_decision_it_ran_under(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        record = run_execution(
            make_request(workspace_root),
            body=OfflineBody(agent_id=AgentId.DSH, plan=(_invocation(),)),
            registry=echo_registry,
            policy=allow_policy(workspace_id_of(workspace_root)),
        )
        call = record.result.tool_calls[0]
        assert call.guard_decision is GuardDecision.ALLOW
        assert call.guard_decision_id
        assert call.guard_reason_code

    def test_the_records_are_run_data_and_not_a_durable_record(self, workspace_root):
        """§13.4: execution-level, so no AI-05 admission is involved and C-1
        cannot be in the way."""
        names = code_names(pathlib.Path("agents/result.py"))
        for forbidden in ("EvidenceRecord", "evidence_id", "record_digest", "content_digest"):
            assert forbidden not in names, forbidden

    def test_a_different_agent_produces_a_different_attribution(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        """§12: the actor is the AgentId, so two Agents' permission records are
        distinguishable without either being authorized differently."""
        workspace_id = workspace_id_of(workspace_root)
        seen = set()
        for agent in (AgentId.DSH, AgentId.CODEX):
            gateway = ToolGateway(
                agent_id=agent,
                workspace_id=workspace_id,
                workspace_root=workspace_root,
                registry=echo_registry,
                policy=None,
            )
            reference = gateway.invoke(_invocation())
            seen.add(reference.guard_decision_id)
        assert len(seen) == 2


class TestGuardBoundVersusPreGuardRefusal:
    """Amendment 3 — §12.2. Three cases, kept apart.

    AI-06 refuses on five paths before `ask_guard` (dispatch.py:75, :79, :85,
    :92, :99). Those invocations carry no `GuardDecision`, and the difference
    between "no evaluation happened" and "an evaluation returned BLOCKED" is the
    whole point of the distinction.
    """

    # -- Case A: the invocation reaches Guard ------------------------------

    def test_case_a_a_guard_bound_invocation_carries_a_real_decision(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        gateway = ToolGateway(
            agent_id=AgentId.DSH,
            workspace_id=workspace_id_of(workspace_root),
            workspace_root=workspace_root,
            registry=echo_registry,
            policy=allow_policy(workspace_id_of(workspace_root)),
        )
        reference = gateway.invoke(_invocation())

        assert reference.was_evaluated
        assert reference.guard_decision_id
        assert reference.guard_decision is GuardDecision.ALLOW
        assert reference.outcome is ToolOutcome.COMPLETED

    # -- Case B: refused before Guard --------------------------------------

    def test_case_b_a_pre_guard_refusal_carries_no_decision(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        gateway = ToolGateway(
            agent_id=AgentId.DSH,
            workspace_id=workspace_id_of(workspace_root),
            workspace_root=workspace_root,
            registry=echo_registry,
            policy=allow_policy(workspace_id_of(workspace_root)),
        )
        # An operation the registry does not declare: refused at
        # dispatch.py:79, before `ask_guard` at :109.
        reference = gateway.invoke(
            ToolInvocation(
                tool_id=ECHO_TOOL_ID,
                tool_version=ECHO_TOOL_VERSION,
                adapter_family=AdapterFamily.TERMINAL,
                operation="no-such-operation",
                permission_level=PermissionLevel.READ,
                target=TargetRef(kind=TargetKind.REPOSITORY),
                timeout_seconds=5,
            )
        )

        assert reference.outcome is ToolOutcome.UNKNOWN
        assert not reference.was_evaluated
        assert reference.guard_decision_id == ""

    def test_case_b_no_decision_is_fabricated(self, workspace_root, echo_registry, workspace_id_of):
        """The one thing §12.2 forbids outright."""
        gateway = ToolGateway(
            agent_id=AgentId.DSH,
            workspace_id=workspace_id_of(workspace_root),
            workspace_root=workspace_root,
            registry=echo_registry,
            policy=allow_policy(workspace_id_of(workspace_root)),
        )
        reference = gateway.invoke(
            ToolInvocation(
                tool_id="no-such-tool",
                tool_version="1.0",
                adapter_family=AdapterFamily.TERMINAL,
                operation="echo",
                permission_level=PermissionLevel.READ,
                target=TargetRef(kind=TargetKind.REPOSITORY),
                timeout_seconds=5,
            )
        )

        # Not UNKNOWN, not BLOCKED — absent. AI-06 supplies the word "BLOCKED"
        # as a fallback alongside an empty id, and carrying it would record a
        # non-evaluation as a decision.
        assert reference.guard_decision is None
        assert reference.guard_decision is not GuardDecision.UNKNOWN
        assert reference.guard_decision is not GuardDecision.BLOCKED

    def test_case_b_the_refusal_is_still_recorded(self, workspace_root, echo_registry, workspace_id_of):
        """§11.2/§12.2: narrowing the quantifier does not license dropping it.

        The invocation still appears in `tool_results`, with AI-06's own reason
        code, and it still does not rewrite the execution outcome.
        """
        record = run_execution(
            make_request(workspace_root),
            body=OfflineBody(
                agent_id=AgentId.DSH,
                plan=(
                    ToolInvocation(
                        tool_id=ECHO_TOOL_ID,
                        tool_version=ECHO_TOOL_VERSION,
                        adapter_family=AdapterFamily.TERMINAL,
                        operation="no-such-operation",
                        permission_level=PermissionLevel.READ,
                        target=TargetRef(kind=TargetKind.REPOSITORY),
                        timeout_seconds=5,
                    ),
                ),
            ),
            registry=echo_registry,
            policy=allow_policy(workspace_id_of(workspace_root)),
        )

        assert record.result.outcome is AgentExecutionOutcome.COMPLETED
        assert len(record.result.tool_calls) == 1
        call = record.result.tool_calls[0]
        assert call.was_evaluated is False
        assert call.guard_reason_code  # AI-06's reason survives

    # -- Case C: repeated Guard-bound invocations --------------------------

    def test_case_c_three_guard_bound_invocations_get_three_decisions(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        record = run_execution(
            make_request(workspace_root),
            body=OfflineBody(
                agent_id=AgentId.DSH, plan=(_invocation(), _invocation(), _invocation())
            ),
            registry=echo_registry,
            policy=allow_policy(workspace_id_of(workspace_root)),
        )
        calls = record.result.tool_calls
        assert len(calls) == 3
        assert all(c.was_evaluated for c in calls)
        assert len({c.guard_decision_id for c in calls}) == 3

    def test_a_mixed_execution_counts_authorizations_not_invocations(
        self, workspace_root, echo_registry, workspace_id_of
    ):
        """§13.4: the two counts may differ, and must not be reported as one."""
        record = run_execution(
            make_request(workspace_root),
            body=OfflineBody(
                agent_id=AgentId.DSH,
                plan=(
                    _invocation(),
                    ToolInvocation(
                        tool_id=ECHO_TOOL_ID,
                        tool_version=ECHO_TOOL_VERSION,
                        adapter_family=AdapterFamily.TERMINAL,
                        operation="no-such-operation",
                        permission_level=PermissionLevel.READ,
                        target=TargetRef(kind=TargetKind.REPOSITORY),
                        timeout_seconds=5,
                    ),
                    _invocation(),
                ),
            ),
            registry=echo_registry,
            policy=allow_policy(workspace_id_of(workspace_root)),
        )
        calls = record.result.tool_calls
        evaluated = [c for c in calls if c.was_evaluated]

        assert len(calls) == 3          # tool invocations
        assert len(evaluated) == 2      # authorization records
        assert len({c.guard_decision_id for c in evaluated}) == 2
