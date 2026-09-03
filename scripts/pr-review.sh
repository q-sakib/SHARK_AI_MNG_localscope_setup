#!/usr/bin/env bash
# Launcher for scripts/pr-review.py.
#
# Resolves Bitbucket credentials, then execs the Python CLI. This wrapper works
# around a common gotcha: a long-running parent process (e.g. an editor/agent)
# keeps a STALE copy of BB_TOKEN from when it started, so an updated token in
# ~/.bashrc is not visible. If BB_TOKEN is unset here, we pull the current value
# straight from an interactive shell (which sources ~/.bashrc).
#
# Usage:
#   scripts/pr-review.sh fetch 13811
#   scripts/pr-review.sh context 13811 --full
#   scripts/pr-review.sh post 13811 findings.json
#   scripts/pr-review.sh list 13811
#   scripts/pr-review.sh checklist
#
# Credentials (Atlassian API token, this repo's model):
#   export BB_EMAIL=you@schertech.com     # else falls back to git config user.email
#   export BB_TOKEN=<token with bitbucket scopes: read:repository, read+write:pullrequest>
# or Bitbucket app password:
#   export BB_USER=<username>  BB_APP_PASSWORD=<app-password>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pull fresh values from an interactive login shell if not already exported here.
if [[ -z "${BB_TOKEN:-}" ]]; then
  BB_TOKEN="$(bash -ic 'printf %s "${BB_TOKEN:-}"' 2>/dev/null || true)"
  export BB_TOKEN
fi
if [[ -z "${BB_EMAIL:-}" ]]; then
  BB_EMAIL="$(bash -ic 'printf %s "${BB_EMAIL:-}"' 2>/dev/null || true)"
  [[ -n "$BB_EMAIL" ]] && export BB_EMAIL
fi
# ANTHROPIC_API_KEY is needed only by the `autoreview` command.
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  ANTHROPIC_API_KEY="$(bash -ic 'printf %s "${ANTHROPIC_API_KEY:-}"' 2>/dev/null || true)"
  [[ -n "$ANTHROPIC_API_KEY" ]] && export ANTHROPIC_API_KEY
fi

# On Windows, `python3` on PATH can resolve to the App Execution Alias stub
# (WindowsApps\python3.exe), which prints "Python was not found; run without
# arguments to install from the Microsoft Store..." instead of running Python.
# Some setups exit nonzero for this, but that's not guaranteed everywhere, so
# check the actual output looks like a real version string rather than relying
# on the exit code alone.
PYTHON_BIN=python3
PYTHON3_VERSION_OUTPUT="$(python3 --version 2>&1 || true)"
if ! grep -qE '^Python [0-9]' <<<"$PYTHON3_VERSION_OUTPUT"; then
  PYTHON_BIN=python
fi

exec "$PYTHON_BIN" "$HERE/pr-review.py" "$@"
