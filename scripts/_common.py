"""Shared paths for the AICTX scripts. Everything is relative to this
project folder (SHARK_AI_MNG) rather than the machine's home directory,
so the whole system is self-contained and portable."""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INDEXES_DIR = BASE / "indexes"
DB_PATH = INDEXES_DIR / "ai.db"
VAULT_PATH = BASE / "obsidian"
SESSIONS_DIR = BASE / "sessions"
PROJECT_NAME = BASE.name  # "SHARK_AI_MNG" -- used as the default project_id
