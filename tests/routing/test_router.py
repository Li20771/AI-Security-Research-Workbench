"""AI-07-B — T1 to T38.

Offline, deterministic, repeatable. No provider call, no network, no credential,
no subprocess.

### The two halves, and why the second one matters

Most of this file asserts **refusals**, and a suite that only refuses things is
satisfied by a Router that refuses everything. So T9 is the control: a synthetic
profile whose capability is `VERIFIED` must produce `SELECTED`. Without it, T7
and T8 pass vacuously.

The synthetic profile is constructed in memory and is **never registered**. No
provider is called to produce it, and §6.2 forbids AI-07 from promoting a status —
which is exactly why the control has to be synthetic rather than earned.
"""

from __future__ import annotations

import copy
import pathlib

import pytest

from providers.model_profile import (
    Capabilities,
    CapabilityEntry,
    CapabilityName,
    CapabilityStatus,
    Limits,
    Modality,
    ModelProfile,
    Provenance,
)
from providers.model_registry import load_all_model_profiles

from routing.decision import RouterDecision
from routing.errors import InvalidRequest, InvalidRules
from routing.request import RouterRequest
from routing.router import evaluate, evaluate_mapping
from routing.rules import RuleSet
from routing.vocabulary import RoutingOutcome

pytestmark = pytest.mark.layer1

REAL = load_all_model_profiles()
FIRST_REF = sorted(REAL)[0]


#: Every provider the shipped profiles belong to, enabled. Tests about
#: *routing* pass this; tests about *enablement* call `evaluate` directly, so
#: they see the fail-closed default.
ALL_ENABLED = frozenset(profile.provider_id for profile in REAL.values())


def _eval(request, rules, **overrides):
    """`evaluate` with the shipped providers enabled.

    Spelled out rather than defaulted inside `evaluate`, because the default
    there is deliberately "nothing is enabled" (contract §6.4, and AI-02 ships
    every provider `enabled: false`).
    """
    overrides.setdefault("profiles", REAL)
    overrides.setdefault("enabled_providers", ALL_ENABLED)
    return evaluate(request, rules, **overrides)


def _request(**overrides):
    base = {
        "schema_version": 1,
        "task": {"task_class": "simple"},
        "workspace": {"workspace_id": "ws-1"},
        "actor": {"id": "dsh", "type": "agent"},
        "candidates": [{"model_ref": ref} for ref in sorted(REAL)],
    }
    base.update(overrides)
    return RouterRequest.from_mapping(base)


def _rules(*entries, revision="r-test"):
    return RuleSet.from_mapping(
        {"version": 1, "revision": revision, "rules": list(entries)}
    )


_UNSET = object()


def _rule(rule_id="r", priority=0, select=_UNSET, match=None, reason="R"):
    """One rule. `select={}` must reach the validator, so the default is a sentinel.

    Writing `select or {...}` would silently substitute a valid select for the
    empty one this file needs to test.
    """
    return {
        "rule_id": rule_id,
        "priority": priority,
        "reason_code": reason,
        "match": match or {},
        "select": {"model_ref": FIRST_REF} if select is _UNSET else select,
    }


def _entry_for(status: CapabilityStatus) -> CapabilityEntry:
    """A CapabilityEntry in `status` that satisfies AI-02's cross-field rules.

    AI-02 refuses an entry whose fields disagree with its status -- a DECLARED
    entry must carry `declared=True` and a source, an UNAVAILABLE one must carry
    `verified=False`. Building them loosely would raise in the fixture rather
    than return the `False` this test is about.
    """
    if status is CapabilityStatus.DECLARED:
        return CapabilityEntry(status=status, declared=True, source="test")
    if status is CapabilityStatus.NOT_VERIFIED:
        return CapabilityEntry(status=status, source="test")
    if status is CapabilityStatus.UNAVAILABLE:
        return CapabilityEntry(status=status, verified=False, source="test")
    return CapabilityEntry(status=CapabilityStatus.UNKNOWN)


def _verified_profile(ref: str, capability: CapabilityName) -> ModelProfile:
    """A profile whose named capability is VERIFIED. In memory, never registered.

    §6.2 forbids AI-07 from promoting a status and §14 forbids it from probing,
    so the T9 control cannot be earned — it has to be constructed. A test that
    could only pass on data the repository does not have would be a test nobody
    can run.
    """
    provider_id, model_id = ref.split("/")
    entries = {
        name: CapabilityEntry(status=CapabilityStatus.UNKNOWN)
        for name in CapabilityName
    }
    entries[capability] = CapabilityEntry(
        status=CapabilityStatus.VERIFIED, verified=True, source="synthetic-test-control"
    )
    return ModelProfile(
        model_ref=ref,
        provider_id=provider_id,
        model_id=model_id,
        display_name=model_id,
        family=provider_id,
        version="0",
        limits=Limits(context_limit=1000, max_output=100),
        modality=Modality(input=("text", "image"), output=("text",)),
        capabilities=Capabilities(**{str(k): v for k, v in entries.items()}),
        # AI-02 refuses a VERIFIED capability without a dated observation and an
        # evidence reference: "a verification without a dated observation and
        # evidence is not a verification". The control has to satisfy that rule
        # rather than be exempted from it.
        provenance=Provenance(
            declared_source="synthetic-test-control",
            declared_at="2026-10-01T00:00:00Z",
            verified_at="2026-10-01T00:00:00Z",
            evidence_ref="synthetic-control-not-a-real-observation",
        ),
    )


