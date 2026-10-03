"""AI-13-B — T7, T8, T10, T16, T18, T22: the artifacts, and what they refuse.

Contract: `docs/AI-13_LONG_RUNNING_WORKFLOWS_EXECUTION_PLAN.md`, frozen as merged.
Every assertion here is a §-reference; none is a preference.
"""

from __future__ import annotations

import pytest

from workflows.canonical import canonical_body, digest_of
from workflows.checkpoint import CHECKPOINT_DIGEST_FIELD, Checkpoint
from workflows.definition import DIGEST_FIELD, WorkflowDefinition
from workflows.errors import InvalidCheckpoint, InvalidDefinition, InvalidRecord

from tests.workflows.conftest import T0, a_step, definition_body, limits

pytestmark = pytest.mark.layer1


# ---------------------------------------------------------------------------
# §7.4 — the canonical form, and the digest that was circular
# ---------------------------------------------------------------------------


def test_canonical_body_is_stable_under_key_order() -> None:
    """Two writers that agree about the FIELDS must agree about the bytes."""
    first = {"b": 1, "a": "x", "digest": ""}
    second = {"a": "x", "b": 1, "digest": ""}
    assert canonical_body(first, digest_field="digest") == canonical_body(
        second, digest_field="digest"
    )


def test_canonical_body_excludes_the_digest_field() -> None:
    """§7.4. The digest field is excluded, and NOTHING else."""
    one = {"a": 1, "digest": "aaa"}
    two = {"a": 1, "digest": "bbb"}
    assert canonical_body(one, digest_field="digest") == canonical_body(
        two, digest_field="digest"
    )


def test_canonical_body_treats_null_as_absent_and_empty_list_as_present() -> None:
    """§7.4 freezes both, because the alternative makes two equivalent records differ."""
    absent = canonical_body({"a": 1, "digest": ""}, digest_field="digest")
    null = canonical_body({"a": 1, "b": None, "digest": ""}, digest_field="digest")
    empty = canonical_body({"a": 1, "b": [], "digest": ""}, digest_field="digest")

    assert absent == null, "null and absent must canonicalise the same"
    assert empty != absent, "an empty list is a value, not an absence"


def test_canonical_body_refuses_a_float() -> None:
    """Two implementations disagreeing about 1.0 vs 1 produce two digests for one fact."""
    with pytest.raises(InvalidRecord):
        canonical_body({"a": 1.5, "digest": ""}, digest_field="digest")


def test_canonical_body_refuses_raw_bytes() -> None:
    """A record carries references and digests, never content (§7.2, §15.2)."""
    with pytest.raises(InvalidRecord):
        canonical_body({"blob": b"\x00\x01", "digest": ""}, digest_field="digest")


def test_canonical_body_requires_the_digest_field_to_exist() -> None:
    with pytest.raises(InvalidRecord):
        canonical_body({"a": 1}, digest_field="digest")


def test_T10_a_tampered_field_changes_the_digest() -> None:
    """§7.4. The mechanical form of the check the contract freezes for T10."""
    original = {"workflow_id": "wf-a", "attempt_no": 1, "digest": ""}
    digest = digest_of(original, digest_field="digest")

    tampered = {"workflow_id": "wf-b", "attempt_no": 1, "digest": ""}
    assert digest_of(tampered, digest_field="digest") != digest


# ---------------------------------------------------------------------------
# T16, T22 — what a definition refuses
# ---------------------------------------------------------------------------


def test_T16_a_definition_with_no_limits_is_refused() -> None:
    """§12. "No limit" and "a limit nobody wrote down" are the same thing at run time."""
    for missing in sorted(limits()):
        declared = limits()
        del declared[missing]
        with pytest.raises(InvalidDefinition) as raised:
            WorkflowDefinition.from_mapping(
                definition_body(limits=declared)
            )
        assert missing in str(raised.value), missing


