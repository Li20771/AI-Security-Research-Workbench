"""AI-12 §5, §7, §8 — the policy artifact. Declared data, not a runtime.

```text
AI-11 measured facts  ->  AI-12 declared policy  ->  a validated policy artifact
```

### What a policy is here

A **reviewed, tracked artifact** in the same sense AI-02's provider profiles, AI-04's
policies and AI-07's rule sets are: not generated, not fetched, and found only
where a reviewer put them. It declares which AI-11 tasks it reasons over, what each rule selects, what
evidence each rule must read, what would prove each rule wrong, and how it would be
rolled back.

### What a policy is not

```text
FROZEN: AI-12 describes policy; it does not become a runtime.
```

No fallback is executed, no model is retried, no second decision is created, no
previous-decision state is kept, and no caller's request is mutated. AI-07 evaluates
a caller-submitted request; AI-12 declares what should be asked for. Nothing in this
module starts a process, opens a socket or reads a file.

### What is refused here

```text
a selecting rule justified by REFERENCE evidence        §4.2
a rule with no falsifier                                §7
a rule with no discrimination control                   §7
an ACTIVATABLE policy with no rollback metadata         §8
a score / weight / confidence / ranking field           §4.3, §9
a duplicate rule_id, or an unsupported version          §5
```

None of those is a tuning question. Each is a shape the contract does not define,
and the refusal names it rather than accepting it and behaving differently later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence

from providers.profile import ModelRef, ProfileError

from benchmarks.vocabulary import OracleVerdict

from routing.errors import InvalidPolicy
from routing.evidence import EvidenceClass, EvidenceRef

__all__ = [
    "POLICY_VERSION",
    "DiscriminationControl",
    "EscalationDeclaration",
    "FallbackDeclaration",
    "Falsifier",
    "Policy",
    "PolicyRule",
    "PolicyState",
    "Rollback",
]

POLICY_VERSION = 1

#: §4.3, §9. Fields a policy MUST NOT carry. Refused by name so the message says
#: which forbidden idea arrived, rather than "unknown field".
FORBIDDEN_POLICY_FIELDS = frozenset(
    {
        "score",
        "weight",
        "weights",
        "confidence",
        "ranking",
        "rank",
        "aggregate",
        "prior",
        "prior_score",
        "effective_score",
        "model_score",
        "success_rate",
    }
)

_POLICY_KEYS = frozenset(
    {
        "version",
        "policy_id",
        "revision",
        "state",
        "evidence_scope",
        "rules",
        "rollback",
        "fallback",
        "escalation",
    }
)

_RULE_KEYS = frozenset(
    {
        "rule_id",
        "priority",
        "reason_code",
        "match_task_id",
        "requires_verdict",
        "requires_evidence_class",
        "requires_run_id",
        "select",
        "falsifier",
        "discrimination",
    }
)

_SELECT_KEYS = frozenset({"model_ref", "agent"})
_FALSIFIER_KEYS = frozenset({"observation", "expected_if_rule_wrong"})
_DISCRIMINATION_KEYS = frozenset({"input_a", "input_b", "expected_distinction"})
_ROLLBACK_KEYS = frozenset({"previous_policy", "trigger", "decider"})
_FALLBACK_KEYS = frozenset({"condition", "target_model_ref", "reason_code"})
_ESCALATION_KEYS = frozenset({"condition", "target_model_ref", "reason_code"})


class PolicyState(StrEnum):
    """What the artifact declares about itself. Closed.

    ```text
    DORMANT   the policy is declared and validated, and it is not to be used for a
              model selection. A policy whose rules require a measurement that does
              not exist is DORMANT, and §6.1 keeps it that way.
    ACTIVE    the policy declares itself usable, which §8 makes conditional on
              complete rollback metadata.
    ```

    The declaration is checked, and it is not authoritative: an ACTIVE policy whose
    rules cannot be satisfied by the supplied records still resolves DORMANT. A
    declaration cannot manufacture a measurement.
    """

    DORMANT = "DORMANT"
    ACTIVE = "ACTIVE"


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidPolicy(f"{where} must be an object")
    return value


def _refuse_forbidden(raw: Mapping[str, Any], where: str) -> None:
    """§4.3. Refuse a score/weight-shaped field BY NAME, wherever it appears."""
    offending = sorted(set(raw) & FORBIDDEN_POLICY_FIELDS)
    if offending:
        raise InvalidPolicy(
            f"{where} carries {', '.join(offending)}; an AI-11 verdict is a fact "
            "consumed by policy and not a numeric quantity, and AI-12 derives no "
            "weight, score, prior, ranking or aggregate from one (§4.3, §9)"
        )


def _closed(raw: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    _refuse_forbidden(raw, where)
    unknown = set(raw) - allowed
    if unknown:
        raise InvalidPolicy(
            f"{where} has field(s) the contract does not define: "
            f"{', '.join(sorted(map(str, unknown)))}"
        )


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidPolicy(f"{where} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class Falsifier:
    """§7. The observation that would show this rule is wrong.

    Not a field that must be present — a claim that must be checkable. Both halves
    are required and both must say something, because `expected_if_rule_wrong: ""`
    is a rule that cannot be contradicted while appearing to have a falsifier.
    """

    observation: str
    expected_if_rule_wrong: str

    @classmethod
    def from_mapping(cls, raw: object, where: str) -> "Falsifier":
        data = _mapping(raw, where)
        _closed(data, _FALSIFIER_KEYS, where)
        return cls(
            observation=_text(data.get("observation"), f"{where}.observation"),
            expected_if_rule_wrong=_text(
                data.get("expected_if_rule_wrong"), f"{where}.expected_if_rule_wrong"
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "observation": self.observation,
            "expected_if_rule_wrong": self.expected_if_rule_wrong,
        }


@dataclass(frozen=True, slots=True)
class DiscriminationControl:
    """§7. Two declared inputs the policy is REQUIRED to route differently.

    Without one, a policy that always answers the same thing passes every check
    written against it. The two inputs must differ: a control whose halves are the
    same string is not a pair.
    """

    input_a: str
    input_b: str
    expected_distinction: str

    @classmethod
    def from_mapping(cls, raw: object, where: str) -> "DiscriminationControl":
        data = _mapping(raw, where)
        _closed(data, _DISCRIMINATION_KEYS, where)
        control = cls(
            input_a=_text(data.get("input_a"), f"{where}.input_a"),
            input_b=_text(data.get("input_b"), f"{where}.input_b"),
            expected_distinction=_text(
                data.get("expected_distinction"), f"{where}.expected_distinction"
            ),
        )
        if control.input_a == control.input_b:
            raise InvalidPolicy(
                f"{where}.input_a and {where}.input_b are the same value; a "
                "discrimination control is a PAIR of declared inputs, and one input "
                "compared with itself cannot show that anything is distinguished"
            )
        return control

    def to_mapping(self) -> dict[str, Any]:
        return {
            "input_a": self.input_a,
            "input_b": self.input_b,
            "expected_distinction": self.expected_distinction,
        }


@dataclass(frozen=True, slots=True)
class Rollback:
    """§8. How this policy stops being used. Required before it may be ACTIVE.

    ```text
    FROZEN: REVERSIBLE does not mean AI-12 reverses anything itself.
    ```

    AI-12 declares the rollback; the actor named in `decider` performs it.
    """

    previous_policy: str
    trigger: str
    decider: str

    @classmethod
    def from_mapping(cls, raw: object, where: str) -> "Rollback":
        data = _mapping(raw, where)
        _closed(data, _ROLLBACK_KEYS, where)
        return cls(
            previous_policy=_text(data.get("previous_policy"), f"{where}.previous_policy"),
            trigger=_text(data.get("trigger"), f"{where}.trigger"),
            decider=_text(data.get("decider"), f"{where}.decider"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "previous_policy": self.previous_policy,
            "trigger": self.trigger,
            "decider": self.decider,
        }


@dataclass(frozen=True, slots=True)
class FallbackDeclaration:
    """§5.2. Declarative data. AI-12 does not execute this.

    When it is realised, a caller submits a NEW `RouterRequest` and AI-07 evaluates
    it independently — the previous decision grants no authorization, and AI-12
    neither widens the candidate set nor relaxes a request constraint.
    """

    condition: str
    target_model_ref: str
    reason_code: str

    @classmethod
    def from_mapping(cls, raw: object, where: str) -> "FallbackDeclaration":
        data = _mapping(raw, where)
        _closed(data, _FALLBACK_KEYS, where)
        return cls(
            condition=_text(data.get("condition"), f"{where}.condition"),
            target_model_ref=_model_ref(data.get("target_model_ref"), where),
            reason_code=_text(data.get("reason_code"), f"{where}.reason_code"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "target_model_ref": self.target_model_ref,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class EscalationDeclaration:
    """§5.2. Declarative data, exactly as `FallbackDeclaration` is."""

    condition: str
    target_model_ref: str
    reason_code: str

    @classmethod
    def from_mapping(cls, raw: object, where: str) -> "EscalationDeclaration":
        data = _mapping(raw, where)
        _closed(data, _ESCALATION_KEYS, where)
        return cls(
            condition=_text(data.get("condition"), f"{where}.condition"),
            target_model_ref=_model_ref(data.get("target_model_ref"), where),
            reason_code=_text(data.get("reason_code"), f"{where}.reason_code"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "target_model_ref": self.target_model_ref,
            "reason_code": self.reason_code,
        }


def _model_ref(value: object, where: str) -> str:
    try:
        return str(ModelRef.parse(value))
    except ProfileError:
        raise InvalidPolicy(
            f"{where}.target_model_ref is not a model reference of the form "
            "provider_id/model_id"
        ) from None


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """§5. A declared condition over supplied evidence, and what it selects.

    The rule states WHAT it needs, never what it found. `requires_verdict` and
    `requires_evidence_class` are requirements checked against the supplied
    records at resolution; the records themselves are cited by the decision (§5.3),
    not by the rule.
    """

    rule_id: str
    priority: int
    reason_code: str
    falsifier: Falsifier
    discrimination: DiscriminationControl
    requires_verdict: OracleVerdict = OracleVerdict.PASS
    requires_evidence_class: EvidenceClass = EvidenceClass.MODEL_EXECUTION
    match_task_id: str | None = None
    requires_run_id: str | None = None
    select_model_ref: str | None = None
    select_agent: str | None = None

    @property
    def selects(self) -> bool:
        return self.select_model_ref is not None or self.select_agent is not None

    @classmethod
    def from_mapping(cls, raw: object, where: str = "rules[]") -> "PolicyRule":
        data = _mapping(raw, where)
        _closed(data, _RULE_KEYS, where)

        rule_id = _text(data.get("rule_id"), f"{where}.rule_id")

        priority = data.get("priority")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise InvalidPolicy(f"{where}.priority must be an integer")

        reason_code = _text(data.get("reason_code"), f"{where}.reason_code")

        # §7. Both are required, and required to SAY something.
        if "falsifier" not in data:
            raise InvalidPolicy(
                f"{where} carries no falsifier; §7 requires every rule to declare the "
                "observation that would show it is wrong, and a rule nothing could "
                "contradict is not a rule this contract defines"
            )
        if "discrimination" not in data:
            raise InvalidPolicy(
                f"{where} carries no discrimination control; §7 requires every policy "
                "to declare a pair of inputs it is REQUIRED to route differently, "
                "because a policy that always answers the same thing passes every "
                "check written against it"
            )
        falsifier = Falsifier.from_mapping(data.get("falsifier"), f"{where}.falsifier")
        discrimination = DiscriminationControl.from_mapping(
            data.get("discrimination"), f"{where}.discrimination"
        )

        try:
            requires_verdict = OracleVerdict(data.get("requires_verdict", "PASS"))
        except ValueError:
            raise InvalidPolicy(
                f"{where}.requires_verdict is not one of AI-11's six verdicts; AI-12 "
                "does not get its own verdict vocabulary"
            ) from None

        try:
            requires_class = EvidenceClass(
                data.get("requires_evidence_class", EvidenceClass.MODEL_EXECUTION)
            )
        except ValueError:
            raise InvalidPolicy(
                f"{where}.requires_evidence_class is not one of "
                f"{', '.join(m.value for m in EvidenceClass)}"
            ) from None

        select = _mapping(data.get("select", {}), f"{where}.select")
        _closed(select, _SELECT_KEYS, f"{where}.select")
        model_ref = select.get("model_ref")
        agent = select.get("agent")
        if model_ref is not None:
            try:
                model_ref = str(ModelRef.parse(model_ref))
            except ProfileError:
                raise InvalidPolicy(
                    f"{where}.select.model_ref is not a model reference of the form "
                    "provider_id/model_id"
                ) from None
        if agent is not None and not isinstance(agent, str):
            raise InvalidPolicy(f"{where}.select.agent must be a string")

        rule = cls(
            rule_id=rule_id,
            priority=priority,
            reason_code=reason_code,
            falsifier=falsifier,
            discrimination=discrimination,
            requires_verdict=requires_verdict,
            requires_evidence_class=requires_class,
            match_task_id=data.get("match_task_id"),
            requires_run_id=data.get("requires_run_id"),
            select_model_ref=model_ref,
            select_agent=agent,
        )
        for name in ("match_task_id", "requires_run_id"):
            value = getattr(rule, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise InvalidPolicy(f"{where}.{name} must be a non-empty string")

        # §4.2. A REFERENCE run says the task is solvable and this oracle says so.
        # It says nothing about any model, so it MUST NOT justify a selection.
        if rule.selects and rule.requires_evidence_class is EvidenceClass.REFERENCE:
            raise InvalidPolicy(
                f"{where} selects a model on REFERENCE evidence; a `BenchmarkRun` "
                "with `executor_kind = REFERENCE` is evidence about the task, the "
                "oracle and the reference execution path, and AI-12 MUST NOT select "
                "a model because such a run received PASS (§4.2)"
            )
        return rule

    def to_mapping(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "priority": self.priority,
            "reason_code": self.reason_code,
            "requires_verdict": str(self.requires_verdict),
            "requires_evidence_class": str(self.requires_evidence_class),
            "falsifier": self.falsifier.to_mapping(),
            "discrimination": self.discrimination.to_mapping(),
        }


@dataclass(frozen=True, slots=True)
class Policy:
    """§5. The artifact. Validated on construction, ordered by a total key."""

    policy_id: str
    revision: str
    evidence_scope: tuple[str, ...]
    rules: tuple[PolicyRule, ...] = ()
    state: PolicyState = PolicyState.DORMANT
    rollback: Rollback | None = None
    fallback: tuple[FallbackDeclaration, ...] = ()
    escalation: tuple[EscalationDeclaration, ...] = ()
    version: int = POLICY_VERSION

    @classmethod
    def from_mapping(cls, raw: object) -> "Policy":
        data = _mapping(raw, "policy")
        _closed(data, _POLICY_KEYS, "policy")

        if data.get("version") != POLICY_VERSION:
            raise InvalidPolicy(
                f"policy version {data.get('version')!r} is not supported; this "
                f"contract defines {POLICY_VERSION}"
            )

        policy_id = _text(data.get("policy_id"), "policy.policy_id")
        revision = _text(data.get("revision"), "policy.revision")

        try:
            state = PolicyState(data.get("state", PolicyState.DORMANT))
        except ValueError:
            raise InvalidPolicy(
                "policy.state is not one of "
                f"{', '.join(m.value for m in PolicyState)}"
            ) from None

        scope_raw = data.get("evidence_scope")
        if isinstance(scope_raw, (str, bytes)) or not isinstance(scope_raw, Sequence):
            raise InvalidPolicy(
                "policy.evidence_scope must be a list of AI-11 task ids; a policy that "
                "names no evidence scope cannot say what it reasoned over (§4.1)"
            )
        scope = tuple(_text(entry, "policy.evidence_scope[]") for entry in scope_raw)
        if not scope:
            raise InvalidPolicy(
                "policy.evidence_scope is empty; a policy that reasoned over no task "
                "has no evidence, and an empty scope would let a policy claim "
                "completeness by naming nothing"
            )
        duplicates = sorted({task for task in scope if scope.count(task) > 1})
        if duplicates:
            raise InvalidPolicy(
                f"policy.evidence_scope repeats {', '.join(duplicates)}; a scope is a "
                "set of tasks"
            )

        raw_rules = data.get("rules", [])
        if isinstance(raw_rules, (str, bytes)) or not isinstance(raw_rules, Sequence):
            raise InvalidPolicy("policy.rules must be a list")
        rules = tuple(PolicyRule.from_mapping(entry) for entry in raw_rules)

        seen = [rule.rule_id for rule in rules]
        duplicates = sorted({rid for rid in seen if seen.count(rid) > 1})
        if duplicates:
            raise InvalidPolicy(
                "rule_id must be unique within a policy (§5); duplicate(s): "
                f"{', '.join(duplicates)}. The ordering key is only total because "
                "rule_id is unique, and a duplicate is not resolved by keeping the "
                "first or the last"
            )

        rollback_raw = data.get("rollback")
        rollback = (
            None
            if rollback_raw is None
            else Rollback.from_mapping(rollback_raw, "policy.rollback")
        )

        raw_fallback = data.get("fallback", [])
        if isinstance(raw_fallback, (str, bytes)) or not isinstance(raw_fallback, Sequence):
            raise InvalidPolicy("policy.fallback must be a list")
        fallback = tuple(
            FallbackDeclaration.from_mapping(entry, f"policy.fallback[{index}]")
            for index, entry in enumerate(raw_fallback)
        )

        raw_escalation = data.get("escalation", [])
        if isinstance(raw_escalation, (str, bytes)) or not isinstance(
            raw_escalation, Sequence
        ):
            raise InvalidPolicy("policy.escalation must be a list")
        escalation = tuple(
            EscalationDeclaration.from_mapping(entry, f"policy.escalation[{index}]")
            for index, entry in enumerate(raw_escalation)
        )

        # §8. An activatable policy with no declared rollback MUST NOT be activated.
        # Refusing it here means "activated without a way back" is unrepresentable
        # rather than merely discouraged.
        if state is PolicyState.ACTIVE and rollback is None:
            raise InvalidPolicy(
                "policy.state is ACTIVE with no rollback; §8 makes a declared "
                "previous policy, trigger and decider mandatory before activation, "
                "and a policy with no way back MUST NOT be activated"
            )

        return cls(
            policy_id=policy_id,
            revision=revision,
            evidence_scope=scope,
            # Ordered by (priority ascending, rule_id lexicographic ascending). The
            # key is total, so no two rules compare equal and no tie-break is left
            # to file order or insertion order.
            rules=tuple(sorted(rules, key=lambda r: (r.priority, r.rule_id))),
            state=state,
            rollback=rollback,
            fallback=fallback,
            escalation=escalation,
        )

    @property
    def selecting_rules(self) -> tuple[PolicyRule, ...]:
        return tuple(rule for rule in self.rules if rule.selects)

    def rule(self, rule_id: str) -> PolicyRule | None:
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
