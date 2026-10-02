"""AI-08 contract T9-T13, T29-T32, T42, T43 — the execution contract.

§7.1 one execution · §7.1.1 one terminal result, every outcome
§7.2 ExecutionId · §7.3 AgentExecutionRequest · §11 the outcome vocabulary
§11.1 BLOCKED is execution-level · §11.2 tool BLOCKED is not execution BLOCKED
§11.4 no AI-12 / AI-13 vocabulary
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from plugins.guard import PermissionLevel, TargetKind, TargetRef
from plugins.guard.vocabulary import GuardDecision
from plugins.security_tools import AdapterFamily, ToolOutcome

from agents.body import BodyOutcome, OfflineBody
from agents.request import AgentExecutionRequest, new_execution_id
from agents.result import AgentExecutionOutcome, AgentResult
from agents.runtime import execute
from agents.toolcall import ToolInvocation
from agents.vocabulary import AgentId

from tests.agents.conftest import ECHO_TOOL_ID, ECHO_TOOL_VERSION, make_request

pytestmark = pytest.mark.layer1


class _ExplodingBody:
    """A body that starts and then fails. §11.1's FAILED, and nothing else."""

    def run(self, *, request, context, tools):  # noqa: ANN001, ANN201
        raise RuntimeError("the body started and did not finish")


class TestTheRequestIsClosed:
    """T11, T13 — §7.3, §7.4."""

    def test_a_well_formed_request_parses(self, workspace_root):
        request = AgentExecutionRequest.from_mapping(
            {
                "schema_version": 1,
                "agent_id": "codex",
                "workspace": {"root": workspace_root},
                "task": "independent-review",
                "input": "sha256:" + "b" * 64,
            }
        )
        assert request.agent_id is AgentId.CODEX
        assert request.context_descriptor is None

    @pytest.mark.parametrize(
        "extra",
        [
            {"api_key": "x"},
            {"token": "x"},
            {"credential": "x"},
            {"arguments": {"a": 1}},
            {"command": "rm -rf /"},
            {"agent_result": "ex-1"},
        ],
    )
    def test_a_refused_field_is_refused_by_name(self, workspace_root, extra):
        raw = {
            "agent_id": "dsh",
            "workspace": {"root": workspace_root},
            "task": "t",
            "input": "sha256:" + "c" * 64,
        }
        raw.update(extra)
        with pytest.raises(ValueError):
            AgentExecutionRequest.from_mapping(raw)

    def test_an_unknown_field_is_refused(self, workspace_root):
        with pytest.raises(ValueError):
            AgentExecutionRequest.from_mapping(
                {
                    "agent_id": "dsh",
                    "workspace": {"root": workspace_root},
                    "task": "t",
                    "input": "x",
                    "surprise": 1,
                }
            )

    def test_the_request_cannot_carry_a_context_response(self, workspace_root, tmp_path):
        """T13 — §7.3. The execution establishes context; the request does not."""
        with pytest.raises(ValueError) as excinfo:
            AgentExecutionRequest.from_mapping(
                {
                    "agent_id": "dsh",
                    "workspace": {"root": workspace_root},
                    "task": "t",
                    "input": "x",
                    "context_response": {"anything": True},
                }
            )
        assert "context_response" in str(excinfo.value)

    def test_a_context_descriptor_is_allowed_and_is_only_a_descriptor(self, workspace_root):
        """§7.3 permits a descriptor: where to read, never what was read."""
        request = AgentExecutionRequest.from_mapping(
            {
                "schema_version": 1,
                "agent_id": "dsh",
                "workspace": {"root": workspace_root},
                "task": "t",
                "input": "x",
                "context": {"descriptor": "workspace:head"},
            }
        )
        assert request.context_descriptor == "workspace:head"
        assert "workspace:head" in str(request.to_mapping())

    def test_a_context_response_object_is_not_accepted_in_its_place(self, workspace_root):
        from plugins.context import build_context

        with pytest.raises(ValueError):
            AgentExecutionRequest.from_mapping(
                {
                    "agent_id": "dsh",
                    "workspace": {"root": workspace_root},
                    "task": "t",
                    "input": "x",
                    "context": build_context(workspace_root),
                }
            )


