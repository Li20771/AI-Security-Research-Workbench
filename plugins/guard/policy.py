"""Policy, rule, and the frozen predicate grammar.

Implements AI-04 contract §9, §9.2, §10 and §11. The grammar is exactly three
predicates over a closed field set:

    eq       field == value
    in       field ∈ {value, ...}      finite, non-empty
    exists   field is present and not null

`conditions[]` is a logical AND. **There is no `OR`**, and none is added by
nesting: §11.1 expresses disjunction by writing multiple rules, because an `OR`
would make rule precedence depend on how a predicate was factored — which is
exactly the ambiguity §12 exists to eliminate.

The grammar is closed and there is no extension point (§11.5). No `eval`, no
scripts, no regex, no arithmetic, no natural-language policy, no LLM-generated
predicate. A policy that names an unlisted predicate or field is **invalid**
(§11.6), and invalid is `BLOCKED` — never `REJECTED`, because a policy defect
must not present as a clean "this rule does not apply and something else may
allow it".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from plugins.guard.errors import PolicyDuplicateRuleId, PolicyInvalid
from plugins.guard.vocabulary import (
    EFFECT_RANK,
    PermissionLevel,
    RuleEffect,
    TargetInterface,
    TargetKind,
    TargetSensitivity,
    WorkingTreeState,
    CapabilityStatus,
    ApprovalStatus,
    Freshness,
    ItemKind,
    StatusValue,
)

#: The three predicates (§11.1). Exactly three.
PREDICATE_NAMES: frozenset[str] = frozenset({"eq", "in", "exists"})

#: Fixed FieldRefs (§11.2), before the parameterised `context.<subject>.<facet>`.
FIXED_FIELD_REFS: frozenset[str] = frozenset(
    {
        "workspace.id",
        "workspace.branch",
        "workspace.working_tree",
        "action.id",
        "action.permission_level",
        "capability.id",
        "capability.status",
        "target.kind",
        "target.sensitivity",
        "target.interface",
        "target.is_real",
        "approval.status",
        "approval.reference",
    }
)

CONTEXT_FIELD_RE = re.compile(
    r"^context\.(?P<subject>[^.]+(?:\.(?!item_kind$|truth_state$|freshness$)[^.]+)*)"
    r"\.(?P<facet>item_kind|truth_state|freshness)$"
)

#: The value domain of each fixed FieldRef (§11.3). A comparison against a value
#: outside the domain is unsupported, not false.
FIELD_DOMAINS: Mapping[str, frozenset[str]] = {
    "workspace.working_tree": frozenset(m.value for m in WorkingTreeState),
    "action.permission_level": frozenset(m.value for m in PermissionLevel),
    "capability.status": frozenset(m.value for m in CapabilityStatus),
    "target.kind": frozenset(m.value for m in TargetKind),
    "target.sensitivity": frozenset(m.value for m in TargetSensitivity),
    "target.interface": frozenset(m.value for m in TargetInterface),
    "approval.status": frozenset(m.value for m in ApprovalStatus),
}

CONTEXT_FACET_DOMAINS: Mapping[str, frozenset[str]] = {
    "item_kind": frozenset(m.value for m in ItemKind),
    "truth_state": frozenset(m.value for m in StatusValue),
    "freshness": frozenset(m.value for m in Freshness),
}

#: Fields whose values are booleans, not vocabulary members.
BOOLEAN_FIELDS: frozenset[str] = frozenset({"target.is_real"})

#: Fields whose values are open strings compared literally (§11.3). They carry
#: no authorization semantics of their own.
OPEN_FIELDS: frozenset[str] = frozenset(
    {
        "workspace.id",
        "workspace.branch",
        "action.id",
        "capability.id",
        "approval.reference",
    }
)


@dataclass(frozen=True, slots=True)
class FieldRef:
    """A parsed, validated field reference (§11.2, §11.3)."""

    text: str
    subject: str | None = None  # set only for context.<subject>.<facet>
    facet: str | None = None

    @property
    def is_context(self) -> bool:
        return self.subject is not None

    @property
    def is_boolean(self) -> bool:
        return self.text in BOOLEAN_FIELDS

    @property
    def domain(self) -> frozenset[str] | None:
        """The closed value domain, or `None` for an open or boolean field."""
        if self.facet is not None:
            return CONTEXT_FACET_DOMAINS.get(self.facet)
        return FIELD_DOMAINS.get(self.text)

    @classmethod
    def parse(cls, text: Any) -> "FieldRef":
        if not isinstance(text, str) or not text:
            raise PolicyInvalid(f"field reference must be a non-empty string; got {text!r}")
        if text in FIXED_FIELD_REFS:
            return cls(text=text)
        match = CONTEXT_FIELD_RE.match(text)
        if match is not None:
            return cls(
                text=text,
                subject=match.group("subject"),
                facet=match.group("facet"),
            )
        raise PolicyInvalid(
            f"field reference {text!r} is not in the closed set (§11.2)"
        )

    def check_literal(self, value: Any) -> None:
        """Refuse a literal the field's domain cannot hold (§11.3, §11.6)."""
        if self.is_boolean:
            if not isinstance(value, bool):
                raise PolicyInvalid(
                    f"{self.text} is boolean; got {type(value).__name__}"
                )
            return
        domain = self.domain
        if domain is None:
            if not isinstance(value, str):
                raise PolicyInvalid(
                    f"{self.text} is an open string field; got {type(value).__name__}"
                )
            return
        if not isinstance(value, str) or value not in domain:
            raise PolicyInvalid(
                f"{self.text}: {value!r} is not one of {sorted(domain)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "subject": self.subject, "facet": self.facet}


@dataclass(frozen=True, slots=True)
class Predicate:
    """One `eq`, `in` or `exists` (§11.1)."""

    field: FieldRef
    op: str
    value: Any = None

    def __post_init__(self) -> None:
        if self.op not in PREDICATE_NAMES:
            raise PolicyInvalid(
                f"predicate {self.op!r} is not one of {sorted(PREDICATE_NAMES)}"
            )
        if self.op == "exists":
            if self.value is not None:
                raise PolicyInvalid("exists takes no value")
            return
        if self.op == "eq":
            self.field.check_literal(self.value)
            return
        # in
        if not isinstance(self.value, (tuple, list)) or not self.value:
            raise PolicyInvalid("in requires a non-empty finite list of literals")
        for item in self.value:
            self.field.check_literal(item)

    @property
    def values(self) -> tuple[Any, ...]:
        return tuple(self.value) if self.op == "in" else (self.value,)

    def check_id(self) -> str:
        if self.op == "exists":
            return f"{self.field.text} exists"
        return f"{self.field.text} {self.op} {sorted(map(str, self.values))}"

    @property
    def canonical_values(self) -> tuple[Any, ...]:
        """The literal in canonical form (§20.3).

        `in` is a **set**, so its values are sorted: `in [a, b]` and `in [b, a]`
        are the same constraint, and serialising them differently would make a
        policy's digest depend on how its author happened to order a list.
        """
        if self.op == "exists":
            return ()
        if self.op == "eq":
            return (self.value,)
        return tuple(sorted(self.value, key=lambda v: (type(v).__name__, str(v))))

    def canonical_key(self) -> tuple[str, str, tuple[str, ...]]:
        """Sort key for §20.3's set-semantic collections.

        `(field, predicate, canonical value)`, exactly as the contract names it.
        """
        return (
            self.field.text,
            self.op,
            tuple(str(v) for v in self.canonical_values),
        )

    def to_dict(self) -> dict[str, Any]:
        values = self.canonical_values
        return {
            "field": self.field.text,
            "op": self.op,
            "value": (
                None
                if self.op == "exists"
                else (values[0] if self.op == "eq" else list(values))
            ),
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], where: str) -> "Predicate":
        if not isinstance(raw, Mapping):
            raise PolicyInvalid(f"{where}: predicate must be an object")
        field = FieldRef.parse(raw.get("field"))
        op = raw.get("op")
        if op not in PREDICATE_NAMES:
            raise PolicyInvalid(
                f"{where}: predicate {op!r} is not one of {sorted(PREDICATE_NAMES)}"
            )
        if op == "exists":
            return cls(field=field, op=op)
        if op == "eq":
            return cls(field=field, op=op, value=raw.get("value"))
        values = raw.get("value")
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise PolicyInvalid(f"{where}: in requires a list literal")
        return cls(field=field, op=op, value=tuple(values))


