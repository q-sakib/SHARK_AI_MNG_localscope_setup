# Wiring AICTX into Claude Code (manual, one-time, on your Mac)

This step can't be done from a Cowork/cloud session: it edits
`~/.claude/settings.json`, which lives outside the SHARK_AI_MNG folder
this session has access to, and it's a **global** file that affects
every Claude Code project on this machine -- not something that should
be changed without you looking at it first.

## What it does

Once wired up:
- **SessionStart**: every time you start Claude Code in any project, it
  runs `aictx.py build-context` and prints your relevant personal
  preferences plus whatever project-scoped memories exist for that
  project's folder name.
- **Stop**: every time a Claude Code session ends, it hands the
  transcript to `extract_session.py`, which calls `claude -p` once to
  pull out durable preferences/decisions/lessons and reconcile them
  against what's already stored (add / supersede / ignore). This costs
  one extra `claude -p` call per session.

## Steps

1. Open Terminal on this Mac.
2. Check whether you already have hooks configured:
   ```bash
   cat ~/.claude/settings.json 2>/dev/null
   ```
3. If that file doesn't exist yet, just copy `claude_hooks_snippet.json`
   in this folder to `~/.claude/settings.json`:
   ```bash
   mkdir -p ~/.claude
   cp /Users/shark/SHARK_AI_MNG/hooks/claude_hooks_snippet.json ~/.claude/settings.json
   ```
4. If you already have a `~/.claude/settings.json` with other settings
   (or other hooks) in it, **don't overwrite it** -- merge the
   `"hooks"."SessionStart"` and `"hooks"."Stop"` arrays from
   `claude_hooks_snippet.json` into your existing file by hand, or ask
   Claude Code itself to do the merge for you in a real terminal
   session:
   ```bash
   claude -p "Merge the hooks in /Users/shark/SHARK_AI_MNG/hooks/claude_hooks_snippet.json into ~/.claude/settings.json without deleting any existing hooks or settings."
   ```
5. Confirm `python3` is on your PATH (`which python3`) -- if you use a
   different Python (pyenv, homebrew python3, etc.), edit the
   `command` lines in `~/.claude/settings.json` to use that path
   instead of the bare `python3`.
6. Test it: run `claude` in any project directory and confirm you see
   the "Active Project Memories & Rules" block at session start.

## Undoing this

Remove the `SessionStart` / `Stop` entries from `~/.claude/settings.json`
(or delete the file if AICTX was the only thing in it).
