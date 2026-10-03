"""AI-12 §8 — resolving a policy against supplied evidence. Explainable, auditable.

```text
tracked policy
    + the exact supplied BenchmarkRun records it cites
    + their recorded provenance
    = a resolution a reader can re-derive
```

### Nothing here executes

No provider call, no model, no retry, no fallback. `resolve_policy` reads declared
data and supplied data and returns what the policy can currently say. A fallback
declared in the policy is data on the artifact; it is not performed here, and
`resolve_policy` has no path that could perform one.

### Why a resolution is not a selection

Today every selecting rule this contract defines requires `MODEL_EXECUTION` evidence
(§4.2 forbids justifying a selection with a REFERENCE run), and no such measurement
exists (§6). A policy constructed today therefore resolves `DORMANT` — and that is the
honest answer, not a gap to be filled by falling back to REFERENCE evidence or by
treating a missing measurement as neutral (§4.3).

### Evidence accounting

Every supplied record appears in the resolution with a disposition. A record whose
verdict is `BLOCKED` is **preserved and accounted for**, never dropped: it cannot
satisfy a rule that requires `PASS`, and the resolution says so per record rather than
by omission. That is what makes "the BLOCKED task disappeared" a visible defect instead
of a silent one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from benchmarks.vocabulary import OracleVerdict

from routing.evidence import EvidenceClass, EvidenceRef, SuppliedRecord
from routing.policy import Policy, PolicyRule

__all__ = [
    "EvidenceDisposition",
    "EvidenceUse",
    "PolicyOutcome",
    "PolicyResolution",
    "RuleDisposition",
    "RuleResolution",
    "resolve_policy",
    "verify_resolution",
]


class PolicyOutcome(StrEnum):
    """What a resolution concluded. Closed.

    ```text
    SELECTED             a rule was activated and its selection is emitted
    DORMANT              rules exist, and the measurement they require does not
    NO_MATCH             no rule named anything the supplied records cover
    INCOMPLETE_EVIDENCE  a task in the policy's scope has no supplied record
    ```
    """

    SELECTED = "SELECTED"
    DORMANT = "DORMANT"
    NO_MATCH = "NO_MATCH"
    INCOMPLETE_EVIDENCE = "INCOMPLETE_EVIDENCE"


class RuleDisposition(StrEnum):
    """What happened to ONE rule. Closed."""

    ACTIVATED = "ACTIVATED"
    DORMANT = "DORMANT"
    NO_MATCH = "NO_MATCH"


class EvidenceDisposition(StrEnum):
    """What happened to ONE supplied record. Closed.

    The two rejections are kept apart because they say different things:

    ```text
    REJECTED_BY_VERDICT        the record's verdict disqualified it. A BLOCKED,
                               NOT_RUN, UNKNOWN or UNAVAILABLE record lands here:
                               it was read, it was accounted for, and it is never a
                               zero, a default or a neutral value (§4.3).
    REJECTED_BY_EVIDENCE_CLASS the verdict was acceptable and the CLASS was not. A
                               REFERENCE run that PASSed lands here against a rule
                               that requires a model execution — which is §4.2 made
                               visible per record rather than asserted in prose.
    ```
    """

    CITED = "CITED"
    REJECTED_BY_VERDICT = "REJECTED_BY_VERDICT"
    REJECTED_BY_EVIDENCE_CLASS = "REJECTED_BY_EVIDENCE_CLASS"
    NOT_NEEDED = "NOT_NEEDED"
    OUTSIDE_SCOPE = "OUTSIDE_SCOPE"


@dataclass(frozen=True, slots=True)
class EvidenceUse:
    """One supplied record, and what the resolution did with it."""

    ref: EvidenceRef
    digest: str
    disposition: EvidenceDisposition
    rule_id: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "run_id": self.ref.run_id,
            "task_id": self.ref.task_id,
            "verdict": str(self.ref.verdict),
            "reason_code": self.ref.reason_code,
            "evidence_class": str(self.ref.evidence_class),
            "record_digest": self.digest,
            "disposition": str(self.disposition),
            "rule_id": self.rule_id,
        }


@dataclass(frozen=True, slots=True)
class RuleResolution:
    """One rule, what it required, and what it found."""

    rule_id: str
    reason_code: str
    disposition: RuleDisposition
    detail: str
    cited_run_id: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "reason_code": self.reason_code,
            "disposition": str(self.disposition),
            "detail": self.detail,
            "cited_run_id": self.cited_run_id,
        }


@dataclass(frozen=True, slots=True)
class PolicyResolution:
    """§8. Explainable and auditable, or it is not emitted.

    `to_mapping()` carries everything a reader needs: which rules fired, what each
    cited, and every supplied record's disposition with its digest. Nothing here
    lives only inside the component that produced it.
    """

    policy_id: str
    revision: str
    declared_state: str
    outcome: PolicyOutcome
    rules: tuple[RuleResolution, ...]
    evidence: tuple[EvidenceUse, ...]
    missing_scope_tasks: tuple[str, ...] = ()
    selected_model_ref: str | None = None
    selected_agent: str | None = None
    selected_by_rule: str | None = None
    #: The COMPLETE projection of the rule that selected, when one did.
    #:
    #: §8 makes the audit triple "tracked policy + exact supplied records + recorded
    #: provenance", so a rule id is technically enough — a reader can look the rule up.
    #: But this artifact MAKES a selection claim, and a claim whose own basis is not in
    #: it asks a reader to go and find one. Carrying the rule's semantics here means
    #: the artifact can answer "why this model" without leaving the page.
    selected_rule: Mapping[str, Any] | None = None

    @property
    def is_dormant(self) -> bool:
        return self.outcome is PolicyOutcome.DORMANT

    def evidence_for(self, run_id: str) -> EvidenceUse | None:
        for use in self.evidence:
            if use.ref.run_id == run_id:
                return use
        return None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "revision": self.revision,
            "declared_state": self.declared_state,
            "outcome": str(self.outcome),
            "selected_model_ref": self.selected_model_ref,
            "selected_agent": self.selected_agent,
            "selected_by_rule": self.selected_by_rule,
            "selected_rule": dict(self.selected_rule) if self.selected_rule else None,
            "missing_scope_tasks": list(self.missing_scope_tasks),
            "rules": [rule.to_mapping() for rule in self.rules],
            "evidence": [use.to_mapping() for use in self.evidence],
        }


def _candidates(
    rule: PolicyRule, records: Sequence[SuppliedRecord]
) -> tuple[SuppliedRecord, ...]:
    """The supplied records this rule declares it reasons over.

    A rule that names no `match_task_id` reasons over every record in scope; a rule
    that names one reasons over that task's records only. A rule that pins a
    `run_id` reasons over exactly that run — the §5.3 identity, not the task.
    """
    selected = [
        record
        for record in records
        if (rule.match_task_id is None or record.ref.task_id == rule.match_task_id)
        and (rule.requires_run_id is None or record.ref.run_id == rule.requires_run_id)
    ]
    return tuple(sorted(selected, key=lambda record: record.ref.run_id))


def resolve_policy(
    policy: Policy, records: Sequence[SuppliedRecord]
) -> PolicyResolution:
    """Resolve `policy` against `records`. Reads; decides nothing about a model."""
    ordered = tuple(sorted(records, key=lambda record: record.ref.run_id))
    in_scope = tuple(
        record for record in ordered if record.ref.task_id in set(policy.evidence_scope)
    )
    supplied_tasks = {record.ref.task_id for record in in_scope}
    missing = tuple(task for task in policy.evidence_scope if task not in supplied_tasks)

    dispositions: dict[str, tuple[EvidenceDisposition, str | None]] = {
        record.ref.run_id: (EvidenceDisposition.NOT_NEEDED, None) for record in ordered
    }
    for record in ordered:
        if record.ref.task_id not in set(policy.evidence_scope):
            dispositions[record.ref.run_id] = (EvidenceDisposition.OUTSIDE_SCOPE, None)

    rule_resolutions: list[RuleResolution] = []
    selected: tuple[PolicyRule, SuppliedRecord] | None = None

    for rule in policy.rules:
        candidates = _candidates(rule, in_scope)
        if not candidates:
            rule_resolutions.append(
                RuleResolution(
                    rule_id=rule.rule_id,
                    reason_code=rule.reason_code,
                    disposition=RuleDisposition.NO_MATCH,
                    detail="no supplied record matches this rule's declared scope",
                )
            )
            continue

        passing = [
            record
            for record in candidates
            if record.ref.verdict is rule.requires_verdict
            and record.ref.evidence_class is rule.requires_evidence_class
        ]
        for record in candidates:
            if record in passing:
                continue
            # Read, accounted for, and not promotable. A BLOCKED record lands here,
            # which is how it stays visible; a REFERENCE run fails to satisfy a rule
            # that demands a model execution, and the disposition says which of the
            # two disqualifications applied.
            disposition = (
                EvidenceDisposition.REJECTED_BY_VERDICT
                if record.ref.verdict is not rule.requires_verdict
                else EvidenceDisposition.REJECTED_BY_EVIDENCE_CLASS
            )
            dispositions[record.ref.run_id] = (disposition, rule.rule_id)

        if not passing:
            classes = sorted({str(r.ref.evidence_class) for r in candidates})
            verdicts = sorted({str(r.ref.verdict) for r in candidates})
            rule_resolutions.append(
                RuleResolution(
                    rule_id=rule.rule_id,
                    reason_code=rule.reason_code,
                    disposition=RuleDisposition.DORMANT,
                    detail=(
                        f"requires {rule.requires_verdict} evidence of class "
                        f"{rule.requires_evidence_class}; supplied records are "
                        f"{', '.join(verdicts)} of class {', '.join(classes)}"
                    ),
                )
            )
            continue

        cited = passing[0]
        dispositions[cited.ref.run_id] = (EvidenceDisposition.CITED, rule.rule_id)
        rule_resolutions.append(
            RuleResolution(
                rule_id=rule.rule_id,
                reason_code=rule.reason_code,
                disposition=RuleDisposition.ACTIVATED,
                detail="requirement met",
                cited_run_id=cited.ref.run_id,
            )
        )
        if selected is None and rule.selects:
            selected = (rule, cited)

    if missing:
        outcome = PolicyOutcome.INCOMPLETE_EVIDENCE
    elif selected is not None:
        outcome = PolicyOutcome.SELECTED
    elif any(r.disposition is RuleDisposition.DORMANT for r in rule_resolutions):
        outcome = PolicyOutcome.DORMANT
    else:
        outcome = PolicyOutcome.NO_MATCH

    if outcome is not PolicyOutcome.SELECTED:
        selected = None

    return PolicyResolution(
        policy_id=policy.policy_id,
        revision=policy.revision,
        declared_state=str(policy.state),
        outcome=outcome,
        rules=tuple(rule_resolutions),
        evidence=tuple(
            EvidenceUse(
                ref=record.ref,
                digest=record.digest,
                disposition=dispositions[record.ref.run_id][0],
                rule_id=dispositions[record.ref.run_id][1],
            )
            for record in ordered
        ),
        missing_scope_tasks=missing,
        selected_model_ref=selected[0].select_model_ref if selected else None,
        selected_agent=selected[0].select_agent if selected else None,
        selected_by_rule=selected[0].rule_id if selected else None,
        selected_rule=selected[0].to_mapping() if selected else None,
    )


def verify_resolution(
    policy: Policy, records: Sequence[SuppliedRecord], resolution: PolicyResolution
) -> bool:
    """§8 AUDITABLE. Re-derive from the policy and the records, and compare.

    A reader with the tracked policy and the exact supplied records must reach the
    same resolution without asking the component that produced it. This is that
    check, and it is what makes the claim testable rather than decorative.
    """
    return resolve_policy(policy, records) == resolution
