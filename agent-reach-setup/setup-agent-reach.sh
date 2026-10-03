#!/usr/bin/env bash
# One-time, user-wide install of Agent Reach (https://github.com/lllTheGodlll/Agent-Reach)
# so Claude Code can use it in every project.
#
#   Local (macOS / Linux):   bash setup-agent-reach.sh
#   Claude Code on the web:  paste this file into the cloud environment's "Setup script"
#
# Safe to re-run: it upgrades everything in place.
#
# Optional environment variables:
#   AGENT_REACH_SOURCE    where to install from (default: your fork on GitHub)
#   AGENT_REACH_CHANNELS  extra channels, e.g. "twitter,reddit" or "all"
#   AGENT_REACH_LANG      skill language, "en" (default) or "zh"
set -euo pipefail

AGENT_REACH_SOURCE="${AGENT_REACH_SOURCE:-git+https://github.com/lllTheGodlll/Agent-Reach}"
AGENT_REACH_LANG="${AGENT_REACH_LANG:-en}"
export AGENT_REACH_LANG
export PATH="$HOME/.local/bin:$PATH"

step() { printf '\n==> %s\n' "$*"; }

# 1. Python tool installer: uv preferred, pipx accepted, otherwise install uv.
step "Checking for uv / pipx"
if command -v uv >/dev/null 2>&1; then
  install_tool() { uv tool install --force --refresh "$@"; }
elif command -v pipx >/dev/null 2>&1; then
  install_tool() { pipx install --force "$@"; }
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
  install_tool() { uv tool install --force --refresh "$@"; }
fi

# 2. The agent-reach CLI, plus yt-dlp as its own tool so the `yt-dlp` command is on PATH.
#    (git+https is used instead of the .zip archive URL because some networks block archive downloads.)
step "Installing agent-reach from $AGENT_REACH_SOURCE"
install_tool "$AGENT_REACH_SOURCE"
step "Installing yt-dlp"
install_tool "yt-dlp[default]"

# Agent Reach only installs its skill into skill folders that already exist.
mkdir -p "$HOME/.claude/skills"

# 3. Core setup: gh CLI + Node.js check, mcporter + Exa search. Run outside any project folder.
step "Running agent-reach install"
cd "${TMPDIR:-/tmp}"
if [ -n "${AGENT_REACH_CHANNELS:-}" ]; then
  agent-reach install --env=auto --system --channels="$AGENT_REACH_CHANNELS" \
    || echo "!! agent-reach install reported problems; see 'agent-reach doctor' below"
else
  agent-reach install --env=auto --system \
    || echo "!! agent-reach install reported problems; see 'agent-reach doctor' below"
fi

# 4. yt-dlp needs a JS runtime for YouTube; point it at Node (what `agent-reach doctor` asks for).
if command -v node >/dev/null 2>&1; then
  mkdir -p "$HOME/.config/yt-dlp"
  grep -qxF -- '--js-runtimes node' "$HOME/.config/yt-dlp/config" 2>/dev/null \
    || printf '%s\n' '--js-runtimes node' >> "$HOME/.config/yt-dlp/config"
fi

# 5. Refresh the skill so re-runs pick up new versions and the chosen language
#    (a plain install keeps an existing SKILL.md untouched).
step "Installing the Agent Reach skill for Claude Code (language: $AGENT_REACH_LANG)"
agent-reach skill --uninstall >/dev/null 2>&1 || true
agent-reach skill --install

step "Status"
agent-reach doctor || true
