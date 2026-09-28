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
    is_usage_complete,
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


#: The models this suite vouches for, declared explicitly so that no test
#: relies on a production default that would accept anything. The synthetic
#: refs at the end exist to exercise grouping; that they are "real" only
#: within this declared set is the point -- attribution is an argument the
#: caller supplies, not a property intrinsic to a ref.
REGISTERED_IN_TESTS = frozenset(
    {
        DEEPSEEK_REF,
        MIMO_REF,
        "mimo/mimo-v2.6-flash",
        "deepseek/shared-name",
        "mimo/shared-name",
        "synthetic/example",
    }
)


def aggregator(
    *observations, catalog=None, known_model_refs=REGISTERED_IN_TESTS
) -> MetricAggregator:
    return MetricAggregator(
        as_of=AT,
        known_model_refs=known_model_refs,
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
            blocked(block_code=BlockCode.CREDENTIAL_CONFIG_DEFECT),
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
        """Codes that name an existing provider and model are collectable."""
        overall = aggregator(
            blocked(block_code=BlockCode.CAPABILITY_NOT_VERIFIED),
            blocked(block_code=BlockCode.CAPABILITY_NOT_VERIFIED),
            blocked(block_code=BlockCode.CREDENTIAL_CONFIG_DEFECT),
        ).snapshot().overall

        assert overall.block_code_counts[BlockCode.CAPABILITY_NOT_VERIFIED] == 2
        assert overall.block_code_counts[BlockCode.CREDENTIAL_CONFIG_DEFECT] == 1


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
        overall = aggregator(
            blocked(block_code=BlockCode.CAPABILITY_NOT_VERIFIED)
        ).snapshot().overall
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


class TestUsageCompleteness:
    """§9.2: a missing token count is null with `usage_status: UNKNOWN`.

    A `Usage` claiming `REPORTED` while omitting a required count is
    self-contradictory. It must not be totalled as a measurement, even though
    its status claims otherwise.
    """

    def test_fully_reported_usage_is_complete(self):
        usage = Usage(100, 200, 300, usage_status=UsageStatus.REPORTED)
        assert is_usage_complete(usage)

    def test_reported_with_a_missing_required_count_is_incomplete(self):
        usage = Usage(input_tokens=100, output_tokens=None, usage_status=UsageStatus.REPORTED)
        assert not is_usage_complete(usage)

    def test_reported_with_a_missing_input_is_incomplete(self):
        usage = Usage(input_tokens=None, output_tokens=200, usage_status=UsageStatus.REPORTED)
        assert not is_usage_complete(usage)

    def test_a_reported_zero_is_complete(self):
        """Zero is a measurement; it must not be downgraded to unknown."""
        usage = Usage(0, 0, 0, usage_status=UsageStatus.REPORTED)
        assert is_usage_complete(usage)
        assert usage.input_tokens == 0
        assert usage.input_tokens is not None

    def test_unknown_usage_is_incomplete(self):
        assert not is_usage_complete(Usage(usage_status=UsageStatus.UNKNOWN))

    def test_estimated_is_not_complete(self):
        """AI-02 does not estimate, and an estimate is never REPORTED."""
        assert not is_usage_complete(Usage(1, 2, 3, usage_status=UsageStatus.ESTIMATED))

    def test_a_missing_cache_count_alone_does_not_make_usage_unknown(self):
        """§9.1 records cache only where the provider reports it.

        Treating an unreported cache as unknown would mark almost every call
        incomplete.
        """
        usage = Usage(
            100,
            200,
            300,
            cache_read_tokens=None,
            cache_write_tokens=None,
            usage_status=UsageStatus.REPORTED,
        )
        assert is_usage_complete(usage)

    def test_partial_reported_usage_is_counted_unknown_in_the_aggregate(self):
        overall = aggregator(
            succeeded(
                usage=Usage(
                    input_tokens=1_000_000,
                    output_tokens=None,
                    usage_status=UsageStatus.REPORTED,
                )
            )
        ).snapshot().overall

        assert overall.tokens.input_tokens == 1_000_000
        assert overall.tokens.usage_unknown_count == 1
        assert not overall.tokens.is_complete

    def test_a_complete_call_plus_a_partial_one_is_incomplete(self):
        overall = aggregator(
            succeeded(usage=Usage(100, 200, 300, usage_status=UsageStatus.REPORTED)),
            succeeded(
                usage=Usage(100, None, None, usage_status=UsageStatus.REPORTED)
            ),
        ).snapshot().overall

        assert overall.tokens.usage_unknown_count == 1
        assert overall.tokens.is_partially_unknown

    def test_the_observation_reports_incompleteness(self):
        observation = succeeded(
            usage=Usage(100, None, None, usage_status=UsageStatus.REPORTED)
        )
        assert not observation.usage_is_complete
        assert observation.is_usage_unknown

    def test_token_aggregate_and_cost_agree_on_partial_usage(self):
        """Both must treat the same partial usage as unknown."""
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
        partial = Usage(
            input_tokens=1_000_000, output_tokens=None, usage_status=UsageStatus.REPORTED
        )
        overall = aggregator(succeeded(usage=partial), catalog=catalog).snapshot().overall

        # The token aggregate refuses to call it complete...
        assert not overall.tokens.is_complete
        assert overall.tokens.usage_unknown_count == 1
        # ...and the cost projection equally refuses to price it.
        assert overall.cost.estimated_cost is None

    def test_token_aggregate_and_cost_agree_on_complete_usage(self):
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
        complete = Usage(1_000_000, 500_000, 1_500_000, usage_status=UsageStatus.REPORTED)
        overall = aggregator(succeeded(usage=complete), catalog=catalog).snapshot().overall

        assert overall.tokens.is_complete
        assert overall.cost.estimated_cost == Decimal("0.20")

    def test_a_real_zero_survives_into_the_aggregate(self):
        overall = aggregator(
            succeeded(usage=Usage(0, 0, 0, usage_status=UsageStatus.REPORTED))
        ).snapshot().overall

        assert overall.tokens.input_tokens == 0
        assert overall.tokens.usage_unknown_count == 0
        assert overall.tokens.is_complete


class TestAttributionRequiresRealEntities:
    """§9.4: a sample that cannot be attributed to a real provider and model
    is not collected.

    The invocation layer already established that a provider or model does not
    exist when it blocks the call for that reason, so the block code carries
    the verdict and no registry lookup is needed.
    """

    @pytest.mark.parametrize(
        "code", [BlockCode.UNKNOWN_PROVIDER, BlockCode.UNKNOWN_MODEL]
    )
    def test_an_unattributable_block_cannot_become_an_observation(self, code):
        with pytest.raises(MetricsError, match="real provider and model"):
            observed(InvocationStatus.BLOCKED, block_code=code)

    def test_an_unattributable_block_is_not_collected(self):
        """Declining is visible through `declined_count`, never silent."""
        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
        with pytest.raises(MetricsError):
            collector.record(
                observed(InvocationStatus.BLOCKED, block_code=BlockCode.UNKNOWN_PROVIDER)
            )
        assert collector.observation_count == 0

    def test_attributable_blocks_are_still_collected(self):
        """A capability block names a real model, so it is collected."""
        collector = aggregator(
            blocked(block_code=BlockCode.CAPABILITY_NOT_VERIFIED),
            blocked(block_code=BlockCode.CREDENTIAL_CONFIG_DEFECT),
            blocked(error_class=ErrorClass.CREDENTIAL_MISSING),
        )
        assert collector.snapshot().overall.blocked_count == 3

    def test_a_narrower_authority_refuses_a_real_but_unlisted_model(self):
        collector = MetricAggregator(as_of=AT, known_model_refs={DEEPSEEK_REF})
        with pytest.raises(MetricsError, match="vouches for"):
            collector.record(succeeded(ref=MIMO_REF))
        assert collector.observation_count == 0

    def test_a_registered_ref_passes_the_authority_check(self):
        collector = MetricAggregator(as_of=AT, known_model_refs={DEEPSEEK_REF})
        collector.record(succeeded(ref=DEEPSEEK_REF))
        assert collector.observation_count == 1

    def test_an_attribution_authority_is_required(self):
        """There is no default that would accept anything (§9.4).

        Without one, §9.4 would hold on the invocation path but not at the
        collection boundary, and a hand-built observation naming a model that
        does not exist would be collectable.
        """
        with pytest.raises(TypeError):
            MetricAggregator(as_of=AT)  # type: ignore[call-arg]

    def test_an_empty_authority_collects_nothing(self):
        """Deny-all is a valid explicit choice, and fails closed."""
        collector = MetricAggregator(as_of=AT, known_model_refs=frozenset())
        with pytest.raises(MetricsError, match="vouches for"):
            collector.record(succeeded(ref=DEEPSEEK_REF))
        assert collector.observation_count == 0

    def test_a_synthetic_ref_is_refused_when_nobody_vouches_for_it(self):
        collector = MetricAggregator(
            as_of=AT, known_model_refs=REGISTERED_IN_TESTS
        )
        with pytest.raises(MetricsError, match="vouches for"):
            collector.record(succeeded(ref="synthetic/not-declared"))
        assert collector.observation_count == 0

    def test_a_synthetic_ref_collects_once_it_is_declared(self):
        """Attribution is an argument the caller supplies, not a property of
        the ref -- declaring it is the explicit act the rule requires."""
        collector = MetricAggregator(
            as_of=AT,
            known_model_refs=REGISTERED_IN_TESTS | {"synthetic/not-declared"},
        )
        collector.record(succeeded(ref="synthetic/not-declared"))
        assert collector.snapshot().overall.request_count == 1

    def test_a_refused_observation_creates_no_bucket(self):
        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
        with pytest.raises(MetricsError):
            collector.record(succeeded(ref="ghost/model"))

        snapshot = collector.snapshot()
        assert snapshot.by_model == {}
        assert snapshot.by_provider == {}
        assert snapshot.overall.request_count == 0

    def test_metrics_never_load_the_registry_themselves(self):
        """The authority is supplied; this module has no registry dependency.

        Asserted against the module namespace and its import statements, not
        against the source text: the docstring shows a caller-side example
        that names the loader, and prose is not a dependency.
        """
        import pathlib

        import providers.metrics as metrics_module

        assert "load_all_model_profiles" not in vars(metrics_module)

        source = pathlib.Path(metrics_module.__file__).read_text(encoding="utf-8")
        assert "from providers.model_registry" not in source
        assert "import model_registry" not in source


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

        aggregator = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
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

        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
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

        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
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

        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
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

        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
        observation = collector.record_invocation(request, result)

        assert observation.status is InvocationStatus.BLOCKED
        assert observation.error_class is ErrorClass.CREDENTIAL_MISSING
        assert collector.snapshot().overall.failure_count == 0

    def test_metrics_never_influence_the_call(
        self, invoker_factory, fake_transport_factory, completion_payload
    ):
        """Observing first, then invoking, changes nothing about the invocation."""
        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
        collector.record(succeeded(total_ms=1))

        transport = fake_transport_factory.success(completion_payload())
        request = self._request()
        result = invoker_factory(transport).invoke(request)

        assert result.status is InvocationStatus.SUCCESS
        assert len(transport.requests) == 1

    def test_a_call_to_an_unregistered_provider_is_declined_end_to_end(
        self, invoker_factory, fake_transport_factory
    ):
        """§9.4 enforced on the real path, with no registry dependency."""
        transport = fake_transport_factory.success()
        request = self._request(model_ref="openai-compatible/gpt")
        result = invoker_factory(transport).invoke(request)
        assert result.blocked.code is BlockCode.UNKNOWN_PROVIDER

        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
        assert collector.record_invocation(request, result) is None
        assert collector.observation_count == 0
        assert collector.declined_count == 1

    def test_a_call_to_an_unregistered_model_is_declined_end_to_end(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.success()
        request = self._request(model_ref="deepseek/not-a-real-model")
        result = invoker_factory(transport).invoke(request)

        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
        assert collector.record_invocation(request, result) is None
        assert collector.declined_count == 1

    def test_a_capability_block_is_collected_end_to_end(
        self, invoker_factory, fake_transport_factory
    ):
        transport = fake_transport_factory.success()
        request = self._request(stream=True)
        result = invoker_factory(transport).invoke(request)

        collector = MetricAggregator(as_of=AT, known_model_refs=REGISTERED_IN_TESTS)
        observation = collector.record_invocation(request, result)

        assert observation is not None
        assert collector.declined_count == 0
        assert collector.snapshot().overall.blocked_count == 1

    def test_the_real_registry_registers_exactly_the_in_scope_models(self):
        """The set a caller would pass to `known_model_refs`."""
        from providers.model_registry import load_all_model_profiles

        refs = frozenset(load_all_model_profiles())
        assert refs == {DEEPSEEK_REF, MIMO_REF, "mimo/mimo-v2.6-flash"}

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
