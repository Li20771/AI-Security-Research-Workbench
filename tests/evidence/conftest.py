"""Shared fixtures for the AI-05-B1 evidence tests.

Builders rather than constants, following `tests/guard/conftest.py`: most tests
vary one field and hold the rest fixed, and a test that restates a whole record
to change one value hides which value it is actually about.

Two facts about this suite:

* It is **offline, pure and filesystem-free**. B1 has no storage, so nothing
  here writes a file or opens a socket.
* The clock is **pinned**. `recorded_at` is operational and excluded from
  `content_digest`, but it *is* in `record_digest`, so a test that compares two
  record digests must hold it fixed or it is comparing the clock.

No test requires a credential, a network, a provider, or a repository.
"""

from __future__ import annotations

from typing import Any

import pytest

#: A fixed instant. Used everywhere a record digest is compared.
FIXED_CLOCK = "2026-09-29T00:00:00Z"

WS = "ws-1"
WS_OTHER = "ws-2"

#: A real 40-character git commit SHA shape. Never a SHA from any repository.
GIT_SHA = "a" * 39 + "1"

#: A real 64-character SHA-256 shape.
SHA256 = "b" * 64

OTHER_SHA256 = "c" * 64


def make_record(**overrides: Any) -> dict[str, Any]:
    """A well-formed, benign OBSERVATION in its **supplied** form.

    Carries no `evidence_id`, no `recorded_at`, no `content_digest`, no
    `record_digest` and no `value_digest` — those are AI-05's to produce, and a
    test that supplies one is testing rejection, not admission.
    """
    record: dict[str, Any] = {
        "schema_version": 1,
        "kind": "OBSERVATION",
        "provenance": {
            "producer": "ai-02",
            "producer_version": "1.0.0",
            "producer_type": "service",
            "actor": {"id": "provider:deepseek", "type": "service"},
            "workspace_id": WS,
            "experiment_id": "EXP-20260929-0001",
            "observed_at": "2026-09-29T00:00:00Z",
        },
        "payload": {
            "subject": "capability.tool_calling",
            "observed": "returned a tool call",
            "outcome": "PASS",
        },
    }
    for key, value in overrides.items():
        if value is None:
            record.pop(key, None)
        else:
            record[key] = value
    return record


def make_context_ref(
    *,
    subject: str = "git.head",
    value: str = "PASS",
    workspace_id: str = WS,
    source_revision: str = GIT_SHA,
    item_kind: str = "FACT",
    truth_state: str = "PASS",
    freshness: str = "CURRENT",
) -> dict[str, Any]:
    """One supplied context reference: identity, state, and a transient `value`."""
    return {
        "workspace_id": workspace_id,
        "source_kind": "git_current_state",
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
    role: str | None = "raw-log",
    external: bool = False,
    owner_workspace_id: str | None = None,
    artifact_ref: str | None = "art-0001",
) -> dict[str, Any]:
    return {
        "artifact_digest": artifact_digest,
        "role": role,
        "external": external,
        "owner_workspace_id": owner_workspace_id,
        "artifact_ref": artifact_ref,
    }


def with_references(**sections: Any) -> dict[str, Any]:
    """A record carrying a `references` block."""
    return make_record(references=sections)


@pytest.fixture
def clock() -> str:
    """The pinned instant used for `recorded_at`."""
    return FIXED_CLOCK


@pytest.fixture
def record_factory():
    return make_record


@pytest.fixture
def context_ref_factory():
    return make_context_ref


@pytest.fixture
def artifact_factory():
    return make_artifact


@pytest.fixture
def build():
    """Parse a supplied record and assign its digests, clock pinned.

    Mirrors what B2's admission will do, minus the rules B1 does not own.
    """
    from plugins.evidence import EvidenceRecord, assign_digests

    def _build(raw: dict[str, Any], *, evidence_id: str | None = None):
        parsed = EvidenceRecord.from_mapping(
            raw, evidence_id=evidence_id, clock=lambda: FIXED_CLOCK
        )
        return assign_digests(parsed)

    return _build