def test_T16b_a_bound_that_no_run_could_reach_is_refused() -> None:
    with pytest.raises(InvalidDefinition):
        WorkflowDefinition.from_mapping(
            definition_body(limits=limits(max_artifact_bytes=1 << 41))
        )


def test_T22_an_approval_step_is_refused_by_name() -> None:
    """§18. AI-13-B's whole obligation toward the approval point, in one assertion."""
    with pytest.raises(InvalidDefinition) as raised:
        WorkflowDefinition.from_mapping(
            definition_body(steps=[a_step("approve-me", kind="APPROVAL")])
        )
    assert raised.value.reason_code == "APPROVAL_STEP_NOT_IMPLEMENTED"


def test_T22b_the_refusal_names_which_step_it_refused() -> None:
    """A caller must be able to say WHICH step stopped the definition.

    It names the POSITION and not the step id, and the difference is the repository's
    error convention rather than an accident: a message names the field, the rule and at
    most a shape fact, and "never an interpolated value" — an error message is a place a
    value escapes to a log. The rule a caller acts on is the reason code; the position
    says where to look.
    """
    with pytest.raises(InvalidDefinition) as raised:
        WorkflowDefinition.from_mapping(
            definition_body(
                steps=[
                    a_step("fine"),
                    a_step("needs-a-human", kind="APPROVAL"),
                ]
            )
        )
    assert raised.value.reason_code == "APPROVAL_STEP_NOT_IMPLEMENTED"
    assert "definition.steps[1]" in str(raised.value)
    assert "needs-a-human" not in str(raised.value)


def test_a_step_naming_no_known_seam_is_refused() -> None:
    """§6.1. A step that names nothing AI-13 may call is not a step."""
    with pytest.raises(InvalidDefinition):
        WorkflowDefinition.from_mapping(
            definition_body(steps=[a_step("s", kind="SOMETHING_ELSE")])
        )


def test_a_definition_with_no_steps_is_refused() -> None:
    """An empty sequence would satisfy every limit vacuously."""
    with pytest.raises(InvalidDefinition):
        WorkflowDefinition.from_mapping(definition_body(steps=[]))


def test_a_duplicate_step_id_is_refused() -> None:
    with pytest.raises(InvalidDefinition):
        WorkflowDefinition.from_mapping(
            definition_body(
                steps=[
                    a_step("same"),
                    a_step("same"),
                ]
            )
        )


def test_a_definition_with_no_digest_field_is_refused() -> None:
    """§5. A run binds to it and a resume is checked against it, so it is not optional."""
    body = definition_body()
    del body[DIGEST_FIELD]
    with pytest.raises(InvalidDefinition):
        WorkflowDefinition.from_mapping(body)


# ---------------------------------------------------------------------------
# T7, T8 — the digest a definition carries must match its own body
# ---------------------------------------------------------------------------


def test_T7_a_forged_definition_digest_is_refused() -> None:
    """§5. The digest is computed here, so a caller cannot choose it.

    The forgery is applied AFTER `definition_body` built the mapping: passing it as an
    override would let the helper recompute the digest and the test would assert
    nothing.
    """
    forged = definition_body()
    forged[DIGEST_FIELD] = "0" * 64

    with pytest.raises(InvalidDefinition) as raised:
        WorkflowDefinition.from_mapping(forged).verify_digest()
    assert raised.value.reason_code == "DEFINITION_DIGEST_MISMATCH"


def test_T8_a_changed_body_under_the_same_revision_is_caught_by_the_digest() -> None:
    """§5. Two definitions can share a revision and differ; only the digest catches it."""
    first = WorkflowDefinition.from_mapping(definition_body())
    second = WorkflowDefinition.from_mapping(
        definition_body(steps=[a_step("s1")])
    )

    assert first.revision == second.revision, "the revision string is deliberately the same"
    assert first.definition_digest != second.definition_digest


