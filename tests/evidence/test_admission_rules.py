"""AI-05 §14.10, §30 step 7 — the published admission rule set, at admission.

C-1 is closed by Amendment 3, which publishes the six rules this module asserts.
Four things are being proven, and they are different:

```text
the catalog IS the published one    six rules, exact ids, exact patterns, in order,
                                    with no substitution data and no secret registry
the rules REFUSE                    T20c, T22a, T22b, T22c
they do not refuse everything       positive controls, clean Class 4 and pre-sanitized
                                    Class 3
they are LOAD-BEARING               remove a rule and its rejection stops happening
```

The last is the one that keeps the others honest: a suite that only asserted
"REJECTED" would pass against a system that rejected for some other reason
entirely. Each negative test below is paired with the rule whose removal makes it
stop rejecting.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from plugins.evidence import (
    ADMISSION_RULES,
    CLASS_3_PATHS,
    CLASS_4_PATHS,
    SCANNED_PATHS,
    AdmissionOutcome,
    AdmissionRuleViolation,
    RULES_REVISION,
    admit,
    first_match,
)
from plugins.evidence import rules as rules_module

from tests.evidence.conftest import (
    FIXED_CLOCK,
    SHA256,
    make_decision,
    make_execution,
    make_observation,
)

pytestmark = pytest.mark.layer1

CLK = lambda: FIXED_CLOCK  # noqa: E731


def _admit(raw):
    return admit(raw, clock=CLK)


def _with_observed(value: str) -> dict:
    """A well-formed OBSERVATION whose Class 4 `observed` carries `value`."""
    raw = make_observation()
    raw["payload"]["observed"] = value
    return raw


# ---------------------------------------------------------------------------
# The catalog is the published one
# ---------------------------------------------------------------------------


class TestTheRuleCatalogIsThePublishedOne:
    """§14.10 published six rules; this asserts the code ships those six."""

    def test_there_are_exactly_six_rules_in_the_published_order(self):
        assert [rule.rule_id for rule in ADMISSION_RULES] == [
            "C1-R01",
            "C1-R02",
            "C1-R03",
            "C1-R04",
            "C1-R05",
            "C1-R06",
        ]

    @pytest.mark.parametrize(
        "rule_id,pattern",
        [
            ("C1-R01", r"(?i)\bauthorization\b\s*[:=]\s*\S+"),
            (
                "C1-R02",
                r"(?i)\b("
                r"api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|auth[_-]?token"
                r"|bearer|token|secret|password|passwd|pwd"
                r")\b\s*[:=]\s*[\"']?([^\s\"',;}\]]+)",
            ),
            ("C1-R03", r"\bsk-[A-Za-z0-9_\-]{8,}"),
            ("C1-R04", r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}"),
            ("C1-R05", r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
            ("C1-R06", r"\b[A-Za-z0-9_\-]{32,}\b"),
        ],
    )
    def test_each_rule_carries_its_published_pattern(self, rule_id, pattern):
        """The pattern STRING, so a recompiled equivalent still has to match."""
        rule = next(r for r in ADMISSION_RULES if r.rule_id == rule_id)
        assert rule.pattern.pattern == pattern

    def test_the_rule_set_is_versioned_by_amendment_and_not_by_a_field(self):
        """§14.10: no rule-set version field, on a record or anywhere else.

        The revision is a module constant — a fact about this code — and it is not
        reachable from any record. A field a decision could read would let
        admission depend on which revision wrote the record.
        """
        assert "§14.10" in RULES_REVISION
        assert "Amendment 3" in RULES_REVISION

        # No record field carries it, and no scanned path is a rule-set version.
        from dataclasses import fields

        from plugins.evidence import EvidenceRecord

        def _all_names(dc) -> set[str]:
            found = set()
            for f in fields(dc):
                found.add(f.name)
                inner = getattr(f.type, "__dataclass_fields__", None)
                if inner is not None:
                    found |= _all_names(f.type)
            return found

        record_fields = _all_names(EvidenceRecord)
        assert "rules_revision" not in record_fields
        assert "rule_set_version" not in record_fields
        assert not [p for p in SCANNED_PATHS if "rules" in p]

    def test_every_rule_carries_exactly_id_name_and_pattern(self):
        """No fourth field — and in particular no replacement string."""
        for rule in ADMISSION_RULES:
            assert [f for f in rule.__dataclass_fields__] == [
                "rule_id",
                "name",
                "pattern",
            ]

    def test_the_module_has_no_substitution_path(self):
        """§14.4.1: detection only. Asserted over the AST, not over prose.

        The module may DESCRIBE substitution in a docstring — the rule it is
        obeying — so the check reads calls and names, the same distinction
        `layer0_policy` makes.
        """
        source = pathlib.Path(rules_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called = getattr(node.func, "attr", None) or getattr(
                    node.func, "id", None
                )
                assert called not in {"sub", "subn", "replace", "translate"}, called
        assert "[REDACTED]" not in source
        assert "extra_secrets" not in source
        assert "providers.redaction" not in source
        assert "import redaction" not in source

    def test_the_module_imports_no_credential_or_provider_module(self):
        """No credential store, no sanitizer, nothing to read a secret from."""
        source = pathlib.Path(rules_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert imported == {"__future__", "re", "dataclasses", "typing",
                            "plugins.evidence.errors"}, sorted(imported)

    def test_the_scan_set_is_the_two_scanned_classes_and_nothing_else(self):
        """§14.10: Class 1 and Class 2 are not scanned, and their absence is the rule."""
        assert len(CLASS_3_PATHS) == 15
        assert len(CLASS_4_PATHS) == 8
        assert SCANNED_PATHS == CLASS_4_PATHS + CLASS_3_PATHS

        structural = (
            "content_digest",
            "record_digest",
            "value_digest",
            "artifact_digest",
            "input_digest",
            "source_revision",
        )
        for name in structural:
            assert not [p for p in SCANNED_PATHS if p.endswith(name)], name

    def test_the_first_matching_rule_is_the_one_reported(self):
        """§14.10 fixes the order, so a two-rule value has one deterministic answer."""
        # Matches C1-R01 (an authorization header) and, were it consulted, nothing
        # earlier. The assertion is that the FIRST match is returned, not a later one.
        assert first_match("authorization: Bearer abc").rule_id == "C1-R01"
        assert first_match("nothing to see") is None


# ---------------------------------------------------------------------------
# The rules refuse
# ---------------------------------------------------------------------------


class TestT20c:
    """T20c — the row that was carried as a static skip while C-1 was deferred.

    It asserted `REJECTED` then and asserts the same `REJECTED` now: a legitimate
    64-character lowercase hex value in a Class 4 field matches C1-R06, and §14.5.1
    declares that over-rejection deliberate. It MUST NOT be "fixed" by narrowing
    the rule (§31.1).
    """

    def test_t20c_a_64_hex_value_in_a_class_4_field_is_rejected(self):
        result = _admit(_with_observed(SHA256))

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "ADMISSION_RULE_VIOLATION"
        assert result.record is None

    def test_t20c_the_same_value_in_a_class_1_field_is_accepted(self):
        """The other half: rule 6 must not destroy a digest.

        The same 64-hex value is legitimate in `artifact_digest`, which is Class 1
        and never scanned. Without this pair, the row above is satisfied by a
        system that rejects every hex value everywhere.
        """
        raw = make_observation(
            artifacts={"items": [{"artifact_digest": SHA256, "external": False,
                                  "owner_workspace_id": None,
                                  "artifact_ref": "art-0001"}]}
        )
        assert _admit(raw).outcome is AdmissionOutcome.ACCEPTED


class TestT22a:
    """T22a — a known test secret in a Class 4 field is REJECTED."""

    @pytest.mark.parametrize(
        "value,rule_id",
        [
            ("authorization: Bearer test-token-abc", "C1-R01"),
            ("api_key: test-value-123", "C1-R02"),
        ],
    )
    def test_t22a_a_credential_shaped_class_4_value_is_rejected(self, value, rule_id):
        result = _admit(_with_observed(value))

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "ADMISSION_RULE_VIOLATION"

    def test_t22a_the_reason_names_the_rule_and_the_field(self):
        with pytest.raises(AdmissionRuleViolation) as excinfo:
            from plugins.evidence import check_admission_rules

            check_admission_rules(_with_observed("authorization: Bearer abc"))

        message = str(excinfo.value)
        assert "C1-R01" in message
        assert "payload.observed" in message


class TestT22b:
    """T22b — a secret-shaped vendor token or a long opaque token is REJECTED."""

    @pytest.mark.parametrize(
        "value,rule_id",
        [
            ("sk-test0123456789abcdef", "C1-R03"),
            ("ghp_" + "A" * 24, "C1-R04"),
            ("xoxb-" + "0" * 14, "C1-R05"),
            ("A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6", "C1-R06"),
        ],
    )
    def test_t22b_a_secret_shaped_token_is_rejected(self, value, rule_id):
        result = _admit(_with_observed(value))

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "ADMISSION_RULE_VIOLATION"

    def test_t22b_the_same_shapes_are_rejected_in_a_context_value(self):
        """`references.context[].value` is the supplied Class 4 path that is
        HASHED during construction — which is why step 7 reads supplied values."""
        raw = make_observation(
            references={
                "context": [
                    {
                        "workspace_id": "ws-1",
                        "source_kind": "git_current_state",
                        "source_identity": "git",
                        "source_revision": "a" * 39 + "1",
                        "subject": "git.head",
                        "value": "sk-test0123456789abcdef",
                        "item_kind": "FACT",
                        "truth_state": "PASS",
                        "freshness": "CURRENT",
                    }
                ]
            }
        )
        result = _admit(raw)

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "ADMISSION_RULE_VIOLATION"


class TestT22c:
    """T22c — an UNSANITIZED secret-shaped token in a Class 3 field is REJECTED.

    §14.5 expects a Class 3 value to arrive pre-sanitized upstream, because an
    identifier can be identifier-shaped and secret-shaped at once. AI-05 checks the
    shape and does not sanitize: a value that is still secret-shaped is refused.
    """

    @pytest.mark.parametrize(
        "value",
        [
            "ghp_" + "A" * 24,          # GitHub token prefix, and identifier-shaped
            "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6",   # a 32-character identifier
        ],
    )
    def test_t22c_an_unsanitized_class_3_value_is_rejected(self, value):
        raw = make_observation()
        raw["provenance"]["producer_version"] = value

        result = _admit(raw)

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "ADMISSION_RULE_VIOLATION"

    def test_t22c_the_pre_sanitized_form_of_the_same_field_is_accepted(self):
        """The control: the field is fine, the UNSANITIZED value is not."""
        raw = make_observation()
        raw["provenance"]["producer_version"] = "redacted"

        assert _admit(raw).outcome is AdmissionOutcome.ACCEPTED


# ---------------------------------------------------------------------------
# The system does not reject everything
# ---------------------------------------------------------------------------


class TestPositiveControls:
    def test_a_clean_class_4_record_is_accepted(self):
        assert _admit(make_observation()).outcome is AdmissionOutcome.ACCEPTED

    def test_a_clean_class_3_decision_record_is_accepted(self):
        assert _admit(make_decision()).outcome is AdmissionOutcome.ACCEPTED

    def test_a_clean_execution_record_is_accepted(self):
        assert _admit(make_execution()).outcome is AdmissionOutcome.ACCEPTED

    def test_a_clean_context_value_is_accepted(self):
        raw = make_observation()
        assert _admit(raw).outcome is AdmissionOutcome.ACCEPTED

    def test_short_hex_and_long_words_that_are_not_tokens_are_accepted(self):
        """The controls that make C1-R06's over-rejection a boundary and not a bug."""
        for value in ("a" * 31, "read the live state", "PASS", "git.head"):
            assert _admit(_with_observed(value)).outcome is AdmissionOutcome.ACCEPTED


