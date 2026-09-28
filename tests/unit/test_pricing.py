"""Pricing metadata and cost projection.

Contract §9.3. Pricing is metadata, never core logic: there is no built-in
price, no per-model branch, and no fallback between models. A cost that cannot
be derived faithfully is `None`, never `0`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from providers.invocation import Usage, UsageStatus
from providers.pricing import (
    TOKEN_UNIT,
    CostStatus,
    PricingCatalog,
    PricingError,
    PricingRecord,
    PricingStatus,
    empty_catalog,
    project_cost,
)

AT = date(2026, 9, 28)
DEEPSEEK_REF = "deepseek/deepseek-flash"
MIMO_REF = "mimo/mimo-v2.6-pro"


def record(**overrides) -> PricingRecord:
    base = {
        "provider_id": "deepseek",
        "model_id": "deepseek-flash",
        "currency": "USD",
        "effective_from": date(2026, 9, 1),
        "input_per_1m": Decimal("0.10"),
        "output_per_1m": Decimal("0.20"),
        "source": "synthetic test catalog",
    }
    base.update(overrides)
    return PricingRecord(**base)


def reported(input_tokens=None, output_tokens=None, **extra) -> Usage:
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        usage_status=UsageStatus.REPORTED,
        **extra,
    )


class TestNoHardcodedPrice:
    def test_the_default_catalog_is_empty(self):
        assert empty_catalog().is_empty
        assert PricingCatalog().is_empty

    def test_no_price_ships_for_the_in_scope_models(self):
        catalog = empty_catalog()
        for ref in (DEEPSEEK_REF, MIMO_REF):
            assert catalog.lookup(ref, at=AT) is None
            assert catalog.records_for(ref) == ()

    def test_an_empty_catalog_projects_no_cost(self):
        projection = project_cost(
            reported(1_000_000, 1_000_000), empty_catalog(), model_ref=DEEPSEEK_REF, at=AT
        )
        assert projection.estimated_cost is None
        assert projection.pricing_status is PricingStatus.UNKNOWN
        assert projection.cost_status is CostStatus.NO_PRICING


class TestPricingRecordValidation:
    def test_a_minimal_record_constructs(self):
        assert record().model_ref == DEEPSEEK_REF

    @pytest.mark.parametrize("bad", ["DeepSeek", "-x", "", "has space"])
    def test_provider_id_must_be_valid(self, bad):
        with pytest.raises(PricingError):
            record(provider_id=bad)

    def test_model_id_must_not_be_empty(self):
        with pytest.raises(PricingError):
            record(model_id="  ")

    def test_currency_must_not_be_empty(self):
        with pytest.raises(PricingError):
            record(currency="")

    def test_unit_must_be_the_frozen_unit(self):
        with pytest.raises(PricingError, match="unit"):
            record(unit="per_1k_tokens")

    @pytest.mark.parametrize("bad", [Decimal("-0.01"), -1, "-0.5"])
    def test_negative_prices_are_rejected(self, bad):
        with pytest.raises(PricingError, match=">= 0"):
            record(input_per_1m=bad)

    @pytest.mark.parametrize("bad", [True, False, "free", []])
    def test_non_numeric_prices_are_rejected(self, bad):
        with pytest.raises(PricingError):
            record(input_per_1m=bad)

    def test_effective_from_is_required(self):
        with pytest.raises(TypeError):
            PricingRecord(
                provider_id="deepseek", model_id="deepseek-flash", currency="USD"
            )

    def test_effective_from_accepts_an_iso_string(self):
        assert record(effective_from="2026-09-01").effective_from == date(2026, 9, 1)

    def test_effective_from_rejects_a_bad_string(self):
        with pytest.raises(PricingError, match="ISO date"):
            record(effective_from="01/09/2026")

    def test_prices_are_exact_not_binary_floats(self):
        """Decimal(str(x)) keeps 0.1 as 0.1 rather than 0.1000000000000000055."""
        assert record(input_per_1m=0.1).input_per_1m == Decimal("0.1")

    def test_a_record_without_input_and_output_prices_is_not_usable(self):
        """The §9.3 shape allows nulls, but such a record cannot project."""
        assert not record(input_per_1m=None, output_per_1m=None).is_usable

    def test_a_record_missing_only_output_is_not_usable(self):
        assert not record(output_per_1m=None).is_usable

    def test_a_complete_record_is_usable(self):
        assert record().is_usable


class TestCatalogLookup:
    def test_a_matching_record_is_found(self):
        catalog = PricingCatalog([record()])
        assert catalog.lookup(DEEPSEEK_REF, at=AT) is not None

    def test_another_models_price_is_never_used(self):
        """No fallback: a price is specific to one provider and model."""
        catalog = PricingCatalog([record()])
        assert catalog.lookup(MIMO_REF, at=AT) is None
        assert catalog.lookup("deepseek/deepseek-pro", at=AT) is None

    def test_a_future_record_is_not_applied(self):
        catalog = PricingCatalog([record(effective_from=date(2027, 1, 1))])
        assert catalog.lookup(DEEPSEEK_REF, at=AT) is None

    def test_the_latest_applicable_record_wins(self):
        catalog = PricingCatalog(
            [
                record(effective_from=date(2026, 1, 1), input_per_1m=Decimal("1")),
                record(effective_from=date(2026, 6, 1), input_per_1m=Decimal("2")),
            ]
        )
        assert catalog.lookup(DEEPSEEK_REF, at=AT).input_per_1m == Decimal("2")

    def test_a_record_effective_exactly_on_the_date_applies(self):
        catalog = PricingCatalog([record(effective_from=AT)])
        assert catalog.lookup(DEEPSEEK_REF, at=AT) is not None

    def test_an_earlier_date_selects_the_older_record(self):
        catalog = PricingCatalog(
            [
                record(effective_from=date(2026, 1, 1), input_per_1m=Decimal("1")),
                record(effective_from=date(2026, 6, 1), input_per_1m=Decimal("2")),
            ]
        )
        found = catalog.lookup(DEEPSEEK_REF, at=date(2026, 3, 1))
        assert found.input_per_1m == Decimal("1")

    def test_two_records_on_the_same_date_are_rejected(self):
        """Ambiguous lookup would make cost non-reproducible."""
        with pytest.raises(PricingError, match="effective_from"):
            PricingCatalog(
                [
                    record(effective_from=date(2026, 9, 1)),
                    record(effective_from=date(2026, 9, 1), input_per_1m=Decimal("9")),
                ]
            )

    def test_records_for_a_model_are_listed(self):
        catalog = PricingCatalog([record(), record(effective_from=date(2026, 10, 1))])
        assert len(catalog.records_for(DEEPSEEK_REF)) == 2

    def test_the_catalog_rejects_a_non_record(self):
        with pytest.raises(PricingError):
            PricingCatalog([{"provider_id": "deepseek"}])


class TestCostProjection:
    def test_a_full_usage_projectes_exactly(self):
        """1M input at 0.10 plus 500k output at 0.20 is 0.20."""
        projection = project_cost(
            reported(1_000_000, 500_000),
            PricingCatalog([record()]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert projection.estimated_cost == Decimal("0.20")
        assert projection.currency == "USD"
        assert projection.cost_status is CostStatus.PROJECTED
        assert projection.is_known

    def test_zero_tokens_with_pricing_is_a_real_zero(self):
        """A genuine zero is a measurement, unlike an unknown count."""
        projection = project_cost(
            reported(0, 0), PricingCatalog([record()]), model_ref=DEEPSEEK_REF, at=AT
        )
        assert projection.estimated_cost == Decimal("0")
        assert projection.estimated_cost is not None

    def test_unknown_usage_yields_no_cost(self):
        projection = project_cost(
            Usage(usage_status=UsageStatus.UNKNOWN),
            PricingCatalog([record()]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert projection.estimated_cost is None
        assert projection.cost_status is CostStatus.USAGE_UNKNOWN
        # A record *was* found, so pricing_status stays KNOWN: the two facts
        # are independent, and reporting NO_PRICING would misdirect the fix.
        assert projection.pricing_status is PricingStatus.KNOWN

    def test_known_input_with_unknown_output_yields_no_cost(self):
        projection = project_cost(
            reported(1_000_000, None),
            PricingCatalog([record()]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert projection.estimated_cost is None
        assert projection.cost_status is CostStatus.USAGE_UNKNOWN
        assert "output" in projection.reason

    def test_known_output_with_unknown_input_yields_no_cost(self):
        projection = project_cost(
            reported(None, 500_000),
            PricingCatalog([record()]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert projection.estimated_cost is None
        assert "input" in projection.reason

    def test_unknown_cache_with_cache_pricing_yields_no_cost(self):
        """The cached component is priced but unmeasured, so the total is unknown."""
        projection = project_cost(
            reported(1_000_000, 500_000),
            PricingCatalog([record(cache_read_per_1m=Decimal("0.05"))]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert projection.estimated_cost is None
        assert "cache_read" in projection.reason

    def test_a_priced_cache_component_is_included_when_measured(self):
        projection = project_cost(
            reported(1_000_000, 500_000, cache_read_tokens=1_000_000),
            PricingCatalog([record(cache_read_per_1m=Decimal("0.05"))]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        # 0.10 + 0.10 + 0.05
        assert projection.estimated_cost == Decimal("0.25")

    def test_an_unpriced_cache_component_is_not_required(self):
        """A record that does not price cache reads does not need them measured."""
        projection = project_cost(
            reported(1_000_000, 500_000),
            PricingCatalog([record()]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert projection.estimated_cost == Decimal("0.20")

    def test_an_unusable_record_projects_nothing(self):
        projection = project_cost(
            reported(1_000_000, 500_000),
            PricingCatalog([record(input_per_1m=None, output_per_1m=None)]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert projection.estimated_cost is None
        assert projection.cost_status is CostStatus.NO_PRICING
        assert projection.pricing_status is PricingStatus.KNOWN

    def test_no_cost_is_ever_zero_from_absence(self):
        """Every unprojectable case returns None, never Decimal(0)."""
        catalog = PricingCatalog([record()])
        cases = [
            (Usage(usage_status=UsageStatus.UNKNOWN), catalog),
            (reported(1_000_000, None), catalog),
            (reported(None, 500_000), catalog),
            (reported(1_000_000, 500_000), empty_catalog()),
        ]
        for usage, cat in cases:
            projection = project_cost(usage, cat, model_ref=DEEPSEEK_REF, at=AT)
            assert projection.estimated_cost is None
            assert projection.estimated_cost != Decimal("0")


class TestPricingProvenance:
    def test_the_used_record_is_identified(self):
        projection = project_cost(
            reported(1_000_000, 500_000),
            PricingCatalog([record()]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert projection.pricing_ref is not None
        assert projection.pricing_ref.provider_id == "deepseek"
        assert projection.pricing_ref.model_id == "deepseek-flash"
        assert projection.pricing_ref.effective_from == date(2026, 9, 1)

    def test_the_source_is_retained(self):
        projection = project_cost(
            reported(1_000_000, 500_000),
            PricingCatalog([record(source="synthetic test catalog")]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert projection.pricing_ref.source == "synthetic test catalog"

    def test_a_different_record_yields_a_different_cost_for_the_same_usage(self):
        """Cost is a projection; the usage is the durable fact (§9.3)."""
        usage = reported(1_000_000, 500_000)
        cheap = project_cost(
            usage,
            PricingCatalog([record(input_per_1m=Decimal("0.10"))]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        dear = project_cost(
            usage,
            PricingCatalog([record(input_per_1m=Decimal("0.40"))]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        assert cheap.estimated_cost != dear.estimated_cost
        assert usage.input_tokens == 1_000_000

    def test_the_reason_names_the_model_and_date(self):
        projection = project_cost(
            reported(1, 1), empty_catalog(), model_ref=DEEPSEEK_REF, at=AT
        )
        assert DEEPSEEK_REF in projection.reason
        assert AT.isoformat() in projection.reason


class TestSerialization:
    def test_a_projection_serializes_without_a_float(self):
        projection = project_cost(
            reported(1_000_000, 500_000),
            PricingCatalog([record()]),
            model_ref=DEEPSEEK_REF,
            at=AT,
        )
        payload = projection.to_dict()
        assert payload["estimated_cost"] == "0.20"
        assert payload["pricing_ref"]["effective_from"] == "2026-09-01"

    def test_an_unknown_projection_serializes_as_null(self):
        payload = project_cost(
            reported(1, 1), empty_catalog(), model_ref=DEEPSEEK_REF, at=AT
        ).to_dict()
        assert payload["estimated_cost"] is None
        assert payload["cost_status"] == "NO_PRICING"
