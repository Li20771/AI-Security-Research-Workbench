"""Shared fixtures for the AI-04 Guard tests.

Builders rather than constants, because most tests need to vary one field and
hold the rest fixed, and a test that restates the whole request to change one
value hides which value it is actually about.

No test requires a credential, a network, a provider, or a filesystem.
"""

from __future__ import annotations

from typing import Any

import pytest

WS = "ws-1"
WS_OTHER = "ws-2"


def make_request(**overrides: Any) -> dict[str, Any]:
    """A well-formed, benign request. `overrides` replaces whole sub-objects."""
    request: dict[str, Any] = {
        "schema_version": 1,
        "actor": {"id": "human:reviewer", "type": "human"},
        "workspace": {
            "workspace_id": WS,
            "repository": "Li20771/AI-Security-Research-Workbench",
            "branch": "main",
            "commit": "a" * 40,
            "detached": False,
            "working_tree": "CLEAN",
        },
        "action": {"id": "read-file", "permission_level": "read"},
        "capability": {"id": None},
        "target": {
            "kind": "repository",
            "identifier": "src/",
            "environment": "isolated",
            "interface": "isolated_harness",
            "is_real": False,
            "sensitivity": "internal",
        },
        "context": None,
        "capability_state": {"records": []},
        "approval": {"status": "MISSING", "scope_digest": None, "reference": None},
    }
    request.update(overrides)
    return request


def make_rule(
    rule_id: str,
    *,
    effect: str = "ALLOW",
    priority: int = 0,
    match: list[dict[str, Any]] | None = None,
    conditions: list[dict[str, Any]] | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "priority": priority,
        "effect": effect,
        "reason_code": reason_code or f"REASON_{rule_id.upper()}",
        "match": match or [],
        "conditions": conditions or [],
    }


def make_policy(
    *rules: dict[str, Any],
    workspace_id: str = WS,
    policy_id: str = "policy-1",
    revision: str = "rev-1",
    digest: str | None = None,
) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "version": 1,
        "policy_id": policy_id,
        "revision": revision,
        "workspace_id": workspace_id,
        "rules": list(rules),
    }
    if digest is not None:
        policy["digest"] = digest
    return policy


def eq(field: str, value: Any) -> dict[str, Any]:
    return {"field": field, "op": "eq", "value": value}


def contains(field: str, *values: Any) -> dict[str, Any]:
    return {"field": field, "op": "in", "value": list(values)}


def exists(field: str) -> dict[str, Any]:
    return {"field": field, "op": "exists"}


def make_context_item(
    subject: str = "declared.gate",
    *,
    item_kind: str = "FACT",
    truth_state: str = "PASS",
    freshness: str = "CURRENT",
    value: str = "PASS",
    workspace_id: str = WS,
):
    """An AI-03 `ContextItem`, built through AI-03's own `classify`.

    Built rather than hand-constructed so the tests consume the real type from
    its owning package (§28.2) rather than a shape redefined here. `replace`
    then sets the facets a given test is about, which `classify` derives rather
    than accepts — a PLAN item, for instance, cannot be produced by classifying
    a declaration.
    """
    import dataclasses

    from plugins.context.classification import RawItem, classify
    from plugins.context.vocabulary import (
        Freshness,
        ItemKind,
        SourceKind,
        StatusValue,
    )

    base = classify(
        RawItem(subject=subject, value=value, declared_state=value),
        source_kind=SourceKind.EXIT_REPORT,
        source_identity="docs/fixture.md",
        source_revision="rev",
        retrieved_at="2026-09-29T00:00:00Z",
        workspace_id=workspace_id,
        freshness=Freshness(freshness),
    )
    return dataclasses.replace(
        base,
        item_kind=ItemKind(item_kind),
        freshness=Freshness(freshness),
        truth_state=StatusValue(truth_state),
    )


def make_context(*items, workspace_id: str = WS):
    """An AI-03 `ContextResponse` holding `items`, split by kind."""
    from plugins.context.context import ContextResponse, FreshnessSummary
    from plugins.context.vocabulary import (
        ContextStatus,
        Freshness,
        ItemKind,
        WorkingTreeState,
    )
    from plugins.context.workspace import WorkspaceIdentity

    facts = tuple(i for i in items if i.item_kind is ItemKind.FACT)
    history = tuple(i for i in items if i.item_kind is ItemKind.HISTORY)
    plans = tuple(i for i in items if i.item_kind is ItemKind.PLAN)
    values = tuple(i.freshness for i in items)

    return ContextResponse(
        workspace=WorkspaceIdentity(
            workspace_id=workspace_id,
            workspace_root="/tmp/ws",
            repository=None,
            branch="main",
            commit="a" * 40,
            detached=False,
            working_tree=WorkingTreeState.CLEAN,
            changed_files=0,
        ),
        facts=facts,
        history=history,
        plans=plans,
        sources=(),
        freshness=FreshnessSummary.of(values),
        status=ContextStatus.FULL,
        conflicts=(),
        retrieved_at="2026-09-29T00:00:00Z",
    )


@pytest.fixture
def request_factory():
    return make_request


@pytest.fixture
def policy_factory():
    return make_policy


@pytest.fixture
def rule_factory():
    return make_rule


@pytest.fixture
def permissive_policy():
    """A policy whose single rule allows anything. Used to reach the gates."""
    return make_policy(make_rule("allow-all", priority=0))
