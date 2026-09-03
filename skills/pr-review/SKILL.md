---
name: pr-review
description: "Bitbucket PR review automation. Fetches PR diff, runs Claude review against project conventions, and posts inline + summary comments. Includes an auto-review daemon that polls for new PRs. Scripts live in scripts/pr-review.sh and scripts/pr-poller.sh. Use when asked to review a PR, set up automated PR review, or run the PR poller."
---

# PR Review (Bitbucket)

Automated Bitbucket PR review — fetches diff, reviews against project conventions via Claude, posts inline + summary comments.

## Scripts

| Script | Use |
|---|---|
| `scripts/pr-review.sh <cmd> <PR>` | Main CLI |
| `scripts/pr-poller.sh` | Auto-review daemon (polls every 120s) |

## Credentials needed (in `.env`)

```bash
BB_EMAIL=you@domain.com          # Atlassian account email
BB_TOKEN=your-atlassian-api-token # scopes: read:repository, read+write:pullrequest
# OR Bitbucket app password:
BB_USER=username
BB_APP_PASSWORD=ATBBxxxx
ANTHROPIC_API_KEY=sk-ant-...     # only for --engine api mode
```

Workspace/repo are parsed automatically from `git remote get-url origin`.

## Commands

```bash
# Fetch + print PR context (human review prep)
scripts/pr-review.sh review 1234

# Fetch only (metadata, branches, changed files)
scripts/pr-review.sh fetch 1234

# Print diff (add --full for changed source files with line numbers)
scripts/pr-review.sh context 1234 --full

# Fully automatic: Claude reviews and posts inline + summary comments
scripts/pr-review.sh autoreview 1234

# Post findings from a JSON file
scripts/pr-review.sh post 1234 findings.json

# List existing comments on a PR
scripts/pr-review.sh list 1234

# Print the project review checklist
scripts/pr-review.sh checklist
```

## Auto-review options

```bash
scripts/pr-review.sh autoreview 1234 --model opus      # override model (default: sonnet)
scripts/pr-review.sh autoreview 1234 --effort high     # override effort (default: high)
scripts/pr-review.sh autoreview 1234 --dry-run         # write findings.json, don't post
scripts/pr-review.sh autoreview 1234 --engine api      # use Anthropic API instead of claude CLI
scripts/pr-review.sh autoreview 1234 --no-caveman      # full prose instead of terse output
```

## PR Poller (auto-review daemon)

Reviews all open PRs targeting `main` that have no comments yet and are ≤4 days old.

```bash
# Start (runs forever)
scripts/pr-poller.sh

# Single pass then exit (cron-friendly)
scripts/pr-poller.sh --once

# Dry run — log what it would review, don't trigger
scripts/pr-poller.sh --once --dry-run

# Watch a different branch
scripts/pr-poller.sh --target develop

# Background with log
nohup scripts/pr-poller.sh >> ~/.cache/pr-poller/poller.log 2>&1 &
```

## findings.json schema

```json
{
  "summary": "markdown text for a top-level PR comment",
  "findings": [
    {
      "severity": "blocker|major|minor|nit",
      "path":     "src/foo.ts",
      "line":     42,
      "anchor":   "to",
      "title":    "short headline",
      "body":     "full comment markdown"
    }
  ]
}
```

See `scripts/pr-review.findings.example.json` for a complete example.

## Severity policy

| Severity | Meaning | Action |
|---|---|---|
| **blocker** | Injection, auth bypass, leaked secret, data loss, crash on hot path, breaking API change | Blocks merge |
| **major** | Likely bug, missing validation, N+1, race condition | Must fix |
| **minor** | Nit, naming, readability, convention | Should fix |
| **nit** | Style, optional refactor | Optional |
