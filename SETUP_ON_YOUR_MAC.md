# One-command setup

Run this once in a real Terminal window on this Mac (not through a
Cowork session -- see "Why this can't run from Cowork" below):

```bash
bash /Users/shark/SHARK_AI_MNG/bootstrap.sh
```

That single command:
1. creates/verifies the database schema and folders (safe to re-run)
2. merges the AICTX hooks into `~/.claude/settings.json` -- **additively**:
   it appends to `hooks.SessionStart`/`hooks.Stop` rather than
   overwriting them, skips anything already installed, and backs up
   your existing settings file first if it changes anything
3. skips the optional semantic-search packages by default (see below)
4. runs a status/sync/index pass so you can see it working

Options:
```bash
bash bootstrap.sh --with-semantic   # also pip installs sqlite-vec + sentence-transformers
bash bootstrap.sh --no-hooks        # skip touching ~/.claude/settings.json entirely
bash bootstrap.sh --help
```

It's safe to run more than once -- every step checks what's already
there before changing anything.

## What "--with-semantic" installs

It creates a Python virtual environment at `.venv/` inside this
folder and installs `sqlite-vec` + `sentence-transformers` there --
**not** into your system Python. macOS's Homebrew Python refuses
system-wide `pip install` by default (PEP 668,
"externally-managed-environment"); a venv is the clean way around
that instead of forcing it with `--break-system-packages`.
`sentence-transformers` also pulls in PyTorch (a few hundred MB).
Skip it unless you want semantic search -- plain full-text search
(`aictx.py note-search`) already works with zero extra installs.

Once installed, use the venv's python to get semantic results:
```bash
/Users/shark/SHARK_AI_MNG/.venv/bin/python3 /Users/shark/SHARK_AI_MNG/scripts/aictx.py note-search "your query"
```
Plain `python3 ... note-search` still works from anywhere -- it just
falls back to full-text-only results if the venv/packages aren't on
that particular `python3`'s path.

## Verify it worked

```bash
python3 /Users/shark/SHARK_AI_MNG/scripts/aictx.py status
cat ~/.claude/settings.json   # should now include AICTX's SessionStart/Stop hooks
```

Then `cd` into any project and run `claude` -- you should see an
"Active Project Memories & Rules" block print at session start.

## Why this can't run from Cowork

This Cowork session reaches this Mac only through the SHARK_AI_MNG
folder you connected -- it can't touch `~/.claude` or your system
Python outside that folder. It also can't reliably run the *database
write* steps (`memory-add`, `sync`... no wait, `sync` only reads the
DB and writes plain Markdown, so that one's fine -- but `index`,
`memory-add`, and `extract_session.py` all write to the SQLite
database) through the bridge itself: that bridge's filesystem doesn't
support the file locking SQLite needs for writes, and testing
`bootstrap.sh` through it during setup briefly left the on-device
database mid-transaction before it was restored from a clean copy.
Reads, and plain file writes (JSON, Markdown), work fine over the
bridge -- it's specifically SQLite *write transactions* that don't.
None of this affects `bootstrap.sh` running normally in your own
Terminal, on your normal Mac filesystem.
