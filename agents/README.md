# Agents

The Workbench **core Agent layer** (AI-08). It sits beside `routing/`, not under
`plugins/`: the Router selects, Guard authorizes, Evidence records, and this
layer executes and attributes.

```text
agents/          AI-08's home. A core layer, reached as a namespace package
                 relative to the repository root, exactly as routing/ is.
agents/dsh/      the primary Agent's execution shape
agents/codex/    the independent second Agent, and the AI-09 provider seam
```

Contract: [`docs/AI-08_AGENT_EXECUTION_EXECUTION_PLAN.md`](../docs/AI-08_AGENT_EXECUTION_EXECUTION_PLAN.md)
(frozen at AI-08-A, two amendments).

## What is here

```text
vocabulary.py    AgentId (dsh | codex), AgentRole (PRIMARY | INDEPENDENT_SECOND),
                 the frozen registration, and resolve_agent
request.py       AgentExecutionRequest, and the opaque ExecutionId
result.py        AgentResult and AgentExecutionOutcome
toolcall.py      the tool path: one fresh GuardRequest and GuardDecision per invocation
body.py          what a body is, and v1's offline deterministic body
runtime.py       the controller: establish context, run the body, one terminal result
independence.py  the I1-I8 predicate over an execution pair
```

## The boundaries this layer keeps

```text
one AgentExecutionRequest -> one ExecutionId -> one terminal AgentResult
    and the last line holds for COMPLETED, FAILED and BLOCKED alike

Context      the runtime establishes exactly one ContextResponse per execution,
             and the execution owns it. The request carries a descriptor, never
             a response.
Guard        AI-08 does not call Guard. It hands AI-06 a ToolRequest whose actor
             is the AgentId, and AI-06 builds a fresh GuardRequest per
             invocation. No decision is cached or reused.
Evidence     AI-08 writes NO EvidenceRecord. The only producer token admissible
             for an EXECUTION record is AI-06's, and AI-08 is not AI-06.
Router       no import runs in either direction. An agent_hint stays a hint.
Provider     none. AI-08 v1 reaches no network and binds no model; that is AI-09's.
```

## What v1 does not do

```text
no inference      the offline bodies perform none. Every capability on every
                  shipped model profile is UNKNOWN and no provider call has ever
                  been made in this repository.
no comparison     no cross-agent review, no second opinion, no vote. AI-10's.
no retry          no retry, resume, timeout, cancellation or escalation. AI-13's.
no ceiling        no Agent-specific permission policy. Guard cannot express one,
                  and AI-08 does not claim one.
```

`COMPLETED` means an execution reached a terminal result. It is **not** `PASS`,
not `VERIFIED`, not `CORRECT`, and not task success.
