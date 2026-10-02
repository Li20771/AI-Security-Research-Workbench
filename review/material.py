"""AI-10 §6 — the material: explicitly submitted review input.

```text
ReviewMaterial is an explicitly submitted review input: a declared analysis,
attributed by its submitter to one Agent execution, carrying a bounded set of
declared claims.
```

```text
IT IS      caller-supplied material, run-scoped
IT IS NOT  a field of AgentResult
IT IS NOT  an AI-05 EvidenceRecord
IT IS NOT  a model-output database, cache or archive
IT IS NOT  an input to any Agent execution
IT IS NOT  a verdict, a score or a ranking
```

### Declared provenance is not verified provenance

`agent_id`, `execution_id`, `workspace_id`, `input_digest` and `source_status`
are what the SUBMITTER declares. AI-10 records the declaration. The one check it
can make — agreement with a supplied `ExecutionRecord` — belongs to
`review.independence.require_aligned_declaration`, and even a fully agreeing
record proves nothing about the material's CONTENT: an execution's terminal
artifact is a reference or a digest, and there is nothing to compare a material
against.

### The two digests are AI-10-generated

`claims_digest` and `material_digest` are computed here and are not constructor
parameters. A caller cannot supply one, and a caller cannot make the object
carry a digest that disagrees with its own content — the same rule AI-05
§14.6.1 states for its generated fields.

`material_id` moves neither digest (§19.2 T8): it is a submitter-chosen audit
identifier, not content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.result import AgentExecutionOutcome
from agents.vocabulary import AgentId, resolve_agent

from review.claim import ReviewClaim
from review.digest import canonical_json, digest_of
from review.errors import InvalidMaterial
from review.validation import (
    closed_keys,
    identifier,
    mapping,
    refused_keys,
    sequence,
    single_line,
)
from review.vocabulary import (
    FORBIDDEN_MATERIAL_FIELDS,
    MAX_CLAIMS_PER_MATERIAL,
    MAX_EXECUTION_ID_CHARS,
    MAX_INPUT_DIGEST_CHARS,
    MAX_WORKSPACE_ID_CHARS,
)

__all__ = ["ReviewMaterial"]

_MATERIAL_KEYS = frozenset(
    {
        "schema_version",
        "material_id",
        "agent_id",
        "execution_id",
        "workspace_id",
        "input_digest",
        "source_status",
        "claims",
    }
)

_GENERATED_KEYS = frozenset({"claims_digest", "material_digest"})


def _claims_projection(claims: tuple[ReviewClaim, ...]) -> list[dict[str, Any]]:
    """The claim set as a deterministically ordered list of content projections.

    Ordered by the canonical text of each projection, so the digest does not
    depend on the caller's array order and two equal claim sets cannot produce
    two different digests.
    """
    return sorted(
        (claim.content_projection() for claim in claims),
        key=canonical_json,
    )


@dataclass(frozen=True, slots=True)
class ReviewMaterial:
    """§6.2. One submitted material."""

    material_id: str
    agent_id: AgentId
    execution_id: str
    workspace_id: str
    input_digest: str
    source_status: AgentExecutionOutcome
    claims: tuple[ReviewClaim, ...] = ()
    schema_version: int = 1

    #: Computed. Never a parameter — see the module docstring.
    claims_digest: str = field(init=False)
    material_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "material_id", identifier(self.material_id, "material.material_id")
        )

        try:
            resolved = resolve_agent(self.agent_id)
        except ValueError as exc:
            raise InvalidMaterial(
                f"material.agent_id is not a registered Agent identity: {exc}. "
                "A free string is never an identity (§6.2)"
            ) from exc
        object.__setattr__(self, "agent_id", resolved)

        object.__setattr__(
            self,
            "execution_id",
            identifier(
                self.execution_id,
                "material.execution_id",
                maximum=MAX_EXECUTION_ID_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "workspace_id",
            single_line(
                self.workspace_id,
                "material.workspace_id",
                maximum=MAX_WORKSPACE_ID_CHARS,
                error=InvalidMaterial,
            ),
        )
        object.__setattr__(
            self,
            "input_digest",
            single_line(
                self.input_digest,
                "material.input_digest",
                maximum=MAX_INPUT_DIGEST_CHARS,
                error=InvalidMaterial,
            ),
        )

        try:
            status = AgentExecutionOutcome(self.source_status)
        except ValueError as exc:
            raise InvalidMaterial(
                "material.source_status must be one of "
                f"{[member.value for member in AgentExecutionOutcome]}; got "
                f"{self.source_status!r}. It is DECLARED by the submitter (§6.2)"
            ) from exc
        object.__setattr__(self, "source_status", status)

        if self.schema_version != 1:
            raise InvalidMaterial(
                f"material.schema_version {self.schema_version!r} is not supported; "
                "this contract defines 1"
            )

        claims = tuple(self.claims)
        if len(claims) > MAX_CLAIMS_PER_MATERIAL:
            raise InvalidMaterial(
                f"material.claims must hold at most {MAX_CLAIMS_PER_MATERIAL} claims; "
                f"got {len(claims)}"
            )
        for claim in claims:
            if not isinstance(claim, ReviewClaim):
                raise InvalidMaterial(
                    "material.claims entries must be ReviewClaim; "
                    f"got {type(claim).__name__}"
                )
        claim_ids = [claim.claim_id for claim in claims]
        if len(set(claim_ids)) != len(claim_ids):
            raise InvalidMaterial(
                "material.claims is SET-semantic keyed by claim_id and a duplicate "
                "claim_id is refused"
            )

        claims_digest = digest_of(_claims_projection(claims))
        material_digest = digest_of(
            {
                "schema_version": self.schema_version,
                "agent_id": str(resolved),
                "execution_id": self.execution_id,
                "workspace_id": self.workspace_id,
                "input_digest": self.input_digest,
                "source_status": str(status),
                "claims_digest": claims_digest,
            }
        )
        object.__setattr__(self, "claims_digest", claims_digest)
        object.__setattr__(self, "material_digest", material_digest)

    # -- raw boundary ------------------------------------------------------

    @classmethod
    def from_mapping(cls, raw: object) -> "ReviewMaterial":
        data = mapping(raw, "material")
        refused_keys(
            data,
            _GENERATED_KEYS,
            "material",
            "claims_digest and material_digest are AI-10-generated and a "
            "caller-supplied digest is refused (§6.2).",
            error=InvalidMaterial,
        )
        refused_keys(
            data,
            FORBIDDEN_MATERIAL_FIELDS,
            "material",
            "A material carries declared claims and attribution; a score, a rank, "
            "a raw transcript or a raw output is not review material (§6.1).",
            error=InvalidMaterial,
        )
        closed_keys(data, _MATERIAL_KEYS, "material", error=InvalidMaterial)
        if data.get("schema_version") != 1:
            raise InvalidMaterial(
                f"material.schema_version {data.get('schema_version')!r} is not "
                "supported; this contract defines 1"
            )
        claims = tuple(
            ReviewClaim.from_mapping(entry)
            for entry in sequence(data.get("claims", []), "material.claims", error=InvalidMaterial)
        )
        return cls(
            material_id=data.get("material_id"),
            agent_id=data.get("agent_id"),
            execution_id=data.get("execution_id"),
            workspace_id=data.get("workspace_id"),
            input_digest=data.get("input_digest"),
            source_status=data.get("source_status"),
            claims=claims,
        )

    # -- projections -------------------------------------------------------

    def to_mapping(self) -> dict[str, Any]:
        """The material's own allowlist, in a deterministic order."""
        return {
            "schema_version": self.schema_version,
            "material_id": self.material_id,
            "agent_id": str(self.agent_id),
            "execution_id": self.execution_id,
            "workspace_id": self.workspace_id,
            "input_digest": self.input_digest,
            "source_status": str(self.source_status),
            "claims": [claim.to_mapping() for claim in self.claims],
            "claims_digest": self.claims_digest,
            "material_digest": self.material_digest,
        }
