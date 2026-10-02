"""AI-10 §6 — the material: declared provenance, generated digests, hard bounds.

Two properties are load-bearing and are tested as such:

```text
declared provenance is NOT verified provenance   the material records what the
                                                 submitter says, and nothing here
                                                 upgrades it
the digests are AI-10-generated                  a caller cannot supply one, and
                                                 cannot make one disagree with the
                                                 content it covers
```
"""

from __future__ import annotations

import dataclasses

import pytest

from agents.result import AgentResult
from agents.vocabulary import AgentId

from review.claim import ReviewClaim
from review.errors import InvalidIdentifier, InvalidMaterial
from review.material import ReviewMaterial
from review.vocabulary import (
    FORBIDDEN_MATERIAL_FIELDS,
    MAX_CLAIMS_PER_MATERIAL,
    MAX_INPUT_DIGEST_CHARS,
)

from tests.review.conftest import claim, sha256

pytestmark = pytest.mark.layer1


def build(**overrides) -> ReviewMaterial:
    values = {
        "material_id": "m1",
        "agent_id": AgentId.DSH,
        "execution_id": "ex-0000000000000001",
        "workspace_id": "ws-1",
        "input_digest": sha256("a"),
        "source_status": "COMPLETED",
        "claims": (claim(),),
    }
    values.update(overrides)
    return ReviewMaterial(**values)


def submission(**overrides) -> dict:
    """The mapping a caller SUBMITS: the audit projection minus generated fields.

    `to_mapping()` is the audit projection and carries the two digests;
    `from_mapping()` is the submission boundary and refuses them. They are two
    directions, not a round trip of one shape.
    """
    raw = build(**overrides).to_mapping()
    for generated in ("claims_digest", "material_digest"):
        raw.pop(generated)
    return raw


class TestMaterialShape:
    def test_a_declared_material_is_valid(self):
        built = build()
        assert built.agent_id is AgentId.DSH
        assert built.source_status is not None

    def test_material_id_is_bounded(self):
        with pytest.raises(InvalidIdentifier):
            build(material_id="has space")

    def test_execution_id_is_bounded(self):
        with pytest.raises(InvalidIdentifier):
            build(execution_id="x" * 129)

    def test_workspace_and_input_are_bounded(self):
        with pytest.raises(InvalidMaterial):
            build(workspace_id="")
        with pytest.raises(InvalidMaterial):
            build(input_digest="x" * (MAX_INPUT_DIGEST_CHARS + 1))

    def test_schema_version_is_closed(self):
        with pytest.raises(InvalidMaterial):
            build(schema_version=2)

    def test_there_is_no_field_for_raw_output(self):
        fields = {field.name for field in dataclasses.fields(ReviewMaterial)}
        for forbidden in ("transcript", "raw_output", "stdout", "stderr", "prompt", "messages"):
            assert forbidden not in fields


class TestProvenanceIsDeclared:
    def test_an_unregistered_agent_is_refused(self):
        with pytest.raises(InvalidMaterial):
            build(agent_id="not-registered")

    def test_source_status_is_declared_and_closed(self):
        with pytest.raises(InvalidMaterial):
            build(source_status="PROBABLY_FINE")
        assert build(source_status="BLOCKED").source_status.value == "BLOCKED"

    def test_source_status_is_not_a_statement_about_the_material(self):
        # The field records what the submitter declares about the execution it
        # is attributed to. It is never read as a quality signal here.
        built = build(source_status="FAILED")
        assert built.source_status.value == "FAILED"
        assert built.claims_digest.startswith("sha256:")

    def test_the_material_is_not_an_agent_result(self):
        assert not issubclass(ReviewMaterial, AgentResult)
        assert ReviewMaterial is not AgentResult

    def test_no_field_can_hold_an_agent_result(self):
        annotation = " ".join(
            str(field.type) for field in dataclasses.fields(ReviewMaterial)
        )
        assert "AgentResult" not in annotation


