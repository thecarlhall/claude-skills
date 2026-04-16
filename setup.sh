#!/usr/bin/env bash
# setup.sh — symlink your Claude Code config onto a new machine
#
# Repo layout this script expects:
#   claude-config/
#   ├── setup.sh             ← this file
#   ├── CLAUDE.md            → ~/.claude/CLAUDE.md
#   ├── settings.json        → ~/.claude/settings.json
#   ├── claude.json          → ~/.claude.json  (MCP servers, global settings)
#   ├── skills/
#   │   └── my-skill/
#   │       └── SKILL.md     → ~/.claude/skills/my-skill/SKILL.md
#   └── commands/
#       └── my-command.md    → ~/.claude/commands/my-command.md

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

# ── helpers ──────────────────────────────────────────────────────────────────

info()    { echo "  [info]  $*"; }
success() { echo "  [ok]    $*"; }
warn()    { echo "  [warn]  $*"; }

symlink() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"

  if [[ -L "$dst" ]]; then
    local current_target
    current_target="$(readlink "$dst")"
    if [[ "$current_target" == "$src" ]]; then
      info "already linked: $dst"
      return
    else
      warn "replacing existing symlink: $dst → $current_target"
      rm "$dst"
    fi
  elif [[ -e "$dst" ]]; then
    local backup="${dst}.bak.$(date +%Y%m%d%H%M%S)"
    warn "backing up existing file: $dst → $backup"
    mv "$dst" "$backup"
  fi

  ln -s "$src" "$dst"
  success "$dst → $src"
}

# ── main setup ────────────────────────────────────────────────────────────────

echo
echo "Claude Code dotfiles setup"
echo "Repo: $REPO_DIR"
echo "────────────────────────────────────────"

mkdir -p "$CLAUDE_DIR"

# CLAUDE.md — personal preferences loaded in every session
if [[ -f "$REPO_DIR/CLAUDE.md" ]]; then
  symlink "$REPO_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
fi

# settings.json — tool permissions, model, env vars, etc.
if [[ -f "$REPO_DIR/settings.json" ]]; then
  symlink "$REPO_DIR/settings.json" "$CLAUDE_DIR/settings.json"
fi

# ~/.claude.json — global MCP server definitions
if [[ -f "$REPO_DIR/claude.json" ]]; then
  symlink "$REPO_DIR/claude.json" "$HOME/.claude.json"
fi

# skills — each subdirectory becomes a skill
SKILLS_SRC="$REPO_DIR/skills"
SKILLS_DST="$CLAUDE_DIR/skills"
if [[ -d "$SKILLS_SRC" ]]; then
  mkdir -p "$SKILLS_DST"
  for skill_dir in "$SKILLS_SRC"/*/; do
    [[ -d "$skill_dir" ]] || continue
    skill_name="$(basename "$skill_dir")"
    symlink "$skill_dir" "$SKILLS_DST/$skill_name"
  done
fi

# commands — each .md file becomes a /slash-command (legacy, still works)
COMMANDS_SRC="$REPO_DIR/commands"
COMMANDS_DST="$CLAUDE_DIR/commands"
if [[ -d "$COMMANDS_SRC" ]]; then
  mkdir -p "$COMMANDS_DST"
  for cmd_file in "$COMMANDS_SRC"/*.md; do
    [[ -f "$cmd_file" ]] || continue
    cmd_name="$(basename "$cmd_file")"
    symlink "$cmd_file" "$COMMANDS_DST/$cmd_name"
  done
fi

echo "────────────────────────────────────────"
echo "Done. Start a new Claude Code session to pick up changes."
echo

# Remind about secrets — never committed
if [[ ! -f "$REPO_DIR/.env" ]]; then
  echo "  [note]  No .env found. If your MCP servers need API keys, copy"
  echo "          .env.example → .env and fill in your secrets."
  echo
fi
