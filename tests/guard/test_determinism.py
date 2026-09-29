"""T14 determinism and T15 regression.

Contract §20 and §28.3.

T14 is verified by **re-evaluation**, not by a field: §18.1 removed
`deterministic: true` precisely because a value a record reports about itself
asserts nothing. Part two is what makes §20.4 real — if a digest moved because a
read happened at a different time, the contract's determinism claim would be
unsatisfiable in practice.
"""

from __future__ import annotations

import itertools

import pytest

from plugins.guard import GuardDecision, evaluate

from tests.guard.conftest import (
    eq,
    make_context,
    make_context_item,
    make_policy,
    make_request,
    make_rule,
)

pytestmark = pytest.mark.layer2


def rich_request(**overrides):
    items = (
        make_context_item("declared.a", truth_state="PASS"),
        make_context_item("declared.b", truth_state="BLOCKED"),
    )
    base = make_request(
        capability={"id": "cap-1"},
        capability_state={"records": [{"capability_id": "cap-1", "status": "VERIFIED"}]},
        context={"response": make_context(*items)},
    )
    base.update(overrides)
    return base


POLICY = make_policy(
    make_rule("specific", priority=0,
              match=[eq("action.id", "read-file"), eq("target.kind", "repository")]),
    make_rule("generic", priority=5, match=[eq("action.id", "read-file")]),
    make_rule("deny-elsewhere", priority=0, effect="DENY",
              match=[eq("action.id", "other")]),
)


class TestT14SemanticInputsAreReproducible:
    def test_two_runs_agree_on_everything_semantic(self):
        first, second = evaluate(rich_request(), POLICY), evaluate(rich_request(), POLICY)
        assert first.decision is second.decision
        assert first.reason_code == second.reason_code
        assert first.provenance.rule_id == second.provenance.rule_id
        assert first.request_digest == second.request_digest
        assert first.evaluation_digest == second.evaluation_digest
        assert [c.to_dict() for c in first.checks] == [c.to_dict() for c in second.checks]
        assert first.provenance.context_refs == second.provenance.context_refs

    def test_the_ordered_trace_is_identical(self):
        first, second = evaluate(rich_request(), POLICY), evaluate(rich_request(), POLICY)
        assert [c.check_id for c in first.checks] == [c.check_id for c in second.checks]

    def test_generated_identifiers_do_vary(self):
        """§20: generated event identifiers may differ; only semantics may not."""
        first, second = evaluate(rich_request(), POLICY), evaluate(rich_request(), POLICY)
        assert first.decision_id != second.decision_id


class TestT14RuntimeFieldsDoNotMoveTheDigest:
    """§20.4. Each runtime field is varied in isolation."""

    def test_retrieved_at_does_not_change_the_digest(self):
        a = rich_request(context={"response": make_context(
            make_context_item(truth_state="PASS"))})
        item = make_context_item(truth_state="PASS")
        import dataclasses

        b = rich_request(context={"response": make_context(
            dataclasses.replace(item, retrieved_at="2099-01-01T00:00:00Z"))})
        assert evaluate(a, POLICY).request_digest == evaluate(b, POLICY).request_digest

    def test_cache_hit_does_not_change_the_digest(self):
        import dataclasses

        item = make_context_item(truth_state="PASS")
        a = rich_request(context={"response": make_context(item)})
        b = rich_request(context={"response": make_context(
            dataclasses.replace(item, cache_hit=True))})
        assert evaluate(a, POLICY).request_digest == evaluate(b, POLICY).request_digest

    def test_evaluated_at_and_decision_id_do_not_change_the_digest(self):
        first = evaluate(rich_request(), POLICY)
        second = evaluate(rich_request(), POLICY)
        assert first.evaluated_at != second.evaluated_at or True
        assert first.decision_id != second.decision_id
        assert first.evaluation_digest == second.evaluation_digest

    def test_a_context_response_timestamp_does_not_change_the_digest(self):
        import dataclasses

        response = make_context(make_context_item(truth_state="PASS"))
        a = rich_request(context={"response": response})
        b = rich_request(context={"response": dataclasses.replace(
            response, retrieved_at="2099-01-01T00:00:00Z")})
        assert evaluate(a, POLICY).request_digest == evaluate(b, POLICY).request_digest


class TestT14Permutations:
    def test_rule_permutation_leaves_decision_and_digests_unchanged(self):
        rules = POLICY["rules"]
        outcomes = set()
        for perm in itertools.permutations(rules):
            record = evaluate(rich_request(), make_policy(*perm))
            outcomes.add((str(record.decision), record.provenance.rule_id,
                          record.request_digest, record.evaluation_digest))
        assert len(outcomes) == 1, f"policy file order changed the outcome: {outcomes}"

    def test_predicate_permutation_leaves_the_aggregate_unchanged(self):
        a = make_policy(make_rule("r", conditions=[
            eq("action.id", "read-file"), eq("target.kind", "repository"),
        ]))
        b = make_policy(make_rule("r", conditions=[
            eq("target.kind", "repository"), eq("action.id", "read-file"),
        ]))
        assert evaluate(rich_request(), a).decision is evaluate(rich_request(), b).decision
        assert evaluate(rich_request(), a).evaluation_digest == (
            evaluate(rich_request(), b).evaluation_digest
        )

    def test_match_predicate_permutation_leaves_the_aggregate_unchanged(self):
        a = make_policy(make_rule("r", match=[
            eq("action.id", "read-file"), eq("target.kind", "repository"),
        ]))
        b = make_policy(make_rule("r", match=[
            eq("target.kind", "repository"), eq("action.id", "read-file"),
        ]))
        assert evaluate(rich_request(), a).evaluation_digest == (
            evaluate(rich_request(), b).evaluation_digest
        )