class TestExecutionIdentity:
    """T9, T10 — §7.2."""

    def test_a_new_id_is_minted_each_time(self):
        assert len({new_execution_id() for _ in range(200)}) == 200

    def test_the_id_is_opaque(self):
        """It encodes no agent, no workspace, no task and no timestamp (§7.2)."""
        identifier = new_execution_id()
        assert identifier.startswith("ex-")
        for agent in AgentId:
            assert agent.value not in identifier
        assert identifier.count("-") == 1

    def test_two_executions_of_one_request_have_different_ids(self, workspace_root):
        request = make_request(workspace_root)
        first = execute(request, body=OfflineBody(agent_id=AgentId.DSH))
        second = execute(request, body=OfflineBody(agent_id=AgentId.DSH))

        assert first.execution_id != second.execution_id
        assert first.execution_id not in second.execution_id
        assert second.execution_id not in first.execution_id

    def test_an_execution_id_is_not_a_task_reference(self, workspace_root):
        """§7.2: task/work-item identity is not execution identity."""
        request = make_request(workspace_root, task="the-task")
        result = execute(request, body=OfflineBody(agent_id=AgentId.DSH))
        assert result.execution_id != request.task
        assert request.task not in result.execution_id


class TestOneTerminalResultForEveryOutcome:
    """T29, T42 — §7.1.1, §11."""

    def test_the_outcome_vocabulary_is_exactly_three(self):
        assert [m.value for m in AgentExecutionOutcome] == [
            "COMPLETED",
            "FAILED",
            "BLOCKED",
        ]

    def test_completed_produces_exactly_one_result(self, workspace_root):
        result = execute(make_request(workspace_root), body=OfflineBody(agent_id=AgentId.DSH))
        assert result.outcome is AgentExecutionOutcome.COMPLETED
        assert result.execution_id
        assert result.result

    def test_failed_still_produces_exactly_one_result(self, workspace_root):
        """The point of T42: FAILED does not mean "no AgentResult"."""
        result = execute(make_request(workspace_root), body=_ExplodingBody())
        assert result.outcome is AgentExecutionOutcome.FAILED
        assert result.execution_id
        assert result.result
        assert result.blocking

    def test_blocked_still_produces_exactly_one_result(self, workspace_root):
        request = make_request(workspace_root)
        blocked_request = AgentExecutionRequest(
            agent_id=request.agent_id,
            workspace_root=request.workspace_root + "-does-not-exist",
            task=request.task,
            input_digest=request.input_digest,
        )
        result = execute(blocked_request, body=_ExplodingBody())

        # The body would have raised had it run. It did not run, and the
        # controller produced the record anyway.
        assert result.outcome is AgentExecutionOutcome.BLOCKED
        assert result.execution_id
        assert result.result

    @pytest.mark.parametrize("outcome", list(AgentExecutionOutcome))
    def test_result_is_present_for_every_outcome(self, outcome, workspace_root):
        """T43 — §10.2. `result` is never absent, and never a task result it lacks."""
        if outcome is AgentExecutionOutcome.COMPLETED:
            result = execute(make_request(workspace_root), body=OfflineBody(agent_id=AgentId.DSH))
        elif outcome is AgentExecutionOutcome.FAILED:
            result = execute(make_request(workspace_root), body=_ExplodingBody())
        else:
            request = make_request(workspace_root)
            result = execute(
                AgentExecutionRequest(
                    agent_id=request.agent_id,
                    workspace_root=request.workspace_root + "-missing",
                    task=request.task,
                    input_digest=request.input_digest,
                ),
                body=_ExplodingBody(),
            )
        assert result.outcome is outcome
        assert isinstance(result.result, str) and result.result

    def test_the_controller_has_one_place_a_result_is_built(self):
        """§7.1.1 as a structural claim: no early return without a result."""
        tree = ast.parse(pathlib.Path("agents/runtime.py").read_text(encoding="utf-8"))
        controller = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "execute"
        )
        returns = [
            node
            for node in ast.walk(controller)
            if isinstance(node, ast.Return) and node.value is not None
        ]
        # Every `return <value>` in the controller returns the single
        # terminal-result constructor, so there is no path that returns a
        # non-result or returns nothing.
        assert len(returns) == 4
        for node in returns:
            assert isinstance(node.value, ast.Call), ast.dump(node.value)[:80]
            assert getattr(node.value.func, "id", "") == "_terminal_result"


