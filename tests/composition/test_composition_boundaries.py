"""AI-14-B / B6 — the authority boundaries, verified end to end.

§4.2's rules are restatements of clauses other phases froze. A composition is
exactly where they can be lost quietly — each layer is correct alone and the
wiring gives one of them a power it never had — so each rule below is checked
across the CONNECTED path rather than inside one layer.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from agents.body import BodyOutcome
from agents.request import AgentExecutionRequest
from agents.vocabulary import AgentId
from plugins.guard.vocabulary import GuardDecision
from plugins.security_tools.vocabulary import ToolOutcome
from providers.model_profile import CapabilityName, CapabilityStatus
from tools import default_registry

from composition.executor import AgentStepExecutor
from agents.body import OfflineBody

from composition.provider import ExecutionBinding, offline_body_factory
from composition.root import run_task

from tests.composition.conftest import (
    ALL_PROVIDERS,
    A_MODEL_REF,
    PROFILES,
    a_router_request,
    a_rule_set,
    a_workspace,
)

pytestmark = pytest.mark.layer2


class _ToolCallingBody:
    """A body that makes exactly one declared tool call, through the gateway.

    It reaches the tool path the only way a body can: `tools.invoke`, which asks
    Guard. It does not touch the registry and does not decide anything.
    """

    agent_id = AgentId.DSH

    def __init__(self, invocation) -> None:  # noqa: ANN001
        self._invocation = invocation

    def run(self, *, request, context, tools):  # noqa: ANN001, ANN201
        self.reference = tools.invoke(self._invocation)
        return BodyOutcome(result_ref="sha256:" + "cd" * 32)


def _run(tmp_path, body_factory=None, **overrides):
    root, _ = a_workspace(tmp_path / "ws")
    arguments = {
        "workspace_root": str(root),
        "task": "wf-demo/v1/s1",
        "input_digest": "0" * 64,
        "router_request": a_router_request(),
        "rule_set": a_rule_set(),
        "profiles": PROFILES,
        "enabled_providers": ALL_PROVIDERS,
        "body_factory": body_factory if body_factory is not None else offline_body_factory(),
        "default_agent": AgentId.DSH,
        "registry": default_registry(),
        "policy": None,
        "clock": lambda: "2026-10-04T00:00:00Z",
    }
    arguments.update(overrides)
    return run_task(**arguments), root


def test_the_router_does_not_authorize_the_tool_call_it_selected_for(tmp_path) -> None:
    """SECURITY BOUNDARY. §4.2 rule 1.

    The Router SELECTED, the execution ran — and the tool invocation the execution
    made was still decided by GUARD, which refused it. The selection authorized
    nothing: a decision that granted permission would have made this call
    COMPLETED.
    """
    from tests.composition.test_controlled_verification import _an_entry

    entry = _an_entry("t-a")
    from agents.toolcall import ToolInvocation

    body = _ToolCallingBody(
        ToolInvocation(
            tool_id=entry.tool_id,
            tool_version=entry.tool_version,
            adapter_family=entry.adapter_family,
            operation=entry.operation,
            permission_level=entry.permission_level,
            target=entry.target,
            timeout_seconds=entry.timeout_seconds,
        )
    )
    def a_factory(*, model_ref, agent_id):
        return ExecutionBinding(body=body, model_ref=None)

    outcome, _ = _run(tmp_path, body_factory=a_factory)

    assert outcome.decision.outcome.value == "SELECTED"
    call = outcome.result.tool_calls[0]
    assert call.outcome is ToolOutcome.BLOCKED
    assert call.outcome is not ToolOutcome.COMPLETED
    # The refusal is attributable to a real Guard evaluation.
    assert call.guard_decision is GuardDecision.BLOCKED
    assert call.guard_decision_id.startswith("grd-")


def test_one_agent_result_cannot_become_another_agents_request(tmp_path) -> None:
    """§4.2 rule 8. AI-08 refuses a result riding into a request by name.

    The composition cannot launder one execution's result into the next
    execution's input, because the shape it would have to use refuses the field.
    """
    for refused in ("result", "agent_result", "previous_result", "other_result"):
        with pytest.raises(ValueError):
            AgentExecutionRequest.from_mapping(
                {
                    "schema_version": 1,
                    "agent_id": "dsh",
                    "workspace": {"root": str(tmp_path)},
                    "task": "wf-demo/v1/s1",
                    "input": "0" * 64,
                    refused: {"result_ref": "sha256:" + "00" * 32},
                }
            )


def test_wiring_did_not_verify_a_capability(tmp_path) -> None:
    """§4.2 rule 10, §8. Every shipped capability is still UNKNOWN after a run.

    The composed path ran end to end and promoted nothing: a capability becomes
    VERIFIED by a contracted live verification, and live verification is NOT_RUN.
    """
    _run(tmp_path)

    profile = PROFILES[A_MODEL_REF]
    assert all(
        profile.capability(capability).status is not CapabilityStatus.VERIFIED
        for capability in CapabilityName
    )


_EVIDENCE_ROOT = "plugins.evidence"
_ADMISSION_ENTRY_POINTS = frozenset({"admit", "admit_to_store"})


def _dotted(node: ast.expr) -> str | None:
    """The dotted source of a Name/Attribute chain, or None if it is not one."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _admission_calls_in_tree(tree: ast.Module) -> list[tuple[int, str]]:
    """`(lineno, what)` for every call in ONE parsed module that can reach admission.

    THE POINT OF RESOLVING NAMES RATHER THAN MATCHING THEM is that the same call has
    several spellings and a name-only check sees one of them:

        from plugins.evidence import admit                  ->  admit(record)
        from plugins.evidence.admission import
            admit_to_store as persist                       ->  persist(record, store=..)
        import plugins.evidence.admission as adm            ->  adm.admit(record)
        plugins.evidence.admission.admit(record)            (fully qualified)

    plus a name REBOUND from any of those (`f = admit` then `f(record)`), followed to
    a fixed point.

    A WILDCARD IMPORT FROM THE PACKAGE IS REFUSED RATHER THAN RESOLVED: it makes the
    call set unknowable from this file, and a static read must not guess at one.

    NOT DETECTED, stated rather than overclaimed. This reads ONE module statically,
    and these are its limits:

        `getattr(module, "admit")`, `importlib.import_module(...)`,
          `__import__(...)`, and any name assembled from a string at runtime
        a name imported from a THIRD module that re-exports an entry point — this
          walk does not follow imports across files
        a callable handed in from outside the package and invoked here

    THOSE ARE NOT COVERED BY THIS TEST, and it MUST NOT be described as exhaustive.
    They are what the Layer 0 rule and review are for.
    """
    call_names: set[str] = set()
    module_roots: set[str] = set()
    findings: list[tuple[int, str]] = []

    # Pass 1 — every import that could bind an entry point or the package itself.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            reaches = node.module == _EVIDENCE_ROOT or node.module.startswith(
                _EVIDENCE_ROOT + "."
            )
            if not reaches:
                continue
            for alias in node.names:
                if alias.name == "*":
                    findings.append(
                        (
                            node.lineno,
                            f"wildcard import from {_EVIDENCE_ROOT}: the call set "
                            "cannot be resolved statically",
                        )
                    )
                elif alias.name in _ADMISSION_ENTRY_POINTS:
                    call_names.add(alias.asname or alias.name)
                elif alias.name == "admission":
                    module_roots.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _EVIDENCE_ROOT or alias.name.startswith(
                    _EVIDENCE_ROOT + "."
                ):
                    module_roots.add(alias.asname or alias.name.split(".")[0])

    # Pass 2 — names rebound from an already-resolved alias, to a fixed point.
    for _ in range(len(call_names) + 1):
        before = set(call_names)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
                if node.value.id in call_names:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            call_names.add(target.id)
        if call_names == before:
            break

    # Pass 3 — the calls themselves.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in call_names:
            findings.append((node.lineno, f"calls {func.id}()"))
        elif isinstance(func, ast.Attribute) and func.attr in _ADMISSION_ENTRY_POINTS:
            dotted = _dotted(func.value)
            if dotted is None:
                continue
            if dotted.split(".")[0] in module_roots or dotted.startswith(_EVIDENCE_ROOT):
                findings.append((node.lineno, f"calls {dotted}.{func.attr}()"))

    return findings


