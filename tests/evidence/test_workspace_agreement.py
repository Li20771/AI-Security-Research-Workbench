"""Workspace agreement — §18.1, covered by T12 and T13.

§30 step 5 requires `workspace_id` to be present, non-empty **and to agree
everywhere**. B1 holds the first two; this module covers the third, which is the
one that was genuinely absent.

### Why T13 is not `assert outcome == REJECTED`

§18.3 records the reason in the contract's own words: AI-04's contract said
*"never merged, filtered, or repaired"* for its entire frozen life, and the
implementation filtered anyway. Foreign context was dropped and evaluation
continued, so an unconditional `ALLOW` rule succeeded on a request spanning two
workspaces.

A test that only asserts `REJECTED` cannot tell a rejecting implementation from
a filtering one, because a filtering implementation produces `ACCEPTED` — and
`ACCEPTED` is exactly what a careless reading of "drop the foreign item" looks
like. So T13 is proven three ways at once:

1. **The input is unchanged.** The supplied mapping is deep-copied before the
   call and compared after. A filter would have removed an element; a repair
   would have rewritten one.
2. **The foreign item is still there and still foreign.** Read back out of the
   caller's own object, not out of anything the implementation returned.
3. **The surviving subset alone is `ACCEPTED`.** This is the control that gives
   the rejection its meaning: the remaining items are admissible, so an
   implementation that dropped the foreign element and carried on would have
   returned `ACCEPTED`. It returned `REJECTED`, and `record is None`.

Point 3 is what makes this direct evidence rather than a restatement. Without
it, `REJECTED` is also consistent with a record that was rejected for some
unrelated reason.

### Scope

T12 and T13 only, plus the §18.2 outcome rows they imply. No Store, no
uniqueness, no lifecycle — `admit()` here covers §30 steps 1-13 and not step 14.
"""

from __future__ import annotations

import copy

import pytest

from plugins.evidence import (
    AdmissionOutcome,
    admit,
    check_workspace_agreement,
    EvidenceRecord,
)
from plugins.evidence.errors import (
    MissingRequiredField,
    WorkspaceAgreementViolation,
)
from tests.evidence.conftest import (
    FIXED_CLOCK,
    SHA256,
    WS,
    WS_OTHER,
    make_artifact,
    make_context_ref,
    make_decision,
    make_execution,
    make_observation,
)

pytestmark = pytest.mark.layer1

REASON = "WORKSPACE_AGREEMENT_VIOLATION"


def _admit(raw):
    """Admit with the clock pinned, so a digest comparison is not a clock read."""
    return admit(raw, clock=lambda: FIXED_CLOCK)


def _parse(raw) -> EvidenceRecord:
    return EvidenceRecord.from_mapping(raw, clock=lambda: FIXED_CLOCK)


def _scopes(raw) -> list[str]:
    return [ref["workspace_id"] for ref in raw["references"]["context"]]


# --------------------------------------------------------------------------
# T12 — one workspace throughout
# --------------------------------------------------------------------------


class TestT12SingleWorkspaceIsAccepted:
    """T12 — every workspace-scoped field names the same workspace."""

    def test_an_observation_whose_context_agrees_is_accepted(self):
        result = _admit(make_observation(references={
            "context": [make_context_ref(subject="git.head", workspace_id=WS)]}))

        assert result.outcome is AdmissionOutcome.ACCEPTED
        assert result.record is not None
        assert result.reason_code is None

    def test_an_admitted_record_carries_both_digests(self):
        """Admission is not a bare boolean: §30 step 12 runs before ACCEPTED."""
        result = _admit(make_observation(references={
            "context": [make_context_ref(workspace_id=WS)]}))

        assert len(result.record.integrity.content_digest) == 64
        assert len(result.record.integrity.record_digest) == 64

    def test_all_kinds_accept_an_agreeing_context(self):
        """The rule is about the record, not about one kind's payload."""
        ref = {"context": [make_context_ref(workspace_id=WS)]}

        for raw in (
            make_observation(references=ref),
            make_decision(references=ref),
            make_execution(references=ref),
        ):
            assert _admit(raw).outcome is AdmissionOutcome.ACCEPTED, raw["kind"]

    def test_an_internal_artifact_naming_the_record_workspace_is_accepted(self):
        result = _admit(make_observation(artifacts={"items": [
            make_artifact(external=False, owner_workspace_id=WS)]}))

        assert result.outcome is AdmissionOutcome.ACCEPTED

    def test_an_internal_artifact_with_no_owner_is_accepted(self):
        """Nothing to disagree with: §18.1 compares values that exist."""
        result = _admit(make_observation(artifacts={"items": [
            make_artifact(external=False, owner_workspace_id=None)]}))

        assert result.outcome is AdmissionOutcome.ACCEPTED

    def test_an_external_artifact_with_its_owner_is_accepted(self):
        """§18.2's ACCEPT row, and §18.4: a declared external dependency."""
        raw = make_observation(artifacts={"items": [
            make_artifact(external=True, owner_workspace_id=WS_OTHER)]})

        assert _admit(raw).outcome is AdmissionOutcome.ACCEPTED


