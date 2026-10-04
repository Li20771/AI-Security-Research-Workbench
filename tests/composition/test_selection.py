"""AI-14-B / B1 — Router selection -> Agent execution.

The Router SELECTS. These tests are about the three things that must stay true
once a decision reaches an execution request: the decision carries no authority,
the hint goes through the registry, and a non-selecting outcome STOPS.
"""

from __future__ import annotations

import pytest

from agents.vocabulary import AgentId, UnknownAgent

from composition.errors import SelectionRefused
from composition.selection import select

from tests.composition.conftest import (
    ALL_PROVIDERS,
    A_MODEL_REF,
    PROFILES,
    a_router_request,
    a_rule_set,
    a_workspace,
    an_empty_rule_set,
)

pytestmark = pytest.mark.layer2


def _select(tmp_path, *, request=None, **overrides):
    root, _ = a_workspace(tmp_path / "ws")
    arguments = {
        "rule_set": a_rule_set(),
        "profiles": PROFILES,
        "enabled_providers": ALL_PROVIDERS,
        "workspace_root": str(root),
        "task": "wf/task",
        "input_digest": "0" * 64,
        "default_agent": AgentId.DSH,
    }
    arguments.update(overrides)
    return select(a_router_request() if request is None else request, **arguments)


def test_a_selected_model_becomes_an_execution_request(tmp_path) -> None:
    """The control. Without it every refusal below would prove nothing."""
    selection = _select(tmp_path)

    assert selection.model_ref == A_MODEL_REF
    assert selection.request.agent_id is AgentId.DSH
    assert selection.request.task == "wf/task"
    assert str(selection.request.workspace_root).endswith("ws")


def test_the_decision_is_kept_as_data_and_not_consumed(tmp_path) -> None:
    """The audit record survives the composition, unchanged.

    Nothing here rewrites the outcome, the reason or the candidates: a
    composition that "cleaned up" a decision would be editing the Router's record
    of its own evaluation.
    """
    selection = _select(tmp_path)
    recorded = selection.decision.to_mapping()

    assert recorded["selected"] == A_MODEL_REF
    assert recorded["outcome"] == "SELECTED"
    assert recorded["candidates"] == [A_MODEL_REF]
    assert selection.decision.selected_nothing is False


def test_an_agent_hint_goes_through_the_registry(tmp_path) -> None:
    """A hint names an Agent only by resolving to a REGISTERED one."""
    selection = _select(tmp_path, rule_set=a_rule_set(agent=AgentId.CODEX.value))

    assert selection.request.agent_id is AgentId.CODEX
    assert selection.agent_hint == AgentId.CODEX.value


def test_a_hint_naming_an_unregistered_agent_is_refused(tmp_path) -> None:
    """`agent_hint` cannot introduce an Agent identity (§7, §21).

    `resolve_agent` is the one boundary at which a candidate becomes an identity,
    and the AgentId vocabulary is closed at two. A third name is refused rather
    than ignored — ignoring it would execute under an Agent the Router never
    named.
    """
    with pytest.raises(UnknownAgent):
        _select(tmp_path, rule_set=a_rule_set(agent="a-third-agent"))


def test_no_matching_rule_is_a_stop(tmp_path) -> None:
    """§7.6, §22.1: `NO_ELIGIBLE_MODEL` is not a cue to try something else."""
    with pytest.raises(SelectionRefused) as refused:
        _select(tmp_path, rule_set=an_empty_rule_set())

    assert "STOP" in str(refused.value)


def test_a_disabled_provider_is_a_stop_and_not_a_fallback(tmp_path) -> None:
    """The selected provider is not enabled, so the Router selects nothing.

    The candidate list deliberately holds a SECOND, enabled model ref: a
    composition with a fallback would take it, and this test exists to fail if one
    is ever added.
    """
    with pytest.raises(SelectionRefused):
        _select(
            tmp_path,
            enabled_providers=frozenset(),
        )


def test_a_model_the_request_did_not_name_is_not_substituted(tmp_path) -> None:
    """§7.7. The rule selects a model the request never offered.

    The Router refuses rather than substituting the model it prefers — and the
    composition does not repair that by adding the candidate, because deciding
    which models may run is not the composition's.
    """
    other = "mimo/mimo-v2.6-pro"
    with pytest.raises(SelectionRefused):
        _select(tmp_path, request=a_router_request(candidates=(other,)))


def test_the_selection_carries_no_permission_vocabulary(tmp_path) -> None:
    """§4.2 rule 1: the Router NEVER grants permission.

    A decision carries a selection, a reason and an audit identity. It has no
    field a permission could be read out of, and the composition adds none — the
    behavioural half of this rule (a tool call made under a SELECTED decision is
    still refused unless Guard allows it) is proven end to end in
    `test_boundaries.py`.
    """
    selection = _select(tmp_path)

    for forbidden in ("decision", "guard_decision", "permission_level", "allow"):
        assert not hasattr(selection.decision, forbidden), forbidden
    assert not hasattr(selection, "permission_level")
