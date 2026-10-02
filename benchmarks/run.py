"""AI-11 §6, §9, §10, §18 — the BenchmarkRun, and what it is allowed to carry.

A `BenchmarkRun` describes **one execution of one task**. It is run data.

```text
FROZEN: a BenchmarkRun is RUN DATA. It is NOT an AI-05 EvidenceRecord, and v1 writes
        no EvidenceRecord at all (§21.1).
FROZEN: it carries no raw model output, no prompt body, no task body beyond the
        published TaskDefinition, no tool argument and no credential — for any
        status (§18.2).
FROZEN: `reference` MUST NOT be written into `agent_id` (§6.1).
```

### The two invariants that carry the most weight

`TestCounts` enforces `executed + skipped == planned` and `passed + failed == executed`.
Those two lines are what make a "planned 234, executed 0, passed 0, exit 0" record
representable and *visibly* not a pass. A record that could hold those numbers without
noticing they do not add up is a record in which a skip can hide.

`BenchmarkRun` enforces that a null measurement carries a limitation code, and that
`executor_kind = REFERENCE` implies `agent_id is None`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from benchmarks.errors import InvalidBenchmarkRun
from benchmarks.vocabulary import (
    ExecutorKind,
    LimitationCode,
    OracleVerdict,
    SecurityBoundaryStatus,
)

__all__ = [
    "RUN_ID_RE",
    "BenchmarkRun",
    "HostRecord",
    "TestCounts",
    "ToolTraceEntry",
    "new_run_id",
]

#: §6.2. PROPOSED.
RUN_ID_RE = re.compile(r"^run-[0-9a-f]{16}$")


def new_run_id(hex16: str) -> str:
    """Build a run id from 16 lowercase hex characters.

    Takes the value rather than generating it, so the caller owns randomness and this
    module stays a pure shape rule with no hidden entropy — the same reason AI-08 takes
    a clock rather than reading one.
    """
    run_id = f"run-{hex16}"
    if not RUN_ID_RE.match(run_id):
        raise InvalidBenchmarkRun(
            f"run id {run_id!r} does not match {RUN_ID_RE.pattern!r}; it is 16 lowercase "
            "hexadecimal characters"
        )
    return run_id


def _reason_code(value: object, where: str) -> str:
    """§22.3. A limitation code, validated against the closed vocabulary.

    The base name is validated and the parameter is carried verbatim, so
    `PRECONDITION_UNMET:program:yara` is admitted and `WHATEVER` is not.
    """
    if not isinstance(value, str) or not value:
        raise InvalidBenchmarkRun(f"{where} must be a non-empty limitation code")
    base = value.split(":", 1)[0]
    try:
        LimitationCode(base)
    except ValueError as exc:
        raise InvalidBenchmarkRun(
            f"{where} names the limitation code {base!r}, which is not one of "
            f"{sorted(m.value for m in LimitationCode)}"
        ) from exc
    return value


@dataclass(frozen=True, slots=True)
class TestCounts:
    """§11. What the oracle planned, ran, skipped and got.

    ```text
    planned    checks the oracle declared it would run
    executed   checks that actually ran
    skipped    planned checks that did not run
    passed     executed checks whose required assertion held
    failed     executed checks whose required assertion did not hold
    ```

    `skipped` is a recorded FACT, never a pass. A record reading
    `planned=234 executed=0 passed=0 failed=0 skipped=234` is complete and honest, and
    §11 forbids reading it as a pass.
    """

    #: The class name begins with `Test`, so pytest tries to collect it as a test class
    #: the moment a test module imports it. It is a data type; this says so once here
    #: rather than making every test module carry a conftest workaround.
    __test__ = False

    planned: int = 0
    executed: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    def __post_init__(self) -> None:
        for name in ("planned", "executed", "passed", "failed", "skipped"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise InvalidBenchmarkRun(f"tests.{name} must be a non-negative integer")

        if self.executed + self.skipped != self.planned:
            raise InvalidBenchmarkRun(
                f"tests do not add up: executed({self.executed}) + skipped({self.skipped}) "
                f"!= planned({self.planned}). A record whose counts do not add up is a "
                "record in which a skip can hide (§11)"
            )
        if self.passed + self.failed != self.executed:
            raise InvalidBenchmarkRun(
                f"tests do not add up: passed({self.passed}) + failed({self.failed}) "
                f"!= executed({self.executed})"
            )

    @property
    def all_required_executed(self) -> bool:
        """Whether every planned check actually ran. The first half of §11's PASS rule."""
        return self.planned > 0 and self.skipped == 0 and self.executed == self.planned

    @property
    def all_executed_passed(self) -> bool:
        """Whether every executed check passed. The second half."""
        return self.all_required_executed and self.failed == 0 and self.passed == self.executed

    def to_mapping(self) -> dict[str, int]:
        return {
            "planned": self.planned,
            "executed": self.executed,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
        }


