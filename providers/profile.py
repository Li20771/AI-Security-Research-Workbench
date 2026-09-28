"""Provider profile types.

Implements AI-02 contract §5.1 (identity), §5.2 (endpoint), §5.4 (protocol),
§5.5 (in-scope profiles) and §5.7 (supported-model exposure).

Provider profiles are reviewable repository data under `providers/<id>/`, not
runtime-editable config (D-1). Runtime config selects, enables, and overrides;
it never redefines identity or protocol facts.

Model *capability* metadata is deliberately absent. It belongs to AI-02-B2;
this module carries only the model reference, which is what a provider needs
to expose the models it can serve (§5.7, task §18).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from providers.credential import CredentialConfigError, CredentialRef

#: Stable machine identity: lowercase, no version, no spaces (§5.1).
#: `-` and `_` are permitted as internal separators, so the pre-existing
#: `openai-compatible` config key and directory name stay valid. Leading,
#: trailing, and doubled separators are rejected.
PROVIDER_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$")

#: Endpoint provenance. `declared` until AI-02-B6 observes it (§5.2).
ENDPOINT_SOURCES: frozenset[str] = frozenset({"declared", "verified", "override"})

_ALLOWED_URL_SCHEMES = ("https://", "http://")


class ProfileError(ValueError):
    """A provider profile is malformed. A configuration defect, not an ErrorClass."""


@dataclass(frozen=True, slots=True)
class ModelRef:
    """A `provider_id/model_id` reference.

    The minimal reference type permitted in AI-02-B1 (task §18). It carries no
    capability metadata -- that is AI-02-B2's deliverable.
    """

    provider_id: str
    model_id: str

    def __str__(self) -> str:
        return f"{self.provider_id}/{self.model_id}"

    @classmethod
    def parse(cls, raw: object) -> "ModelRef":
        if not isinstance(raw, str):
            raise ProfileError(f"model ref must be a string, got {type(raw).__name__}")
        text = raw.strip()
        if not text:
            raise ProfileError("model ref is empty")
        if text.count("/") != 1:
            raise ProfileError(
                f"model ref {text!r} must be exactly '<provider_id>/<model_id>'"
            )
        provider_id, _, model_id = text.partition("/")

        # Checked before stripping: the surrounding whitespace on `text` is
        # already gone, so whitespace here is internal and therefore a defect
        # in the separator (`'a /b'`, `'a/ b'`). Stripping first would hide it.
        if any(ch.isspace() for ch in provider_id + model_id):
            raise ProfileError(
                f"model ref {text!r} must not contain whitespace around '/'"
            )
        if not provider_id or not model_id:
            raise ProfileError(
                f"model ref {text!r} must name both a provider and a model"
            )
        return cls(provider_id=provider_id, model_id=model_id)


@dataclass(frozen=True, slots=True)
class Protocol:
    """Wire protocol family and revision (§5.4).

    `family` names the protocol, not the vendor. Both in-scope providers
    declare `openai_compatible_chat`.
    """

    family: str
    version: str

    def __post_init__(self) -> None:
        if not self.family or not self.family.strip():
            raise ProfileError("protocol.family must not be empty")
        if not self.version or not self.version.strip():
            raise ProfileError("protocol.version must not be empty")

    def to_dict(self) -> dict[str, str]:
        return {"family": self.family, "version": self.version}


@dataclass(frozen=True, slots=True)
class Endpoint:
    """A declared provider endpoint (§5.2).

    `base_url` and `path_template` are stored separately and composed by
    `effective_url`. No shared URL prefix is assumed, and `/v1` is never
    inserted -- the two in-scope providers declare different base URL shapes.
    """

    base_url: str
    path_template: str
    source: str = "declared"
    verified_at: str | None = None
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        base = (self.base_url or "").strip()
        if not any(base.startswith(s) for s in _ALLOWED_URL_SCHEMES):
            raise ProfileError(
                f"endpoint.base_url must be http(s), got {self.base_url!r}"
            )
        if "@" in base:
            # userinfo would embed a credential in the URL; §5.2 forbids it.
            raise ProfileError(
                "endpoint.base_url must not contain userinfo; the credential is "
                "never part of the URL"
            )
        if "?" in base or "#" in base:
            raise ProfileError(
                "endpoint.base_url must not contain a query or fragment"
            )

        path = (self.path_template or "").strip()
        if not path:
            raise ProfileError("endpoint.path_template must not be empty")
        if "?" in path or "#" in path:
            raise ProfileError(
                "endpoint.path_template must not contain a query or fragment"
            )

        if self.source not in ENDPOINT_SOURCES:
            raise ProfileError(
                f"endpoint.source must be one of {sorted(ENDPOINT_SOURCES)}, "
                f"got {self.source!r}"
            )

        object.__setattr__(self, "base_url", base.rstrip("/"))
        object.__setattr__(self, "path_template", "/" + path.strip("/"))

    @property
    def effective_url(self) -> str:
        """`base_url` + `path_template`.

        Composition only. Nothing is inferred and no prefix is injected, so
        DeepSeek (`https://api.deepseek.com`) and MiMo
        (`https://api.xiaomimimo.com/v1`) each produce exactly the URL their
        own declaration implies.
        """
        return f"{self.base_url}{self.path_template}"

    @property
    def is_verified(self) -> bool:
        """True only when AI-02-B6 observed this endpoint."""
        return self.source == "verified" and self.verified_at is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "path_template": self.path_template,
            "source": self.source,
            "verified_at": self.verified_at,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True, slots=True)
class CredentialSpec:
    """A credential *reference* and its metadata (§5.3).

    Construction validates the reference shape, so a literal credential value
    cannot be represented by this type at all.
    """

    ref: str
    kind: str = "api_key"
    required: bool = True

    def __post_init__(self) -> None:
        # Raises CredentialConfigError for a literal value or a malformed ref.
        CredentialRef.parse(self.ref)
        if not isinstance(self.required, bool):
            raise ProfileError(
                f"credential.required must be a bool, got {type(self.required).__name__}"
            )

    @property
    def parsed(self) -> CredentialRef:
        return CredentialRef.parse(self.ref)

    def to_dict(self) -> dict[str, Any]:
        return {"ref": self.ref, "kind": self.kind, "required": self.required}


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    """A provider profile (§5.1 - §5.7).

    Carries identity, protocol, endpoint, credential reference, and the model
    references the provider exposes. It carries no capability claims, no
    credential value, and **no transport settings**.

    Transport settings are runtime config, not profile data (§5.11), so they
    live in `config/providers/*.yaml` and are supplied to the adapter
    explicitly. Keeping them out of this type is what makes the layering
    enforceable rather than merely documented.
    """

    provider_id: str
    display_name: str
    protocol: Protocol
    endpoint: Endpoint
    credential: CredentialSpec
    models: tuple[ModelRef, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not PROVIDER_ID_RE.match(self.provider_id or ""):
            raise ProfileError(
                f"provider_id {self.provider_id!r} must match "
                f"{PROVIDER_ID_RE.pattern} (lowercase, no version, no spaces)"
            )
        if not (self.display_name or "").strip():
            raise ProfileError("display_name must not be empty")

        for ref in self.models:
            if ref.provider_id != self.provider_id:
                raise ProfileError(
                    f"model ref {ref} names provider {ref.provider_id!r}, but this "
                    f"profile is {self.provider_id!r}"
                )

    @property
    def model_refs(self) -> tuple[str, ...]:
        return tuple(str(ref) for ref in self.models)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "protocol": self.protocol.to_dict(),
            "endpoint": self.endpoint.to_dict(),
            "credential": self.credential.to_dict(),
            "models": list(self.model_refs),
        }


__all__ = [
    "CredentialConfigError",
    "CredentialSpec",
    "Endpoint",
    "ModelRef",
    "ProfileError",
    "Protocol",
    "ProviderProfile",
]