# ---------------------------------------------------------------------------
# The rules are load-bearing
# ---------------------------------------------------------------------------


class TestTheRulesAreLoadBearing:
    """Non-vacuity: remove a rule and the rejection it causes must stop happening.

    A suite that asserted only `REJECTED` would pass against a system rejecting for
    some other reason — a shape rule, a grammar, a typo in a fixture. Each probe
    below matches exactly ONE published rule, so the before/after pair isolates it.
    """

    PROBES = {
        "C1-R01": "authorization: Bearer abc",
        "C1-R02": "api_key: test-value",
        "C1-R03": "sk-test0123456789abcdef",
        "C1-R04": "ghp_" + "A" * 24,
        "C1-R05": "xoxb-" + "0" * 14,
        "C1-R06": "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6",
    }

    @pytest.mark.parametrize("rule_id", sorted(PROBES))
    def test_the_probe_really_matches_that_rule_and_only_that_rule(self, rule_id):
        """The control for the control: the probe is unambiguous."""
        matched = first_match(self.PROBES[rule_id])

        assert matched is not None
        assert matched.rule_id == rule_id

    @pytest.mark.parametrize("rule_id", sorted(PROBES))
    def test_removing_the_rule_makes_its_rejection_stop(self, rule_id, monkeypatch):
        probe = self.PROBES[rule_id]
        assert _admit(_with_observed(probe)).outcome is AdmissionOutcome.REJECTED

        remaining = tuple(r for r in ADMISSION_RULES if r.rule_id != rule_id)
        monkeypatch.setattr(rules_module, "ADMISSION_RULES", remaining)

        assert first_match(probe) is None
        # The record is otherwise well formed, so with the rule gone it is admitted:
        # nothing else in §30 was refusing it.
        assert _admit(_with_observed(probe)).outcome is AdmissionOutcome.ACCEPTED

    def test_removing_every_rule_admits_every_probe(self, monkeypatch):
        """The whole set, in one direction: no rule, no rejection."""
        monkeypatch.setattr(rules_module, "ADMISSION_RULES", ())

        for probe in self.PROBES.values():
            assert _admit(_with_observed(probe)).outcome is AdmissionOutcome.ACCEPTED

        assert first_match("authorization: Bearer abc") is None


