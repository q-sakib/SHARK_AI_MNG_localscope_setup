#!/usr/bin/env python3
"""
aictx -- the command-line entry point for this project's personal AI
context/memory system. Stdlib-only (argparse), so it runs anywhere
python3 runs, with no pip installs required.

Usage:
  python3 aictx.py status
  python3 aictx.py memory-add "We decided to keep Redis for sessions" --type decision --scope project --project SHARK_AI_MNG
  python3 aictx.py memory-search "redis"
  python3 aictx.py note-search "authentication timeout"   # full-text + semantic (if .venv installed) over obsidian/ notes
  python3 aictx.py build-context --project SHARK_AI_MNG
  python3 aictx.py sync            # re-export DB -> obsidian/ notes
  python3 aictx.py index           # re-index obsidian/ notes -> FTS5
"""
import argparse
import sqlite3
import sys
from _common import DB_PATH, PROJECT_NAME


def cmd_status(args):
    if not DB_PATH.exists():
        print(f"No database at {DB_PATH}. Run: python3 install.py")
        return
    conn = sqlite3.connect(DB_PATH)
    n_memories = conn.execute("SELECT COUNT(*) FROM memories WHERE valid_until IS NULL").fetchone()[0]
    try:
        n_notes = conn.execute("SELECT COUNT(*) FROM obsidian_fts").fetchone()[0]
    except sqlite3.OperationalError:
        n_notes = 0
    conn.close()
    print("AICTX status")
    print(f"  Database:        {DB_PATH}")
    print(f"  Active memories: {n_memories}")
    print(f"  Indexed chunks:  {n_notes}")


def cmd_memory_add(args):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO memories (project_id, scope, type, content, source_ref) VALUES (?, ?, ?, ?, ?)",
        (args.project, args.scope, args.type, args.content, args.source or "manual"),
    )
    conn.commit()
    conn.close()
    print(f"Added [{args.scope}/{args.type}] memory to project '{args.project}'.")


def cmd_memory_search(args):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, project_id, scope, type, content, created_at FROM memories "
        "WHERE valid_until IS NULL AND content LIKE ? ORDER BY created_at DESC",
        (f"%{args.query}%",),
    ).fetchall()
    conn.close()
    if not rows:
        print("No matching memories.")
        return
    for mem_id, project_id, scope, type_, content, created_at in rows:
        print(f"#{mem_id} [{project_id}/{scope}/{type_}] {content}  ({created_at})")


def cmd_note_search(args):
    if not DB_PATH.exists():
        print(f"No database at {DB_PATH}. Run: python3 install.py")
        return
    conn = sqlite3.connect(DB_PATH)

    try:
        rows = conn.execute(
            "SELECT title, file_path, content FROM obsidian_fts WHERE obsidian_fts MATCH ? ORDER BY rank LIMIT ?",
            (args.query, args.limit),
        ).fetchall()
    except sqlite3.OperationalError as e:
        rows = []
        print(f"(full-text query error: {e})")

    if rows:
        print("### Full-text matches")
        for title, file_path, content in rows:
            snippet = " ".join(content.split())[:150]
            print(f"- {title} ({file_path}): {snippet}...")
    else:
        print("No full-text matches.")

    try:
        import sqlite_vec
        from sentence_transformers import SentenceTransformer
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb = model.encode(args.query).tolist()
        vec_rows = conn.execute(
            "SELECT f.title, f.file_path, v.distance FROM obsidian_vec v "
            "JOIN obsidian_fts f ON v.doc_id = f.doc_id "
            "WHERE v.embedding MATCH ? AND v.k = ? ORDER BY v.distance",
            (sqlite_vec.serialize_float32(emb), args.limit),
        ).fetchall()
        if vec_rows:
            print("\n### Semantic matches")
            for title, file_path, dist in vec_rows:
                print(f"- {title} ({file_path})  distance={dist:.3f}")
    except ModuleNotFoundError:
        pass  # sqlite-vec / sentence-transformers not installed -- FTS results above still stand
    except sqlite3.OperationalError:
        pass  # obsidian_vec table doesn't exist yet -- run `index` with the venv's python first
    except Exception as e:
        # Model loading can fail lots of ways (no internet on first run
        # to download it, a corrupted cache, etc.) -- never let that
        # take down the whole command when FTS results already printed.
        print(f"(semantic search unavailable this time: {type(e).__name__}: {e})")
    finally:
        conn.close()


def cmd_build_context(args):
    if not DB_PATH.exists():
        print(f"No database at {DB_PATH}. Run: python3 install.py")
        return
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT scope, type, content FROM memories WHERE (project_id = ? OR scope = 'personal') AND valid_until IS NULL",
        (args.project,),
    ).fetchall()
    conn.close()
    if rows:
        print("### Active Project Memories & Rules")
        for scope, mtype, content in rows:
            print(f"- [{mtype.upper()}] {content}")
    else:
        print(f"(no memories yet for project '{args.project}')")


def cmd_sync(args):
    from sync_obsidian import export_to_obsidian
    export_to_obsidian()


def cmd_index(args):
    from index_obsidian import index_vault
    index_vault()


def main():
    parser = argparse.ArgumentParser(prog="aictx")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status").set_defaults(func=cmd_status)

    p_add = sub.add_parser("memory-add", help="add a memory")
    p_add.add_argument("content")
    p_add.add_argument("--project", default=PROJECT_NAME)
    p_add.add_argument("--scope", choices=["personal", "project"], default="project")
    p_add.add_argument("--type", choices=["preference", "decision", "lesson", "fact"], default="lesson")
    p_add.add_argument("--source")
    p_add.set_defaults(func=cmd_memory_add)

    p_search = sub.add_parser("memory-search", help="search memories")
    p_search.add_argument("query")
    p_search.set_defaults(func=cmd_memory_search)

    p_ctx = sub.add_parser("build-context", help="print active context for a project")
    p_ctx.add_argument("--project", default=PROJECT_NAME)
    p_ctx.set_defaults(func=cmd_build_context)

    p_notes = sub.add_parser("note-search", help="search obsidian/ notes (full-text, plus semantic if installed)")
    p_notes.add_argument("query")
    p_notes.add_argument("--limit", type=int, default=5)
    p_notes.set_defaults(func=cmd_note_search)

    sub.add_parser("sync", help="export DB -> obsidian/ notes").set_defaults(func=cmd_sync)
    sub.add_parser("index", help="index obsidian/ notes -> FTS5").set_defaults(func=cmd_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
