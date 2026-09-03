#!/usr/bin/env bash
# SHARK AI MNG — Master Bootstrap v2.0
# Installs: caveman, ai helper, Claude skills/agents/commands/hooks
# Safe: idempotent, never overwrites existing ~/.claude/CLAUDE.md
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"
BIN_DIR="${HOME}/.local/bin"
BACKUP_ROOT="${HOME}/.claude-backups"
VERSION="2.0.0"

log()  { printf '\033[1;36m[SHARK]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

cmd_exists() { command -v "$1" >/dev/null 2>&1; }

backup_file() {
  local f="$1"
  [[ -e "$f" ]] || return 0
  local stamp; stamp="$(date +%Y%m%d-%H%M%S)"
  mkdir -p "${BACKUP_ROOT}/${stamp}"
  cp -R "$f" "${BACKUP_ROOT}/${stamp}/"
  log "Backed up $f → ${BACKUP_ROOT}/${stamp}/"
}

link_dir() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -L "$dst" ]]; then
    rm "$dst"
  elif [[ -d "$dst" ]]; then
    backup_file "$dst"
    rm -rf "$dst"
  fi
  ln -sf "$src" "$dst"
  ok "Linked: $dst → $src"
}

copy_if_missing() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" ]]; then
    warn "Keeping existing: $dst"
  else
    cp "$src" "$dst"
    ok "Created: $dst"
  fi
}

log "SHARK AI MNG Bootstrap v${VERSION}"

[[ "$(uname -s)" == "Darwin" ]] || warn "Optimized for macOS. Continuing anyway."
cmd_exists brew || die "Homebrew required: https://brew.sh"

# ── 1. CLI tools ──────────────────────────────────────────────────────────────
log "Installing CLI tools..."
for tool in jq yq ripgrep fd fzf bat eza git-delta just shellcheck; do
  if ! brew list --formula "$tool" >/dev/null 2>&1; then
    brew install "$tool" && ok "Installed: $tool"
  else
    ok "Already installed: $tool"
  fi
done

for tool in gitleaks trivy; do
  brew list --formula "$tool" >/dev/null 2>&1 || brew install "$tool" 2>/dev/null || warn "Optional: $tool unavailable"
done

# ── 2. Ollama check ───────────────────────────────────────────────────────────
if cmd_exists ollama; then
  log "Ollama: $(ollama --version 2>/dev/null || echo 'installed')"
  log "Installed models:"
  ollama list 2>/dev/null || true
  if ! ollama list 2>/dev/null | grep -q 'qwen2.5-coder:1.5b'; then
    warn "qwen2.5-coder:1.5b not found. Run: ollama pull qwen2.5-coder:1.5b"
  fi
else
  warn "Ollama not installed. caveman uses mechanical fallback. Install: https://ollama.com"
fi

# ── 3. Install bin tools ─────────────────────────────────────────────────────
log "Installing bin tools to ${BIN_DIR}..."
mkdir -p "$BIN_DIR"

cp "${SCRIPT_DIR}/bin/ai" "${BIN_DIR}/ai"
chmod +x "${BIN_DIR}/ai"
ok "Installed: ${BIN_DIR}/ai"

cp "${SCRIPT_DIR}/bin/caveman" "${BIN_DIR}/caveman"
chmod +x "${BIN_DIR}/caveman"
ok "Installed: ${BIN_DIR}/caveman"

# ── 4. PATH in shell config ───────────────────────────────────────────────────
ZSHRC="${HOME}/.zshrc"
if [[ -f "$ZSHRC" ]] && ! grep -q 'SHARK_AI_MNG' "$ZSHRC"; then
  cat >> "$ZSHRC" <<'ZSHEOF'

# SHARK_AI_MNG
export PATH="${HOME}/.local/bin:${PATH}"
ZSHEOF
  ok "Added ~/.local/bin to PATH in ~/.zshrc"
fi

# ── 5. Claude dirs ────────────────────────────────────────────────────────────
log "Linking Claude dirs..."
mkdir -p "$CLAUDE_DIR"

for d in skills agents commands hooks; do
  link_dir "${SCRIPT_DIR}/${d}" "${CLAUDE_DIR}/${d}"
done

mkdir -p "${CLAUDE_DIR}/ai"
for f in "${SCRIPT_DIR}/ai/"*.md; do
  [[ -e "$f" ]] && copy_if_missing "$f" "${CLAUDE_DIR}/ai/$(basename "$f")"
done
for sub in workflows evaluations/cases evaluations/results prompts logs cache models backups; do
  mkdir -p "${CLAUDE_DIR}/ai/${sub}"
done

GLOBAL_CLAUDE="${CLAUDE_DIR}/CLAUDE.md"
if [[ -f "$GLOBAL_CLAUDE" ]]; then
  warn "Keeping existing global CLAUDE.md: ${GLOBAL_CLAUDE}"
  warn "Review ${SCRIPT_DIR}/CLAUDE.md and merge manually if needed."
else
  cp "${SCRIPT_DIR}/CLAUDE.md" "$GLOBAL_CLAUDE"
  ok "Created global CLAUDE.md"
fi

# ── 6. Claude settings ────────────────────────────────────────────────────────
SETTINGS="${CLAUDE_DIR}/settings.json"
if [[ ! -f "$SETTINGS" ]]; then
  echo '{"model":"claude-sonnet-4-6"}' > "$SETTINGS"
  ok "Created ${SETTINGS}"
else
  ok "Keeping existing ${SETTINGS}"
fi

PROJECT_SETTINGS="${SCRIPT_DIR}/.claude/settings.json"
mkdir -p "${SCRIPT_DIR}/.claude"
cat > "$PROJECT_SETTINGS" <<'JSON'
{
  "permissions": {
    "allow": [
      "Bash(ls:*)",
      "Bash(find:*)",
      "Bash(cat:*)",
      "Bash(ollama:*)",
      "Bash(caveman:*)",
      "Bash(ai:*)",
      "Bash(git status)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Read(**)"
    ]
  }
}
JSON
ok "Updated project .claude/settings.json"

# ── 7. projects/ dir ──────────────────────────────────────────────────────────
mkdir -p "${SCRIPT_DIR}/projects"
[[ -f "${SCRIPT_DIR}/projects/.gitkeep" ]] || touch "${SCRIPT_DIR}/projects/.gitkeep"
ok "projects/ directory ready"

# ── 8. Validate ───────────────────────────────────────────────────────────────
log ""
log "VALIDATION"
for x in caveman ai claude ollama jq rg fd fzf; do
  cmd_exists "$x" && ok "$x" || warn "$x not in PATH (run: source ~/.zshrc first)"
done

cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHARK AI MNG v${VERSION} INSTALLED

Tools:       ${BIN_DIR}/caveman
             ${BIN_DIR}/ai

Claude dirs (symlinked):
             ${CLAUDE_DIR}/skills/
             ${CLAUDE_DIR}/agents/
             ${CLAUDE_DIR}/commands/   ← /cpres available in Claude Code
             ${CLAUDE_DIR}/hooks/

Projects:    ${SCRIPT_DIR}/projects/  ← all new projects go here

Next:
  1. source ~/.zshrc
  2. ai doctor
  3. ai status
  4. claude                           ← type /cpres to compress context
  5. echo "long text" | caveman       ← compress from terminal
  6. ai run qwen2.5-coder:14b         ← local heavy reasoning
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
