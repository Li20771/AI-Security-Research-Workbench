"""Metrics observation and aggregation.

Implements AI-02 contract §9 (§9.1 required metrics, §9.2 zero-vs-unknown,
§9.4 attribution).

The relationship is one-way:

    InvocationResult  ->  MetricObservation  ->  aggregate

Metrics observe facts. They never feed back into a call: nothing here selects
a model, ranks one against another, decides a fallback, or moves a capability
toward `VERIFIED`. **Collecting a metric does not implement a policy on it**
(§9) -- routing on these numbers is AI-07/AI-12.

Three rules shape the module:

**`BLOCKED` is not a failure.** A refused call still counts as a request, but
it lands in `blocked_count`, never in `failure_count` (§9.1). An unconfigured
environment must not look like a failing provider.

**Unknown is not zero.** A count nobody reported stays `None` and increments
`usage_unknown_count`; it is never folded into a total as `0`.

**Unattributable calls are not collected.** An observation must name a real
provider and model. There is no `unknown-provider` bucket, because a bucket
like that would hide exactly the attribution gap it papers over (§9.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from providers.errors import PRECONDITION_CLASSES, ErrorClass
from providers.invocation import (
    BlockCode,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    Latency,
    Usage,
    UsageStatus,
)
from providers.pricing import (
    CostProjection,
    CostStatus,
    PricingCatalog,
    PricingRef,
    PricingStatus,
    empty_catalog,
    project_cost,
)
from providers.profile import PROVIDER_ID_RE
from providers.protocol import FinishState

#: Key used for the whole-corpus aggregate in `MetricsSnapshot`.
OVERALL_KEY = "*"


class MetricsError(ValueError):
    """A metric observation is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class MetricObservation:
    """One recorded fact about one invocation (§9.4).

    Carries the full attribution a metric sample requires: `provider_id`,
    `model_id`, `model_ref`, `status`, `error_class`, and the request metadata
    from §7.4.

    Built from an `InvocationResult`, which does not itself carry the request
    metadata — so `from_invocation` takes the request as well. That keeps the
    B3 result contract untouched and puts attribution where it belongs: on the
    metric sample, which is what §9.4 actually requires.
    """

    provider_id: str
    model_id: str
    model_ref: str
    status: InvocationStatus
    attempts: int = 1
    error_class: ErrorClass | None = None
    block_code: BlockCode | None = None
    finish_state: FinishState = FinishState.UNKNOWN
    latency: Latency = field(default_factory=Latency)
    usage: Usage = field(
        default_factory=lambda: Usage(usage_status=UsageStatus.UNKNOWN)
    )
    request_id: str | None = None
    experiment_id: str | None = None
    task_id: str | None = None
    task_class: str | None = None
    agent: str | None = None
    purpose: str | None = None

    def __post_init__(self) -> None:
        # Attribution is mandatory: an observation that cannot name a real
        # provider and model is not collected (§9.4), and the way to enforce
        # that is to make it unconstructable.
        if not PROVIDER_ID_RE.match(self.provider_id or ""):
            raise MetricsError(
                f"provider_id {self.provider_id!r} is not a valid provider id; "
                "unattributable observations are not collected"
            )
        if not self.model_id or not self.model_id.strip():
            raise MetricsError("model_id must not be empty")
        expected_ref = f"{self.provider_id}/{self.model_id}"
        if self.model_ref != expected_ref:
            raise MetricsError(
                f"model_ref {self.model_ref!r} must equal {expected_ref!r}"
            )
        if not isinstance(self.status, InvocationStatus):
            raise MetricsError(
                f"status must be an InvocationStatus; got {self.status!r}"
            )
        if self.error_class is not None and not isinstance(self.error_class, ErrorClass):
            raise MetricsError(
                f"error_class must be an ErrorClass or null; got {self.error_class!r}"
            )
        if isinstance(self.attempts, bool) or not isinstance(self.attempts, int):
            raise MetricsError("attempts must be an integer")
        if self.attempts < 1:
            raise MetricsError(f"attempts must be >= 1; got {self.attempts}")

        self._check_status_consistency()
        for name in ("request_id", "experiment_id", "task_id", "task_class", "agent", "purpose"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise MetricsError(f"{name} must be a string or null")

    def _check_status_consistency(self) -> None:
        """Keep `status` and `error_class` from describing different calls."""
        if self.status is InvocationStatus.SUCCESS:
            if self.error_class is not None:
                raise MetricsError(
                    f"a SUCCESS observation must not carry error_class "
                    f"{self.error_class}; status is the only success signal"
                )
            return

        if self.status is InvocationStatus.ERROR:
            if self.error_class is None:
                raise MetricsError(
                    "an ERROR observation must carry its error_class; a failure "
                    "without a class cannot be attributed to a cause"
                )
            return

        # BLOCKED. An invocation-layer refusal has no provider taxonomy class;
        # a credential precondition does, because those are frozen classes.
        if self.error_class is not None and self.error_class not in PRECONDITION_CLASSES:
            raise MetricsError(
                f"a BLOCKED observation may only carry a precondition class; "
                f"got {self.error_class}. An invocation-layer refusal has no "
                "provider ErrorClass"
            )

    @classmethod
    def from_invocation(
        cls, request: InvocationRequest, result: InvocationResult
    ) -> "MetricObservation":
        """Build an observation from a completed invocation.

        The request supplies §7.4 metadata; the result supplies the facts.
        Combining them here is what keeps attribution available without
        widening the B3 result contract.
        """
        metadata = request.metadata
        return cls(
            provider_id=result.provider_id,
            model_id=result.model_id,
            model_ref=result.model_ref,
            status=result.status,
            attempts=result.attempts,
            error_class=result.error.error_class if result.error else None,
            block_code=result.blocked.code if result.blocked else None,
            finish_state=result.finish_state,
            latency=result.latency,
            usage=result.usage
            or Usage(usage_status=UsageStatus.UNKNOWN),
            request_id=result.request_id,
            experiment_id=metadata.experiment_id,
            task_id=metadata.task_id,
            task_class=metadata.task_class,
            agent=metadata.agent,
            purpose=metadata.purpose,
        )

    @property
    def is_usage_unknown(self) -> bool:
        return self.usage.usage_status is UsageStatus.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "model_ref": self.model_ref,
            "status": str(self.status),
            "attempts": self.attempts,
            "error_class": str(self.error_class) if self.error_class else None,
            "block_code": str(self.block_code) if self.block_code else None,
            "finish_state": str(self.finish_state),
            "latency": self.latency.to_dict(),
            "usage": self.usage.to_dict(),
            "request_id": self.request_id,
            "experiment_id": self.experiment_id,
            "task_id": self.task_id,
            "task_class": self.task_class,
            "agent": self.agent,
            "purpose": self.purpose,
        }


