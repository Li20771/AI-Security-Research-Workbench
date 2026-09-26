# Workbench Bootstrap

## Clean checkout
```bash
git clone git@github.com:Li20771/AI-Security-Research-Workbench.git
cd AI-Security-Research-Workbench
git status
```

## Local secrets
Copy .env.example to .env only when a provider integration needs credentials. Never commit .env.

## Baseline rule
Implementation must happen on a task branch, not main. Record the base SHA before meaningful changes.

## Version freeze
AI-01 will record the exact supported versions for DSH, Codex, Git, Python, Node/npm, and Docker as actually tested.