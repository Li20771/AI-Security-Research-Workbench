"""AI-04 — Security Guard Plugin.

Guard is the deterministic, rule-based, workspace-scoped authorization boundary
of the Workbench. It decides whether a normalized action may proceed under an
explicit policy and verified execution preconditions.

```text
Guard decides. It does not execute.
```

The frozen entry point (contract §9.1):

```python
from plugins.guard import evaluate

record = evaluate(request, policy)     # -> DecisionRecord
record.decision                        # GuardDecision
record.reason_code, record.reasons     # why
record.provenance.rule_id              # which rule decided
record.request_digest, record.evaluation_digest
```

The policy is a **parameter**, never something Guard obtains. Guard performs no
policy discovery, storage, selection or loading, and imports no network client,
no subprocess and no `eval`. A component that both chooses its rules and applies
them can authorize anything by choosing a permissive rule set.

Guard is not Context collection, capability probing, evidence persistence, model
routing, provider invocation, tool execution, approval issuance, or SecurityLab
integration — see §22 of the contract.

**Frozen types are imported, not restated** (§28.2): AI-02's `CapabilityStatus`
and AI-03's `WorkingTreeState`, `ItemKind`, `StatusValue`, `Freshness`,
`ContextResponse` and `ItemRef` are consumed from their owning packages.
Redefining one would mean two definitions to keep in step, and one of them would
be forgotten.

Contract: `docs/AI-04_GUARD_EXECUTION_PLAN.md`.
"""

from __future__ import annotations

from plugins.guard.digest import (
    RUNTIME_ONLY_FIELDS,
    RuleTraceEntry,
    canonical_json,
    context_projection,
    digest_of,
    evaluation_projection,
    policy_digest,
    request_projection,
    sha256_hex,
)
from plugins.guard.errors import (
    GuardError,
    OrderingCycle,
    PolicyDigestMismatch,
    PolicyDuplicateRuleId,
    PolicyInvalid,
    PolicyMissing,
    PolicyWorkspaceMismatch,
    PredicateUnsupported,
    RequestMalformed,
    RequestUnscoped,
    WorkspaceUnresolvable,
)
from plugins.guard.evaluator import (
    GateOutcome,
    WalkResult,
    check_absolute_deny,
    check_approval_gate,
    check_policy,
    check_target_classification,
    check_workspace_agreement,
    evaluate,
    walk,
)
from plugins.guard.models import (
    SUPPORTED_SCHEMA_VERSION,
    Actor,
    ActionRef,
    ApprovalRef,
    CapabilityRecord,
    CapabilityRef,
    CheckRecord,
    DecisionRecord,
    GuardRequest,
    Provenance,
    TargetRef,
    WorkspaceRef,
)
from plugins.guard.ordering import (
    Constraint,
    at_least_as_specific,
    constraints_for,
    is_total_order,
    linearize_bucket,
    order_rules,
    strictly_more_specific,
)
from plugins.guard.policy import (
    FIXED_FIELD_REFS,
    PREDICATE_NAMES,
    FieldRef,
    Policy,
    Predicate,
    Rule,
    validate_policy,
)
from plugins.guard.predicates import (
    Resolution,
    evaluate_predicate,
    evaluate_predicates,
    resolve_field,
)
from plugins.guard.vocabulary import (
    AGGREGATE_DECISION,
    CHECK_RESULT_RANK,
    EFFECT_RANK,
    ActorType,
    ApprovalStatus,
    CapabilityStatus,
    CheckResult,
    Freshness,
    GuardDecision,
    ItemKind,
    PermissionLevel,
    RuleEffect,
    StatusValue,
    TargetEnvironment,
    TargetInterface,
    TargetKind,
    TargetSensitivity,
    WorkingTreeState,
    aggregate,
)

__all__ = [
    "AGGREGATE_DECISION",
    "CHECK_RESULT_RANK",
    "EFFECT_RANK",
    "FIXED_FIELD_REFS",
    "PREDICATE_NAMES",
    "RUNTIME_ONLY_FIELDS",
    "SUPPORTED_SCHEMA_VERSION",
    "Actor",
    "ActorType",
    "ActionRef",
    "ApprovalRef",
    "ApprovalStatus",
    "CapabilityRecord",
    "CapabilityRef",
    "CapabilityStatus",
    "CheckRecord",
    "CheckResult",
    "Constraint",
    "DecisionRecord",
    "FieldRef",
    "Freshness",
    "GateOutcome",
    "GuardDecision",
    "GuardError",
    "GuardRequest",
    "ItemKind",
    "OrderingCycle",
    "PermissionLevel",
    "Policy",
    "PolicyDigestMismatch",
    "PolicyDuplicateRuleId",
    "PolicyInvalid",
    "PolicyMissing",
    "PolicyWorkspaceMismatch",
    "Predicate",
    "PredicateUnsupported",
    "Provenance",
    "RequestMalformed",
    "RequestUnscoped",
    "Resolution",
    "Rule",
    "RuleEffect",
    "RuleTraceEntry",
    "StatusValue",
    "TargetEnvironment",
    "TargetInterface",
    "TargetKind",
    "TargetRef",
    "TargetSensitivity",
    "WalkResult",
    "WorkingTreeState",
    "WorkspaceRef",
    "WorkspaceUnresolvable",
    "aggregate",
    "at_least_as_specific",
    "canonical_json",
    "check_absolute_deny",
    "check_approval_gate",
    "check_policy",
    "check_target_classification",
    "check_workspace_agreement",
    "constraints_for",
    "context_projection",
    "digest_of",
    "evaluate",
    "evaluate_predicate",
    "evaluate_predicates",
    "evaluation_projection",
    "is_total_order",
    "linearize_bucket",
    "order_rules",
    "policy_digest",
    "request_projection",
    "resolve_field",
    "sha256_hex",
    "strictly_more_specific",
    "validate_policy",
    "walk",
]
