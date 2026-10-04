"""Builders for the AI-14-B composition tests.

Everything here is built from the SHIPPED registry — the real `providers/`
profiles and the real `tools/` adapter family — because the composition's job is
to connect what exists. A test that needed synthetic profiles would be testing a
repository this one is not.
"""

from __future__ import annotations

import pathlib
from typing import Any, Mapping

from plugins.context import resolve_workspace
from plugins.guard.models import Actor, TargetRef
from plugins.guard.vocabulary import ActorType, PermissionLevel, TargetKind
from providers.config import ProviderConfig, ProviderConfigEntry
from providers.model_registry import load_all_model_profiles
from providers.registry import load_all_providers
from plugins.security_tools.identity import ToolIdentity
from plugins.security_tools.request import ToolWorkspace
from plugins.security_tools.vocabulary import AdapterFamily
from routing.request import RouterRequest
from routing.rules import RuleSet

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: AI-02's registry, as it ships. Every capability on every profile is UNKNOWN.
PROFILES = load_all_model_profiles()
PROVIDERS = load_all_providers()

#: Every registered provider id.
ALL_PROVIDERS = frozenset(PROVIDERS)

#: One shipped model ref, inside AI-09's supported scope.
A_MODEL_REF = "mimo/mimo-v2.6-flash"

#: The git adapter's declared identity (tools/git/__init__.py).
GIT_TOOL_ID = "git"
GIT_TOOL_VERSION = "1.0.0"


def a_rule_set(
    *,
    model_ref: str | None = A_MODEL_REF,
    agent: str | None = None,
    task_class: str = "simple",
    revision: str = "rules-test",
) -> RuleSet:
    """One matching rule, selecting `model_ref` and optionally an agent hint."""
    select: dict[str, Any] = {}
    if model_ref is not None:
        select["model_ref"] = model_ref
    if agent is not None:
        select["agent"] = agent
    return RuleSet.from_mapping(
        {
            "version": 1,
            "revision": revision,
            "rules": [
                {
                    "rule_id": "r-select",
                    "priority": 10,
                    "reason_code": "TEST_MATCH",
                    "match": {"task_class": task_class},
                    "select": select,
                }
            ],
        }
    )


def an_empty_rule_set(revision: str = "rules-empty") -> RuleSet:
    """No rules at all: the Router selects nothing (§7.6)."""
    return RuleSet.empty(revision)


def a_router_request(
    *,
    task_class: str = "simple",
    workspace_id: str = "ws-1",
    candidates: tuple[str, ...] = (A_MODEL_REF,),
    actor_id: str = "dsh",
    extra: Mapping[str, Any] | None = None,
) -> RouterRequest:
    """A valid request naming the shipped candidates."""
    raw: dict[str, Any] = {
        "schema_version": 1,
        "task": {"task_class": task_class},
        "workspace": {"workspace_id": workspace_id},
        "actor": {"id": actor_id, "type": "agent"},
        "candidates": [{"model_ref": ref} for ref in candidates],
    }
    raw.update(extra or {})
    return RouterRequest.from_mapping(raw)


def a_workspace(root: pathlib.Path) -> tuple[pathlib.Path, str]:
    """A real directory, and the workspace identity AI-03 resolves for it."""
    root.mkdir(parents=True, exist_ok=True)
    return root, resolve_workspace(root).workspace_id


def a_provider_config(
    *, enabled: tuple[str, ...] = (), reserved: tuple[str, ...] = ()
) -> ProviderConfig:
    """Runtime config for every registered provider, disabled unless named.

    AI-02 ships every provider `enabled: false`, so this mirrors the shipped
    posture and turns one on only where a test says so.
    """
    return ProviderConfig(
        version=1,
        providers={
            provider_id: ProviderConfigEntry(
                provider_id=provider_id,
                enabled=provider_id in enabled,
                reserved=provider_id in reserved,
            )
            for provider_id in sorted(PROVIDERS)
        },
    )


def a_tool_workspace(root: pathlib.Path, workspace_id: str) -> ToolWorkspace:
    return ToolWorkspace(workspace_id=workspace_id, root=str(root))


def an_actor(actor_id: str = "operator-li") -> Actor:
    return Actor(id=actor_id, type=ActorType.HUMAN)


def a_read_only_target(identifier: str = "repo") -> TargetRef:
    return TargetRef(kind=TargetKind.REPOSITORY, identifier=identifier)


def a_git_identity() -> ToolIdentity:
    return ToolIdentity(
        tool_id=GIT_TOOL_ID,
        tool_version=GIT_TOOL_VERSION,
        adapter_family=AdapterFamily.GIT,
    )


def read_level() -> PermissionLevel:
    return PermissionLevel.READ
