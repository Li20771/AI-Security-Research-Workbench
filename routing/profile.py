"""What AI-07 reads from AI-02. Contract §6.

**AI-07 defines none of this.** There is no `RouterModelProfile`, no
`RouterProvider`, no `RouterCapability` and no `RouterRegistry`: every name below
is imported from `providers`, because two definitions of one vocabulary means one
of them is eventually forgotten (§6.1).

### The rule the whole phase turns on — §6.2

```text
FROZEN: `UNKNOWN` is NOT `available`.
        Only VERIFIED satisfies a capability requirement.
```

Every capability on every shipped profile is `UNKNOWN`, and no provider call has
ever been made in this repository. So a request that requires a capability has no
eligible candidate in v1, and the outcome is `NO_ELIGIBLE_MODEL`. That is the
design, not a defect: reading `UNKNOWN` as "probably fine" would make the Router
select on claims nobody tested, and would make the first model it picked look
verified by having been picked. AI-00 F-10 outranks model confidence.
"""

from __future__ import annotations

from typing import Mapping

from providers.model_profile import (
    CapabilityName,
    CapabilityStatus,
    ModelProfile,
    Modality,
)

__all__ = [
    "CapabilityName",
    "CapabilityStatus",
    "ModelProfile",
    "Modality",
    "capability_is_available",
    "input_modalities",
    "modality_satisfies",
]


def capability_is_available(profile: ModelProfile, name: CapabilityName) -> bool:
    """Whether this profile's status for `name` is `VERIFIED`. Contract §6.2.

    A one-line function, and it is one line on purpose: this is the single place
    the answer to "may this capability be relied on" is decided, so there is one
    place to audit and one place for a reviewer to change.

    `UNKNOWN`, `DECLARED`, `NOT_VERIFIED` and `UNAVAILABLE` all return `False`.
    There is deliberately no "probably" branch.
    """
    return profile.capability(CapabilityName(name)).status is CapabilityStatus.VERIFIED


def input_modalities(profile: ModelProfile) -> tuple[str, ...]:
    """The input modalities this profile declares. AI-02's `Modality`, read only.

    AI-02 defines no `multimodal` capability, so a modality requirement is
    matched here rather than against a capability the model layer does not have
    (§6.3). The names come from the profile, never from a display name, a family
    or a provider — none of which is a modality.
    """
    return tuple(profile.modality.input)


def modality_satisfies(profile: ModelProfile, requested: str) -> bool:
    """Whether every requested modality is one the profile declares as input."""
    return requested in input_modalities(profile)