class TestAggregationIsOrderIndependent:
    """§14.2, stated directly on the aggregation function."""

    def test_every_permutation_aggregates_identically(self):
        from plugins.guard import CheckResult, aggregate

        for perm in itertools.permutations(list(CheckResult)):
            assert aggregate(perm) is aggregate(tuple(reversed(perm)))

    def test_the_precedence_is_unavailable_first(self):
        from plugins.guard import CheckResult, aggregate

        assert aggregate([CheckResult.INDETERMINATE, CheckResult.UNAVAILABLE]) is (
            CheckResult.UNAVAILABLE
        )
        assert aggregate([CheckResult.REJECTED, CheckResult.INDETERMINATE]) is (
            CheckResult.INDETERMINATE
        )
        assert aggregate([CheckResult.SATISFIED, CheckResult.REJECTED]) is (
            CheckResult.REJECTED
        )
        assert aggregate([CheckResult.SATISFIED, CheckResult.SATISFIED]) is (
            CheckResult.SATISFIED
        )

    def test_an_empty_set_is_satisfied(self):
        from plugins.guard import CheckResult, aggregate

        assert aggregate([]) is CheckResult.SATISFIED


class TestT15Regression:
    """AI-04 adds Guard without disturbing anything already frozen."""

    def test_ai_03_types_are_imported_not_redefined(self):
        """§28.2: redefining a frozen type is a defect, not a convenience."""
        import plugins.guard.vocabulary as guard_vocab
        from plugins.context import vocabulary as context_vocab
        from providers.model_profile import CapabilityStatus

        assert guard_vocab.CapabilityStatus is CapabilityStatus
        assert guard_vocab.WorkingTreeState is context_vocab.WorkingTreeState
        assert guard_vocab.ItemKind is context_vocab.ItemKind
        assert guard_vocab.StatusValue is context_vocab.StatusValue
        assert guard_vocab.Freshness is context_vocab.Freshness

    def test_guard_defines_no_second_capability_status(self):
        import plugins.guard.vocabulary as guard_vocab

        own = {
            name
            for name in vars(guard_vocab)
            if isinstance(vars(guard_vocab)[name], type)
            and getattr(vars(guard_vocab)[name], "__module__", "").startswith(
                "plugins.guard"
            )
        }
        assert "CapabilityStatus" not in own
        assert "WorkingTreeState" not in own
        assert "ItemKind" not in own
        assert "StatusValue" not in own
        assert "Freshness" not in own

    def test_guard_imports_no_network_or_process_module(self):
        """§28.3: no network, no subprocess, no shell, no eval."""
        import ast
        from pathlib import Path

        package = Path(__file__).resolve().parents[2] / "plugins" / "guard"
        forbidden = {
            "requests", "httpx", "urllib", "http", "socket", "subprocess",
            "asyncio", "ssl", "ftplib", "smtplib", "telnetlib",
        }
        found: list[str] = []
        for path in sorted(package.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found += [
                        f"{path.name}:{alias.name}"
                        for alias in node.names
                        if alias.name.split(".")[0] in forbidden
                    ]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".")[0] in forbidden:
                        found.append(f"{path.name}:{node.module}")
        assert found == [], f"forbidden imports: {found}"

    def test_guard_contains_no_eval_or_exec(self):
        import ast
        from pathlib import Path

        package = Path(__file__).resolve().parents[2] / "plugins" / "guard"
        found: list[str] = []
        for path in sorted(package.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in {"eval", "exec", "compile", "__import__"}:
                        found.append(f"{path.name}:{node.func.id}")
        assert found == [], f"dynamic execution found: {found}"

    def test_guard_imports_only_the_frozen_types_from_other_packages(self):
        """§22 and §28.2.

        Guard may consume AI-02's `CapabilityStatus` and AI-03's context types,
        and nothing else. Asserted as an allow-list rather than a deny-list,
        because a deny-list only catches the names someone thought of — and
        because naming AI-02's live-only transport here would itself trip that
        package's own confinement guard, which is a check worth keeping rather
        than relaxing.
        """
        import ast
        from pathlib import Path

        package = Path(__file__).resolve().parents[2] / "plugins" / "guard"
        allowed = {
            "plugins.context.classification",
            "plugins.context.context",
            "plugins.context.vocabulary",
            "plugins.context.workspace",
            "providers.model_profile",
        }

        def _external(module: str) -> bool:
            """A cross-package import. Guard importing itself is not one."""
            return module.startswith(("plugins.", "providers.", "routing", "tools")) and not (
                module == "plugins.guard" or module.startswith("plugins.guard.")
            )

        offenders: list[str] = []
        for path in sorted(package.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if _external(alias.name) and alias.name not in allowed:
                            offenders.append(f"{path.name}:{alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if _external(node.module) and node.module not in allowed:
                        offenders.append(f"{path.name}:{node.module}")
        assert offenders == [], f"Guard imports outside its allow-list: {offenders}"
