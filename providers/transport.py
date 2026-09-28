"""Transport settings shape and validation.

Implements AI-02 contract §5.11.

A timeout is always explicit: there is no unbounded or default-infinite
request. `max_retries` defaults to 0 (D-12) and must never be negative; the
field is frozen so AI-13 can consume it, but AI-02 implements no retry loop,
so a non-zero value here is inert.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Frozen defaults (contract §5.11).
DEFAULT_TIMEOUT_CONNECT_MS = 10_000
DEFAULT_TIMEOUT_TOTAL_MS = 120_000

#: AI-02 implements no retry loop (D-12). Any other value is inert.
AI02_MAX_RETRIES = 0


class TransportConfigError(ValueError):
    """Invalid transport settings. A configuration defect, not an ErrorClass."""


def _positive_ms(value: object, field_name: str) -> int:
    """Validate a millisecond timeout.

    Rejects `None`, booleans, non-numerics, non-finite values (inf/nan), and
    non-positive values -- each of which would produce an unbounded or
    implicit-infinite deadline.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransportConfigError(
            f"{field_name} must be a number of milliseconds, got {type(value).__name__}"
        )
    if not math.isfinite(value):
        raise TransportConfigError(
            f"{field_name} must be finite; unbounded timeouts are not permitted"
        )
    if value <= 0:
        raise TransportConfigError(
            f"{field_name} must be > 0; got {value} "
            "(a non-positive timeout is not an unbounded timeout)"
        )
    if float(value) != int(value):
        raise TransportConfigError(
            f"{field_name} must be whole milliseconds, got {value}"
        )
    return int(value)


@dataclass(frozen=True, slots=True)
class TransportSettings:
    """Transport configuration for one provider profile.

    Attributes:
        timeout_connect_ms: connection establishment deadline.
        timeout_total_ms: hard deadline covering the whole call.
        max_retries: reserved for AI-13; 0 in AI-02.
        verify_tls: TLS verification. Disabling it is a security-relevant
            change requiring explicit human approval (contract §5.11).
    """

    timeout_connect_ms: int = DEFAULT_TIMEOUT_CONNECT_MS
    timeout_total_ms: int = DEFAULT_TIMEOUT_TOTAL_MS
    max_retries: int = AI02_MAX_RETRIES
    verify_tls: bool = True

    def __post_init__(self) -> None:
        connect = _positive_ms(self.timeout_connect_ms, "timeout_connect_ms")
        total = _positive_ms(self.timeout_total_ms, "timeout_total_ms")

        if total < connect:
            raise TransportConfigError(
                f"timeout_total_ms ({total}) must be >= timeout_connect_ms ({connect}); "
                "a total deadline shorter than the connect deadline is incoherent"
            )

        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int):
            raise TransportConfigError(
                f"max_retries must be an integer, got {type(self.max_retries).__name__}"
            )
        if self.max_retries < 0:
            raise TransportConfigError(
                f"max_retries must be >= 0, got {self.max_retries}"
            )

        if not isinstance(self.verify_tls, bool):
            raise TransportConfigError(
                f"verify_tls must be a bool, got {type(self.verify_tls).__name__}"
            )

        # Normalize integral floats to int so equality and hashing are stable.
        object.__setattr__(self, "timeout_connect_ms", connect)
        object.__setattr__(self, "timeout_total_ms", total)

    @property
    def retries_are_inert(self) -> bool:
        """True when `max_retries` cannot take effect in AI-02."""
        return self.max_retries != AI02_MAX_RETRIES

    def to_dict(self) -> dict[str, object]:
        return {
            "timeout_connect_ms": self.timeout_connect_ms,
            "timeout_total_ms": self.timeout_total_ms,
            "max_retries": self.max_retries,
            "verify_tls": self.verify_tls,
        }

    @classmethod
    def from_mapping(cls, data: object) -> "TransportSettings":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise TransportConfigError(
                f"transport must be a mapping, got {type(data).__name__}"
            )
        unknown = set(data) - {
            "timeout_connect_ms",
            "timeout_total_ms",
            "max_retries",
            "verify_tls",
        }
        if unknown:
            raise TransportConfigError(
                f"unknown transport field(s): {', '.join(sorted(unknown))}"
            )
        return cls(**data)
