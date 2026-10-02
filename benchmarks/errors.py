"""AI-11 error taxonomy.

Every refusal names what was refused and why. A refusal that says only "invalid" makes
the caller guess, and a caller that guesses eventually relaxes the check.

**These are REJECTIONS, not verdicts.** A malformed TaskDefinition is refused at load;
it does not become an `OracleVerdict.BLOCKED` run. The two are different facts: BLOCKED
means "the task is well-formed and cannot run here", REJECTED means "this is not a task
at all". Collapsing them would let a schema defect be reported as an environment
problem, and an environment problem is the one a reader is most willing to ignore.
"""

from __future__ import annotations

__all__ = [
    "BenchmarkError",
    "CorpusError",
    "InvalidBenchmarkRun",
    "InvalidOracleDeclaration",
    "InvalidTaskDefinition",
    "OracleProtocolError",
    "UnregisteredTool",
    "WorkspaceDerivationError",
]


class BenchmarkError(ValueError):
    """Base class. A `ValueError`, so a raw boundary refuses malformed input with the
    exception type the rest of the repository already uses."""


class InvalidTaskDefinition(BenchmarkError):
    """§5. A TaskDefinition that the contract does not admit.

    Raised at construction rather than at run time: a definition that failed the shape
    rule must never reach a corpus, because a corpus is what a reader trusts to be
    well-formed.
    """

    reason_code = "INVALID_TASK_DEFINITION"


class InvalidOracleDeclaration(BenchmarkError):
    """§7.3, §7.4. An oracle missing a required declaration, or declaring a
    discrimination control it cannot exercise."""

    reason_code = "INVALID_ORACLE_DECLARATION"


class UnregisteredTool(BenchmarkError):
    """§5.6. A tool pair that is not in the registered v1 descriptor set.

    The registry describes; this check reads it. A task may not name a tool that does
    not exist, because a forbidden-tool list is only meaningful if the allowed one is
    real.
    """

    reason_code = "UNREGISTERED_TOOL"


class InvalidBenchmarkRun(BenchmarkError):
    """§6, §18. A run record the contract does not admit."""

    reason_code = "INVALID_BENCHMARK_RUN"


class OracleProtocolError(BenchmarkError):
    """§7.3. An oracle whose output does not carry the declared result protocol.

    Distinct from a FAIL: an oracle that did not speak is not an oracle that said no.
    """

    reason_code = "ORACLE_PROTOCOL_ERROR"


class CorpusError(BenchmarkError):
    """§17. A corpus directory that does not hold what the contract says it holds."""

    reason_code = "CORPUS_ERROR"


class WorkspaceDerivationError(BenchmarkError):
    """§15.2, §16. A workspace that could not be derived without writing to the source.

    Raised rather than worked around. The one thing this derivation exists to guarantee
    is that the source repository is not written to, and a fallback that wrote to it
    would be the guarantee failing quietly.
    """

    reason_code = "WORKSPACE_DERIVATION_ERROR"
