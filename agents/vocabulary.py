"""AI-08 §5 — the Agent identity vocabulary.

**Owner: AI-08.** FROZEN by AI-08-A (contract §5, amendment log §22).

```text
AgentId     closed      dsh | codex
AgentRole   closed      PRIMARY | INDEPENDENT_SECOND
```

### Three questions, three fields

The single most likely way to get this layer wrong is to collapse these into one
another. AI-08-A §5.3 freezes them apart:

```text
ActorType   WHAT KIND of actor is this     AI-04 owns it
            ActorType.AGENT means "this is an agent actor". It does not say
            which agent.

AgentId     WHICH registered Agent         AI-08 owns it, here
            It does not say what the agent is for.

AgentRole   WHAT ROLE does it carry        AI-08 owns it, here
            It restates neither, and it grants nothing.
```

`ActorType` is **imported, never redefined** — the defect AI-04 §28.2 names, and
the one AI-05 §7.1 paid for once already.

### Registration, not discovery — §5.4

```text
FROZEN: identity resolution is a pure function over the frozen vocabulary and
        the frozen registration table.

FORBIDDEN: reading a directory, an environment variable or a config file to
           decide which Agents exist; treating an unregistered token as a new
           Agent; a default agent for an unrecognised token.
```

`config/dsh/config.example.yaml` and `config/codex/config.example.yaml` remain
what they were: documentation. Nothing here reads them, and nothing may.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

__all__ = [
    "AgentId",
    "AgentRole",
    "ROLE_BY_AGENT",
    "UnknownAgent",
    "resolve_agent",
    "role_for",
]


class AgentId(StrEnum):
    """§5.1. The registered Agents. Closed, two members, FROZEN.

    A free-form string is **never** a trusted Agent identity. Adding a member is
    a code change and a contract amendment (§18); it must not arise from
    filesystem discovery, environment inspection, configuration reading or any
    other runtime mechanism.
    """

    DSH = "dsh"
    CODEX = "codex"


class AgentRole(StrEnum):
    """§5.2. AI-08's own role vocabulary. Closed, FROZEN.

    It does not restate HUMAN / AGENT / SERVICE, and it carries no permission,
    no capability and no authorization.

    **A role is not an independence finding** (§5.2.1). `INDEPENDENT_SECOND` is
    an architectural name; the role alone never satisfies I1-I8 and is never
    proof of structural independence, which is a property of an execution
    *pair* and of nothing else.
    """

    PRIMARY = "PRIMARY"
    INDEPENDENT_SECOND = "INDEPENDENT_SECOND"


class UnknownAgent(ValueError):
    """§6.2. A candidate that is not a registered `AgentId`.

    Refused rather than guessed at. There is no "probably dsh" branch and no
    default agent — a caller that wanted `codex` and silently got `dsh` would
    have two Agents' work attributed to one.
    """

    reason_code = "UNKNOWN_AGENT"


#: §5.2. The v1 registration. Total over `AgentId`, and fixed.
#:
#: A read-only mapping rather than a function with branches, so the table is
#: the single place the pairing is stated and a reader can see all of it at
#: once.
ROLE_BY_AGENT: Mapping[AgentId, AgentRole] = MappingProxyType(
    {
        AgentId.DSH: AgentRole.PRIMARY,
        AgentId.CODEX: AgentRole.INDEPENDENT_SECOND,
    }
)


def role_for(agent_id: AgentId) -> AgentRole:
    """The registered role of a known Agent (§5.2).

    Total over `AgentId`: every member has a row, and the mapping is closed, so
    this cannot return `None` for a value the type admits.
    """
    return ROLE_BY_AGENT[AgentId(agent_id)]


def resolve_agent(candidate: object) -> AgentId:
    """§6.2. The ONE boundary at which a candidate becomes a trusted identity.

    ```text
    a registered AgentId member  -> returned
    anything else                -> REFUSED
    ```

    This is where a `RouterDecision.agent_hint` stops being a hint. AI-07 froze
    that a hint is a hint and that AI-07 must not assert it identifies a
    verified Agent; AI-08 does not change that — it makes the caller pass the
    candidate through here before anything acts on it.

    No discovery, no guessing, no default (§5.4). A membership test and the
    frozen table, and nothing else.
    """
    if isinstance(candidate, AgentId):
        return candidate
    if isinstance(candidate, str):
        try:
            return AgentId(candidate)
        except ValueError:
            pass
    raise UnknownAgent(
        f"{candidate!r} is not a registered Agent. The AgentId vocabulary is "
        f"{sorted(m.value for m in AgentId)} and it is closed (§5.1). An "
        "unregistered token is refused rather than treated as a new Agent, and "
        "there is no default agent (§5.4, §6.2)"
    )
