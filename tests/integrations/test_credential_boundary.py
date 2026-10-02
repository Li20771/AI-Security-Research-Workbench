"""The credential boundary (contract §13).

Layer 2: behaviour through the shared fake transport, plus structural checks on
the backend's own shape.

Contract §13: *the credential is resolved by the provider layer at invocation
time, and the integration layer never sees it, holds it, or passes it.*

An earlier revision of this layer took an `environ` mapping and forwarded it into
an `InvocationContext`. Nothing there read a key, logged one or put one in a body
— and it was still a violation, because holding the mapping is holding the
credential source. These tests pin the corrected shape so it cannot drift back.

The corrected split:

```text
external composition root   builds InvocationContext(environ=...) and the Invoker
                            over it. OUTSIDE `integrations/` — contract §10.1 makes
                            `integrations/codex/` the AI-09 boundary in full, so a
                            composition root placed inside the package would still
                            be the integration layer holding the credential source.
MimoCodexBackend            receives the Invoker, and has no argument for a mapping
```

The repository has no production application entry point that would own that
wiring, so in this suite it is the `invoker_factory` / `backend_factory` fixtures
that play the composition root. That is test wiring, not production
architecture, and these tests keep the two apart.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from integrations.codex.errors import CodexInvocationError
from integrations.codex.reference import REFERENCE_RE

pytestmark = pytest.mark.layer2

BACKEND = pathlib.Path("integrations/codex/backend.py")

#: Names that would mean the backend had taken over credential resolution.
CREDENTIAL_NAMES = ("CredentialRef", "SecretValue", "resolve", "getenv")


def _code_names(path: pathlib.Path) -> set[str]:
    """Every identifier the module's code names, excluding docstrings.

    AST-based on purpose: this module documents the rule at length, so a
    substring search would match the prose that states the rule and fail the
    test that checks it.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return names


class TestTheBackendHasNoCredentialSurface:
    def test_the_constructor_has_no_environ_parameter(self):
        from integrations.codex.backend import MimoCodexBackend

        parameters = set(inspect.signature(MimoCodexBackend.__init__).parameters)
        assert "environ" not in parameters
        assert parameters == {
            "self",
            "model_ref",
            "config",
            "providers",
            "models",
            "invoker",
            "timeout_ms",
        }

    def test_the_constructor_takes_no_transport_either(self):
        """The transport moved to the composition root along with the mapping.

        A backend that could be handed a transport could be handed a different
        one, and choosing a transport is not this layer's job.
        """
        from integrations.codex.backend import MimoCodexBackend

        parameters = set(inspect.signature(MimoCodexBackend.__init__).parameters)
        assert "transport" not in parameters
        assert "transport_settings" not in parameters

    def test_the_source_names_no_credential_mechanism(self):
        names = _code_names(BACKEND)
        for forbidden in CREDENTIAL_NAMES:
            assert forbidden not in names, f"backend.py names {forbidden!r}"

    def test_the_source_never_binds_an_environment_mapping(self):
        """Not as a parameter, not as a local, not as an attribute, not as prose.

        The raw-text assertion runs alongside the AST one so that reading the file
        — by eye or by `grep` — is a valid audit, not just a scan the AST happens
        to pass. It matches the *identifier*: a word-boundary match leaves the
        English word "environment" alone, which this module legitimately needs
        when it explains where the mapping does belong.
        """
        assert "environ" not in _code_names(BACKEND)
        assert not re.search(r"\benviron\b", BACKEND.read_text(encoding="utf-8"))

    def test_the_source_does_not_import_os(self):
        names = _code_names(BACKEND)
        assert "os" not in names
        assert "os.environ" not in BACKEND.read_text(encoding="utf-8")

    def test_the_instance_holds_no_credential_mapping(
        self, backend_factory, fake_transport_factory, credentials_env
    ):
        transport = fake_transport_factory.success()
        backend = backend_factory(transport, environ=credentials_env)

        assert "environ" not in vars(backend)
        for value in vars(backend).values():
            assert value is not credentials_env

    def test_the_reference_digest_cannot_contain_a_credential(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
        credentials_env,
    ):
        from agents.vocabulary import AgentId

        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport, environ=credentials_env)

        reference = backend.produce(
            agent_id=AgentId.CODEX, request=execution_request, context=context
        )

        assert REFERENCE_RE.match(reference)
        assert credentials_env["MIMO_API_KEY"] not in reference


class TestTheCredentialStaysProviderSide:
    def test_the_invoker_owns_the_credential_bearing_context(
        self, invoker_factory, fake_transport_factory, credentials_env
    ):
        """The mapping reaches an AI-02 object, which is where it belongs."""
        from providers.invocation import InvocationContext

        transport = fake_transport_factory.success()
        invoker = invoker_factory(transport, environ=credentials_env)
        context = invoker._context  # noqa: SLF001 - the boundary under test

        assert isinstance(context, InvocationContext)
        assert context.environ is credentials_env

    def test_only_the_test_composition_root_holds_the_mapping(
        self, backend_factory, fake_transport_factory, credentials_env
    ):
        """The backend it returns does not reference the mapping at all."""
        transport = fake_transport_factory.success()
        backend = backend_factory(transport, environ=credentials_env)

        for value in vars(backend).values():
            assert value is not credentials_env
        assert not hasattr(backend, "_context")

    def test_no_production_module_of_this_layer_holds_the_mapping(self):
        """Not in the backend, and not in a composition module either.

        There is deliberately no `composition.py` here: §10.1 makes the whole
        package the AI-09 boundary, so the credential-bearing context is
        assembled outside it. This asserts the package contains no such module.
        """
        modules = sorted(
            path.name
            for path in pathlib.Path("integrations").rglob("*.py")
            if "__pycache__" not in path.parts
        )
        assert "composition.py" not in modules

        for path in sorted(pathlib.Path("integrations").rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            assert not re.search(r"\benviron\b", path.read_text(encoding="utf-8")), path

    def test_a_missing_credential_is_refused_by_the_provider_layer(
        self, backend_factory, fake_transport_factory, execution_request, context
    ):
        """The backend does not resolve anything: the refusal comes from AI-02."""
        from agents.vocabulary import AgentId

        transport = fake_transport_factory.success()
        backend = backend_factory(transport, environ={})

        with pytest.raises(CodexInvocationError) as excinfo:
            backend.produce(
                agent_id=AgentId.CODEX, request=execution_request, context=context
            )

        result = excinfo.value.result
        assert str(result.status) == "BLOCKED"
        assert str(result.error.error_class) == "CREDENTIAL_MISSING"
        assert transport.requests == []

    def test_a_successful_call_still_uses_exactly_one_invocation(
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

        backend.produce(
            agent_id=AgentId.CODEX, request=execution_request, context=context
        )

        assert len(transport.requests) == 1

    def test_the_credential_never_reaches_the_request_body(
        self,
        backend_factory,
        fake_transport_factory,
        completion_payload,
        execution_request,
        context,
        credentials_env,
    ):
        from agents.vocabulary import AgentId

        transport = fake_transport_factory.success(payload=completion_payload())
        backend = backend_factory(transport, environ=credentials_env)

        backend.produce(
            agent_id=AgentId.CODEX, request=execution_request, context=context
        )

        request = transport.requests[0]
        secret = credentials_env["MIMO_API_KEY"]
        assert secret not in request.body
        assert secret not in request.url
        assert secret not in str(request.redacted_headers())
