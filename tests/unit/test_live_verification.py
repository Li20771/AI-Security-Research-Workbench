"""Opt-in live verification — offline coverage.

Contract §11, §13. Every test here runs with no network: the live mechanism is
exercised through the shared `FakeTransport`, and the tests that assert "no
network activity" assert `transport.requests == []`.

The live probes themselves live in `tests/live/` under the `layer4` marker and
are never run by a default pytest invocation.
"""

from __future__ import annotations

import pathlib

import pytest

from providers.errors import ErrorClass, ErrorStage
from providers.invocation import InvocationContext, ProbeAuthorisation
from providers.live_verification import (
    LIVE_MAX_OUTPUT,
    LIVE_MAX_RETRIES,
    LIVE_OPT_IN_ENV,
    LIVE_OPT_IN_VALUE,
    LIVE_PROVIDER_ALLOWLIST,
    LIVE_TEXT_PROMPT,
    LIVE_TIMEOUT_MS,
    LIVE_TOOL_SCHEMA,
    PROBE_CATALOG,
    LiveBlockCode,
    LiveRunStatus,
    LiveVerifier,
    ProbeOutcome,
    candidate_status,
    endpoint_host,
    evaluate_preconditions,
)
from providers.model_profile import CapabilityEntry, CapabilityName, CapabilityStatus, Provenance
from providers.profile import ModelRef
from providers.protocol import TransportFailureKind
from providers.transport import TransportSettings

pytestmark = pytest.mark.layer2

DEEPSEEK_REF = "deepseek/deepseek-flash"
MIMO_REF = "mimo/mimo-v2.6-pro"


def _context(transport, providers, models, environ):
    return InvocationContext(
        providers=providers,
        models=models,
        transport=transport,
        transport_settings_for=lambda _pid: TransportSettings(),
        environ=environ,
    )


