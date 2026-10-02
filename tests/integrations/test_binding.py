"""Model binding and runtime enablement (contract §5.3, §6, §11).

Layer 1: schema and contract, no transport. Nothing here builds an invocation.
"""

from __future__ import annotations

import dataclasses

import pytest

from integrations.codex.binding import (
    CODEX_PROVIDER_ID,
    SUPPORTED_MODEL_REFS,
    bind_codex_model,
)
from integrations.codex.errors import CodexBindingError

from tests.integrations.support import DEEPSEEK_MODEL_REF, MIMO_MODEL_REFS

pytestmark = pytest.mark.layer1


def _bind(model_ref, *, config, providers, models):
    return bind_codex_model(
        model_ref, config=config, providers=providers, models=models
    )


class TestTheSupportedScope:
    def test_the_provider_is_mimo(self):
        assert CODEX_PROVIDER_ID == "mimo"

    def test_exactly_two_model_refs_and_no_third(self):
        assert SUPPORTED_MODEL_REFS == (
            "mimo/mimo-v2.6-pro",
            "mimo/mimo-v2.6-flash",
        )

    @pytest.mark.parametrize("model_ref", MIMO_MODEL_REFS)
    def test_a_supported_ref_binds(self, model_ref, enabled_config, providers, models):
        binding = _bind(
            model_ref, config=enabled_config, providers=providers, models=models
        )
        assert binding.model_ref == model_ref
        assert binding.provider_id == "mimo"


class TestTheBindingIsExplicitAndNarrow:
    def test_a_malformed_ref_is_refused(self, enabled_config, providers, models):
        with pytest.raises(CodexBindingError, match="malformed"):
            _bind("mimo", config=enabled_config, providers=providers, models=models)

    def test_a_bare_model_id_is_refused(self, enabled_config, providers, models):
        with pytest.raises(CodexBindingError, match="malformed"):
            _bind(
                "mimo-v2.6-pro",
                config=enabled_config,
                providers=providers,
                models=models,
            )

    def test_another_provider_is_refused(self, enabled_config, providers, models):
        with pytest.raises(CodexBindingError, match="serves provider"):
            _bind(
                DEEPSEEK_MODEL_REF,
                config=enabled_config,
                providers=providers,
                models=models,
            )

    def test_an_unregistered_mimo_model_is_refused(
        self, enabled_config, providers, models
    ):
        with pytest.raises(CodexBindingError, match="not a supported AI-09 model ref"):
            _bind(
                "mimo/mimo-v2.6-ultra",
                config=enabled_config,
                providers=providers,
                models=models,
            )

    def test_there_is_no_default_model(self):
        """The constructor requires an explicit ref; there is nothing to fall back to."""
        import inspect

        from integrations.codex.backend import MimoCodexBackend

        parameter = inspect.signature(MimoCodexBackend.__init__).parameters["model_ref"]
        assert parameter.default is inspect.Parameter.empty

    def test_a_missing_ref_is_refused(self, backend_factory, fake_transport_factory):
        transport = fake_transport_factory.success()
        with pytest.raises(CodexBindingError, match="malformed"):
            backend_factory(transport, model_ref=None)

    def test_binding_flash_does_not_yield_pro(self, backend_factory, fake_transport_factory):
        """No fallback, no substitution: the ref asked for is the ref reported."""
        transport = fake_transport_factory.success()
        backend = backend_factory(transport, model_ref="mimo/mimo-v2.6-flash")
        assert backend.binding.model_ref == "mimo/mimo-v2.6-flash"
        assert backend.binding.model_id == "mimo-v2.6-flash"

    def test_the_binding_is_immutable(self, backend_factory, fake_transport_factory):
        transport = fake_transport_factory.success()
        backend = backend_factory(transport)
        with pytest.raises(dataclasses.FrozenInstanceError):
            backend.binding.model_ref = "mimo/mimo-v2.6-flash"

    def test_produce_takes_no_model_parameter(self, backend_factory, fake_transport_factory):
        """AI-08's signature is used verbatim; the model is not a call argument."""
        import inspect

        from integrations.codex.backend import MimoCodexBackend

        parameters = set(inspect.signature(MimoCodexBackend.produce).parameters)
        assert parameters == {"self", "agent_id", "request", "context"}