# ---------------------------------------------------------------------------
# T10, T18 — the checkpoint's digest, and what it may not carry
# ---------------------------------------------------------------------------


def _checkpoint_mapping(**overrides):  # noqa: ANN202
    body = {
        "workflow_id": "wf-demo",
        "revision": "v1",
        "definition_digest": "d" * 64,
        "run_id": "run-1",
        "step_id": "s1",
        "attempt_no": 1,
        "completed_steps": ["s1"],
        "artifact_refs": [],
        "created_at": T0,
    }
    body.update(overrides)
    body[CHECKPOINT_DIGEST_FIELD] = digest_of(
        {**body, CHECKPOINT_DIGEST_FIELD: ""}, digest_field=CHECKPOINT_DIGEST_FIELD
    )
    return body


def test_a_valid_checkpoint_verifies() -> None:
    checkpoint = Checkpoint.from_mapping(_checkpoint_mapping())
    assert checkpoint.verify_digest() is None
    assert checkpoint.completed_steps == ("s1",)


def test_T10_a_tampered_checkpoint_is_CHECKPOINT_CORRUPT() -> None:
    """§7.4, §8.1. The digest is computed over the canonical body, digest excluded."""
    tampered = _checkpoint_mapping(completed_steps=["s1", "s2"])
    tampered[CHECKPOINT_DIGEST_FIELD] = _checkpoint_mapping()[CHECKPOINT_DIGEST_FIELD]

    with pytest.raises(InvalidRecord) as raised:
        Checkpoint.from_mapping(tampered)
    assert raised.value.reason_code == "CHECKPOINT_CORRUPT"


def test_T18_a_checkpoint_carrying_a_guard_decision_is_refused() -> None:
    """§7.2. Authorization is not resume state, at any depth."""
    with pytest.raises(InvalidCheckpoint) as raised:
        Checkpoint.from_mapping(_checkpoint_mapping(guard_decision={"decision": "ALLOW"}))
    assert raised.value.reason_code == "CHECKPOINT_CARRIES_FORBIDDEN_STATE"


@pytest.mark.parametrize(
    "forbidden",
    [
        "authorization",
        "approval",
        "approval_status",
        "router_decision",
        "model_ref",
        "selected_model",
        "context",
        "context_payload",
        "tool_state",
        "tool_result",
        "tool_output",
        "capability",
        "capability_status",
        "raw_output",
        "prompt",
        "completion",
        "provider_response",
        "credential",
        "secret",
        "token",
        "key",
        "password",
        "diff",
        "file_content",
        "repository_content",
        "evidence_id",
        "content_digest",
        "record_digest",
        "producer",
    ],
)
def test_T18_every_forbidden_name_is_refused(forbidden: str) -> None:
    """The list §7.2 freezes, one name at a time, so a gap names itself."""
    with pytest.raises(InvalidCheckpoint):
        Checkpoint.from_mapping(_checkpoint_mapping(**{forbidden: "anything"}))


def test_T18b_a_forbidden_name_NESTED_inside_state_is_refused() -> None:
    """How a forbidden field actually arrives: inside something ordinary."""
    with pytest.raises(InvalidCheckpoint):
        Checkpoint.from_mapping(
            _checkpoint_mapping(completed_steps=["s1"], provenance={"guard_decision": "ALLOW"})
        )


def test_T18c_an_artifact_ref_carrying_content_is_refused() -> None:
    """§7.2. A reference and a digest — a third field is how the bytes would arrive."""
    with pytest.raises(InvalidCheckpoint):
        Checkpoint.from_mapping(
            _checkpoint_mapping(
                artifact_refs=[{"reference": "r", "digest": "d", "body": "the bytes"}]
            )
        )


def test_a_checkpoint_with_no_digest_is_refused() -> None:
    body = _checkpoint_mapping()
    del body[CHECKPOINT_DIGEST_FIELD]
    with pytest.raises(InvalidCheckpoint):
        Checkpoint.from_mapping(body)
