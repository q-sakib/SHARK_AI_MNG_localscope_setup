#!/usr/bin/env python3
"""
Reads a session transcript (stdin, or a file path as argv[2]) and asks
the `claude` CLI to extract durable preferences/decisions/lessons from
it, reconciling against what's already stored (ADD / SUPERSEDE /
IGNORE). Meant to be wired up as a Claude Code "Stop" hook so memory
capture happens automatically at the end of a session -- see
../hooks/HOOKS_SETUP.md for how to wire that up (that step has to be
done on the real machine; it can't be done from this sandboxed
session).

This is the one script that costs an extra `claude -p` call each time
it runs, since it needs an LLM to do the extraction/reconciliation.
"""
import json
import subprocess
import sys
from pathlib import Path
from _common import DB_PATH, PROJECT_NAME
import sqlite3


def get_existing_memories(conn, project_name):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, scope, type, content FROM memories WHERE (project_id = ? OR scope = 'personal') AND valid_until IS NULL",
        (project_name,),
    )
    return [{"id": r[0], "scope": r[1], "type": r[2], "content": r[3]} for r in cursor.fetchall()]


def extract_and_reconcile(transcript_text, project_name):
    if not transcript_text.strip():
        print("Empty transcript, nothing to extract.")
        return
    if not DB_PATH.exists():
        print(f"No database at {DB_PATH} -- run install.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    existing_memories = get_existing_memories(conn, project_name)

    prompt = f"""Analyze this transcript and extract key developer preferences, architectural decisions, and technical lessons worth remembering long-term.

EXISTING MEMORIES: {json.dumps(existing_memories)}
TRANSCRIPT: {transcript_text[-6000:]}

Respond with ONLY JSON matching this schema, nothing else:
{{
  "operations": [
    {{
      "action": "ADD" | "SUPERSEDE" | "IGNORE",
      "supersedes_id": null or int,
      "memory": {{"scope": "personal"|"project", "type": "preference"|"decision"|"lesson"|"fact", "content": "one-line summary"}}
    }}
  ]
}}"""

    try:
        res = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=60)
        output = res.stdout.strip()
        start, end = output.find("{"), output.rfind("}") + 1
        if start == -1 or end == -1:
            print("No JSON found in claude's response; nothing recorded.")
            return
        data = json.loads(output[start:end])
        cursor = conn.cursor()
        n_added = 0
        for op in data.get("operations", []):
            act, mem = op.get("action"), op.get("memory", {})
            if act == "IGNORE" or not mem.get("content"):
                continue
            if act == "SUPERSEDE" and op.get("supersedes_id"):
                cursor.execute("UPDATE memories SET valid_until = CURRENT_TIMESTAMP WHERE id = ?", (op["supersedes_id"],))
                cursor.execute(
                    "INSERT INTO memories (project_id, scope, type, content, supersedes_id) VALUES (?, ?, ?, ?, ?)",
                    (project_name, mem.get("scope", "project"), mem.get("type", "decision"), mem.get("content"), op["supersedes_id"]),
                )
                n_added += 1
            elif act == "ADD":
                cursor.execute(
                    "INSERT INTO memories (project_id, scope, type, content) VALUES (?, ?, ?, ?)",
                    (project_name, mem.get("scope", "project"), mem.get("type", "lesson"), mem.get("content")),
                )
                n_added += 1
        conn.commit()
        print(f"Recorded {n_added} memory operation(s).")
        if n_added:
            subprocess.run([sys.executable, str(Path(__file__).parent / "sync_obsidian.py")])
    except FileNotFoundError:
        print("`claude` CLI not found on PATH -- skipping extraction.")
    except Exception as e:
        print(f"Extraction failed ({type(e).__name__}: {e}); nothing recorded.")
    finally:
        conn.close()


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else PROJECT_NAME
    input_data = sys.stdin.read() if not sys.stdin.isatty() else ""
    extract_and_reconcile(input_data, project)
