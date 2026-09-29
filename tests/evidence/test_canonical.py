"""Canonicalization: the field table, determinism, and collection ordering.

Covers T7, T9, T10 and T11.

T9/T10 and T11 are the two halves of one idea, and they pull in opposite
directions on purpose. Set-semantic collections must be **permutation
invariant** — a digest that moves when a caller reorders a list is a digest that
changes when nothing semantic did. Order-semantic collections must be
**sensitive to their ordinal and insensitive to their array position** — a
sequence is a claim, but where it sits in an array is not.

Getting either one wrong is the defect AI-04 paid for twice.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
import sys

import pytest

from plugins.evidence import (
    FIELD_TABLE,
    Inclusion,
    canonical_json,
    content_projection,
    record_projection,
    resolver_paths,
)

pytestmark = pytest.mark.layer1


class TestTheFieldTableIsAuthoritative:
    """§15.2 — the table is the single source of truth for digest behaviour."""

    def test_every_resolvable_path_has_a_table_row(self):
        table_paths = {row.path for row in FIELD_TABLE}
        for path in resolver_paths():
            assert path in table_paths, (
                f"{path} has a resolver but no table row; the table would no "
                "longer be authoritative"
            )

    def test_every_non_virtual_table_row_has_a_resolver(self):
        """A row that classifies a stored field must be projectable."""
        for row in FIELD_TABLE:
            if row.record is Inclusion.NOT_A_FIELD:
                assert row.content is Inclusion.NOT_A_FIELD
                assert row.path not in resolver_paths()
                continue
            assert row.path in resolver_paths(), (
                f"{row.path} is classified by the table but has no resolver, so "
                "its classification is decorative"
            )

    def test_paths_are_unique(self):
        paths = [row.path for row in FIELD_TABLE]
        assert len(paths) == len(set(paths))

    def test_the_operational_fields_are_exactly_the_frozen_five(self):
        """§16's exclusion list, derived from the table rather than restated."""
        excluded = {
            row.path
            for row in FIELD_TABLE
            if row.content is Inclusion.EXCLUDED and row.path != "record_digest"
        }
        assert excluded == {
            "evidence_id",
            "experiment_id",
            "producer_version",
            "recorded_at",
        }

    def test_no_generated_field_is_marked_caller_supplied(self):
        """§14.6.1 and §8.1 — the origin column must agree with the rule."""
        from plugins.evidence import AI05_GENERATED_DIGEST_FIELDS

        for row in FIELD_TABLE:
            if row.ai05_generated and row.path in AI05_GENERATED_DIGEST_FIELDS:
                assert row.caller_supplied is False, row.path

    def test_observed_at_is_per_kind(self):
        row = next(r for r in FIELD_TABLE if r.path == "observed_at")
        assert row.content is Inclusion.PER_KIND


