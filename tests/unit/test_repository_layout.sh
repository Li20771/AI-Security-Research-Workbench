#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"

required_files=(
  README.md
  docs/MASTER_ROADMAP.md
  docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md
  docs/AI-02_MODEL_LAYER_EXECUTION_PLAN.md
  docs/AI-03_CONTEXT_PLUGIN_EXECUTION_PLAN.md
  docs/AI-04_GUARD_EXECUTION_PLAN.md
  docs/GIT_AND_SECURITY_BOUNDARY.md
  docs/PROJECT_STATUS.md
  docs/BOOTSTRAP.md
  .gitignore
  .env.example
  config/dsh/config.example.yaml
  config/codex/config.example.yaml
  config/providers/providers.example.yaml
  config/routing/rules.example.yaml
  evidence/schema/experiment.schema.yaml
  plugins/context/__init__.py
  plugins/context/context.py
  plugins/context/workspace.py
  plugins/context/sources.py
  plugins/context/classification.py
  plugins/context/cache.py
  plugins/context/resolution.py
  plugins/context/declarations.py
  plugins/context/vocabulary.py
  plugins/context/validate.py
  workspaces/workspaces.example.yaml
)

required_dirs=(
  agents/dsh
  agents/codex
  benchmarks/tasks
  benchmarks/results
  config/dsh
  config/codex
  config/providers
  config/routing
  docs/adr
  docs/architecture
  evidence/schema
  evidence/runs
  plugins/context
  plugins/guard
  plugins/evidence
  plugins/security_tools
  providers/deepseek
  providers/mimo
  providers/openai-compatible
  routing
  scripts/bootstrap
  scripts/maintenance
  scripts/repro
  tests/unit
  tests/integration
  tests/context
  tests/guard
  tests/benchmarks
  tools/git
  tools/github
  tools/terminal
  tools/mcp
  tools/tests
  tools/vehicle_network
  tools/firmware
  tools/reverse_engineering
  workflows/definitions
  workflows/checkpoints
  workflows/policies
  workflows/runs
  workspaces
)

for path in "${required_files[@]}"; do
  test -f "$path" || { echo "MISSING FILE: $path"; exit 1; }
done

for path in "${required_dirs[@]}"; do
  test -d "$path" || { echo "MISSING DIR: $path"; exit 1; }
done

echo "repository layout: PASS"