# ---------------------------------------------------------------------------
# The refusal is the one place a value must not travel
# ---------------------------------------------------------------------------


class TestTheRefusalLeaksNothing:
    SECRET = "ghp_" + "A" * 24

    def test_the_message_names_the_field_and_the_rule(self):
        from plugins.evidence import check_admission_rules

        with pytest.raises(AdmissionRuleViolation) as excinfo:
            check_admission_rules(_with_observed(self.SECRET))

        message = str(excinfo.value)
        assert "payload.observed" in message
        assert "C1-R04" in message

    def test_the_message_carries_no_part_of_the_value(self):
        from plugins.evidence import check_admission_rules

        with pytest.raises(AdmissionRuleViolation) as excinfo:
            check_admission_rules(_with_observed(self.SECRET))

        message = str(excinfo.value)
        assert self.SECRET not in message
        assert "ghp_" not in message
        assert "AAAA" not in message
        # Not even a length: §14.10's refusal says which rule, not how long.
        assert str(len(self.SECRET)) not in message

    def test_a_rejected_record_stores_nothing_and_states_no_digest(self, tmp_path):
        """R2: no digest is computed over rule-tripping content.

        The record is refused before construction, so no `value_digest` is derived
        from the supplied context value and no record exists to digest.
        """
        from plugins.evidence import StagedEvidenceStore, admit_to_store

        store = StagedEvidenceStore(tmp_path / "staged")
        result = admit_to_store(_with_observed(self.SECRET), store=store, clock=CLK)

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.record is None
        assert store.list_ids() == ()
