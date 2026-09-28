"""Pricing metadata and cost projection.

Implements AI-02 contract §9.3.

Pricing is **updatable metadata, never core logic**. There is no price
constant anywhere in this module, no per-model branch, and no default price.
A cost only exists when a dated pricing record applies to the model and every
component that record prices has a *measured* usage count.

Three rules carry the weight:

**No price is hardcoded.** `PricingCatalog` starts empty. A model with no
record produces `estimated_cost: None`, never `0` and never another model's
price.

**Token counts are durable; cost is a projection.** The same usage priced
against a newer record yields a different cost, which is why callers keep the
raw counts and re-derive cost rather than storing it as fact.

**Unknown usage cannot be priced.** A component with a price but no measured
count makes the *total* unknown, because a partial sum would under-report --
and an under-reported cost is a false figure, not a conservative one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Iterable, Mapping

from providers.profile import PROVIDER_ID_RE
from providers.invocation import Usage, UsageStatus

#: The only unit AI-02 defines (§9.3). A record in another unit would produce
#: a cost off by orders of magnitude, so it is rejected rather than converted.
TOKEN_UNIT = "per_1m_tokens"

_TOKENS_PER_UNIT = Decimal(1_000_000)


class PricingError(ValueError):
    """A pricing record or catalog is malformed. A configuration defect."""


class PricingStatus(StrEnum):
    """Whether an applicable pricing record was found (§9.3)."""

    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class CostStatus(StrEnum):
    """Why a cost projection is or is not available.

    Kept separate from `PricingStatus` because the two are independent facts:
    a record can apply and the cost still be unknown, and reporting "no
    pricing" then would point a reader at the wrong problem.
    """

    PROJECTED = "PROJECTED"
    NO_PRICING = "NO_PRICING"
    USAGE_UNKNOWN = "USAGE_UNKNOWN"


def _as_decimal(value: object, name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise PricingError(f"{name} must be a number or null")
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, (int, float, str)):
        try:
            # `str()` first: Decimal(0.1) is not Decimal("0.1").
            amount = Decimal(str(value))
        except InvalidOperation as exc:
            raise PricingError(f"{name} is not a number: {value!r}") from exc
    else:
        raise PricingError(f"{name} must be a number or null")
    if not amount.is_finite():
        raise PricingError(f"{name} must be finite")
    if amount < 0:
        raise PricingError(f"{name} must be >= 0; got {amount}")
    return amount


def _as_date(value: object, name: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise PricingError(
                f"{name} must be an ISO date (YYYY-MM-DD); got {value!r}"
            ) from exc
    raise PricingError(f"{name} must be a date or ISO date string")


@dataclass(frozen=True, slots=True)
class PricingRecord:
    """A dated price for one model (§9.3).

    `effective_from` is required: a cost figure without its record's date is
    not reproducible, and an undated record cannot participate in versioned
    lookup.

    All four rates are optional in the *shape*, but a record that prices
    neither input nor output cannot project a cost -- `is_usable` reports
    that, rather than the record silently contributing nothing.
    """

    provider_id: str
    model_id: str
    currency: str
    effective_from: date
    unit: str = TOKEN_UNIT
    input_per_1m: Decimal | None = None
    output_per_1m: Decimal | None = None
    cache_read_per_1m: Decimal | None = None
    cache_write_per_1m: Decimal | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        if not PROVIDER_ID_RE.match(self.provider_id or ""):
            raise PricingError(
                f"provider_id {self.provider_id!r} is not a valid provider id"
            )
        if not self.model_id or not self.model_id.strip():
            raise PricingError("model_id must not be empty")
        if not self.currency or not self.currency.strip():
            raise PricingError("currency must not be empty")
        if self.unit != TOKEN_UNIT:
            raise PricingError(
                f"unit must be {TOKEN_UNIT!r}; got {self.unit!r}. A record in "
                "another unit would produce a cost off by orders of magnitude"
            )
        if self.source is not None and not str(self.source).strip():
            raise PricingError("source must be null or a non-empty string")

        for name in (
            "input_per_1m",
            "output_per_1m",
            "cache_read_per_1m",
            "cache_write_per_1m",
        ):
            object.__setattr__(self, name, _as_decimal(getattr(self, name), name))

        object.__setattr__(
            self, "effective_from", _as_date(self.effective_from, "effective_from")
        )

    @property
    def model_ref(self) -> str:
        return f"{self.provider_id}/{self.model_id}"

    @property
    def is_usable(self) -> bool:
        """True when the record prices the two counts a cost requires.

        A record touching neither input nor output cannot project anything; a
        record missing one of them would under-report the total.
        """
        return self.input_per_1m is not None and self.output_per_1m is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "currency": self.currency,
            "unit": self.unit,
            "effective_from": self.effective_from.isoformat(),
            "input_per_1m": str(self.input_per_1m) if self.input_per_1m is not None else None,
            "output_per_1m": str(self.output_per_1m) if self.output_per_1m is not None else None,
            "cache_read_per_1m": (
                str(self.cache_read_per_1m) if self.cache_read_per_1m is not None else None
            ),
            "cache_write_per_1m": (
                str(self.cache_write_per_1m) if self.cache_write_per_1m is not None else None
            ),
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class PricingRef:
    """Which record a projection used, so a cost is never orphaned (§9.3)."""

    provider_id: str
    model_id: str
    effective_from: date
    source: str | None = None

    @property
    def model_ref(self) -> str:
        return f"{self.provider_id}/{self.model_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "effective_from": self.effective_from.isoformat(),
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class CostProjection:
    """A projected cost, or the reason there isn't one (§9.3).

    `estimated_cost` is `None` far more often than it is a number, and that is
    the correct state: an unknown input cannot produce a known output.
    """

    estimated_cost: Decimal | None = None
    currency: str | None = None
    pricing_status: PricingStatus = PricingStatus.UNKNOWN
    cost_status: CostStatus = CostStatus.NO_PRICING
    pricing_ref: PricingRef | None = None
    reason: str | None = None

    @property
    def is_known(self) -> bool:
        return self.estimated_cost is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_cost": (
                str(self.estimated_cost) if self.estimated_cost is not None else None
            ),
            "currency": self.currency,
            "pricing_status": str(self.pricing_status),
            "cost_status": str(self.cost_status),
            "pricing_ref": self.pricing_ref.to_dict() if self.pricing_ref else None,
            "reason": self.reason,
        }


class PricingCatalog:
    """A versioned set of pricing records, looked up by model and date.

    Immutable after construction, and empty by default -- there is no built-in
    price list and no fallback. Adding a price is an explicit act.
    """

    __slots__ = ("_by_model",)

    def __init__(self, records: Iterable[PricingRecord] = ()) -> None:
        by_model: dict[str, list[PricingRecord]] = {}
        for record in records:
            if not isinstance(record, PricingRecord):
                raise PricingError(
                    f"expected PricingRecord, got {type(record).__name__}"
                )
            by_model.setdefault(record.model_ref, []).append(record)

        frozen: dict[str, tuple[PricingRecord, ...]] = {}
        for model_ref, entries in by_model.items():
            seen: set[date] = set()
            for entry in entries:
                if entry.effective_from in seen:
                    # Ambiguous lookup: two records claiming the same date for
                    # the same model would make cost non-reproducible.
                    raise PricingError(
                        f"{model_ref}: two pricing records share effective_from "
                        f"{entry.effective_from.isoformat()}"
                    )
                seen.add(entry.effective_from)
            frozen[model_ref] = tuple(
                sorted(entries, key=lambda item: item.effective_from)
            )

        self._by_model = frozen

    @property
    def is_empty(self) -> bool:
        return not self._by_model

    @property
    def model_refs(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_model))

    def records_for(self, model_ref: str) -> tuple[PricingRecord, ...]:
        return self._by_model.get(model_ref, ())

    def lookup(self, model_ref: str, *, at: date) -> PricingRecord | None:
        """The applicable record for `model_ref` on `at`, or `None`.

        Selects the most recent record whose `effective_from` is on or before
        `at`. A record dated after `at` describes a price that had not taken
        effect yet and is never used.
        """
        applicable = [
            record
            for record in self._by_model.get(model_ref, ())
            if record.effective_from <= at
        ]
        if not applicable:
            return None
        return max(applicable, key=lambda record: record.effective_from)


def project_cost(
    usage: Usage,
    catalog: PricingCatalog,
    *,
    model_ref: str,
    at: date,
) -> CostProjection:
    """Project a cost for one call, or explain why it cannot be projected.

    Never returns `0` as a stand-in for "unknown": zero is a claim that the
    call was free, which is a different statement from "we cannot say".
    """
    record = catalog.lookup(model_ref, at=at)

    if record is None:
        return CostProjection(
            pricing_status=PricingStatus.UNKNOWN,
            cost_status=CostStatus.NO_PRICING,
            reason=f"no pricing record applies to {model_ref} on {at.isoformat()}",
        )

    reference = PricingRef(
        provider_id=record.provider_id,
        model_id=record.model_id,
        effective_from=record.effective_from,
        source=record.source,
    )

    def unknown(reason: str) -> CostProjection:
        return CostProjection(
            pricing_status=PricingStatus.KNOWN,
            cost_status=CostStatus.USAGE_UNKNOWN,
            pricing_ref=reference,
            reason=reason,
        )

    # §9.3: "Estimated cost is null whenever usage_status: UNKNOWN, because
    # the inputs are unknown." Checked before the per-component sums so an
    # inconsistent Usage cannot slip through.
    if usage.usage_status is UsageStatus.UNKNOWN:
        return unknown("usage_status is UNKNOWN, so the inputs are unknown")

    if not record.is_usable:
        return CostProjection(
            pricing_status=PricingStatus.KNOWN,
            cost_status=CostStatus.NO_PRICING,
            pricing_ref=reference,
            reason=(
                "pricing record prices neither input nor output; an incomplete "
                "rate card cannot project a whole cost"
            ),
        )

    components: tuple[tuple[str, int | None, Decimal | None], ...] = (
        ("input", usage.input_tokens, record.input_per_1m),
        ("output", usage.output_tokens, record.output_per_1m),
        ("cache_read", usage.cache_read_tokens, record.cache_read_per_1m),
        ("cache_write", usage.cache_write_tokens, record.cache_write_per_1m),
    )

    total = Decimal(0)
    for name, count, rate in components:
        if rate is None:
            # Unpriced component: contributes nothing, and is not a claim
            # that it was free -- the record simply does not price it.
            continue
        if count is None:
            return unknown(
                f"{name} is priced but its token count was not reported; a "
                "partial sum would under-report the total"
            )
        total += Decimal(count) * rate / _TOKENS_PER_UNIT

    return CostProjection(
        estimated_cost=total,
        currency=record.currency,
        pricing_status=PricingStatus.KNOWN,
        cost_status=CostStatus.PROJECTED,
        pricing_ref=reference,
    )


def empty_catalog() -> PricingCatalog:
    """The default catalog. Empty on purpose: no price ships with AI-02."""
    return PricingCatalog()


__all__ = [
    "CostProjection",
    "CostStatus",
    "PricingCatalog",
    "PricingError",
    "PricingRecord",
    "PricingRef",
    "PricingStatus",
    "TOKEN_UNIT",
    "empty_catalog",
    "project_cost",
]
