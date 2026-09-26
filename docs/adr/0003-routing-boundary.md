# ADR 0003: Routing Boundary

## Status
Accepted

## Decision
Model Router is a Workbench core service, not a DSH plugin.

## Rationale
Routing spans multiple Agents and providers. It should not become coupled to one Agent runtime.

## Security consequence
Router never grants permissions. Guard remains authoritative.
```text
Task -> Router -> eligible Agent/Provider/Model -> Guard -> Tool
```