class TestClaims:
    def test_a_duplicate_claim_id_is_refused(self):
        with pytest.raises(InvalidMaterial):
            build(claims=(claim("c1"), claim("c1", statement="another statement")))

    def test_claims_are_bounded(self):
        with pytest.raises(InvalidMaterial):
            build(
                claims=tuple(
                    claim(f"c{index}") for index in range(MAX_CLAIMS_PER_MATERIAL + 1)
                )
            )

    def test_claims_must_be_claims(self):
        with pytest.raises(InvalidMaterial):
            build(claims=("a statement",))

    def test_claim_order_does_not_change_the_claim_set_digest(self):
        first = build(claims=(claim("c1"), claim("c2", statement="second")))
        second = build(claims=(claim("c2", statement="second"), claim("c1")))
        assert first.claims_digest == second.claims_digest


class TestGeneratedDigests:
    def test_both_digests_are_produced(self):
        built = build()
        for value in (built.claims_digest, built.material_digest):
            assert value.startswith("sha256:")
            assert len(value) == len("sha256:") + 64

    def test_a_caller_supplied_digest_is_refused(self):
        raw = build().to_mapping()
        for key in ("claims_digest", "material_digest"):
            with pytest.raises(InvalidMaterial):
                ReviewMaterial.from_mapping({**raw, key: sha256("f")})

    def test_the_digests_are_not_constructor_parameters(self):
        fields = {field.name: field for field in dataclasses.fields(ReviewMaterial)}
        assert fields["claims_digest"].init is False
        assert fields["material_digest"].init is False

    def test_material_id_moves_neither_digest(self):
        first = build(material_id="m1")
        second = build(material_id="m2")
        assert first.claims_digest == second.claims_digest
        assert first.material_digest == second.material_digest

    def test_claim_content_moves_the_claim_set_digest(self):
        assert build(claims=(claim(statement="one"),)).claims_digest != build(
            claims=(claim(statement="two"),)
        ).claims_digest

    def test_a_claim_id_does_not_move_the_claim_set_digest(self):
        assert build(claims=(claim("c1"),)).claims_digest == build(
            claims=(claim("c9"),)
        ).claims_digest

    def test_attribution_moves_the_material_digest(self):
        assert build(execution_id="ex-1").material_digest != build(
            execution_id="ex-2"
        ).material_digest

    def test_the_digest_is_deterministic(self):
        assert build().material_digest == build().material_digest


class TestForbiddenFields:
    @pytest.mark.parametrize("forbidden", sorted(FORBIDDEN_MATERIAL_FIELDS))
    def test_a_forbidden_field_is_refused_by_name(self, forbidden):
        raw = submission()
        raw[forbidden] = "anything"
        with pytest.raises(InvalidMaterial) as excinfo:
            ReviewMaterial.from_mapping(raw)
        assert forbidden in str(excinfo.value)

    def test_an_unknown_field_is_refused(self):
        raw = submission()
        raw["extra"] = 1
        with pytest.raises(InvalidMaterial):
            ReviewMaterial.from_mapping(raw)


class TestRoundTrip:
    def test_a_submission_round_trips_with_its_digests_recomputed(self):
        built = build()
        assert ReviewMaterial.from_mapping(submission()) == built

    def test_the_audit_projection_carries_the_digests(self):
        raw = build().to_mapping()
        assert raw["claims_digest"].startswith("sha256:")
        assert raw["material_digest"].startswith("sha256:")

    def test_from_mapping_accepts_nested_claim_mappings(self):
        raw = {
            "schema_version": 1,
            "material_id": "m1",
            "agent_id": "codex",
            "execution_id": "ex-1",
            "workspace_id": "ws-1",
            "input_digest": "sha256:" + "a" * 64,
            "source_status": "COMPLETED",
            "claims": [claim(claim_id="c1").to_mapping()],
        }
        built = ReviewMaterial.from_mapping(raw)
        assert isinstance(built.claims[0], ReviewClaim)
        assert built.agent_id is AgentId.CODEX
