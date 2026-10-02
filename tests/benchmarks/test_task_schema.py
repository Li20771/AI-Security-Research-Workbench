"""AI-11 §5, §7.3, §12 — the TaskDefinition schema. Layer 1: contract and schema.

The load-bearing assertions here are the two refusals: a TaskDefinition that carries a
result, and a source_sha that is not a full commit id. Everything else is shape.
"""

from __future__ import annotations

import copy
import dataclasses
from pathlib import Path

import pytest

from benchmarks.errors import (
    InvalidOracleDeclaration,
    InvalidTaskDefinition,
    UnregisteredTool,
)
from benchmarks.task import (
    FORBIDDEN_TASK_FIELDS,
    TASK_ID_RE,
    TaskDefinition,
    load_corpus,
)
from benchmarks.vocabulary import Difficulty, OracleKind, TaskFamily
from tests.benchmarks.conftest import REMOVE, SOURCE_SHA, valid_task_mapping

pytestmark = pytest.mark.layer1


# ---------------------------------------------------------------------------
# T1 — task_id grammar (§5.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "task_id",
    [
        "ai11-v1-can-dbc-decode",
        "ai11-v1-a",
        "ai11-v1-a1-b2-c3",
    ],
)
def test_T1_task_id_grammar_accepts(task_id: str) -> None:
    assert TASK_ID_RE.match(task_id)
    task = TaskDefinition.from_mapping(valid_task_mapping(task_id=task_id))
    assert task.task_id == task_id


@pytest.mark.parametrize(
    "task_id",
    [
        "ai11-can-dbc-decode",       # missing the version segment
        "ai11-v1-Can-Dbc",           # uppercase
        "ai11-v1-can_dbc",           # underscore outside the grammar
        "ai11-v1--leading",          # empty segment
        "ai11-v1-trailing-",         # trailing separator
        "v1-can-dbc",                # wrong prefix
        "",
    ],
)
def test_T2_task_id_grammar_rejects(task_id: str) -> None:
    with pytest.raises(InvalidTaskDefinition):
        TaskDefinition.from_mapping(valid_task_mapping(task_id=task_id))


def test_T3_task_id_is_not_normalised() -> None:
    """A rejected id is refused, never quietly reshaped into an accepted one."""
    with pytest.raises(InvalidTaskDefinition) as excinfo:
        TaskDefinition.from_mapping(valid_task_mapping(task_id="AI11-V1-CAN"))
    assert "AI11-V1-CAN" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T4 — source_sha (§5.3)
# ---------------------------------------------------------------------------


def test_T4_full_commit_id_is_accepted(valid_task: TaskDefinition) -> None:
    assert valid_task.source_sha == SOURCE_SHA


@pytest.mark.parametrize(
    "sha",
    [
        "HEAD",
        "main",
        "latest",
        "v1.0.0",
        "2026-10-02",
        "efa836f",                                    # short sha
        "EFA836FF9225F6226CA8A76615F3F45C31110D58",   # uppercase
        "efa836ff9225f6226ca8a76615f3f45c31110d5",    # 39 characters
        "efa836ff9225f6226ca8a76615f3f45c31110d58a",  # 41 characters
        "zzz836ff9225f6226ca8a76615f3f45c31110d58",   # not hex
        "refs/heads/main",
    ],
)
def test_T5_source_sha_must_be_a_full_commit_id(sha: str) -> None:
    with pytest.raises(InvalidTaskDefinition) as excinfo:
        TaskDefinition.from_mapping(valid_task_mapping(source_sha=sha))
    assert "source_sha" in str(excinfo.value)


def test_T6_source_sha_existence_is_not_checked_at_load() -> None:
    """§5.3 checks SHAPE here and EXISTENCE at run time.

    A well-formed sha that does not exist must still LOAD. Existence is a precondition,
    and a precondition failure is BLOCKED — a different fact from "this is not a task".
    Collapsing them would let an environment problem be reported as a schema defect.
    """
    task = TaskDefinition.from_mapping(
        valid_task_mapping(source_sha="0" * 40)
    )
    assert task.source_sha == "0" * 40


# ---------------------------------------------------------------------------
# T7 — a TaskDefinition never carries a result (§5.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", sorted(FORBIDDEN_TASK_FIELDS))
def test_T7_result_shaped_fields_are_rejected(field: str) -> None:
    mapping = valid_task_mapping()
    mapping[field] = "anything"
    with pytest.raises(InvalidTaskDefinition) as excinfo:
        TaskDefinition.from_mapping(mapping)
    assert field in str(excinfo.value)


def test_T8_the_result_refusal_is_named_not_generic() -> None:
    """A definition carrying `pass_rate` is refused FOR carrying it.

    Not for "unknown field". The two messages send a reader to different places, and the
    wrong one sends them to fix a typo instead of a design error.
    """
    mapping = valid_task_mapping()
    mapping["pass_rate"] = 0.5
    with pytest.raises(InvalidTaskDefinition) as excinfo:
        TaskDefinition.from_mapping(mapping)
    assert "run result" in str(excinfo.value)


