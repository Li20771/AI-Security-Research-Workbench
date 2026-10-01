"""Rules and rule sets. Contract §7, §12.

```text
v1 is deterministic, explainable and configurable.
```

Not: reinforcement learning, online learning, model self-selection, an opaque
score, or an LLM-generated routing decision. AI-00 §13 records that the Workbench
does not accept "the model said so" as a result, and a routing decision produced
by a model would be exactly that — a judgement nobody can audit, made by the thing
being selected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from providers.profile import ModelRef, ProfileError

from routing.errors import InvalidRules
from routing.request import RouterRequest

__all__ = ["Rule", "RuleSet", "SUPPORTED_RULES_VERSION"]

SUPPORTED_RULES_VERSION = 1

_MATCH_KEYS = frozenset(
    {"task_class", "requested_capability", "modality", "require_independence"}
)
_SELECT_KEYS = frozenset({"model_ref", "agent"})
_RULE_KEYS = frozenset({"rule_id", "priority", "match", "select", "reason_code"})


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidRules(f"{where} must be an object")
    return value


def _closed(raw: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise InvalidRules(
            f"{where} has field(s) the contract does not define: "
            f"{', '.join(sorted(map(str, unknown)))}"
        )


@dataclass(frozen=True, slots=True)
class Rule:
    """§7.2. A condition and a selection.

    An **absent match field is no constraint**, not an empty one. Every present
    field must match.
    """

    rule_id: str
    priority: int
    reason_code: str
    match_task_class: str | None = None
    match_requested_capability: str | None = None
    match_modality: str | None = None
    match_require_independence: bool | None = None
    select_model_ref: str | None = None
    select_agent: str | None = None

    @classmethod
    def from_mapping(cls, raw: object, where: str = "rules[]") -> "Rule":
        data = _mapping(raw, where)
        _closed(data, _RULE_KEYS, where)

        rule_id = data.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            raise InvalidRules(f"{where}.rule_id must be a non-empty string")

        priority = data.get("priority")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise InvalidRules(f"{where}.priority must be an integer")

        reason_code = data.get("reason_code")
        if not isinstance(reason_code, str) or not reason_code:
            raise InvalidRules(f"{where}.reason_code must be a non-empty string")

        match = _mapping(data.get("match", {}), f"{where}.match")
        _closed(match, _MATCH_KEYS, f"{where}.match")

        select = _mapping(data.get("select", {}), f"{where}.select")
        _closed(select, _SELECT_KEYS, f"{where}.select")
        model_ref = select.get("model_ref")
        agent = select.get("agent")
        if model_ref is None and agent is None:
            raise InvalidRules(
                f"{where}.select names neither a model_ref nor an agent; a rule that "
                "selects nothing cannot be evaluated (§12.4)"
            )
        if model_ref is not None:
            try:
                model_ref = str(ModelRef.parse(model_ref))
            except ProfileError:
                raise InvalidRules(
                    f"{where}.select.model_ref is not a model reference of the form "
                    "provider_id/model_id"
                ) from None
        if agent is not None and not isinstance(agent, str):
            raise InvalidRules(f"{where}.select.agent must be a string")

        independence = match.get("require_independence")
        if independence is not None and not isinstance(independence, bool):
            raise InvalidRules(f"{where}.match.require_independence must be true or false")

        return cls(
            rule_id=rule_id,
            priority=priority,
            reason_code=reason_code,
            match_task_class=match.get("task_class"),
            match_requested_capability=match.get("requested_capability"),
            match_modality=match.get("modality"),
            match_require_independence=independence,
            select_model_ref=model_ref,
            select_agent=agent,
        )

    def matches(self, request: RouterRequest) -> bool:
        """Every present constraint must hold. An absent one is not a constraint."""
        if self.match_task_class is not None and self.match_task_class != request.task_class:
            return False
        if (
            self.match_requested_capability is not None
            and self.match_requested_capability != request.requested_capability
        ):
            return False
        if self.match_modality is not None and self.match_modality != request.modality:
            return False
        if (
            self.match_require_independence is not None
            and self.match_require_independence != request.require_independence
        ):
            return False
        return True

    def to_mapping(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "priority": self.priority,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class RuleSet:
    """§12. A reviewed, tracked rule set.

    The rules are stored in the order the contract's key defines, computed once at
    construction, so no caller can read file order or insertion order as
    selection semantics.
    """

    revision: str
    rules: tuple[Rule, ...]
    version: int = SUPPORTED_RULES_VERSION

    @classmethod
    def from_mapping(cls, raw: object) -> "RuleSet":
        data = _mapping(raw, "rule set")
        _closed(data, frozenset({"version", "revision", "rules"}), "rule set")

        if data.get("version") != SUPPORTED_RULES_VERSION:
            raise InvalidRules(
                f"rule set version {data.get('version')!r} is not supported; this "
                f"contract defines {SUPPORTED_RULES_VERSION}"
            )
        revision = data.get("revision")
        if not isinstance(revision, str) or not revision:
            raise InvalidRules("rule set revision must be a non-empty string")

        raw_rules = data.get("rules", [])
        if isinstance(raw_rules, (str, bytes)) or not isinstance(raw_rules, Sequence):
            raise InvalidRules("rule set rules must be a list")
        rules = tuple(Rule.from_mapping(entry) for entry in raw_rules)

        seen = [rule.rule_id for rule in rules]
        duplicates = sorted({rid for rid in seen if seen.count(rid) > 1})
        if duplicates:
            raise InvalidRules(
                "rule_id must be unique within a rule set (§12.4); duplicate(s): "
                f"{', '.join(duplicates)}. §7.5's ordering key is only total because "
                "rule_id is unique, and a duplicate is not resolved by keeping the "
                "first or the last"
            )

        # §7.5: ordered by (priority ascending, rule_id lexicographic ascending).
        # The key is total, so no two rules compare equal and no tie-break is
        # left to chance.
        return cls(revision=revision, rules=tuple(sorted(rules, key=lambda r: (r.priority, r.rule_id))))

    @classmethod
    def empty(cls, revision: str = "v1-empty") -> "RuleSet":
        """The v1 default: the mechanism, and no tuned rule set.

        AI-00 F-12: *"Model routing v2 must be built on real benchmark data."*
        There is no benchmark, and a default rule set presented as tuned would be
        a claim the repository cannot support.
        """
        return cls(revision=revision, rules=())

    def first_match(self, request: RouterRequest) -> Rule | None:
        """The first rule in the frozen order that matches, or `None`.

        There is deliberately no implicit default: §7.6 makes a request that
        matches no rule `NO_ELIGIBLE_MODEL`, because a default would be a rule
        nobody wrote applying to every request the author did not consider.
        """
        for rule in self.rules:
            if rule.matches(request):
                return rule
        return None
