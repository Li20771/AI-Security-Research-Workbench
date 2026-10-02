"""The Codex backend's behaviour (contract §8, §12, §17, §18, §19).

Layer 2: behaviour through the shared fake transport. No network, no credential,
and no real network transport anywhere in this package — AI-02's live-only
implementation is not imported, instantiated or named here.
"""

from __future__ import annotations

import json

import pytest

from integrations.codex.errors import (
    CodexAgentMismatch,
    CodexInvocationError,
    CodexWorkspaceMismatch,
)
from integrations.codex.reference import REFERENCE_RE

from tests.integrations.support import (
    SENTINEL_CONTEXT,
    SENTINEL_EXECUTION,
    SENTINEL_SOURCE,
    SENTINEL_WORKSPACE,
)

pytestmark = pytest.mark.layer2

ALL_SENTINELS = (
    SENTINEL_CONTEXT,
    SENTINEL_WORKSPACE,
    SENTINEL_EXECUTION,
    SENTINEL_SOURCE,
)


def _produce(backend, request, context):
    from agents.vocabulary import AgentId

    return backend.produce(agent_id=AgentId.CODEX, request=request, context=context)


class TestAgentIdentity:
    """A Codex backend serves one Agent, and refuses the others.

    `CodexBody` already refuses a mismatched request upstream. This is the
    concrete backend's own invariant: it must not generate a provider invocation
    for an Agent it does not serve, whatever the caller already checked.
    """

    def test_a_dsh_request_is_refused(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        from agents.vocabulary import AgentId

        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        with pytest.raises(CodexAgentMismatch):
            backend.produce(
                agent_id=AgentId.DSH, request=execution_request, context=context
            )

        assert transport.requests == []

    def test_the_refusal_happens_before_any_provider_activity(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        sentinel_context,
    ):
        from agents.vocabulary import AgentId

        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        with pytest.raises(CodexAgentMismatch):
            backend.produce(
                agent_id=AgentId.DSH, request=execution_request, context=sentinel_context
            )

        assert transport.requests == []

    def test_an_unregistered_identity_is_refused(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        with pytest.raises(CodexAgentMismatch):
            backend.produce(
                agent_id="not-registered", request=execution_request, context=context
            )

        assert transport.requests == []

    def test_the_identity_check_is_not_a_model_inference(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        """The AgentId never influences which model answers."""
        from agents.vocabulary import AgentId

        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport, model_ref="mimo/mimo-v2.6-flash")

        backend.produce(
            agent_id=AgentId.CODEX, request=execution_request, context=context
        )

        assert json.loads(transport.requests[0].body)["model"] == "mimo-v2.6-flash"
        assert backend.binding.model_ref == "mimo/mimo-v2.6-flash"


class TestOneInvocation:
    def test_produce_makes_exactly_one_transport_call(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        reference = _produce(backend, execution_request, context)

        assert len(transport.requests) == 1
        assert REFERENCE_RE.match(reference)

    def test_attempts_is_one_and_there_is_no_retry(
        self,
        backend_factory,
        fake_transport_factory,
        execution_request,
        context,
    ):
        """A failing call is observed once, not retried into ambiguity."""
        transport = fake_transport_factory.http_error(500, "boom")
        backend = backend_factory(transport)

        with pytest.raises(CodexInvocationError) as excinfo:
            _produce(backend, execution_request, context)

        assert len(transport.requests) == 1
        assert excinfo.value.result.attempts == 1

    def test_no_retry_loop_on_a_transport_failure(
        self, backend_factory, fake_transport_factory, execution_request, context
    ):
        transport = fake_transport_factory.timeout()
        backend = backend_factory(transport)

        with pytest.raises(CodexInvocationError):
            _produce(backend, execution_request, context)

        assert len(transport.requests) == 1


class TestTheTaskProjection:
    def test_the_task_is_exactly_one_user_message(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        _produce(backend, execution_request, context)

        body = json.loads(transport.requests[0].body)
        assert body["messages"] == [
            {"role": "user", "content": execution_request.task}
        ]

    def test_no_system_message_is_generated(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        _produce(backend, execution_request, context)

        body = json.loads(transport.requests[0].body)
        assert all(m["role"] != "system" for m in body["messages"])

    def test_the_api_model_id_is_sent_and_the_ref_is_not(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        """`model` is the API model id. A display name or a ref is never sent."""
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport, model_ref="mimo/mimo-v2.6-flash")

        _produce(backend, execution_request, context)

        body = json.loads(transport.requests[0].body)
        assert body["model"] == "mimo-v2.6-flash"
        assert "mimo/mimo-v2.6-flash" not in transport.requests[0].body
        assert "MiMo" not in transport.requests[0].body

    def test_no_tool_schema_and_no_response_format_are_sent(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        """A plain invocation requests neither, and Layer B is not an excuse to add them."""
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        _produce(backend, execution_request, context)

        body = json.loads(transport.requests[0].body)
        assert "tools" not in body
        assert "response_format" not in body
        assert body["stream"] is False


class TestContextIsolation:
    def test_no_context_sentinel_reaches_the_request(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        sentinel_context,
    ):
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        _produce(backend, execution_request, sentinel_context)

        request = transport.requests[0]
        haystack = "\n".join(
            (request.url, request.body, json.dumps(dict(request.headers)))
        )
        for sentinel in ALL_SENTINELS:
            assert sentinel not in haystack, sentinel

    def test_the_context_is_not_a_parameter_of_the_request_builder(
        self, backend_factory, fake_transport_factory
    ):
        """There is no argument through which a ContextResponse could reach a payload."""
        import inspect

        from integrations.codex.backend import MimoCodexBackend

        parameters = set(
            inspect.signature(MimoCodexBackend._build_invocation).parameters
        )
        assert "context" not in parameters

    def test_the_credential_never_appears_in_the_body(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
        credentials_env,
    ):
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        _produce(backend, execution_request, context)

        assert credentials_env["MIMO_API_KEY"] not in transport.requests[0].body


class TestWorkspaceAlignment:
    def test_a_matching_workspace_proceeds(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        assert REFERENCE_RE.match(_produce(backend, execution_request, context))
        assert len(transport.requests) == 1

    def test_a_mismatch_is_refused_before_any_transport_activity(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        context,
        tmp_path,
    ):
        """A request for a different workspace than the context describes."""
        from agents.request import AgentExecutionRequest
        from agents.vocabulary import AgentId

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        mismatched = AgentExecutionRequest(
            agent_id=AgentId.CODEX,
            workspace_root=str(elsewhere),
            task="summarise the workspace",
            input_digest="sha256:" + "c" * 64,
        )
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        with pytest.raises(CodexWorkspaceMismatch):
            _produce(backend, mismatched, context)

        assert transport.requests == []

    def test_a_context_from_another_workspace_is_refused(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        tmp_path,
    ):
        from plugins.context import build_context

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        with pytest.raises(CodexWorkspaceMismatch):
            _produce(backend, execution_request, build_context(elsewhere))

        assert transport.requests == []

    def test_an_unresolvable_execution_workspace_is_refused(
        self, backend_factory, fake_transport_factory, completion_payload, context, tmp_path
    ):
        from agents.request import AgentExecutionRequest
        from agents.vocabulary import AgentId

        missing = AgentExecutionRequest(
            agent_id=AgentId.CODEX,
            workspace_root=str(tmp_path / "does-not-exist"),
            task="summarise the workspace",
            input_digest="sha256:" + "d" * 64,
        )
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        with pytest.raises(CodexWorkspaceMismatch):
            _produce(backend, missing, context)

        assert transport.requests == []


class TestResultMapping:
    def test_success_produces_a_reference(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)
        assert REFERENCE_RE.match(_produce(backend, execution_request, context))

    def test_an_error_raises_and_produces_no_reference(
        self, backend_factory, fake_transport_factory, execution_request, context
    ):
        transport = fake_transport_factory.http_error(500, "boom")
        backend = backend_factory(transport)
        with pytest.raises(CodexInvocationError):
            _produce(backend, execution_request, context)

    def test_a_blocked_invocation_raises_and_produces_no_reference(
        self, backend_factory, fake_transport_factory, execution_request, context
    ):
        """No credential resolves, so the call is refused pre-flight."""
        transport = fake_transport_factory.success()
        backend = backend_factory(transport, environ={})

        with pytest.raises(CodexInvocationError) as excinfo:
            _produce(backend, execution_request, context)

        assert transport.requests == []
        # A missing credential is a pre-flight refusal carrying a real taxonomy
        # class, not an invocation-layer BlockCode (AI-02 §5.3, §5.10).
        assert str(excinfo.value.result.status) == "BLOCKED"
        assert str(excinfo.value.result.error.error_class) == "CREDENTIAL_MISSING"

    def test_a_truncated_answer_is_refused(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        payload = completion_payload()
        payload["choices"][0]["finish_reason"] = "length"
        transport = fake_transport_factory.success(payload=payload)
        backend = backend_factory(transport)

        with pytest.raises(CodexInvocationError, match="truncated"):
            _produce(backend, execution_request, context)

    def test_a_non_text_content_shape_is_refused_not_absorbed(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
    ):
        payload = completion_payload()
        payload["choices"][0]["message"]["content"] = [{"type": "text"}]
        transport = fake_transport_factory.success(payload=payload)
        backend = backend_factory(transport)
        with pytest.raises(CodexInvocationError):
            _produce(backend, execution_request, context)


class TestCapabilityTruthIsUntouched:
    def test_a_successful_call_promotes_nothing(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
        models,
    ):
        from providers.model_profile import CapabilityStatus

        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)
        _produce(backend, execution_request, context)

        profile = models["mimo/mimo-v2.6-pro"]
        assert all(
            entry.status is CapabilityStatus.UNKNOWN
            for _, entry in profile.capabilities.items()
        )

    def test_runtime_enablement_does_not_bypass_the_capability_gate(
        self, providers, models, enabled_config, fake_transport_factory, credentials_env
    ):
        """The gate is AI-02's and enablement does not stand in for it."""
        from providers.invocation import (
            InvocationContext,
            InvocationRequest,
            InvocationStatus,
            Invoker,
            Message,
            MessageRole,
        )
        from providers.transport import TransportSettings

        transport = fake_transport_factory.success()
        context = InvocationContext(
            providers=providers,
            models=models,
            transport=transport,
            transport_settings_for=lambda _pid: TransportSettings(),
            environ=credentials_env,
        )
        result = Invoker(context).invoke(
            InvocationRequest(
                model_ref="mimo/mimo-v2.6-pro",
                messages=(Message(role=MessageRole.USER, content="x"),),
                timeout_ms=1_000,
                tools=({"type": "function"},),
            )
        )

        assert result.status is InvocationStatus.BLOCKED
        assert transport.requests == []


class TestThroughTheFrozenSeam:
    def test_a_real_codex_execution_completes_with_the_backend_reference(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
    ):
        """End to end through AI-08's runtime, with AI-08 unchanged.

        `agents.runtime.execute` builds the context itself, so this also proves
        the backend's workspace alignment holds for the identity AI-03 derives
        rather than only for a fixture.
        """
        from agents.codex.body import CodexBody
        from agents.result import AgentExecutionOutcome
        from agents.runtime import execute

        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport)

        result = execute(execution_request, body=CodexBody(backend=backend))

        assert result.outcome is AgentExecutionOutcome.COMPLETED
        assert REFERENCE_RE.match(result.result)
        assert len(transport.requests) == 1
        # No raw output anywhere in the result: the grammar admits a reference only.
        assert execution_request.task not in result.result

    def test_a_provider_failure_yields_failed_not_completed(
        self, backend_factory, fake_transport_factory, execution_request
    ):
        """A failed call must not read as COMPLETED. That is why the backend raises."""
        from agents.codex.body import CodexBody
        from agents.result import AgentExecutionOutcome
        from agents.runtime import execute

        transport = fake_transport_factory.http_error(500, "boom")
        backend = backend_factory(transport)

        result = execute(execution_request, body=CodexBody(backend=backend))

        assert result.outcome is AgentExecutionOutcome.FAILED
        assert not REFERENCE_RE.match(result.result)

    def test_the_backend_satisfies_the_frozen_signature(
        self, backend_factory, fake_transport_factory
    ):
        import inspect

        from agents.codex.body import CodexBackend

        transport = fake_transport_factory.success()
        backend = backend_factory(transport)

        assert isinstance(backend.backend_id, str)
        assert inspect.signature(type(backend).produce) == inspect.signature(
            CodexBackend.produce
        )