def test_T9_unknown_top_level_field_is_rejected(valid_task: TaskDefinition) -> None:
    mapping = valid_task_mapping()
    mapping["notes"] = "hello"
    with pytest.raises(InvalidTaskDefinition) as excinfo:
        TaskDefinition.from_mapping(mapping)
    assert "notes" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T10 — immutability (§5.1)
# ---------------------------------------------------------------------------


def test_T10_task_definition_is_frozen(valid_task: TaskDefinition) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        valid_task.task_id = "ai11-v1-other"  # type: ignore[misc]


def test_T11_source_mapping_mutation_does_not_reach_the_task() -> None:
    """The definition copies its inputs; a caller cannot mutate it afterwards.

    A shared nested dict is how a frozen dataclass ends up mutable in practice.
    """
    mapping = valid_task_mapping()
    task = TaskDefinition.from_mapping(copy.deepcopy(mapping))
    before = task.to_mapping()
    mapping["workspace_setup"]["include"].append("control/truth.json")
    mapping["oracle"]["success_condition"] = "something else"
    assert task.to_mapping() == before


# ---------------------------------------------------------------------------
# T12 — workspace_setup (§5.4)
# ---------------------------------------------------------------------------


def test_T12_author_supplied_manifest_digest_is_rejected() -> None:
    """§5.4 makes manifest_digest HARNESS-MEASURED."""
    mapping = valid_task_mapping()
    mapping["workspace_setup"]["manifest_digest"] = "a" * 64
    with pytest.raises(InvalidTaskDefinition) as excinfo:
        TaskDefinition.from_mapping(mapping)
    assert "manifest_digest" in str(excinfo.value)


def test_T13_generated_artifacts_are_declared_not_assumed() -> None:
    task = TaskDefinition.from_mapping(
        valid_task_mapping(
            workspace_setup={
                "include": ["task/README.txt"],
                "exclude": ["control"],
                "generated": ["work/hello_arm64"],
            }
        )
    )
    assert task.workspace_setup.generated == ("work/hello_arm64",)


# ---------------------------------------------------------------------------
# T14 — tools (§5.6)
# ---------------------------------------------------------------------------


def test_T14_unregistered_tool_is_rejected() -> None:
    mapping = valid_task_mapping(
        allowed_tools=[{"tool_id": "nosuchtool", "operation": "read_file"}]
    )
    with pytest.raises(UnregisteredTool):
        TaskDefinition.from_mapping(mapping)


def test_T15_unregistered_operation_is_rejected() -> None:
    mapping = valid_task_mapping(
        allowed_tools=[{"tool_id": "git", "operation": "commit"}]
    )
    with pytest.raises(UnregisteredTool) as excinfo:
        TaskDefinition.from_mapping(mapping)
    assert "commit" in str(excinfo.value)


def test_T16_a_pair_cannot_be_both_allowed_and_forbidden() -> None:
    pair = [{"tool_id": "git", "operation": "read_file"}]
    with pytest.raises(InvalidTaskDefinition) as excinfo:
        TaskDefinition.from_mapping(
            valid_task_mapping(allowed_tools=pair, forbidden_tools=pair)
        )
    assert "both allowed and forbidden" in str(excinfo.value)


def test_T17_github_and_mcp_declare_no_operation() -> None:
    """The v1 registry declares no operation for either family, so neither is nameable.

    This is asserted rather than assumed: if a later phase opens one of these families,
    this test fails and the corpus gets reviewed instead of silently gaining a
    network-capable tool.
    """
    for tool_id in ("github", "mcp"):
        with pytest.raises(UnregisteredTool):
            TaskDefinition.from_mapping(
                valid_task_mapping(
                    allowed_tools=[{"tool_id": tool_id, "operation": "anything"}]
                )
            )


# ---------------------------------------------------------------------------
# T18 — the oracle declaration (§7.3, §7.4)
# ---------------------------------------------------------------------------


def test_T18_oracle_material_must_be_excluded() -> None:
    """§7.2, FROZEN. An oracle the Agent can read is not an oracle."""
    mapping = valid_task_mapping()
    mapping["oracle"]["material_excluded_from_workspace"] = False
    with pytest.raises(InvalidOracleDeclaration) as excinfo:
        TaskDefinition.from_mapping(mapping)
    assert "material_excluded_from_workspace" in str(excinfo.value)


@pytest.mark.parametrize("missing", ["known_good", "known_bad"])
def test_T19_discrimination_control_is_required(missing: str) -> None:
    """§7.4. An oracle that cannot fail is not an oracle."""
    mapping = valid_task_mapping()
    del mapping["oracle"]["expected_negative"][missing]
    with pytest.raises(InvalidOracleDeclaration):
        TaskDefinition.from_mapping(mapping)


def test_T20_oracle_kind_is_closed() -> None:
    mapping = valid_task_mapping()
    mapping["oracle"]["kind"] = "VIBES"
    with pytest.raises(InvalidOracleDeclaration):
        TaskDefinition.from_mapping(mapping)


def test_T21_oracle_kinds_are_the_five_frozen_members() -> None:
    assert sorted(m.value for m in OracleKind) == [
        "CONTROLLED_REPRODUCTION",
        "DIFF_INSPECTION",
        "INDEPENDENT_TEST",
        "SECURITY_BOUNDARY_FACT",
        "TRACKED_DEFINITION",
    ]


