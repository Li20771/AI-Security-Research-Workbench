"""Model profile types.

Implements AI-02 contract §6 (model profile contract) and §8 (capability truth
model), frozen in `docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md`.

A model profile describes **one model available from one provider**, keyed by
`provider_id/model_id`. It is separate from a provider profile (AI-02-B1):

    Provider profile   identity, protocol, endpoint, credential, model refs
    Model profile      model identity, limits, modality, capabilities

The split is structural. A provider profile cannot carry a capability, and a
model profile cannot carry an endpoint, a credential, transport settings, or an
`enabled` flag. Anything a capability describes is a claim about a *model*, and
capability claims are exactly what this contract refuses to assert without
evidence.

Two rules dominate this module:

**Unknown is not false.** A limit nobody has measured is `None`, and a
capability nobody has checked is `UNKNOWN` -- never `0`, never `False`. A zero
is a measurement, and a wrong measurement is worse than an absent one.

**Declared is not verified.** The truth model (§8) keeps two axes. What a
vendor claims and what the Workbench has observed are recorded separately and
never collapsed into one boolean. AI-02-B2 produces no `VERIFIED` capability:
only AI-02-B6 may promote one, and only from a dated observation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterator

from providers.profile import PROVIDER_ID_RE, ModelRef, ProfileError

#: `model_id` is passed verbatim to the provider: no whitespace, no control
#: characters, no separator that would collide with the model-ref `/`.
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]*$")

#: Modality values are recorded as declared strings. Deliberately not a closed
#: vocabulary: §6.6 names only `text` for v1, and inventing a wider one would
#: prejudge modalities the contract has not defined.
_MODALITY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ModelProfileError(ValueError):
    """A model profile is malformed. A configuration defect, not an ErrorClass."""


class CapabilityStatus(StrEnum):
    """The capability truth model (contract §8.1). Frozen.

    Relationship to the repository truth model:

        VERIFIED      ~ PASS       executed, evidenced, positive
        UNAVAILABLE   ~ FAIL       executed, evidenced, negative
        NOT_VERIFIED  ~ BLOCKED    attempted, no conclusive evidence
        DECLARED      ~ (none)     documented only, no Workbench execution
        UNKNOWN       ~ UNKNOWN    nothing known

    `DECLARED` never auto-promotes to `VERIFIED`, and `UNKNOWN` is neither
    `False` nor `UNAVAILABLE`.
    """

    DECLARED = "DECLARED"
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class CapabilityName(StrEnum):
    """The five capabilities a model profile records (§6.1)."""

    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    REASONING = "reasoning"
    PROMPT_CACHING = "prompt_caching"


class StructuredOutputMode(StrEnum):
    """Declared structured-output support level (§6.7).

    More than a boolean, because the levels are not interchangeable:
    `json_object` guarantees JSON but **not** schema conformance, so a consumer
    must validate the output rather than trust it.
    """

    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"
    NONE = "none"


def _require_optional_bool(value: object, field_name: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value  # type: ignore[return-value]
    raise ModelProfileError(
        f"{field_name} must be true, false, or null; got {type(value).__name__}"
    )


def _require_optional_str(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ModelProfileError(
            f"{field_name} must be a string or null; got {type(value).__name__}"
        )
    return value


@dataclass(frozen=True, slots=True)
class CapabilityEntry:
    """One capability, recorded on two axes (§6.7, §8.2).

    `declared` and `verified` answer different questions and are never
    collapsed: a capability can be declared without being verified, verified
    without having been declared, or neither.

    Attributes:
        status: the frozen five-state truth model.
        declared: what an external source claims, or `None` if nobody claimed.
        verified: what the Workbench observed, or `None` if not observed.
        source: where the claim or the observation came from.
        mode: structured-output support level. Only meaningful for
            `structured_output`; `None` elsewhere.
    """

    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    declared: bool | None = None
    verified: bool | None = None
    source: str | None = None
    mode: StructuredOutputMode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CapabilityStatus):
            raise ModelProfileError(
                f"capability status must be one of "
                f"{[s.value for s in CapabilityStatus]}; got {self.status!r}"
            )
        _require_optional_bool(self.declared, "declared")
        _require_optional_bool(self.verified, "verified")
        _require_optional_str(self.source, "source")

        if self.mode is not None and not isinstance(self.mode, StructuredOutputMode):
            raise ModelProfileError(
                f"structured_output mode must be one of "
                f"{[m.value for m in StructuredOutputMode]}; got {self.mode!r}"
            )

        # `verified: true` is only meaningful as VERIFIED. Anything else would
        # let an unverified capability look observed (§8.3).
        if self.verified is True and self.status is not CapabilityStatus.VERIFIED:
            raise ModelProfileError(
                f"verified=true is only valid with status VERIFIED; "
                f"got status {self.status.value}"
            )

        if self.status is CapabilityStatus.UNKNOWN:
            # §6.8: no claim and no observation. Not "false".
            if self.declared is not None or self.verified is not None:
                raise ModelProfileError(
                    "status UNKNOWN requires declared=null and verified=null; "
                    "an asserted claim is not an unknown"
                )
            if self.source is not None:
                raise ModelProfileError("status UNKNOWN requires source=null")

        elif self.status is CapabilityStatus.DECLARED:
            # §13: declared, with a source, and explicitly not verified.
            if self.declared is not True:
                raise ModelProfileError("status DECLARED requires declared=true")
            if self.verified is True:
                raise ModelProfileError("status DECLARED must not be verified=true")
            if not self.source:
                raise ModelProfileError(
                    "status DECLARED requires a non-empty source; a claim without "
                    "a source is not a declared capability"
                )

        elif self.status is CapabilityStatus.NOT_VERIFIED:
            # Verification was attempted and was inconclusive (§8.1).
            if self.verified is True:
                raise ModelProfileError(
                    "status NOT_VERIFIED must not be verified=true"
                )
            if not self.source:
                raise ModelProfileError(
                    "status NOT_VERIFIED requires a non-empty source recording "
                    "where the attempted check came from"
                )

        elif self.status is CapabilityStatus.UNAVAILABLE:
            # Observed absent. A negative observation is still an observation.
            if self.verified is not False:
                raise ModelProfileError(
                    "status UNAVAILABLE requires verified=false; it is a negative "
                    "observation, not an absence of one"
                )
            if not self.source:
                raise ModelProfileError(
                    "status UNAVAILABLE requires a non-empty source recording "
                    "the negative observation"
                )

        # VERIFIED is validated at profile level: it also requires provenance
        # `verified_at` and `evidence_ref`, which live on the profile (§13).

    @property
    def is_unknown(self) -> bool:
        return self.status is CapabilityStatus.UNKNOWN

    @property
    def is_verified(self) -> bool:
        return self.status is CapabilityStatus.VERIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "declared": self.declared,
            "verified": self.verified,
            "status": str(self.status),
            "source": self.source,
            "mode": str(self.mode) if self.mode is not None else None,
        }


def _default_entry() -> CapabilityEntry:
    """The honest default: nothing claimed, nothing observed (§6.1)."""
    return CapabilityEntry(
        status=CapabilityStatus.UNKNOWN,
        declared=None,
        verified=None,
        source=None,
    )


@dataclass(frozen=True, slots=True)
class Capabilities:
    """The five capability entries of a model profile (§6.1).

    Named fields rather than a mapping, so a missing capability is a
    construction error rather than a silent `KeyError` at read time.
    """

    tool_calling: CapabilityEntry = field(default_factory=_default_entry)
    structured_output: CapabilityEntry = field(default_factory=_default_entry)
    streaming: CapabilityEntry = field(default_factory=_default_entry)
    reasoning: CapabilityEntry = field(default_factory=_default_entry)
    prompt_caching: CapabilityEntry = field(default_factory=_default_entry)

    def __post_init__(self) -> None:
        for name in CapabilityName:
            entry = self.get(name)
            if not isinstance(entry, CapabilityEntry):
                raise ModelProfileError(
                    f"{name.value} must be a CapabilityEntry, "
                    f"got {type(entry).__name__}"
                )
            # `mode` describes structured output only (§6.7).
            if name is not CapabilityName.STRUCTURED_OUTPUT and entry.mode is not None:
                raise ModelProfileError(
                    f"{name.value} must not carry a mode; it is a "
                    "structured_output field"
                )

    def get(self, name: CapabilityName) -> CapabilityEntry:
        return getattr(self, str(name))

    def items(self) -> Iterator[tuple[CapabilityName, CapabilityEntry]]:
        for name in CapabilityName:
            yield name, self.get(name)

    def to_dict(self) -> dict[str, Any]:
        return {name.value: entry.to_dict() for name, entry in self.items()}


@dataclass(frozen=True, slots=True)
class Limits:
    """Declared context and output limits (§6.5).

    `None` means **unknown**, never zero. A wrong limit is materially worse
    than an absent one, so nothing here is ever defaulted or inferred.
    """

    context_limit: int | None = None
    max_output: int | None = None

    def __post_init__(self) -> None:
        for name in ("context_limit", "max_output"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise ModelProfileError(
                    f"{name} must be an integer or null; got {type(value).__name__}"
                )
            if value <= 0:
                raise ModelProfileError(
                    f"{name} must be > 0 or null; got {value}. An unknown limit is "
                    "null, and a non-positive one is not a limit"
                )

    @property
    def are_unknown(self) -> bool:
        return self.context_limit is None and self.max_output is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_limit": self.context_limit,
            "max_output": self.max_output,
        }


@dataclass(frozen=True, slots=True)
class Modality:
    """Input and output modality sets (§6.6). A set, not a scalar."""

    input: tuple[str, ...] = ("text",)
    output: tuple[str, ...] = ("text",)

    def __post_init__(self) -> None:
        for name in ("input", "output"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or not values:
                raise ModelProfileError(
                    f"modality.{name} must be a non-empty list of modality names"
                )
            if len(set(values)) != len(values):
                raise ModelProfileError(f"modality.{name} must not repeat a value")
            for value in values:
                if not isinstance(value, str) or not _MODALITY_RE.match(value):
                    raise ModelProfileError(
                        f"modality.{name} value {value!r} must be a lowercase "
                        "identifier such as 'text'"
                    )

    def to_dict(self) -> dict[str, Any]:
        return {"input": list(self.input), "output": list(self.output)}


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a profile's claims and observations came from (§6.8).

    All four fields are `None` until something is actually declared or
    observed. Nothing here is ever fabricated: a `verified_at` without an
    observation would be a false record.
    """

    declared_source: str | None = None
    declared_at: str | None = None
    verified_at: str | None = None
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        for name in ("declared_source", "declared_at", "verified_at", "evidence_ref"):
            _require_optional_str(getattr(self, name), name)

    @property
    def has_declaration(self) -> bool:
        return self.declared_source is not None

    @property
    def has_verification(self) -> bool:
        return self.verified_at is not None and self.evidence_ref is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "declared_source": self.declared_source,
            "declared_at": self.declared_at,
            "verified_at": self.verified_at,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """A model profile (§6.1 - §6.8).

    Carries model identity, declared limits, modality, capability truth state,
    and provenance. It carries no endpoint, no credential, no transport
    settings, and no enablement flag -- those belong to the provider profile
    and to runtime config respectively.
    """

    model_ref: str
    provider_id: str
    model_id: str
    display_name: str
    family: str
    version: str
    limits: Limits = field(default_factory=Limits)
    modality: Modality = field(default_factory=Modality)
    capabilities: Capabilities = field(default_factory=Capabilities)
    provenance: Provenance = field(default_factory=Provenance)

    def __post_init__(self) -> None:
        if not PROVIDER_ID_RE.match(self.provider_id or ""):
            raise ModelProfileError(
                f"provider_id {self.provider_id!r} is not a valid provider id"
            )
        if not self.model_id or not _MODEL_ID_RE.match(self.model_id):
            raise ModelProfileError(
                f"model_id {self.model_id!r} must be a non-empty identifier; it is "
                "sent to the provider verbatim"
            )
        for name, value in (("display_name", self.display_name), ("family", self.family)):
            if not value or not value.strip():
                raise ModelProfileError(f"{name} must not be empty")
        if not isinstance(self.version, str) or not self.version.strip():
            # A YAML `version: 4.1` parses as a float; require the quoted form
            # rather than silently reinterpreting it.
            raise ModelProfileError(
                f"version must be a non-empty string; got {self.version!r}. "
                "Quote it in YAML (version: \"4.1\") so it is not parsed as a number"
            )

        expected_ref = f"{self.provider_id}/{self.model_id}"
        if self.model_ref != expected_ref:
            raise ModelProfileError(
                f"model_ref {self.model_ref!r} must equal "
                f"'{expected_ref}' (provider_id/model_id)"
            )

        # Cross-field rule that needs provenance, so it lives here rather than
        # on CapabilityEntry (§13).
        for name, entry in self.capabilities.items():
            if entry.status is CapabilityStatus.VERIFIED:
                if entry.verified is not True:
                    raise ModelProfileError(
                        f"{name.value}: status VERIFIED requires verified=true"
                    )
                if not self.provenance.verified_at or not self.provenance.evidence_ref:
                    raise ModelProfileError(
                        f"{name.value}: status VERIFIED requires provenance "
                        "verified_at and evidence_ref; a verification without a "
                        "dated observation and evidence is not a verification"
                    )

    @property
    def provider_ref(self) -> ModelRef:
        return ModelRef(provider_id=self.provider_id, model_id=self.model_id)

    @property
    def has_verified_capability(self) -> bool:
        return any(entry.is_verified for _, entry in self.capabilities.items())

    def capability(self, name: CapabilityName) -> CapabilityEntry:
        return self.capabilities.get(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_ref": self.model_ref,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "family": self.family,
            "version": self.version,
            "limits": self.limits.to_dict(),
            "modality": self.modality.to_dict(),
            "capabilities": self.capabilities.to_dict(),
            "provenance": self.provenance.to_dict(),
        }


__all__ = [
    "Capabilities",
    "CapabilityEntry",
    "CapabilityName",
    "CapabilityStatus",
    "Limits",
    "ModelProfile",
    "ModelProfileError",
    "Modality",
    "ProfileError",
    "Provenance",
    "StructuredOutputMode",
]