def _admission_call_sites(package: pathlib.Path) -> list[str]:
    """Every call under `package/*.py` that can reach an admission entry point."""
    findings: list[str] = []
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        findings.extend(
            f"{path.name}:{line} {what}"
            for line, what in _admission_calls_in_tree(tree)
        )
    return findings


def test_the_composition_reaches_no_evidence_writer() -> None:
    """B5 stays BLOCKED: no module here CALLS admission, and that is the boundary.

    THE IMPORT IS NO LONGER THE BOUNDARY. AI-14 Amendment 2 (§22.1 B5, STEP 1)
    AUTHORIZED the composition -> Evidence edge, so `plugins.evidence` is a layer
    this package may import and this test no longer refuses it. AN AUTHORIZED IMPORT
    IS PERMISSION TO WRITE A CALL, NOT A CALL.

    WHAT IS STILL CHECKED IS THE CALL — the current-state fact §5.1 and Appendix A
    depend on: no module in this package calls `admit` or `admit_to_store`, which is
    what keeps the edge IMPLEMENTED BUT NOT CONNECTED. If a call appears here, the
    edge is being connected, and §22.1 requires that change to carry the
    classification update in the SAME merged change rather than after it.

    Checked by CALL rather than by the word: the docstrings explain the rule, and a
    word scan would flag the explanation as the violation — the same distinction
    `layer0_policy` makes when it reads identifiers rather than text.
    """
    package = pathlib.Path(__file__).resolve().parents[2] / "composition"
    assert _admission_call_sites(package) == []