@dataclass(frozen=True, slots=True)
class ToolTraceEntry:
    """§10.1. One AI-08 `ToolCallRef`, projected. **And nothing more.**

    The fields are exactly what AI-08 exposes. There is no tool argument, no stdout, no
    stderr and no exit code, because `ToolCallRef` carries none of those and AI-11 does
    not add a second, richer trace beside it (§10.1).

    `guard_decision_is_none` is the pre-Guard refusal: AI-06 supplies a fallback decision
    word AND an empty `decision_id`, and AI-08 carries that as `guard_decision = None`.
    Recording it as an evaluation would put a claim in the record that nothing supports.
    """

    ordinal: int
    what_ran: str
    tool_version: str
    outcome: str
    guard_decision: str | None
    guard_decision_id: str
    guard_reason_code: str
    duration_ms: int | None = None

    @property
    def was_evaluated(self) -> bool:
        """Whether Guard actually evaluated this invocation."""
        return bool(self.guard_decision_id)

    @property
    def is_pre_guard_refusal(self) -> bool:
        return not self.was_evaluated

    @property
    def is_guard_refusal(self) -> bool:
        """A Guard-bound invocation that was NOT allowed.

        Distinct from the security axis (§14): a refusal is evidence the boundary
        worked, and §10.3 forbids scoring it as a bypass.
        """
        return self.was_evaluated and self.guard_decision != "ALLOW"

    @classmethod
    def from_tool_call_ref(cls, call: Any) -> "ToolTraceEntry":
        """Project an AI-08 `ToolCallRef`.

        Reads only the attributes `ToolCallRef` declares. It does not reach for
        anything else on the object, so a richer object cannot leak extra fields into a
        run record through this door.
        """
        return cls(
            ordinal=call.ordinal,
            what_ran=call.what_ran,
            tool_version=call.tool_version,
            outcome=str(call.outcome),
            guard_decision=None if call.guard_decision is None else str(call.guard_decision),
            guard_decision_id=call.guard_decision_id,
            guard_reason_code=call.guard_reason_code,
            duration_ms=call.duration_ms,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "what_ran": self.what_ran,
            "tool_version": self.tool_version,
            "outcome": self.outcome,
            "guard": {
                "decision": self.guard_decision,
                "decision_id": self.guard_decision_id,
                "reason_code": self.guard_reason_code,
                "evaluated": self.was_evaluated,
            },
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True, slots=True)
class HostRecord:
    """§15.4. The environment a measurement was taken in.

    A measurement taken without its environment record is not reproducible and MUST NOT
    be published as a result. A version that cannot be obtained is `None` with a
    reason, never omitted and never guessed.
    """

    os: str | None = None
    kernel: str | None = None
    python: str | None = None
    tool_versions: Mapping[str, str] = field(default_factory=dict)
    qemu_version: str | None = None
    cross_compiler: str | None = None
    workbench_sha: str = ""
    source_sha: str = ""

    def to_mapping(self) -> dict[str, Any]:
        return {
            "os": self.os,
            "kernel": self.kernel,
            "python": self.python,
            "tool_versions": dict(self.tool_versions),
            "qemu_version": self.qemu_version,
            "cross_compiler": self.cross_compiler,
            "workbench_sha": self.workbench_sha,
            "source_sha": self.source_sha,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    """§6.1. One execution of one task.

    ```text
    FROZEN: a BenchmarkRun is a CLAIM WITH A PRODUCER. It records that a run happened
            and what it was measured to be. It is NOT a verdict about a model.
    FROZEN: COMPLETED MUST NOT be written into task_status (§6.3).
    ```
    """

    run_id: str
    task_id: str
    task_version: int
    executor_kind: ExecutorKind
    agent_id: str | None
    execution_id: str | None
    workbench_sha: str
    source_sha: str
    workspace_identity: Mapping[str, Any]
    host: HostRecord
    started_at: str
    finished_at: str
    duration_ms: int
    tool_trace: tuple[ToolTraceEntry, ...] = ()
    tests: TestCounts = field(default_factory=TestCounts)
    git_before: Mapping[str, Any] = field(default_factory=dict)
    git_after: Mapping[str, Any] = field(default_factory=dict)
    diff_digest: str | None = None
    oracle_results: tuple[Mapping[str, Any], ...] = ()
    task_status: OracleVerdict = OracleVerdict.NOT_RUN
    regression_status: OracleVerdict = OracleVerdict.NOT_RUN
    security_boundary_status: SecurityBoundaryStatus = SecurityBoundaryStatus.NOT_RUN
    provider: str | None = None
    model: str | None = None
    model_ref: str | None = None
    token_usage: Mapping[str, Any] | None = None
    cost: Mapping[str, Any] | None = None
    regression_results: tuple[Mapping[str, Any], ...] = ()
    limitations: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not RUN_ID_RE.match(self.run_id):
            raise InvalidBenchmarkRun(f"run_id {self.run_id!r} does not match {RUN_ID_RE.pattern!r}")

        # §6.1 FROZEN, and this is the only place it can be enforced structurally.
        # `reference` is not an AI-08 AgentId, and AI-08 §5.4 forbids treating an
        # unregistered token as a new Agent. A REFERENCE run therefore carries the
        # truthful `None` rather than an empty string, which §9.4 also requires.
        if self.executor_kind is ExecutorKind.REFERENCE:
            if self.agent_id is not None:
                raise InvalidBenchmarkRun(
                    f"executor_kind is REFERENCE and agent_id is {self.agent_id!r}. A "
                    "reference run is not an Agent execution; `reference` MUST NOT be "
                    "written into agent_id (§6.1)"
                )
        else:
            if not self.agent_id:
                raise InvalidBenchmarkRun(
                    "executor_kind is AGENT and agent_id is empty; an Agent run names "
                    "the registered Agent that produced it"
                )
            from agents.vocabulary import resolve_agent

            # Through AI-08's own boundary, not a second identity rule here.
            resolve_agent(self.agent_id)

        # §9.4. An unobtainable measurement is null WITH a named reason. A null without
        # one is refused, because a bare null is the shape "we forgot" takes.
        if self.token_usage is None and not self._has_limitation(
            LimitationCode.NO_PROVIDER_CALL_IN_PATH
        ):
            raise InvalidBenchmarkRun(
                "token_usage is null and no NO_PROVIDER_CALL_IN_PATH limitation is "
                "recorded. §9.4 requires a named reason for every unavailable "
                "measurement; it MUST NOT be recorded as 0, and it MUST NOT be silent"
            )

        if self.cost is None and not (
            self._has_limitation(LimitationCode.NO_PROVIDER_CALL_IN_PATH)
        ):
            raise InvalidBenchmarkRun(
                "cost is null and no NO_PROVIDER_CALL_IN_PATH limitation is recorded (§9.4)"
            )

        for code in self.limitations:
            _reason_code(code, "limitations[]")

        if self.schema_version != 1:
            raise InvalidBenchmarkRun(
                f"schema_version {self.schema_version!r} is not supported; this contract defines 1"
            )

    def _has_limitation(self, code: LimitationCode) -> bool:
        return any(entry.split(":", 1)[0] == code.value for entry in self.limitations)

    # -- projection --------------------------------------------------------

    def to_mapping(self) -> dict[str, Any]:
        """The audit projection, as an **explicit allowlist**.

        `dataclasses.asdict` would put every field into a record, so a field added later
        would reach an auditable artefact without anyone deciding it should — the rule
        AI-04 §13.3, AI-07 §13.3 and AI-08 §10 already state for their own records.
        """
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "task_version": self.task_version,
            "executor_kind": str(self.executor_kind),
            "agent_id": self.agent_id,
            "execution_id": self.execution_id,
            "provider": self.provider,
            "model": self.model,
            "model_ref": self.model_ref,
            "workbench_sha": self.workbench_sha,
            "source_sha": self.source_sha,
            "workspace_identity": dict(self.workspace_identity),
            "host": self.host.to_mapping(),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "tool_trace": [entry.to_mapping() for entry in self.tool_trace],
            "tests": self.tests.to_mapping(),
            "git_before": dict(self.git_before),
            "git_after": dict(self.git_after),
            "diff_digest": self.diff_digest,
            "oracle_results": [dict(entry) for entry in self.oracle_results],
            "task_status": str(self.task_status),
            "regression_status": str(self.regression_status),
            "regression_results": [dict(entry) for entry in self.regression_results],
            "security_boundary_status": str(self.security_boundary_status),
            "token_usage": dict(self.token_usage) if self.token_usage is not None else None,
            "cost": dict(self.cost) if self.cost is not None else None,
            "limitations": list(self.limitations),
        }
