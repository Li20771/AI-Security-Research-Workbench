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
    """§4.2. Closed. Two members, and the difference is the whole point.

    ```text
    REFERENCE        a `BenchmarkRun` with `executor_kind = REFERENCE`.
    MODEL_EXECUTION  a record whose producer identifies the model / provider
                     execution, under a contract that defines how that measurement is
                     produced and attributed. NO SUCH CONTRACT EXISTS (§6), so no
                     supplied record can be one — see SUPPLIABLE_EVIDENCE_CLASSES.
    ```

    The member exists because a POLICY may REQUIRE it: a rule that selects a model
    declares that it needs that measurement, and the requirement is expressible today.
    What is not expressible is a supplied record claiming to BE one.
    """

    REFERENCE = "REFERENCE"
    MODEL_EXECUTION = "MODEL_EXECUTION"


#: The evidence classes a SUPPLIED record may carry. One of the two, and that is the
#: whole point.
#:
#: ```text
#: FROZEN: model-specific routing evidence requires an execution record whose producer
#:         identifies the model / provider execution, under a contract that defines
#:         how that measurement is produced and attributed.
#: ```
#:
#: No such contract exists (§6, and §6.1 says implementing this infrastructure does not
#: satisfy it). A supplied record therefore CANNOT be `MODEL_EXECUTION`, because the
#: only thing that could make it one is the contract that does not exist — and a caller
#: who types the word into a mapping has supplied a LABEL, not a measurement.
#:
#: This is the boundary §4.2 needs and cannot get from an enum alone. Without it, a
#: single caller-supplied field — `evidence_class: MODEL_EXECUTION` — manufactured the
#: §6 prerequisite, activated a model-comparative rule and emitted a model selection,
#: from a record whose own `limitations` said `NO_PROVIDER_CALL_IN_PATH`. The
#: prerequisite is BLOCKED, and a caller does not unblock it by declaring it unblocked.
#:
#: When a separate contract defines that producer and attribution, it amends this tuple
#: and states what a record must carry to qualify — not before.
SUPPLIABLE_EVIDENCE_CLASSES: tuple[EvidenceClass, ...] = (EvidenceClass.REFERENCE,)


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

    def __post_init__(self) -> None:
        """The invariants hold AT CONSTRUCTION, so an illegal record cannot exist.

        ```text
        FROZEN: model-specific routing evidence requires an execution record whose
                producer identifies the model / provider execution, under a contract
                that defines how that measurement is produced and attributed.
        ```

        `from_mapping` enforced that, and a caller could step around it by calling the
        constructor: three lines built an `EvidenceRef` labelled `MODEL_EXECUTION`,
        wrapped it in a `SuppliedRecord`, and handed it to `resolve_policy`, which
        selected a model. Guarding the parser and leaving the type open is a boundary
        with a door in it.

        The check therefore lives here, where it applies to every path — a supplied
        mapping, a direct construction, and anything a later revision adds — and
        `from_mapping` coerces and delegates rather than restating the rules. One
        definition, no path around it.
        """
        for name in ("run_id", "task_id", "source_sha", "workbench_sha"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidEvidence(f"EvidenceRef.{name} must be a non-empty string")

        if not isinstance(self.verdict, OracleVerdict):
            raise InvalidEvidence(
                "EvidenceRef.verdict must be one of AI-11's six verdicts, not a bare "
                "string: a rule compares verdicts by identity, so a string would "
                "silently satisfy nothing and the record would be evidence of nothing"
            )
        if not isinstance(self.reason_code, str):
            raise InvalidEvidence("EvidenceRef.reason_code must be a string")
        if self.verdict is not OracleVerdict.PASS and not self.reason_code.strip():
            raise InvalidEvidence(
                f"EvidenceRef.reason_code is empty under a {self.verdict} verdict; a "
                "non-PASS record names why, and a reader cannot act on a refusal it "
                "cannot read"
            )

        if not isinstance(self.limitations, tuple):
            raise InvalidEvidence("EvidenceRef.limitations must be a tuple")
        for entry in self.limitations:
            if not isinstance(entry, str) or not entry.strip():
                raise InvalidEvidence(
                    "EvidenceRef.limitations[] must be a non-empty string"
                )

        if not isinstance(self.evidence_class, EvidenceClass):
            raise InvalidEvidence(
                "EvidenceRef.evidence_class must be an EvidenceClass"
            )

        if self.evidence_class not in SUPPLIABLE_EVIDENCE_CLASSES:
            # §4.2, §6. A record is not model evidence because it says so — whether the
            # claim arrives in a mapping or in a constructor call.
            raise InvalidEvidence(
                f"EvidenceRef.evidence_class is {self.evidence_class}, which no supplied "
                "record may be: model-specific routing evidence requires an execution "
                "record whose producer identifies the model / provider execution under "
                "a contract that defines how that measurement is produced and "
                "attributed (§4.2), and no such contract exists (§6). A caller cannot "
                "satisfy the prerequisite by declaring it satisfied; the declaration is "
                "what the missing contract would define"
            )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "evidence") -> "EvidenceRef":
        """Coerce one mapping, then let the CONSTRUCTOR decide whether it is legal.

        This method deliberately restates none of the invariants. They live in
        `__post_init__`, so the parser and a direct construction are held to the same
        rules by construction rather than by two lists that can drift apart — and a
        rule enforced in only one of those places is a rule with a way around it.
        """
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

        try:
            evidence_class = EvidenceClass(data.get("evidence_class"))
        except ValueError:
            raise InvalidEvidence(
                f"{where}.evidence_class is not one of "
                f"{', '.join(m.value for m in EvidenceClass)}"
            ) from None

        return cls(
            run_id=data.get("run_id"),
            task_id=data.get("task_id"),
            source_sha=data.get("source_sha"),
            workbench_sha=data.get("workbench_sha"),
            verdict=verdict,
            reason_code=data.get("reason_code"),
            limitations=tuple(limitations_raw),
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

    def __post_init__(self) -> None:
        """The same boundary, for the record that holds the reference.

        A `SuppliedRecord` cannot carry a legal digest around an illegal reference:
        `EvidenceRef` refuses to exist, so there is nothing to wrap.
        """
        if not isinstance(self.ref, EvidenceRef):
            raise InvalidEvidence("SuppliedRecord.ref must be an EvidenceRef")
        if not isinstance(self.digest, str) or not self.digest.strip():
            raise InvalidEvidence(
                "SuppliedRecord.digest must be a non-empty string; the digest is what "
                "makes the exact supplied record checkable (§4.1)"
            )

    @classmethod
    def from_mapping(cls, raw: object, where: str = "record") -> "SuppliedRecord":
        data = _mapping(raw, where)
        _closed(data, _RECORD_KEYS, where)
        return cls(
            ref=EvidenceRef.from_mapping(data.get("evidence"), f"{where}.evidence"),
            digest=data.get("record_digest"),
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
