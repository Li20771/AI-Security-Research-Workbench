"""AI-11 §5, §7.3, §12, §17 — the TaskDefinition, and the corpus that holds it.

A `TaskDefinition` describes **what the task is**. It never holds a result.

```text
FROZEN: a TaskDefinition MUST NOT contain any field that holds, summarises, references
        or implies the result of any run (§5.1).
FROZEN: a TaskDefinition is immutable once published at a task_version. A change to
        what a task asks is a new task_version, never an edit in place.
FROZEN: an unknown top-level field is REJECTED, not ignored.
```

### One oracle per task, and why that reading was taken

§5.1 types the field as `oracle object` (singular) while §6.1 says `oracle_results` is
"one entry per declared oracle". §7.3 then describes the fields of *an* oracle.

§7.3 is the operative section for the shape, and it describes one oracle. The v1 corpus
in Annex A gives each task exactly one independent oracle. So v1 declares one oracle per
task and `oracle_results` is a one-entry list, which satisfies §5.1, §7.3 and §8.4
without inventing a declaration form the contract does not freeze.

The list shape is kept for `oracle_results` so that a future amendment permitting more
than one oracle does not have to change the run record. It is NOT a claim that v1
declares several.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from plugins.security_tools import ToolRegistry

from benchmarks.errors import (
    BenchmarkError,
    CorpusError,
    InvalidOracleDeclaration,
    InvalidTaskDefinition,
    UnregisteredTool,
)
from benchmarks.vocabulary import Difficulty, OracleKind, TaskFamily

__all__ = [
    "FORBIDDEN_TASK_FIELDS",
    "MAX_DESCRIPTION_CHARS",
    "MAX_TOKEN_CHARS",
    "PRECONDITION_KINDS",
    "SOURCE_SHA_RE",
    "TASK_ID_RE",
    "DiscriminationControl",
    "OracleDeclaration",
    "Precondition",
    "RegressionCondition",
    "TaskDefinition",
    "ToolPair",
    "WorkspaceSetup",
    "load_corpus",
    "load_task",
]

#: §5.2. PROPOSED. Validated at load; a task_id that does not match is REJECTED, never
#: normalised.
TASK_ID_RE = re.compile(r"^ai11-v1-[a-z0-9]+(-[a-z0-9]+)*$")
MAX_TASK_ID_CHARS = 64

#: §5.3. A full 40-character lowercase hexadecimal commit id. A branch name, a tag, a
#: short sha, `HEAD`, a date and a "latest" are all REFUSED by this pattern.
SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

#: §18.3. Class 3 bounded machine token. Single line, declared grammar, no CR, no LF.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/=<>!+-]{0,199}$")
MAX_TOKEN_CHARS = 200

#: §18.3. Class 4. The TaskDefinition's `task_description` is the ONLY Class 4 field in
#: the whole schema, and it is AUTHORED MATERIAL, never model output.
MAX_DESCRIPTION_CHARS = 512

_IDENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

#: §5.1. Field names that never exist on a TaskDefinition, and never mean anything here.
#: Held as data so the schema, the tests and the Layer 0 gate all read one list — the
#: shape AI-10 §7.3 already established for its own forbidden fields.
FORBIDDEN_TASK_FIELDS: frozenset[str] = frozenset(
    {
        "last_result",
        "last_run",
        "result",
        "results",
        "run_result",
        "pass_rate",
        "success_rate",
        "failure_rate",
        "best_model",
        "best_agent",
        "winner",
        "rank",
        "ranking",
        "score",
        "difficulty_score",
        "weight",
        "priority",
        "confidence",
        "correctness",
        "accuracy",
        "quality",
        "baseline_result",
        "expected_result",
    }
)

#: §5.7. What a precondition may name. Closed.
PRECONDITION_KINDS = (
    "program",
    "python_module",
    "kernel_module",
    "directory",
    "environment",
)


# ---------------------------------------------------------------------------
# small validators — every refusal names the field and the expectation
# ---------------------------------------------------------------------------


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidTaskDefinition(f"{where} must be an object")
    return value


def _no_unknown(raw: Mapping[str, Any], allowed: Iterable[str], where: str) -> None:
    unknown = set(raw) - set(allowed)
    if unknown:
        raise InvalidTaskDefinition(
            f"{where} has field(s) the contract does not define: "
            f"{', '.join(sorted(map(str, unknown)))}"
        )


def _text(
    value: object,
    where: str,
    *,
    maximum: int,
    single_line: bool = True,
    error: type[BenchmarkError] = InvalidTaskDefinition,
) -> str:
    """Bounded text. `error` selects the refusal type.

    An oracle defect raises `InvalidOracleDeclaration` and a task defect raises
    `InvalidTaskDefinition`. The two send a reader to different places — the oracle
    declaration or the task — and a single type would send half of them to the wrong one.
    """
    if not isinstance(value, str) or not value:
        raise error(f"{where} must be a non-empty string")
    if len(value) > maximum:
        raise error(f"{where} must be at most {maximum} characters")
    if single_line and ("\n" in value or "\r" in value):
        # §14.2's rule for Class 4, applied here: AI-11 REJECTS rather than flattening,
        # because flattening would be the silent substitution this repository forbids.
        raise error(f"{where} must be a single line")
    return value


def _token(
    value: object, where: str, *, error: type[BenchmarkError] = InvalidTaskDefinition
) -> str:
    text = _text(value, where, maximum=MAX_TOKEN_CHARS, error=error)
    if not _TOKEN_RE.match(text):
        raise error(
            f"{where} is not a bounded machine token; it must match "
            f"{_TOKEN_RE.pattern!r} (single line, no quotes, no CR, no LF)"
        )
    return text


def _identifier(value: object, where: str) -> str:
    text = _text(value, where, maximum=64)
    if not _IDENT_RE.match(text):
        raise InvalidTaskDefinition(f"{where} must match {_IDENT_RE.pattern!r}")
    return text


def _sequence(value: object, where: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise InvalidTaskDefinition(f"{where} must be a list")
    return value


def _tokens(value: object, where: str) -> tuple[str, ...]:
    return tuple(_token(entry, f"{where}[{index}]") for index, entry in enumerate(_sequence(value, where)))


# ---------------------------------------------------------------------------
# components
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolPair:
    """§5.6. One AI-06 `(tool_id, operation)` pair.

    Both halves are checked against the REGISTERED descriptor set. A task may not name
    a tool that does not exist: a forbidden-tool list is only meaningful if the allowed
    one is real, and a typo in an allowlist is an allowlist that permits nothing while
    reading as though it permits something.
    """

    tool_id: str
    operation: str

    @property
    def what_ran(self) -> str:
        """The spelling AI-06 uses, so the pair names the same operation it names."""
        return f"{self.tool_id}/{self.operation}"

    def to_mapping(self) -> dict[str, str]:
        return {"tool_id": self.tool_id, "operation": self.operation}


def _tool_pair(value: object, where: str, registry: ToolRegistry) -> ToolPair:
    raw = _mapping(value, where)
    _no_unknown(raw, ("tool_id", "operation"), where)
    tool_id = _text(raw.get("tool_id"), f"{where}.tool_id", maximum=64)
    operation = _text(raw.get("operation"), f"{where}.operation", maximum=64)

    for descriptor in registry.descriptors():
        if descriptor.identity.tool_id != tool_id:
            continue
        if descriptor.operation(operation) is None:
            raise UnregisteredTool(
                f"{where} names {tool_id}/{operation}, and the {tool_id} family declares "
                f"no such operation. Declared: {sorted(descriptor.capability_names)}"
            )
        return ToolPair(tool_id=tool_id, operation=operation)

    raise UnregisteredTool(
        f"{where} names the tool {tool_id!r}, which is not in the registered v1 "
        f"descriptor set. Registered: "
        f"{sorted(d.identity.tool_id for d in registry.descriptors())}"
    )


@dataclass(frozen=True, slots=True)
class Precondition:
    """§5.7. A fact the harness must establish before execution.

    A precondition is a HARNESS act. It is never delegated to the Agent and never
    inferred from the Agent's behaviour.
    """

    kind: str
    name: str
    minimum_version: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in PRECONDITION_KINDS:
            raise InvalidTaskDefinition(
                f"precondition kind {self.kind!r} is not one of {list(PRECONDITION_KINDS)}"
            )
        if not self.name:
            raise InvalidTaskDefinition("precondition.name must be non-empty")

    @property
    def reason_code(self) -> str:
        """§22.3. The parameterised limitation code a BLOCKED run carries."""
        return f"PRECONDITION_UNMET:{self.kind}:{self.name}"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "minimum_version": self.minimum_version,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceSetup:
    """§5.4. How the agent-visible tree is derived.

    ```text
    include     paths exported into the agent-visible tree
    exclude     paths withheld from it
    generated   artifacts the harness must BUILD before execution
    ```

    **`manifest_digest` is absent on purpose.** §5.4 makes it HARNESS-MEASURED, and an
    author-supplied value is REJECTED — the rule AI-05 §13.5 states for `artifact_digest`,
    applied here. A definition that declared its own manifest digest would let the
    declaration stand in for the measurement.
    """

    include: tuple[str, ...]
    exclude: tuple[str, ...]
    generated: tuple[str, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {
            "include": list(self.include),
            "exclude": list(self.exclude),
            "generated": list(self.generated),
        }


@dataclass(frozen=True, slots=True)
class DiscriminationControl:
    """§7.4. What makes an oracle falsifiable.

    ```text
    FROZEN: every Oracle MUST declare a DISCRIMINATION CONTROL: a known-bad input that
            the Oracle MUST judge non-PASS, and a known-good input that it MUST judge
            PASS.
    FROZEN: an Oracle that cannot fail is not an Oracle.
    ```

    The two references point at tracked fixtures under the task's own `control/`
    directory. They are material, so like every other oracle input they are excluded
    from the agent-visible tree.
    """

    known_good: str
    known_bad: str

    def to_mapping(self) -> dict[str, str]:
        return {"known_good": self.known_good, "known_bad": self.known_bad}


@dataclass(frozen=True, slots=True)
class RegressionCondition:
    """§12. A condition the harness evaluates on the POST-execution state.

    Regression is its OWN axis. A run may be `task_status = PASS` and
    `regression_status = FAIL`, and the pair is recorded as it is.
    """

    condition_id: str
    kind: str
    reproduce_command: str
    required: bool = True

    def __post_init__(self) -> None:
        if self.kind not in ("TRACKED_TEST_SUITE", "FROZEN_DEFINITION", "BEHAVIOURAL_PIN"):
            raise InvalidTaskDefinition(
                f"regression kind {self.kind!r} is not TRACKED_TEST_SUITE, "
                "FROZEN_DEFINITION or BEHAVIOURAL_PIN"
            )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "kind": self.kind,
            "reproduce_command": self.reproduce_command,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class OracleDeclaration:
    """§7.3. The oracle's declaration. The fields are the contract's, and no others."""

    oracle_id: str
    kind: OracleKind
    required: bool
    reproduce_command: str
    expected_negative: DiscriminationControl
    success_condition: str
    material_excluded_from_workspace: bool

    def __post_init__(self) -> None:
        if not self.oracle_id:
            raise InvalidOracleDeclaration("oracle_id must be non-empty")

        # §7.2 is FROZEN and this is where it is enforced at the schema boundary. An
        # oracle whose material the Agent can reach is not an oracle, and a task that
        # declared one false would be a task that could be satisfied without being done.
        if self.material_excluded_from_workspace is not True:
            raise InvalidOracleDeclaration(
                "material_excluded_from_workspace must be true (§7.2). An oracle whose "
                "material is reachable from the agent-visible tree is not an oracle"
            )

        if not self.expected_negative.known_good or not self.expected_negative.known_bad:
            raise InvalidOracleDeclaration(
                "the discrimination control must name both a known-good and a known-bad "
                "input (§7.4); an oracle that cannot fail is not an oracle"
            )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "oracle_id": self.oracle_id,
            "kind": str(self.kind),
            "required": self.required,
            "reproduce_command": self.reproduce_command,
            "expected_negative": self.expected_negative.to_mapping(),
            "success_condition": self.success_condition,
            "material_excluded_from_workspace": self.material_excluded_from_workspace,
        }


# ---------------------------------------------------------------------------
# the TaskDefinition
# ---------------------------------------------------------------------------

_TOP_KEYS = frozenset(
    {
        "task_id",
        "task_version",
        "task_family",
        "difficulty",
        "source_repository",
        "source_sha",
        "workspace_setup",
        "task_description",
        "allowed_tools",
        "forbidden_tools",
        "required_preconditions",
        "oracle",
        "success_conditions",
        "regression_conditions",
        "security_constraints",
        "time_budget_seconds",
        "cost_budget",
        "schema_version",
    }
)


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    """§5.1. The closed description of a benchmark task.

    It describes what the task IS. It holds no result, and §5.1 forbids a field that
    could hold one.
    """

    task_id: str
    task_version: int
    task_family: TaskFamily
    difficulty: Difficulty
    source_repository: str
    source_sha: str
    workspace_setup: WorkspaceSetup
    task_description: str
    allowed_tools: tuple[ToolPair, ...]
    forbidden_tools: tuple[ToolPair, ...]
    required_preconditions: tuple[Precondition, ...]
    oracle: OracleDeclaration
    success_conditions: tuple[str, ...]
    regression_conditions: tuple[RegressionCondition, ...]
    security_constraints: tuple[str, ...]
    time_budget_seconds: int
    cost_budget: Mapping[str, Any] | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not TASK_ID_RE.match(self.task_id):
            raise InvalidTaskDefinition(
                f"task_id {self.task_id!r} does not match {TASK_ID_RE.pattern!r} (§5.2)"
            )
        if len(self.task_id) > MAX_TASK_ID_CHARS:
            raise InvalidTaskDefinition(
                f"task_id must be at most {MAX_TASK_ID_CHARS} characters"
            )

        if not isinstance(self.task_version, int) or isinstance(self.task_version, bool):
            raise InvalidTaskDefinition("task_version must be an integer")
        if self.task_version < 1:
            raise InvalidTaskDefinition("task_version must be >= 1")

        # §5.3. Shape is the loader's business; EXISTENCE is a precondition, evaluated
        # at run time against the source repository, and it produces BLOCKED rather
        # than a rejection. The two are different facts and are checked in different
        # places on purpose.
        if not SOURCE_SHA_RE.match(self.source_sha):
            raise InvalidTaskDefinition(
                f"source_sha {self.source_sha!r} is not a full 40-character lowercase "
                "hexadecimal commit id. A branch, a tag, a short sha, 'HEAD', a date "
                "and 'latest' are refused (§5.3)"
            )

        if self.schema_version != 1:
            raise InvalidTaskDefinition(
                f"schema_version {self.schema_version!r} is not supported; this "
                "contract defines 1"
            )

        if not isinstance(self.time_budget_seconds, int) or isinstance(
            self.time_budget_seconds, bool
        ):
            raise InvalidTaskDefinition(
                f"time_budget_seconds must be an integer and is "
                f"{type(self.time_budget_seconds).__name__}"
            )
        if self.time_budget_seconds <= 0:
            raise InvalidTaskDefinition("time_budget_seconds must be > 0")

        overlap = {pair.what_ran for pair in self.allowed_tools} & {
            pair.what_ran for pair in self.forbidden_tools
        }
        if overlap:
            raise InvalidTaskDefinition(
                f"tool pair(s) {sorted(overlap)} are both allowed and forbidden; a task "
                "must not declare one operation on both lists"
            )

    # -- projection --------------------------------------------------------

    def to_mapping(self) -> dict[str, Any]:
        """An **explicit allowlist**, so that a field added later does not reach a
        published corpus without a decision that it should (§18.1)."""
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "task_version": self.task_version,
            "task_family": str(self.task_family),
            "difficulty": str(self.difficulty),
            "source_repository": self.source_repository,
            "source_sha": self.source_sha,
            "workspace_setup": self.workspace_setup.to_mapping(),
            "task_description": self.task_description,
            "allowed_tools": [pair.to_mapping() for pair in self.allowed_tools],
            "forbidden_tools": [pair.to_mapping() for pair in self.forbidden_tools],
            "required_preconditions": [p.to_mapping() for p in self.required_preconditions],
            "oracle": self.oracle.to_mapping(),
            "success_conditions": list(self.success_conditions),
            "regression_conditions": [c.to_mapping() for c in self.regression_conditions],
            "security_constraints": list(self.security_constraints),
            "time_budget_seconds": self.time_budget_seconds,
            "cost_budget": dict(self.cost_budget) if self.cost_budget is not None else None,
        }

    # -- loading -----------------------------------------------------------

    @classmethod
    def from_mapping(
        cls, raw: object, *, registry: ToolRegistry | None = None
    ) -> "TaskDefinition":
        """Parse a TaskDefinition. Every refusal names the field and the expectation."""
        if not isinstance(raw, Mapping):
            raise InvalidTaskDefinition("a TaskDefinition must be an object")

        # §5.1. The result-shaped refusal runs FIRST, so a definition carrying
        # `pass_rate` is refused for carrying it rather than for having an unknown key.
        forbidden = FORBIDDEN_TASK_FIELDS & set(raw)
        if forbidden:
            raise InvalidTaskDefinition(
                "this TaskDefinition carries field(s) that hold or imply a run result: "
                f"{', '.join(sorted(forbidden))}. §5.1 forbids a TaskDefinition from "
                "holding, summarising, referencing or implying the result of any run"
            )

        _no_unknown(raw, _TOP_KEYS, "TaskDefinition")

        registry = registry if registry is not None else _default_registry()

        workspace = _mapping(raw.get("workspace_setup"), "workspace_setup")
        _no_unknown(workspace, ("include", "exclude", "generated"), "workspace_setup")
        if "manifest_digest" in workspace:
            raise InvalidTaskDefinition(
                "workspace_setup.manifest_digest is HARNESS-MEASURED (§5.4). An "
                "author-supplied value is rejected, not overwritten"
            )

        oracle_raw = _mapping(raw.get("oracle"), "oracle")
        _no_unknown(
            oracle_raw,
            (
                "oracle_id",
                "kind",
                "required",
                "reproduce_command",
                "expected_negative",
                "success_condition",
                "material_excluded_from_workspace",
            ),
            "oracle",
        )
        control_raw = _mapping(oracle_raw.get("expected_negative"), "oracle.expected_negative")
        _no_unknown(control_raw, ("known_good", "known_bad"), "oracle.expected_negative")

        try:
            kind = OracleKind(oracle_raw.get("kind"))
        except ValueError as exc:
            raise InvalidOracleDeclaration(
                f"oracle.kind {oracle_raw.get('kind')!r} is not one of "
                f"{sorted(m.value for m in OracleKind)}"
            ) from exc

        try:
            family = TaskFamily(raw.get("task_family"))
        except ValueError as exc:
            raise InvalidTaskDefinition(
                f"task_family {raw.get('task_family')!r} is not one of "
                f"{sorted(m.value for m in TaskFamily)}"
            ) from exc

        try:
            difficulty = Difficulty(raw.get("difficulty"))
        except ValueError as exc:
            raise InvalidTaskDefinition(
                f"difficulty {raw.get('difficulty')!r} is not one of "
                f"{sorted(m.value for m in Difficulty)}"
            ) from exc

        conditions_raw = _sequence(raw.get("regression_conditions"), "regression_conditions")
        regression = []
        for index, entry in enumerate(conditions_raw):
            where = f"regression_conditions[{index}]"
            item = _mapping(entry, where)
            _no_unknown(
                item, ("condition_id", "kind", "reproduce_command", "required"), where
            )
            regression.append(
                RegressionCondition(
                    condition_id=_identifier(item.get("condition_id"), f"{where}.condition_id"),
                    kind=_text(item.get("kind"), f"{where}.kind", maximum=32),
                    reproduce_command=_text(
                        item.get("reproduce_command"), f"{where}.reproduce_command", maximum=512
                    ),
                    required=bool(item.get("required", True)),
                )
            )

        preconditions_raw = _sequence(
            raw.get("required_preconditions"), "required_preconditions"
        )
        preconditions = []
        for index, entry in enumerate(preconditions_raw):
            where = f"required_preconditions[{index}]"
            item = _mapping(entry, where)
            _no_unknown(item, ("kind", "name", "minimum_version"), where)
            version = item.get("minimum_version")
            preconditions.append(
                Precondition(
                    kind=_text(item.get("kind"), f"{where}.kind", maximum=32),
                    name=_text(item.get("name"), f"{where}.name", maximum=128),
                    minimum_version=(
                        None
                        if version is None
                        else _text(version, f"{where}.minimum_version", maximum=64)
                    ),
                )
            )

        cost_budget = raw.get("cost_budget")
        if cost_budget is not None:
            # §9.4. `null` and `0` are different facts, and a budget that is present is
            # an object. A bare zero would read as "a budget of nothing".
            if not isinstance(cost_budget, Mapping):
                raise InvalidTaskDefinition(
                    "cost_budget must be an object or null; a bare value would make "
                    "'no budget declared' and 'a budget of zero' indistinguishable"
                )

        return cls(
            task_id=_text(raw.get("task_id"), "task_id", maximum=MAX_TASK_ID_CHARS),
            task_version=raw.get("task_version"),
            task_family=family,
            difficulty=difficulty,
            source_repository=_text(
                raw.get("source_repository"), "source_repository", maximum=256
            ),
            source_sha=_text(raw.get("source_sha"), "source_sha", maximum=40),
            workspace_setup=WorkspaceSetup(
                include=tuple(
                    _text(p, f"workspace_setup.include[{i}]", maximum=512)
                    for i, p in enumerate(_sequence(workspace.get("include"), "workspace_setup.include"))
                ),
                exclude=tuple(
                    _text(p, f"workspace_setup.exclude[{i}]", maximum=512)
                    for i, p in enumerate(_sequence(workspace.get("exclude"), "workspace_setup.exclude"))
                ),
                generated=tuple(
                    _text(p, f"workspace_setup.generated[{i}]", maximum=512)
                    for i, p in enumerate(_sequence(workspace.get("generated"), "workspace_setup.generated"))
                ),
            ),
            task_description=_text(
                raw.get("task_description"),
                "task_description",
                maximum=MAX_DESCRIPTION_CHARS,
            ),
            allowed_tools=tuple(
                _tool_pair(pair, f"allowed_tools[{i}]", registry)
                for i, pair in enumerate(_sequence(raw.get("allowed_tools"), "allowed_tools"))
            ),
            forbidden_tools=tuple(
                _tool_pair(pair, f"forbidden_tools[{i}]", registry)
                for i, pair in enumerate(_sequence(raw.get("forbidden_tools"), "forbidden_tools"))
            ),
            required_preconditions=tuple(preconditions),
            oracle=OracleDeclaration(
                oracle_id=_text(
                    oracle_raw.get("oracle_id"), "oracle.oracle_id",
                    maximum=128, error=InvalidOracleDeclaration,
                ),
                kind=kind,
                required=bool(oracle_raw.get("required", True)),
                reproduce_command=_text(
                    oracle_raw.get("reproduce_command"),
                    "oracle.reproduce_command",
                    maximum=512,
                    error=InvalidOracleDeclaration,
                ),
                expected_negative=DiscriminationControl(
                    known_good=_text(
                        control_raw.get("known_good"),
                        "oracle.expected_negative.known_good",
                        maximum=512,
                        error=InvalidOracleDeclaration,
                    ),
                    known_bad=_text(
                        control_raw.get("known_bad"),
                        "oracle.expected_negative.known_bad",
                        maximum=512,
                        error=InvalidOracleDeclaration,
                    ),
                ),
                success_condition=_token(
                    oracle_raw.get("success_condition"), "oracle.success_condition",
                    error=InvalidOracleDeclaration,
                ),
                material_excluded_from_workspace=oracle_raw.get(
                    "material_excluded_from_workspace"
                )
                is True,
            ),
            success_conditions=_tokens(raw.get("success_conditions"), "success_conditions"),
            regression_conditions=tuple(regression),
            security_constraints=_tokens(
                raw.get("security_constraints"), "security_constraints"
            ),
            time_budget_seconds=raw.get("time_budget_seconds"),
            cost_budget=dict(cost_budget) if isinstance(cost_budget, Mapping) else None,
        )


def _default_registry() -> ToolRegistry:
    """The v1 registry, imported lazily.

    Lazy so that `benchmarks.task` can be imported by a schema test without pulling the
    eight adapters in, and so the import is a plain function call rather than a module
    side effect.
    """
    from tools import default_registry

    return default_registry()


# ---------------------------------------------------------------------------
# corpus loading
# ---------------------------------------------------------------------------

TASK_FILE_NAME = "task.yaml"


def load_task(path: str | Path, *, registry: ToolRegistry | None = None) -> TaskDefinition:
    """Load one `task.yaml`.

    YAML because the corpus is reviewed material, read by people, and the rest of the
    repository's reviewed configuration is YAML. `yaml.safe_load` only: a corpus file is
    data, and a data file that can construct objects is a data file that can execute.
    """
    import yaml

    task_path = Path(path)
    if not task_path.is_file():
        raise CorpusError(f"{task_path} is not a file")
    try:
        raw = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CorpusError(f"{task_path} is not valid YAML: {type(exc).__name__}") from exc
    return TaskDefinition.from_mapping(raw, registry=registry)


def load_corpus(
    root: str | Path, *, registry: ToolRegistry | None = None
) -> tuple[TaskDefinition, ...]:
    """Load every task under a corpus root.

    The layout is `root/<task_id>/task.yaml`. A directory without one is REJECTED
    rather than skipped: a silently skipped task is a task that is absent from a
    corpus while reading as though the corpus were complete.
    """
    corpus_root = Path(root)
    if not corpus_root.is_dir():
        raise CorpusError(f"{corpus_root} is not a directory")

    tasks: list[TaskDefinition] = []
    for entry in sorted(corpus_root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        task_file = entry / TASK_FILE_NAME
        if not task_file.is_file():
            raise CorpusError(
                f"{entry} holds no {TASK_FILE_NAME}. Every corpus directory declares a "
                "task; a directory that declares none is refused rather than skipped"
            )
        task = load_task(task_file, registry=registry)
        if task.task_id != entry.name:
            raise CorpusError(
                f"{task_file} declares task_id {task.task_id!r} but lives in {entry.name!r}; "
                "the directory names the task and the two must agree"
            )
        tasks.append(task)

    ids = [task.task_id for task in tasks]
    if len(set(ids)) != len(ids):
        raise CorpusError(f"duplicate task_id in {corpus_root}: {sorted(ids)}")
    return tuple(tasks)