class TestT7Determinism:
    """T7 — same semantics, same content digest, independently of this process.

    Three assertions, weakest to strongest: two parses in this process agree; the
    digest recomputes from the canonical string with a bare `hashlib` call, so it
    does not depend on the plugin's own hashing helper; and a **separate
    interpreter** reaches the same value.
    """

    def test_two_independent_parses_agree(self, record_factory, build):
        a, b = build(record_factory()), build(record_factory())
        assert a.integrity.content_digest == b.integrity.content_digest

    def test_the_digest_recomputes_from_the_canonical_string(self, record_factory, build):
        record = build(record_factory())
        canonical = canonical_json(content_projection(record))
        independent = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert record.integrity.content_digest == independent

    def test_the_record_digest_recomputes_from_the_canonical_string(self, record_factory, build):
        record = build(record_factory())
        canonical = canonical_json(record_projection(record))
        independent = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert record.integrity.record_digest == independent

    def test_a_separate_interpreter_reaches_the_same_value(self, record_factory, build):
        """The cross-process half of T7.

        In this container a spawned process can fail on handle inheritance before
        any assertion runs, which is an environment limitation rather than a
        determinism result — so it is reported as a skip rather than silently
        passing. CI runs it.
        """
        record = build(record_factory())
        projection = content_projection(record)
        program = (
            "import hashlib,json,sys;"
            "payload=json.loads(sys.stdin.read());"
            "canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,"
            "separators=(',',':'),allow_nan=False);"
            "print(hashlib.sha256(canonical.encode('utf-8')).hexdigest())"
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-c", program],
                input=json.dumps(projection),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except OSError as exc:  # pragma: no cover - environment limitation
            pytest.skip(f"cannot spawn an interpreter here: {exc}")

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == record.integrity.content_digest

    def test_key_order_in_the_supplied_mapping_is_irrelevant(self, record_factory, build):
        forward = record_factory()
        reversed_mapping = dict(reversed(list(forward.items())))
        assert (
            build(forward).integrity.content_digest
            == build(reversed_mapping).integrity.content_digest
        )


class TestT9T10SetSemanticCollections:
    """T9/T10 — permutation invariance, asserted for **every** set collection.

    One collection is not enough: `references.context`, `references.decisions`,
    `references.supersedes` and `artifacts.items` are each ordered by a different
    key, and a bug in one key would hide behind a test of another.
    """

    @staticmethod
    def _permutations(items):
        return list(itertools.permutations(items))

    def test_context_references_are_permutation_invariant(self, record_factory, build):
        items = [
            _context("git.head", "PASS"),
            _context("git.branch", "main"),
            _context("git.working_tree", "CLEAN"),
        ]
        digests = {
            build(
                record_factory(references={"context": list(ordering)})
            ).integrity.content_digest
            for ordering in self._permutations(items)
        }
        assert len(digests) == 1, "the context collection is SET-semantic (§15.4)"

    def test_decision_references_are_permutation_invariant(self, record_factory, build):
        items = [{"record_ref": ref} for ref in (_ref("1"), _ref("2"), _ref("3"))]
        digests = {
            build(
                record_factory(references={"decisions": list(ordering)})
            ).integrity.content_digest
            for ordering in self._permutations(items)
        }
        assert len(digests) == 1

    def test_supersede_references_are_permutation_invariant(self, record_factory, build):
        items = [
            {"record_ref": _ref("1"), "correction_reason": "one"},
            {"record_ref": _ref("2"), "correction_reason": "two"},
            {"record_ref": _ref("3"), "correction_reason": "three"},
        ]
        digests = {
            build(
                record_factory(references={"supersedes": list(ordering)})
            ).integrity.content_digest
            for ordering in self._permutations(items)
        }
        assert len(digests) == 1

    def test_artifacts_are_permutation_invariant(self, record_factory, build):
        items = [
            _artifact("raw-log", "a" * 64),
            _artifact("pcap", "b" * 64),
            _artifact("core-dump", "c" * 64),
        ]
        digests = {
            build(
                record_factory(artifacts={"items": list(ordering)})
            ).integrity.content_digest
            for ordering in self._permutations(items)
        }
        assert len(digests) == 1

    def test_ordering_never_uses_the_locator(self, record_factory, build):
        """§15.4 — `artifact_ref` is not an ordering input.

        Two records whose artifacts differ only in where the bytes live must
        order identically, or the content digest would depend on location.
        """
        left = build(
            record_factory(
                artifacts={
                    "items": [
                        _artifact("raw-log", "a" * 64, ref="loc-1"),
                        _artifact("pcap", "b" * 64, ref="loc-2"),
                    ]
                }
            )
        )
        right = build(
            record_factory(
                artifacts={
                    "items": [
                        _artifact("pcap", "b" * 64, ref="loc-9"),
                        _artifact("raw-log", "a" * 64, ref="loc-8"),
                    ]
                }
            )
        )
        assert left.integrity.content_digest == right.integrity.content_digest

    def test_a_genuinely_different_set_does_change_the_digest(self, record_factory, build):
        """The control: permutation invariance must not mean insensitivity."""
        a = build(record_factory(references={"context": [_context("git.head", "PASS")]}))
        b = build(record_factory(references={"context": [_context("git.head", "FAIL")]}))
        assert a.integrity.content_digest != b.integrity.content_digest


class TestT11OrderSemanticCollections:
    """T11 — ordinal decides, array position does not.

    Rewriting the array with the same ordinals must leave the digest unchanged;
    changing an ordinal must change it. An implementation that sorted by array
    index would fail the first half, and one that ignored ordering entirely would
    fail the second.
    """

    @staticmethod
    def _execution(calls):
        return {
            "schema_version": 1,
            "kind": "EXECUTION",
            "provenance": {
                "producer": "ai-06",
                "producer_version": "1.0.0",
                "producer_type": "service",
                "actor": {"id": "tool:runner", "type": "agent"},
                "workspace_id": "ws-1",
            },
            "payload": {"tool_calls": calls},
        }

    def test_array_order_does_not_matter_when_ordinals_are_kept(self, build):
        calls = [
            {"ordinal": 0, "name": "git.status", "status": "PASS"},
            {"ordinal": 1, "name": "pytest", "status": "PASS"},
            {"ordinal": 2, "name": "git.diff", "status": "PASS"},
        ]
        canonical = build(self._execution(calls)).integrity.content_digest
        for ordering in itertools.permutations(calls):
            assert (
                build(self._execution(list(ordering))).integrity.content_digest
                == canonical
            ), "array position is not semantic — the ordinal is (§11.1)"

    def test_changing_an_ordinal_changes_the_digest(self, build):
        original = [
            {"ordinal": 0, "name": "a", "status": "PASS"},
            {"ordinal": 1, "name": "b", "status": "PASS"},
        ]
        swapped = [
            {"ordinal": 1, "name": "a", "status": "PASS"},
            {"ordinal": 0, "name": "b", "status": "PASS"},
        ]
        assert (
            build(self._execution(original)).integrity.content_digest
            != build(self._execution(swapped)).integrity.content_digest
        ), "a sequence is a claim; reversing it asserts something different"

    def test_the_ordinal_survives_into_the_projection(self, build):
        record = build(
            self._execution(
                [
                    {"ordinal": 1, "name": "b", "status": "PASS"},
                    {"ordinal": 0, "name": "a", "status": "PASS"},
                ]
            )
        )
        ordinals = [c["ordinal"] for c in content_projection(record)["payload"]["tool_calls"]]
        assert ordinals == [0, 1], "the projection is emitted in ordinal order"

    def test_a_non_integer_ordinal_is_rejected(self, build):
        from plugins.evidence import errors as ev_errors

        with pytest.raises(ev_errors.RecordMalformed):
            build(self._execution([{"ordinal": "0", "name": "a", "status": "PASS"}]))

    def test_a_negative_ordinal_is_rejected(self, build):
        from plugins.evidence import errors as ev_errors

        with pytest.raises(ev_errors.RecordMalformed):
            build(self._execution([{"ordinal": -1, "name": "a", "status": "PASS"}]))


class TestCanonicalJsonPrimitive:
    """§15 — the rules AI-04 §20.2 freezes, imported rather than restated."""

    def test_keys_are_sorted_and_whitespace_is_absent(self):
        assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    def test_enum_values_render_as_their_canonical_string(self):
        from plugins.evidence import EvidenceKind

        assert canonical_json(EvidenceKind.OBSERVATION) == '"OBSERVATION"'

    def test_a_bare_set_is_refused_rather_than_guessed_at(self):
        with pytest.raises(TypeError):
            canonical_json({"items": {1, 2, 3}})

    def test_canonicalization_does_not_lowercase_anything(self):
        """§15 — canonicalization represents; it does not repair.

        If it lowercased, an uppercase digest would be silently accepted here and
        T21c's rejection would be unreachable.
        """
        assert canonical_json({"d": "ABC"}) == '{"d":"ABC"}'


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _context(subject, value, revision="a" * 39 + "1"):
    return {
        "workspace_id": "ws-1",
        "source_kind": "git_current_state",
        "source_identity": "git",
        "source_revision": revision,
        "subject": subject,
        "value": value,
        "item_kind": "FACT",
        "truth_state": "PASS",
        "freshness": "CURRENT",
    }


def _artifact(role, digest, ref="art-0001"):
    return {
        "artifact_digest": digest,
        "role": role,
        "external": False,
        "owner_workspace_id": None,
        "artifact_ref": ref,
    }


def _ref(suffix: str) -> str:
    """A record reference of the shape `evidence_id` takes (§8.1)."""
    return "ev-" + suffix.rjust(16, "0")