class TestBlockedIsExecutionLevel:
    """T30 — §11.1."""

    def test_a_body_that_never_started_is_blocked(self, workspace_root):
        request = make_request(workspace_root)
        result = execute(
            AgentExecutionRequest(
                agent_id=request.agent_id,
                workspace_root=request.workspace_root + "-absent",
                task=request.task,
                input_digest=request.input_digest,
            ),
            body=_ExplodingBody(),
        )
        assert result.outcome is AgentExecutionOutcome.BLOCKED
        assert result.reason_code == "WORKSPACE_UNAVAILABLE"
        assert result.workspace_id == ""

    def test_a_body_that_started_is_never_blocked(self, workspace_root):
        result = execute(make_request(workspace_root), body=_ExplodingBody())
        assert result.outcome is AgentExecutionOutcome.FAILED
        assert result.outcome is not AgentExecutionOutcome.BLOCKED

    def test_no_authorization_is_an_execution_level_precondition(self):
        """§11.1 closes the list, and it holds no authorization member."""
        source = pathlib.Path("agents/runtime.py").read_text(encoding="utf-8")
        for forbidden in ("DENY", "not_allowed", "unauthorized"):
            assert forbidden not in source, forbidden


class TestToolBlockedIsNotExecutionBlocked:
    """T31 — §11.2."""

    def test_a_guard_refused_tool_call_does_not_rewrite_the_outcome(
        self, workspace_root, echo_registry
    ):
        """The body ran, so the execution is COMPLETED — and says so."""
        plan = (
            ToolInvocation(
                tool_id=ECHO_TOOL_ID,
                tool_version=ECHO_TOOL_VERSION,
                adapter_family=AdapterFamily.TERMINAL,
                operation="echo",
                permission_level=PermissionLevel.READ,
                target=TargetRef(kind=TargetKind.REPOSITORY),
                timeout_seconds=5,
            ),
        )
        # No policy: Guard refuses, and the tool never runs.
        result = execute(
            make_request(workspace_root),
            body=OfflineBody(agent_id=AgentId.DSH, plan=plan),
            registry=echo_registry,
            policy=None,
        )

        assert result.outcome is AgentExecutionOutcome.COMPLETED
        assert result.outcome is not AgentExecutionOutcome.BLOCKED
        assert len(result.tool_calls) == 1
        call = result.tool_calls[0]
        assert call.outcome is ToolOutcome.BLOCKED
        assert call.guard_decision is GuardDecision.BLOCKED

    def test_the_two_blocked_words_stay_in_their_own_vocabularies(self):
        """§11.2: one word in two vocabularies is a cost, not a conflation."""
        assert "BLOCKED" in {m.value for m in AgentExecutionOutcome}
        assert "BLOCKED" in {m.value for m in ToolOutcome}
        assert AgentExecutionOutcome is not ToolOutcome


