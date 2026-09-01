#!/usr/bin/env python3
"""Index the obsidian/ vault's Markdown notes into the FTS5 full-text
search table so `aictx.py search` can find them. Also feeds the
optional vec0 table when sqlite-vec + sentence-transformers are
installed (semantic search) -- entirely optional, skipped otherwise."""
import sqlite3
from pathlib import Path
from _common import DB_PATH, VAULT_PATH


def index_vault():
    if not DB_PATH.exists():
        print(f"No database at {DB_PATH} -- run install.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    model = None
    vec_enabled = False
    try:
        import sqlite_vec
        from sentence_transformers import SentenceTransformer
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS obsidian_vec USING vec0(
                doc_id TEXT PRIMARY KEY,
                embedding float[384]
            );
        """)
        model = SentenceTransformer("all-MiniLM-L6-v2")
        vec_enabled = True
    except Exception:
        pass  # semantic search stays off; FTS5 still works fully

    cursor.execute("DELETE FROM obsidian_fts;")
    if vec_enabled:
        cursor.execute("DELETE FROM obsidian_vec;")

    count = 0
    if VAULT_PATH.exists():
        for path in VAULT_PATH.rglob("*.md"):
            content = path.read_text(encoding="utf-8")
            sections = content.split("\n## ")
            for i, section in enumerate(sections):
                doc_id = f"{path.stem}#chunk-{i}"
                cursor.execute(
                    "INSERT INTO obsidian_fts (doc_id, file_path, title, content) VALUES (?, ?, ?, ?)",
                    (doc_id, str(path), path.stem, section),
                )
                if vec_enabled:
                    import sqlite_vec
                    emb = model.encode(section).tolist()
                    cursor.execute(
                        "INSERT INTO obsidian_vec (doc_id, embedding) VALUES (?, ?)",
                        (doc_id, sqlite_vec.serialize_float32(emb)),
                    )
                count += 1

    conn.commit()
    conn.close()
    mode = "FTS5 + semantic (sqlite-vec)" if vec_enabled else "FTS5 only"
    print(f"Indexed {count} chunk(s) from {VAULT_PATH} [{mode}]")


if __name__ == "__main__":
    index_vault()
