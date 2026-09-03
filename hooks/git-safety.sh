#!/usr/bin/env bash
set -euo pipefail
# Read-only guard intended for use before git operations.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch="$(git branch --show-current 2>/dev/null || true)"
  printf '[AI HOOK] branch=%s\n' "$branch"
fi
