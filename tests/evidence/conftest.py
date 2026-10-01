"""Shared fixtures for the AI-05-B1 evidence tests.

Builders rather than constants, following `tests/guard/conftest.py`: most tests
vary one field and hold the rest fixed, and a test that restates a whole record
to change one value hides which value it is actually about.

Three facts about this suite:

* It is **offline, pure and filesystem-free**. B1 has no storage, so nothing
  here writes a file or opens a socket.
* The clock is **pinned**. `recorded_at` is operational and excluded from
  `content_digest`, but it *is* in `record_digest`, so a test that compares two
  record digests must hold it fixed or it is comparing the clock.
* The vocabulary here follows the **amended** contract: every OBSERVATION names
  its `family`, `role` is absent, `reasons` is a set, and a source revision's
  width is decided by its sibling `source_kind`.

No test requires a credential, a network, a provider, or a repository.
"""

from __future__ import annotations

from typing import Any

import pytest

#: A fixed instant. Used everywhere a record digest is compared.
FIXED_CLOCK = "2026-09-30T00:00:00Z"

WS = "ws-1"
WS_OTHER = "ws-2"

#: A real 40-character git commit SHA shape. Never a SHA from any repository.
GIT_SHA = "a" * 39 + "1"

#: A real 64-character SHA-256 shape.
SHA256 = "b" * 64

OTHER_SHA256 = "c" * 64


def make_observation(**overrides: Any) -> dict[str, Any]:
    """A well-formed SOURCE_READ OBSERVATION in its **supplied** form.

    Carries no `evidence_id`, no `recorded_at`, no `content_digest`, no
    `record_digest` and no `value_digest` — those are AI-05's to produce, and a
    test that supplies one is testing rejection, not admission.
    """
    record: dict[str, Any] = {
        "schema_version": 1,
        "kind": "OBSERVATION",
        "provenance": {
            "producer": "ai-03",
            "producer_version": "1.0.0",
            "producer_type": "service",
            "actor": {"id": "ai-03", "type": "service"},
            "workspace_id": WS,
            "experiment_id": "EXP-20260930-0001",
            "observed_at": "2026-09-30T00:00:00Z",
        },
        "payload": {
            "family": "SOURCE_READ",
            "subject": "git.head",
            "observed": "read the live state",
            "read_status": "READ",
            "binding": {
                "source_kind": "git_current_state",
                "source_identity": "git",
                "source_revision": GIT_SHA,
            },
        },
    }
    for key, value in overrides.items():
        if value is None:
            record.pop(key, None)
        else:
            record[key] = value
    return record


def make_provider_probe(**overrides: Any) -> dict[str, Any]:
    """A well-formed PROVIDER_PROBE OBSERVATION."""
    return make_observation(
        provenance={
            "producer": "ai-02",
            "producer_version": "1.0.0",
            "producer_type": "service",
            "actor": {"id": "ai-02", "type": "service"},
            "workspace_id": WS,
        },
        payload={
            "family": "PROVIDER_PROBE",
            "subject": "probe.text_baseline",
            "observed": "the endpoint answered",
            "run_status": "PASS",
            "binding": {
                "model_ref": "deepseek/deepseek-flash",
                "endpoint_host": "api.deepseek.com",
            },
        },
        **overrides,
    )


def make_capability_observation(**overrides: Any) -> dict[str, Any]:
    """A well-formed CAPABILITY_OBSERVATION, which requires a capability."""
    return make_observation(
        provenance={
            "producer": "ai-02",
            "producer_version": "1.0.0",
            "producer_type": "service",
            "actor": {"id": "ai-02", "type": "service"},
            "workspace_id": WS,
        },
        payload={
            "family": "CAPABILITY_OBSERVATION",
            "subject": "capability.tool_calling",
            "observed": "returned a tool call",
            "outcome": "PASS",
            "candidate_status": "DECLARED",
            "binding": {
                "model_ref": "deepseek/deepseek-flash",
                "endpoint_host": "api.deepseek.com",
                "capability": "tool_calling",
            },
        },
        **overrides,
    )


def make_decision(**overrides: Any) -> dict[str, Any]:
    """A well-formed AI-04 Guard DECISION, the only arm v1 admits."""
    return {
        "schema_version": 1,
        "kind": "DECISION",
        "provenance": {
            "producer": "ai-04",
            "producer_version": "1.0.0",
            "producer_type": "service",
            "actor": {"id": "ai-04", "type": "service"},
            "workspace_id": WS,
        },
        "payload": {
            "decision": "ALLOW",
            "reason_code": "ALLOWED_BY_RULE",
            "input_digest": SHA256,
            "reasons": ["matched the allow rule"],
        },
        **(overrides or {}),
    }


def make_execution(**overrides: Any) -> dict[str, Any]:
    """A well-formed AI-06 EXECUTION."""
    return {
        "schema_version": 1,
        "kind": "EXECUTION",
        "provenance": {
            "producer": "ai-06",
            "producer_version": "1.0.0",
            "producer_type": "service",
            "actor": {"id": "ai-06", "type": "service"},
            "workspace_id": WS,
        },
        "payload": {
            "tool_calls[]": [
                {"ordinal": 0, "what_ran": "git status", "status": "PASS"},
            ]
        },
        **(overrides or {}),
    }


def make_context_ref(
    *,
    subject: str = "git.head",
    value: str = "PASS",
    workspace_id: str = WS,
    source_kind: str = "git_current_state",
    source_revision: str = GIT_SHA,
    item_kind: str = "FACT",
    truth_state: str = "PASS",
    freshness: str = "CURRENT",
) -> dict[str, Any]:
    """One supplied context reference: identity, state, and a transient `value`.

    `source_revision` defaults to a 40-character revision because the default
    `source_kind` is a git kind; a test that changes the kind must change the
    width with it, which is the rule under test.
    """
    return {
        "workspace_id": workspace_id,
        "source_kind": source_kind,
        "source_identity": "git",
        "source_revision": source_revision,
        "subject": subject,
        "value": value,
        "item_kind": item_kind,
        "truth_state": truth_state,
        "freshness": freshness,
    }


def make_artifact(
    *,
    artifact_digest: str = SHA256,
    external: bool = False,
    owner_workspace_id: str | None = None,
    artifact_ref: str | None = "art-0001",
) -> dict[str, Any]:
    """An artifact entry. Carries no `role`, which §13.1 forbids in v1."""
    return {
        "artifact_digest": artifact_digest,
        "external": external,
        "owner_workspace_id": owner_workspace_id,
        "artifact_ref": artifact_ref,
    }


@pytest.fixture
def clock() -> str:
    """The pinned instant used for `recorded_at`."""
    return FIXED_CLOCK


@pytest.fixture
def record_factory():
    return make_observation


@pytest.fixture
def decision_factory():
    return make_decision


@pytest.fixture
def execution_factory():
    return make_execution


@pytest.fixture
def context_ref_factory():
    return make_context_ref


@pytest.fixture
def artifact_factory():
    return make_artifact


@pytest.fixture
def build():
    """Parse a supplied record and assign its digests, clock pinned."""
    from plugins.evidence import EvidenceRecord, assign_digests

    def _build(raw: dict[str, Any], *, evidence_id: str | None = None):
        parsed = EvidenceRecord.from_mapping(
            raw, evidence_id=evidence_id, clock=lambda: FIXED_CLOCK
        )
        return assign_digests(parsed)

    return _build
