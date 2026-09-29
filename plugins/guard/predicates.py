"""Field resolution and predicate evaluation.

Implements AI-04 contract §6 (context), §7 (capability), §8 (approval), §11.4
(resolution), §11.6 (fail-closed) and §14.2 (aggregation).

Three resolution gates decide whether a field has a comparable value at all, and
they are the reason this module is not a dictionary lookup:

**Context (§6.3).** Only a `FACT` at `CURRENT` freshness in the same workspace
yields a comparable value. Everything else is `UNAVAILABLE` or `INDETERMINATE`
rather than a value some rule might satisfy. This is what makes §6.2 true: a
`PLAN` never authorizes, *even when its content says* `COMPLETE`, `PASS` or
`APPROVED` — AI-03 already reports `COMPLETE` as truth state `UNKNOWN`, and this
gate refuses to compare it as though it were a fact.

**Capability (§7).** Only `VERIFIED` resolves. `DECLARED`, `NOT_VERIFIED` and
`UNAVAILABLE` are `UNAVAILABLE`; `UNKNOWN` is `INDETERMINATE`. A policy cannot
be written to authorize on `DECLARED`, because that field never yields the value
`DECLARED` for a comparison to match.

**Approval (§8.1).** Only `VERIFIED` resolves. `MISSING`, `INVALID` and
`UNKNOWN` are all `UNAVAILABLE` — an approval whose state cannot be established
is no approval, and is treated as no approval.

The distinction between `UNAVAILABLE` and `INDETERMINATE` is not cosmetic:
§18.2 maps the first to `BLOCKED` ("something is missing or unsupported and can
be fixed") and the second to `UNKNOWN` ("an upstream truth model says the fact
is unknown and it must be established").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from plugins.context.context import ContextItem, ContextResponse
from plugins.guard.errors import PredicateUnsupported
from plugins.guard.models import GuardRequest
from plugins.guard.policy import FieldRef, Predicate
from plugins.guard.vocabulary import (
    ApprovalStatus,
    CapabilityStatus,
    CheckResult,
    Freshness,
    ItemKind,
    StatusValue,
    aggregate,
)

#: Truth states that are non-authorizing even on a `FACT` at `CURRENT`
#: freshness (§6.2). `UNKNOWN` is handled separately because §2.3 makes it
#: `INDETERMINATE` rather than `UNAVAILABLE` — a different decision, and a
#: different thing for the caller to go and do.
NON_AUTHORIZING_TRUTH_STATES: frozenset[StatusValue] = frozenset(
    {StatusValue.NOT_RUN, StatusValue.BLOCKED}
)


@dataclass(frozen=True, slots=True)
class Resolution:
    """What a field reference resolved to, or why it did not."""

    result: CheckResult
    value: Any = None
    detail: str = ""

    @property
    def resolved(self) -> bool:
        return self.result is CheckResult.SATISFIED


def _unavailable(detail: str) -> Resolution:
    return Resolution(result=CheckResult.UNAVAILABLE, detail=detail)


def _indeterminate(detail: str) -> Resolution:
    return Resolution(result=CheckResult.INDETERMINATE, detail=detail)


def _value(value: Any, detail: str = "") -> Resolution:
    return Resolution(result=CheckResult.SATISFIED, value=value, detail=detail)


def resolve_context_item(
    request: GuardRequest, subject: str
) -> tuple[ContextItem | None, Resolution | None]:
    """The authorizing item for `subject`, or the reason there is none (§6.3).

    Returns `(item, None)` when the item is an authorizing `FACT` at `CURRENT`
    freshness, and `(None, resolution)` otherwise.
    """
    response: ContextResponse | None = request.context
    if response is None:
        return None, _unavailable("no context response in the request")

    if response.workspace.workspace_id != request.workspace.workspace_id:
        # §5: a mismatch is never merged or filtered. The workspace gate in the
        # evaluator turns this into DENY; here it must not yield a value.
        return None, _unavailable(
            "context belongs to a different workspace than the request"
        )

    matches = [
        item
        for item in (*response.facts, *response.history, *response.plans)
        if item.subject == subject
    ]
    if not matches:
        return None, _unavailable(f"subject {subject!r} is absent from the context")

    fact = next((item for item in matches if item.item_kind is ItemKind.FACT), None)
    if fact is None:
        kinds = sorted({str(item.item_kind) for item in matches})
        return None, _unavailable(
            f"subject {subject!r} is present as {kinds} but not as a FACT"
        )

    if fact.workspace_id != request.workspace.workspace_id:
        return None, _unavailable(
            f"item {subject!r} carries a different workspace"
        )

    if fact.freshness is Freshness.STALE:
        # §10.2: STALE is not WRONG -- it says only that nothing currently shows
        # this to still be the newest state. The caller should re-read.
        return None, _unavailable(f"item {subject!r} is STALE")
    if fact.freshness is Freshness.UNKNOWN:
        return None, _indeterminate(f"item {subject!r} has unknown freshness")

    return fact, None


def resolve_field(request: GuardRequest, field: FieldRef) -> Resolution:
    """Resolve one field reference, applying the §6/§7/§8 gates.

    Never raises for an unsupported value: an unlisted vocabulary member is
    `UNAVAILABLE` (§11.6), because a policy defect must not present as a clean
    "this rule does not apply".
    """
    try:
        return _resolve_field(request, field)
    except PredicateUnsupported as exc:
        return _unavailable(f"{field.text}: {exc}")


def _resolve_field(request: GuardRequest, field: FieldRef) -> Resolution:
    text = field.text

    if field.is_context:
        item, failure = resolve_context_item(request, field.subject or "")
        if failure is not None:
            return failure
        assert item is not None  # narrowed by resolve_context_item

        if field.facet == "item_kind":
            return _value(str(item.item_kind))
        if field.facet == "freshness":
            return _value(str(item.freshness))
        # truth_state
        if item.truth_state is StatusValue.UNKNOWN:
            return _indeterminate(
                f"item {field.subject!r} carries truth state UNKNOWN"
            )
        if item.truth_state in NON_AUTHORIZING_TRUTH_STATES:
            return _unavailable(
                f"item {field.subject!r} carries non-authorizing truth state "
                f"{item.truth_state}"
            )
        return _value(str(item.truth_state))

    if text == "workspace.id":
        return _value(request.workspace.workspace_id)
    if text == "workspace.branch":
        return _resolve_optional(request.workspace.branch, "workspace.branch")
    if text == "workspace.working_tree":
        return _value(str(request.workspace.working_tree))
    if text == "action.id":
        return _value(request.action.id)
    if text == "action.permission_level":
        return _value(str(request.action.permission_level))

    if text == "capability.id":
        return _resolve_optional(request.capability.id, "capability.id")
    if text == "capability.status":
        record = request.record_for(request.capability.id)
        if record is None:
            # §11.2: a policy constraining a capability the request does not
            # name has not been satisfied, and has not been refuted either.
            return _unavailable(
                "no capability record matches request.capability.id"
            )
        if record.status is CapabilityStatus.VERIFIED:
            return _value(str(record.status))
        if record.status is CapabilityStatus.UNKNOWN:
            return _indeterminate("capability status is UNKNOWN")
        return _unavailable(f"capability status {record.status} is not VERIFIED")

    if text == "target.kind":
        return _value(str(request.target.kind))
    if text == "target.sensitivity":
        return _resolve_optional(request.target.sensitivity, "target.sensitivity")
    if text == "target.interface":
        return _resolve_optional(request.target.interface, "target.interface")
    if text == "target.is_real":
        return _resolve_optional(request.target.is_real, "target.is_real")

    if text == "approval.status":
        status = request.approval.status
        if status is ApprovalStatus.VERIFIED:
            return _value(str(status))
        # §8.1: MISSING, INVALID and UNKNOWN are all no-approval, and all
        # fail closed. UNKNOWN is BLOCKED rather than UNKNOWN because approval
        # is a precondition this contract owns, not a truth model it inherits.
        return _unavailable(f"approval status {status} is not VERIFIED")
    if text == "approval.reference":
        return _resolve_optional(request.approval.reference, "approval.reference")

    raise PredicateUnsupported(f"field {text!r} is not in the closed set (§11.2)")


def _resolve_optional(value: Any, name: str) -> Resolution:
    if value is None:
        return _unavailable(f"{name} is not present in the request")
    return _value(value)


def evaluate_predicate(request: GuardRequest, predicate: Predicate) -> CheckResult:
    """Evaluate one predicate to a `CheckResult` (§11.1, §11.6)."""
    resolution = resolve_field(request, predicate.field)
    if not resolution.resolved:
        return resolution.result

    actual = resolution.value
    if predicate.op == "exists":
        return CheckResult.SATISFIED
    if predicate.op == "eq":
        return (
            CheckResult.SATISFIED
            if actual == predicate.value
            else CheckResult.REJECTED
        )
    # in
    return (
        CheckResult.SATISFIED
        if actual in predicate.values
        else CheckResult.REJECTED
    )


def evaluate_predicates(
    request: GuardRequest, predicates: Iterable[Predicate]
) -> CheckResult:
    """Aggregate a `match` or `conditions[]` by §14.2.

    Order-independent: `aggregate` reduces by `max` over a total rank, so any
    permutation of the same predicates yields the same result. That is what lets
    §20.3 serialise those collections in sorted order without the *result*
    depending on that order.
    """
    return aggregate(
        evaluate_predicate(request, predicate) for predicate in predicates
    )


def explain_predicates(
    request: GuardRequest, predicates: Iterable[Predicate]
) -> tuple[CheckResult, tuple[str, ...]]:
    """The aggregate plus the reason each non-satisfied predicate gave.

    The aggregate alone tells a caller *that* a rule could not be evaluated; the
    details tell them *what to go and fix* — "item is STALE" (re-read it) reads
    very differently from "item is absent" (produce it). §19 exists so a
    decision can answer "why", and a bare aggregate cannot.
    """
    results: list[CheckResult] = []
    details: list[str] = []
    for predicate in predicates:
        resolution = resolve_field(request, predicate.field)
        if resolution.resolved:
            result = evaluate_predicate(request, predicate)
        else:
            result = resolution.result
            details.append(f"{predicate.check_id()}: {resolution.detail}")
        results.append(result)
    return aggregate(results), tuple(details)


__all__ = [
    "NON_AUTHORIZING_TRUTH_STATES",
    "Resolution",
    "evaluate_predicate",
    "evaluate_predicates",
    "explain_predicates",
    "resolve_context_item",
    "resolve_field",
]
