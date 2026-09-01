# SHARK_AI_MNG -- personal AI context & memory system

This folder is now a working, self-contained implementation of the
"personal AI memory layer" designed in the three source documents
below, built and verified in this session.

## The three source documents

- **DISCUSSION.MD** -- the architecture conversation that started
  this. Its core idea: split everything into **project scope**
  (Git-controlled: CLAUDE.md, rules, skills, ADRs -- what any developer
  needs to work on the repo) versus **personal scope** (local/private:
  memory, RAG, decisions, session history -- what *you* need to work on
  it efficiently). Project rules always outrank personal preference.
  It also proposes classifying stored knowledge as memory (facts about
  you), knowledge (facts about the project), or history (things that
  happened), each with scope/type/confidence/expiry metadata, plus a
  "context broker" that assembles only the relevant slice of all this
  for a given task rather than dumping everything into the prompt.

- **plan.md** -- turns that architecture into a concrete, runnable
  installer: a SQLite database (`memories` table + FTS5 full-text
  search, optional sqlite-vec vector search), a set of Python scripts
  (`sync_obsidian.py`, `extract_session.py`, `index_obsidian.py`,
  an `aictx` CLI), and Claude Code `SessionStart`/`Stop` hooks that
  load memories in and extract new ones out automatically. This is the
  version actually built here (see "What was adapted" below).

- **SUGGESTION.MD** -- a tour of the more advanced ideas worth
  knowing about if this grows: dedicated memory tools (Letta, Mem0,
  Zep), context-compression techniques (LLMLingua-style), temporal
  memory (valid_from/valid_until, already present in the schema here),
  contradiction detection and memory "garbage collection", hybrid
  search + reranking, and treating your knowledge base like compiled
  source (raw notes -> canonical knowledge -> index -> wiki). None of
  this is required for the system to be useful now; it's a menu for
  later, roughly in the priority order the document lays out (Tier 1
  through Tier 4).

## What was adapted, and why

plan.md's installer targets the machine's home directory directly:
`~/ai/scripts`, `~/Obsidian/AI-Knowledge-Hub`, `~/.claude/settings.json`.
This session reaches your Mac only through the SHARK_AI_MNG folder you
connected -- it cannot create folders elsewhere in your home directory,
install packages into your system Python, or edit `~/.claude/settings.json`
directly. So the whole system was rebuilt to live entirely inside this
folder instead. What's left needs one command in your own Terminal --
`bootstrap.sh` -- see `SETUP_ON_YOUR_MAC.md`.

## Layout

```
SHARK_AI_MNG/
├── README.md                    (this file)
├── DISCUSSION.MD, plan.md, SUGGESTION.MD   (source docs, unchanged)
├── SETUP_ON_YOUR_MAC.md         (run bootstrap.sh -- read this next)
├── bootstrap.sh                 (one-command setup: schema + hooks + verify)
├── scripts/
│   ├── _common.py               (shared paths -- everything is relative to this folder)
│   ├── install.py               (creates indexes/ai.db schema -- idempotent)
│   ├── aictx.py                 (CLI: status / memory-add / memory-search / build-context / sync / index)
│   ├── sync_obsidian.py         (DB -> obsidian/ Markdown notes)
│   ├── index_obsidian.py        (obsidian/ notes -> FTS5 search index)
│   ├── extract_session.py       (transcript -> claude -p -> new memories; used by the Stop hook)
│   └── merge_hooks.py           (additively merges hooks/claude_hooks_snippet.json into ~/.claude/settings.json)
├── indexes/
│   └── ai.db                    (SQLite: memories, obsidian_fts, optionally obsidian_vec)
├── obsidian/                    (point a real Obsidian vault at this folder if you want the human view)
│   ├── Preferences/Personal-Preferences.md
│   ├── Projects/<project>.md
│   └── Decisions/               (reserved for future ADR-style notes)
├── sessions/                    (reserved for per-session working context, per SUGGESTION.MD idea #10)
└── hooks/
    ├── claude_hooks_snippet.json
    └── HOOKS_SETUP.md
```

## One-command setup

```bash
bash /Users/shark/SHARK_AI_MNG/bootstrap.sh
```

Creates the DB/folders, wires the Claude Code hooks into
`~/.claude/settings.json` (additively -- won't clobber anything you
already have there), and runs a verification pass. Options:
`--with-semantic` (installs sqlite-vec + sentence-transformers for
fuzzy search), `--no-hooks` (skip the hooks step). Safe to re-run.
Full details: `SETUP_ON_YOUR_MAC.md`.

## Using it day to day

```bash
cd /Users/shark/SHARK_AI_MNG/scripts

# see what's stored
python3 aictx.py status

# record something durable
python3 aictx.py memory-add "We decided to keep Redis for session storage" \
    --scope project --type decision --project my-other-project

# a personal preference (applies everywhere, not tied to one project)
python3 aictx.py memory-add "Prefer concise PR descriptions" --scope personal --type preference

# regenerate the human-readable notes + search index after adding memories
python3 aictx.py sync
python3 aictx.py index

# pull up what's relevant before starting work on a project
python3 aictx.py build-context --project my-other-project

# search memories (exact substring match)
python3 aictx.py memory-search redis

# search the obsidian/ notes themselves (full-text always; also semantic
# if you ran bootstrap.sh --with-semantic -- use the .venv python for that)
python3 aictx.py note-search "authentication timeout"
../.venv/bin/python3 aictx.py note-search "authentication timeout"   # + semantic, if installed
```

Everything above is stdlib-only Python -- no installs required. It
already has 3 seeded memories from this setup session (see
`obsidian/Projects/SHARK_AI_MNG.md`) documenting the two adaptation
decisions and the SQLite-over-FUSE limitation discovered while
building it.

If you wire up the Claude Code hooks (`SETUP_ON_YOUR_MAC.md`, step 1),
`build-context` and `extract_session.py` run automatically at the
start/end of every Claude Code session on this machine, tagged by
whatever project directory you're in.

## Known limitation of this bridge

SQLite **write** transactions fail with a "disk I/O error" when run
through the Cowork device bridge (the mount doesn't support the file
locking SQLite needs for writes); reads work fine. This isn't a
problem once the files are sitting on your normal Mac disk -- it only
affects trying to run `memory-add` / `sync` / `index` /
`extract_session.py` *through a Cowork session*. Run those from a
regular Terminal window on this Mac instead.
