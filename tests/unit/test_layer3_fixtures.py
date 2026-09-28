"""Layer 3 — offline contract fixtures.

Contract §12.4. Fixtures pin normalization behaviour across refactors; they are
**not** evidence of what a provider returns, and nothing here may move a
capability out of `UNKNOWN`.

Every fixture is labelled with a provenance of `synthetic` or `scrubbed`, and
the loader refuses anything unlabelled. That enforcement is itself tested here
against throwaway trees, so the rule is verified rather than asserted in prose.
"""

from __future__ import annotations

import textwrap

import pytest
import yaml

from providers.errors import ErrorClass
from providers.profile import ModelRef
from providers.protocol import FinishState, adapter_for
from tests.fixtures.loader import (
    FIXTURES_ROOT,
    FixtureError,
    Provenance,
    declared_paths,
    fixture_names_by_provider,
    load_fixtures,
    paths_on_disk,
)

pytestmark = pytest.mark.layer3

FAMILY = "openai_compatible_chat"
DEEPSEEK_REF = ModelRef(provider_id="deepseek", model_id="deepseek-flash")
MIMO_REF = ModelRef(provider_id="mimo", model_id="mimo-v2.6-pro")

#: The only key-shaped string anywhere in the fixtures. It is a placeholder
#: whose entire purpose is to give redaction something to remove.
SYNTHETIC_KEY_PLACEHOLDER = "sk-fixture-not-a-real-key"


@pytest.fixture
def fixtures():
    return load_fixtures()


def _response(profile, model_ref, payload):
    adapter = adapter_for(FAMILY)
    return adapter.parse_response(profile, model_ref, payload)


def _mkdir_fixture_tree(root, manifest: dict, payloads: dict[str, str]):
    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    for relative, body in payloads.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def _manifest(entries, version=1):
    return {"version": version, "fixtures": entries}


def _entry(path="deepseek/a.json", provider_id="deepseek"):
    return {
        "path": path,
        "provider_id": provider_id,
        "provenance": "synthetic",
        "note": "throwaway fixture for an enforcement test",
    }


class TestManifestAndProvenance:
    def test_the_manifest_declares_fixtures(self):
        assert declared_paths()

    def test_every_declared_fixture_is_present(self, fixtures):
        assert {fixture.path for fixture in fixtures.values()} == set(declared_paths())
        assert len(fixtures) == len(declared_paths())

    def test_fixture_keys_are_provider_qualified(self, fixtures):
        """Two providers may describe the same scenario without colliding."""
        assert set(fixtures) == {
            "deepseek/chat_stop",
            "deepseek/chat_tool_calls",
            "deepseek/chat_reasoning",
            "deepseek/error_401",
            "mimo/chat_stop",
            "mimo/chat_length",
            "mimo/chat_no_usage",
        }

    def test_no_fixture_is_undeclared(self):
        assert set(paths_on_disk()) == set(declared_paths())

    def test_every_provenance_is_one_of_the_two_frozen_values(self, fixtures):
        allowed = {Provenance.SYNTHETIC, Provenance.SCRUBBED}
        for fixture in fixtures.values():
            assert fixture.provenance in allowed, fixture.path

    def test_every_fixture_carries_a_note(self, fixtures):
        for fixture in fixtures.values():
            assert fixture.note.strip(), fixture.path

    def test_both_providers_are_represented(self):
        """The shared adapter must be exercised for each in-scope provider."""
        assert set(fixture_names_by_provider()) == {"deepseek", "mimo"}

    def test_the_fixtures_are_declared_synthetic(self, fixtures):
        """Nothing here is claimed as an observed capture."""
        assert all(fixture.is_synthetic for fixture in fixtures.values())


