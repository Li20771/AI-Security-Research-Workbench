"""The closed vocabularies AI-06 owns, and the ones it imports.

Contract §5.3, §6.3, §8.2 and §15.3.

**AI-06 owns exactly two vocabularies**, both new here:

```text
AdapterFamily   git | github | tests | terminal | mcp | vehicle_network |
                firmware | reverse_engineering
ToolOutcome     COMPLETED | FAILED | BLOCKED | NOT_RUN | TIMED_OUT | UNKNOWN
```

**Everything else is imported and not restated.** `PermissionLevel`, `TargetKind`,
`TargetEnvironment`, `TargetInterface`, `TargetSensitivity`, `GuardDecision`,
`ActorType` and the whole request/decision model come from AI-04, because AI-06's
request is built to be handed to AI-04's evaluator and two definitions of one
vocabulary means one of them is eventually forgotten. `StatusValue` comes from
AI-03, and AI-06 imports it rather than inventing a fifth status vocabulary for
the Evidence projection to land in.

### The three vocabularies stay distinct — contract §6.3

```text
ToolOutcome       did the operation execute           AI-06 owns it
GuardDecision     may the operation proceed           AI-04 owns it
StatusValue       what is the state of this item      AI-03 owns it
```

`BLOCKED` and `UNKNOWN` appear in more than one of them. That is a known cost,
recorded by AI-04 §3 as a defect AI-03 already paid for once. AI-06 does not
merge the vocabularies to remove it — it keeps the types distinct, so that a
reader can always tell which question a value answers.
"""

from __future__ import annotations

from enum import StrEnum

# Frozen elsewhere, imported, never redefined (contract §3.4, §6.1).
from plugins.context.vocabulary import StatusValue  # noqa: F401  (re-exported)
from plugins.guard.vocabulary import (  # noqa: F401  (re-exported)
    ActorType,
    GuardDecision,
    PermissionLevel,
    TargetEnvironment,
    TargetInterface,
    TargetKind,
    TargetSensitivity,
)


class AdapterFamily(StrEnum):
    """The eight adapter families (contract §5.3). Closed. Owned by AI-06.

    A transcription of `docs/MASTER_ROADMAP.md` §1.1 rather than a choice:

        "The first-class tool adapter families are Git, GitHub, Terminal, MCP,
         Tests, Vehicle Network, Firmware, and Reverse Engineering. The Security
         Tools plugin composes these adapters."

    The spellings are lowercased into identifiers so that each member names
    exactly one package under `tools/`. A ninth family requires an amendment.
    """

    GIT = "git"
    GITHUB = "github"
    TESTS = "tests"
    TERMINAL = "terminal"
    MCP = "mcp"
    VEHICLE_NETWORK = "vehicle_network"
    FIRMWARE = "firmware"
    REVERSE_ENGINEERING = "reverse_engineering"


class ToolOutcome(StrEnum):
    """What AI-06 says about an invocation (contract §8.2). Closed. Six members.

    **A ToolOutcome is a claim by the adapter about the OPERATION.** It is never
    a claim about the research question. AI-05 §26 states the rule AI-06
    inherits: *"A tool's own claim of success is a claim with a producer. AI-05
    records the claim and its producer. It adjudicates nothing."*

    Deliberately absent: `PASS`, `FAIL`, `SUCCESS`, `DENIED`, `VERIFIED` and any
    other name that would let `exit_code == 0` be read as a research conclusion.
    """

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    TIMED_OUT = "TIMED_OUT"
    UNKNOWN = "UNKNOWN"


class FilesystemAccess(StrEnum):
    """What an operation needs of a filesystem (contract §7.2)."""

    NONE = "none"
    READ = "read"
    WRITE = "write"


class VehicleInterface(StrEnum):
    """What an operation needs of a vehicle interface (contract §7.2).

    `PHYSICAL` exists so that an operation can *declare* it and be refused at
    registration; there is no v1 operation that legitimately needs it (§12.2).
    """

    NONE = "none"
    VCAN = "vcan"
    SIMULATOR = "simulator"
    ISOLATED_HARNESS = "isolated_harness"
    PHYSICAL = "physical"


#: The interfaces v1 may reach (contract §12.1). Anything else is refused.
V1_PERMITTED_VEHICLE_INTERFACES: frozenset[VehicleInterface] = frozenset(
    {
        VehicleInterface.VCAN,
        VehicleInterface.SIMULATOR,
        VehicleInterface.ISOLATED_HARNESS,
    }
)

#: The targets v1 may reach, by AI-04's classification (contract §12.1).
V1_PERMITTED_TARGET_ENVIRONMENTS: frozenset[TargetEnvironment] = frozenset(
    {
        TargetEnvironment.SIMULATED,
        TargetEnvironment.ISOLATED,
    }
)

#: The outcome projection (contract §15.3). Total and one-way.
#:
#: The cost is recorded rather than hidden: `StatusValue` has no `TIMED_OUT`, so
#: a timed-out operation is recorded as `FAIL` and the fact that it was stopped
#: is carried by the `ToolResult`, which is not the record.
OUTCOME_TO_STATUS: dict[ToolOutcome, StatusValue] = {
    ToolOutcome.COMPLETED: StatusValue.PASS,
    ToolOutcome.FAILED: StatusValue.FAIL,
    ToolOutcome.TIMED_OUT: StatusValue.FAIL,
    ToolOutcome.BLOCKED: StatusValue.BLOCKED,
    ToolOutcome.NOT_RUN: StatusValue.NOT_RUN,
    ToolOutcome.UNKNOWN: StatusValue.UNKNOWN,
}


def status_for(outcome: ToolOutcome) -> StatusValue:
    """The one place the two vocabularies meet (contract §6.3, §15.3).

    Total by construction: `OUTCOME_TO_STATUS` has a row for every member, and a
    test asserts that against `ToolOutcome` itself rather than against a copy.

    There is deliberately **no inverse**. Nothing converts a `StatusValue` back
    into a `ToolOutcome`, and the contract forbids adding one.
    """
    return OUTCOME_TO_STATUS[ToolOutcome(outcome)]


__all__ = [
    "ADMITTED_FAMILIES",
    "ActorType",
    "AdapterFamily",
    "FilesystemAccess",
    "GuardDecision",
    "OUTCOME_TO_STATUS",
    "PermissionLevel",
    "StatusValue",
    "TargetEnvironment",
    "TargetInterface",
    "TargetKind",
    "TargetSensitivity",
    "ToolOutcome",
    "V1_PERMITTED_TARGET_ENVIRONMENTS",
    "V1_PERMITTED_VEHICLE_INTERFACES",
    "VehicleInterface",
    "status_for",
]

#: Alias kept for readability at call sites that name the frozen set.
ADMITTED_FAMILIES = frozenset(AdapterFamily)
