"""Credential reference grammar and v1 resolver.

Implements AI-02 contract §5.3 (reference grammar) and the three distinct
outcomes frozen by amendment 1 / decision D-16:

    env:<VAR_NAME> unset / empty / whitespace   -> CREDENTIAL_MISSING
    file: / keyring: / vault: / unknown scheme  -> CREDENTIAL_UNSUPPORTED
    <literal value>                             -> configuration rejection

The first two are runtime precondition failures: both raise before any
network attempt, and both are raised as `CredentialError` carrying a real
`ErrorClass`. The third is a configuration/schema defect -- it raises
`CredentialConfigError`, which is deliberately **not** an `ErrorClass`, because
a malformed reference never reaches the runtime taxonomy (§5.3, §10.3).

`CREDENTIAL_MISSING` and `CREDENTIAL_UNSUPPORTED` are never merged. One means
the runtime environment supplied no credential; the other means the reference
named a mechanism this layer does not implement. Their remedies differ --
provision a credential versus write a supported reference -- so conflating them
sends an operator to fix the wrong cause.

The resolved value is only ever wrapped in `SecretValue`, whose `repr` and
`str` are redacted so it cannot leak through logging, exception formatting, or
dataclass dumps.
"""

from __future__ import annotations

import hmac
import os
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from providers.errors import ErrorClass, ErrorStage, ProviderError

#: Schemes implemented in AI-02. Only `env:` (contract §5.3).
SUPPORTED_SCHEMES: frozenset[str] = frozenset({"env"})

#: Schemes reserved for future phases. Well-formed, but not implemented.
#: Resolving one is CREDENTIAL_UNSUPPORTED, never CREDENTIAL_MISSING.
RESERVED_SCHEMES: frozenset[str] = frozenset({"file", "keyring", "vault"})

_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CredentialConfigError(ValueError):
    """The reference is malformed, or is a literal credential value.

    A configuration/schema defect. Deliberately NOT an `ErrorClass`: it never
    reaches the runtime taxonomy, and it is never resolved, never sent, and
    never reported as missing or unsupported.
    """


class CredentialError(Exception):
    """A runtime precondition failure while resolving a credential.

    Carries the frozen `ErrorClass`; both possible classes are raised before
    any network attempt.
    """

    def __init__(self, error_class: ErrorClass, message: str) -> None:
        if error_class not in (
            ErrorClass.CREDENTIAL_MISSING,
            ErrorClass.CREDENTIAL_UNSUPPORTED,
        ):
            raise ValueError(
                f"CredentialError carries only precondition classes, got {error_class}"
            )
        super().__init__(message)
        self.error_class = error_class

    def to_provider_error(self) -> ProviderError:
        """Convert to the contract §5.9 error shape, stage `resolve`."""
        return ProviderError(
            error_class=self.error_class,
            stage=ErrorStage.RESOLVE,
            provider_message_sanitized=str(self),
        )


class SecretValue:
    """A resolved credential.

    `repr` and `str` are redacted so the value cannot escape through logging,
    tracebacks, f-strings, or dataclass serialization. The only way to obtain
    the plaintext is `reveal()`, which exists for exactly one caller: the
    transport header builder.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not value or not value.strip():
            raise CredentialConfigError(
                "SecretValue must not be empty; empty resolves to CREDENTIAL_MISSING"
            )
        self._value = value

    def reveal(self) -> str:
        """Return the plaintext. Never log, store, or serialize the result."""
        return self._value

    def matches(self, other: "SecretValue") -> bool:
        """Constant-time comparison, for tests and future credential checks."""
        return hmac.compare_digest(self._value, other._value)

    def __repr__(self) -> str:
        return "SecretValue(***)"

    def __str__(self) -> str:
        return "***"

    def __bool__(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class CredentialRef:
    """A parsed credential reference. Holds a reference, never a value."""

    scheme: str
    target: str

    @property
    def is_supported(self) -> bool:
        return self.scheme in SUPPORTED_SCHEMES

    def __str__(self) -> str:
        # A reference is not a secret; it is safe to show. This is what
        # appears in config errors and diagnostics.
        return f"{self.scheme}:{self.target}"

    @classmethod
    def parse(cls, ref: object) -> "CredentialRef":
        """Validate the *shape* of a reference.

        Raises `CredentialConfigError` for a literal value, an empty or
        non-string reference, or a malformed `env:` target.

        A well-formed reference to an unimplemented scheme parses
        successfully -- the failure for that belongs at resolution time, as
        `CREDENTIAL_UNSUPPORTED`. Rejecting it here would misreport an
        unimplemented mechanism as a malformed configuration.
        """
        if not isinstance(ref, str):
            raise CredentialConfigError(
                f"credential ref must be a string, got {type(ref).__name__}"
            )

        raw = ref.strip()
        if not raw:
            raise CredentialConfigError("credential ref is empty")

        if ":" not in raw:
            # No scheme separator: this is a bare credential value.
            # Contract §5.3 marks this FORBIDDEN; §10.3 rejects it at
            # configuration/schema validation.
            raise CredentialConfigError(
                "credential ref looks like a literal value; refs must use "
                "'<scheme>:<target>' (literal values are forbidden)"
            )

        scheme, _, target = raw.partition(":")
        scheme = scheme.strip().lower()

        if scheme in SUPPORTED_SCHEMES:
            name = target.strip()
            if not name:
                raise CredentialConfigError(
                    f"malformed '{scheme}:' ref: missing target"
                )
            if not _VAR_NAME_RE.match(name):
                raise CredentialConfigError(
                    f"malformed '{scheme}:' ref: {name!r} is not a valid variable name"
                )
            return cls(scheme=scheme, target=name)

        # Reserved or unknown scheme: shape is fine, mechanism is absent.
        # Reported at resolution time as CREDENTIAL_UNSUPPORTED.
        return cls(scheme=scheme, target=target.strip())


def resolve(ref: CredentialRef, *, environ: Mapping[str, str] | None = None) -> SecretValue:
    """Resolve a parsed reference to a credential value.

    Raises `CredentialError(CREDENTIAL_UNSUPPORTED)` for an unimplemented
    scheme, and `CredentialError(CREDENTIAL_MISSING)` when the environment
    variable is unset, empty, or whitespace.

    Both are raised before any network attempt. A missing credential is never
    resolved by trying anyway, and an unsupported scheme is never resolved by
    guessing at the reference (§10.5).
    """
    if not ref.is_supported:
        raise CredentialError(
            ErrorClass.CREDENTIAL_UNSUPPORTED,
            f"credential scheme {ref.scheme!r} is not implemented "
            f"(supported: {', '.join(sorted(SUPPORTED_SCHEMES))})",
        )

    source = os.environ if environ is None else environ
    value = source.get(ref.target)

    # Unset, empty, and whitespace are the same failure (§5.3).
    if value is None or not value.strip():
        raise CredentialError(
            ErrorClass.CREDENTIAL_MISSING,
            f"credential {ref} is unset or empty",
        )

    return SecretValue(value)


def resolve_ref(ref: object, *, environ: Mapping[str, str] | None = None) -> SecretValue:
    """Parse and resolve in one step, for callers holding a raw reference."""
    return resolve(CredentialRef.parse(ref), environ=environ)


#: Exposed for tests and documentation: the reference grammar, verbatim.
REFERENCE_GRAMMAR: Mapping[str, str] = MappingProxyType(
    {
        "env": "supported (v1)",
        "file": "reserved",
        "keyring": "reserved",
        "vault": "reserved",
        "literal": "forbidden",
    }
)
