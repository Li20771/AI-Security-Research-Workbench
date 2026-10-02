"""AI-10 §10, §11 — the verification boundary.

A request authorizes nothing. An observation is a projection of an AI-06
execution and carries no tool output. The invocation itself belongs to the
controlled verification caller, because AI-06's public entry point requires
AI-04's evaluator and AI-10 must never hold one.
"""

from __future__ import annotations

import dataclasses

import pytest

from plugins.security_tools import ToolOutcome

from review.errors import InvalidVerification, ReviewError
from review.verification import VerificationObservation, VerificationRequest

from tests.review.conftest import target

pytestmark = pytest.mark.layer1


def request(**overrides) -> VerificationRequest:
    values = {
        "verification_id": "vr-1",
        "review_case_id": "rc-1",
        "subject": "m-left#c1",
        "targets": (target(),),
        "requested_at": "2026-10-02T00:00:00Z",
    }
    values.update(overrides)
    return VerificationRequest(**values)


def observation(**overrides) -> VerificationObservation:
    values = {
        "verification_id": "vr-1",
        "review_case_id": "rc-1",
        "subject": "m-left#c1",
        "outcome": ToolOutcome.COMPLETED,
        "tool_id": "tests",
        "operation": "run",
        "guard_decision_id": "gd-1",
        "observed_at": "2026-10-02T00:01:00Z",
    }
    values.update(overrides)
    return VerificationObservation(**values)


class TestRequestShape:
    def test_a_request_names_its_case_claim_and_targets(self):
        built = request()
        assert built.subject == "m-left#c1"
        assert built.targets[0].target_id == "t1"

    def test_a_request_must_name_at_least_one_target(self):
        with pytest.raises(InvalidVerification):
            request(targets=())

    def test_a_duplicate_target_is_refused(self):
        with pytest.raises(InvalidVerification):
            request(targets=(target("t1"), target("t1", description="other")))

    def test_the_subject_is_a_bounded_label(self):
        for bad in ("a free-form sentence", "m-left#", "#c1", ""):
            with pytest.raises(ReviewError):
                request(subject=bad)

    def test_a_bare_material_is_not_a_verification_subject(self):
        """§10.2 names ONE claim; a material alone cannot be verified."""
        with pytest.raises(InvalidVerification):
            request(subject="m-left")
        with pytest.raises(InvalidVerification):
            observation(subject="m-left")

    def test_the_request_carries_no_authorization(self):
        fields = {field.name for field in dataclasses.fields(VerificationRequest)}
        for forbidden in (
            "permission_level",
            "actor",
            "actor_id",
            "tool_id",
            "operation",
            "command",
            "arguments",
            "environment",
            "policy",
            "evaluator",
            "registry",
        ):
            assert forbidden not in fields

    @pytest.mark.parametrize(
        "forbidden",
        [
            "permission_level",
            "actor",
            "tool_id",
            "operation",
            "command",
            "arguments",
            "environment",
            "policy",
            "evaluator",
            "registry",
            "credential",
        ],
    )
    def test_a_request_carrying_authorization_is_refused_by_name(self, forbidden):
        raw = request().to_mapping()
        raw[forbidden] = "anything"
        with pytest.raises(InvalidVerification) as excinfo:
            VerificationRequest.from_mapping(raw)
        assert forbidden in str(excinfo.value)

    def test_a_request_round_trips(self):
        built = request()
        assert VerificationRequest.from_mapping(built.to_mapping()) == built


class TestObservationShape:
    def test_an_observation_names_what_ran_and_what_decided_it(self):
        built = observation()
        assert built.outcome is ToolOutcome.COMPLETED
        assert built.tool_id == "tests"
        assert built.evaluated is True

    def test_the_outcome_is_ai06s_vocabulary(self):
        with pytest.raises(InvalidVerification):
            observation(outcome="SUCCEEDED")

    def test_a_pre_guard_refusal_is_recorded_truthfully(self):
        """An empty decision id means no evaluation happened.

        It is not a missing value to fill in, and it is not an evaluation that
        returned something.
        """
        built = observation(guard_decision_id="")
        assert built.evaluated is False

    def test_an_observation_carries_no_tool_output(self):
        fields = {field.name for field in dataclasses.fields(VerificationObservation)}
        for forbidden in ("stdout", "stderr", "text", "output", "arguments", "environment"):
            assert forbidden not in fields

    @pytest.mark.parametrize(
        "forbidden", ["stdout", "stderr", "arguments", "environment", "tool_result", "raw"]
    )
    def test_an_observation_absorbing_output_is_refused_by_name(self, forbidden):
        raw = observation().to_mapping()
        raw[forbidden] = "anything"
        with pytest.raises(InvalidVerification) as excinfo:
            VerificationObservation.from_mapping(raw)
        assert forbidden in str(excinfo.value)

    def test_an_observation_round_trips(self):
        built = observation()
        assert VerificationObservation.from_mapping(built.to_mapping()) == built

    def test_duration_is_whole_and_non_negative(self):
        with pytest.raises(InvalidVerification):
            observation(duration_ms=-1)
        with pytest.raises(InvalidVerification):
            observation(duration_ms="fast")
        assert observation(duration_ms=None).duration_ms is None


class TestNoExecutionPath:
    def test_the_request_and_observation_are_passive_values(self):
        """Neither type has a method that could run anything."""
        for record in (VerificationRequest, VerificationObservation):
            methods = {
                name
                for name in vars(record)
                if callable(getattr(record, name)) and not name.startswith("__")
            }
            # Properties are fine; a verifier would be a function, not a value.
            assert methods <= {"from_mapping", "to_mapping", "evaluated"}, record

    def test_the_module_imports_no_execution_surface(self):
        import ast
        import pathlib

        tree = ast.parse(pathlib.Path("review/verification.py").read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert imported == {
            "__future__",
            "dataclasses",
            "typing",
            "plugins.security_tools",
            "review.claim",
            "review.errors",
            "review.validation",
            "review.vocabulary",
        }