# --------------------------------------------------------------------------
# T13 — a genuine two-workspace record
# --------------------------------------------------------------------------


class TestT13ForeignWorkspaceIsRejected:
    """T13 — a constructible two-workspace input is REJECTED, not filtered."""

    @staticmethod
    def _two_workspace_input(foreign_at: int = 1) -> dict:
        """A record whose context spans two workspaces. Built, not described."""
        subjects = ["git.head", "git.branch"]
        scopes = [WS, WS]
        scopes[foreign_at] = WS_OTHER
        return make_observation(references={"context": [
            make_context_ref(subject=s, workspace_id=w)
            for s, w in zip(subjects, scopes)
        ]})

    def test_a_genuine_two_workspace_record_is_rejected(self):
        result = _admit(self._two_workspace_input())

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == REASON
        assert result.record is None

    @pytest.mark.parametrize("foreign_at", [0, 1])
    def test_the_position_of_the_foreign_item_does_not_matter(self, foreign_at):
        """Not a check of the first or the last element, but of every element."""
        result = _admit(self._two_workspace_input(foreign_at=foreign_at))

        assert result.outcome is AdmissionOutcome.REJECTED

    def test_a_context_ref_that_alone_is_foreign_is_rejected(self):
        result = _admit(make_observation(references={
            "context": [make_context_ref(workspace_id=WS_OTHER)]}))

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == REASON

    # ---- the three anti-filtering proofs --------------------------------

    def test_the_foreign_item_is_never_dropped_from_the_input(self):
        """A filter removes the element. The caller's object is untouched."""
        raw = self._two_workspace_input()
        before = copy.deepcopy(raw)

        result = _admit(raw)

        assert result.outcome is AdmissionOutcome.REJECTED
        assert raw == before, "the supplied mapping was modified"
        assert _scopes(raw) == [WS, WS_OTHER], "an element was removed or reordered"

    def test_the_foreign_item_is_never_repaired_to_the_record_scope(self):
        """Repair would rewrite the value. The foreign value is still foreign."""
        raw = self._two_workspace_input()

        _admit(raw)

        assert WS_OTHER in _scopes(raw), "the foreign value was rewritten to the scope"

    def test_admission_does_not_continue_with_the_remaining_items(self):
        """The control that separates REJECT from FILTER-AND-CONTINUE.

        The surviving subset is admitted on its own, so a filter-and-continue
        implementation would have returned ACCEPTED for the two-workspace input.
        It returned REJECTED and produced no record.
        """
        surviving_subset = make_observation(references={
            "context": [make_context_ref(subject="git.head", workspace_id=WS)]})

        assert _admit(surviving_subset).outcome is AdmissionOutcome.ACCEPTED

        result = _admit(self._two_workspace_input())
        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.record is None, "admission continued with the remaining items"

    def test_a_second_context_ref_in_a_foreign_workspace_is_rejected(self):
        """The same boundary one field over: two refs, one foreign workspace."""
        raw = make_observation(references={"context": [
            make_context_ref(subject="git.head", workspace_id=WS),
            make_context_ref(subject="git.branch", workspace_id=WS),
            make_context_ref(subject="git.remote", workspace_id=WS_OTHER),
        ]})
        before = copy.deepcopy(raw)

        result = _admit(raw)

        assert result.outcome is AdmissionOutcome.REJECTED
        assert raw == before
        assert len(_scopes(raw)) == 3