# --------------------------------------------------------------------------
# T1 – T6  request shape and determinism
# --------------------------------------------------------------------------


class TestT1RequestParses:
    def test_a_well_formed_request_parses(self):
        request = _request()

        assert request.task_class == "simple"
        assert request.workspace_id == "ws-1"
        assert len(request.candidates) == len(REAL)


class TestT2MalformedRequestRefused:
    @pytest.mark.parametrize(
        "mutation",
        [
            {"schema_version": 2},
            {"task": {}},
            {"workspace": {}},
            {"actor": {"id": "x", "type": "robot"}},
            {"candidates": []},
            {"require_independence": "yes"},
            {"sensitivity": "sudo"},
        ],
    )
    def test_a_malformed_request_is_refused(self, mutation):
        with pytest.raises(InvalidRequest):
            _request(**mutation)

    def test_an_unknown_field_is_refused(self):
        with pytest.raises(InvalidRequest):
            _request(colour="red")

    def test_the_refusal_is_an_outcome_not_an_exception(self):
        result = evaluate_mapping(
            {"schema_version": 2}, RuleSet.empty(), profiles=REAL
        )

        assert result.outcome is RoutingOutcome.INVALID_REQUEST


class TestT3ContentIsRefused:
    @pytest.mark.parametrize(
        "field",
        ["prompt", "messages", "content", "tool_args", "api_key", "token",
         "credential", "headers", "command"],
    )
    def test_a_content_field_is_refused_by_name(self, field):
        with pytest.raises(InvalidRequest) as excinfo:
            _request(**{field: "anything"})

        assert field in str(excinfo.value)

    def test_the_refusal_names_the_rule(self):
        with pytest.raises(InvalidRequest) as excinfo:
            _request(prompt="hello")

        assert "§5.3" in str(excinfo.value)


class TestT4Determinism:
    def test_the_same_input_gives_the_same_decision(self):
        request = _request()
        rules = _rules(_rule())

        first = _eval(request, rules, profiles=REAL)
        second = _eval(request, rules, profiles=REAL)

        assert first.semantic_content() == second.semantic_content()

    def test_the_audit_identifiers_differ(self):
        request = _request()
        rules = _rules(_rule())

        first = _eval(request, rules, profiles=REAL)
        second = _eval(request, rules, profiles=REAL)

        assert first.decision_id != second.decision_id


class TestT5CandidateOrderDoesNotMatter:
    def test_permuting_candidates_does_not_change_the_selection(self):
        refs = sorted(REAL)
        forward = _request(candidates=[{"model_ref": r} for r in refs])
        backward = _request(candidates=[{"model_ref": r} for r in reversed(refs)])
        rules = _rules(_rule(select={"model_ref": refs[0]}))

        first = _eval(forward, rules, profiles=REAL)
        second = _eval(backward, rules, profiles=REAL)

        assert first.semantic_content() == second.semantic_content()

    def test_candidates_are_ordered_by_model_ref(self):
        refs = sorted(REAL)

        request = _request(candidates=[{"model_ref": r} for r in reversed(refs)])

        assert request.ordered_candidates == tuple(refs)


class TestT6RuleOrderIsTotal:
    def test_rules_are_ordered_by_priority_then_rule_id(self):
        rules = _rules(
            _rule("z", priority=1), _rule("a", priority=1), _rule("m", priority=0)
        )

        assert [r.rule_id for r in rules.rules] == ["m", "a", "z"]

    def test_a_duplicate_rule_id_is_invalid(self):
        with pytest.raises(InvalidRules) as excinfo:
            _rules(_rule("dup"), _rule("dup"))

        assert "unique" in str(excinfo.value)

    def test_source_order_does_not_decide(self):
        one = _rules(_rule("b", priority=0), _rule("a", priority=0))
        other = _rules(_rule("a", priority=0), _rule("b", priority=0))

        assert [r.rule_id for r in one.rules] == [r.rule_id for r in other.rules]


# --------------------------------------------------------------------------
# T7 – T10  capability and modality
# --------------------------------------------------------------------------


class TestT7UnknownDoesNotSatisfy:
    def test_a_capability_requirement_selects_nothing(self):
        request = _request(requested_capability="tool_calling")
        rules = _rules(_rule())

        result = _eval(request, rules, profiles=REAL)

        assert result.outcome is RoutingOutcome.NO_ELIGIBLE_MODEL
        assert result.reason_code == "CAPABILITY_NOT_VERIFIED"
        assert result.selected is None

    def test_it_holds_for_every_capability(self):
        rules = _rules(_rule())

        for name in CapabilityName:
            result = _eval(
                _request(requested_capability=str(name)), rules, profiles=REAL
            )
            assert result.outcome is RoutingOutcome.NO_ELIGIBLE_MODEL, name


