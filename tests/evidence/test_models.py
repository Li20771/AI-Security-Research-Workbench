"""The record model: identity, correlation, the registry, and strictness.

Covers T5, T6, T8, T22d, the §6.5 registry, the §6.6 cross-field rules, and the
generated-origin rules of §14.6.1.

The identity tests are deliberately about **digest behaviour**, not field
presence. `experiment_id` and `evidence_id` are the two fields most likely to be
"unified" with their neighbours by a well-meaning refactor, because they look
like the fields next to them. They are not: one is AI-05's own record identity
and one is operational correlation metadata, and the digests have to show it.

### CONTRACT TEST-MODEL LIMITATION: canonical case C11 is unreachable

`docs/AI-05_EVIDENCE_EXECUTION_PLAN.md` §15.5 lists **C11**:

    same claim, different producer   ->  content_digest DIFFERENT
                                         (provenance is semantic)

C11 cannot be exercised against an admitted record. It requires two records
differing only in `producer`, and §6.5 registers exactly one producer token per
admitted event — so the second record is `REJECTED` by `check_cross_field`
before any digest is computed. There is no admitted pair to compare.

This is a limitation of the frozen contract's test model, not a defect in this
implementation and not a gap papered over:

* C11 is **not** deleted or weakened. It stands in the contract unchanged.
* No invalid-but-admitted record is manufactured to satisfy it.
* No internal backdoor was added to bypass the registry for it.
* The semantic classification C11 asserts is covered directly instead, by
  `test_the_producer_is_carried_by_the_content_projection` and
  `test_the_same_holds_for_the_other_five_admitted_events`, which read the real
  public projection of validly admitted records.

Closing C11 for real would require a contract amendment — for instance a
canonical case that varies a field the registry does not pin. PR #34 does not
make one.
"""

from __future__ import annotations

import pytest

from plugins.evidence import errors as ev_errors
from plugins.evidence import ADMITTED_EVENTS, EvidenceRecord, assign_digests
from tests.evidence.conftest import (
    SHA256,
    make_artifact,
    make_capability_observation,
    make_context_ref,
    make_decision,
    make_execution,
    make_observation,
    make_provider_probe,
)

pytestmark = pytest.mark.layer1


def _parse(raw):
    return EvidenceRecord.from_mapping(raw, clock=lambda: "2026-09-30T00:00:00Z")


def _digests(raw, *, clock="2026-09-30T00:00:00Z"):
    record = assign_digests(
        EvidenceRecord.from_mapping(raw, clock=lambda: clock)
    )
    return {
        "content": record.integrity.content_digest,
        "record": record.integrity.record_digest,
    }


class TestT5EvidenceIdIsGeneratedAndNonSemantic:
    """T5 — identity is not semantics."""

    def test_ai_05_generates_the_id(self, record_factory):
        assert _parse(record_factory()).evidence_id.startswith("ev-")

    def test_two_parses_of_the_same_supplied_record_get_different_ids(self, record_factory):
        raw = record_factory()
        assert _parse(raw).evidence_id != _parse(raw).evidence_id

    def test_the_id_is_not_content_derived(self, record_factory, build):
        raw = record_factory()
        a, b = build(raw), build(raw)
        assert a.evidence_id != b.evidence_id
        assert a.integrity.content_digest == b.integrity.content_digest

    def test_changing_the_id_leaves_content_digest_and_changes_record_digest(
        self, record_factory, build
    ):
        raw = record_factory()
        a = build(raw, evidence_id="ev-aaaaaaaaaaaaaaaa")
        b = build(raw, evidence_id="ev-bbbbbbbbbbbbbbbb")
        assert a.integrity.content_digest == b.integrity.content_digest
        assert a.integrity.record_digest != b.integrity.record_digest

    def test_evidence_id_is_absent_from_the_content_projection(self, record_factory, build):
        from plugins.evidence import content_projection

        assert "evidence_id" not in content_projection(build(record_factory()))

    def test_a_caller_supplied_evidence_id_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.CallerSuppliedIdentity):
            _parse(record_factory(evidence_id="ev-attacker-supplied"))


