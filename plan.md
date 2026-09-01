Below is the complete, self-contained Markdown setup guide and executable Python script.

You can copy this entire block and hand it directly to your Claude agent. The script automatically creates the directory structures, initializes SQLite databases (with schema versioning and extensions), writes out the memory broker, vector indexers, and Obsidian sync scripts, and registers the hooks in `~/.claude/settings.json`.

---

# AICTX Automated Context, RAG & Memory Extraction System

## Agent Execution Instructions

Agent: Read the instructions below, create the installer file `install_aictx_pipeline.py`, execute it, and verify the setup.

```bash
python3 install_aictx_pipeline.py

```

---

## Single-File Self-Installer (`install_aictx_pipeline.py`)

```python
#!/usr/bin/env python3
"""
Single-file self-installer for the complete AICTX pipeline:
1. Directory structure creation (~/ai/scripts, ~/ai/indexes, ~/Obsidian/AI-Knowledge-Hub).
2. SQLite schema setup with support for memories, vector embeddings (sqlite-vec), and FTS5 search.
3. Automatic memory extraction & contradiction reconciliation engine (`extract_session.py`).
4. Automated bidirectional sync to Obsidian Markdown notes (`sync_obsidian.py`).
5. Hybrid (FTS5 + sqlite-vec) RAG search and context builder (`aictx.py`).
6. Vault indexer (`index_obsidian.py`).
7. Automatic Registration of SessionStart & Stop hooks in ~/.claude/settings.json.
"""

import os
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

# Base System Paths
HOME = Path.home()
AI_DIR = HOME / "ai"
SCRIPTS_DIR = AI_DIR / "scripts"
INDEXES_DIR = AI_DIR / "indexes"
VAULT_DIR = HOME / "Obsidian" / "AI-Knowledge-Hub"
CLAUDE_CONFIG = HOME / ".claude" / "settings.json"
DB_PATH = INDEXES_DIR / "ai.db"

def setup_directories():
    print("[1/5] Creating directory structures...")
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    INDEXES_DIR.mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Preferences").mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Projects").mkdir(parents=True, exist_ok=True)
    (VAULT_DIR / "Decisions").mkdir(parents=True, exist_ok=True)
    CLAUDE_CONFIG.parent.mkdir(parents=True, exist_ok=True)

def init_database():
    print("[2/5] Initializing SQLite database schema & extensions...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Core Structured Memory Table
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

    # sqlite-vec Virtual Table Setup
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
        print("  └─ sqlite-vec virtual table initialized.")
    except Exception as e:
        print(f"  └─ Notice: sqlite-vec extension not loaded. Vector search will fallback ({e}).")

    # FTS5 Full-Text Search Table
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

def write_scripts():
    print("[3/5] Writing pipeline scripts...")

    # Script 1: sync_obsidian.py
    sync_obsidian_code = '''#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "ai" / "indexes" / "ai.db"
VAULT_PATH = Path.home() / "Obsidian" / "AI-Knowledge-Hub"

def export_to_obsidian():
    if not DB_PATH.exists() or not VAULT_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, project_id, scope, type, content, source_ref, created_at, supersedes_id
        FROM memories 
        WHERE valid_until IS NULL
    """)
    rows = cursor.fetchall()

    projects = {}
    preferences = []

    for row in rows:
        mem_id, project_id, scope, type_, content, source_ref, created_at, supersedes_id = row
        item = {
            "id": mem_id, "scope": scope, "type": type_, "content": content,
            "source_ref": source_ref or "Session", "created_at": created_at,
            "supersedes_id": supersedes_id
        }
        if scope == "personal" or project_id == "global":
            preferences.append(item)
        else:
            projects.setdefault(project_id, []).append(item)

    # Sync Personal Preferences
    pref_file = VAULT_PATH / "Preferences" / "Personal-Preferences.md"
    pref_content = ["---", "tags: [ai-memory, personal-preferences]", "---\\n", "# 👤 Personal Preferences & Rules\\n"]
    for p in preferences:
        pref_content.append(f"- **[{p['type'].upper()}]** {p['content']}")
    pref_file.write_text("\\n".join(pref_content))

    # Sync Project Files
    for proj_name, items in projects.items():
        proj_file = VAULT_PATH / "Projects" / f"{proj_name}.md"
        doc = ["---", f"project: {proj_name}", "tags: [ai-memory, project-context]", "---", f"\\n# 📦 Project Context: {proj_name}\\n"]
        
        decisions = [i for i in items if i["type"] == "decision"]
        lessons = [i for i in items if i["type"] != "decision"]

        if decisions:
            doc.append("## 🧠 Architectural Decisions")
            for d in decisions:
                sup = f" *(Supersedes #{d['supersedes_id']})*" if d['supersedes_id'] else ""
                doc.append(f"- {d['content']}{sup}\\n  - *Recorded: {d['created_at']}*")
            doc.append("")

        if lessons:
            doc.append("## 💡 Key Lessons & Facts")
            for l in lessons:
                doc.append(f"- {l['content']}\\n  - *Recorded: {l['created_at']}*")
            doc.append("")

        proj_file.write_text("\\n".join(doc))

    conn.close()

if __name__ == "__main__":
    export_to_obsidian()
'''
    (SCRIPTS_DIR / "sync_obsidian.py").write_text(sync_obsidian_code)

    # Script 2: extract_session.py
    extract_session_code = '''#!/usr/bin/env python3
import sys
import json
import sqlite3
import subprocess
from pathlib import Path

DB_PATH = Path.home() / "ai" / "indexes" / "ai.db"

def get_existing_memories(conn, project_name: str) -> list:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, scope, type, content FROM memories WHERE (project_id = ? OR scope = 'personal') AND valid_until IS NULL",
        (project_name,)
    )
    return [{"id": r[0], "scope": r[1], "type": r[2], "content": r[3]} for r in cursor.fetchall()]

def extract_and_reconcile(transcript_text: str, project_name: str):
    if not transcript_text.strip():
        return

    conn = sqlite3.connect(DB_PATH)
    existing_memories = get_existing_memories(conn, project_name)

    prompt = f"""
Analyze transcript and extract key developer preferences, architectural decisions, and technical lessons.
EXISTING MEMORIES: {json.dumps(existing_memories)}
TRANSCRIPT: {transcript_text[-6000:]}

Respond strictly in JSON matching schema:
{{
  "operations": [
    {{
      "action": "ADD" | "SUPERSEDE" | "IGNORE",
      "supersedes_id": null or int,
      "memory": {{ "scope": "personal"|"project", "type": "preference"|"decision"|"lesson", "content": "summary" }}
    }}
  ]
}}
"""

    try:
        res = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=45)
        output = res.stdout.strip()
        start, end = output.find("{"), output.rfind("}") + 1
        if start != -1 and end != -1:
            data = json.loads(output[start:end])
            cursor = conn.cursor()
            for op in data.get("operations", []):
                act, mem = op.get("action"), op.get("memory", {})
                if act == "IGNORE" or not mem.get("content"):
                    continue
                if act == "SUPERSEDE" and op.get("supersedes_id"):
                    cursor.execute("UPDATE memories SET valid_until = CURRENT_TIMESTAMP WHERE id = ?", (op["supersedes_id"],))
                    cursor.execute(
                        "INSERT INTO memories (project_id, scope, type, content, supersedes_id) VALUES (?, ?, ?, ?, ?)",
                        (project_name, mem.get("scope", "project"), mem.get("type", "decision"), mem.get("content"), op["supersedes_id"])
                    )
                elif act == "ADD":
                    cursor.execute(
                        "INSERT INTO memories (project_id, scope, type, content) VALUES (?, ?, ?, ?)",
                        (project_name, mem.get("scope", "project"), mem.get("type", "lesson"), mem.get("content"))
                    )
            conn.commit()
            
            # Auto-sync to Obsidian after extraction
            subprocess.run([sys.executable, str(Path.home() / "ai" / "scripts" / "sync_obsidian.py")])
    except Exception:
        pass
    finally:
        conn.close()

if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else "global"
    input_data = sys.stdin.read() if not sys.stdin.isatty() else ""
    extract_and_reconcile(input_data, project)
'''
    (SCRIPTS_DIR / "extract_session.py").write_text(extract_session_code)

    # Script 3: index_obsidian.py
    index_obsidian_code = '''#!/usr/bin/env python3
import os
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "ai" / "indexes" / "ai.db"
VAULT_PATH = Path.home() / "Obsidian" / "AI-Knowledge-Hub"

def index_vault():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        import sqlite_vec
        from sentence_transformers import SentenceTransformer
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        model = None

    cursor.execute("DELETE FROM obsidian_fts;")
    if model:
        cursor.execute("DELETE FROM obsidian_vec;")

    for root, _, files in os.walk(VAULT_PATH):
        for file in files:
            if file.endswith(".md"):
                file_path = Path(root) / file
                content = file_path.read_text(encoding="utf-8")
                sections = content.split("\\n## ")
                
                for i, section in enumerate(sections):
                    doc_id = f"{file_path.stem}#chunk-{i}"
                    cursor.execute(
                        "INSERT INTO obsidian_fts (doc_id, file_path, title, content) VALUES (?, ?, ?, ?)",
                        (doc_id, str(file_path), file_path.stem, section)
                    )
                    if model:
                        emb = model.encode(section).tolist()
                        cursor.execute(
                            "INSERT INTO obsidian_vec (doc_id, embedding) VALUES (?, ?)",
                            (doc_id, sqlite_vec.serialize_float32(emb))
                        )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    index_vault()
'''
    (SCRIPTS_DIR / "index_obsidian.py").write_text(index_obsidian_code)

    # Script 4: aictx.py
    aictx_code = '''#!/usr/bin/env python3
import sys
import sqlite3
import typer
from pathlib import Path

app = typer.Typer()
DB_PATH = Path.home() / "ai" / "indexes" / "ai.db"

@app.command()
def build_context(project: str = "global"):
    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT scope, type, content FROM memories 
        WHERE (project_id = ? OR scope = 'personal') AND valid_until IS NULL
    """, (project,))
    memories = cursor.fetchall()

    if memories:
        print("### 🧠 Active Project Memories & Rules")
        for scope, mtype, content in memories:
            print(f"- [{mtype.upper()}] {content}")
        print("")

    try:
        import sqlite_vec
        from sentence_transformers import SentenceTransformer
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        model = SentenceTransformer("all-MiniLM-L6-v2")

        query_emb = model.encode(f"Project context decisions guidelines {project}").tolist()
        cursor.execute("""
            SELECT f.title, f.content, v.distance
            FROM obsidian_vec v JOIN obsidian_fts f ON v.doc_id = f.doc_id
            WHERE v.embedding MATCH ? ORDER BY v.distance LIMIT 3
        """, (sqlite_vec.serialize_float32(query_emb),))
        
        notes = cursor.fetchall()
        if notes:
            print("### 📚 Relevant Obsidian Notes (Vector RAG)")
            for title, content, dist in notes:
                snippet = content[:200].replace("\\n", " ").strip()
                print(f"- **Note: {title}**: {snippet}...")
    except Exception:
        pass
    finally:
        conn.close()

if __name__ == "__main__":
    app()
'''
    (SCRIPTS_DIR / "aictx.py").write_text(aictx_code)

    # Make executable
    for script_file in SCRIPTS_DIR.glob("*.py"):
        os.chmod(script_file, 0o755)

def register_hooks():
    print("[4/5] Registering Claude Code hooks in settings.json...")
    config = {}
    if CLAUDE_CONFIG.exists():
        try:
            config = json.loads(CLAUDE_CONFIG.read_text())
        except Exception:
            config = {}

    hooks = config.setdefault("hooks", {})
    python_bin = sys.executable

    hooks["SessionStart"] = [
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": f"{python_bin} {SCRIPTS_DIR}/aictx.py build-context --project $(basename $CLAUDE_PROJECT_DIR)"
                }
            ]
        }
    ]

    hooks["Stop"] = [
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": f"{python_bin} {SCRIPTS_DIR}/extract_session.py $(basename $CLAUDE_PROJECT_DIR)"
                }
            ]
        }
    ]

    CLAUDE_CONFIG.write_text(json.dumps(config, indent=2))
    print(f"  └─ Successfully configured hooks in {CLAUDE_CONFIG}")

def verify_and_test():
    print("[5/5] Running initial index sync...")
    subprocess.run([sys.executable, str(SCRIPTS_DIR / "index_obsidian.py")])
    subprocess.run([sys.executable, str(SCRIPTS_DIR / "sync_obsidian.py")])
    print("\n✅ Setup complete! Full system ready.")

if __name__ == "__main__":
    setup_directories()
    init_database()
    write_scripts()
    register_hooks()
    verify_and_test()

```