class TestNoLaterPhaseVocabularyLeaked:
    """T32 — §11.4."""

    @pytest.mark.parametrize(
        "forbidden", ["TIMED_OUT", "CANCELLED", "RETRYING", "RETRIED", "FALLBACK", "ESCALATED"]
    )
    def test_the_outcome_vocabulary_has_no_ai12_or_ai13_member(self, forbidden):
        assert forbidden not in {m.value for m in AgentExecutionOutcome}

    def test_no_retry_or_resume_machinery_exists(self):
        """§7.2: a second attempt is a second execution, not a retry state.

        Checked over defined names rather than raw text: the prose that
        *documents* the prohibition is not the prohibition.
        """
        forbidden = ("retry", "resume", "checkpoint", "fallback", "escalat")
        for path in sorted(pathlib.Path("agents").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name.lower()
                elif isinstance(node, ast.Attribute):
                    name = node.attr.lower()
                else:
                    continue
                for needle in forbidden:
                    assert needle not in name, f"{path}: {node.name}"


class TestTheResultReferenceShape:
    """Amendment-review regression — §10.2 at the construction boundary.

    The defect this class exists for: `result` was caller convention only. A body
    returning `BodyOutcome(result_ref="AWS_SECRET=...\nraw task body")` had the
    whole string written into a COMPLETED AgentResult verbatim, and nothing
    objected.
    """

    def test_the_two_admitted_shapes_are_accepted(self):
        from agents.result import is_valid_result_reference

        assert is_valid_result_reference("sha256:" + "a" * 64)
        assert is_valid_result_reference("ref:agent-block:ex-0123456789abcdef")
        assert is_valid_result_reference("ref:" + "x")

    @pytest.mark.parametrize(
        "value",
        [
            "AWS_SECRET=abc123",              # an assignment
            "raw task body",                  # prose with a space
            "line one\nline two",             # multi-line
            "line one\r\nline two",           # CRLF
            "",                               # empty
            "sha256:" + "A" * 64,             # uppercase hex
            "sha256:" + "a" * 63,             # short digest
            "ref:",                           # empty reference
            "ref:has space",                  # whitespace in the token
            "ref:has\nequals=sign",           # LF and '='
            "not-a-reference",
            None,
            7,
        ],
    )
    def test_raw_and_malformed_forms_are_refused(self, value):
        from agents.result import InvalidResultReference, is_valid_result_reference

        assert not is_valid_result_reference(value)
        with pytest.raises(InvalidResultReference):
            AgentResult(
                agent_id=AgentId.DSH,
                execution_id="ex-1",
                workspace_id="ws-1",
                input_digest="sha256:" + "a" * 64,
                outcome=AgentExecutionOutcome.COMPLETED,
                result=value,
            )

    def test_a_body_returning_raw_content_cannot_produce_a_result(self, workspace_root):
        """The runtime path, not just the constructor."""

        class RawBody:
            def run(self, *, request, context, tools):  # noqa: ANN001, ANN202
                return BodyOutcome(result_ref="AWS_SECRET=abc123\nraw task body")

        from agents.result import InvalidResultReference

        with pytest.raises(InvalidResultReference):
            execute(make_request(workspace_root), body=RawBody())

    def test_every_runtime_produced_reference_has_the_shape(self, workspace_root):
        """Including the failure and block paths — neither bypasses the rule."""
        from agents.result import is_valid_result_reference

        completed = execute(
            make_request(workspace_root), body=OfflineBody(agent_id=AgentId.DSH)
        )
        failed = execute(make_request(workspace_root), body=_ExplodingBody())

        request = make_request(workspace_root)
        blocked = execute(
            AgentExecutionRequest(
                agent_id=request.agent_id,
                workspace_root=request.workspace_root + "-absent",
                task=request.task,
                input_digest=request.input_digest,
            ),
            body=_ExplodingBody(),
        )

        for result in (completed, failed, blocked):
            assert is_valid_result_reference(result.result), result.result
        assert failed.result.startswith("ref:agent-failure:")
        assert blocked.result.startswith("ref:agent-block:")

    def test_the_grammar_is_documented_as_bounded(self):
        """§10.2's limit is stated, not implied away."""
        import pathlib

        source = pathlib.Path("agents/result.py").read_text(encoding="utf-8")
        assert "IS NOT  a universal secret-content classifier" in source
        assert "C-1" in source
