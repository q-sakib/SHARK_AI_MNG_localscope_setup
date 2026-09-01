#!/usr/bin/env python3
"""Export the memories table to human-readable Obsidian-style Markdown
notes under obsidian/Preferences and obsidian/Projects. Run this after
adding memories so the notes stay in sync with the database."""
import sqlite3
from _common import DB_PATH, VAULT_PATH


def export_to_obsidian():
    if not DB_PATH.exists():
        print(f"No database at {DB_PATH} -- run install.py first.")
        return
    VAULT_PATH.mkdir(parents=True, exist_ok=True)
    (VAULT_PATH / "Preferences").mkdir(parents=True, exist_ok=True)
    (VAULT_PATH / "Projects").mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, project_id, scope, type, content, source_ref, created_at, supersedes_id
        FROM memories
        WHERE valid_until IS NULL
        ORDER BY created_at
    """)
    rows = cursor.fetchall()
    conn.close()

    projects = {}
    preferences = []
    for row in rows:
        mem_id, project_id, scope, type_, content, source_ref, created_at, supersedes_id = row
        item = {
            "id": mem_id, "scope": scope, "type": type_, "content": content,
            "source_ref": source_ref or "Session", "created_at": created_at,
            "supersedes_id": supersedes_id,
        }
        if scope == "personal" or project_id == "global":
            preferences.append(item)
        else:
            projects.setdefault(project_id, []).append(item)

    pref_file = VAULT_PATH / "Preferences" / "Personal-Preferences.md"
    pref_content = ["---", "tags: [ai-memory, personal-preferences]", "---", "", "# Personal Preferences & Rules", ""]
    for p in preferences:
        pref_content.append(f"- **[{p['type'].upper()}]** {p['content']}")
    pref_file.write_text("\n".join(pref_content) + "\n")

    for proj_name, items in projects.items():
        proj_file = VAULT_PATH / "Projects" / f"{proj_name}.md"
        doc = ["---", f"project: {proj_name}", "tags: [ai-memory, project-context]", "---", "", f"# Project Context: {proj_name}", ""]
        decisions = [i for i in items if i["type"] == "decision"]
        lessons = [i for i in items if i["type"] != "decision"]
        if decisions:
            doc.append("## Architectural Decisions")
            for d in decisions:
                sup = f" (Supersedes #{d['supersedes_id']})" if d["supersedes_id"] else ""
                doc.append(f"- {d['content']}{sup}\n  - Recorded: {d['created_at']}")
            doc.append("")
        if lessons:
            doc.append("## Key Lessons & Facts")
            for l in lessons:
                doc.append(f"- {l['content']}\n  - Recorded: {l['created_at']}")
            doc.append("")
        proj_file.write_text("\n".join(doc) + "\n")

    print(f"Synced {len(preferences)} personal preference(s) and {len(projects)} project file(s) to {VAULT_PATH}")


if __name__ == "__main__":
    export_to_obsidian()