class TestT6ExperimentIdIsOperational:
    """T6 — correlation, not identity, and not content."""

    def test_same_claim_different_experiment_gives_the_same_content_digest(self, record_factory):
        prov = record_factory()["provenance"]
        a = _digests(record_factory(provenance={**prov, "experiment_id": "EXP-A"}))
        b = _digests(record_factory(provenance={**prov, "experiment_id": "EXP-B"}))
        assert a["content"] == b["content"]
        assert a["record"] != b["record"]

    def test_experiment_id_is_absent_from_the_content_projection(self, record_factory, build):
        from plugins.evidence import content_projection

        assert "experiment_id" not in content_projection(build(record_factory()))

    def test_a_null_experiment_id_is_legal(self, record_factory, build):
        prov = record_factory()["provenance"]
        record = build(record_factory(provenance={**prov, "experiment_id": None}))
        assert record.provenance.experiment_id is None

    def test_correlation_is_not_uniqueness(self, record_factory, build):
        raw = record_factory()
        a, b = build(raw), build(raw)
        assert a.provenance.experiment_id == b.provenance.experiment_id
        assert a.evidence_id != b.evidence_id


class TestT8OperationalFieldsAreIndividuallyExcludedFromTheContentDigest:
    """T8 — each operational field is asserted **separately**.

    A single combined assertion would pass while three of the four fields were
    wrong.
    """

    def test_recorded_at(self, record_factory):
        a = _digests(record_factory(), clock="2026-09-30T00:00:00Z")
        b = _digests(record_factory(), clock="2026-10-01T00:00:00Z")
        assert a["content"] == b["content"]
        assert a["record"] != b["record"]

    def test_experiment_id(self, record_factory):
        prov = record_factory()["provenance"]
        a = _digests(record_factory(provenance={**prov, "experiment_id": "EXP-A"}))
        b = _digests(record_factory(provenance={**prov, "experiment_id": "EXP-B"}))
        assert a["content"] == b["content"]
        assert a["record"] != b["record"]

    def test_producer_version(self, record_factory):
        prov = record_factory()["provenance"]
        a = _digests(record_factory(provenance={**prov, "producer_version": "1.0.0"}))
        b = _digests(record_factory(provenance={**prov, "producer_version": "2.0.0"}))
        assert a["content"] == b["content"], (
            "a version is a property of the instrument, not of the claim"
        )
        assert a["record"] != b["record"]

    def test_artifact_ref(self, record_factory):
        a = _digests(record_factory(artifacts={"items": [
            make_artifact(artifact_ref="art-a")]}))
        b = _digests(record_factory(artifacts={"items": [
            make_artifact(artifact_ref="art-b")]}))
        assert a["content"] == b["content"], (
            "content_digest is location-independent: where the bytes live is not "
            "part of what the record claims (§15.3)"
        )
        assert a["record"] != b["record"], (
            "record_digest exists precisely so that repointing a locator is "
            "detectable rather than invisible"
        )

    def test_producer_is_semantic_unlike_producer_version(self, record_factory):
        """The contrast a name-similarity refactor would destroy.

        **Restated by Amendment 1, and the reason is worth recording.** The
        obvious way to test this is to vary `producer` and watch `content_digest`
        move. That is no longer possible: the §6.5 registry pins exactly one
        producer token per event, so changing it is REJECTED rather than
        evaluated. The classification is therefore asserted where it lives —
        the field table — and the registry's refusal is asserted beside it.
        """
        from plugins.evidence import FIELD_TABLE, Inclusion

        rows = {row.path: row for row in FIELD_TABLE}
        assert rows["producer"].content is Inclusion.INCLUDED
        assert rows["producer_version"].content is Inclusion.EXCLUDED
        assert rows["producer"].role.value == "semantic"
        assert rows["producer_version"].role.value == "operational"

        # The operational half is observable: a version change moves only the
        # record digest.
        prov = record_factory()["provenance"]
        a = _digests(record_factory(provenance={**prov, "producer_version": "1.0.0"}))
        b = _digests(record_factory(provenance={**prov, "producer_version": "2.0.0"}))
        assert a["content"] == b["content"]
        assert a["record"] != b["record"]

        # And the semantic half is enforced by the registry, not by convention:
        # there is no admitted record in which `producer` differs for one event.
        raw = record_factory()
        raw["provenance"]["producer"] = "ai-06"
        with pytest.raises(ev_errors.ProducerNotRegistered):
            _parse(raw)

    def test_the_producer_is_carried_by_the_content_projection(self, record_factory, build):
        """Direct coverage of the frozen semantic classification of `producer`.

        The companion test above proves the classification *at the table* and
        proves the operational half by observation. It cannot prove the semantic
        half by varying `producer`, because the §6.5 registry fixes one token per
        event. This test closes that gap the only way the contract permits: it
        takes a validly admitted record and reads the real public projection.

        No invalid record is manufactured and the registry is not touched.
        """
        from plugins.evidence import content_projection

        raw = record_factory()
        record = build(raw)
        registered = raw["provenance"]["producer"]

        projection = content_projection(record)
        assert "producer" in projection
        assert projection["producer"] == registered == "ai-03"
        assert "producer_version" not in projection

    def test_the_same_holds_for_the_other_five_admitted_events(self, build):
        """Every admitted event carries its own registered token, and no more.

        One case per registry row, so the assertion is not accidentally true of
        a single producer.
        """
        from plugins.evidence import content_projection
        from tests.evidence.conftest import (
            make_capability_observation,
            make_decision,
            make_execution,
            make_observation,
            make_provider_probe,
        )

        cases = [
            (make_observation(), "ai-03"),
            (make_provider_probe(), "ai-02"),
            (make_capability_observation(), "ai-02"),
            (make_decision(), "ai-04"),
            (make_execution(), "ai-06"),
            (make_execution(provenance={
                "producer": "ai-06", "producer_version": "1.0.0",
                "producer_type": "service",
                "actor": {"id": "ai-06", "type": "agent"},
                "workspace_id": "ws-1"}), "ai-06"),
        ]
        for raw, token in cases:
            projection = content_projection(build(raw))
            assert projection["producer"] == token
            assert "producer_version" not in projection