def test_the_absence_check_allows_an_authorized_import_with_no_call(
    tmp_path: pathlib.Path,
) -> None:
    """The import is PERMITTED; only the call is refused. A control, not a violation.

    Without this, a check that fired on the import as well would still pass the
    absence test above while contradicting AI-14 STEP 1.
    """
    package = tmp_path / "composition"
    package.mkdir()
    (package / "zz_imported.py").write_text(
        "from plugins.evidence import ExecutionPayload, ToolCall\n"
        "from plugins.evidence.admission import admit_to_store as persist\n"
        "\n"
        "__all__ = ['ExecutionPayload', 'ToolCall', 'persist']\n",
        encoding="utf-8",
    )
    assert _admission_call_sites(package) == []


@pytest.mark.parametrize(
    "planted",
    [
        pytest.param(
            "from plugins.evidence.admission import admit_to_store as persist\n"
            "\n"
            "\n"
            "def submit(record, store):\n"
            "    return persist(record, store=store)\n",
            id="renamed-import-of-an-entry-point",
        ),
        pytest.param(
            "from plugins.evidence import admit as submit_record\n"
            "\n"
            "\n"
            "def submit(record):\n"
            "    return submit_record(record)\n",
            id="renamed-package-level-import",
        ),
        pytest.param(
            "import plugins.evidence.admission as adm\n"
            "\n"
            "\n"
            "def submit(record):\n"
            "    return adm.admit(record)\n",
            id="module-alias-attribute-call",
        ),
        pytest.param(
            "import plugins.evidence.admission\n"
            "\n"
            "\n"
            "def submit(record):\n"
            "    return plugins.evidence.admission.admit(record)\n",
            id="fully-qualified-call",
        ),
        pytest.param(
            "from plugins.evidence import admit\n"
            "\n"
            "submit = admit\n"
            "\n"
            "\n"
            "def go(record):\n"
            "    return submit(record)\n",
            id="entry-point-rebound-to-another-name",
        ),
    ],
)
def test_the_absence_check_catches_an_aliased_admission_call(
    planted: str, tmp_path: pathlib.Path
) -> None:
    """THE CONTROL THAT MAKES THE ABSENCE TEST MEAN SOMETHING.

    Each case below is the SAME call the absence test refuses, written so that a
    name-only match would miss it. If any of them stopped being reported, the
    absence test above would still pass — and would have stopped meaning anything.
    """
    package = tmp_path / "composition"
    package.mkdir()
    (package / "zz_planted.py").write_text(planted, encoding="utf-8")
    findings = _admission_call_sites(package)
    assert findings, f"an admission call was planted and NOT detected:\n{planted}"


def test_the_composition_adds_no_authority_vocabulary() -> None:
    """§4.2. The glue names no grant of its own.

    `ALLOW` may be READ (the tool path owns that decision) but this package never
    constructs one, and it holds no approval, trust-root or producer vocabulary at
    all.
    """
    package = pathlib.Path(__file__).resolve().parents[2] / "composition"
    forbidden = (
        "Ed25519PrivateKey",
        "ApprovalRef",
        "ApprovalStatus",
        "producer_token",
        "ADMITTED_EVENTS",
        "ALLOWED",
    )
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name in forbidden:
            assert name not in text, f"{path.name} names {name}"


def test_the_composition_holds_no_workflow_state(tmp_path) -> None:
    """§4.2 rule 7. The executor returns an outcome; the engine owns the record.

    The value the executor produces has no field a run, a step or an approval
    could travel in — so a delegation cannot carry workflow state back out of
    AI-08, and cannot carry any in.
    """
    from workflows.engine import ExecutionOutcome

    fields = set(ExecutionOutcome.__dataclass_fields__)
    assert not (fields & {"run_id", "steps", "approvals", "state", "scope_digest"})

    root, _ = a_workspace(tmp_path / "ws")
    executor = AgentStepExecutor(
        body=OfflineBody(agent_id=AgentId.DSH),
        agent_id=AgentId.DSH,
        workspace_root=str(root),
        clock=lambda: "2026-10-04T00:00:00Z",
    )
    assert not hasattr(executor, "run")
    assert not hasattr(executor, "approvals")
