"""Fixtures for the AI-09 Codex integration layer.

Everything here is offline. The only `Transport` any test in this package can
reach is the shared `FakeTransport` from `tests/conftest.py`; the real HTTP
transport is live-only and is not imported anywhere in this package.

The two contexts below exist for different jobs:

- `context` is a real one, built by AI-03 from a real directory, so workspace
  alignment is exercised against the identity AI-03 actually produces.
- `sentinel_context` is that same context with recognisable markers injected into
  every field family, so an egress test can assert on strings that could not
  appear by accident.
"""

from __future__ import annotations

import dataclasses

import pytest

from plugins.context import (
    ContextItem,
    Freshness,
    ItemKind,
    SourceKind,
    StatusValue,
    build_context,
)

from tests.integrations.support import (
    MIMO_MODEL_REFS,
    SENTINEL_CONTEXT,
    SENTINEL_EXECUTION,
    SENTINEL_SOURCE,
    SENTINEL_WORKSPACE,
    mimo_entry,
    write_provider_config,
)


@pytest.fixture
def providers():
    from providers.registry import load_all_providers

    return load_all_providers()


@pytest.fixture
def models():
    from providers.model_registry import load_all_model_profiles

    return load_all_model_profiles()


@pytest.fixture
def enabled_config(tmp_path):
    """Runtime config that explicitly enables `mimo`."""
    return write_provider_config(tmp_path, {"mimo": mimo_entry(enabled=True)})


@pytest.fixture
def disabled_config(tmp_path):
    """Runtime config that leaves `mimo` disabled — the shipped default."""
    return write_provider_config(tmp_path, {"mimo": mimo_entry(enabled=False)})


@pytest.fixture
def narrowed_config(tmp_path):
    """Runtime config that enables `mimo` but permits only one of its models."""
    return write_provider_config(
        tmp_path,
        {"mimo": mimo_entry(enabled=True, models=("mimo/mimo-v2.6-pro",))},
    )


@pytest.fixture
def reserved_config(tmp_path):
    """Runtime config marking `mimo` reserved. A reserved provider is never enabled."""
    return write_provider_config(
        tmp_path,
        {"mimo": {"enabled": False, "reserved": True, "reserved_for": "AI-09"}},
    )


@pytest.fixture
def missing_entry_config(tmp_path):
    """Runtime config with no entry for `mimo` at all."""
    return write_provider_config(tmp_path, {})


@pytest.fixture
def runtime_transport_settings():
    from providers.transport import TransportSettings

    return TransportSettings()


@pytest.fixture
def workspace_root(tmp_path) -> str:
    """A real directory, so AI-03 resolves a real workspace identity for it."""
    return str(tmp_path)


@pytest.fixture
def context(workspace_root):
    """The context AI-03 actually produces for `workspace_root`."""
    return build_context(workspace_root)


@pytest.fixture
def sentinel_context(context):
    """`context`, with sentinel-laden values in every field family.

    Built by replacing fields on a real `ContextResponse` rather than
    hand-constructing one, so the workspace identity stays the one AI-03 derived
    and the alignment precondition still holds.
    """
    item = ContextItem(
        workspace_id=SENTINEL_WORKSPACE,
        item_kind=ItemKind.FACT,
        subject=SENTINEL_CONTEXT,
        value=SENTINEL_CONTEXT,
        source_kind=SourceKind.MASTER_ROADMAP,
        source_identity=SENTINEL_SOURCE,
        source_revision=SENTINEL_EXECUTION,
        retrieved_at="2026-10-02T00:00:00Z",
        freshness=Freshness.UNKNOWN,
        declared_state=None,
        truth_state=StatusValue.UNKNOWN,
        cache_hit=False,
    )
    workspace = dataclasses.replace(
        context.workspace, branch=SENTINEL_WORKSPACE, commit=SENTINEL_EXECUTION
    )
    return dataclasses.replace(
        context,
        workspace=workspace,
        facts=(item,),
        retrieved_at=SENTINEL_EXECUTION,
    )


@pytest.fixture
def invoker_factory(providers, models, runtime_transport_settings, credentials_env):
    """Build an AI-02 `Invoker` over a supplied transport.

    This is the credential-bearing side of the boundary. It lives in the test's
    composition fixtures, never in the integration layer, which is what lets a
    test drive the missing-credential path without the backend ever seeing an
    environment mapping.
    """
    from providers.invocation import InvocationContext, Invoker

    def build(transport, *, environ=credentials_env, clock=None):
        context = InvocationContext(
            providers=providers,
            models=models,
            transport=transport,
            transport_settings_for=lambda _provider_id: runtime_transport_settings,
            environ=environ,
        )
        if clock is None:
            return Invoker(context)
        return Invoker(context, clock=clock)

    return build


@pytest.fixture
def backend_factory(providers, models, enabled_config, invoker_factory, credentials_env):
    """The TEST composition root for a `MimoCodexBackend`.

    The credential-bearing `InvocationContext` is assembled here, in the test
    suite, and handed to the backend as an already-built `Invoker`. That is not
    an implementation shortcut: AI-09 contract §10.1 makes `integrations/codex/`
    the AI-09 boundary in full, so a composition root placed inside the package
    would still be the integration layer holding the credential source. The
    repository has no production application entry point that would own this
    wiring, so it lives here rather than in the layer under test.

    The returned backend therefore has no reference to `environ`, `transport` or
    `transport_settings`, and no parameter for any of them.
    """
    from integrations.codex.backend import MimoCodexBackend

    def build(
        transport,
        *,
        model_ref: str = MIMO_MODEL_REFS[0],
        config=None,
        environ=credentials_env,
        clock=None,
        **kwargs,
    ):
        return MimoCodexBackend(
            model_ref=model_ref,
            config=enabled_config if config is None else config,
            providers=providers,
            models=models,
            invoker=invoker_factory(transport, environ=environ, clock=clock),
            **kwargs,
        )

    return build


@pytest.fixture
def execution_request(workspace_root):
    """A real `AgentExecutionRequest` for the Codex Agent."""
    from agents.request import AgentExecutionRequest
    from agents.vocabulary import AgentId

    return AgentExecutionRequest(
        agent_id=AgentId.CODEX,
        workspace_root=workspace_root,
        task="summarise the workspace",
        input_digest="sha256:" + "b" * 64,
    )
