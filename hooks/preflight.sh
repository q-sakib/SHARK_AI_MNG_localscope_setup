#!/usr/bin/env bash
set -euo pipefail
# Lightweight safety hook. Never modifies files.
if [[ -z "${PWD:-}" ]]; then exit 0; fi
if [[ -d .git ]]; then
  if git diff --name-only 2>/dev/null | grep -E '(^|/)(\.env|.*credentials.*|.*secret.*)$' >/dev/null 2>&1; then
    printf '[AI HOOK] Warning: sensitive-looking changed file detected.\n' >&2
  fi
fi