class TestPreconditions:
    """§11.3: opt-in, allowlist, and a resolvable credential, in that order."""

    def test_opt_in_absent_is_not_run(
        self, all_profiles, model_profiles, credentials_env
    ):
        gate = evaluate_preconditions(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            providers=all_profiles,
            models=model_profiles,
            environ=credentials_env,
            opt_in=None,
        )
        assert not gate.allowed
        assert gate.status is LiveRunStatus.NOT_RUN
        assert gate.code is LiveBlockCode.OPT_IN_ABSENT

    @pytest.mark.parametrize("value", ["0", "true", "yes", "", "2"])
    def test_only_the_exact_opt_in_value_enables(
        self, value, all_profiles, model_profiles, credentials_env
    ):
        gate = evaluate_preconditions(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            providers=all_profiles,
            models=model_profiles,
            environ=credentials_env,
            opt_in=value,
        )
        assert gate.status is LiveRunStatus.NOT_RUN

    def test_provider_not_allowlisted_is_blocked(
        self, all_profiles, model_profiles, credentials_env
    ):
        gate = evaluate_preconditions(
            provider_id="openai-compatible",
            model_ref="openai-compatible/gpt",
            providers=all_profiles,
            models=model_profiles,
            environ=credentials_env,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert gate.status is LiveRunStatus.BLOCKED
        assert gate.code is LiveBlockCode.PROVIDER_NOT_ALLOWLISTED

    def test_the_allowlist_is_exactly_the_two_in_scope_providers(self):
        assert LIVE_PROVIDER_ALLOWLIST == {"deepseek", "mimo"}
        assert "openai-compatible" not in LIVE_PROVIDER_ALLOWLIST

    def test_unknown_provider_is_blocked(
        self, all_profiles, model_profiles, credentials_env
    ):
        gate = evaluate_preconditions(
            provider_id="acme",
            model_ref="acme/ghost",
            providers=all_profiles,
            models=model_profiles,
            environ=credentials_env,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert gate.code is LiveBlockCode.PROVIDER_NOT_ALLOWLISTED

    def test_unknown_model_is_blocked(
        self, all_profiles, model_profiles, credentials_env
    ):
        gate = evaluate_preconditions(
            provider_id="deepseek",
            model_ref="deepseek/not-a-real-model",
            providers=all_profiles,
            models=model_profiles,
            environ=credentials_env,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert gate.status is LiveRunStatus.BLOCKED
        assert gate.code is LiveBlockCode.UNKNOWN_MODEL

    def test_a_model_ref_from_another_provider_is_blocked(
        self, all_profiles, model_profiles, credentials_env
    ):
        gate = evaluate_preconditions(
            provider_id="deepseek",
            model_ref=MIMO_REF,
            providers=all_profiles,
            models=model_profiles,
            environ=credentials_env,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert gate.status is LiveRunStatus.BLOCKED

    def test_missing_credential_is_blocked(
        self, all_profiles, model_profiles
    ):
        gate = evaluate_preconditions(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            providers=all_profiles,
            models=model_profiles,
            environ={},
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert gate.status is LiveRunStatus.BLOCKED
        assert gate.code is LiveBlockCode.CREDENTIAL_MISSING

    @pytest.mark.parametrize("value", ["", "   "])
    def test_empty_and_whitespace_credentials_are_missing(
        self, value, all_profiles, model_profiles
    ):
        gate = evaluate_preconditions(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            providers=all_profiles,
            models=model_profiles,
            environ={"DEEPSEEK_API_KEY": value},
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert gate.code is LiveBlockCode.CREDENTIAL_MISSING

    def test_unsupported_credential_scheme_stays_unsupported(
        self, all_profiles, model_profiles
    ):
        """CREDENTIAL_UNSUPPORTED must never collapse into MISSING."""
        import dataclasses

        from providers.profile import CredentialSpec

        provider = dataclasses.replace(
            all_profiles["deepseek"],
            credential=CredentialSpec(ref="vault:secret/deepseek"),
        )
        gate = evaluate_preconditions(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            providers={**all_profiles, "deepseek": provider},
            models=model_profiles,
            environ={},
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert gate.status is LiveRunStatus.BLOCKED
        assert gate.code is LiveBlockCode.CREDENTIAL_UNSUPPORTED
        assert gate.code is not LiveBlockCode.CREDENTIAL_MISSING

    def test_satisfied_preconditions_allow(
        self, all_profiles, model_profiles, credentials_env
    ):
        gate = evaluate_preconditions(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            providers=all_profiles,
            models=model_profiles,
            environ=credentials_env,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert gate.allowed
        assert gate.status is LiveRunStatus.PASS


class TestNoNetworkWithoutEveryPrecondition:
    """Every refusal must leave the transport untouched."""

    def test_opt_in_absent_sends_nothing(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        transport = fake_transport_factory.success()
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        record = verifier.verify(
            provider_id="deepseek", model_ref=DEEPSEEK_REF, opt_in=None
        )
        assert record.status is LiveRunStatus.NOT_RUN
        assert transport.requests == []

    def test_missing_credential_sends_nothing(
        self, fake_transport_factory, all_profiles, model_profiles
    ):
        transport = fake_transport_factory.success()
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, {}))
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert record.status is LiveRunStatus.BLOCKED
        assert transport.requests == []

    def test_unlisted_provider_sends_nothing(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        transport = fake_transport_factory.success()
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        record = verifier.verify(
            provider_id="openai-compatible",
            model_ref="openai-compatible/gpt",
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert record.status is LiveRunStatus.BLOCKED
        assert transport.requests == []

    def test_unknown_model_sends_nothing(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        transport = fake_transport_factory.success()
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        record = verifier.verify(
            provider_id="deepseek",
            model_ref="deepseek/not-a-real-model",
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert transport.requests == []


class TestRequestBoundary:
    """§10, §17, §18: what a live probe is allowed to send."""

    def test_the_prompt_is_a_fixed_literal(self):
        assert LIVE_TEXT_PROMPT == "Reply with exactly: WORKBENCH_LIVE_OK"

    def test_there_is_no_user_prompt_parameter(self):
        """A probe sends one of the catalogue's prompts or it sends nothing."""
        import inspect

        signature = inspect.signature(LiveVerifier.verify)
        assert "prompt" not in signature.parameters
        assert "messages" not in signature.parameters

    def test_prompts_carry_no_repository_content(self):
        from providers import live_verification

        forbidden = ("def ", "import ", "git ", "diff ", ".py", "README", "://")
        for name in dir(live_verification):
            if not name.startswith("LIVE_") or not name.endswith("PROMPT"):
                continue
            prompt = getattr(live_verification, name)
            for marker in forbidden:
                assert marker not in prompt, f"{name} contains {marker!r}"

    def test_the_tool_schema_is_provider_agnostic(self):
        assert LIVE_TOOL_SCHEMA["type"] == "function"
        assert set(LIVE_TOOL_SCHEMA["function"]) <= {
            "name",
            "description",
            "parameters",
        }

    def test_the_output_is_bounded(self):
        assert LIVE_MAX_OUTPUT == 64
        assert LIVE_MAX_OUTPUT <= 128

    def test_the_timeout_is_explicit(self):
        assert isinstance(LIVE_TIMEOUT_MS, int)
        assert 0 < LIVE_TIMEOUT_MS <= 120_000

    def test_retries_are_zero(self):
        assert LIVE_MAX_RETRIES == 0

    def test_the_probe_request_carries_the_boundaries(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        import json

        transport = fake_transport_factory.success(completion_payload())
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
        )
        sent = json.loads(transport.requests[0].body)
        assert sent["messages"] == [{"role": "user", "content": LIVE_TEXT_PROMPT}]
        assert sent["max_tokens"] == LIVE_MAX_OUTPUT
        assert sent["stream"] is False

    def test_the_transport_deadline_comes_from_the_request(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        transport = fake_transport_factory.success(completion_payload())
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
        )
        assert transport.requests[0].timeout_total_ms == LIVE_TIMEOUT_MS
        assert transport.requests[0].verify_tls is True


class TestOneProbeOneRun:
    def test_a_run_sends_one_baseline_request(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        transport = fake_transport_factory.success(completion_payload())
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
        )
        assert len(transport.requests) == 1

    def test_no_retry_after_a_failure(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        transport = fake_transport_factory.timeout()
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
        )
        assert record.status is LiveRunStatus.FAIL
        assert len(transport.requests) == 1


class TestCapabilityPromotionRules:
    """§12, §13, §22: what an observation would and would not support."""

    def test_pass_candidates_verified(self):
        assert candidate_status(ProbeOutcome.PASS) is CapabilityStatus.VERIFIED

    def test_fail_candidates_unavailable(self):
        assert candidate_status(ProbeOutcome.FAIL) is CapabilityStatus.UNAVAILABLE

    def test_inconclusive_candidates_not_verified(self):
        assert (
            candidate_status(ProbeOutcome.INCONCLUSIVE)
            is CapabilityStatus.NOT_VERIFIED
        )

    def test_not_run_changes_nothing(self):
        assert (
            candidate_status(ProbeOutcome.NOT_RUN, CapabilityStatus.UNKNOWN)
            is CapabilityStatus.UNKNOWN
        )
        assert (
            candidate_status(ProbeOutcome.NOT_RUN, CapabilityStatus.DECLARED)
            is CapabilityStatus.DECLARED
        )

    def test_a_text_success_does_not_promote_any_capability(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        """The central rule: a text completion proves text, and nothing else."""
        transport = fake_transport_factory.success(completion_payload())
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
        )
        # The baseline passed...
        assert record.probes[0].status is LiveRunStatus.PASS
        # ...and no capability was observed at all.
        assert record.observations == ()

    def test_a_run_never_modifies_a_profile(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        before = model_profiles[DEEPSEEK_REF].to_dict()
        transport = fake_transport_factory.success(completion_payload())
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert model_profiles[DEEPSEEK_REF].to_dict() == before


class TestProbeCatalogue:
    def test_every_capability_is_either_probed_or_declined(self):
        assert set(PROBE_CATALOG) == set(CapabilityName)

    def test_every_declined_probe_records_a_reason(self):
        for capability, definition in PROBE_CATALOG.items():
            if not definition.available:
                assert definition.unavailable_reason, capability
                assert len(definition.unavailable_reason) > 40

    def test_streaming_reasoning_and_caching_have_no_probe(self):
        for capability in (
            CapabilityName.STREAMING,
            CapabilityName.REASONING,
            CapabilityName.PROMPT_CACHING,
        ):
            assert not PROBE_CATALOG[capability].available, capability

    def test_tool_calling_and_structured_output_are_probed(self):
        assert PROBE_CATALOG[CapabilityName.TOOL_CALLING].available
        assert PROBE_CATALOG[CapabilityName.STRUCTURED_OUTPUT].available

    def test_declined_capabilities_stay_unknown(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        transport = fake_transport_factory.success(completion_payload())
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        by_capability = {obs.capability: obs for obs in record.observations}
        for capability in (
            CapabilityName.STREAMING,
            CapabilityName.REASONING,
            CapabilityName.PROMPT_CACHING,
        ):
            assert by_capability[capability].outcome is ProbeOutcome.NOT_RUN
            assert by_capability[capability].candidate_status is CapabilityStatus.UNKNOWN

    def test_structured_output_is_probed_as_json_object_not_schema(self):
        """§6.7: the two modes are not interchangeable, and json_schema's
        wrapper shape is unverified for both providers."""
        definition = PROBE_CATALOG[CapabilityName.STRUCTURED_OUTPUT]
        assert "json_object" in definition.description
        assert "json_schema" in definition.description


class _Sequenced:
    """Returns a different canned payload per request.

    A live run sends a baseline probe before any capability probe. With one
    canned response the baseline is judged on the probe's payload too -- and a
    tool-call payload would make the baseline itself inconclusive, so the
    capability probe would never run.
    """

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.requests = []

    def send(self, request):
        from providers.protocol import TransportResult

        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self._payloads) - 1)
        return TransportResult.success(200, self._payloads[index])


def _tool_payload(completion_payload, name="workbench_probe", finish="tool_calls"):
    payload = completion_payload()
    payload["choices"][0]["message"] = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "c1", "function": {"name": name, "arguments": "{}"}}],
    }
    payload["choices"][0]["finish_reason"] = finish
    return payload


class TestToolCallProbeJudgement:
    def _run(
        self, baseline, probe, all_profiles, model_profiles, credentials_env
    ):
        verifier = LiveVerifier(
            _context(_Sequenced([baseline, probe]), all_profiles, model_profiles, credentials_env)
        )
        return verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(CapabilityName.TOOL_CALLING,),
        )

    def test_a_matching_tool_call_passes(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        record = self._run(
            completion_payload(),
            _tool_payload(completion_payload),
            all_profiles,
            model_profiles,
            credentials_env,
        )
        observation = record.observations[0]
        assert observation.outcome is ProbeOutcome.PASS
        assert observation.candidate_status is CapabilityStatus.VERIFIED

    def test_answering_in_prose_is_inconclusive_not_a_failure(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        """A prompt that did not elicit a tool call is not evidence the
        capability is absent."""
        record = self._run(
            completion_payload(),
            completion_payload(),
            all_profiles,
            model_profiles,
            credentials_env,
        )
        observation = record.observations[0]
        assert observation.outcome is ProbeOutcome.INCONCLUSIVE
        assert observation.candidate_status is CapabilityStatus.NOT_VERIFIED
        assert observation.candidate_status is not CapabilityStatus.UNAVAILABLE

    def test_a_different_tool_name_still_verifies_the_mechanism(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        """§6.7: this capability records the mechanism, not tool selection.

        A tool call came back and was normalized. Which tool the model chose is
        selection correctness, which AI-11 measures — asserting it here would
        turn an AI-02 capability into an AI-11 benchmark, and would report a
        working mechanism as absent.
        """
        record = self._run(
            completion_payload(),
            _tool_payload(completion_payload, name="other"),
            all_profiles,
            model_profiles,
            credentials_env,
        )
        observation = record.observations[0]
        assert observation.outcome is ProbeOutcome.PASS
        assert observation.candidate_status is CapabilityStatus.VERIFIED
        # The mismatch is still recorded, for a reviewer to see.
        assert "tool-selection correctness" in observation.observed

    def test_a_name_mismatch_is_never_unavailable(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        record = self._run(
            completion_payload(),
            _tool_payload(completion_payload, name="other"),
            all_profiles,
            model_profiles,
            credentials_env,
        )
        assert record.observations[0].candidate_status is not CapabilityStatus.UNAVAILABLE


class TestProviderErrorsAreInconclusive:
    """A failed attempt is not an observation that a capability is absent.

    A TIMEOUT, a 429, or a 500 says the attempt failed. Recording any of them
    as UNAVAILABLE would assert a negative observation that was never made.
    """

    def _observe(self, capability, transport, all_profiles, model_profiles, credentials_env):
        verifier = LiveVerifier(
            _context(transport, all_profiles, model_profiles, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(capability,),
        )
        return record.observations[0]

    @pytest.mark.parametrize(
        "error_class,status_code",
        [
            (ErrorClass.TIMEOUT, None),
            (ErrorClass.RATE_LIMIT, 429),
            (ErrorClass.QUOTA_EXHAUSTED, 402),
            (ErrorClass.SERVER, 500),
            (ErrorClass.AUTHENTICATION, 401),
            (ErrorClass.TRANSPORT, None),
            (ErrorClass.PROTOCOL, None),
        ],
    )
    @pytest.mark.parametrize(
        "capability",
        [CapabilityName.TOOL_CALLING, CapabilityName.STRUCTURED_OUTPUT],
    )
    def test_a_provider_error_is_inconclusive_not_unavailable(
        self,
        capability,
        error_class,
        status_code,
        fake_transport_factory,
        all_profiles,
        model_profiles,
        credentials_env,
        completion_payload,
    ):
        # The baseline must succeed so the capability probe actually runs.
        class Sequenced:
            def __init__(self, factory):
                self._factory = factory
                self.requests = []
                self._calls = 0

            def send(self, request):
                from providers.protocol import TransportResult

                self.requests.append(request)
                self._calls += 1
                if self._calls == 1:
                    return TransportResult.success(200, completion_payload())
                if error_class is ErrorClass.TIMEOUT:
                    return TransportResult(
                        failure=TransportFailureKind.TIMEOUT,
                        stage=ErrorStage.RECEIVE,
                        message="probe timeout",
                    )
                if error_class is ErrorClass.TRANSPORT:
                    return TransportResult(
                        failure=TransportFailureKind.TRANSPORT,
                        stage=ErrorStage.CONNECT,
                        message="probe transport failure",
                    )
                if error_class is ErrorClass.PROTOCOL:
                    return TransportResult.success(200, "not-an-object")
                return TransportResult.success(
                    status_code, {"error": {"message": "provider refused"}}
                )

        observation = self._observe(
            capability,
            Sequenced(fake_transport_factory),
            all_profiles,
            model_profiles,
            credentials_env,
        )

        assert observation.outcome is ProbeOutcome.INCONCLUSIVE, error_class
        assert observation.candidate_status is CapabilityStatus.NOT_VERIFIED, error_class
        assert observation.candidate_status is not CapabilityStatus.UNAVAILABLE
        assert observation.reason and "not an observation" in observation.reason

    def test_a_structured_output_negative_on_a_successful_response_is_unavailable(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        """The one clean negative: a 200 that contradicts the capability."""
        payload = completion_payload()
        payload["choices"][0]["message"]["content"] = "definitely not json"
        transport = fake_transport_factory.success(payload)
        observation = self._observe(
            CapabilityName.STRUCTURED_OUTPUT,
            transport,
            all_profiles,
            model_profiles,
            credentials_env,
        )
        assert observation.outcome is ProbeOutcome.FAIL
        assert observation.candidate_status is CapabilityStatus.UNAVAILABLE


class TestStructuredOutputProbeJudgement:
    def _run(self, baseline, probe, all_profiles, model_profiles, credentials_env):
        verifier = LiveVerifier(
            _context(_Sequenced([baseline, probe]), all_profiles, model_profiles, credentials_env)
        )
        return verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(CapabilityName.STRUCTURED_OUTPUT,),
        )

    def test_a_json_object_passes(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"]["content"] = '{"status": "ok"}'
        record = self._run(
            completion_payload(), payload, all_profiles, model_profiles, credentials_env
        )
        assert record.observations[0].outcome is ProbeOutcome.PASS

    def test_non_json_fails(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"]["content"] = "not json at all"
        record = self._run(
            completion_payload(), payload, all_profiles, model_profiles, credentials_env
        )
        assert record.observations[0].outcome is ProbeOutcome.FAIL

    def test_json_that_is_not_an_object_fails(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        payload = completion_payload()
        payload["choices"][0]["message"]["content"] = "[1, 2, 3]"
        record = self._run(
            completion_payload(), payload, all_profiles, model_profiles, credentials_env
        )
        assert record.observations[0].outcome is ProbeOutcome.FAIL


class TestBaselineFailureStopsTheRun:
    def test_a_failed_baseline_skips_capability_probes(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        transport = fake_transport_factory.http_error(500)
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert record.status is LiveRunStatus.FAIL
        assert len(transport.requests) == 1
        assert all(obs.outcome is ProbeOutcome.NOT_RUN for obs in record.observations)


class TestEvidenceBoundary:
    """§14, §15: what a record contains, and what it must never contain."""

    def _record(self, transport, env, **kwargs):
        _, all_profiles, model_profiles, credentials_env = env
        verifier = LiveVerifier(_context(transport, all_profiles, model_profiles, credentials_env))
        return verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            **kwargs,
        )

    def test_a_record_carries_the_required_fields(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        record = self._record(
            fake_transport_factory.success(completion_payload()),
            (None, all_profiles, model_profiles, credentials_env),
            capabilities=(),
        )
        payload = record.to_dict()
        for field in (
            "run_id",
            "timestamp",
            "provider_id",
            "model_id",
            "model_ref",
            "endpoint_host",
            "status",
            "probes",
        ):
            assert field in payload, field

    def test_a_record_carries_response_metadata_not_response_text(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        record = self._record(
            fake_transport_factory.success(completion_payload()),
            (None, all_profiles, model_profiles, credentials_env),
            capabilities=(),
        )
        rendered = str(record.to_dict())
        assert "hello" not in rendered  # the fixture's content

    def test_a_record_never_carries_a_credential(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        record = self._record(
            fake_transport_factory.success(completion_payload()),
            (None, all_profiles, model_profiles, credentials_env),
            capabilities=(),
        )
        rendered = str(record.to_dict())
        for value in credentials_env.values():
            assert value not in rendered
        assert "sk-" not in rendered
        assert "Authorization" not in rendered

    def test_a_blocked_record_never_carries_a_credential(
        self, fake_transport_factory, all_profiles, model_profiles
    ):
        """A refusal carries the reference, never a resolved value."""
        record = self._record(
            fake_transport_factory.success(),
            (None, all_profiles, model_profiles, {}),
            capabilities=(),
        )
        assert record.status is LiveRunStatus.BLOCKED
        rendered = str(record.to_dict())
        assert "sk-" not in rendered
        assert "DEEPSEEK_API_KEY" in rendered  # the reference is safe to name

    def test_the_endpoint_host_is_a_host_not_a_url(self):
        assert endpoint_host("https://api.deepseek.com/chat/completions") == "api.deepseek.com"
        assert endpoint_host("https://api.xiaomimimo.com/v1/chat") == "api.xiaomimimo.com"

    def test_userinfo_is_stripped_from_the_endpoint_host(self):
        """A URL with userinfo would otherwise put a credential into evidence."""
        assert endpoint_host("https://user:secret@api.example.test/x") == "api.example.test"

    def test_a_non_url_has_no_host(self):
        assert endpoint_host("not-a-url") is None
        assert endpoint_host("") is None

    def test_the_record_states_that_it_grants_nothing(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        record = self._record(
            fake_transport_factory.success(completion_payload()),
            (None, all_profiles, model_profiles, credentials_env),
            capabilities=(),
        )
        assert "not a grant" in record.boundary

    def test_the_record_is_bound_to_one_model_and_endpoint(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        record = self._record(
            fake_transport_factory.success(completion_payload()),
            (None, all_profiles, model_profiles, credentials_env),
            capabilities=(),
        )
        payload = record.to_dict()
        assert payload["model_ref"] == DEEPSEEK_REF
        assert payload["endpoint_host"] == "api.deepseek.com"
        assert payload["timestamp"]


class TestStatusVocabulary:
    def test_the_five_live_states_are_frozen(self):
        assert {s.value for s in LiveRunStatus} == {
            "PASS",
            "FAIL",
            "BLOCKED",
            "NOT_RUN",
            "UNKNOWN",
        }

    def test_not_run_is_not_pass(self):
        assert LiveRunStatus.NOT_RUN is not LiveRunStatus.PASS

    def test_blocked_is_not_pass(self):
        assert LiveRunStatus.BLOCKED is not LiveRunStatus.PASS

    def test_blocked_is_not_fail(self):
        assert LiveRunStatus.BLOCKED is not LiveRunStatus.FAIL


class TestProbeAuthorisation:
    """§7.1's B6 carve-out is narrow and auditable."""

    def test_it_covers_one_capability_on_one_model(self):
        authorisation = ProbeAuthorisation(
            capability=CapabilityName.TOOL_CALLING,
            model_ref=DEEPSEEK_REF,
            authorised_by="test",
        )
        assert authorisation.covers(CapabilityName.TOOL_CALLING, DEEPSEEK_REF)
        assert not authorisation.covers(CapabilityName.STREAMING, DEEPSEEK_REF)
        assert not authorisation.covers(CapabilityName.TOOL_CALLING, MIMO_REF)

    def test_without_authorisation_the_gate_still_refuses(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        """The default path is unchanged: an unverified capability is refused."""
        from providers.invocation import InvocationRequest, Invoker, Message, MessageRole

        transport = fake_transport_factory.success()
        invoker = Invoker(_context(transport, all_profiles, model_profiles, credentials_env))
        result = invoker.invoke(
            InvocationRequest(
                model_ref=DEEPSEEK_REF,
                messages=(Message(MessageRole.USER, "x"),),
                timeout_ms=1000,
                tools=(LIVE_TOOL_SCHEMA,),
            )
        )
        assert result.blocked is not None
        assert transport.requests == []


class TestRunIdentity:
    """P2-1: a run id must identify one run, not one provider."""

    def test_two_runs_of_the_same_model_have_different_ids(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        """Same provider, same model, same day — still two runs."""
        records = []
        for _ in range(2):
            transport = fake_transport_factory.success(completion_payload())
            verifier = LiveVerifier(
                _context(transport, all_profiles, model_profiles, credentials_env)
            )
            records.append(
                verifier.verify(
                    provider_id="deepseek",
                    model_ref=DEEPSEEK_REF,
                    opt_in=LIVE_OPT_IN_VALUE,
                    capabilities=(),
                )
            )
        assert records[0].run_id != records[1].run_id

    def test_refusals_also_get_unique_ids(
        self, fake_transport_factory, all_profiles, model_profiles
    ):
        ids = set()
        for _ in range(3):
            verifier = LiveVerifier(
                _context(fake_transport_factory.success(), all_profiles, model_profiles, {})
            )
            record = verifier.verify(
                provider_id="deepseek", model_ref=DEEPSEEK_REF, opt_in=None
            )
            assert record.status is LiveRunStatus.NOT_RUN
            ids.add(record.run_id)
        assert len(ids) == 3

    def test_the_id_names_the_provider_and_carries_entropy(self):
        from providers.live_verification import new_run_id

        run_id = new_run_id("deepseek")
        assert run_id.startswith("LV-deepseek-")
        assert len(run_id) > len("LV-deepseek-") + 8

    def test_ids_are_not_derived_from_the_timestamp(self):
        """Two runs can share a second; a timestamp is not an identifier."""
        from providers.live_verification import new_run_id

        assert len({new_run_id("mimo") for _ in range(200)}) == 200


class TestMalformedModelRef:
    """P2-2: a malformed ref must produce a refusal, not an exception.

    A refusal that raises is not a refusal — it surfaces as a runner crash
    rather than the machine-readable code the workflow distinguishes on.
    """

    @pytest.mark.parametrize(
        "model_ref", ["", "garbage", "no-slash", "deepseek/", "/model", "a/b/c", "  "]
    )
    def test_a_malformed_ref_is_blocked_not_raised(
        self, model_ref, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        transport = fake_transport_factory.success()
        verifier = LiveVerifier(
            _context(transport, all_profiles, model_profiles, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=model_ref,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert record.status is LiveRunStatus.BLOCKED, model_ref
        assert record.gate.code is LiveBlockCode.UNKNOWN_MODEL, model_ref
        assert transport.requests == []

    @pytest.mark.parametrize("model_ref", ["", "garbage", "no-slash", "deepseek/"])
    def test_the_gate_itself_never_raises(
        self, model_ref, all_profiles, model_profiles, credentials_env
    ):
        gate = evaluate_preconditions(
            provider_id="deepseek",
            model_ref=model_ref,
            providers=all_profiles,
            models=model_profiles,
            environ=credentials_env,
            opt_in=LIVE_OPT_IN_VALUE,
        )
        assert not gate.allowed
        assert gate.code is LiveBlockCode.UNKNOWN_MODEL

    def test_a_malformed_ref_still_produces_an_attributable_record(
        self, fake_transport_factory, all_profiles, model_profiles
    ):
        verifier = LiveVerifier(
            _context(fake_transport_factory.success(), all_profiles, model_profiles, {})
        )
        record = verifier.verify(
            provider_id="deepseek", model_ref="garbage", opt_in=LIVE_OPT_IN_VALUE
        )
        # The raw caller text is not echoed: it is arbitrary input, and the
        # refusal is attributable without repeating it.
        assert record.model_ref == "<invalid>"
        assert "garbage" not in str(record.to_dict())
        assert record.provider_id == "deepseek"
        assert record.run_id

    def test_the_safe_splitter_never_raises(self):
        from providers.live_verification import split_model_ref

        for value in ("", "garbage", "/", "a/b/c", None):
            provider_id, model_id = split_model_ref(value)
            assert isinstance(provider_id, str)
            assert isinstance(model_id, str)


def _single(payload):
    """A transport that always returns one payload — for baseline-only runs."""
    from providers.protocol import TransportResult

    class _Single:
        def __init__(self):
            self.requests = []

        def send(self, request):
            self.requests.append(request)
            return TransportResult.success(200, payload)

    return _Single()


def _profile_with(model_profiles, capability, entry):
    """A synthetic profile whose named capability has the given truth state."""
    import dataclasses as _dc

    base = model_profiles[DEEPSEEK_REF]
    capabilities = _dc.replace(base.capabilities, **{capability.value: entry})
    provenance = base.provenance
    if entry.status is CapabilityStatus.VERIFIED:
        provenance = Provenance(verified_at="2026-09-28", evidence_ref="SYNTHETIC")
    profile = _dc.replace(base, capabilities=capabilities, provenance=provenance)
    return {**model_profiles, DEEPSEEK_REF: profile}


class TestFinishStateGating:
    """§7.3: LENGTH is a truncation warning and UNKNOWN is not STOP.

    Neither can support a positive observation, however the text reads.
    """

    @pytest.mark.parametrize(
        "finish,expected",
        [
            ("stop", LiveRunStatus.PASS),
            ("length", LiveRunStatus.UNKNOWN),
            ("something_new", LiveRunStatus.UNKNOWN),
        ],
    )
    def test_the_baseline_requires_a_clean_stop(
        self,
        finish,
        expected,
        all_profiles,
        model_profiles,
        credentials_env,
        completion_payload,
    ):
        payload = completion_payload()
        payload["choices"][0]["finish_reason"] = finish
        verifier = LiveVerifier(
            _context(_single(payload), all_profiles, model_profiles, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
        )
        assert record.status is expected, finish
        if finish != "stop":
            # Never a pass, and never blamed on the provider either: a
            # truncation says nothing about connectivity.
            assert record.status is not LiveRunStatus.PASS
            assert record.status is not LiveRunStatus.FAIL

    def test_a_missing_finish_state_is_not_a_pass(
        self, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        payload = completion_payload()
        del payload["choices"][0]["finish_reason"]
        verifier = LiveVerifier(
            _context(_single(payload), all_profiles, model_profiles, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
        )
        assert record.status is LiveRunStatus.UNKNOWN

    def _structured(self, finish, content, all_profiles, model_profiles, credentials_env, completion_payload):
        probe = completion_payload()
        probe["choices"][0]["finish_reason"] = finish
        probe["choices"][0]["message"]["content"] = content
        verifier = LiveVerifier(
            _context(
                _Sequenced([completion_payload(), probe]),
                all_profiles,
                model_profiles,
                credentials_env,
            )
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(CapabilityName.STRUCTURED_OUTPUT,),
        )
        return record.observations[0]

    def test_a_truncated_but_valid_json_answer_is_not_verified(
        self, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        """LENGTH with parseable JSON would otherwise look like a pass."""
        observation = self._structured(
            "length", '{"status": "ok"}', all_profiles, model_profiles, credentials_env, completion_payload
        )
        assert observation.outcome is ProbeOutcome.INCONCLUSIVE
        assert observation.candidate_status is CapabilityStatus.NOT_VERIFIED
        assert observation.candidate_status is not CapabilityStatus.VERIFIED

    def test_an_unknown_finish_state_with_valid_json_is_not_verified(
        self, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        observation = self._structured(
            "something_new", '{"status": "ok"}', all_profiles, model_profiles, credentials_env, completion_payload
        )
        assert observation.outcome is ProbeOutcome.INCONCLUSIVE
        assert observation.candidate_status is not CapabilityStatus.VERIFIED

    def test_a_clean_stop_with_valid_json_is_verified(
        self, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        observation = self._structured(
            "stop", '{"status": "ok"}', all_profiles, model_profiles, credentials_env, completion_payload
        )
        assert observation.candidate_status is CapabilityStatus.VERIFIED

    @pytest.mark.parametrize("finish", ["stop", "length", "something_new"])
    def test_returned_tool_calls_under_a_non_tool_call_finish_are_inconclusive(
        self, finish, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        """Calls came back, but the provider did not signal a tool-call turn.

        The observation must agree with TOOL_CALLS semantics, so this is not a
        completed observation of the mechanism.
        """
        probe = _tool_payload(completion_payload, finish=finish)
        verifier = LiveVerifier(
            _context(
                _Sequenced([completion_payload(), probe]),
                all_profiles,
                model_profiles,
                credentials_env,
            )
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(CapabilityName.TOOL_CALLING,),
        )
        observation = record.observations[0]
        assert observation.outcome is ProbeOutcome.INCONCLUSIVE, finish
        assert observation.candidate_status is not CapabilityStatus.VERIFIED

    def test_a_signalled_tool_call_turn_verifies(
        self, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        probe = _tool_payload(completion_payload, finish="tool_calls")
        verifier = LiveVerifier(
            _context(
                _Sequenced([completion_payload(), probe]),
                all_profiles,
                model_profiles,
                credentials_env,
            )
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(CapabilityName.TOOL_CALLING,),
        )
        assert record.observations[0].candidate_status is CapabilityStatus.VERIFIED


class TestCallerInputBoundary:
    """§10: caller-supplied text does not reach a record or a log verbatim."""

    SMUGGLED = "sk-live-not-a-real-key-abcdef"

    def test_a_malformed_ref_carrying_key_shaped_text_is_not_echoed(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        verifier = LiveVerifier(
            _context(fake_transport_factory.success(), all_profiles, model_profiles, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek", model_ref=self.SMUGGLED, opt_in=LIVE_OPT_IN_VALUE
        )
        assert record.status is LiveRunStatus.BLOCKED
        rendered = str(record.to_dict())
        assert self.SMUGGLED not in rendered
        assert "sk-" not in rendered

    def test_a_key_shaped_experiment_id_is_sanitized_not_recorded(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        """An id can be identifier-shaped and secret-shaped at once.

        Hyphens are legal in both, so `sk-...` passes shape validation and
        redaction is what keeps it out of the record. Shape and secrecy are
        different questions and need different checks.
        """
        verifier = LiveVerifier(
            _context(
                fake_transport_factory.success(completion_payload()),
                all_profiles,
                model_profiles,
                credentials_env,
            )
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
            experiment_id=self.SMUGGLED,
        )
        rendered = str(record.to_dict())
        assert self.SMUGGLED not in rendered
        assert "sk-" not in rendered
        assert record.experiment_id == "[REDACTED]"

    @pytest.mark.parametrize(
        "bad",
        [
            "x" * 200,
            "has space",
            "has\nnewline",
            "semi;colon",
            "back`tick`",
            "$(subshell)",
            "a/b",
            "quote'injection",
            "",
        ],
    )
    def test_an_invalid_experiment_id_is_refused_without_echoing_it(
        self, bad, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        transport = fake_transport_factory.success()
        verifier = LiveVerifier(
            _context(transport, all_profiles, model_profiles, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            experiment_id=bad,
        )
        assert record.status is LiveRunStatus.BLOCKED
        assert record.gate.code is LiveBlockCode.INVALID_EXPERIMENT_ID
        if bad:
            assert bad not in str(record.to_dict())
        assert transport.requests == []

    @pytest.mark.parametrize("good", ["EXP-1", "live.2026-09-29", "a_b-c.d", "EXP-2026-09-29-abcdef"])
    def test_a_valid_experiment_id_is_accepted(
        self, good, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        verifier = LiveVerifier(
            _context(fake_transport_factory.success(completion_payload()), all_profiles, model_profiles, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
            experiment_id=good,
        )
        assert record.status is LiveRunStatus.PASS
        assert record.experiment_id == good

    def test_a_valid_model_ref_is_unchanged(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        verifier = LiveVerifier(
            _context(fake_transport_factory.success(completion_payload()), all_profiles, model_profiles, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(),
        )
        assert record.model_ref == DEEPSEEK_REF

    def test_safe_caller_text_redacts_flattens_and_caps(self):
        from providers.live_verification import safe_caller_text

        assert "sk-live-not-a-real-key" not in safe_caller_text(self.SMUGGLED)
        assert "\n" not in safe_caller_text("a\nb")
        assert len(safe_caller_text("x" * 500)) <= 130


class TestNotRunPreservesTruthState:
    """A probe that did not run observed nothing, so it changes nothing."""

    def test_a_failed_baseline_preserves_a_declared_capability(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env
    ):
        declared = CapabilityEntry(
            status=CapabilityStatus.DECLARED,
            declared=True,
            source="synthetic declaration for this test",
        )
        models = _profile_with(model_profiles, CapabilityName.TOOL_CALLING, declared)
        transport = fake_transport_factory.http_error(500)
        verifier = LiveVerifier(_context(transport, all_profiles, models, credentials_env))
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(CapabilityName.TOOL_CALLING,),
        )
        observation = record.observations[0]
        assert observation.outcome is ProbeOutcome.NOT_RUN
        assert observation.candidate_status is CapabilityStatus.DECLARED
        assert observation.candidate_status is not CapabilityStatus.UNKNOWN

    def test_a_declined_probe_preserves_a_declared_capability(
        self, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        declared = CapabilityEntry(
            status=CapabilityStatus.DECLARED,
            declared=True,
            source="synthetic declaration for this test",
        )
        models = _profile_with(model_profiles, CapabilityName.STREAMING, declared)
        verifier = LiveVerifier(
            _context(fake_transport_factory.success(completion_payload()), all_profiles, models, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(CapabilityName.STREAMING,),
        )
        observation = record.observations[0]
        assert observation.outcome is ProbeOutcome.NOT_RUN
        assert observation.candidate_status is CapabilityStatus.DECLARED

    @pytest.mark.parametrize(
        "prior",
        [CapabilityStatus.UNKNOWN, CapabilityStatus.NOT_VERIFIED, CapabilityStatus.UNAVAILABLE],
    )
    def test_every_prior_state_survives_a_not_run(
        self, prior, fake_transport_factory, all_profiles, model_profiles, credentials_env, completion_payload
    ):
        if prior is CapabilityStatus.UNKNOWN:
            entry = CapabilityEntry(status=prior)
        elif prior is CapabilityStatus.NOT_VERIFIED:
            entry = CapabilityEntry(status=prior, declared=True, source="attempted")
        else:
            entry = CapabilityEntry(status=prior, verified=False, source="observed absent")
        models = _profile_with(model_profiles, CapabilityName.PROMPT_CACHING, entry)
        verifier = LiveVerifier(
            _context(fake_transport_factory.success(completion_payload()), all_profiles, models, credentials_env)
        )
        record = verifier.verify(
            provider_id="deepseek",
            model_ref=DEEPSEEK_REF,
            opt_in=LIVE_OPT_IN_VALUE,
            capabilities=(CapabilityName.PROMPT_CACHING,),
        )
        observation = record.observations[0]
        assert observation.outcome is ProbeOutcome.NOT_RUN
        assert observation.candidate_status is prior

    def test_the_candidate_helper_itself_preserves_the_prior(self):
        for prior in CapabilityStatus:
            assert candidate_status(ProbeOutcome.NOT_RUN, prior) is prior


class TestLiveOnlyTransport:
    """The one concrete Transport must not leak into the offline suite."""

    def test_the_http_transport_is_confined_to_the_live_path(self):
        """Only the live entry points may reference it.

        Importing the module opens nothing -- `urllib` performs no I/O at
        import -- and pytest imports every module under `tests/` during
        collection, so the property worth asserting is not "never imported"
        but "referenced nowhere the default path would reach".
        """
        allowed = (
            "providers/http_transport.py",
            "tests/live/",
            "scripts/live/",
            # This guard itself names the thing it guards.
            "tests/unit/test_live_verification.py",
        )
        offenders = []
        for root in ("providers", "tests", "scripts"):
            for path in pathlib.Path(root).rglob("*.py"):
                posix = path.as_posix()
                if "__pycache__" in posix or posix.startswith(allowed):
                    continue
                text = path.read_text(encoding="utf-8")
                if "HttpTransport" in text or "http_transport" in text:
                    offenders.append(posix)
        assert offenders == [], (
            f"the live-only HTTP transport is referenced outside the live "
            f"path: {offenders}"
        )

    def test_no_provider_module_imports_it(self):
        forbidden = ("http_transport", "urllib.request")
        for path in (pathlib.Path("providers")).glob("*.py"):
            if path.name == "http_transport.py":
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                assert marker not in text, f"{path.name} references {marker!r}"

    def test_it_refuses_redirects(self):
        """A redirect could forward the Authorization header elsewhere."""
        source = (
            pathlib.Path("providers") / "http_transport.py"
        ).read_text(encoding="utf-8")
        assert "_NoRedirectHandler" in source
        assert "redirect_request" in source
