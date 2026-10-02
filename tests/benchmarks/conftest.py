"""Shared fixtures for the AI-11 benchmark tests.

The helpers here build MINIMAL valid records, so that each test changes exactly the one
field it is about. A test that has to build a whole valid TaskDefinition inline to make
one assertion is a test whose failure is hard to read.
"""

from __future__ import annotations

from typing import Any

import pytest

from benchmarks.task import TaskDefinition

#: The pinned SecurityLab revision the v1 corpus names. Used as data, never resolved:
#: these tests do not clone anything.
SOURCE_SHA = "efa836ff9225f6226ca8a76615f3f45c31110d58"


def valid_task_mapping(**overrides: Any) -> dict[str, Any]:
    """A TaskDefinition mapping that validates, with `overrides` applied.

    Overriding a key to the sentinel `REMOVE` deletes it, so a test can assert on a
    missing required field without rebuilding the mapping.
    """
    mapping: dict[str, Any] = {
        "schema_version": 1,
        "task_id": "ai11-v1-test-fixture",
        "task_version": 1,
        "task_family": "can",
        "difficulty": "INTRODUCTORY",
        "source_repository": "Li20771/SecurityLab",
        "source_sha": SOURCE_SHA,
        "workspace_setup": {
            "include": ["task/input.txt"],
            "exclude": ["control"],
            "generated": [],
        },
        "task_description": "A fixture task used by the AI-11 test suite.",
        "allowed_tools": [{"tool_id": "git", "operation": "read_file"}],
        "forbidden_tools": [{"tool_id": "terminal", "operation": "run"}],
        "required_preconditions": [],
        "oracle": {
            "oracle_id": "ai11-v1-test-fixture.oracle",
            "kind": "TRACKED_DEFINITION",
            "required": True,
            "reproduce_command": "python3 -m benchmarks.replay ai11-v1-test-fixture",
            "expected_negative": {
                "known_good": "control/known_good.json",
                "known_bad": "control/known_bad.json",
            },
            "success_condition": "the declared answer matches the tracked truth",
            "material_excluded_from_workspace": True,
        },
        "success_conditions": ["the answer matches"],
        "regression_conditions": [],
        "security_constraints": ["no operation outside the declared allowed set"],
        "time_budget_seconds": 60,
        "cost_budget": None,
    }
    for key, value in overrides.items():
        if value is REMOVE:
            mapping.pop(key, None)
        else:
            mapping[key] = value
    return mapping


class _Remove:
    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "REMOVE"


REMOVE = _Remove()


@pytest.fixture
def valid_task() -> TaskDefinition:
    return TaskDefinition.from_mapping(valid_task_mapping())
