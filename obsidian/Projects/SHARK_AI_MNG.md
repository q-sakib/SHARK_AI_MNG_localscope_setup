---
project: SHARK_AI_MNG
tags: [ai-memory, project-context]
---

# Project Context: SHARK_AI_MNG

## Architectural Decisions
- AICTX personal memory system lives entirely inside SHARK_AI_MNG (scripts/, indexes/ai.db, obsidian/) instead of ~/ai + ~/Obsidian, because the Cowork device bridge can only reach this connected folder, not the rest of the home directory.
  - Recorded: 2026-09-01 13:11:30
- Claude Code SessionStart/Stop hooks (~/.claude/settings.json) and optional pip installs (sqlite-vec, sentence-transformers) must be set up manually on the real Mac -- see hooks/HOOKS_SETUP.md and SETUP_ON_YOUR_MAC.md -- since this Cowork session cannot write outside the connected SHARK_AI_MNG folder.
  - Recorded: 2026-09-01 13:11:30

## Key Lessons & Facts
- SQLite write transactions (CREATE TABLE, INSERT) fail with a disk I/O error when run through the Cowork device_bash FUSE bridge; reads work fine over it. Run aictx.py memory-add / sync / extract_session.py from a real Terminal on the Mac, not through Cowork.
  - Recorded: 2026-09-01 13:11:30

