"""AI-12 §4.1, §5.3 — the AI-11 record AI-12 consumes, and how it is identified.

```text
FROZEN: AI-12 consumes explicitly supplied immutable AI-11 `BenchmarkRun` records.
FROZEN: every consumed `BenchmarkRun` is identified by its exact `run_id` and a
        recorded digest of the supplied record.
```

### Why the record is supplied rather than located

AI-11's run data is **disposable by design**: a `BenchmarkRun` is produced into a
scratch root, and the campaign report is command output. Neither is durable tracked
corpus, and §4.1 forbids assuming `benchmarks/results/` holds anything. A location is
therefore not an input; **a supplied artifact is**.

### Why `run_id` and not `task_id`

```text
task_id     says which task was measured   — many runs share one
source_sha  says which revision it pinned  — many runs share one
run_id      says which run it was           — exactly one
```

A policy that bound its evidence to `task_id` would treat a re-run as the same
evidence, which is precisely the substitution §5.3 forbids.

### What this module does not do

It does not read a file — reading a path is forbidden under `routing/`, and a policy
core that could reach the filesystem could reach a benchmark — it does not run
anything, and it does not re-derive a verdict. It takes mappings a caller supplies
and validates their shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from benchmarks.vocabulary import OracleVerdict

from routing.errors import InvalidEvidence

__all__ = [
    "EvidenceClass",
    "EvidenceRef",
    "SuppliedRecord",
    "supplied_records",
]

#: §4.2. What a record is evidence ABOUT.
#:
#: ```text
#: REFERENCE        a `BenchmarkRun` with `executor_kind = REFERENCE`. It is evidence
#:                  about the benchmark task, the oracle and the reference execution
#:                  path — and about nothing else.
#: MODEL_EXECUTION  a record whose producer identifies the model / provider execution,
#:                  under a contract that defines how that measurement is produced and
#:                  attributed. None exists yet (§6).
#: ```
class EvidenceClass(StrEnum):
    """§4.2. Closed. Two members, and the difference is the whole point."""

    REFERENCE = "REFERENCE"
    MODEL_EXECUTION = "MODEL_EXECUTION"


_EVIDENCE_KEYS = frozenset(
    {
        "run_id",
        "task_id",
        "source_sha",
        "workbench_sha",
        "verdict",
        "reason_code",
        "limitations",
        "evidence_class",
    }
)

_RECORD_KEYS = frozenset({"record_digest", "evidence"})


def _mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidEvidence(f"{where} must be an object")
    return value


def _closed(raw: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise InvalidEvidence(
            f"{where} has field(s) the contract does not define: "
            f"{', '.join(sorted(map(str, unknown)))}"
        )


def _non_empty_text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidEvidence(f"{where} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """§5.3. The identity of one measured run, as a decision must cite it.

    Every field is required. A partially identified record is not evidence: the
    contract's binding carries all of these, and a citation missing one of them
    cannot be re-derived by a reader.
    """

    run_id: str
    task_id: str
    source_sha: str
    workbench_sha: str
    verdict: OracleVerdict
    reason_code: str
    limitations: tuple[str, ...]
    evidence_class: EvidenceClass

    @classmethod
    def from_mapping(cls, raw: object, where: str = "evidence") -> "EvidenceRef":
        data = _mapping(raw, where)
        _closed(data, _EVIDENCE_KEYS, where)

        verdict_raw = data.get("verdict")
        try:
            verdict = OracleVerdict(verdict_raw)
        except ValueError:
            # AI-11's vocabulary is CLOSED and is not redefined here. A verdict
            # outside it is not a verdict this policy can read, and inventing a
            # member for it would be a second definition of one vocabulary.
            raise InvalidEvidence(
                f"{where}.verdict is not one of AI-11's six verdicts; AI-12 does not "
                "get its own verdict vocabulary"
            ) from None

        limitations_raw = data.get("limitations", [])
        if isinstance(limitations_raw, (str, bytes)) or not isinstance(
            limitations_raw, Sequence
        ):
            raise InvalidEvidence(f"{where}.limitations must be a list")
        limitations = tuple(
            _non_empty_text(entry, f"{where}.limitations[]") for entry in limitations_raw
        )

        try:
            evidence_class = EvidenceClass(data.get("evidence_class"))
        except ValueError:
            raise InvalidEvidence(
                f"{where}.evidence_class is not one of "
                f"{', '.join(m.value for m in EvidenceClass)}"
            ) from None

        # AI-11 records an EMPTY reason_code on a PASS — there is no refusal to name.
        # A non-PASS verdict without one is a different thing: a reader cannot act on
        # "this did not pass" and not know why, so that shape is refused.
        reason_code = data.get("reason_code")
        if not isinstance(reason_code, str):
            raise InvalidEvidence(f"{where}.reason_code must be a string")
        if verdict is not OracleVerdict.PASS and not reason_code.strip():
            raise InvalidEvidence(
                f"{where}.reason_code is empty under a {verdict} verdict; a non-PASS "
                "record names why, and a reader cannot act on a refusal it cannot read"
            )

        return cls(
            run_id=_non_empty_text(data.get("run_id"), f"{where}.run_id"),
            task_id=_non_empty_text(data.get("task_id"), f"{where}.task_id"),
            source_sha=_non_empty_text(data.get("source_sha"), f"{where}.source_sha"),
            workbench_sha=_non_empty_text(
                data.get("workbench_sha"), f"{where}.workbench_sha"
            ),
            verdict=verdict,
            reason_code=reason_code,
            limitations=limitations,
            evidence_class=evidence_class,
        )

    @property
    def is_pass(self) -> bool:
        """Whether this run's verdict is PASS. §4.3: only PASS is promotable."""
        return self.verdict is OracleVerdict.PASS

    def to_mapping(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "source_sha": self.source_sha,
            "workbench_sha": self.workbench_sha,
            "verdict": str(self.verdict),
            "reason_code": self.reason_code,
            "limitations": list(self.limitations),
            "evidence_class": str(self.evidence_class),
        }


