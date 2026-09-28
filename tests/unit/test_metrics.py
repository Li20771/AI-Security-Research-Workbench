"""Metrics observation and aggregation.

Contract §9.1, §9.2, §9.4. Metrics observe facts; they never feed back into a
call. The most load-bearing assertions here are that `BLOCKED` is not a
failure, that unknown is not zero, and that an aggregate containing unknown
usage cannot be read as complete.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from providers.errors import ErrorClass
from providers.invocation import (
    BlockCode,
    InvocationRequest,
    InvocationStatus,
    Latency,
    Message,
    MessageRole,
    Usage,
    UsageStatus,
)
from providers.metrics import (
    MetricAggregator,
    MetricObservation,
    MetricsError,
    TokenTotals,
)
from providers.pricing import PricingCatalog, PricingRecord
from providers.protocol import FinishState

AT = date(2026, 9, 28)
DEEPSEEK_REF = "deepseek/deepseek-flash"
MIMO_REF = "mimo/mimo-v2.6-pro"


def observed(
    status: InvocationStatus,
    *,
    ref: str = DEEPSEEK_REF,
    error_class: ErrorClass | None = None,
    block_code: BlockCode | None = None,
    usage: Usage | None = None,
    total_ms: int | None = None,
    attempts: int = 1,
    experiment_id: str | None = None,
    task_class: str | None = None,
) -> MetricObservation:
    provider_id, model_id = ref.split("/", 1)
    return MetricObservation(
        provider_id=provider_id,
        model_id=model_id,
        model_ref=ref,
        status=status,
        error_class=error_class,
        block_code=block_code,
        attempts=attempts,
        latency=Latency(total_ms=total_ms),
        usage=usage if usage is not None else Usage(usage_status=UsageStatus.UNKNOWN),
        experiment_id=experiment_id,
        task_class=task_class,
    )


def succeeded(**kwargs) -> MetricObservation:
    return observed(InvocationStatus.SUCCESS, **kwargs)


def failed(error_class: ErrorClass, **kwargs) -> MetricObservation:
    return observed(InvocationStatus.ERROR, error_class=error_class, **kwargs)


def blocked(**kwargs) -> MetricObservation:
    return observed(InvocationStatus.BLOCKED, **kwargs)


def aggregator(*observations, catalog=None) -> MetricAggregator:
    return MetricAggregator(
        as_of=AT,
        catalog=catalog,
        observations=observations,
    )


class TestCounters:
    def test_counts_are_separated_by_status(self):
        snapshot = aggregator(
            succeeded(total_ms=10),
            failed(ErrorClass.SERVER),
            blocked(block_code=BlockCode.CAPABILITY_NOT_VERIFIED),
        ).snapshot()

        overall = snapshot.overall
        assert overall.request_count == 3
        assert overall.success_count == 1
        assert overall.failure_count == 1
        assert overall.blocked_count == 1

    def test_blocked_is_never_counted_as_a_failure(self):
        snapshot = aggregator(
            failed(ErrorClass.SERVER),
            blocked(block_code=BlockCode.CAPABILITY_NOT_VERIFIED),
            blocked(block_code=BlockCode.UNKNOWN_MODEL),
        ).snapshot()

        assert snapshot.overall.failure_count == 1
        assert snapshot.overall.blocked_count == 2

    def test_a_credential_precondition_is_blocked_not_failed(self):
        snapshot = aggregator(
            blocked(error_class=ErrorClass.CREDENTIAL_MISSING)
        ).snapshot()

        assert snapshot.overall.blocked_count == 1
        assert snapshot.overall.failure_count == 0

    def test_blocked_does_not_increment_timeout(self):
        snapshot = aggregator(
            blocked(error_class=ErrorClass.CREDENTIAL_MISSING)
        ).snapshot()
        assert snapshot.overall.timeout_count == 0

    def test_timeout_is_counted_independently_and_also_a_failure(self):
        snapshot = aggregator(
            failed(ErrorClass.TIMEOUT),
            failed(ErrorClass.SERVER),
        ).snapshot()

        assert snapshot.overall.failure_count == 2
        assert snapshot.overall.timeout_count == 1

    def test_an_empty_aggregator_reports_zeroes_not_nulls(self):
        overall = aggregator().snapshot().overall
        assert overall.request_count == 0
        assert overall.failure_count == 0
        assert overall.is_empty

    def test_attempts_are_recorded_and_not_invented(self):
        overall = aggregator(succeeded(), succeeded()).snapshot().overall
        assert overall.attempts_total == 2
        assert overall.attempts_max == 1

    def test_no_retry_count_is_produced(self):
        """Retry belongs to AI-13; B4 only reports what it was given."""
        payload = aggregator(succeeded()).snapshot().overall.to_dict()
        assert "retry_count" not in payload


class TestErrorClassDistribution:
    @pytest.mark.parametrize(
        "error_class",
        [
            ErrorClass.TIMEOUT,
            ErrorClass.RATE_LIMIT,
            ErrorClass.QUOTA_EXHAUSTED,
            ErrorClass.PROTOCOL,
            ErrorClass.INVALID_REQUEST,
            ErrorClass.SERVER,
            ErrorClass.AUTHENTICATION,
        ],
    )
    def test_each_class_survives_aggregation(self, error_class):
        overall = aggregator(failed(error_class)).snapshot().overall
        assert overall.error_class_counts[error_class] == 1
        assert overall.failure_count == 1

    def test_rate_limit_and_quota_exhausted_stay_distinct(self):
        overall = aggregator(
            failed(ErrorClass.RATE_LIMIT), failed(ErrorClass.QUOTA_EXHAUSTED)
        ).snapshot().overall

        assert overall.error_class_counts[ErrorClass.RATE_LIMIT] == 1
        assert overall.error_class_counts[ErrorClass.QUOTA_EXHAUSTED] == 1

    def test_protocol_and_invalid_request_stay_distinct(self):
        overall = aggregator(
            failed(ErrorClass.PROTOCOL), failed(ErrorClass.INVALID_REQUEST)
        ).snapshot().overall

        assert overall.error_class_counts[ErrorClass.PROTOCOL] == 1
        assert overall.error_class_counts[ErrorClass.INVALID_REQUEST] == 1

    def test_credential_classes_are_kept_from_blocked_calls(self):
        overall = aggregator(
            blocked(error_class=ErrorClass.CREDENTIAL_MISSING),
            blocked(error_class=ErrorClass.CREDENTIAL_UNSUPPORTED),
        ).snapshot().overall

        assert overall.error_class_counts[ErrorClass.CREDENTIAL_MISSING] == 1
        assert overall.error_class_counts[ErrorClass.CREDENTIAL_UNSUPPORTED] == 1
        assert overall.failure_count == 0

    def test_block_codes_are_distributed(self):
        overall = aggregator(
            blocked(block_code=BlockCode.CAPABILITY_NOT_VERIFIED),
            blocked(block_code=BlockCode.CAPABILITY_NOT_VERIFIED),
            blocked(block_code=BlockCode.UNKNOWN_PROVIDER),
        ).snapshot().overall

        assert overall.block_code_counts[BlockCode.CAPABILITY_NOT_VERIFIED] == 2
        assert overall.block_code_counts[BlockCode.UNKNOWN_PROVIDER] == 1


class TestUsageZeroVersusUnknown:
    def test_reported_counts_are_preserved(self):
        overall = aggregator(
            succeeded(usage=Usage(100, 50, 150, usage_status=UsageStatus.REPORTED))
        ).snapshot().overall

        assert overall.tokens.input_tokens == 100
        assert overall.tokens.output_tokens == 50
        assert overall.tokens.usage_unknown_count == 0
        assert overall.tokens.is_complete

    def test_a_genuine_zero_is_preserved_and_is_not_unknown(self):
        overall = aggregator(
            succeeded(usage=Usage(0, 0, 0, usage_status=UsageStatus.REPORTED))
        ).snapshot().overall

        assert overall.tokens.input_tokens == 0
        assert overall.tokens.input_tokens is not None
        assert overall.tokens.usage_unknown_count == 0
        assert overall.tokens.is_complete

    def test_unknown_usage_is_counted_and_not_zeroed(self):
        overall = aggregator(
            succeeded(usage=Usage(usage_status=UsageStatus.UNKNOWN))
        ).snapshot().overall

        assert overall.tokens.input_tokens is None
        assert overall.tokens.input_tokens != 0
        assert overall.tokens.usage_unknown_count == 1
        assert not overall.tokens.is_complete

    def test_a_blocked_call_has_unmeasured_usage(self):
        overall = aggregator(blocked(block_code=BlockCode.UNKNOWN_MODEL)).snapshot().overall
        assert overall.tokens.usage_unknown_count == 1
        assert overall.tokens.input_tokens is None


class TestUnknownPropagation:
    def test_a_partial_aggregate_is_labelled_incomplete(self):
        """100 reported plus one unknown must not read as a complete total."""
        overall = aggregator(
            succeeded(usage=Usage(100, 10, 110, usage_status=UsageStatus.REPORTED)),
            succeeded(usage=Usage(usage_status=UsageStatus.UNKNOWN)),
        ).snapshot().overall

        assert overall.tokens.input_tokens == 100
        assert overall.tokens.usage_unknown_count == 1
        assert not overall.tokens.is_complete
        assert overall.tokens.is_partially_unknown

    def test_the_unknown_count_travels_with_every_total(self):
        overall = aggregator(
            succeeded(usage=Usage(100, 10, 110, usage_status=UsageStatus.REPORTED)),
            succeeded(usage=Usage(usage_status=UsageStatus.UNKNOWN)),
        ).snapshot().overall

        payload = overall.tokens.to_dict()
        assert payload["usage_unknown_count"] == 1
        assert payload["is_complete"] is False
        assert payload["observation_count"] == 2
        assert payload["reported_count"] == 1

    def test_an_all_unknown_aggregate_has_no_totals_at_all(self):
        overall = aggregator(
            succeeded(usage=Usage(usage_status=UsageStatus.UNKNOWN)),
            succeeded(usage=Usage(usage_status=UsageStatus.UNKNOWN)),
        ).snapshot().overall

        assert overall.tokens.input_tokens is None
        assert overall.tokens.output_tokens is None
        assert overall.tokens.usage_unknown_count == 2

    def test_estimation_is_never_fabricated(self):
        """AI-02 does not tokenize locally, so no count is invented."""
        overall = aggregator(
            succeeded(usage=Usage(usage_status=UsageStatus.UNKNOWN))
        ).snapshot().overall
        assert overall.tokens.to_dict().get("usage_status") is None
        assert overall.tokens.input_tokens is None


class TestLatency:
    def test_raw_samples_are_preserved(self):
        overall = aggregator(
            succeeded(total_ms=100), succeeded(total_ms=300), succeeded(total_ms=200)
        ).snapshot().overall

        assert overall.latency.samples == (100, 300, 200)
        assert overall.latency.count == 3

    def test_aggregates_over_the_samples(self):
        overall = aggregator(
            succeeded(total_ms=100), succeeded(total_ms=300), succeeded(total_ms=200)
        ).snapshot().overall

        assert overall.latency.min_ms == 100
        assert overall.latency.max_ms == 300
        assert overall.latency.total_ms == 600
        assert overall.latency.average_ms == 200.0

    def test_unmeasured_latency_is_not_zero(self):
        overall = aggregator(succeeded(total_ms=None)).snapshot().overall
        assert overall.latency.samples == ()
        assert overall.latency.min_ms is None
        assert overall.latency.average_ms is None

    def test_a_blocked_call_contributes_no_latency(self):
        """Nothing was sent, so there is no call latency to record."""
        overall = aggregator(
            blocked(block_code=BlockCode.CAPABILITY_NOT_VERIFIED),
            succeeded(total_ms=250),
        ).snapshot().overall

        assert overall.latency.samples == (250,)
        assert overall.latency.count == 1
        assert 0 not in overall.latency.samples

    def test_no_percentiles_are_invented(self):
        payload = aggregator(succeeded(total_ms=100)).snapshot().overall.latency.to_dict()
        assert set(payload) == {"count", "min_ms", "max_ms", "total_ms", "average_ms", "samples"}


class TestAttribution:
    def test_grouping_by_provider(self):
        snapshot = aggregator(
            succeeded(ref=DEEPSEEK_REF),
            succeeded(ref=MIMO_REF),
            succeeded(ref=MIMO_REF),
        ).snapshot()

        assert snapshot.by_provider["deepseek"].request_count == 1
        assert snapshot.by_provider["mimo"].request_count == 2

    def test_grouping_by_model_uses_the_qualified_ref(self):
        snapshot = aggregator(
            succeeded(ref=DEEPSEEK_REF), succeeded(ref=MIMO_REF)
        ).snapshot()

        assert set(snapshot.by_model) == {DEEPSEEK_REF, MIMO_REF}

    def test_two_providers_are_never_collapsed_into_one_bucket(self):
        snapshot = aggregator(
            succeeded(ref="deepseek/shared-name"), succeeded(ref="mimo/shared-name")
        ).snapshot()

        assert set(snapshot.by_model) == {"deepseek/shared-name", "mimo/shared-name"}

    def test_grouping_by_experiment_and_task_class(self):
        snapshot = aggregator(
            succeeded(experiment_id="EXP-1", task_class="simple"),
            succeeded(experiment_id="EXP-1", task_class="complex-security"),
            succeeded(experiment_id="EXP-2", task_class="simple"),
        ).snapshot()

        assert snapshot.by_experiment["EXP-1"].request_count == 2
        assert snapshot.by_experiment["EXP-2"].request_count == 1
        assert snapshot.by_task_class["simple"].request_count == 2

    def test_unattributed_calls_are_absent_from_the_breakdown(self):
        """No `unknown` bucket is fabricated for a missing experiment id."""
        snapshot = aggregator(succeeded(experiment_id=None)).snapshot()

        assert snapshot.by_experiment == {}
        assert snapshot.overall.request_count == 1

    def test_an_observation_must_name_a_provider(self):
        with pytest.raises(MetricsError, match="provider_id"):
            MetricObservation(
                provider_id="DeepSeek",
                model_id="m",
                model_ref="DeepSeek/m",
                status=InvocationStatus.SUCCESS,
            )

    def test_an_observation_must_name_a_model(self):
        with pytest.raises(MetricsError, match="model_id"):
            MetricObservation(
                provider_id="deepseek",
                model_id="  ",
                model_ref="deepseek/  ",
                status=InvocationStatus.SUCCESS,
            )

    def test_an_observation_ref_must_match_its_parts(self):
        with pytest.raises(MetricsError, match="model_ref"):
            MetricObservation(
                provider_id="deepseek",
                model_id="deepseek-flash",
                model_ref="mimo/deepseek-flash",
                status=InvocationStatus.SUCCESS,
            )


class TestObservationConsistency:
    def test_a_success_may_not_carry_an_error_class(self):
        with pytest.raises(MetricsError, match="SUCCESS"):
            observed(InvocationStatus.SUCCESS, error_class=ErrorClass.SERVER)

    def test_an_error_must_carry_its_class(self):
        with pytest.raises(MetricsError, match="ERROR"):
            observed(InvocationStatus.ERROR)

    def test_a_blocked_call_may_carry_a_precondition_class(self):
        observed(InvocationStatus.BLOCKED, error_class=ErrorClass.CREDENTIAL_MISSING)

    def test_a_blocked_call_may_not_carry_a_provider_class(self):
        """An invocation-layer refusal has no provider ErrorClass."""
        with pytest.raises(MetricsError, match="precondition"):
            observed(InvocationStatus.BLOCKED, error_class=ErrorClass.SERVER)

    @pytest.mark.parametrize("attempts", [0, -1, True, 1.5])
    def test_attempts_must_be_a_positive_integer(self, attempts):
        with pytest.raises(MetricsError, match="attempts"):
            observed(InvocationStatus.SUCCESS, attempts=attempts)

    def test_a_non_observation_is_rejected(self):
        with pytest.raises(MetricsError):
            aggregator().record({"status": "SUCCESS"})


class TestPricingThroughMetrics:
    def test_no_catalog_means_no_cost(self):
        overall = aggregator(
            succeeded(usage=Usage(1_000_000, 500_000, usage_status=UsageStatus.REPORTED))
        ).snapshot().overall

        assert overall.cost.estimated_cost is None
        assert overall.costed_count == 0
        assert overall.uncosted_count == 1

    def test_a_matching_catalog_projects_a_cost(self):
        catalog = PricingCatalog(
            [
                PricingRecord(
                    provider_id="deepseek",
                    model_id="deepseek-flash",
                    currency="USD",
                    effective_from=date(2026, 9, 1),
                    input_per_1m=Decimal("0.10"),
                    output_per_1m=Decimal("0.20"),
                    source="synthetic",
                )
            ]
        )
        overall = aggregator(
            succeeded(usage=Usage(1_000_000, 500_000, usage_status=UsageStatus.REPORTED)),
            catalog=catalog,
        ).snapshot().overall

        assert overall.cost.estimated_cost == Decimal("0.20")
        assert overall.costed_count == 1
        assert overall.pricing_refs

    def test_a_partially_costed_aggregate_reports_no_total(self):
        """Quoting a partial sum would under-report the corpus cost."""
        catalog = PricingCatalog(
            [
                PricingRecord(
                    provider_id="deepseek",
                    model_id="deepseek-flash",
                    currency="USD",
                    effective_from=date(2026, 9, 1),
                    input_per_1m=Decimal("0.10"),
                    output_per_1m=Decimal("0.20"),
                )
            ]
        )
        overall = aggregator(
            succeeded(usage=Usage(1_000_000, 500_000, usage_status=UsageStatus.REPORTED)),
            succeeded(usage=Usage(usage_status=UsageStatus.UNKNOWN)),
            catalog=catalog,
        ).snapshot().overall

        assert overall.cost.estimated_cost is None
        assert overall.costed_count == 1
        assert overall.uncosted_count == 1
        assert "under-report" in overall.cost.reason

    def test_a_model_without_a_price_never_borrows_anothers(self):
        catalog = PricingCatalog(
            [
                PricingRecord(
                    provider_id="deepseek",
                    model_id="deepseek-flash",
                    currency="USD",
                    effective_from=date(2026, 9, 1),
                    input_per_1m=Decimal("0.10"),
                    output_per_1m=Decimal("0.20"),
                )
            ]
        )
        overall = aggregator(
            succeeded(
                ref=MIMO_REF,
                usage=Usage(1_000_000, 500_000, usage_status=UsageStatus.REPORTED),
            ),
            catalog=catalog,
        ).snapshot().overall

        assert overall.cost.estimated_cost is None

    def test_mixed_currencies_are_not_totalled(self):
        catalog = PricingCatalog(
            [
                PricingRecord(
                    provider_id="deepseek",
                    model_id="deepseek-flash",
                    currency="USD",
                    effective_from=date(2026, 9, 1),
                    input_per_1m=Decimal("1"),
                    output_per_1m=Decimal("1"),
                ),
                PricingRecord(
                    provider_id="mimo",
                    model_id="mimo-v2.6-pro",
                    currency="EUR",
                    effective_from=date(2026, 9, 1),
                    input_per_1m=Decimal("1"),
                    output_per_1m=Decimal("1"),
                ),
            ]
        )
        overall = aggregator(
            succeeded(
                ref=DEEPSEEK_REF,
                usage=Usage(1_000_000, 0, usage_status=UsageStatus.REPORTED),
            ),
            succeeded(
                ref=MIMO_REF,
                usage=Usage(1_000_000, 0, usage_status=UsageStatus.REPORTED),
            ),
            catalog=catalog,
        ).snapshot().overall

        assert overall.cost.estimated_cost is None
        assert "currencies" in overall.cost.reason


class TestImmutabilityAndSafety:
    def test_recording_does_not_change_the_result(self, invoker_factory, fake_transport_factory, completion_payload):
        import dataclasses

        transport = fake_transport_factory.success(completion_payload())
        invoker = invoker_factory(transport)
        request = InvocationRequest(
            model_ref=DEEPSEEK_REF,
            messages=(Message(MessageRole.USER, "ping"),),
            timeout_ms=1000,
        )
        result = invoker.invoke(request)
        before = dataclasses.asdict(result)

        aggregator = MetricAggregator(as_of=AT)
        aggregator.record_invocation(request, result)

        assert dataclasses.asdict(result) == before

    def test_observing_does_not_change_the_observation(self):
        observation = succeeded(total_ms=10)
        returned = aggregator().record(observation)
        assert returned is observation

    def test_observations_carry_no_credential(self, credentials_env):
        rendered = str(succeeded().to_dict()) + repr(succeeded())
        for value in credentials_env.values():
            assert value not in rendered
        assert "sk-" not in rendered
        assert "Authorization" not in rendered

    def test_aggregate_payloads_carry_no_credential(self, credentials_env):
        rendered = str(aggregator(succeeded()).snapshot().to_dict())
        for value in credentials_env.values():
            assert value not in rendered

    def test_pricing_records_carry_no_credential(self, credentials_env):
        from providers.pricing import PricingRecord

        rendered = repr(
            PricingRecord(
                provider_id="deepseek",
                model_id="deepseek-flash",
                currency="USD",
                effective_from=AT,
            )
        )
        for value in credentials_env.values():
            assert value not in rendered


class TestEndToEndWithTheInvoker:
    """The B3 -> B4 relationship, exercised through the real boundary."""

    def _request(self, **overrides) -> InvocationRequest:
        base = {
            "model_ref": DEEPSEEK_REF,
            "messages": (Message(MessageRole.USER, "ping"),),
            "timeout_ms": 1000,
        }
        base.update(overrides)
        return InvocationRequest(**base)

    def test_a_successful_call_is_observed_with_attribution(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        request = self._request()
        result = invoker_factory(
            fake_transport_factory.success(completion_payload())
        ).invoke(request)

        collector = MetricAggregator(as_of=AT)
        observation = collector.record_invocation(request, result)

        assert observation.status is InvocationStatus.SUCCESS
        assert observation.provider_id == "deepseek"
        assert observation.model_id == "deepseek-flash"
        assert observation.model_ref == DEEPSEEK_REF
        assert observation.usage.input_tokens == 11
        assert collector.snapshot().overall.success_count == 1

    def test_a_blocked_call_is_observed_without_a_fabricated_latency(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.success()
        request = self._request(stream=True)
        result = invoker_factory(transport).invoke(request)

        collector = MetricAggregator(as_of=AT)
        observation = collector.record_invocation(request, result)

        assert observation.status is InvocationStatus.BLOCKED
        assert observation.block_code is BlockCode.CAPABILITY_NOT_VERIFIED
        assert observation.latency.total_ms is None
        assert transport.requests == []

        overall = collector.snapshot().overall
        assert overall.blocked_count == 1
        assert overall.failure_count == 0
        assert overall.latency.samples == ()

    def test_request_metadata_reaches_the_observation(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        from providers.invocation import RequestMetadata

        request = self._request(
            metadata=RequestMetadata(
                experiment_id="EXP-B4-1", task_class="complex-security", agent="dsh"
            )
        )
        result = invoker_factory(
            fake_transport_factory.success(completion_payload())
        ).invoke(request)

        collector = MetricAggregator(as_of=AT)
        collector.record_invocation(request, result)
        snapshot = collector.snapshot()

        assert snapshot.by_experiment["EXP-B4-1"].request_count == 1
        assert snapshot.by_task_class["complex-security"].request_count == 1

    def test_a_credential_block_is_observed_with_its_class(
        self, invoker_factory, fake_transport_factory
    ):
        request = self._request()
        result = invoker_factory(
            fake_transport_factory.success(), environ={}
        ).invoke(request)

        collector = MetricAggregator(as_of=AT)
        observation = collector.record_invocation(request, result)

        assert observation.status is InvocationStatus.BLOCKED
        assert observation.error_class is ErrorClass.CREDENTIAL_MISSING
        assert collector.snapshot().overall.failure_count == 0

    def test_metrics_never_influence_the_call(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """Observing first, then invoking, changes nothing about the invocation."""
        collector = MetricAggregator(as_of=AT)
        collector.record(succeeded(total_ms=1))

        transport = fake_transport_factory.success(completion_payload())
        request = self._request()
        result = invoker_factory(transport).invoke(request)

        assert result.status is InvocationStatus.SUCCESS
        assert len(transport.requests) == 1

    def test_read_only_views_cannot_be_mutated(self):
        snapshot = aggregator(succeeded()).snapshot()
        with pytest.raises(TypeError):
            snapshot.by_model["x"] = None  # type: ignore[index]
        with pytest.raises(TypeError):
            snapshot.overall.error_class_counts[ErrorClass.SERVER] = 1  # type: ignore[index]


class TestTokenTotalsHelpers:
    def test_completeness_helpers_agree(self):
        complete = TokenTotals(usage_unknown_count=0)
        assert complete.is_complete
        assert not complete.is_partially_unknown

        partial = TokenTotals(usage_unknown_count=1)
        assert not partial.is_complete
        assert partial.is_partially_unknown
