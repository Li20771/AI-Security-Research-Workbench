"""AI-10 §8 — AI-08's independence, consumed read-only.

AI-10 does not define independence, does not extend it and does not restate it.
It imports AI-08's predicate and its finding type and passes them through
unchanged:

```text
I1-I8                          AI-08's, imported by identity
IndependenceFinding            AI-08's, returned verbatim — never wrapped
structural_independence        AI-08's, called; never reimplemented
```

There is deliberately no second independence vocabulary here. A second one would
be a second definition of the same property, and one of the two would eventually
be forgotten — the defect AI-04 §28.2 names.

### What the observation is, and is not

```text
IS      a structural finding about two EXECUTIONS
IS NOT  a statement about either material
IS NOT  correctness, agreement, verification or a verdict
IS NOT  a review finding
```

### The one check AI-10 can make

A declared attribution (`execution_id`, `agent_id`, `workspace_id`,
`input_digest`, `source_status`) can be compared with a supplied
`ExecutionRecord`. A mismatch is a REFUSAL, not a warning. Agreement proves the
declaration is consistent with the record — and proves nothing about the
material's content, because an execution's terminal artifact is a reference or a
digest and there is nothing to compare a material against.
"""

from __future__ import annotations

from agents.independence import (
    ExecutionRecord,
    IndependenceFinding,
    structural_independence,
)

from review.errors import ProvenanceMismatch
from review.material import ReviewMaterial

__all__ = ["observe_independence", "require_aligned_declaration"]


def require_aligned_declaration(
    material: ReviewMaterial, record: ExecutionRecord
) -> None:
    """§6.4. Every declared attribution field must agree with the record.

    Checked in a fixed order so the first disagreement reported is the same one
    every time.
    """
    result = record.result
    request = record.request

    pairs = (
        ("execution_id", material.execution_id, result.execution_id),
        ("agent_id", str(material.agent_id), str(request.agent_id)),
        ("workspace_id", material.workspace_id, result.workspace_id),
        ("input_digest", material.input_digest, request.input_digest),
        ("source_status", str(material.source_status), str(result.outcome)),
    )
    for field_name, declared, recorded in pairs:
        if declared != recorded:
            raise ProvenanceMismatch(
                f"material {material.material_id!r} declares {field_name} "
                f"{declared!r}, but the supplied execution record says "
                f"{recorded!r}. The declaration would attribute one execution's "
                "work to another, so the pair is refused rather than re-scoped "
                "(§6.4)"
            )


def observe_independence(
    left: ExecutionRecord, right: ExecutionRecord
) -> IndependenceFinding:
    """§8.1. AI-08's finding, returned verbatim.

    Nothing is added, subtracted or re-labelled. The caller records the object
    AI-08 produced, which is what makes "read-only consumption" checkable rather
    than promised.
    """
    return structural_independence(left, right)