@dataclass(frozen=True, slots=True)
class Rule:
    """Contract §10. `effect` is `ALLOW` or `DENY` and nothing else."""

    rule_id: str
    priority: int
    effect: RuleEffect
    reason_code: str
    match: tuple[Predicate, ...] = ()
    conditions: tuple[Predicate, ...] = ()

    @property
    def sort_bucket(self) -> tuple[int, int]:
        """§12 steps 2 and 3: the `(priority, effect)` bucket."""
        return (self.priority, EFFECT_RANK[self.effect])

    @property
    def canonical_match(self) -> tuple[Predicate, ...]:
        """`match` entries sorted for serialization (§20.3: sorted by field)."""
        return tuple(sorted(self.match, key=Predicate.canonical_key))

    @property
    def canonical_conditions(self) -> tuple[Predicate, ...]:
        """`conditions[]` sorted for serialization (§20.3)."""
        return tuple(sorted(self.conditions, key=Predicate.canonical_key))

    def to_dict(self) -> dict[str, Any]:
        """The canonical form, used for `policy.digest`.

        `match` and `conditions[]` are **set-semantic** (§20.3), so they are
        emitted sorted. Without this, two policies whose predicates differ only
        in written order would hash differently — a digest that changes when
        nothing semantic did, which is precisely what §12's "policy file order
        is never semantically meaningful" forbids one level up.
        """
        return {
            "rule_id": self.rule_id,
            "priority": self.priority,
            "effect": str(self.effect),
            "reason_code": self.reason_code,
            "match": [p.to_dict() for p in self.canonical_match],
            "conditions": [p.to_dict() for p in self.canonical_conditions],
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], index: int) -> "Rule":
        where = f"rules[{index}]"
        if not isinstance(raw, Mapping):
            raise PolicyInvalid(f"{where}: rule must be an object")

        rule_id = raw.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            raise PolicyInvalid(f"{where}: rule_id must be a non-empty string")

        priority = raw.get("priority")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise PolicyInvalid(f"{where}: priority must be an integer")

        effect = raw.get("effect")
        try:
            effect_value = RuleEffect(effect)
        except ValueError:
            raise PolicyInvalid(
                f"{where}: effect {effect!r} must be ALLOW or DENY; BLOCKED and "
                "UNKNOWN are evaluation outcomes, not policy effects (§10)"
            ) from None

        reason_code = raw.get("reason_code")
        if not isinstance(reason_code, str) or not reason_code:
            raise PolicyInvalid(f"{where}: reason_code must be a non-empty string")

        return cls(
            rule_id=rule_id,
            priority=priority,
            effect=effect_value,
            reason_code=reason_code,
            match=_predicates(raw.get("match", []), f"{where}.match"),
            conditions=_predicates(raw.get("conditions", []), f"{where}.conditions"),
        )


