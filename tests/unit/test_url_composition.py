"""Endpoint composition.

Contract §5.2 / D-4: `effective_url = base_url + path_template`, exactly. No
prefix is injected and `/v1` is never added, because the two in-scope
providers declare different base URL shapes.
"""

from __future__ import annotations

import pytest

from providers.profile import Endpoint, ProfileError
from providers.protocol import adapter_for

#: Transcribed from contract §5.5 and the task's declared metadata.
EXPECTED = {
    "deepseek": "https://api.deepseek.com/chat/completions",
    "mimo": "https://api.xiaomimimo.com/v1/chat/completions",
}


class TestDeclaredComposition:
    @pytest.mark.parametrize("provider_id,expected", sorted(EXPECTED.items()))
    def test_declared_effective_url(self, all_profiles, provider_id, expected):
        assert all_profiles[provider_id].endpoint.effective_url == expected

    def test_deepseek_url_has_no_version_segment(self, deepseek_profile):
        """`/v1` must never be inserted on a base URL that omits it."""
        url = deepseek_profile.endpoint.effective_url
        assert "/v1" not in url
        assert url == "https://api.deepseek.com/chat/completions"

    def test_mimo_url_keeps_exactly_one_version_segment(self, mimo_profile):
        """MiMo's declared base URL already carries `/v1`; it must not double."""
        url = mimo_profile.endpoint.effective_url
        assert url.count("/v1") == 1
        assert url == "https://api.xiaomimimo.com/v1/chat/completions"

    def test_adapter_does_not_rewrite_the_composition(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            adapter = adapter_for(profile.protocol.family)
            assert adapter.effective_url(profile) == EXPECTED[provider_id]


class TestCompositionRule:
    @pytest.mark.parametrize(
        "base,path,expected",
        [
            ("https://api.deepseek.com", "/chat/completions", "https://api.deepseek.com/chat/completions"),
            ("https://api.deepseek.com/", "/chat/completions", "https://api.deepseek.com/chat/completions"),
            ("https://api.xiaomimimo.com/v1", "/chat/completions", "https://api.xiaomimimo.com/v1/chat/completions"),
            ("https://example.test/v1/", "chat/completions", "https://example.test/v1/chat/completions"),
            ("https://example.test/api", "/v2/chat", "https://example.test/api/v2/chat"),
        ],
    )
    def test_join_is_exact_regardless_of_slashes(self, base, path, expected):
        assert Endpoint(base_url=base, path_template=path).effective_url == expected

    def test_no_prefix_is_ever_injected(self):
        """A base URL with no version segment stays that way."""
        endpoint = Endpoint(base_url="https://example.test", path_template="/chat")
        assert endpoint.effective_url == "https://example.test/chat"
        assert "/v1" not in endpoint.effective_url

    def test_path_is_not_prefixed_with_v1(self):
        endpoint = Endpoint(base_url="https://example.test", path_template="/completions")
        assert endpoint.effective_url.endswith("/completions")
        assert "/v1/" not in endpoint.effective_url


class TestEndpointValidation:
    @pytest.mark.parametrize("bad", ["ftp://example.test", "example.test", "", "//example.test"])
    def test_base_url_must_be_http_s(self, bad):
        with pytest.raises(ProfileError):
            Endpoint(base_url=bad, path_template="/chat")

    def test_base_url_must_not_embed_a_credential(self):
        """`user:pass@host` would put a credential in the URL (§5.2)."""
        with pytest.raises(ProfileError):
            Endpoint(base_url="https://user:secret@example.test", path_template="/chat")

    @pytest.mark.parametrize(
        "base,path",
        [
            ("https://example.test?q=1", "/chat"),
            ("https://example.test#frag", "/chat"),
            ("https://example.test", "/chat?q=1"),
            ("https://example.test", "/chat#frag"),
        ],
    )
    def test_query_and_fragment_are_rejected(self, base, path):
        with pytest.raises(ProfileError):
            Endpoint(base_url=base, path_template=path)

    def test_path_template_must_not_be_empty(self):
        with pytest.raises(ProfileError):
            Endpoint(base_url="https://example.test", path_template="   ")

    def test_source_must_be_a_known_value(self):
        with pytest.raises(ProfileError):
            Endpoint(base_url="https://example.test", path_template="/chat", source="guess")

    def test_declared_endpoint_is_not_verified(self, all_profiles):
        for provider_id, profile in all_profiles.items():
            assert profile.endpoint.source == "declared", provider_id
            assert profile.endpoint.verified_at is None, provider_id
            assert not profile.endpoint.is_verified, provider_id
