"""Shared test fixtures.

Includes `FakeTransport`, the only `Transport` implementation that exists
anywhere in this repository. AI-02-B1 ships no network transport, so every
adapter path is exercised through canned outcomes and no test can reach a
provider.

No test requires `DEEPSEEK_API_KEY`, `MIMO_API_KEY`, or any credential. The
suite must pass in an environment where both are unset, which is the CI
condition.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from providers.errors import ErrorStage
from providers.protocol import (
    Transport,
    TransportFailureKind,
    TransportRequest,
    TransportResult,
)
from providers.registry import load_provider


class FakeTransport(Transport):
    """Records requests and returns one canned outcome. Never opens a socket."""

    def __init__(self, result: TransportResult) -> None:
        self.result = result
        self.requests: list[TransportRequest] = []

    def send(self, request: TransportRequest) -> TransportResult:
        self.requests.append(request)
        return self.result

    @classmethod
    def success(cls, payload: Any | None = None, http_status: int = 200) -> "FakeTransport":
        if payload is None:
            payload = {
                "id": "fake-completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}],
            }
        return cls(TransportResult.success(http_status=http_status, payload=payload))

    @classmethod
    def timeout(cls) -> "FakeTransport":
        return cls(
            TransportResult.failed(
                TransportFailureKind.TIMEOUT,
                ErrorStage.RECEIVE,
                "read deadline exceeded",
            )
        )

    @classmethod
    def transport_error(cls) -> "FakeTransport":
        return cls(
            TransportResult.failed(
                TransportFailureKind.TRANSPORT,
                ErrorStage.CONNECT,
                "connection refused",
            )
        )

    @classmethod
    def auth_error(cls) -> "FakeTransport":
        return cls(
            TransportResult.success(
                http_status=401,
                payload={"error": {"message": "invalid api key"}},
            )
        )

    @classmethod
    def protocol_error(cls) -> "FakeTransport":
        # A 200 whose body is not an object: the provider broke its own
        # declared protocol.
        return cls(TransportResult.success(http_status=200, payload="not-a-json-object"))

    @classmethod
    def http_error(cls, status: int, message: str = "") -> "FakeTransport":
        return cls(
            TransportResult.success(
                http_status=status, payload={"error": {"message": message}}
            )
        )


@pytest.fixture
def fake_transport_factory():
    return FakeTransport


@pytest.fixture
def deepseek_profile():
    return load_provider("deepseek")


@pytest.fixture
def mimo_profile():
    return load_provider("mimo")


@pytest.fixture
def all_profiles():
    return {pid: load_provider(pid) for pid in ("deepseek", "mimo")}


@pytest.fixture
def body() -> str:
    return json.dumps(
        {
            "model": "deepseek-flash",
            "messages": [{"role": "user", "content": "ping"}],
        }
    )


@pytest.fixture
def example_config():
    """The checked-in runtime provider config."""
    from providers.config import example_config_path, load_provider_config

    return load_provider_config(example_config_path())


@pytest.fixture
def runtime_transport():
    """Runtime transport settings, supplied explicitly to the adapter.

    Transport settings are runtime config, not profile data (§5.11), so tests
    obtain them the same way production code does -- from config, never from a
    `ProviderProfile`.
    """
    from providers.transport import TransportSettings

    return TransportSettings()


@pytest.fixture
def model_profiles():
    """All three registered model profiles, keyed by model ref."""
    from providers.model_registry import load_all_model_profiles

    return load_all_model_profiles()


@pytest.fixture
def deepseek_flash(model_profiles):
    return model_profiles["deepseek/deepseek-flash"]


@pytest.fixture
def mimo_pro(model_profiles):
    return model_profiles["mimo/mimo-v2.6-pro"]


@pytest.fixture
def mimo_flash(model_profiles):
    return model_profiles["mimo/mimo-v2.6-flash"]


#: Synthetic credentials. Never a real key, and never used against a network --
#: the only transport in this suite is `FakeTransport`.
PLACEHOLDER_CREDENTIAL = "sk-test-placeholder-not-a-real-key-000000"


@pytest.fixture
def credentials_env() -> dict[str, str]:
    """An environment where both providers' credential references resolve."""
    return {
        "DEEPSEEK_API_KEY": PLACEHOLDER_CREDENTIAL,
        "MIMO_API_KEY": PLACEHOLDER_CREDENTIAL,
    }


@pytest.fixture
def invoker_factory(model_profiles, all_profiles, credentials_env):
    """Build an `Invoker` over a supplied transport.

    Defaults to an environment where credentials resolve, so a test exercises
    the path it names rather than tripping the credential precondition. Pass
    `environ={}` explicitly to test the no-credential path.

    Transport settings come from runtime config, matching production wiring.
    """
    from providers.invocation import InvocationContext, Invoker
    from providers.transport import TransportSettings

    def build(transport, *, environ=credentials_env, clock=None, settings=None):
        context = InvocationContext(
            providers=all_profiles,
            models=model_profiles,
            transport=transport,
            transport_settings_for=lambda _provider_id: (
                TransportSettings() if settings is None else settings
            ),
            environ=environ,
        )
        if clock is None:
            return Invoker(context)
        return Invoker(context, clock=clock)

    return build


@pytest.fixture
def completion_payload():
    """A minimal, well-formed chat-completion response body."""

    def build(**overrides):
        payload = {
            "id": "chatcmpl-fake-0001",
            "object": "chat.completion",
            "model": "deepseek-flash",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        }
        payload.update(overrides)
        return payload

    return build