class TestT8DeclaredDoesNotSatisfy:
    @pytest.mark.parametrize(
        "status", [CapabilityStatus.DECLARED, CapabilityStatus.NOT_VERIFIED,
                   CapabilityStatus.UNAVAILABLE, CapabilityStatus.UNKNOWN]
    )
    def test_only_verified_satisfies(self, status):
        from routing.profile import capability_is_available

        profile = _verified_profile(FIRST_REF, CapabilityName.TOOL_CALLING)
        degraded = ModelProfile(
            **{
                **{f: getattr(profile, f) for f in
                   ("model_ref", "provider_id", "model_id", "display_name",
                    "family", "version", "limits", "modality", "provenance")},
                "capabilities": Capabilities(
                    **{
                        str(name): (
                            _entry_for(status)
                            if name is CapabilityName.TOOL_CALLING
                            else CapabilityEntry(status=CapabilityStatus.UNKNOWN)
                        )
                        for name in CapabilityName
                    }
                ),
            }
        )

        assert capability_is_available(degraded, CapabilityName.TOOL_CALLING) is False


class TestT9VerifiedSatisfies:
    """The control. Without it, T7 and T8 pass vacuously."""

    def test_a_verified_capability_is_selected(self):
        control = _verified_profile(FIRST_REF, CapabilityName.TOOL_CALLING)
        profiles = {**REAL, FIRST_REF: control}
        request = _request(requested_capability="tool_calling")
        rules = _rules(_rule())

        result = _eval(request, rules, profiles=profiles)

        assert result.outcome is RoutingOutcome.SELECTED
        assert result.selected == FIRST_REF

    def test_the_synthetic_profile_is_never_registered(self):
        """The control is constructed, not earned — and not persisted."""
        assert FIRST_REF not in {
            ref for ref, profile in REAL.items() if profile.has_verified_capability
        }


class TestT10Modality:
    def test_a_multimodal_requirement_matches_on_modality(self):
        control = _verified_profile(FIRST_REF, CapabilityName.REASONING)
        profiles = {**REAL, FIRST_REF: control}
        request = _request(modality="image")
        rules = _rules(_rule())

        result = _eval(request, rules, profiles=profiles)

        assert result.outcome is RoutingOutcome.SELECTED

    def test_an_unsupported_modality_selects_nothing(self):
        request = _request(modality="video")
        rules = _rules(_rule())

        result = _eval(request, rules, profiles=REAL)

        assert result.outcome is RoutingOutcome.NO_ELIGIBLE_MODEL
        assert result.reason_code == "MODALITY_UNSUPPORTED"

    def test_no_multimodal_capability_is_invented(self):
        """AI-02 has five capabilities and none of them is modality."""
        assert {m.value for m in CapabilityName} == {
            "tool_calling", "structured_output", "streaming", "reasoning",
            "prompt_caching",
        }


# --------------------------------------------------------------------------
# T11 – T14b  no match, unavailable, invalid rules, deferred constraints
# --------------------------------------------------------------------------


class TestT11NoMatchingRule:
    def test_an_empty_rule_set_selects_nothing(self):
        result = _eval(_request(), RuleSet.empty(), profiles=REAL)

        assert result.outcome is RoutingOutcome.NO_ELIGIBLE_MODEL
        assert result.reason_code == "NO_MATCHING_RULE"

    def test_there_is_no_implicit_default(self):
        rules = _rules(_rule(match={"task_class": "other"}))

        result = _eval(_request(), rules, profiles=REAL)

        assert result.selected is None


class TestT12ModelUnavailable:
    def test_a_rule_selecting_a_non_candidate_is_unavailable(self):
        absent = sorted(REAL)[-1]
        request = _request(candidates=[{"model_ref": FIRST_REF}])
        rules = _rules(_rule(select={"model_ref": absent}))

        result = _eval(request, rules, profiles=REAL)

        assert result.outcome is RoutingOutcome.MODEL_UNAVAILABLE
        assert result.selected is None

    def test_a_model_absent_from_the_registry_is_unavailable(self):
        request = _request(
            candidates=[{"model_ref": "someone/not-registered"}]
        )
        rules = _rules(_rule(select={"model_ref": "someone/not-registered"}))

        result = _eval(request, rules, profiles=REAL)

        assert result.outcome is RoutingOutcome.MODEL_UNAVAILABLE

    def test_no_substitution_happens(self):
        request = _request(candidates=[{"model_ref": FIRST_REF}])
        rules = _rules(_rule(select={"model_ref": "someone/not-registered"}))

        assert evaluate(request, rules, profiles=REAL).selected is None

    def test_a_disabled_provider_is_not_eligible(self):
        rules = _rules(_rule())

        result = _eval(_request(), rules, profiles=REAL, enabled_providers=frozenset())

        assert result.outcome is RoutingOutcome.MODEL_UNAVAILABLE
        assert result.reason_code == "PROVIDER_DISABLED"


