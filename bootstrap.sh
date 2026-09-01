#!/usr/bin/env bash
# One-command AICTX setup. Run this in a real Terminal window on this
# Mac (not through a Cowork/cloud session -- see README.md for why:
# it needs to reach ~/.claude and your system Python, which a sandboxed
# session can't touch).
#
# Usage:
#   bash bootstrap.sh                     # core setup + hook wiring
#   bash bootstrap.sh --with-semantic     # also installs sqlite-vec + sentence-transformers (in a .venv)
#   bash bootstrap.sh --no-hooks          # skip touching ~/.claude/settings.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

WITH_SEMANTIC=0
WITH_HOOKS=1
for arg in "$@"; do
  case "$arg" in
    --with-semantic) WITH_SEMANTIC=1 ;;
    --no-hooks) WITH_HOOKS=0 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

echo "== AICTX bootstrap =="
echo "Project folder: $SCRIPT_DIR"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found on PATH. Install Python 3 first (e.g. 'brew install python3'), then re-run this script." >&2
  exit 1
fi
echo "[ok] python3 found: $(command -v python3) ($(python3 --version))"

echo
echo "-- 1/4: database + folder schema --"
python3 scripts/install.py

echo
echo "-- 2/4: Claude Code hooks --"
if [ "$WITH_HOOKS" -eq 1 ]; then
  python3 scripts/merge_hooks.py
else
  echo "  (skipped: --no-hooks)"
fi

# Which python to use for the verify pass at the end -- the venv's if
# we just built one (so status/index reflect what actually got
# installed), otherwise plain system python3.
VERIFY_PYTHON="python3"

echo
echo "-- 3/4: optional semantic search deps --"
if [ "$WITH_SEMANTIC" -eq 1 ]; then
  VENV_DIR="$SCRIPT_DIR/.venv"
  # macOS system/Homebrew Python refuses "pip install" system-wide
  # (PEP 668, "externally-managed-environment"). A venv sidesteps that
  # cleanly instead of forcing it with --break-system-packages.
  if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating virtual environment at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
  fi
  echo "  Installing sqlite-vec + sentence-transformers into .venv (pulls in PyTorch, may take a few minutes)..."
  "$VENV_DIR/bin/pip" install --upgrade pip --quiet
  "$VENV_DIR/bin/pip" install sqlite-vec sentence-transformers
  VERIFY_PYTHON="$VENV_DIR/bin/python3"
  echo "  Installed. Use $VENV_DIR/bin/python3 instead of plain python3 to get"
  echo "  semantic search from aictx.py from now on (see README.md)."
else
  echo "  (skipped -- re-run with --with-semantic to enable vector/semantic search)"
  echo "  Full-text search (aictx.py note-search) already works without this."
fi

echo
echo "-- 4/4: verifying (using $VERIFY_PYTHON) --"
"$VERIFY_PYTHON" scripts/aictx.py status
"$VERIFY_PYTHON" scripts/aictx.py sync
"$VERIFY_PYTHON" scripts/aictx.py index

echo
echo "== Done =="
if [ "$WITH_HOOKS" -eq 1 ]; then
  echo "Open a new terminal and run 'claude' in any project -- you should see"
  echo "an 'Active Project Memories & Rules' block print at session start."
fi
echo "Day-to-day: $VERIFY_PYTHON $SCRIPT_DIR/scripts/aictx.py {status|memory-add|memory-search|note-search|build-context|sync|index}"