# ---------------------------------------------------------------------------
# T22 — closed vocabularies (§5.5, §17.1)
# ---------------------------------------------------------------------------


def test_T22_family_and_difficulty_are_closed() -> None:
    with pytest.raises(InvalidTaskDefinition):
        TaskDefinition.from_mapping(valid_task_mapping(task_family="web"))
    with pytest.raises(InvalidTaskDefinition):
        TaskDefinition.from_mapping(valid_task_mapping(difficulty="EXPERT"))


def test_T23_task_family_covers_the_six_annex_a_families() -> None:
    assert sorted(m.value for m in TaskFamily) == [
        "can",
        "firmware",
        "fuzzing_recovery",
        "reverse",
        "uds",
        "yara",
    ]


def test_T24_difficulty_is_an_ordinal_label_not_a_score() -> None:
    """§5.5. Three members, and no numeric value anywhere in the type."""
    assert sorted(m.value for m in Difficulty) == ["ADVANCED", "INTERMEDIATE", "INTRODUCTORY"]
    for member in Difficulty:
        assert not member.value.replace(".", "").isdigit()


# ---------------------------------------------------------------------------
# T25 — regression conditions (§12)
# ---------------------------------------------------------------------------


def test_T25_regression_kind_is_closed() -> None:
    mapping = valid_task_mapping(
        regression_conditions=[
            {
                "condition_id": "c1",
                "kind": "VIBES",
                "reproduce_command": "true",
                "required": True,
            }
        ]
    )
    with pytest.raises(InvalidTaskDefinition):
        TaskDefinition.from_mapping(mapping)


def test_T26_regression_conditions_are_structured(valid_task: TaskDefinition) -> None:
    task = TaskDefinition.from_mapping(
        valid_task_mapping(
            regression_conditions=[
                {
                    "condition_id": "factor-offset-transposition",
                    "kind": "FROZEN_DEFINITION",
                    "reproduce_command": "python3 -m benchmarks.replay x --variant known_bad",
                    "required": True,
                }
            ]
        )
    )
    assert len(task.regression_conditions) == 1
    assert task.regression_conditions[0].kind == "FROZEN_DEFINITION"


# ---------------------------------------------------------------------------
# T27 — class 4 is bounded (§18.3)
# ---------------------------------------------------------------------------


def test_T27_task_description_must_be_single_line() -> None:
    with pytest.raises(InvalidTaskDefinition) as excinfo:
        TaskDefinition.from_mapping(
            valid_task_mapping(task_description="line one\nline two")
        )
    assert "single line" in str(excinfo.value)


def test_T28_task_description_is_length_bounded() -> None:
    with pytest.raises(InvalidTaskDefinition):
        TaskDefinition.from_mapping(valid_task_mapping(task_description="x" * 513))


def test_T29_success_conditions_are_machine_tokens() -> None:
    """§18.3 keeps Class 4 to `task_description` alone."""
    with pytest.raises(InvalidTaskDefinition):
        TaskDefinition.from_mapping(
            valid_task_mapping(success_conditions=['a "quoted" condition'])
        )


# ---------------------------------------------------------------------------
# T30 — projection is an allowlist (§18.1)
# ---------------------------------------------------------------------------


def test_T30_to_mapping_is_an_explicit_allowlist(valid_task: TaskDefinition) -> None:
    projected = valid_task.to_mapping()
    assert set(projected) == {
        "schema_version",
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
    }


def test_T31_cost_budget_null_is_not_zero(valid_task: TaskDefinition) -> None:
    """§9.4. `no budget declared` and `a budget of zero` are different facts."""
    assert valid_task.cost_budget is None
    assert valid_task.to_mapping()["cost_budget"] is None

    with pytest.raises(InvalidTaskDefinition):
        TaskDefinition.from_mapping(valid_task_mapping(cost_budget=0))


# ---------------------------------------------------------------------------
# T32 — corpus loading (§17)
# ---------------------------------------------------------------------------


def test_T32_corpus_directory_without_a_task_is_refused(tmp_path: Path) -> None:
    (tmp_path / "ai11-v1-empty").mkdir()
    with pytest.raises(Exception) as excinfo:
        load_corpus(tmp_path)
    assert "task.yaml" in str(excinfo.value)


def test_T33_corpus_directory_name_must_match_task_id(tmp_path: Path) -> None:
    import yaml

    directory = tmp_path / "ai11-v1-wrong-name"
    directory.mkdir()
    (directory / "task.yaml").write_text(
        yaml.safe_dump(valid_task_mapping()), encoding="utf-8"
    )
    with pytest.raises(Exception) as excinfo:
        load_corpus(tmp_path)
    assert "must agree" in str(excinfo.value)


def test_T34_a_missing_required_field_is_named() -> None:
    with pytest.raises(InvalidTaskDefinition) as excinfo:
        TaskDefinition.from_mapping(valid_task_mapping(time_budget_seconds=REMOVE))
    assert "time_budget_seconds" in str(excinfo.value)
