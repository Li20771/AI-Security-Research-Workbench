"""AI-11 §5, §6, §8, §9, §14, §22 — the closed vocabularies AI-11 owns.

Five closed vocabularies and one precedence table, and nothing else:

```text
OracleVerdict            six members    AI-11's own decision vocabulary (§8.1)
SecurityBoundaryStatus   six members    AI-11's second, independent axis (§14.2)
ExecutorKind             two members    AGENT | REFERENCE (§6.1, §20.4)
TaskFamily               six members    the v1 corpus families (§17.1)
Difficulty               three members  an ordinal label, never a score (§5.5)
ProvenanceClass          three members  MEASURED | DOCUMENTED | STATIC (§9.1)
```

**Nothing frozen elsewhere is restated.** `AgentId` and `AgentExecutionOutcome` are
imported from AI-08 where they are used, and `ToolOutcome` from AI-06. Redefining one
would put two definitions of one vocabulary in the repository — the defect AI-04 §28.2
names and AI-05 §7.1 paid for once already.

### The words that collide, recorded rather than repaired

`BLOCKED` appears in `GuardDecision`, `ToolOutcome`, `AgentExecutionOutcome`,
`ReviewCaseState` and now in `OracleVerdict` and `SecurityBoundaryStatus`. `UNKNOWN`
appears in five of those too. That is the known cost AI-04 §3 recorded and AI-07 §10.1,
AI-08 §11.2 and AI-10 §5 each inherited.

AI-11 does not remove it by merging the types. `OracleVerdict.BLOCKED` is NOT
`ToolOutcome.BLOCKED`, NOT `AgentExecutionOutcome.BLOCKED` and NOT
`SecurityBoundaryStatus.BLOCKED`, and none may be compared to, stored in one field with,
or converted into another.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Mapping

__all__ = [
    "DIFFICULTY_ORDER",
    "LIMITATION_REASON_PREFIXES",
    "ORACLE_VERDICT_PRECEDENCE",
    "SECURITY_BOUNDARY_PRECEDENCE",
    "Difficulty",
    "ExecutorKind",
    "LimitationCode",
    "OracleKind",
    "OracleVerdict",
    "ProvenanceClass",
    "SecurityBoundaryStatus",
    "TaskFamily",
    "is_pass",
]


class OracleVerdict(StrEnum):
    """§8.1. The six decisions an oracle may reach. Closed, exactly six. FROZEN.

    ```text
    PASS          required checks executed and passed
    FAIL          required checks executed and one or more required assertions failed
    BLOCKED       a prerequisite or the environment prevented required execution
    NOT_RUN       intentionally not executed
    UNKNOWN       execution or observation happened, but the evidence is insufficient
                  for classification
    UNAVAILABLE   the required metric or observation cannot be obtained from the
                  current architecture
    ```

    ### What each member does NOT mean

    ```text
    BLOCKED and UNAVAILABLE are not FAIL. An environment that cannot run a check has
    produced no evidence about the thing checked, and recording it as FAIL would be a
    claim nothing supports.

    BLOCKED, UNAVAILABLE, NOT_RUN and UNKNOWN are not PASS. There is no path that
    promotes a not-measured state into a measured one (§8.2).

    PASS is not a capability claim. It means: for THIS task, at THIS version, against
    THESE oracles, on THIS host, at THIS source_sha, the required checks executed and
    passed (§8.5).
    ```
    """

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


#: §8.4. The reporting order for a run's aggregate, highest first. PROPOSED, and it
#: governs REPORTING ONLY — it is not a severity claim about a model.
#:
#: `FAIL` leads because a definite negative finding must never be masked by a
#: not-measured state. `BLOCKED` and `UNAVAILABLE` follow because both name something
#: actionable. `UNKNOWN` says something ran and could not be classified. `NOT_RUN` is
#: the least informative non-PASS state: nothing was attempted.
#:
#: `PASS` is absent from the table on purpose. It is not a rung on this ladder; it is
#: reachable only through the invariant in `is_pass`, and no member below it may be
#: read as "almost PASS".
ORACLE_VERDICT_PRECEDENCE: tuple[OracleVerdict, ...] = (
    OracleVerdict.FAIL,
    OracleVerdict.BLOCKED,
    OracleVerdict.UNAVAILABLE,
    OracleVerdict.UNKNOWN,
    OracleVerdict.NOT_RUN,
)


class SecurityBoundaryStatus(StrEnum):
    """§14.2. The security axis. Closed. PROPOSED. A distinct type.

    ```text
    NO_VIOLATION    no operation executed outside the declared allowed set
    VIOLATION       an operation executed outside the declared allowed set (§10.3b)
    NOT_RUN         the security observation was intentionally not performed
    BLOCKED         a prerequisite prevented the observation
    UNKNOWN         the observation happened and is insufficient to classify
    UNAVAILABLE     the observation cannot be obtained from the current architecture
    ```

    **It shares member spellings with `OracleVerdict` and shares nothing else.** The two
    are never compared, never stored in one field and never converted into one another.
    §14.1 makes task result and security result two independent axes, and merging the
    vocabularies is the first step of merging the axes.

    Only `VIOLATION` records a violation, and only `NO_VIOLATION` records its absence.
    """

    NO_VIOLATION = "NO_VIOLATION"
    VIOLATION = "VIOLATION"
    NOT_RUN = "NOT_RUN"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


#: §14.2. Reporting order for the security axis, highest first. `VIOLATION` leads: a
#: recorded violation must never be masked by an observation that did not happen.
SECURITY_BOUNDARY_PRECEDENCE: tuple[SecurityBoundaryStatus, ...] = (
    SecurityBoundaryStatus.VIOLATION,
    SecurityBoundaryStatus.BLOCKED,
    SecurityBoundaryStatus.UNAVAILABLE,
    SecurityBoundaryStatus.UNKNOWN,
    SecurityBoundaryStatus.NOT_RUN,
)


class ExecutorKind(StrEnum):
    """§6.1, §20.4. What produced a run. Closed, exactly two.

    ```text
    AGENT       an AI-08 Agent execution. `agent_id` is a member of AI-08's AgentId.
    REFERENCE   AI-11's deterministic, non-model reference executor (§20.4).
                `agent_id` is null.
    ```

    **`REFERENCE` is not an AgentId and MUST NOT be written into `agent_id`.** AI-08 §5.4
    forbids treating an unregistered token as a new Agent, and a benchmark that
    registered a fake Agent to have something to run would be doing exactly that.

    A REFERENCE run proves the harness is deterministic, the tasks are solvable and the
    oracles discriminate. It measures no model and MUST NOT be read as a model result.
    """

    AGENT = "AGENT"
    REFERENCE = "REFERENCE"


class TaskFamily(StrEnum):
    """§17.1. The six families the v1 corpus covers. Closed."""

    FIRMWARE = "firmware"
    YARA = "yara"
    CAN = "can"
    UDS = "uds"
    REVERSE = "reverse"
    FUZZING_RECOVERY = "fuzzing_recovery"


class Difficulty(StrEnum):
    """§5.5. An ordinal label. Closed, exactly three.

    **Not a score.** It MUST NOT be averaged, summed, weighted or placed in any
    aggregate. It classifies a task; it does not rank one.
    """

    INTRODUCTORY = "INTRODUCTORY"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


#: §5.5. The ordinal order, for a reader that wants to sort. NOT a distance and NOT a
#: quantity: the step from INTRODUCTORY to INTERMEDIATE is not equal to the step from
#: INTERMEDIATE to ADVANCED, and nothing may compute with these values.
DIFFICULTY_ORDER: Mapping[Difficulty, int] = {
    Difficulty.INTRODUCTORY: 0,
    Difficulty.INTERMEDIATE: 1,
    Difficulty.ADVANCED: 2,
}


class OracleKind(StrEnum):
    """§7.3. How an oracle reaches its decision. Closed, exactly five."""

    INDEPENDENT_TEST = "INDEPENDENT_TEST"
    TRACKED_DEFINITION = "TRACKED_DEFINITION"
    CONTROLLED_REPRODUCTION = "CONTROLLED_REPRODUCTION"
    DIFF_INSPECTION = "DIFF_INSPECTION"
    SECURITY_BOUNDARY_FACT = "SECURITY_BOUNDARY_FACT"


class ProvenanceClass(StrEnum):
    """§9.1. Where a number came from. Closed, exactly three. Never mixed in one field.

    ```text
    MEASURED     produced by this campaign, by executing something, on this host
    DOCUMENTED   quoted from a repository document. It is a CLAIM BY THAT DOCUMENT.
    STATIC       obtained by inspecting source or Git without executing anything
    ```

    A DOCUMENTED number MUST be labelled as such wherever it appears, and MUST NOT be
    presented as an executed quantity (§9.1).
    """

    MEASURED = "MEASURED"
    DOCUMENTED = "DOCUMENTED"
    STATIC = "STATIC"


class LimitationCode(StrEnum):
    """§22.3. Why a measurement is unavailable. Closed. PROPOSED.

    Every null measurement carries exactly one of these, or a code added by amendment.
    **A null without a reason code is REJECTED** — that is the shape rule that stops
    "we did not measure this" from decaying into "we measured nothing".

    A parameterised code is the base name, a colon, and the parameter:
    `PRECONDITION_UNMET:program:yara`. The base name is validated against this
    vocabulary and the parameter is carried verbatim.
    """

    NO_PROVIDER_CALL_IN_PATH = "NO_PROVIDER_CALL_IN_PATH"
    NO_ADMISSIBLE_FIELD = "NO_ADMISSIBLE_FIELD"
    NO_CLAIM_SOURCE = "NO_CLAIM_SOURCE"
    LAYER4_BLOCKED = "LAYER4_BLOCKED"
    PRECONDITION_UNMET = "PRECONDITION_UNMET"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    ORACLE_MATERIAL_UNAVAILABLE = "ORACLE_MATERIAL_UNAVAILABLE"
    SOURCE_SHA_UNRESOLVED = "SOURCE_SHA_UNRESOLVED"
    HOST_NOT_AUTHORITATIVE = "HOST_NOT_AUTHORITATIVE"


#: §22.3. The codes that may be parameterised with a `:<parameter>` suffix.
LIMITATION_REASON_PREFIXES: frozenset[LimitationCode] = frozenset(
    {LimitationCode.PRECONDITION_UNMET}
)


def is_pass(verdict: OracleVerdict) -> bool:
    """Whether a verdict is `PASS`.

    One line, and it exists so that no caller writes `not in {FAIL, BLOCKED, ...}` — a
    set that has to be kept in step with the vocabulary and will not be. The positive
    test is the only safe direction: a member added by amendment is not a PASS by
    default.
    """
    return verdict is OracleVerdict.PASS
