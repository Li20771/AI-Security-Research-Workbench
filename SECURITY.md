# Security Policy

## High-impact actions
The following require explicit human approval:

- modifying main
- history rewrite or force push
- merge / deployment
- sudo or system configuration
- credential changes
- real CAN / ECU / vehicle access
- destructive filesystem operations
- uncontrolled remote execution

## Vehicle-network boundary
Default experiments use vcan, simulators, or isolated harnesses. Real physical interfaces are outside the default Agent permission set.

## Secrets
Never commit API keys, tokens, passwords, private keys, SSH credentials, or session cookies.

## Evidence
Agent text is not evidence. Successful claims require executable validation or another recorded evidence source.