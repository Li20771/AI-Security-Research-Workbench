"""Capability truth model.

Contract §8 (five frozen states, two axes) and §6.8 (unknown is not false).

The point of these tests is that the schema cannot express a false confidence:
a capability that nobody checked cannot be recorded as working, and a claim
cannot be recorded as an observation.
"""

from __future__ import annotations

import pytest

from providers.model_profile import (
    Capabilities,
    CapabilityEntry,
    CapabilityName,
    CapabilityStatus,
    ModelProfileError,
    Provenance,
)

from tests.unit.test_model_profile import make_profile


pytestmark = pytest.mark.layer1

FROZEN_STATES = {"DECLARED", "VERIFIED", "NOT_VERIFIED", "UNAVAILABLE", "UNKNOWN"}


class TestFrozenStates:
    def test_exactly_the_five_frozen_states_exist(self):
        assert {s.value for s in CapabilityStatus} == FROZEN_STATES

    def test_states_are_not_python_booleans(self):
        """`supported: true/false` is not an acceptable model (§6.8)."""
        for state in CapabilityStatus:
            assert not isinstance(state, bool)
        assert CapabilityStatus.UNKNOWN is not False
        assert CapabilityStatus.UNKNOWN != "false"

    def test_unknown_and_unavailable_are_distinct(self):
        """Nobody knows, versus someone observed it is absent."""
        assert CapabilityStatus.UNKNOWN != CapabilityStatus.UNAVAILABLE

    def test_not_verified_and_verified_are_distinct(self):
        assert CapabilityStatus.NOT_VERIFIED != CapabilityStatus.VERIFIED

    def test_declared_and_verified_are_distinct(self):
        assert CapabilityStatus.DECLARED != CapabilityStatus.VERIFIED


class TestTwoAxes:
    def test_declared_and_verified_are_separate_fields(self):
        entry = CapabilityEntry(
            status=CapabilityStatus.NOT_VERIFIED,
            declared=True,
            verified=None,
            source="provider model card",
        )
        assert entry.declared is True
        assert entry.verified is None
        assert entry.status is CapabilityStatus.NOT_VERIFIED

    def test_verified_true_is_only_valid_as_verified(self):
        """An unobserved capability must not carry verified=true (§8.3)."""
        for status in (
            CapabilityStatus.UNKNOWN,
            CapabilityStatus.DECLARED,
            CapabilityStatus.NOT_VERIFIED,
            CapabilityStatus.UNAVAILABLE,
        ):
            with pytest.raises(ModelProfileError, match="VERIFIED"):
                CapabilityEntry(status=status, verified=True)

    def test_declared_does_not_imply_verified(self):
        entry = CapabilityEntry(
            status=CapabilityStatus.DECLARED,
            declared=True,
            verified=None,
            source="vendor documentation",
        )
        assert entry.declared is True
        assert entry.verified is not True
        assert not entry.is_verified


class TestUnknown:
    def test_unknown_requires_nothing_claimed_and_nothing_observed(self):
        entry = CapabilityEntry(status=CapabilityStatus.UNKNOWN)
        assert entry.declared is None
        assert entry.verified is None
        assert entry.source is None
        assert entry.is_unknown
        assert not entry.is_verified
        assert entry.declared is not False

    @pytest.mark.parametrize("declared", [True, False])
    def test_unknown_rejects_any_declaration(self, declared):
        with pytest.raises(ModelProfileError, match="UNKNOWN"):
            CapabilityEntry(status=CapabilityStatus.UNKNOWN, declared=declared)

    def test_unknown_rejects_an_observation(self):
        with pytest.raises(ModelProfileError, match="UNKNOWN"):
            CapabilityEntry(status=CapabilityStatus.UNKNOWN, verified=False)

    def test_unknown_rejects_a_source(self):
        with pytest.raises(ModelProfileError, match="source"):
            CapabilityEntry(status=CapabilityStatus.UNKNOWN, source="somewhere")


class TestDeclared:
    def test_valid_declared_entry(self):
        entry = CapabilityEntry(
            status=CapabilityStatus.DECLARED,
            declared=True,
            verified=None,
            source="DeepSeek API reference",
        )
        assert entry.is_unknown is False

    def test_declared_requires_declared_true(self):
        with pytest.raises(ModelProfileError, match="declared=true"):
            CapabilityEntry(
                status=CapabilityStatus.DECLARED, declared=None, source="docs"
            )

    def test_declared_requires_a_source(self):
        with pytest.raises(ModelProfileError, match="source"):
            CapabilityEntry(status=CapabilityStatus.DECLARED, declared=True)


