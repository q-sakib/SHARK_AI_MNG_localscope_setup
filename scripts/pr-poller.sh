#!/usr/bin/env bash
# Launcher for scripts/pr-poller.py.
#
# Long-running local daemon: every --interval seconds it polls Bitbucket for OPEN
# pull requests targeting the --target branch (default: main) and, for each new
# one, runs `scripts/pr-review.sh autoreview <PR_NUMBER>`.
#
# Like pr-review.sh, this pulls a fresh BB_TOKEN / BB_EMAIL / ANTHROPIC_API_KEY
# from an interactive login shell if they are not already exported here (works
# around a stale token cached in a long-lived parent process).
#
# Usage:
#   scripts/pr-poller.sh                    # poll every 120s, watch main
#   scripts/pr-poller.sh --interval 60
#   scripts/pr-poller.sh --review-backlog   # also review already-open PRs on first run
#   scripts/pr-poller.sh --once             # single pass (cron-friendly)
#   scripts/pr-poller.sh --dry-run
#
# Run detached:
#   nohup scripts/pr-poller.sh >> ~/.cache/sfs-pr-poller/poller.log 2>&1 &
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
# ANTHROPIC_API_KEY is used by pr-review.sh autoreview when engine=api.
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  ANTHROPIC_API_KEY="$(bash -ic 'printf %s "${ANTHROPIC_API_KEY:-}"' 2>/dev/null || true)"
  [[ -n "$ANTHROPIC_API_KEY" ]] && export ANTHROPIC_API_KEY
fi

exec python3 "$HERE/pr-poller.py" "$@"