class TestProvenanceEnforcement:
    """A fixture of unknown provenance is not usable (§12.4)."""

    def test_an_undeclared_fixture_is_refused(self, tmp_path):
        _mkdir_fixture_tree(
            tmp_path,
            _manifest([_entry()]),
            {"deepseek/a.json": "{}", "deepseek/sneaky.json": "{}"},
        )
        with pytest.raises(FixtureError, match="undeclared"):
            load_fixtures(tmp_path)

    def test_an_unknown_provenance_is_refused(self, tmp_path):
        entry = _entry()
        entry["provenance"] = "unknown"
        _mkdir_fixture_tree(tmp_path, _manifest([entry]), {"deepseek/a.json": "{}"})
        with pytest.raises(FixtureError, match="provenance"):
            load_fixtures(tmp_path)

    def test_a_missing_provenance_is_refused(self, tmp_path):
        entry = _entry()
        del entry["provenance"]
        _mkdir_fixture_tree(tmp_path, _manifest([entry]), {"deepseek/a.json": "{}"})
        with pytest.raises(FixtureError, match="provenance"):
            load_fixtures(tmp_path)

    def test_a_missing_note_is_refused(self, tmp_path):
        entry = _entry()
        del entry["note"]
        _mkdir_fixture_tree(tmp_path, _manifest([entry]), {"deepseek/a.json": "{}"})
        with pytest.raises(FixtureError, match="note"):
            load_fixtures(tmp_path)

    def test_a_declared_but_absent_fixture_is_refused(self, tmp_path):
        _mkdir_fixture_tree(tmp_path, _manifest([_entry()]), {})
        with pytest.raises(FixtureError, match="not present"):
            load_fixtures(tmp_path)

    def test_an_unsupported_manifest_version_is_refused(self, tmp_path):
        _mkdir_fixture_tree(
            tmp_path,
            _manifest([_entry()], version=99),
            {"deepseek/a.json": "{}"},
        )
        with pytest.raises(FixtureError, match="version"):
            load_fixtures(tmp_path)

    def test_a_missing_manifest_is_refused(self, tmp_path):
        with pytest.raises(FixtureError, match="manifest not found"):
            load_fixtures(tmp_path)

    def test_scrubbed_is_an_accepted_provenance(self, tmp_path):
        entry = _entry()
        entry["provenance"] = "scrubbed"
        _mkdir_fixture_tree(tmp_path, _manifest([entry]), {"deepseek/a.json": "{}"})
        loaded = load_fixtures(tmp_path)
        assert loaded["deepseek/a"].provenance is Provenance.SCRUBBED


class TestNoRealCredentials:
    def test_the_only_key_shaped_string_is_the_declared_placeholder(self):
        """Every fixture is scanned: a real-looking secret would be a leak."""
        import re

        pattern = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
        found = set()
        for path in FIXTURES_ROOT.rglob("*.json"):
            found.update(pattern.findall(path.read_text(encoding="utf-8")))
        assert found == {SYNTHETIC_KEY_PLACEHOLDER}

    def test_no_fixture_carries_an_authorization_header(self):
        for path in FIXTURES_ROOT.rglob("*.json"):
            text = path.read_text(encoding="utf-8").lower()
            assert "authorization" not in text, path

    def test_the_placeholder_is_not_a_valid_credential_shape(self):
        assert SYNTHETIC_KEY_PLACEHOLDER.startswith("sk-fixture-")
        assert "not-a-real-key" in SYNTHETIC_KEY_PLACEHOLDER


