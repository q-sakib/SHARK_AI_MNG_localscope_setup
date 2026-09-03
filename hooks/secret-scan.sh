#!/usr/bin/env bash
set -euo pipefail
# Optional advisory scan. Does not block by default.
if command -v gitleaks >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  gitleaks protect --staged --no-banner >/dev/null 2>&1 || {
    printf '[AI HOOK] Potential secret detected in staged changes. Review before commit.\n' >&2
  }
fi