def _predicates(raw: Any, where: str) -> tuple[Predicate, ...]:
    if raw is None:
        return ()
    if isinstance(raw, Mapping):
        raw = [raw]
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise PolicyInvalid(f"{where} must be a list of predicates")
    return tuple(Predicate.from_mapping(entry, where) for entry in raw)


@dataclass(frozen=True, slots=True)
class Policy:
    """An immutable, reviewed snapshot for exactly one workspace (§9).

    Guard **verifies and evaluates** a policy; it never discovers, stores,
    selects or loads one (§9.1). This type is therefore a value a caller hands
    in, not something Guard goes looking for.
    """

    policy_id: str
    revision: str
    workspace_id: str
    rules: tuple[Rule, ...]
    digest: str | None = None
    version: int = 1

    @property
    def digest_is_declared(self) -> bool:
        return self.digest is not None

    def rule_by_id(self, rule_id: str) -> Rule | None:
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    @property
    def duplicate_rule_ids(self) -> tuple[str, ...]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for rule in self.rules:
            if rule.rule_id in seen and rule.rule_id not in duplicates:
                duplicates.append(rule.rule_id)
            seen.add(rule.rule_id)
        return tuple(duplicates)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Policy":
        if not isinstance(raw, Mapping):
            raise PolicyInvalid("policy must be an object")

        version = raw.get("version")
        if version != 1:
            raise PolicyInvalid(f"policy version {version!r} is not supported")

        for name in ("policy_id", "revision", "workspace_id"):
            value = raw.get(name)
            if not isinstance(value, str) or not value:
                raise PolicyInvalid(f"policy.{name} must be a non-empty string")

        rules_raw = raw.get("rules")
        if isinstance(rules_raw, (str, bytes)) or not isinstance(rules_raw, Sequence):
            raise PolicyInvalid("policy.rules must be a list")

        digest = raw.get("digest")
        if digest is not None and (not isinstance(digest, str) or not digest):
            raise PolicyInvalid("policy.digest must be a non-empty string or null")

        return cls(
            policy_id=raw["policy_id"],
            revision=raw["revision"],
            workspace_id=raw["workspace_id"],
            rules=tuple(
                Rule.from_mapping(entry, index)
                for index, entry in enumerate(rules_raw)
            ),
            digest=digest,
            version=version,
        )

    def to_semantic_dict(self) -> dict[str, Any]:
        """The §20.5 projection hashed for `policy.digest`.

        `rules` is sorted by `rule_id` here, not evaluation order: a digest must
        not depend on how a file was written (§20.3), and file order is not
        semantically meaningful (§12). The **evaluation trace** is a different
        order and is produced by §12.2.2 — conflating the two would either make
        the digest file-order-dependent or misreport the order rules were
        actually evaluated in.
        """
        return {
            "version": self.version,
            "policy_id": self.policy_id,
            "revision": self.revision,
            "workspace_id": self.workspace_id,
            "rules": [
                rule.to_dict() for rule in sorted(self.rules, key=lambda r: r.rule_id)
            ],
        }


