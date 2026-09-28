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