class TestNotVerified:
    def test_valid_entry_records_the_attempted_check(self):
        entry = CapabilityEntry(
            status=CapabilityStatus.NOT_VERIFIED,
            declared=True,
            verified=None,
            source="connectivity check blocked: no credential",
        )
        assert not entry.is_verified

    def test_requires_a_source(self):
        with pytest.raises(ModelProfileError, match="source"):
            CapabilityEntry(status=CapabilityStatus.NOT_VERIFIED, declared=True)

    def test_rejects_verified_true(self):
        with pytest.raises(ModelProfileError, match="VERIFIED"):
            CapabilityEntry(
                status=CapabilityStatus.NOT_VERIFIED, verified=True, source="x"
            )


class TestUnavailable:
    def test_valid_entry_records_a_negative_observation(self):
        entry = CapabilityEntry(
            status=CapabilityStatus.UNAVAILABLE,
            verified=False,
            source="observed rejected by provider",
        )
        assert entry.verified is False
        assert not entry.is_verified

    def test_requires_an_explicit_false(self):
        """UNAVAILABLE is an observation, not the absence of one."""
        with pytest.raises(ModelProfileError, match="verified=false"):
            CapabilityEntry(status=CapabilityStatus.UNAVAILABLE, source="x")

    def test_requires_a_source(self):
        with pytest.raises(ModelProfileError, match="source"):
            CapabilityEntry(status=CapabilityStatus.UNAVAILABLE, verified=False)


class TestVerifiedCrossFieldRule:
    """VERIFIED needs a dated observation and evidence, both on the profile."""

    def _profile_with(self, entry: CapabilityEntry, provenance: Provenance):
        return make_profile(
            capabilities=Capabilities(tool_calling=entry), provenance=provenance
        )

    def test_verified_requires_provenance(self):
        entry = CapabilityEntry(status=CapabilityStatus.VERIFIED, verified=True)
        with pytest.raises(ModelProfileError, match="verified_at"):
            self._profile_with(entry, Provenance())

    def test_verified_requires_both_timestamp_and_evidence(self):
        entry = CapabilityEntry(status=CapabilityStatus.VERIFIED, verified=True)
        with pytest.raises(ModelProfileError, match="evidence_ref"):
            self._profile_with(entry, Provenance(verified_at="2026-09-28"))

    def test_verified_is_expressible_for_a_future_phase(self):
        """The schema supports VERIFIED; B2 simply never produces it."""
        entry = CapabilityEntry(status=CapabilityStatus.VERIFIED, verified=True)
        profile = self._profile_with(
            entry,
            Provenance(verified_at="2026-09-28", evidence_ref="AI-02-B6-RUN-001"),
        )
        assert profile.has_verified_capability

    def test_verified_entry_still_requires_verified_true(self):
        entry = CapabilityEntry(status=CapabilityStatus.VERIFIED, verified=None)
        with pytest.raises(ModelProfileError, match="verified=true"):
            self._profile_with(
                entry,
                Provenance(verified_at="2026-09-28", evidence_ref="EV-1"),
            )


class TestShippedProfilesAssertNothing:
    """AI-02-B2 produces no capability claim of any kind."""

    def test_every_capability_is_unknown(self, model_profiles):
        for ref, profile in model_profiles.items():
            for name, entry in profile.capabilities.items():
                assert entry.status is CapabilityStatus.UNKNOWN, f"{ref}:{name.value}"

    def test_no_capability_is_verified(self, model_profiles):
        for ref, profile in model_profiles.items():
            assert not profile.has_verified_capability, ref
            for name, entry in profile.capabilities.items():
                assert entry.status is not CapabilityStatus.VERIFIED, ref

    def test_no_capability_is_declared(self, model_profiles):
        """No traceable declared source exists in the repository today."""
        for ref, profile in model_profiles.items():
            for name, entry in profile.capabilities.items():
                assert entry.status is not CapabilityStatus.DECLARED, ref

    def test_no_capability_claims_a_source(self, model_profiles):
        for ref, profile in model_profiles.items():
            for name, entry in profile.capabilities.items():
                assert entry.source is None, f"{ref}:{name.value}"

    def test_no_capability_is_a_boolean(self, model_profiles):
        for ref, profile in model_profiles.items():
            for name, entry in profile.capabilities.items():
                assert entry.declared is None, f"{ref}:{name.value}"
                assert entry.verified is None, f"{ref}:{name.value}"

    def test_all_five_capabilities_are_present_on_every_profile(self, model_profiles):
        expected = {name.value for name in CapabilityName}
        for ref, profile in model_profiles.items():
            assert set(profile.capabilities.to_dict()) == expected, ref