@dataclass(frozen=True, slots=True)
class SuppliedRecord:
    """One supplied record: an identity, and a digest of the bytes supplied.

    The digest is what makes "the exact supplied record" checkable. Without it a
    reader can see WHICH run was cited but not WHICH artifact was read, and a
    decision re-derived from a different artifact would be indistinguishable.
    """

    ref: EvidenceRef
    digest: str

    @classmethod
    def from_mapping(cls, raw: object, where: str = "record") -> "SuppliedRecord":
        data = _mapping(raw, where)
        _closed(data, _RECORD_KEYS, where)
        return cls(
            ref=EvidenceRef.from_mapping(data.get("evidence"), f"{where}.evidence"),
            digest=_non_empty_text(data.get("record_digest"), f"{where}.record_digest"),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {"record_digest": self.digest, "evidence": self.ref.to_mapping()}


def supplied_records(raw: object) -> tuple[SuppliedRecord, ...]:
    """Validate a supplied record set and refuse two records claiming one run.

    §5.3 makes `run_id` the identity of a measured run. Two supplied records
    carrying the same `run_id` are therefore either the same record supplied twice
    or two different records claiming one identity; neither can be resolved by
    keeping the first or the last, so both are refused.
    """
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise InvalidEvidence("supplied records must be a list")

    records = tuple(
        SuppliedRecord.from_mapping(entry, f"records[{index}]")
        for index, entry in enumerate(raw)
    )

    seen = [record.ref.run_id for record in records]
    duplicates = sorted({run_id for run_id in seen if seen.count(run_id) > 1})
    if duplicates:
        raise InvalidEvidence(
            "run_id must be unique across the supplied records (§5.3); duplicate(s): "
            f"{', '.join(duplicates)}. A run is one measured run, and a second record "
            "claiming its identity is not resolved by keeping the first or the last"
        )
    return records
