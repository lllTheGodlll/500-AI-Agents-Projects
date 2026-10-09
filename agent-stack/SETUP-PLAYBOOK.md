# Agent stack setup playbook

**For the agent running this:** you are setting up one shared memory layer for Claude Code,
Codex, Antigravity CLI (agy), Hermes Agent and Ollama on the user's own computer. The design and
the reasons are in [PLAN.md](PLAN.md); read it first. This file is the procedure.

How to start (the user says one of these):

- Claude Code (recommended), from a clone of this repo: `Read agent-stack/SETUP-PLAYBOOK.md and run it. Ask me the decisions first.`
- Any other agent: the same sentence works. Codex, agy and Hermes can run every shell step here.
  They cannot show multiple-choice questions, so ask the decisions in plain text.
- After Claude Code finished, each other agent runs its own section of [Self-checks](#11-self-checks-for-each-agent).

## 0. Rules for the agent running this

1. **Back up before you change anything** (Phase 1). Never delete user data. Stopping a service is fine; deleting its data is not.
2. **Ask before** each step marked **ASK**, before anything destructive, and before any step that sends data off the machine.
3. **Check, then do, then verify.** Every step is idempotent: if the check shows it is already done, skip it. If a verify step fails, stop that phase, report what you saw, and propose a fix. Do not improvise around it.
4. **Never paste secrets into chat** or into files other than the ones named here. API keys go into `chmod 600` files.
5. **Versions.** The steps were verified against: Claude Code 2.1.295, Codex 0.162.0, agy 1.3.2, Hermes v2026.9.24, Ollama 0.40.2, codebase-memory-mcp 0.11.0, agentmemory 0.9.30, graphifyy 0.9.82, ruflo 3.56.0, claude-obsidian 2.2.0 (commit `32ac5a0`), Hindsight 0.10.3 / coding-agents 0.8.0, OmniRoute 3.8.51. If an installed version is newer, read its changelog for breaking changes before running that tool's steps. Pin versions when installing.
6. **VERIFY** marks behaviour that could not be confirmed in docs or source. Test it as written; if it fails, use the fallback given.
7. Keep a log: append every command you run and its outcome to `~/.agents/stack/SETUP-LOG.md`.
8. Use the repo checkout as `$KIT` (the folder that contains this file), for example `KIT="$(git rev-parse --show-toplevel)/agent-stack"`.

## Decisions (ASK all of these first)

Record the answers in `~/.agents/stack/SETUP-LOG.md` and use them below.

| Var | Question | Default |
|---|---|---|
| `VAULT` | Obsidian vault path (an existing vault is fine) | `~/Vaults/AgentBrain` |
| `CODE_ROOT` | Folder that holds your repos | `~/code` |
| `REPOS` | Repos to index now | the ones you are working on |
| `RUFLO_MODE` | ruflo: `orchestration` (Claude-only MCP, memory off) or `remove` | `orchestration` |
| `HINDSIGHT_MODE` | `off` (remove hooks, stop server, keep data), `vault-brain` (search over the vault, no hooks), or `primary` (use Hindsight instead of agentmemory; then adapt Phase 6 yourself and keep agentmemory's hooks off) | `off` |
| `FALLBACK_MODEL` | Local Ollama model for coding fallback. Ask for RAM/VRAM: ≤16 GB → `qwen3.5` or `gemma4`; 32 GB+ → `qwen3-coder:30b` or `gpt-oss:20b` | by RAM |
| `MEMORY_MODEL` | Small local model for memory summaries | `qwen3:8b` |
| `THRESHOLDS` | Popup at these % of the 5-hour window / weekly window | `85,95` / `90` |
| `TERMINAL` | Terminal app for new agent windows | `Terminal` (or `iTerm`) |
| `FALLBACK_COMBO` | OmniRoute combo name for coding fallback | `coding-fallback` |
| `AUTO_CONTINUE` | Let Claude Code continue by itself after the limit resets | `false` |
| `AM_INJECT` | agentmemory injects memory at session start (`AGENTMEMORY_INJECT_CONTEXT`) | `false` |
| `HOT_INJECT` | claude-obsidian injects `wiki/hot.md` into Claude at session start | `false` |
| `OBSIDIAN_MCP` | Add the Obsidian Local REST API MCP to the agents | `no` (files + skills are enough) |

---

## 1. Preflight, backup, inventory

**1.1 Tools present.** Run and log:

```bash
uname -a; sw_vers 2>/dev/null
for c in claude codex agy hermes ollama omniroute agentmemory codebase-memory-mcp graphify git node npm npx python3 uv docker; do
  printf '%-22s %s\n' "$c" "$(command -v $c || echo MISSING)"; done
claude --version; codex --version; agy --version; hermes --version; ollama --version
codebase-memory-mcp --version; graphify --version 2>/dev/null; node --version; python3 --version
```

Python 3.9+ and git are required. A missing agent is fine: skip its steps.

**1.2 Backup** every config this playbook touches:

```bash
TS=$(date +%Y%m%d-%H%M%S); B=~/.agents/stack/backups/$TS; mkdir -p "$B"; chmod 700 ~/.agents/stack/backups
paths=()
for p in ~/.claude/settings.json ~/.claude.json ~/.claude/CLAUDE.md ~/.claude/skills ~/.claude/agents \
         ~/.codex/config.toml ~/.codex/hooks.json ~/.codex/AGENTS.md ~/.codex/AGENTS.override.md \
         ~/.gemini/config ~/.gemini/AGENTS.md ~/.gemini/GEMINI.md ~/.gemini/antigravity-cli/settings.json \
         ~/.hermes/config.yaml ~/.hermes/SOUL.md ~/.hermes/.env ~/.hermes/hindsight \
         ~/.agentmemory/.env ~/.omniroute/.env ~/.omniroute/server.env ~/.hindsight ~/.ruflo; do
  [ -e "$p" ] && paths+=("${p#/}"); done
tar -czf "$B/configs.tgz" -C / "${paths[@]}" && chmod 600 "$B/configs.tgz" && tar -tzf "$B/configs.tgz" | head -50
```

The archive contains secrets. It stays on this machine.

**1.3 Inventory.** Save the output to `~/.agents/stack/SETUP-LOG.md`:

```bash
claude plugin list; claude mcp list
codex mcp list; ls ~/.codex/*.config.toml 2>/dev/null; cat ~/.codex/hooks.json 2>/dev/null
cat ~/.gemini/config/mcp_config.json 2>/dev/null; cat ~/.gemini/config/hooks.json 2>/dev/null
hermes mcp list; hermes memory status; hermes plugins list
ollama list; omniroute --version; docker ps -a --filter name=hindsight 2>/dev/null
jq '.hooks | keys' ~/.claude/settings.json 2>/dev/null; jq -r '.. | .command? // empty' ~/.claude/settings.json 2>/dev/null
grep -n "Ruflo Integration\|# graphify\|agentmemory" ~/.claude/CLAUDE.md 2>/dev/null
for r in $REPOS; do echo "== $r"; ls "$r"/.claude/settings*.json "$r"/.mcp.json "$r"/.codex 2>/dev/null; done
```

Show the user a short summary: which agents, which memory tools are wired where, and which
duplicates you see (two memory hook sets in one agent, two code-graph hook sets, ruflo hooks).

## 2. Install the glue (agentstack)

```bash
mkdir -p ~/.agents/stack/bin ~/.agents/skills
install -m 755 "$KIT/bin/agentstack" ~/.agents/stack/bin/agentstack
python3 "$KIT/tests/test_agentstack.py"          # must end with OK (24 tests)
```

Write `~/.agents/stack/config.json` from the decisions (keep JSON valid):

```json
{
  "thresholds_5h": [85, 95],
  "thresholds_7d": [90],
  "terminal": "Terminal",
  "ollama_model": "FALLBACK_MODEL",
  "choices": ["codex", "agy", "hermes", "claude-ollama", "claude-omniroute", "codex-omniroute"],
  "claude_skip_skills": [],
  "agy_skills_mode": "symlink"
}
```

Verify: `~/.agents/stack/bin/agentstack doctor` runs and prints a table (FAILs are expected now).
Save that output as the "before" report.

## 3. Model plane: Ollama and OmniRoute

### 3.1 Ollama

1. `ollama --version` must be 0.15 or newer (needed for `ollama launch`).
2. `ollama pull "$FALLBACK_MODEL"` and `ollama pull "$MEMORY_MODEL"`. **ASK** first; these are large downloads.
3. Coding agents need 64K context; Ollama defaults to 4K on GPUs under 24 GB.
   - macOS app: Settings → context length → 64k (this persists). For the current login also run
     `launchctl setenv OLLAMA_CONTEXT_LENGTH 65536; launchctl setenv OLLAMA_KEEP_ALIVE 24h`, then quit
     and reopen Ollama. (`launchctl setenv` does not survive a reboot.)
   - Linux: `sudo systemctl edit ollama`, add `Environment="OLLAMA_CONTEXT_LENGTH=65536"` and
     `Environment="OLLAMA_KEEP_ALIVE=24h"`, then `sudo systemctl restart ollama`.
4. Verify: `ollama run "$FALLBACK_MODEL" "say ok"` then `ollama ps`. The CONTEXT column must be 65536 or more.
5. Optional, **ASK**: `OLLAMA_NO_CLOUD=1` blocks Ollama Cloud models so code never leaves the machine.

### 3.2 OmniRoute: lock it down

1. `omniroute --version` (verified with 3.8.51). Ask the user how OmniRoute is started (npm, Docker, autostart).
2. Merge `$KIT/templates/omniroute/env` into `~/.omniroute/.env` (back up first, keep the existing
   keys). For Docker, set `APP_BIND_HOST=127.0.0.1` instead of `HOST`. If `.env` still has
   `INITIAL_PASSWORD=CHANGEME`, ask the user to change it. Restart OmniRoute.
3. **Terms-of-service check (ASK).** Open the dashboard (http://127.0.0.1:20128 → Providers) with
   the user, or list connections through the management API. Flag any connection of type
   `claude`/`cc` (Claude Pro/Max login or setup-token), `antigravity`/`agy` (Google login), `codex`
   (ChatGPT login replay), or a web-cookie provider (ChatGPT Web, Claude Web, Gemini Web). Explain
   PLAN.md → Terms of service and recommend removing them. The user decides. Keep: API-key
   providers and `ollama-local` (base URL `http://localhost:11434/v1`).
4. **API keys.** In the dashboard (Endpoints / API Keys) the user creates four keys: `claude-fallback`,
   `codex-fallback`, `hermes-fallback`, `memory-services`. Store them:
   - `~/.agents/stack/secrets.env` (`chmod 600`) with
     `export OMNIROUTE_CODEX_KEY=...` and `export OMNIROUTE_MEMORY_KEY=...`, and add
     `[ -f ~/.agents/stack/secrets.env ] && . ~/.agents/stack/secrets.env` to `~/.zshrc` (or `~/.bashrc`).
   - The Claude and Hermes keys go into their own files in Phase 9.
5. **Fallback combo.** List model IDs:
   `curl -s -H "Authorization: Bearer $OMNIROUTE_CODEX_KEY" http://127.0.0.1:20128/v1/models | jq -r '.data[].id'`.
   With the user, pick API-key models first and the local model last, then:
   `omniroute combo create "$FALLBACK_COMBO" --strategy priority --models "<api model>,<cheaper api model>,ollama/$FALLBACK_MODEL"`.
   Do not use the built-in `auto` model (it can route private code to keyless free providers).
6. Dashboard settings: Quota Preflight Cutoff → 10–15% remaining; Memory → off; Skills → off;
   Obsidian/Notion context sources → not configured; Thinking Budget → `passthrough` (Codex needs
   it); Compression → off or lite. MCP: `omniroute mcp status`, and `omniroute mcp disable` if it
   is on (110 tools; agents do not need it).
7. Verify: `~/.agents/stack/bin/agentstack doctor` shows `omniroute  inference requires an API key`
   (PASS) and no "reachable on the LAN" line.

## 4. Remove the conflicts

### 4.1 ruflo

Detect:

```bash
claude plugin list | grep -i ruflo; grep -n "Ruflo Integration" ~/.claude/CLAUDE.md
grep -l "hook-handler.cjs\|auto-memory-hook" ~/.claude/settings.json "$CODE_ROOT"/*/.claude/settings*.json 2>/dev/null
grep -n "ruflo\|claude-flow" ~/.claude.json ~/.codex/config.toml ~/.gemini/config/mcp_config.json ~/.hermes/config.yaml 2>/dev/null
```

`RUFLO_MODE=orchestration`:

1. In every project `.claude/settings.json` found above, remove the hook entries whose command
   contains `.claude/helpers/hook-handler.cjs` or `.claude/helpers/auto-memory-hook.mjs`, and
   remove a ruflo `statusLine` there (it overrides yours). Back up each file first. **ASK** before
   editing files inside repos.
2. `npx -y ruflo@3.56.0 mods uninstall` and `npx -y ruflo@3.56.0 spinner disable`.
3. `mkdir -p ~/.ruflo && echo '{"enabled": false}' > ~/.ruflo/funnel.json`.
4. Delete the `# Ruflo Integration` block from `~/.claude/CLAUDE.md` (show the user the diff).
5. Uninstall ruflo Claude plugins (`claude plugin uninstall <name>@ruflo` for each one listed) so
   there is one registration only, then register the pinned, filtered MCP:
   `claude mcp remove claude-flow --scope user 2>/dev/null; claude mcp add --scope user --env CLAUDE_FLOW_MCP_TOOLS=swarm,agent,task,workflow --env RUFLO_FUNNEL=0 --env RUFLO_NO_AUTO_ENABLE=1 --transport stdio claude-flow -- npx -y ruflo@3.56.0 mcp start`
6. Remove ruflo MCP entries from Codex (`codex mcp remove ruflo`), agy (`mcp_config.json`) and Hermes (`config.yaml`).

`RUFLO_MODE=remove`: steps 2–4 and 6, uninstall every ruflo Claude plugin, `claude mcp remove claude-flow`.
In each repo run `npx -y ruflo@3.56.0 cleanup` (a dry run) and show the list. **Never** run
`cleanup --force` in a repo that has its own `data/`, `memory/` or `coordination/` folder: it
deletes them. Remove ruflo files by hand there.

Verify: `agentstack doctor` shows no "ruflo hooks" warnings.

### 4.2 Hindsight

Detect: `ls ~/.hindsight`, `claude mcp get hindsight`, Hindsight entries in `~/.claude/settings.json`,
`~/.codex/hooks.json`, `~/.gemini/config/hooks.json`, `claude plugin list | grep -i hindsight`, and
`grep -n provider ~/.hermes/config.yaml`.

All modes except `primary`:

1. `npx -y @vectorize-io/hindsight-coding-agents@0.8.0 uninstall all` (removes its hooks, MCP entry and skill from Claude Code, Codex and agy). VERIFY with `agentstack doctor` afterwards; remove anything left by hand.
2. Legacy plugin: `claude plugin uninstall hindsight-memory@<marketplace>` if listed.
3. Hermes switches to agentmemory in Phase 6.6.
4. `HINDSIGHT_MODE=off`: stop the server (`docker stop hindsight`, or `hindsight-embed daemon stop`). Keep the data volume.
   `HINDSIGHT_MODE=vault-brain`: leave it for Phase 7.5.

### 4.3 graphify hooks

graphify stays, but its per-tool-call hooks go (codebase-memory-mcp owns code navigation):

1. For each repo whose `.claude/settings.json` has a command containing `hook-guard`: in that repo
   run `graphify claude uninstall` (VERIFY; if the command does not exist, delete those hook entries
   by hand). **ASK** before editing files inside repos.
2. In each repo with `.codex/hooks.json` containing `graphify hook-check` (a deliberate no-op), remove that entry.
3. Leave graphify's `## graphify` sections in repo `AGENTS.md`/`CLAUDE.md` unless the user wants
   them gone. They are short, and the shared rules already say codebase-memory-mcp comes first.

### 4.4 Other duplicates

- If `obsidian-mind` hooks are present (doctor warns), **ASK** to remove them: they duplicate agentmemory's capture.
- If agentmemory appears in Claude both as a plugin and in `~/.claude.json` `mcpServers`, or has
  hooks in `~/.claude/settings.json` **and** the plugin, keep the plugin only (Phase 6.2 does this).

## 5. Code layer: codebase-memory-mcp (+ graphify for docs)

### 5.1 codebase-memory-mcp

1. One binary only. List the copies: `for d in $(echo "$PATH" | tr ':' ' '); do [ -x "$d/codebase-memory-mcp" ] && ls -l "$d/codebase-memory-mcp"; done`
   and `grep -rn "codebase-memory-mcp" ~/.claude.json ~/.codex/config.toml ~/.gemini/config/mcp_config.json ~/.hermes/config.yaml`.
   Mixed builds (npx, uvx, Homebrew, `~/.local/bin`) are refused by its daemon. Every agent must point at the same absolute path.
2. Install or update to 0.11.0+: `curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash -s -- --skip-config`
   (**ASK**: this runs a remote script; show it first if the user wants).
3. agy detection: the installer looks for `~/.gemini/antigravity-cli/` or an `antigravity` binary, not `agy`.
   If agy is installed: `mkdir -p ~/.gemini/antigravity-cli`.
4. Preview: `codebase-memory-mcp install --plan > ~/.agents/stack/cbm-plan.json` and summarize the files it will touch for the user.
5. Apply, only for agents that are installed: `codebase-memory-mcp install -y --clients=claude,codex,antigravity,hermes`
6. `codebase-memory-mcp config set auto_index true && codebase-memory-mcp daemon stop`
7. Index: for each repo in `$REPOS`: `codebase-memory-mcp cli index_repository --repo-path "$(git -C "$r" rev-parse --show-toplevel)"`.
8. Verify: `codebase-memory-mcp cli list_projects --format json` lists the repos. In Claude `/mcp`
   shows `codebase-memory-mcp` with 17 tools. Codex and Hermes approvals for its hooks happen in Phase 10.

### 5.2 graphify (docs, papers, media)

1. `uv tool install --reinstall "graphifyy[mcp,ollama,pdf,watch]==0.9.82"` (the package name has two y's; other `graphify*` packages are not the project).
2. Add `export GRAPHIFY_NO_TIPS=1` to the shell profile.
3. `graphify install` (Claude skill; leaves `~/.claude/skills/graphify`) and `graphify install --platform agents` (writes `~/.agents/skills/graphify` for Codex, agy and Hermes).
   Add `"graphify"` to `claude_skip_skills` in `~/.agents/stack/config.json` (Claude already has its own copy).
4. Do **not** run `graphify claude install` or `graphify codex install` (they add the hooks removed in 4.3).
5. Optional per repo (**ASK**; the document pass sends docs to the chosen model):
   `OLLAMA_MODEL="$FALLBACK_MODEL" graphify extract . --backend ollama && graphify cluster-only . --backend ollama`,
   then `graphify hook install` for free AST-only rebuilds on commit and checkout.

## 6. Session-memory layer: agentmemory

### 6.1 Daemon

1. `npm install -g @agentmemory/agentmemory@0.9.30 @agentmemory/mcp@0.9.30` (a global install keeps hook paths stable across upgrades).
2. If `~/.agentmemory/secret` does not exist, the user runs `agentmemory` once in a terminal to finish onboarding, then stops it (`agentmemory stop`).
3. Merge `$KIT/templates/agentmemory/env` into `~/.agentmemory/.env`. Replace `__MEMORY_MODEL__` and `__VAULT__`.
   Keep `EMBEDDING_PROVIDER=local` even if another provider is suggested: switching later breaks the stored vectors.
4. Service:
   - macOS: fill in `$KIT/templates/launchd/dev.agentstack.agentmemory.plist` (`__AGENTMEMORY_BIN__` = `command -v agentmemory`,
     `__NODE_DIR__` = `dirname "$(command -v node)"`, `__HOME__` = `$HOME`), save it as
     `~/Library/LaunchAgents/dev.agentstack.agentmemory.plist`, then
     `mkdir -p ~/.agents/stack/logs && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dev.agentstack.agentmemory.plist`.
   - Linux: fill in `$KIT/templates/systemd/agentmemory.service` → `~/.config/systemd/user/agentmemory.service`, then
     `systemctl --user daemon-reload && systemctl --user enable --now agentmemory`.
5. Verify: `curl -fsS -H "Authorization: Bearer $(cat ~/.agentmemory/secret)" http://localhost:3111/agentmemory/livez`.
   Restart test: `launchctl kickstart -k gui/$(id -u)/dev.agentstack.agentmemory`, then livez again (VERIFY: no port clash with the detached engine).
   Viewer: http://localhost:3113.

### 6.2 Claude Code (plugin; one path only)

1. Remove the non-plugin wiring if present: `claude mcp remove agentmemory --scope user`, and hook
   entries in `~/.claude/settings.json` whose command points into the agentmemory package.
2. Install the plugin: `claude plugin marketplace add rohitg00/agentmemory`, then
   `claude plugin install agentmemory@<marketplace name from claude plugin marketplace list>`
   (inside a session the same is `/plugin marketplace add rohitg00/agentmemory` and `/plugin install agentmemory`).
3. Verify in a new session: `/mcp` lists agentmemory, and `/hooks` shows its hooks. Expect 8 tools
   because of `AGENTMEMORY_TOOLS=core` (VERIFY; 54 means the plugin ignores the daemon setting, which is acceptable).

### 6.3 Codex (plugin)

1. Remove `[mcp_servers.agentmemory]` from `~/.codex/config.toml` if present (back up first).
2. `codex plugin marketplace add rohitg00/agentmemory && codex plugin add agentmemory@agentmemory`
3. The user opens Codex and trusts the plugin hooks in `/hooks` (Phase 10 lists this).

### 6.4 agy

1. `agentmemory connect antigravity-cli --with-hooks` (writes the MCP entry in `~/.gemini/config/mcp_config.json`,
   hooks in `~/.gemini/config/hooks.json`, and a guideline block in `~/.gemini/GEMINI.md`).
2. In `~/.gemini/config/mcp_config.json`, set `"env": {"AGENTMEMORY_FORCE_PROXY": "1"}` on the
   `agentmemory` entry, so the shim fails visibly instead of writing to a private fallback store when the daemon is down.
3. Verify: `agy mcp list` (or `/mcp` inside agy) and `/hooks`.

### 6.5 Hermes (memory provider)

1. `git clone --depth 1 --branch v0.9.30 https://github.com/rohitg00/agentmemory ~/tools/agentmemory`
   (VERIFY the tag name with `git ls-remote --tags`; else clone and check out the 0.9.30 commit).
2. `mkdir -p ~/.hermes/plugins && cp -R ~/tools/agentmemory/integrations/hermes ~/.hermes/plugins/agentmemory`
3. `hermes config set memory.provider agentmemory` (only one external provider can be active; this replaces Hindsight).
4. Do **not** add agentmemory as an MCP server in Hermes: the provider already adds `memory_recall`/`memory_save`/`memory_search`, and the MCP copy would add tools with the same names.
5. Verify: `hermes plugins doctor` and `hermes memory status`.

### 6.6 Shell environment

Add to `~/.zshrc` (or `~/.bashrc`):

```bash
export CLAUDE_OBSIDIAN_VAULT="$VAULT"      # literal path
export GRAPHIFY_NO_TIPS=1
# only if AM_INJECT=true (hooks read it from the environment the agent is launched from):
# export AGENTMEMORY_INJECT_CONTEXT=true
```

## 7. Notes layer: Obsidian vault + claude-obsidian

1. Plugin for Claude Code (skip if `claude plugin list` already shows it):
   `claude plugin marketplace add AgriciDaniel/claude-obsidian && claude plugin install claude-obsidian@agricidaniel-claude-obsidian`
2. Shared checkout for the other agents:
   `git clone https://github.com/AgriciDaniel/claude-obsidian.git ~/tools/claude-obsidian && git -C ~/tools/claude-obsidian checkout 32ac5a0`
3. Vault: `python3 ~/tools/claude-obsidian/scripts/claude-obsidian.py doctor --vault "$VAULT"`.
   If it is not initialized, run `init` (new vault) or `adopt` (existing vault) as a **plan first**:
   ```bash
   cd ~/tools/claude-obsidian; GEN="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; OP=agent-stack-setup
   python3 scripts/claude-obsidian.py adopt "$VAULT" --generated-at "$GEN" --operation-id "$OP"
   ```
   Show the plan to the user. Only after a yes, apply with the hash it printed:
   `... adopt "$VAULT" --generated-at "$GEN" --operation-id "$OP" --approved-plan-sha256 <hash> --apply`.
   Never pass a hash the user has not seen.
4. Skills for Codex, agy and Hermes (links into `~/.agents/skills`):
   `bash ~/tools/claude-obsidian/scripts/setup-multi-agent.sh --host codex --dry-run`, then `--apply`.
   Add its skill names to `claude_skip_skills` (Claude has the plugin versions): `wiki`, `save`,
   `wiki-ingest`, `wiki-query`, `wiki-lint`, `autoresearch`, `canvas`, `defuddle`, `wiki-fold`,
   `wiki-mode`, `wiki-retrieve`, `wiki-cli`, `obsidian-markdown`, `obsidian-bases`, `think`.
   Hermes can edit skills inside `external_dirs`, so protect the checkout: `chmod -R a-w ~/tools/claude-obsidian/skills`
   (run `chmod -R u+w` before a `git pull`).
5. Claude settings: add `"CLAUDE_OBSIDIAN_VAULT": "<VAULT>"` to the `env` block of `~/.claude/settings.json`.
   Only if `HOT_INJECT=true`, also add `"CLAUDE_OBSIDIAN_SESSION_CONTEXT": "1"` and `"CLAUDE_OBSIDIAN_SESSION_CONTEXT_VAULT": "<VAULT>"`.
   The product treats this as explicit consent; never set it without the user's yes.
6. Generated content gets its own folders, so it never mixes with curated wiki pages:
   `<VAULT>/agentmemory/` (agentmemory export) and `<VAULT>/graphify/<repo>/` (graphify export). Lint with
   `--exclude 'agentmemory/**' --exclude 'graphify/**'`.
7. Backup: **ASK** whether to use claude-obsidian `checkpoint` commits or the obsidian-git plugin. Use only one of them.
8. `OBSIDIAN_MCP=yes` only: the user installs the "Local REST API" community plugin in Obsidian and copies its API key. Then:
   - Claude: `claude mcp add --transport http obsidian https://127.0.0.1:27124/mcp/ --header "Authorization: Bearer <key>" --scope user`,
     and add `"mcp__obsidian__vault_delete"` and `"mcp__obsidian__command_execute"` to `permissions.deny` in `~/.claude/settings.json`.
   - Codex: `[mcp_servers.obsidian]` with `url = "https://127.0.0.1:27124/mcp/"`, `bearer_token_env_var = "OBSIDIAN_API_KEY"`, `disabled_tools = ["vault_delete", "command_execute"]`.
   - agy: `"obsidian": {"serverUrl": "https://127.0.0.1:27124/mcp/", "headers": {"Authorization": "Bearer <key>"}, "disabledTools": ["vault_delete", "command_execute"]}`.
   - Hermes: `mcp_servers.obsidian` with `url`, `headers.Authorization: "Bearer ${OBSIDIAN_API_KEY}"` and `trust: untrusted`.
   - TLS: trust the plugin's certificate (https://127.0.0.1:27124/obsidian-local-rest-api.crt) in Keychain, or enable its HTTP port 27123 and use `http://127.0.0.1:27123/mcp/`.

### 7.5 Hindsight vault brain (`HINDSIGHT_MODE=vault-brain` only)

1. Server bound to loopback, LLM on local Ollama:
   ```bash
   docker run -d --name hindsight --restart unless-stopped -p 127.0.0.1:8888:8888 -p 127.0.0.1:9999:9999 \
     -e HINDSIGHT_API_LLM_PROVIDER=ollama -e HINDSIGHT_API_LLM_BASE_URL=http://host.docker.internal:11434/v1 \
     -e HINDSIGHT_API_LLM_MODEL="$MEMORY_MODEL" -e HINDSIGHT_API_LLM_STRICT_SCHEMA=true \
     -e HINDSIGHT_API_RETAIN_MAX_COMPLETION_TOKENS=16000 -e HINDSIGHT_API_MCP_ENABLED_TOOLS=recall,reflect \
     -v hindsight-data:/home/hindsight/.pg0 ghcr.io/vectorize-io/hindsight:latest-slim
   ```
   (The slim image needs external embeddings; use `:latest` if the user has the disk space. On Linux add `--add-host=host.docker.internal:host-gateway`.)
2. One-way sync of the vault into a bank: `npm install -g @vectorize-io/hindsight-obsidian` and
   `hindsight-obsidian-sync reconcile --vault "$VAULT" --bank obsidian --api-url http://localhost:8888 --watch` (run it as a login service like 6.1).
3. Register the read-mostly MCP in each agent as `hindsight-vault` → `http://localhost:8888/mcp/obsidian/`
   (Claude `--transport http`, Codex `url =`, agy `serverUrl`, Hermes `url:`).
4. Append to `~/.agents/AGENTS.md` under "Where knowledge lives": `| Meaning-based search over the notes | hindsight-vault (recall, reflect) | |`.

## 8. Rules and skills for every agent

1. Shared rules: `sed "s#__VAULT__#$VAULT#g" "$KIT/shared/AGENTS.md" > ~/.agents/AGENTS.md` (use the literal vault path).
2. Shared skill: `cp -R "$KIT/shared/skills/agent-handoff" ~/.agents/skills/`
3. Preview, then apply: `~/.agents/stack/bin/agentstack sync --check` and `~/.agents/stack/bin/agentstack sync`.
   This adds `@~/.agents/AGENTS.md` to `~/.claude/CLAUDE.md`, writes managed blocks into
   `~/.codex/AGENTS.md`, `~/.gemini/AGENTS.md` and `~/.hermes/SOUL.md`, and links each skill into
   `~/.claude/skills` (except `claude_skip_skills`) and `~/.gemini/antigravity-cli/skills`.
4. Hermes `~/.hermes/config.yaml` (edit by hand, back up first; see `$KIT/templates/hermes/omniroute.yaml`):
   `skills.external_dirs: [~/.agents/skills]` and `skills.write_approval: true`. Run `agentstack sync` again; it must report `hermes skills  ok`.
5. Claude reads a repo's `AGENTS.md` only when the repo has no `CLAUDE.md`. To make Claude read both
   (so per-repo `AGENTS.md` written by other tools is shared), **ASK**, then add to `~/.claude/settings.json`:
   `"pluginConfigs": {"cc-plugin-agents-md@builtin": {"options": {"instructionFiles": "claude-md-and-agents-md"}}}`.
6. Verify agy skills: `agy -p "/skills" --output-format json --print-timeout 2m < /dev/null` must list `agent-handoff`.
   VERIFY: if symlinked skills are not listed, set `"agy_skills_mode": "copy"` in `config.json`, delete the links in
   `~/.gemini/antigravity-cli/skills/`, and run `agentstack sync` again.

## 9. Usage-limit switcher and fallback profiles

1. Claude hooks and status line: `~/.agents/stack/bin/agentstack install --agent claude --dry-run`, show the
   diff, then run it without `--dry-run`. An existing status line is kept and shown in front of the usage figures.
2. Codex SessionStart hook: `~/.agents/stack/bin/agentstack install --agent codex` (trust it in `/hooks` later).
3. agy status line (optional, **ASK**): `~/.agents/stack/bin/agentstack install --agent agy`. It shows agy's
   remaining quota and opens the picker at the thresholds too.
4. `AUTO_CONTINUE=false`: set `"autoContinueAtUsageLimit": false` in `~/.claude/settings.json`.
5. Claude Code on Ollama: `ollama launch claude --model "$FALLBACK_MODEL" -- -p "say ok"` must answer.
   Then start it interactively and run `/mcp`: codebase-memory-mcp and agentmemory must be listed
   (VERIFY: an Ollama issue reported MCP tools missing under `ollama launch`. If they are missing, use
   `ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" ANTHROPIC_BASE_URL=http://localhost:11434 claude --model "$FALLBACK_MODEL"`
   instead, and tell the user the `claude-ollama` choice needs that form).
6. Claude Code via OmniRoute: fill in `$KIT/templates/claude/omniroute.settings.json` (`claude-fallback` key, the combo,
   a small model for background work, and the combo's context window as an integer such as `128000`), save it as
   `~/.claude/omniroute.settings.json`, and run `chmod 600` on it. Test: `claude --settings ~/.claude/omniroute.settings.json -p "say ok"`.
   If you get 400 errors about betas or `context_management`, add `"CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1"` to its env.
7. Codex via OmniRoute: append `$KIT/templates/codex/omniroute-provider.toml` to `~/.codex/config.toml` (only if no
   `[model_providers.omniroute]` exists), save `$KIT/templates/codex/omniroute.config.toml` as `~/.codex/omniroute.config.toml`
   with the combo name. Test: `codex exec --profile omniroute "say ok"`.
8. Hermes: add the `providers.omniroute` block from `$KIT/templates/hermes/omniroute.yaml`, put `OMNIROUTE_HERMES_KEY=<hermes-fallback key>`
   in `~/.hermes/.env`, then the user runs `hermes fallback add` and picks the omniroute provider and the combo.
   Test: `hermes -z "say ok" --provider custom:omniroute -m "$FALLBACK_COMBO"` (VERIFY the provider name format).
9. agy stays on its own Google login. Do not point it at OmniRoute.
10. Picker test: `~/.agents/stack/bin/agentstack switch --reason "Setup test"`. A dialog lists the installed agents.
    Pick "Keep using the current agent". The first run on macOS may ask to allow automation; allow it.
11. Launch test in a scratch repo: `~/.agents/stack/bin/agentstack switch --pick codex --reason "Setup test"`. A new
    terminal opens in the repo and Codex starts with the resume prompt.
12. Clean up test state: `rm -f ~/.agents/stack/state/handoff-request.json ~/.agents/stack/state/fired/*` and delete the scratch repo's `HANDOFF.md`.

## 10. Verify end to end

1. `~/.agents/stack/bin/agentstack doctor`: no FAIL lines. Go through every WARN with the user.
2. **Manual approvals the user must do** (list them clearly at the end):
   - Codex: open `codex`, run `/hooks`, trust the codebase-memory, agentmemory and agentstack hooks.
   - Hermes: `hermes hooks list` and approve the codebase-memory `pre_llm_call` hook once (interactive), then `hermes hooks doctor`.
   - Obsidian: only for `OBSIDIAN_MCP=yes`, install the Local REST API plugin in the app.
   - OmniRoute dashboard items from 3.2 that the user has not done yet.
3. **Memory round trip.** In Claude Code: "Save a memory: agent-stack drill word is `<pick a random word>`."
   Then: `codex exec "Use memory_smart_search for 'agent-stack drill' and print the drill word."`,
   `agy -p "Use memory_smart_search for 'agent-stack drill' and print the drill word." --print-timeout 5m < /dev/null`,
   `hermes -z "Search memory for 'agent-stack drill' and print the drill word."`. Each must print the word.
4. **Code graph.** In each agent ask: "Use codebase-memory-mcp search_graph to find the function `<a real function>` in this repo."
5. **Handoff drill.** In a scratch repo, in Claude Code: "Use the agent-handoff skill to write a handoff for a fake task."
   Then `~/.agents/stack/bin/agentstack switch --pick codex --from claude --reason drill`. Codex must quote the handoff narrative
   on its first answer. Set `status: done` afterwards.
6. **Threshold drill:**
   `echo '{"model":{"display_name":"Drill"},"workspace":{"current_dir":"'"$PWD"'"},"rate_limits":{"five_hour":{"used_percentage":86,"resets_at":"drill-1"}}}' | ~/.agents/stack/bin/agentstack statusline`
   The picker must appear. Clean up as in 9.12.
7. **Status line.** Start Claude Code and send one message. The status line must show `5h NN%` after
   the first reply. If it never does, the `rate_limits` bug applies: the 85% popup cannot fire, but the
   at-limit path (`StopFailure`) still works. Tell the user and check again after a Claude Code update.

## 11. Self-checks for each agent

The user pastes the line into that agent after Phase 10. Each agent checks only its own wiring and
fixes only what is listed for it.

**Codex:** `Read agent-stack/SETUP-PLAYBOOK.md section 11 "Codex" and run those checks.`
- `codex mcp list` includes `codebase-memory-mcp`; agentmemory comes from the plugin (`/plugins`), and no `[mcp_servers.agentmemory]` duplicate exists.
- `/skills` lists `agent-handoff`, `graphify` and the claude-obsidian skills (from `~/.agents/skills`).
- `~/.codex/AGENTS.md` contains the `agent-stack:begin` block. `/hooks` shows trusted codebase-memory, agentmemory and agentstack hooks.
- `memory_smart_search "agent-stack drill"` returns the drill memory.
- `codex --profile omniroute` starts if the OmniRoute fallback was set up.

**agy:** `Read agent-stack/SETUP-PLAYBOOK.md section 11 "agy" and run those checks.`
- `/mcp` lists `codebase-memory-mcp` and `agentmemory`; no `hindsight`.
- `/skills` lists `agent-handoff` (else switch to copy mode, see 8.6).
- `~/.gemini/AGENTS.md` has the `agent-stack:begin` block; `/hooks` shows agentmemory's 4 hooks.
- Memory round trip as in 10.3.

**Hermes:** `Read agent-stack/SETUP-PLAYBOOK.md section 11 "Hermes" and run those checks.`
- `hermes memory status` shows provider `agentmemory`; `hermes mcp list` shows `codebase-memory-mcp` and no `agentmemory`/`hindsight` MCP.
- `hermes skills list` includes `agent-handoff`; `skills.write_approval` is true.
- `~/.hermes/SOUL.md` has the `agent-stack:begin` block. `hermes hooks doctor` is clean.
- The model's context window is 64K or more (Hermes refuses smaller ones).

**Claude Code on Ollama:** start `ollama launch claude --model <FALLBACK_MODEL>`, then `/mcp` (codebase-memory-mcp, agentmemory),
and ask it to read `HANDOFF.md` in a repo that has one. Small local models may handle many tool schemas poorly; if so,
register the lighter code-graph profile: `claude mcp add --scope user codebase-memory-scout -- "$(command -v codebase-memory-mcp)" --tool-profile=scout`.

## 12. Maintenance and rollback

- **Weekly:** `~/.agents/stack/bin/agentstack doctor`.
- **After editing** `~/.agents/AGENTS.md` or adding a skill to `~/.agents/skills`: `agentstack sync`.
- **Updating a tool:** read its changelog, then:
  - codebase-memory-mcp: re-run its `install.sh`, restart every agent session, re-trust Codex hooks if asked.
  - agentmemory: `npm install -g @agentmemory/agentmemory@<v> @agentmemory/mcp@<v>`, restart the service, re-run
    `agentmemory connect antigravity-cli --with-hooks --force`, update the Hermes plugin copy from the new tag.
  - graphify: `uv tool upgrade graphifyy`, then `graphify hook install` again in repos that use the git hooks.
  - agentstack: copy the new `bin/agentstack`, run its tests, then `agentstack install --agent claude` and `--agent codex` again (idempotent).
- **Turn the switcher off:** `agentstack uninstall --agent claude`, `--agent codex`, `--agent agy`. Your previous status line comes back.
- **Full rollback:** stop the agentmemory service (`launchctl bootout gui/$(id -u)/dev.agentstack.agentmemory`), then restore
  `~/.agents/stack/backups/<TS>/configs.tgz` with `tar -xzf configs.tgz -C /` after showing the user what it will overwrite.
