#!/usr/bin/env python3
"""
AICTX bootstrap: creates the SQLite schema for this project's personal
AI memory system. Idempotent -- safe to re-run.

Adapted from plan.md's install_aictx_pipeline.py: instead of targeting
the real machine's home directory (~/ai, ~/Obsidian, ~/.claude), every
path here is relative to this project folder (BASE), so the whole
system is self-contained inside SHARK_AI_MNG.
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INDEXES_DIR = BASE / "indexes"
VAULT_DIR = BASE / "obsidian"
DB_PATH = INDEXES_DIR / "ai.db"


def setup_directories():
    print("[1/3] Ensuring directory structure...")
    INDEXES_DIR.mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Preferences").mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Projects").mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Decisions").mkdir(parents=True, exist_ok=True)
    (BASE / "sessions").mkdir(parents=True, exist_ok=True)


def init_database():
    print("[2/3] Initializing SQLite schema...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            scope TEXT CHECK(scope IN ('personal', 'project')) DEFAULT 'project',
            type TEXT CHECK(type IN ('preference', 'decision', 'lesson', 'fact')) DEFAULT 'lesson',
            content TEXT NOT NULL,
            source_ref TEXT DEFAULT 'SessionLog',
            supersedes_id INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            valid_until TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (supersedes_id) REFERENCES memories(id)
        );
    """)

    # Optional vector search -- only if sqlite-vec is installed. Purely
    # additive: everything else works with stdlib sqlite3 alone.
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS obsidian_vec USING vec0(
                doc_id TEXT PRIMARY KEY,
                embedding float[384]
            );
        """)
        print("  - sqlite-vec virtual table initialized (semantic search enabled).")
    except Exception as e:
        print(f"  - sqlite-vec not installed; semantic search disabled, full-text search still works ({type(e).__name__}).")

    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS obsidian_fts USING fts5(
            doc_id UNINDEXED,
            file_path,
            title,
            content
        );
    """)

    conn.commit()
    conn.close()


def verify():
    print("[3/3] Verifying...")
    assert DB_PATH.exists(), "DB was not created"
    conn = sqlite3.connect(DB_PATH)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
    conn.close()
    print(f"  - DB at {DB_PATH}")
    print(f"  - Tables: {tables}")


if __name__ == "__main__":
    setup_directories()
    init_database()
    verify()
    print("\nSetup complete.")
