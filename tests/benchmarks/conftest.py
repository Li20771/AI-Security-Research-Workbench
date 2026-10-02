"""Shared fixtures for the AI-11 benchmark tests.

The helpers here build MINIMAL valid records, so that each test changes exactly the one
field it is about. A test that has to build a whole valid TaskDefinition inline to make
one assertion is a test whose failure is hard to read.
"""

from __future__ import annotations

import re
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

    What it implements is the CLI CONTRACT, and the contract is the one the real YARA
    4.5.0 binary was MEASURED to have:

    ```text
        0 + "<rule identifier> <target>" on stdout   the rule MATCHED
        0 + an empty stdout                          the rule did NOT match
        non-zero + a diagnostic on stderr            the invocation failed
    ```

    The exit code does NOT separate a match from a non-match: the real CLI exits 0 for
    both, and returns 1 for a rule it cannot compile, a target it cannot open, or bad
    arguments.

    An earlier version of this double encoded `0 = match, 1 = no match`. That is not a
    contract yara has ever had, and because the double was the only scanner most hosts
    had, it made the collector's misreading of the exit code look correct — the tests
    agreed with the defect instead of catching it. A double that disagrees with the tool
    it stands in for is worse than no double at all.

    What it does NOT implement is YARA. A rule outside the subset below is not evaluated
    faithfully, and any test relying on one would be testing this class rather than the
    scanner. The subset is `$name = "literal" ascii`, `$name = /regex/`, and a condition
    built from `any of (...)`, `N of (...)`, a bare `$name`, joined by `or`. The
    real-scanner test is marked `skipif` on the binary being absent, and it is the one
    that says whether the corpus's fixtures and rules actually agree.
    """

    def __init__(self, *, failure: str = "") -> None:
        """`failure` makes every invocation fail the way a refused rule does: a non-zero
        exit, a diagnostic on stderr, and nothing on stdout."""
        self.calls: list[list[str]] = []
        self._failure = failure

    def run(self, argv, *, cwd=None, timeout_seconds=0):  # noqa: ANN001, ANN201
        from benchmarks.oracle import ProcessResult

        args = list(argv)
        self.calls.append(args)
        if self._failure:
            return ProcessResult(exit_code=1, stderr=self._failure)
        if args[0] != "yara" or len(args) != 3:
            return ProcessResult(
                exit_code=1, stderr="usage: yara [OPTION]... [NAMESPACE:]RULES_FILE... FILE"
            )
        try:
            rule_text = Path(args[1]).read_text(encoding="utf-8")
            sample_text = Path(args[2]).read_text(encoding="utf-8")
        except OSError as exc:
            # The real CLI's wording for this case, on the stream it uses for it.
            return ProcessResult(exit_code=1, stderr=f"error scanning {args[2]}: {exc}")
        # One line per MATCHING rule, naming the rule and echoing the target path the
        # invocation was given. A rule that did not match prints nothing at all.
        try:
            names = _stub_yara_matching_rules(rule_text, sample_text)
        except ValueError as exc:
            return ProcessResult(exit_code=1, stderr=f"error: {exc}")
        return ProcessResult(exit_code=0, stdout="".join(f"{name} {args[2]}\n" for name in names))


#: A rule declaration, anchored at the start of a line so that the word "rule" in a
#: comment is not read as one. Deliberately NOT imported from `benchmarks.oracles`: the
#: double parses the fixtures itself, so a defect in the collector's own declaration
#: parser cannot be hidden by both sides making the same mistake.
_STUB_RULE_DECLARATION = re.compile(
    r"^[ \t]*(?:(?:private|global)[ \t]+)*rule[ \t]+([A-Za-z_]\w*)", re.MULTILINE
)

_STUB_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _stub_yara_matching_rules(rule_text: str, sample_text: str) -> list[str]:
    """The identifiers of the rules whose `condition` the sample satisfies.

    Raises `ValueError` when a declaration has no body, which every YARA would refuse to
    compile — `StubYara.run` turns that into the non-zero exit the real CLI gives.
    """
    source = _STUB_BLOCK_COMMENT.sub(" ", rule_text)
    declarations = list(_STUB_RULE_DECLARATION.finditer(source))
    matching: list[str] = []
    for index, declaration in enumerate(declarations):
        end = declarations[index + 1].start() if index + 1 < len(declarations) else len(source)
        try:
            body_start = source.index("{", declaration.end(), end)
        except ValueError as exc:
            raise ValueError(f"rule {declaration.group(1)!r} has no body") from exc
        # The rule's own closing brace ends its body. `rsplit` takes the LAST one, so a
        # quantifier inside a regex (`/a{2,3}/`) does not truncate the body early.
        body = source[body_start + 1 : end].rsplit("}", 1)[0]
        if _stub_condition_holds(body, sample_text):
            matching.append(declaration.group(1))
    return matching


def _stub_condition_holds(body: str, sample_text: str) -> bool:
    literals = dict(re.findall(r'(\$\w+)\s*=\s*"([^"]*)"\s*ascii', body))
    patterns = dict(re.findall(r"(\$\w+)\s*=\s*/([^/]+)/", body))

    def hits(name: str) -> bool:
        if name in literals:
            return literals[name] in sample_text
        if name in patterns:
            return re.search(patterns[name], sample_text) is not None
        return False

    _, _, condition = body.partition("condition:")
    for clause in re.split(r"\bor\b", condition):
        clause = clause.strip()
        match = re.match(r"any of \(([^)]*)\)", clause)
        if match and any(hits(n.strip()) for n in match.group(1).split(",")):
            return True
        match = re.match(r"(\d+) of \(([^)]*)\)", clause)
        if match and sum(hits(n.strip()) for n in match.group(2).split(",")) >= int(
            match.group(1)
        ):
            return True
        match = re.match(r"(\$\w+)\s*$", clause)
        if match and hits(match.group(1)):
            return True
    return False


def cantools_available() -> bool:
    """Whether A.1's declared decoder is importable on this host."""
    import importlib.util

    return importlib.util.find_spec("cantools") is not None


def yara_available() -> bool:
    """Whether the real scanner is on this host."""
    import shutil

    return shutil.which("yara") is not None