@dataclass(frozen=True, slots=True)
class LatencyStats:
    """Latency aggregates **and** the raw samples they came from (§9.1).

    Aggregates never replace samples: a mean alone cannot be re-analysed, and
    the contract is explicit that both are kept.

    Percentiles are deliberately absent: §9 does not ask for them, and adding
    them now would be building a benchmark engine this phase does not own.
    """

    samples: tuple[int, ...] = ()

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def has_samples(self) -> bool:
        return bool(self.samples)

    @property
    def min_ms(self) -> int | None:
        return min(self.samples) if self.samples else None

    @property
    def max_ms(self) -> int | None:
        return max(self.samples) if self.samples else None

    @property
    def total_ms(self) -> int | None:
        return sum(self.samples) if self.samples else None

    @property
    def average_ms(self) -> float | None:
        if not self.samples:
            return None
        return sum(self.samples) / len(self.samples)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "total_ms": self.total_ms,
            "average_ms": self.average_ms,
            # Raw samples are preserved, not summarised away.
            "samples": list(self.samples),
        }


@dataclass(frozen=True, slots=True)
class TokenTotals:
    """Token totals with explicit unknown accounting (§9.2).

    Each total sums only the counts that were actually reported. A field with
    nothing reported stays `None` rather than becoming `0`.

    `usage_unknown_count` travels with the totals, so a partially-unknown
    aggregate cannot be read as a complete one. `is_complete` is that label.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    observation_count: int = 0
    reported_count: int = 0
    usage_unknown_count: int = 0

    @property
    def is_complete(self) -> bool:
        """True only when every observation reported its usage.

        A `False` here means the totals are partial and must not be quoted as
        the whole corpus.
        """
        return self.usage_unknown_count == 0

    @property
    def is_partially_unknown(self) -> bool:
        return not self.is_complete

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "observation_count": self.observation_count,
            "reported_count": self.reported_count,
            "usage_unknown_count": self.usage_unknown_count,
            "is_complete": self.is_complete,
        }


def _sum_known(values: Iterable[int | None]) -> int | None:
    """Sum the reported values, or `None` when nothing was reported.

    Never returns `0` for "nothing reported": that would be a measurement the
    provider never made.
    """
    known = [value for value in values if value is not None]
    return sum(known) if known else None


@dataclass(frozen=True, slots=True)
class MetricAggregate:
    """Counters and totals over a set of observations (§9.1)."""

    key: str
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    blocked_count: int = 0
    timeout_count: int = 0
    attempts_total: int = 0
    attempts_max: int = 0
    error_class_counts: Mapping[ErrorClass, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    block_code_counts: Mapping[BlockCode, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    latency: LatencyStats = field(default_factory=LatencyStats)
    tokens: TokenTotals = field(default_factory=TokenTotals)
    cost: CostProjection = field(default_factory=CostProjection)
    costed_count: int = 0
    uncosted_count: int = 0
    pricing_refs: tuple[PricingRef, ...] = ()

    @property
    def is_empty(self) -> bool:
        return self.request_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "blocked_count": self.blocked_count,
            "timeout_count": self.timeout_count,
            "attempts_total": self.attempts_total,
            "attempts_max": self.attempts_max,
            "error_class_counts": {
                str(name): count for name, count in self.error_class_counts.items()
            },
            "block_code_counts": {
                str(name): count for name, count in self.block_code_counts.items()
            },
            "latency": self.latency.to_dict(),
            "tokens": self.tokens.to_dict(),
            "cost": self.cost.to_dict(),
            "costed_count": self.costed_count,
            "uncosted_count": self.uncosted_count,
            "pricing_refs": [ref.to_dict() for ref in self.pricing_refs],
        }


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """A read-only view of everything recorded so far (§9.4)."""

    overall: MetricAggregate
    by_provider: Mapping[str, MetricAggregate] = field(
        default_factory=lambda: MappingProxyType({})
    )
    by_model: Mapping[str, MetricAggregate] = field(
        default_factory=lambda: MappingProxyType({})
    )
    by_experiment: Mapping[str, MetricAggregate] = field(
        default_factory=lambda: MappingProxyType({})
    )
    by_task_class: Mapping[str, MetricAggregate] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall.to_dict(),
            "by_provider": {k: v.to_dict() for k, v in self.by_provider.items()},
            "by_model": {k: v.to_dict() for k, v in self.by_model.items()},
            "by_experiment": {k: v.to_dict() for k, v in self.by_experiment.items()},
            "by_task_class": {k: v.to_dict() for k, v in self.by_task_class.items()},
        }


class MetricAggregator:
    """Collects observations and produces aggregates.

    `as_of` is required: cost is derived from a *dated* pricing record
    (§9.3), so an aggregator that silently used the wall clock would produce
    non-reproducible figures. The caller chooses which date's prices apply.

    The catalog defaults to empty, so no cost is projected until a price is
    supplied explicitly.
    """

    def __init__(
        self,
        *,
        as_of: date,
        catalog: PricingCatalog | None = None,
        observations: Iterable[MetricObservation] = (),
    ) -> None:
        self._as_of = as_of
        self._catalog = empty_catalog() if catalog is None else catalog
        self._observations: list[MetricObservation] = []
        for observation in observations:
            self.record(observation)

    @property
    def as_of(self) -> date:
        return self._as_of

    @property
    def catalog(self) -> PricingCatalog:
        return self._catalog

    @property
    def observation_count(self) -> int:
        return len(self._observations)

    def record(self, observation: MetricObservation) -> MetricObservation:
        """Record one observation. Returns it unchanged.

        Observing does not modify the observed value: `MetricObservation` and
        `InvocationResult` are both frozen, and the reference is retained, not
        copied into something mutable.
        """
        if not isinstance(observation, MetricObservation):
            raise MetricsError(
                f"expected MetricObservation, got {type(observation).__name__}"
            )
        self._observations.append(observation)
        return observation

    def record_invocation(
        self, request: InvocationRequest, result: InvocationResult
    ) -> MetricObservation:
        """Observe a completed invocation in one step."""
        return self.record(MetricObservation.from_invocation(request, result))

    def snapshot(self) -> MetricsSnapshot:
        """Aggregate everything recorded so far."""
        return MetricsSnapshot(
            overall=self._aggregate(OVERALL_KEY, self._observations),
            by_provider=self._group_by(lambda o: o.provider_id),
            by_model=self._group_by(lambda o: o.model_ref),
            by_experiment=self._group_by(
                lambda o: o.experiment_id, drop_none=True
            ),
            by_task_class=self._group_by(lambda o: o.task_class, drop_none=True),
        )

    # -- aggregation ------------------------------------------------------

    def _group_by(
        self, key_of: Any, *, drop_none: bool = False
    ) -> Mapping[str, MetricAggregate]:
        groups: dict[str, list[MetricObservation]] = {}
        for observation in self._observations:
            key = key_of(observation)
            if key is None:
                # An unattributed call is not forced into an `unknown` bucket:
                # it stays in the provider/model aggregates and is simply
                # absent from this breakdown.
                if drop_none:
                    continue
                key = OVERALL_KEY
            groups.setdefault(key, []).append(observation)
        return MappingProxyType(
            {
                key: self._aggregate(key, entries)
                for key, entries in sorted(groups.items())
            }
        )

    def _aggregate(
        self, key: str, observations: list[MetricObservation]
    ) -> MetricAggregate:
        error_counts: dict[ErrorClass, int] = {}
        block_counts: dict[BlockCode, int] = {}
        latencies: list[int] = []
        usages: list[Usage] = []
        costs: list[CostProjection] = []

        success = failure = blocked = timeout = 0
        attempts_total = 0
        attempts_max = 0

        for observation in observations:
            # BLOCKED is counted as its own outcome, never as a failure.
            if observation.status is InvocationStatus.SUCCESS:
                success += 1
            elif observation.status is InvocationStatus.ERROR:
                failure += 1
            else:
                blocked += 1

            if observation.error_class is not None:
                error_counts[observation.error_class] = (
                    error_counts.get(observation.error_class, 0) + 1
                )
                if observation.error_class is ErrorClass.TIMEOUT:
                    timeout += 1

            if observation.block_code is not None:
                block_counts[observation.block_code] = (
                    block_counts.get(observation.block_code, 0) + 1
                )

            attempts_total += observation.attempts
            attempts_max = max(attempts_max, observation.attempts)

            # Only a measured latency is sampled. A refused call never reached
            # a provider, so it has no call latency and contributes nothing --
            # recording 0 would invent a measurement.
            if observation.latency.total_ms is not None:
                latencies.append(observation.latency.total_ms)

            usages.append(observation.usage)
            costs.append(
                project_cost(
                    observation.usage,
                    self._catalog,
                    model_ref=observation.model_ref,
                    at=self._as_of,
                )
            )

        return MetricAggregate(
            key=key,
            request_count=len(observations),
            success_count=success,
            failure_count=failure,
            blocked_count=blocked,
            timeout_count=timeout,
            attempts_total=attempts_total,
            attempts_max=attempts_max,
            error_class_counts=MappingProxyType(dict(sorted(error_counts.items(), key=lambda i: str(i[0])))),
            block_code_counts=MappingProxyType(dict(sorted(block_counts.items(), key=lambda i: str(i[0])))),
            latency=LatencyStats(samples=tuple(latencies)),
            tokens=_totals(usages),
            cost=_aggregate_cost(costs),
            costed_count=sum(1 for c in costs if c.estimated_cost is not None),
            uncosted_count=sum(1 for c in costs if c.estimated_cost is None),
            pricing_refs=tuple(
                sorted(
                    {ref for c in costs if (ref := c.pricing_ref) is not None},
                    key=lambda r: (r.model_ref, r.effective_from),
                )
            ),
        )


def _totals(usages: list[Usage]) -> TokenTotals:
    unknown = sum(1 for usage in usages if usage.usage_status is UsageStatus.UNKNOWN)
    return TokenTotals(
        input_tokens=_sum_known(usage.input_tokens for usage in usages),
        output_tokens=_sum_known(usage.output_tokens for usage in usages),
        total_tokens=_sum_known(usage.total_tokens for usage in usages),
        cache_read_tokens=_sum_known(usage.cache_read_tokens for usage in usages),
        cache_write_tokens=_sum_known(usage.cache_write_tokens for usage in usages),
        observation_count=len(usages),
        reported_count=len(usages) - unknown,
        usage_unknown_count=unknown,
    )


def _aggregate_cost(costs: list[CostProjection]) -> CostProjection:
    """Total the projections, or explain why the total is unknown.

    A single uncosted call makes the whole total unknown: quoting a partial
    sum as the corpus cost would under-report it, and an under-reported cost
    is a false figure rather than a conservative one (§9.3).
    """
    if not costs:
        return CostProjection(
            pricing_status=PricingStatus.UNKNOWN,
            cost_status=CostStatus.NO_PRICING,
            reason="no observations",
        )

    priced = [cost for cost in costs if cost.estimated_cost is not None]
    refs = tuple({c.pricing_ref for c in priced if c.pricing_ref is not None})
    uncosted = len(costs) - len(priced)

    if not priced:
        # Nothing could be costed. Report the common cause when there is one,
        # so the reason points at the real problem: a missing price list and
        # an unreported token count need different fixes.
        causes = {cost.cost_status for cost in costs}
        cost_status = (
            next(iter(causes)) if len(causes) == 1 else CostStatus.USAGE_UNKNOWN
        )
        all_refs = tuple(
            {c.pricing_ref for c in costs if c.pricing_ref is not None}
        )
        return CostProjection(
            pricing_status=costs[0].pricing_status,
            cost_status=cost_status,
            pricing_ref=all_refs[0] if all_refs else None,
            reason=f"no observation could be costed ({len(costs)} uncosted)",
        )

    currencies = {cost.currency for cost in priced}
    if len(currencies) > 1:
        return CostProjection(
            pricing_status=PricingStatus.KNOWN,
            cost_status=CostStatus.USAGE_UNKNOWN,
            pricing_ref=priced[0].pricing_ref,
            reason=(
                "observations span multiple currencies "
                f"({', '.join(sorted(str(c) for c in currencies))}); totalling "
                "them would be meaningless"
            ),
        )

    if uncosted:
        return CostProjection(
            pricing_status=PricingStatus.KNOWN,
            cost_status=CostStatus.USAGE_UNKNOWN,
            currency=priced[0].currency,
            pricing_ref=priced[0].pricing_ref,
            reason=(
                f"{uncosted} of {len(costs)} observations could not be costed; "
                "a partial sum would under-report the total"
            ),
        )

    return CostProjection(
        estimated_cost=sum((c.estimated_cost for c in priced), Decimal(0)),
        currency=priced[0].currency,
        pricing_status=PricingStatus.KNOWN,
        cost_status=CostStatus.PROJECTED,
        pricing_ref=priced[0].pricing_ref,
    )


__all__ = [
    "LatencyStats",
    "MetricAggregate",
    "MetricAggregator",
    "MetricObservation",
    "MetricsError",
    "MetricsSnapshot",
    "OVERALL_KEY",
    "TokenTotals",
]