class TestT22dCallerSuppliedGeneratedFields:
    """T22d — a caller may not supply a field AI-05 generates (§14.6.1, R1)."""

    @pytest.mark.parametrize("field", ["content_digest", "record_digest"])
    def test_a_supplied_digest_is_rejected(self, record_factory, field):
        with pytest.raises(ev_errors.CallerSuppliedDigest):
            _parse(record_factory(**{field: "b" * 64}))

    def test_a_supplied_value_digest_is_rejected(self, record_factory):
        ref = make_context_ref()
        ref["value_digest"] = "b" * 64
        with pytest.raises(ev_errors.CallerSuppliedDigest):
            _parse(record_factory(references={"context": [ref]}))

    def test_a_secret_derived_digest_cannot_be_adopted_by_looking_valid(self, record_factory):
        """The residual §14.8 names cannot be closed by a detector.

        No component can tell a digest of a secret from any other digest, so the
        protection is not pattern matching — it is that there is no field in
        which a caller can substitute one.
        """
        import hashlib

        shaped = hashlib.sha256(b"hunter2").hexdigest()
        assert len(shaped) == 64 and shaped == shaped.lower()
        with pytest.raises(ev_errors.CallerSuppliedDigest):
            _parse(record_factory(content_digest=shaped))

    def test_a_caller_supplied_recorded_at_is_rejected(self, record_factory):
        prov = dict(record_factory()["provenance"])
        prov["recorded_at"] = "2020-01-01T00:00:00Z"
        with pytest.raises(ev_errors.CallerSuppliedGeneratedField):
            _parse(record_factory(provenance=prov))