class TestRuntimeEnablement:
    def test_an_enabled_provider_binds(self, enabled_config, providers, models):
        binding = _bind(
            MIMO_MODEL_REFS[0],
            config=enabled_config,
            providers=providers,
            models=models,
        )
        assert binding.model_ref == MIMO_MODEL_REFS[0]

    def test_a_disabled_provider_is_refused(self, disabled_config, providers, models):
        with pytest.raises(CodexBindingError, match="not enabled by runtime config"):
            _bind(
                MIMO_MODEL_REFS[0],
                config=disabled_config,
                providers=providers,
                models=models,
            )

    def test_the_shipped_example_config_enables_nothing(
        self, example_config, providers, models
    ):
        """`providers.example.yaml` is a template, not production enablement."""
        assert example_config.enabled_providers == ()
        with pytest.raises(CodexBindingError, match="not enabled by runtime config"):
            _bind(
                MIMO_MODEL_REFS[0],
                config=example_config,
                providers=providers,
                models=models,
            )

    def test_profile_existence_is_not_enablement(
        self, missing_entry_config, providers, models
    ):
        """The profile is registered; runtime config says nothing. That is a refusal."""
        assert "mimo" in providers
        with pytest.raises(CodexBindingError, match="no runtime config entry"):
            _bind(
                MIMO_MODEL_REFS[0],
                config=missing_entry_config,
                providers=providers,
                models=models,
            )

    def test_a_reserved_provider_is_refused(self, reserved_config, providers, models):
        with pytest.raises(CodexBindingError, match="reserved extension point"):
            _bind(
                MIMO_MODEL_REFS[0],
                config=reserved_config,
                providers=providers,
                models=models,
            )

    def test_a_model_the_provider_does_not_permit_is_refused(
        self, narrowed_config, providers, models
    ):
        """Config may narrow the provider's set, and the narrowed-out ref is refused."""
        assert (
            _bind(
                "mimo/mimo-v2.6-pro",
                config=narrowed_config,
                providers=providers,
                models=models,
            ).model_ref
            == "mimo/mimo-v2.6-pro"
        )
        with pytest.raises(CodexBindingError, match="not permitted"):
            _bind(
                "mimo/mimo-v2.6-flash",
                config=narrowed_config,
                providers=providers,
                models=models,
            )

    def test_a_refused_binding_never_builds_a_backend(
        self, backend_factory, disabled_config, fake_transport_factory
    ):
        transport = fake_transport_factory.success()
        with pytest.raises(CodexBindingError):
            backend_factory(transport, config=disabled_config)
        assert transport.requests == []


class TestConstructionRefusesBeforeAnyCall:
    def test_a_bad_transport_is_refused(
        self, providers, models, enabled_config, runtime_transport_settings
    ):
        from integrations.codex.backend import MimoCodexBackend

        with pytest.raises(CodexBindingError, match="transport must be"):
            MimoCodexBackend(
                model_ref=MIMO_MODEL_REFS[0],
                config=enabled_config,
                providers=providers,
                models=models,
                transport=object(),
                transport_settings=runtime_transport_settings,
            )

    def test_a_non_positive_timeout_is_refused(
        self, backend_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.success()
        with pytest.raises(CodexBindingError, match="must be > 0"):
            backend_factory(transport, timeout_ms=0)

    def test_the_default_timeout_is_bounded(self):
        import inspect

        from integrations.codex.backend import (
            CODEX_INVOCATION_TIMEOUT_MS,
            MimoCodexBackend,
        )

        assert CODEX_INVOCATION_TIMEOUT_MS > 0
        default = inspect.signature(MimoCodexBackend.__init__).parameters["timeout_ms"]
        assert default.default == CODEX_INVOCATION_TIMEOUT_MS

    def test_transport_is_required_and_has_no_default(self):
        import inspect

        from integrations.codex.backend import MimoCodexBackend

        parameter = inspect.signature(MimoCodexBackend.__init__).parameters["transport"]
        assert parameter.default is inspect.Parameter.empty
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
