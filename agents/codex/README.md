# codex

The independent second Agent (`AgentRole.INDEPENDENT_SECOND`). See `body.py`.

The role is an **architectural name**, not an independence finding. The role
alone never satisfies I1-I8; independence is a property of an execution *pair*.

## The provider seam

```text
CodexBody          AI-08 owns this
    |
CodexBackend       the interface AI-08-B defines and does NOT implement
    |
provider / model   AI-09 wires a real one
```

AI-08 implements no OpenAI-compatible client, no domestic provider, no model
profile, no credential path and no network call. `OfflineCodexBackend` is the
only backend v1 ships: deterministic, offline, and not a model.