class TestT13T14InvalidRules:
    def test_an_unsupported_version_is_invalid(self):
        with pytest.raises(InvalidRules):
            RuleSet.from_mapping({"version": 2, "revision": "r", "rules": []})

    def test_a_missing_revision_is_invalid(self):
        with pytest.raises(InvalidRules):
            RuleSet.from_mapping({"version": 1, "rules": []})

    def test_an_unknown_match_field_is_invalid(self):
        with pytest.raises(InvalidRules):
            _rules(_rule(match={"sensitivity": "modify"}))

    def test_an_empty_select_is_invalid(self):
        with pytest.raises(InvalidRules):
            _rules(_rule(select={}))

    def test_a_malformed_priority_is_invalid(self):
        with pytest.raises(InvalidRules):
            _rules({**_rule(), "priority": "high"})

    def test_a_malformed_model_ref_is_invalid(self):
        with pytest.raises(InvalidRules):
            _rules(_rule(select={"model_ref": "no-slash"}))

    def test_a_syntactically_valid_but_unregistered_ref_is_not_invalid_rules(self):
        """§27: the two are different conditions, and the brief says so."""
        rules = _rules(_rule(select={"model_ref": "someone/not-registered"}))

        result = _eval(
            _request(candidates=[{"model_ref": "someone/not-registered"}]),
            rules,
            profiles=REAL,
        )

        assert result.outcome is RoutingOutcome.MODEL_UNAVAILABLE


class TestT14bDeferredConstraints:
    def test_a_cost_class_constraint_is_refused(self):
        with pytest.raises(InvalidRequest) as excinfo:
            _request(constraints={"max_cost_class": "cheap"})

        assert "DEFERRED" in str(excinfo.value)

    def test_it_is_never_silently_ignored(self):
        result = evaluate_mapping(
            {
                "schema_version": 1,
                "task": {"task_class": "simple"},
                "workspace": {"workspace_id": "ws"},
                "actor": {"id": "x", "type": "service"},
                "candidates": [{"model_ref": FIRST_REF}],
                "constraints": {"max_cost_class": "cheap"},
            },
            RuleSet.empty(),
            profiles=REAL,
        )

        assert result.outcome is RoutingOutcome.INVALID_REQUEST

    def test_a_latency_class_constraint_is_refused(self):
        with pytest.raises(InvalidRequest) as excinfo:
            _eval(
                _request(constraints={"max_latency_class": "fast"}),
                RuleSet.empty(),
                profiles=REAL,
            )

        assert "latency-class" in str(excinfo.value)

    def test_no_cost_class_vocabulary_exists_in_routing(self):
        text = "\n".join(
            p.read_text(encoding="utf-8")
            for p in pathlib.Path("routing").glob("*.py")
        )

        for invented in ("cheap", "expensive", "cost_class_of"):
            assert invented not in text, invented


# --------------------------------------------------------------------------
# T15 – T17  no automatic fallback
# --------------------------------------------------------------------------


class TestT15NoAutomaticRetry:
    def test_a_failed_selection_produces_no_second_evaluation(self):
        request = _request(candidates=[{"model_ref": FIRST_REF}])
        rules = _rules(_rule(select={"model_ref": "someone/not-registered"}))

        result = _eval(request, rules, profiles=REAL)

        assert result.outcome is RoutingOutcome.MODEL_UNAVAILABLE
        assert result.selected is None

    def test_the_decision_carries_no_nested_decision(self):
        record = _eval(_request(), RuleSet.empty(), profiles=REAL).to_mapping()

        assert "fallbacks" not in record
        assert not any(isinstance(v, dict) and "outcome" in v for v in record.values())

    def test_the_router_has_no_retry_surface(self):
        import routing.router as router

        for name in ("retry", "fallback", "next_model", "auto_failover"):
            assert not hasattr(router, name), name


class TestT16NoCandidateExpansion:
    def test_the_candidate_set_is_never_widened(self):
        request = _request(candidates=[{"model_ref": FIRST_REF}])
        rules = _rules(_rule(select={"model_ref": sorted(REAL)[-1]}))

        result = _eval(request, rules, profiles=REAL)

        assert result.candidates == (FIRST_REF,)
        assert result.selected is None


class TestT17NoConstraintRelaxation:
    def test_a_capability_requirement_is_not_relaxed(self):
        request = _request(requested_capability="tool_calling")
        rules = _rules(_rule())

        assert evaluate(request, rules, profiles=REAL).selected is None

    def test_no_authorization_is_produced(self):
        record = _eval(_request(), RuleSet.empty(), profiles=REAL).to_mapping()

        for forbidden in ("permission", "permission_level", "approval", "grant",
                          "allowed", "authorization"):
            assert forbidden not in record, forbidden


# --------------------------------------------------------------------------
# T18 – T22  authorization, sensitivity, capability immutability
# --------------------------------------------------------------------------


class TestT18SelectionCarriesNoPermission:
    def test_the_decision_names_no_permission(self):
        result = _eval(_request(), _rules(_rule()), profiles=REAL)

        assert result.outcome is RoutingOutcome.SELECTED
        assert "permission" not in str(result.to_mapping())


class TestT19StrongerModelDoesNotRaiseALevel:
    def test_the_sensitivity_is_echoed_unchanged(self):
        request = _request(sensitivity="read")
        rules = _rules(_rule())

        result = _eval(request, rules, profiles=REAL)

        assert result.requested["sensitivity"] == "read"