def validate_policy(policy: Policy) -> None:
    """Enforce every §9.2 validation invariant.

    Raises `PolicyInvalid` (or a subclass) on the first violation. The evaluator
    converts any of these to `BLOCKED`; an invalid policy never reaches ordinary
    rule evaluation.

    The digest check lives in `digest.py` because it needs the canonicalizer;
    it is applied by the evaluator alongside this one, and §9.2 lists both.
    """
    if policy.version != 1:
        raise PolicyInvalid(f"policy version {policy.version!r} is not supported")

    duplicates = policy.duplicate_rule_ids
    if duplicates:
        # §9.2: never resolved by overwriting, by keeping first or last, by
        # dictionary order, or by file order. There is no defined behaviour
        # because there is no defined behaviour -- the policy is invalid.
        raise PolicyDuplicateRuleId(
            f"duplicate rule_id(s) {sorted(duplicates)}; rule_id must be unique "
            "within a policy (§9.2)"
        )

    for rule in policy.rules:
        for predicate in (*rule.match, *rule.conditions):
            # Constructing the Predicate already validated the grammar and the
            # literal against its domain; this re-walk is what catches a policy
            # built programmatically rather than parsed.
            if predicate.op not in PREDICATE_NAMES:
                raise PolicyInvalid(f"{rule.rule_id}: unsupported predicate {predicate.op!r}")
            if predicate.op != "exists":
                for value in predicate.values:
                    predicate.field.check_literal(value)


__all__ = [
    "BOOLEAN_FIELDS",
    "CONTEXT_FACET_DOMAINS",
    "FIELD_DOMAINS",
    "FIXED_FIELD_REFS",
    "OPEN_FIELDS",
    "PREDICATE_NAMES",
    "FieldRef",
    "Policy",
    "Predicate",
    "Rule",
    "validate_policy",
]
