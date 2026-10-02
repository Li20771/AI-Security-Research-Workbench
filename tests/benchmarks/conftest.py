"""Shared fixtures for the AI-11 benchmark tests.

The helpers here build MINIMAL valid records, so that each test changes exactly the one
field it is about. A test that has to build a whole valid TaskDefinition inline to make
one assertion is a test whose failure is hard to read.
"""

from __future__ import annotations

from pathlib import Path
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


# ---------------------------------------------------------------------------
# A test double for the yara CLI
# ---------------------------------------------------------------------------


class StubYara:
    """A test double for the `yara` command line. **It is NOT yara.**

    It exists because `yara` is not installed on every host, and without it the whole
    collection path would be untestable there — the oracle would be BLOCKED everywhere
    and nothing about the machinery would be exercised.

    What it does implement is the CLI CONTRACT the collector depends on:

    ```text
        0   the rule matched
        1   the rule did not match
        2   the invocation failed (bad arguments, unreadable rule)
    ```

    and the small subset of rule syntax the corpus declares: `$name = "literal" ascii`,
    `$name = /regex/`, and a condition built from `any of (...)`, `N of (...)`, a bare
    `$name`, joined by `or`.

    What it does NOT implement is YARA. A rule outside that subset is not evaluated
    faithfully, and any test relying on one would be testing this class rather than the
    scanner. The real-scanner test is marked `skipif` on the binary being absent, and it
    is the one that says whether the corpus's fixtures and rules actually agree.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        from benchmarks.oracle import ProcessResult

        args = list(argv)
        self.calls.append(args)
        if args[0] != "yara" or len(args) != 3:
            return ProcessResult(exit_code=2, stderr="usage: yara <rules> <target>")
        try:
            rule_text = Path(args[1]).read_text(encoding="utf-8")
            sample_text = Path(args[2]).read_text(encoding="utf-8")
        except OSError as exc:
            return ProcessResult(exit_code=2, stderr=str(exc))
        return ProcessResult(exit_code=_stub_yara_match(rule_text, sample_text))


def _stub_yara_match(rule_text: str, sample_text: str) -> int:
    import re as _re

    literals = dict(_re.findall(r'(\$\w+)\s*=\s*"([^"]*)"\s*ascii', rule_text))
    patterns = dict(_re.findall(r"(\$\w+)\s*=\s*/([^/]+)/", rule_text))

    def hits(name: str) -> bool:
        if name in literals:
            return literals[name] in sample_text
        if name in patterns:
            return _re.search(patterns[name], sample_text) is not None
        return False

    _, _, condition = rule_text.partition("condition:")
    # Stop at the rule's closing brace: without this the last clause carries a trailing
    # `}` and matches no clause form, so the condition silently becomes "no match".
    condition = condition.split("}", 1)[0]
    for clause in _re.split(r"\bor\b", condition):
        clause = clause.strip()
        match = _re.match(r"any of \(([^)]*)\)", clause)
        if match and any(hits(n.strip()) for n in match.group(1).split(",")):
            return 0
        match = _re.match(r"(\d+) of \(([^)]*)\)", clause)
        if match and sum(hits(n.strip()) for n in match.group(2).split(",")) >= int(
            match.group(1)
        ):
            return 0
        match = _re.match(r"(\$\w+)\s*$", clause)
        if match and hits(match.group(1)):
            return 0
    return 1


def cantools_available() -> bool:
    """Whether A.1's declared decoder is importable on this host."""
    import importlib.util

    return importlib.util.find_spec("cantools") is not None


def yara_available() -> bool:
    """Whether the real scanner is on this host."""
    import shutil

    return shutil.which("yara") is not None