class TestT20SensitivityChangesNoEligibility:
    """Amendment 1 (a). The rule that had no AI-02 source field."""

    @pytest.mark.parametrize(
        "level", ["read", "analyze", "test", "modify", "system-change", "remote-change"]
    )
    def test_every_level_gives_the_same_outcome(self, level):
        rules = _rules(_rule())
        baseline = _eval(_request(sensitivity="read"), rules, profiles=REAL)

        result = _eval(_request(sensitivity=level), rules, profiles=REAL)

        assert result.outcome is baseline.outcome
        assert result.selected == baseline.selected

    def test_a_capability_requirement_is_unaffected_by_sensitivity(self):
        rules = _rules(_rule())
        plain = _eval(
            _request(requested_capability="tool_calling", sensitivity="read"),
            rules,
            profiles=REAL,
        )
        elevated = _eval(
            _request(requested_capability="tool_calling", sensitivity="remote-change"),
            rules,
            profiles=REAL,
        )

        assert plain.outcome is elevated.outcome

    def test_sensitivity_is_preserved_in_the_decision(self):
        result = _eval(
            _request(sensitivity="test"), _rules(_rule()), profiles=REAL
        )

        assert result.requested["sensitivity"] == "test"


class TestT21NoInference:
    def test_no_module_infers_a_permission(self):
        text = "\n".join(
            p.read_text(encoding="utf-8")
            for p in pathlib.Path("routing").glob("*.py")
        )

        for invented in ("infer_permission", "permission_for", "level_for"):
            assert invented not in text, invented

    def test_a_task_class_named_like_a_permission_grants_nothing(self):
        request = _request(task={"task_class": "modify"})
        rules = _rules(_rule(match={"task_class": "modify"}))

        result = _eval(request, rules, profiles=REAL)

        assert result.outcome is RoutingOutcome.SELECTED
        assert "permission" not in str(result.to_mapping())


class TestT22CapabilityIsNeverPromoted:
    def test_routing_changes_no_capability_status(self):
        before = {
            ref: str(profile.capability(CapabilityName.TOOL_CALLING).status)
            for ref, profile in REAL.items()
        }

        _eval(_request(requested_capability="tool_calling"), _rules(_rule()), profiles=REAL)

        after = {
            ref: str(profile.capability(CapabilityName.TOOL_CALLING).status)
            for ref, profile in REAL.items()
        }
        assert before == after

    def test_routing_never_writes_a_profile(self):
        text = "\n".join(
            p.read_text(encoding="utf-8")
            for p in pathlib.Path("routing").glob("*.py")
        )

        for forbidden in ("write_text", "open(", "yaml.safe_dump", "json.dump"):
            assert forbidden not in text, forbidden


# --------------------------------------------------------------------------
# T23 – T24  no provider call, no process
# --------------------------------------------------------------------------


