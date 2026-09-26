#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
cd "$root"

echo "== AI Workbench preflight =="
git status --short
printf 'branch: '
git branch --show-current
printf 'sha: '
git rev-parse --short HEAD

test -f README.md
test -f docs/MASTER_ROADMAP.md
test -f docs/AI-00_REQUIREMENTS_AND_ARCHITECTURE.md
test -f docs/GIT_AND_SECURITY_BOUNDARY.md
test -f .gitignore
test -f .env.example

git diff --quiet
echo "preflight: PASS"