# --------------------------------------------------------------------------
# Artifacts — the second §18.1 comparison
# --------------------------------------------------------------------------


class TestArtifactWorkspaceAgreement:
    """§18.1's artifact row and §13.6's owner requirement, as outcomes."""

    def test_an_internal_artifact_naming_a_foreign_workspace_is_rejected(self):
        """The §18.1 exemption covers external artifacts only."""
        raw = make_observation(artifacts={"items": [
            make_artifact(external=False, owner_workspace_id=WS_OTHER)]})

        result = _admit(raw)

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == REASON

    def test_an_external_artifact_without_an_owner_is_rejected(self):
        """§13.6, refused by B1 and reported here as an outcome."""
        raw = make_observation(artifacts={"items": [
            make_artifact(external=True, owner_workspace_id=None)]})

        result = _admit(raw)

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "MISSING_REQUIRED_FIELD"

    def test_a_foreign_artifact_is_not_dropped_from_the_input(self):
        raw = make_observation(artifacts={"items": [
            make_artifact(external=False, owner_workspace_id=WS_OTHER)]})
        before = copy.deepcopy(raw)

        _admit(raw)

        assert raw == before
        assert raw["artifacts"]["items"][0]["owner_workspace_id"] == WS_OTHER


# --------------------------------------------------------------------------
# Missing workspace — §18.2's REJECT rows, as outcomes
# --------------------------------------------------------------------------


class TestMissingWorkspaceIsRejected:
    """§18.2: "missing workspace REJECT". Both are B1's refusals, mapped."""

    def test_a_record_with_no_workspace_is_rejected(self):
        provenance = {
            k: v for k, v in make_observation()["provenance"].items()
            if k != "workspace_id"
        }

        result = _admit(make_observation(provenance=provenance))

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "MISSING_REQUIRED_FIELD"

    def test_a_context_ref_with_no_workspace_is_rejected(self):
        ref = make_context_ref()
        del ref["workspace_id"]

        result = _admit(make_observation(references={"context": [ref]}))

        assert result.outcome is AdmissionOutcome.REJECTED
        assert result.reason_code == "MISSING_REQUIRED_FIELD"


# --------------------------------------------------------------------------
# The rule function, directly
# --------------------------------------------------------------------------


class TestTheRuleItself:
    """Assertions about `check_workspace_agreement` that an outcome cannot make."""

    def test_it_raises_the_workspace_error_and_not_a_generic_one(self):
        record = _parse(make_observation(references={"context": [
            make_context_ref(workspace_id=WS),
            make_context_ref(subject="git.branch", workspace_id=WS_OTHER),
        ]}))

        with pytest.raises(WorkspaceAgreementViolation) as excinfo:
            check_workspace_agreement(record)

        assert excinfo.value.reason_code == REASON

    def test_it_returns_none_for_an_agreeing_record(self):
        record = _parse(make_observation(references={
            "context": [make_context_ref(workspace_id=WS)]}))

        assert check_workspace_agreement(record) is None

    def test_the_reason_does_not_echo_either_workspace_value(self):
        """An error message is a place a value escapes to a log (`errors.py`)."""
        record = _parse(make_observation(references={"context": [
            make_context_ref(workspace_id=WS_OTHER)]}))

        with pytest.raises(WorkspaceAgreementViolation) as excinfo:
            check_workspace_agreement(record)

        message = str(excinfo.value)
        assert WS_OTHER not in message
        assert WS not in message
        assert "workspace_id" in message

    def test_the_error_is_not_a_cross_field_violation(self):
        """§6.6 is a frozen enumerable list; §18 is a separate frozen section.

        An `except CrossFieldViolation` handler must not claim to hold the
        workspace rule, and this is what keeps the families separate.
        """
        from plugins.evidence.errors import CrossFieldViolation, EvidenceError

        assert issubclass(WorkspaceAgreementViolation, EvidenceError)
        assert not issubclass(WorkspaceAgreementViolation, CrossFieldViolation)
