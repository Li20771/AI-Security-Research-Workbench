# Routing

Workbench core service for Model Router.

Responsibilities:

- Select eligible Agent / Provider / Model profiles.
- Apply configurable routing rules.
- Record routing decisions for audit and evidence.

Model Router never grants permissions.
Guard remains authoritative.

Configuration:
- `config/routing/`

Versioned progression: Router v1 -> benchmark data -> Router v2.
