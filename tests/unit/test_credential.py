"""Credential reference grammar and resolution.

Covers contract §5.3 and amendment 1 / D-16. The central assertion is that the
three outcomes stay distinct:

    missing / empty / whitespace  ->  CREDENTIAL_MISSING
    unsupported scheme            ->  CREDENTIAL_UNSUPPORTED
    literal value                 ->  configuration rejection

No test reads a real credential. Every value used here is a synthetic
placeholder, and no test requires an API key to be present.
"""

from __future__ import annotations

import pytest

from providers.credential import (
    RESERVED_SCHEMES,
    SUPPORTED_SCHEMES,
    CredentialConfigError,
    CredentialError,
    CredentialRef,
    SecretValue,
    resolve,
    resolve_ref,
)
from providers.errors import ErrorClass, ErrorStage

VALID_REF = "env:DEEPSEEK_API_KEY"
PLACEHOLDER = "test-key-not-a-real-key"


class TestReferenceParsing:
    def test_env_reference_parses(self):
        ref = CredentialRef.parse(VALID_REF)
        assert ref.scheme == "env"
        assert ref.target == "DEEPSEEK_API_KEY"
        assert ref.is_supported

    def test_env_is_the_only_supported_scheme(self):
        assert SUPPORTED_SCHEMES == frozenset({"env"})

    @pytest.mark.parametrize("scheme", sorted(RESERVED_SCHEMES))
    def test_reserved_schemes_parse_but_are_unsupported(self, scheme):
        """A reserved scheme is well-formed. Its failure belongs at resolve time."""
        ref = CredentialRef.parse(f"{scheme}:some-target")
        assert ref.scheme == scheme
        assert not ref.is_supported

    def test_unknown_scheme_parses_but_is_unsupported(self):
        ref = CredentialRef.parse("aws:secretsmanager/prod")
        assert not ref.is_supported

    @pytest.mark.parametrize(
        "literal",
        [
            PLACEHOLDER,
            "sk-abcdef1234567890abcdef",
            "Bearer sometoken",
            "somebarevalue",
        ],
    )
    def test_literal_values_are_rejected_at_parse_time(self, literal):
        """A bare value has no scheme separator: a defect, not a credential."""
        with pytest.raises(CredentialConfigError):
            CredentialRef.parse(literal)

    @pytest.mark.parametrize("bad", ["", "   ", "\t", None, 123, ["env:X"], {}])
    def test_empty_and_non_string_references_are_rejected(self, bad):
        with pytest.raises(CredentialConfigError):
            CredentialRef.parse(bad)

    @pytest.mark.parametrize("bad", ["env:", "env:   ", "env:1BADNAME", "env:has space"])
    def test_malformed_env_references_are_rejected(self, bad):
        with pytest.raises(CredentialConfigError):
            CredentialRef.parse(bad)

    def test_scheme_is_case_insensitive(self):
        assert CredentialRef.parse("ENV:DEEPSEEK_API_KEY").scheme == "env"


class TestResolution:
    def test_unset_variable_is_credential_missing(self):
        with pytest.raises(CredentialError) as excinfo:
            resolve_ref("env:DEEPSEEK_API_KEY", environ={})
        assert excinfo.value.error_class is ErrorClass.CREDENTIAL_MISSING

    @pytest.mark.parametrize("value", ["", "   ", "\t\n", "  \t "])
    def test_empty_and_whitespace_are_credential_missing(self, value):
        """Unset, empty, and whitespace are the same failure (§5.3)."""
        with pytest.raises(CredentialError) as excinfo:
            resolve_ref("env:DEEPSEEK_API_KEY", environ={"DEEPSEEK_API_KEY": value})
        assert excinfo.value.error_class is ErrorClass.CREDENTIAL_MISSING

    @pytest.mark.parametrize("scheme", sorted(RESERVED_SCHEMES | {"aws", "unknown"}))
    def test_unsupported_scheme_is_credential_unsupported(self, scheme):
        with pytest.raises(CredentialError) as excinfo:
            resolve_ref(f"{scheme}:whatever", environ={})
        assert excinfo.value.error_class is ErrorClass.CREDENTIAL_UNSUPPORTED

    def test_present_value_resolves(self):
        secret = resolve_ref(
            "env:DEEPSEEK_API_KEY", environ={"DEEPSEEK_API_KEY": PLACEHOLDER}
        )
        assert isinstance(secret, SecretValue)
        assert secret.reveal() == PLACEHOLDER