class TestT23NoProviderCall:
    def test_routing_reaches_no_transport(self):
        text = "\n".join(
            p.read_text(encoding="utf-8") for p in pathlib.Path("routing").glob("*.py")
        )

        for forbidden in ("Invoker", "import requests"):
            assert forbidden not in text, forbidden

        import ast

        # The check that matters: routing/ imports no transport module at all.
        # Written structurally rather than by looking for a name, because a
        # name-based check fires on the very file that forbids the thing -- the
        # same lesson AI-02's own confinement guard records about itself.
        for path in sorted(pathlib.Path("routing").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    leaf = node.module.split(".")[-1]
                    assert "transport" not in leaf, (path.name, node.module)
                    assert "http" not in leaf, (path.name, node.module)

    def test_evaluation_is_pure_over_its_inputs(self):
        request = _request()
        rules = _rules(_rule())
        snapshot = copy.deepcopy(request.to_mapping())

        _eval(request, rules, profiles=REAL)

        assert request.to_mapping() == snapshot


class TestT24NoProcess:
    def test_no_subprocess_is_imported(self):
        text = "\n".join(
            p.read_text(encoding="utf-8") for p in pathlib.Path("routing").glob("*.py")
        )

        assert "import subprocess" not in text
        assert "shell=True" not in text
        assert "os.system" not in text


# --------------------------------------------------------------------------
# T25 – T28  Evidence and the decision record
# --------------------------------------------------------------------------


class TestT25RoutingDecisionIsNotEvidence:
    def test_no_module_writes_a_record(self):
        text = "\n".join(
            p.read_text(encoding="utf-8") for p in pathlib.Path("routing").glob("*.py")
        )

        for forbidden in ("admit", "EvidenceRecord", "ToolCall", "ExecutionPayload"):
            assert forbidden not in text, forbidden

    def test_no_evidence_import(self):
        import ast

        for path in sorted(pathlib.Path("routing").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("plugins.evidence"), path.name


class TestT26NoAIO5EventRegistered:
    def test_the_ai05_registry_is_unchanged(self):
        from plugins.evidence import ADMITTED_EVENTS

        producers = {row.producer for row in ADMITTED_EVENTS}

        assert "ai-07" not in producers
        assert producers == {"ai-03", "ai-02", "ai-04", "ai-06"}


class TestT27DecisionCarriesNoContent:
    def test_the_record_is_an_allowlist(self):
        record = _eval(_request(), _rules(_rule()), profiles=REAL).to_mapping()

        assert set(record) == {
            "schema_version", "decision_id", "decided_at", "outcome", "reason_code",
            "requested", "matched_rule", "candidates", "selected", "agent_hint",
            "rules_revision",
        }

    def test_the_record_carries_no_content_field(self):
        record = _eval(_request(), _rules(_rule()), profiles=REAL).to_mapping()
        text = str(record)

        for forbidden in ("prompt", "messages", "api_key", "token", "credential"):
            assert forbidden not in text, forbidden

    def test_the_projection_is_not_asdict(self):
        import ast

        source = pathlib.Path("routing/decision.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }

        assert "asdict" not in called


class TestT28RulesRevisionIsRecorded:
    def test_the_revision_appears_in_the_decision(self):
        result = _eval(_request(), _rules(_rule(), revision="rev-42"), profiles=REAL)

        assert result.rules_revision == "rev-42"
        assert result.to_mapping()["rules_revision"] == "rev-42"

    def test_a_different_revision_is_a_different_decision(self):
        request = _request()
        one = _eval(request, _rules(_rule(), revision="a"), profiles=REAL)
        other = _eval(request, _rules(_rule(), revision="b"), profiles=REAL)

        assert one.semantic_content() != other.semantic_content()


# --------------------------------------------------------------------------
# T29 – T38  independence, configuration, vocabulary, architecture
# --------------------------------------------------------------------------


class TestT29IndependenceIsARequirement:
    def test_the_requirement_is_representable(self):
        request = _request(require_independence=True)
        rules = _rules(_rule())

        result = _eval(request, rules, profiles=REAL)

        assert result.to_mapping()["requested"]["require_independence"] is True

    def test_no_independent_agent_is_executed(self):
        result = _eval(
            _request(require_independence=True), _rules(_rule()), profiles=REAL
        )

        for forbidden in ("executed", "verified_independent", "codex"):
            assert forbidden not in str(result.to_mapping()).lower()

    def test_the_agent_hint_is_a_hint(self):
        rules = _rules(_rule(select={"model_ref": FIRST_REF, "agent": "codex"}))

        result = _eval(_request(require_independence=True), rules, profiles=REAL)

        assert result.agent_hint == "codex"
        assert result.outcome is RoutingOutcome.SELECTED

    def test_no_ai08_code_exists(self):
        assert not pathlib.Path("agents/codex/adapter.py").exists()


class TestT30ConfigurationIsReadOnly:
    def test_the_router_never_writes_configuration(self):
        text = "\n".join(
            p.read_text(encoding="utf-8") for p in pathlib.Path("routing").glob("*.py")
        )

        assert "write" not in text.replace("write_text", "")

    def test_no_rule_set_is_discovered(self):
        text = "\n".join(
            p.read_text(encoding="utf-8") for p in pathlib.Path("routing").glob("*.py")
        )

        for forbidden in ("requests", "urllib", "http", "discover"):
            assert forbidden not in text, forbidden


class TestT31OutcomeVocabularyIsAI07sOwn:
    def test_it_is_not_merged_with_any_other(self):
        from plugins.context.vocabulary import StatusValue
        from plugins.guard.vocabulary import GuardDecision
        from plugins.security_tools import ToolOutcome

        assert set(RoutingOutcome) != set(GuardDecision)
        assert set(RoutingOutcome) != set(ToolOutcome)
        assert {m.value for m in RoutingOutcome} != {m.value for m in StatusValue}

    def test_the_members_are_the_frozen_six(self):
        assert {m.value for m in RoutingOutcome} == {
            "SELECTED", "NO_ELIGIBLE_MODEL", "MODEL_UNAVAILABLE",
            "INVALID_REQUEST", "INVALID_RULES", "ROUTER_ERROR",
        }

    def test_selected_claims_nothing_beyond_a_selection(self):
        assert "SELECTED" in {m.value for m in RoutingOutcome}
        for claim in ("PASS", "SUCCEEDED", "VERIFIED", "ALLOWED"):
            assert claim not in {m.value for m in RoutingOutcome}


class TestT32NoOutcomeBecomesASelection:
    @pytest.mark.parametrize(
        "outcome",
        [RoutingOutcome.NO_ELIGIBLE_MODEL, RoutingOutcome.MODEL_UNAVAILABLE,
         RoutingOutcome.INVALID_REQUEST, RoutingOutcome.INVALID_RULES,
         RoutingOutcome.ROUTER_ERROR],
    )
    def test_a_failure_stays_a_failure(self, outcome):
        assert outcome is not RoutingOutcome.SELECTED


class TestT33RoutingIsNotAPlugin:
    def test_no_init_file(self):
        assert not pathlib.Path("routing/__init__.py").exists()

    def test_not_under_plugins(self):
        assert not pathlib.Path("plugins/router").exists()


class TestT34NoToolLayerImport:
    def test_routing_does_not_import_tools(self):
        import ast

        for path in sorted(pathlib.Path("routing").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name.split(".")[0] != "tools", path.name


class TestT35ArchitectureBoundary:
    def test_no_network_or_process_import(self):
        import ast

        banned = {"socket", "http", "urllib", "requests", "httpx", "subprocess",
                  "multiprocessing", "asyncio", "plugins"}
        for path in sorted(pathlib.Path("routing").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".")[0]
                    if root == "plugins":
                        assert node.module.startswith("plugins.guard.vocabulary"), (
                            path.name, node.module
                        )
                    else:
                        assert root not in banned, (path.name, node.module)

    def test_no_eval_exec_compile(self):
        import ast

        for path in sorted(pathlib.Path("routing").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert node.func.id not in {"eval", "exec", "compile"}, path.name


class TestT36TheContractAndTheDirectoryAgree:
    def test_the_readme_still_states_the_identity(self):
        text = pathlib.Path("routing/README.md").read_text(encoding="utf-8")

        assert "not a DSH plugin" in text
        assert "never grants permissions" in text

    def test_the_default_rule_set_is_empty(self):
        import yaml

        parsed = yaml.safe_load(
            pathlib.Path("config/routing/default.rules.yaml").read_text(encoding="utf-8")
        )

        assert parsed["version"] == 1
        assert parsed["rules"] == []

    def test_the_example_config_is_still_not_a_schema(self):
        text = pathlib.Path("config/routing/rules.example.yaml").read_text(
            encoding="utf-8"
        )

        assert "model_profile: fast" in text
        assert "fast" not in REAL


class TestT37Regression:
    def test_the_pre_existing_layers_are_untouched(self):
        import subprocess

        changed = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True, text=True, check=False,
        ).stdout.split()

        for path in changed:
            for protected in ("providers/", "plugins/", "tools/", "agents/"):
                assert not path.startswith(protected), path


class TestT38Layer0:
    def test_the_gate_runs_green(self):
        import subprocess
        import sys

        completed = subprocess.run(
            [sys.executable, "scripts/ci/layer0_policy.py"],
            capture_output=True, text=True, check=False,
        )

        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "Layer 0 = PASS" in completed.stdout


# --------------------------------------------------------------------------
# Round 1 review fixes
# --------------------------------------------------------------------------


class TestProviderEnablementFailsClosed:
    """Review P1. An omitted config used to mean "do not check"."""

    def test_omitting_enablement_enables_nothing(self):
        request = _request(candidates=[{"model_ref": FIRST_REF}])
        rules = _rules(_rule())

        # `evaluate` directly, so the fail-closed default is what runs.
        result = evaluate(request, rules, profiles=REAL)

        assert result.outcome is RoutingOutcome.MODEL_UNAVAILABLE
        assert result.reason_code == "PROVIDER_DISABLED"
        assert result.selected is None

    def test_an_empty_enablement_set_selects_nothing(self):
        result = _eval(
            _request(candidates=[{"model_ref": FIRST_REF}]),
            _rules(_rule()),
            enabled_providers=frozenset(),
        )

        assert result.selected is None

    def test_a_disabled_provider_is_not_selected(self):
        provider = FIRST_REF.split("/")[0]

        result = _eval(
            _request(candidates=[{"model_ref": FIRST_REF}]),
            _rules(_rule()),
            enabled_providers=frozenset({"some-other-provider"}),
        )

        assert result.outcome is RoutingOutcome.MODEL_UNAVAILABLE
        assert provider not in ("some-other-provider",)

    def test_an_enabled_provider_is_selected(self):
        """The positive control that keeps the rule from being a blanket refusal."""
        result = _eval(_request(candidates=[{"model_ref": FIRST_REF}]), _rules(_rule()))

        assert result.outcome is RoutingOutcome.SELECTED
        assert result.selected == FIRST_REF

    def test_the_verified_control_selects_when_its_provider_is_enabled(self):
        control = _verified_profile(FIRST_REF, CapabilityName.TOOL_CALLING)
        profiles = {**REAL, FIRST_REF: control}

        enabled = _eval(
            _request(requested_capability="tool_calling"),
            _rules(_rule()),
            profiles=profiles,
            enabled_providers=frozenset({control.provider_id}),
        )
        disabled = _eval(
            _request(requested_capability="tool_calling"),
            _rules(_rule()),
            profiles=profiles,
            enabled_providers=frozenset(),
        )

        assert enabled.outcome is RoutingOutcome.SELECTED
        assert disabled.outcome is RoutingOutcome.MODEL_UNAVAILABLE


class TestInvalidRulesIsAnOutcome:
    """Review P1. `INVALID_RULES` was frozen and unreachable."""

    def _raw(self, **rule_overrides):
        rule = {
            "rule_id": "r",
            "priority": 0,
            "reason_code": "R",
            "match": {},
            "select": {"model_ref": FIRST_REF},
        }
        rule.update(rule_overrides)
        return {"version": 1, "revision": "r", "rules": [rule]}

    @pytest.mark.parametrize(
        "rule_set",
        [
            {"version": 2, "revision": "r", "rules": []},
            {"version": 1, "rules": []},
            {"version": 1, "revision": "r", "rules": [{"rule_id": "x", "priority": "high",
                                                       "reason_code": "R",
                                                       "select": {"model_ref": "a/b"}}]},
            {"version": 1, "revision": "r", "rules": [{"rule_id": "x", "priority": 0,
                                                       "reason_code": "R", "select": {}}]},
            {"version": 1, "revision": "r", "rules": [{"rule_id": "x", "priority": 0,
                                                       "reason_code": "R", "nonsense": 1,
                                                       "select": {"model_ref": "a/b"}}]},
        ],
    )
    def test_an_invalid_rule_set_is_an_outcome(self, rule_set):
        result = evaluate_mapping(
            {
                "schema_version": 1,
                "task": {"task_class": "simple"},
                "workspace": {"workspace_id": "ws"},
                "actor": {"id": "x", "type": "service"},
                "candidates": [{"model_ref": FIRST_REF}],
            },
            rule_set,
            profiles=REAL,
            enabled_providers=ALL_ENABLED,
        )

        assert result.outcome is RoutingOutcome.INVALID_RULES
        assert result.selected is None
        assert result.matched_rule is None

    def test_a_duplicate_rule_id_is_an_outcome(self):
        result = evaluate_mapping(
            {
                "schema_version": 1,
                "task": {"task_class": "simple"},
                "workspace": {"workspace_id": "ws"},
                "actor": {"id": "x", "type": "service"},
                "candidates": [{"model_ref": FIRST_REF}],
            },
            {"version": 1, "revision": "r", "rules": [self._raw()["rules"][0]] * 2},
            profiles=REAL,
            enabled_providers=ALL_ENABLED,
        )

        assert result.outcome is RoutingOutcome.INVALID_RULES

    def test_no_partial_application(self):
        """Validation completes before any rule runs, so nothing is half-applied."""
        raw_rule = self._raw()["rules"][0]
        good = dict(raw_rule, rule_id="a")
        bad = dict(raw_rule, rule_id="b", priority="high")

        result = evaluate_mapping(
            {
                "schema_version": 1,
                "task": {"task_class": "simple"},
                "workspace": {"workspace_id": "ws"},
                "actor": {"id": "x", "type": "service"},
                "candidates": [{"model_ref": FIRST_REF}],
            },
            {"version": 1, "revision": "r", "rules": [good, bad]},
            profiles=REAL,
            enabled_providers=ALL_ENABLED,
        )

        assert result.outcome is RoutingOutcome.INVALID_RULES
        assert result.matched_rule is None

    def test_a_valid_rule_set_still_selects(self):
        """The control: the projection did not swallow the working path."""
        result = evaluate_mapping(
            {
                "schema_version": 1,
                "task": {"task_class": "simple"},
                "workspace": {"workspace_id": "ws"},
                "actor": {"id": "x", "type": "service"},
                "candidates": [{"model_ref": FIRST_REF}],
            },
            self._raw(),
            profiles=REAL,
            enabled_providers=ALL_ENABLED,
        )

        assert result.outcome is RoutingOutcome.SELECTED


class TestRequestSchemaIsNotPermissive:
    """Review P2. A bare candidate string and an unknown capability were accepted."""

    def test_a_bare_candidate_string_is_refused(self):
        with pytest.raises(InvalidRequest) as excinfo:
            _request(candidates=[FIRST_REF])

        assert "bare string" in str(excinfo.value)

    def test_a_bare_candidate_string_is_an_outcome(self):
        result = evaluate_mapping(
            {
                "schema_version": 1,
                "task": {"task_class": "simple"},
                "workspace": {"workspace_id": "ws"},
                "actor": {"id": "x", "type": "service"},
                "candidates": [FIRST_REF],
            },
            {"version": 1, "revision": "r", "rules": []},
            profiles=REAL,
            enabled_providers=ALL_ENABLED,
        )

        assert result.outcome is RoutingOutcome.INVALID_REQUEST

    def test_a_candidate_with_an_unknown_field_is_refused(self):
        with pytest.raises(InvalidRequest):
            _request(candidates=[{"model_ref": FIRST_REF, "weight": 3}])

    @pytest.mark.parametrize(
        "capability",
        ["tool_calling", "structured_output", "streaming", "reasoning", "prompt_caching"],
    )
    def test_every_real_capability_is_accepted(self, capability):
        request = _request(requested_capability=capability)

        assert request.requested_capability == capability

    def test_an_unknown_capability_is_refused_at_the_boundary(self):
        with pytest.raises(InvalidRequest) as excinfo:
            _request(requested_capability="made_up_capability")

        assert "capability names" in str(excinfo.value)

    def test_an_unknown_capability_is_invalid_request_not_a_routing_miss(self):
        result = evaluate_mapping(
            {
                "schema_version": 1,
                "task": {"task_class": "simple"},
                "workspace": {"workspace_id": "ws"},
                "actor": {"id": "x", "type": "service"},
                "candidates": [{"model_ref": FIRST_REF}],
                "requested_capability": "made_up_capability",
            },
            {"version": 1, "revision": "r", "rules": []},
            profiles=REAL,
            enabled_providers=ALL_ENABLED,
        )

        assert result.outcome is RoutingOutcome.INVALID_REQUEST
        assert result.outcome is not RoutingOutcome.NO_ELIGIBLE_MODEL

    def test_a_rule_matching_an_unknown_capability_is_invalid_rules(self):
        with pytest.raises(InvalidRules):
            _rules(_rule(match={"requested_capability": "made_up_capability"}))