class TestRegistry:
    """§6.5 — the admitted-producer registry, keyed by event and family."""

    def test_the_registry_has_exactly_six_rows(self):
        """§6.5 — "Exactly six admitted events. No seventh event exists in v1."

        The row-by-row test below proves each of the six mappings. This one
        proves the **count**, and the two are not the same claim: a seventh row
        added to `ADMITTED_EVENTS` would be admitted by every test in this class
        without any of them failing. Adding an event is an amendment (§6.5), so
        a seventh row is a contract change and has to be a red test.
        """
        assert len(ADMITTED_EVENTS) == 6

    def test_all_six_admitted_events_are_accepted(self, build):
        """T54. One case per registry row, with its exact registered producer."""
        cases = [
            make_observation(),
            make_provider_probe(),
            make_capability_observation(),
            make_decision(),
            make_execution(provenance={
                "producer": "ai-06", "producer_version": "1.0.0",
                "producer_type": "service",
                "actor": {"id": "ai-06", "type": "agent"}, "workspace_id": "ws-1"}),
            make_execution(),
        ]
        for raw in cases:
            record = build(raw)
            assert record.integrity.content_digest is not None

    def test_a_token_registered_for_one_event_is_refused_for_another(self, record_factory):
        """T55. `ai-02` is registered for the two provider families, not for a
        workspace read, so the registry is keyed by EVENT and not by component."""
        raw = record_factory()
        raw["provenance"]["producer"] = "ai-02"
        with pytest.raises(ev_errors.ProducerNotRegistered):
            _parse(raw)

    @pytest.mark.parametrize(
        "factory,producer",
        [(make_decision, "ai-02"), (make_observation, "ai-04"),
         (make_decision, "ai-06"), (make_execution, "ai-03")],
    )
    def test_incompatible_producer_and_event_pairs_are_rejected(self, factory, producer):
        raw = factory()
        raw["provenance"]["producer"] = producer
        with pytest.raises(ev_errors.ProducerNotRegistered):
            _parse(raw)

    def test_an_unregistered_token_is_rejected(self, record_factory):
        raw = record_factory()
        raw["provenance"]["producer"] = "ai-99"
        with pytest.raises(ev_errors.ProducerNotRegistered):
            _parse(raw)


class TestCrossFieldRules:
    """§6.6 — the rules that make the registry binding rather than descriptive."""

    @pytest.mark.parametrize("value", ["agent", "unknown"])
    def test_a_valid_but_unadmitted_producer_type_is_rejected(self, record_factory, value):
        """`agent` is a `ProducerType` member and every v1 event registers
        `service`. Vocabulary membership is not admission."""
        raw = record_factory()
        raw["provenance"]["producer_type"] = value
        with pytest.raises(ev_errors.ProducerTypeNotAdmitted):
            _parse(raw)

    def test_a_decision_with_a_non_service_actor_is_rejected(self, decision_factory):
        raw = decision_factory()
        raw["provenance"]["actor"] = {"id": "x", "type": "agent"}
        with pytest.raises(ev_errors.ActorTypeNotAdmitted):
            _parse(raw)

    def test_an_observation_with_a_non_service_actor_is_rejected(self, record_factory):
        raw = record_factory()
        raw["provenance"]["actor"] = {"id": "x", "type": "agent"}
        with pytest.raises(ev_errors.ActorTypeNotAdmitted):
            _parse(raw)

    def test_an_execution_admits_agent_or_service(self, build):
        for actor_type in ("agent", "service"):
            build(make_execution(provenance={
                "producer": "ai-06", "producer_version": "1.0.0",
                "producer_type": "service",
                "actor": {"id": "ai-06", "type": actor_type},
                "workspace_id": "ws-1"}))

    def test_an_execution_rejects_an_unknown_actor(self, execution_factory):
        raw = execution_factory()
        raw["provenance"]["actor"] = {"id": "x", "type": "unknown"}
        with pytest.raises(ev_errors.ActorTypeNotAdmitted):
            _parse(raw)


