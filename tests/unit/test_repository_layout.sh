#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"

required=(
  README.md
  docs/MASTER_ROADMAP.md
  docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md
  docs/GIT_AND_SECURITY_BOUNDARY.md
  .gitignore
  .env.example
  agents/dsh
  agents/codex
  providers/deepseek
  providers/mimo
  plugins/context
  plugins/guard
  plugins/evidence
  plugins/security-tools
  tools/vehicle-network
  benchmarks/tasks
  evidence/schema
  workspaces
)

for path in "${required[@]}"; do
  test -e "$path" || { echo "MISSING: $path"; exit 1; }
done

echo "repository layout: PASS"