class TestNormalizationIsPinned:
    """What the fixtures pin: our normalization, not provider behaviour."""

    def test_deepseek_plain_completion(self, fixtures, deepseek_profile):
        response = _response(
            deepseek_profile, DEEPSEEK_REF, fixtures["deepseek/chat_stop"].payload
        )
        assert response.error is None
        assert response.text == "fixture answer"
        assert response.finish_state is FinishState.STOP
        assert response.tool_calls == ()
        assert response.reasoning is None

    def test_mimo_plain_completion(self, fixtures, mimo_profile):
        response = _response(mimo_profile, MIMO_REF, fixtures["deepseek/chat_stop"].payload)
        assert response.text == "fixture answer"
        assert response.finish_state is FinishState.STOP

    def test_both_providers_normalize_identically(self, fixtures, all_profiles):
        """One adapter, two profiles: the payload shape drives the result."""
        deepseek = _response(
            all_profiles["deepseek"], DEEPSEEK_REF, fixtures["deepseek/chat_stop"].payload
        )
        mimo = _response(
            all_profiles["mimo"], MIMO_REF, fixtures["deepseek/chat_stop"].payload
        )
        assert deepseek.text == mimo.text
        assert deepseek.finish_state is mimo.finish_state
        # Attribution still differs, and comes from the profile, not the body.
        assert deepseek.provider_id == "deepseek"
        assert mimo.provider_id == "mimo"

    def test_tool_calls_are_flattened_and_kept_out_of_text(self, fixtures, deepseek_profile):
        response = _response(
            deepseek_profile, DEEPSEEK_REF, fixtures["deepseek/chat_tool_calls"].payload
        )
        assert response.text is None
        assert response.finish_state is FinishState.TOOL_CALLS
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["name"] == "read_file"
        assert "read_file" not in (response.text or "")

    def test_reasoning_is_kept_out_of_text(self, fixtures, deepseek_profile):
        response = _response(
            deepseek_profile, DEEPSEEK_REF, fixtures["deepseek/chat_reasoning"].payload
        )
        assert response.text == "fixture answer"
        assert response.reasoning == "fixture reasoning trace"
        assert "reasoning trace" not in (response.text or "")

    def test_a_length_finish_is_truncation_not_stop(self, fixtures, mimo_profile):
        response = _response(
            mimo_profile, MIMO_REF, fixtures["mimo/chat_length"].payload
        )
        assert response.finish_state is FinishState.LENGTH
        assert response.finish_state is not FinishState.STOP

    def test_absent_usage_is_none_not_zero(self, fixtures, mimo_profile):
        response = _response(
            mimo_profile, MIMO_REF, fixtures["mimo/chat_no_usage"].payload
        )
        assert response.usage is None

    def test_reported_usage_is_preserved(self, fixtures, deepseek_profile):
        response = _response(
            deepseek_profile, DEEPSEEK_REF, fixtures["deepseek/chat_stop"].payload
        )
        assert response.usage["input_tokens"] == 12
        assert response.usage["output_tokens"] == 5
        assert response.usage["usage_status"] == "REPORTED"

    def test_an_error_body_is_classified_and_redacted(
        self, fixtures, deepseek_profile, fake_transport_factory
    ):
        from providers.protocol import TransportResult

        transport = fake_transport_factory(
            TransportResult.success(
                http_status=401, payload=fixtures["deepseek/error_401"].payload
            )
        )
        response = adapter_for(FAMILY).send(
            _call(deepseek_profile, DEEPSEEK_REF), transport
        )

        assert response.error.error_class is ErrorClass.AUTHENTICATION
        assert response.error.http_status == 401
        # Redaction must have removed the placeholder from stored text.
        assert SYNTHETIC_KEY_PLACEHOLDER not in (
            response.error.provider_message_sanitized or ""
        )

    def test_a_malformed_payload_is_refused(self, deepseek_profile):
        with pytest.raises(Exception):
            _response(deepseek_profile, DEEPSEEK_REF, "not-an-object")


def _call(profile, model_ref):
    from providers.protocol import ProviderCall

    adapter = adapter_for(FAMILY)
    from providers.transport import TransportSettings

    return ProviderCall(
        profile=profile,
        model_ref=model_ref,
        request=adapter.build_request(
            profile,
            model_ref,
            credential="placeholder",
            body="{}",
            transport_settings=TransportSettings(),
        ),
    )


class TestFixturesCannotPromoteCapabilities:
    """A fixture is not evidence (§12.3)."""

    def test_loading_fixtures_leaves_every_capability_unknown(self, model_profiles):
        load_fixtures()
        for ref, profile in model_profiles.items():
            for name, entry in profile.capabilities.items():
                assert entry.status.value == "UNKNOWN", f"{ref}:{name.value}"
            assert not profile.has_verified_capability, ref

    def test_the_loader_returns_payloads_not_capability_claims(self, fixtures):
        for fixture in fixtures.values():
            assert not hasattr(fixture, "capabilities")
            assert not hasattr(fixture, "status")

    def test_no_fixture_declares_a_verification(self):
        """A fixture cannot carry a dated observation, because it has none."""
        for path in FIXTURES_ROOT.rglob("*.json"):
            text = path.read_text(encoding="utf-8").lower()
            for forbidden in ("verified_at", "evidence_ref", "verified"):
                assert forbidden not in text, f"{path}: {forbidden}"


class TestFixtureHygiene:
    def test_the_manifest_is_valid_yaml_with_a_version(self):
        raw = yaml.safe_load((FIXTURES_ROOT / "manifest.yaml").read_text(encoding="utf-8"))
        assert raw["version"] == 1

    def test_every_fixture_is_valid_json(self, fixtures):
        for fixture in fixtures.values():
            assert isinstance(fixture.payload, (dict, list)), fixture.path

    def test_fixture_paths_live_under_a_provider_directory(self, fixtures):
        for fixture in fixtures.values():
            directory = fixture.path.split("/")[0]
            assert directory == fixture.provider_id, fixture.path