class TestSemanticsAreNeverMerged:
    """D-16: the three outcomes are distinct and must not collapse."""

    def test_missing_and_unsupported_are_different_classes(self):
        with pytest.raises(CredentialError) as missing:
            resolve_ref("env:UNSET_VAR_NAME_FOR_TEST", environ={})
        with pytest.raises(CredentialError) as unsupported:
            resolve_ref("file:/etc/key", environ={})

        assert missing.value.error_class is ErrorClass.CREDENTIAL_MISSING
        assert unsupported.value.error_class is ErrorClass.CREDENTIAL_UNSUPPORTED
        assert missing.value.error_class is not unsupported.value.error_class

    def test_unsupported_scheme_is_not_reported_as_missing(self):
        """An unimplemented mechanism must never look like a configuration gap."""
        for scheme in sorted(RESERVED_SCHEMES | {"aws"}):
            with pytest.raises(CredentialError) as excinfo:
                resolve_ref(f"{scheme}:target", environ={})
            assert excinfo.value.error_class is not ErrorClass.CREDENTIAL_MISSING

    def test_literal_value_is_not_reported_as_either_error_class(self):
        """A literal is a config defect. It has no ErrorClass at all."""
        with pytest.raises(CredentialConfigError) as excinfo:
            resolve_ref(PLACEHOLDER, environ={})
        assert not isinstance(excinfo.value, CredentialError)
        assert not hasattr(excinfo.value, "error_class")

    def test_a_missing_variable_is_never_reported_as_unsupported(self):
        with pytest.raises(CredentialError) as excinfo:
            resolve_ref("env:UNSET_VAR_NAME_FOR_TEST", environ={})
        assert excinfo.value.error_class is not ErrorClass.CREDENTIAL_UNSUPPORTED


class TestPreconditionBehaviour:
    """Both classes are precondition failures raised before any network attempt."""

    @pytest.mark.parametrize(
        "ref,environ",
        [("env:UNSET_VAR_NAME_FOR_TEST", {}), ("file:/etc/key", {})],
    )
    def test_preconditions_convert_to_resolve_stage_errors(self, ref, environ):
        with pytest.raises(CredentialError) as excinfo:
            resolve_ref(ref, environ=environ)
        error = excinfo.value.to_provider_error()
        assert error.stage is ErrorStage.RESOLVE
        assert error.is_precondition
        assert error.http_status is None

    def test_credential_error_rejects_non_precondition_classes(self):
        """The type cannot carry a network-phase class."""
        with pytest.raises(ValueError):
            CredentialError(ErrorClass.AUTHENTICATION, "not a precondition")


class TestEnvIsInjectable:
    """Resolution reads exactly the mapping it is given."""

    def test_resolution_does_not_read_the_process_environment(self):
        secret = resolve(
            CredentialRef.parse("env:SOME_VAR"), environ={"SOME_VAR": PLACEHOLDER}
        )
        assert secret.reveal() == PLACEHOLDER

    def test_credential_error_message_names_the_reference_not_a_value(self):
        with pytest.raises(CredentialError) as excinfo:
            resolve_ref("env:DEEPSEEK_API_KEY", environ={})
        message = str(excinfo.value)
        assert "env:DEEPSEEK_API_KEY" in message
        assert PLACEHOLDER not in message