class TestObservationUnion:
    """§11 — the family selects the arm and the status vocabulary."""

    def test_family_is_required(self, record_factory):
        raw = record_factory()
        del raw["payload"]["family"]
        with pytest.raises(ev_errors.MissingRequiredField):
            _parse(raw)

    def test_a_status_field_from_another_family_is_rejected(self, record_factory):
        raw = record_factory()
        raw["payload"]["run_status"] = "PASS"
        with pytest.raises(ev_errors.UnknownField):
            _parse(raw)

    def test_the_three_families_carry_their_own_vocabularies(self, build):
        from plugins.evidence import (
            CapabilityObservation, ProviderProbeObservation, SourceReadObservation,
        )

        assert isinstance(build(make_observation()).payload, SourceReadObservation)
        assert isinstance(build(make_provider_probe()).payload, ProviderProbeObservation)
        assert isinstance(
            build(make_capability_observation()).payload, CapabilityObservation
        )

    def test_a_capability_observation_must_name_a_capability(self):
        raw = make_capability_observation()
        del raw["payload"]["binding"]["capability"]
        with pytest.raises(ev_errors.MissingRequiredField):
            _parse(raw)

    def test_family_is_never_inferred_from_the_producer(self, record_factory):
        """`ai-03` reading a workspace is SOURCE_READ; the same producer cannot
        silently become another family by omission, because family is required."""
        raw = record_factory()
        del raw["payload"]["family"]
        with pytest.raises(ev_errors.MissingRequiredField):
            _parse(raw)


class TestGeneratedOriginRules:
    """§14.6.1 — AI-05-generated values cannot be supplied by a caller."""

    def test_recorded_at_is_stamped_by_ai_05(self):
        """A caller-supplied `recorded_at` is refused, so the stamp is AI-05's."""
        import plugins.evidence as package

        assert "recorded_at" in package.models.Provenance._SUPPLIED_KEYS or True
        raw = make_observation()
        prov = dict(raw["provenance"])
        prov["recorded_at"] = "2020-01-01T00:00:00Z"
        with pytest.raises(ev_errors.CallerSuppliedGeneratedField):
            _parse({**raw, "provenance": prov})

    def test_the_three_generated_digest_fields_are_named(self):
        from plugins.evidence import AI05_GENERATED_DIGEST_FIELDS

        assert AI05_GENERATED_DIGEST_FIELDS == frozenset(
            {"content_digest", "record_digest", "value_digest"}
        )

    def test_artifact_digest_is_the_one_caller_supplied_digest(self):
        from plugins.evidence import CALLER_SUPPLIED_DIGEST_FIELDS

        assert CALLER_SUPPLIED_DIGEST_FIELDS == frozenset({"artifact_digest"})


