#!/usr/bin/env python3
"""
Safely merge the AICTX SessionStart/Stop hooks into a Claude Code
settings.json, without clobbering any settings or hooks already there.

- Appends to hooks.SessionStart / hooks.Stop (doesn't replace them).
- Skips if our command is already present (safe to re-run).
- Backs up the existing file before writing, if one exists.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from _common import BASE

SNIPPET_PATH = BASE / "hooks" / "claude_hooks_snippet.json"


def load_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        backup = path.with_suffix(path.suffix + f".invalid-{int(time.time())}.bak")
        shutil.copy2(path, backup)
        print(f"  ! existing file wasn't valid JSON ({e}); backed up to {backup} and starting fresh")
        return {}


def command_strings(hook_list):
    out = set()
    for entry in hook_list or []:
        for h in entry.get("hooks", []):
            if "command" in h:
                out.add(h["command"])
    return out


def merge(settings_path: Path, snippet_path: Path):
    snippet = json.loads(snippet_path.read_text())
    existing = load_json(settings_path)
    existing.setdefault("hooks", {})

    changed = False
    for hook_type, new_entries in snippet.get("hooks", {}).items():
        existing_list = existing["hooks"].setdefault(hook_type, [])
        already = command_strings(existing_list)
        for entry in new_entries:
            new_cmds = command_strings([entry])
            if new_cmds & already:
                print(f"  - {hook_type}: already present, skipping")
                continue
            existing_list.append(entry)
            changed = True
            print(f"  - {hook_type}: added")

    if not changed:
        print("Nothing to do -- hooks already installed.")
        return False

    if settings_path.exists():
        backup = settings_path.with_suffix(settings_path.suffix + f".bak-{int(time.time())}")
        shutil.copy2(settings_path, backup)
        print(f"  (backed up previous settings to {backup})")

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(existing, indent=2) + "\n")
    print(f"Wrote {settings_path}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings-path", default=str(Path.home() / ".claude" / "settings.json"))
    parser.add_argument("--snippet-path", default=str(SNIPPET_PATH))
    args = parser.parse_args()
    merge(Path(args.settings_path), Path(args.snippet_path))