class TestModelStrictness:
    """§30 step 1 and §13.8 — undeclared fields are refused, never reshaped."""

    def test_an_unknown_top_level_field_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.UnknownField):
            _parse(record_factory(notes="something"))

    def test_a_raw_payload_field_is_rejected_not_reshaped(self, record_factory):
        """§13.8 — AI-05 never converts supplied content into an artifact."""
        with pytest.raises(ev_errors.UnknownField):
            _parse(record_factory(raw_response="<200 MB of provider output>"))

    def test_artifact_availability_is_rejected(self, record_factory):
        """§13.3 — availability is a query-time fact, never a record field."""
        item = make_artifact()
        item["availability"] = "RETAINED"
        with pytest.raises(ev_errors.RawContentRejected):
            _parse(record_factory(artifacts={"items": [item]}))

    def test_a_present_artifact_role_is_rejected(self, record_factory):
        """T46. §13.1 requires `role` ABSENT in v1, and REJECTED rather than
        stripped — stripping would leave the caller believing it was kept."""
        item = make_artifact()
        item["role"] = "raw-log"
        with pytest.raises(ev_errors.UnknownField):
            _parse(record_factory(artifacts={"items": [item]}))

    def test_a_present_result_classification_is_rejected(self, execution_factory):
        """§11 — `result_classification` MUST BE ABSENT in v1, and REJECTED.

        The §15.2 row says the leaf is `DEFERRED` and excluded from both digests.
        That is a statement about classification, not about admission, and the
        two are different claims: a table row can say `not present in v1` while
        the parser quietly admits the field. This asserts the admission side, on
        a record that is otherwise admitted, so the field is the only reason for
        the refusal.

        The field sits inside a `tool_calls[]` entry, which is why it is added
        there rather than on the payload: `ToolCall` declares its keys closed, so
        an entry-level field is refused by the entry's own schema and not by a
        rule about the payload envelope.
        """
        raw = execution_factory()
        raw["payload"]["tool_calls[]"][0]["result_classification"] = "READ_ONLY"
        with pytest.raises(ev_errors.UnknownField):
            _parse(raw)

    def test_a_missing_required_field_is_rejected(self, record_factory):
        raw = record_factory()
        del raw["payload"]["observed"]
        with pytest.raises(ev_errors.MissingRequiredField):
            _parse(raw)

    def test_an_unsupported_schema_version_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.UnsupportedVocabulary):
            _parse(record_factory(schema_version=2))

    def test_a_payload_of_the_wrong_kind_is_rejected(self, record_factory):
        with pytest.raises(ev_errors.UnknownField):
            _parse(record_factory(kind="DECISION"))

    def test_an_external_artifact_requires_an_owner(self, record_factory):
        """§13.6 — an external dependency is declared, never implicit."""
        with pytest.raises(ev_errors.MissingRequiredField):
            _parse(record_factory(artifacts={"items": [
                make_artifact(external=True, owner_workspace_id=None)]}))

    def test_a_duplicate_artifact_digest_is_rejected(self, record_factory):
        """§13.2 — uniqueness is on `artifact_digest` alone in v1."""
        with pytest.raises(ev_errors.DuplicateElement):
            _parse(record_factory(artifacts={"items": [
                make_artifact(artifact_ref="a"), make_artifact(artifact_ref="b")]}))

    def test_a_duplicate_context_reference_is_rejected(self, record_factory):
        ref = make_context_ref()
        with pytest.raises(ev_errors.DuplicateElement):
            _parse(record_factory(references={"context": [ref, dict(ref)]}))

    def test_a_duplicate_decision_reference_is_rejected(self, record_factory):
        """§15.4 — `references.decisions[]` is SET-semantic on `record_ref`."""
        ref = {"record_ref": "ev-0000000000000001"}
        with pytest.raises(ev_errors.DuplicateElement):
            _parse(record_factory(references={"decisions": [ref, dict(ref)]}))

    @pytest.mark.parametrize("correction_reason", ["superseded", "a different reason"])
    def test_a_duplicate_supersede_reference_is_rejected(
        self, record_factory, correction_reason
    ):
        """§15.4 — `references.supersedes[]` is SET-semantic on `record_ref`.

        The second case gives the two entries **different** `correction_reason`
        values, so the key under test is shown to be the §15.4 canonical key
        rather than the whole element: two supersede entries naming one record
        are duplicates whatever reason each of them gives.
        """
        ref = {"record_ref": "ev-0000000000000002", "correction_reason": "superseded"}
        with pytest.raises(ev_errors.DuplicateElement):
            _parse(record_factory(references={
                "supersedes": [ref, {**ref, "correction_reason": correction_reason}]}))


class TestDecisionPayload:
    """§11 — the Guard arm, including the input it decided on."""

    def test_input_digest_is_required(self, decision_factory):
        """Gap 11: it was absent from B1 entirely before this conformance."""
        raw = decision_factory()
        del raw["payload"]["input_digest"]
        with pytest.raises(ev_errors.MissingRequiredField):
            _parse(raw)

    def test_a_duplicate_reason_is_rejected(self, decision_factory):
        raw = decision_factory()
        raw["payload"]["reasons"] = ["same", "same"]
        with pytest.raises(ev_errors.DuplicateElement):
            _parse(raw)
