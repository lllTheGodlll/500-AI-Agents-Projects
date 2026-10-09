# Agent stack setup playbook

**For the agent running this:** you are setting up one shared memory layer for Claude Code,
Codex, Antigravity CLI (agy), Hermes Agent and Ollama on the user's own computer. The design and
the reasons are in [PLAN.md](PLAN.md); read it first. This file is the procedure.

How to start (the user says one of these):

- Claude Code (recommended), from a clone of this repo: `Read agent-stack/SETUP-PLAYBOOK.md and run it. Ask me the decisions first.`
- Any other agent: the same sentence works. Codex, agy and Hermes can run every shell step here.
  They cannot show multiple-choice questions, so ask the decisions in plain text. If an agent's
  sandbox blocks writes outside the repo (for example to `~/.agents`), run the setup from Claude
  Code or from a normal terminal instead.
- After the setup, each other agent runs its own section of [Self-checks](#11-self-checks-for-each-agent).

## 0. Rules for the agent running this

1. **Back up before you change anything** (Phase 1). Never delete user data. Stopping a service is fine; deleting its data is not.
2. **Ask before** each step marked **ASK**, before anything destructive, before editing files inside the user's repos, and before any step that sends data off the machine.
3. **Check, then do, then verify.** Every step is idempotent: if the check shows it is already done, skip it. If a verify step fails, stop that phase, report what you saw, and propose a fix. Do not improvise around it.
4. **Secrets.** Never ask the user to paste a key into the chat. Never put a literal secret in a command line, a file-writing tool call, or the log. Never print `env`, `headers`, `args` or token values from any config file; list key names only. Keys live in `~/.agents/stack/secrets.env` (mode 600), which the user fills in with their own editor, and reach config files only by shell expansion. If a key was pasted into the chat by mistake, tell the user to rotate it: memory hooks may already have recorded it.
5. **Versions.** The steps were verified against: Claude Code 2.1.295, Codex 0.162.0, agy 1.3.2, Hermes v2026.9.24, Ollama 0.40.2, codebase-memory-mcp 0.11.0, agentmemory 0.9.30, graphifyy 0.9.82, ruflo 3.56.0, claude-obsidian 2.2.0 (commit `32ac5a0`), Hindsight 0.10.3 / coding-agents 0.8.0, OmniRoute 3.8.51. If an installed version is newer, read its changelog for breaking changes before running that tool's steps, and never downgrade. Pin versions when installing.
6. **VERIFY** marks behaviour that could not be confirmed in docs or source. Test it as written; if it fails, use the fallback given.
7. **Log.** First run `umask 077; mkdir -p ~/.agents/stack && chmod 700 ~/.agents/stack; touch ~/.agents/stack/SETUP-LOG.md; chmod 600 ~/.agents/stack/SETUP-LOG.md`. Append every command and its outcome there, never a secret value.
8. Use the repo checkout as `$KIT` (the folder that contains this file), for example `KIT="$(git rev-parse --show-toplevel)/agent-stack"`.
9. Drills and tests run only in the scratch repo created in Phase 2, never in the user's real repos.

## Decisions (ASK all of these first)

Record the answers in `~/.agents/stack/SETUP-LOG.md` and use them below.

| Var | Question | Default |
|---|---|---|
| `VAULT` | Obsidian vault path (an existing vault is fine) | `~/Vaults/AgentBrain` |
| `CODE_ROOT` | Folder that holds your repos | `~/code` |
| `REPOS` | Repos to index now | the ones you are working on |
| `RUFLO_MODE` | ruflo: `orchestration` (Claude-only MCP, memory off) or `remove` | `orchestration` |
| `HINDSIGHT_MODE` | `off` (remove hooks, stop the server, keep its data) or `vault-brain` (search over the vault, no hooks) | `off` |
| `RAM` | Memory of this machine (unified memory on Apple Silicon) | ask |
| `FALLBACK_MODEL` | Local coding model. Under 24 GB: none (use API models through OmniRoute; `qwen3:8b` is possible but weak) · about 24 GB: `gemma4` or `qwen3.5` · 32 GB+: `qwen3-coder:30b` or `gpt-oss:20b` | by `RAM` |
| `MEMORY_MODEL` | Small local model for memory summaries (Phase 3.1 makes a 16K-context copy) | `qwen3:8b` |
| `THRESHOLDS` | Popup at these % of the 5-hour window / weekly window | `85,95` / `90` |
| `TERMINAL` | Terminal app for new agent windows | `Terminal` (or `iTerm`) |
| `FALLBACK_COMBO` | OmniRoute combo for Codex and Hermes fallback | `coding-fallback` |
| `AUTO_CONTINUE` | Let Claude Code continue by itself after the limit resets | `false` |
| `AM_INJECT` | agentmemory injects memory at session start (`AGENTMEMORY_INJECT_CONTEXT`) | `false` |
| `AM_PRECOMPACT_BUDGET` | Tokens of memory agentmemory injects before compaction in Claude and Codex | `1500` (`0` = off) |
| `HOT_INJECT` | claude-obsidian injects `wiki/hot.md` into Claude at session start | `false` |
| `OBSIDIAN_MCP` | Add the Obsidian Local REST API MCP to the agents | `no` (files + skills are enough) |

---

## 1. Preflight, backup, inventory

**1.1 Tools present.** Run and log:

```bash
uname -a; sw_vers 2>/dev/null
for c in claude codex agy hermes ollama omniroute agentmemory codebase-memory-mcp graphify git node npm npx python3 uv docker jq; do
  printf '%-22s %s\n' "$c" "$(command -v $c || echo MISSING)"; done
claude --version; codex --version; agy --version; hermes --version; ollama --version
codebase-memory-mcp --version; graphify --version 2>/dev/null; node --version; python3 --version
npm ls -g --depth=0 @agentmemory/agentmemory @agentmemory/mcp 2>/dev/null; pgrep -fl agentmemory
python3 -c 'import sys; sys.exit(sys.version_info < (3,11))' && echo 'python3 OK for claude-obsidian' || echo 'python3 too old for claude-obsidian (needs 3.11+)'
```

- git and jq are required. Python 3.9+ is enough for agentstack. A missing agent is fine: skip its steps.
- claude-obsidian (Phase 7) needs Python 3.11+ as the first `python3` on PATH: its CLI, its Claude
  Code hooks and its skills in other agents all run a bare `python3`. If it is too old, **ASK** to
  install a newer one (macOS: `brew install python`, with `eval "$(brew shellenv)"` in `~/.zprofile`
  so it comes before `/usr/bin`; Linux: the distro's python3.11+ or `uv python install 3.12 --default --preview`).
  Open a new shell and re-check. If the user declines, skip Phase 7 steps 1–4.
- agentmemory: **ASK** how the user starts it today: from which folder, with `--data-dir`,
  `AGENTMEMORY_DATA_DIR` or `--instance`, and whether a `data/state_store.db` exists in that folder.
  Record the installed version as `AM_OLD_VERSION` and the store path as `AM_DATA_DIR`. The default
  store is `~/Library/Application Support/agentmemory` (macOS) or `${XDG_DATA_HOME:-~/.local/share}/agentmemory` (Linux).

**1.2 Backup.** Configs first:

```bash
TS=$(date +%Y%m%d-%H%M%S); B=~/.agents/stack/backups/$TS; mkdir -p "$B"; chmod 700 ~/.agents/stack/backups "$B"
paths=()
for p in ~/.claude/settings.json ~/.claude.json ~/.claude/CLAUDE.md ~/.claude/skills ~/.claude/agents \
         ~/.claude/omniroute.settings.json ~/.claude/profiles \
         ~/.codex/config.toml ~/.codex/hooks.json ~/.codex/AGENTS.md ~/.codex/AGENTS.override.md ~/.codex/*.config.toml \
         ~/.gemini/config ~/.gemini/AGENTS.md ~/.gemini/GEMINI.md ~/.gemini/antigravity-cli/settings.json \
         ~/.gemini/antigravity-cli/skills ~/.hermes/config.yaml ~/.hermes/SOUL.md ~/.hermes/.env \
         ~/.hermes/hindsight ~/.hermes/plugins ~/.agentmemory ~/.omniroute/.env ~/.omniroute/server.env \
         "${XDG_CONFIG_HOME:-/nonexistent}/omniroute/.env" "${XDG_CONFIG_HOME:-/nonexistent}/omniroute/server.env" \
         ~/.hindsight ~/.ruflo ~/.agents/AGENTS.md ~/.agents/skills ~/.zshrc ~/.zprofile ~/.bashrc; do
  [ -e "$p" ] && paths+=("${p#/}"); done
tar -czf "$B/configs.tgz" -C / "${paths[@]}" && chmod 600 "$B/configs.tgz" && tar -tzf "$B/configs.tgz" | head -60
```

Then the agentmemory store itself, with the daemon stopped so its last writes are flushed:

```bash
curl -fsS -H "Authorization: Bearer $(cat ~/.agentmemory/secret 2>/dev/null)" http://127.0.0.1:3111/agentmemory/export \
  > "$B/agentmemory-export.json" 2>/dev/null && chmod 600 "$B/agentmemory-export.json" || echo "no running daemon to export from"
agentmemory stop 2>/dev/null || true      # or launchctl/systemctl stop if it already runs as a service
i=0; for d in "${AM_DATA_DIR:-}" "$HOME/Library/Application Support/agentmemory" "${XDG_DATA_HOME:-$HOME/.local/share}/agentmemory"; do
  [ -n "$d" ] && [ -d "$d" ] || continue; i=$((i+1))
  tar -czf "$B/agentmemory-data-$i.tgz" -C "$(dirname "$d")" "$(basename "$d")" && echo "$i $d" >> "$B/agentmemory-data.index"; done
chmod 600 "$B"/agentmemory-* 2>/dev/null
```

If the user named a legacy `data/state_store.db`, tar that folder into `$B` too. The export is
paged (`?maxSessions`, `?offset`), so treat it as a convenience copy; the tar archives are the backup.
Leave the daemon stopped until Phase 6.1 starts the service. All archives contain secrets and stay on this machine.

**1.3 Inventory** (names only, never values). Save the output to the log:

```bash
claude plugin list; claude mcp list
codex mcp list; ls ~/.codex/*.config.toml 2>/dev/null
jq '[.hooks // {} | to_entries[] | {event: .key, cmd: [.value[].hooks[]?.command]}]' ~/.codex/hooks.json ~/.gemini/config/hooks.json 2>/dev/null
jq '.mcpServers | to_entries | map({name: .key, url: (.value.serverUrl // .value.url), command: .value.command})' ~/.gemini/config/mcp_config.json 2>/dev/null
hermes mcp list; hermes memory status; hermes plugins list
grep -nE '^\s*(provider|default):' ~/.hermes/config.yaml 2>/dev/null; hermes auth list 2>/dev/null   # VERIFY subcommand; names only
ollama list; omniroute --version; docker ps -a --filter name=hindsight --format '{{.Names}} {{.Status}} {{.Ports}}' 2>/dev/null
jq -r '.hooks // {} | to_entries[] | .key as $e | .value[].hooks[]?.command | "\($e): \(.)"' ~/.claude/settings.json 2>/dev/null
grep -n "Ruflo Integration\|# graphify\|agentmemory" ~/.claude/CLAUDE.md 2>/dev/null
for r in $REPOS; do echo "== $r"; ls "$r"/.claude/settings*.json "$r"/.mcp.json "$r"/.codex "$r"/HANDOFF.md 2>/dev/null; done
```

Never `cat` `~/.hermes/auth.json`, `~/.hermes/.env`, `~/.agentmemory/.env` or `~/.claude.json`.
Show the user a short summary: which agents, which memory tools are wired where, and which
duplicates you see (two memory hook sets in one agent, two code-graph hook sets, ruflo hooks).

## 2. Install the glue (agentstack) and a scratch repo

```bash
mkdir -p ~/.agents/stack/bin ~/.agents/skills
install -m 755 "$KIT/bin/agentstack" ~/.agents/stack/bin/agentstack
python3 "$KIT/tests/test_agentstack.py"          # must end with OK (40 tests)
SCRATCH=~/.agents/stack/scratch-repo; mkdir -p "$SCRATCH" && git -C "$SCRATCH" init -q && \
  git -C "$SCRATCH" -c user.name=t -c user.email=t@e commit -q --allow-empty -m scratch
```

Write `~/.agents/stack/config.json` from the decisions (keep JSON valid; leave `claude-ollama` out of
`choices` if there is no `FALLBACK_MODEL`):

```json
{
  "thresholds_5h": [85, 95],
  "thresholds_7d": [90],
  "terminal": "Terminal",
  "ollama_model": "FALLBACK_MODEL",
  "claude_ollama_mode": "launch",
  "ollama_url": "http://localhost:11434",
  "choices": ["codex", "agy", "hermes", "claude-ollama", "claude-omniroute", "codex-omniroute"],
  "claude_skip_skills": [],
  "agy_skills_mode": "symlink"
}
```

Verify: `~/.agents/stack/bin/agentstack doctor` prints a table (FAILs are expected now). Save it as the "before" report.

## 3. Model plane: Ollama and OmniRoute

### 3.1 Ollama

1. `ollama --version` must be 0.15 or newer (needed for `ollama launch`).
2. **ASK** (large downloads), then `ollama pull "$MEMORY_MODEL"`, and `ollama pull "$FALLBACK_MODEL"` if one was chosen.
3. Give the memory model its own small window, so the server-wide 64K setting below does not apply to it:
   `printf 'FROM %s\nPARAMETER num_ctx 16384\n' "$MEMORY_MODEL" > ~/.agents/stack/memory.Modelfile && ollama create agentstack-memory -f ~/.agents/stack/memory.Modelfile`,
   then use `MEMORY_MODEL=agentstack-memory` from here on.
4. Coding agents need a 64K context; Ollama defaults to 4K on GPUs under 24 GB. Only if there is a `FALLBACK_MODEL`:
   - macOS app: Settings → context length → 64k (this persists). For the current login also run
     `launchctl setenv OLLAMA_CONTEXT_LENGTH 65536`, and on machines with 32 GB+ `launchctl setenv OLLAMA_KEEP_ALIVE 24h`;
     then quit and reopen Ollama. (`launchctl setenv` does not survive a reboot.)
   - Linux: this needs sudo and an editor, so the **user** runs `sudo systemctl edit ollama`, adds
     `Environment="OLLAMA_CONTEXT_LENGTH=65536"` under `[Service]`, then `sudo systemctl restart ollama`.
5. Verify: run each model once (`ollama run <model> "say ok"`), then `ollama ps`. The fallback model's CONTEXT must be
   65536 or more, PROCESSOR must say `100% GPU` for each model, and SIZE must fit (on a Mac, the total of both models should
   stay under about 70% of unified memory). If not, drop to the next smaller model or to no local fallback.
6. Optional, **ASK**: `OLLAMA_NO_CLOUD=1` blocks Ollama Cloud models so code never leaves the machine.
7. Never set `OLLAMA_HOST=0.0.0.0`: Ollama has no auth, so that opens it to your network.

### 3.2 OmniRoute: lock it down

1. `omniroute --version` (verified with 3.8.51). Ask the user how OmniRoute is started (npm, Docker, autostart).
2. Merge `$KIT/templates/omniroute/env` into the `.env` OmniRoute reads (`DATA_DIR/.env`; DATA_DIR is
   `~/.omniroute`, or `$XDG_CONFIG_HOME/omniroute` when that is set). Back it up first and keep the existing keys.
   For Docker, set `APP_BIND_HOST=127.0.0.1` instead of `HOST`. Restart OmniRoute. If the dashboard
   password is still the default, the user changes it in the dashboard (`INITIAL_PASSWORD` only applies on first boot).
3. **Terms-of-service check (ASK).** With the user, open the dashboard (http://127.0.0.1:20128 → Providers). Flag:
   - `claude`/`cc` (Claude Pro/Max login or setup-token), `antigravity`/`agy` (Google login), `codex` (ChatGPT login replay);
   - other OAuth logins (Cursor, Kiro), web-cookie providers (ChatGPT Web, Claude Web, Gemini Web);
   - `codex-app-server` (gray: one personal account at most);
   - more than one account on the same subscription provider (pooling breaks OpenAI's terms);
   - keyless free providers the catalog marks "avoid" (OpenCode Free, Kiro).
   Explain PLAN.md → Terms of service and recommend removing them. The user decides. Keep API-key providers and
   `ollama-local` with base URL `http://localhost:11434/v1` (OmniRoute in Docker on macOS: `http://host.docker.internal:11434/v1`;
   on Linux run OmniRoute's container with `--network host` and `APP_BIND_HOST=127.0.0.1` instead).
4. **Hermes login check (ASK).** If Hermes uses the Anthropic OAuth login (`hermes model` → Anthropic), explain PLAN.md →
   Terms → Anthropic and recommend switching Hermes's primary provider to its own `hermes auth add openai-codex` login, an
   Anthropic API key, `custom:omniroute` or Ollama. If Hermes got its ChatGPT login by importing `~/.codex/auth.json`,
   recommend logging Hermes in again with its own device-code flow. The user decides.
5. **API keys.** The user creates four keys in the dashboard (Endpoints / API Keys): `claude-fallback`, `codex-fallback`,
   `hermes-fallback`, `memory-services`. Prepare the file they go into:
   ```bash
   ( umask 077; f=~/.agents/stack/secrets.env; [ -f "$f" ] || printf '%s\n' 'export OMNIROUTE_CLAUDE_KEY=' \
     'export OMNIROUTE_CODEX_KEY=' 'export OMNIROUTE_HERMES_KEY=' 'export OMNIROUTE_MEMORY_KEY=' 'export OBSIDIAN_API_KEY=' > "$f"; chmod 600 "$f" )
   ```
   The user pastes the values into that file **in their own editor**, not in the chat. Then check presence only:
   `bash -c '. ~/.agents/stack/secrets.env; for v in OMNIROUTE_CLAUDE_KEY OMNIROUTE_CODEX_KEY OMNIROUTE_HERMES_KEY OMNIROUTE_MEMORY_KEY; do [ -n "${!v}" ] && echo "$v set" || echo "$v MISSING"; done'`.
   Add `[ -f ~/.agents/stack/secrets.env ] && . ~/.agents/stack/secrets.env` to `~/.zshrc` (or `~/.bashrc`).
6. **Combos.** List model IDs: `bash -c '. ~/.agents/stack/secrets.env; curl -s -H "Authorization: Bearer $OMNIROUTE_CODEX_KEY" http://127.0.0.1:20128/v1/models' | jq -r '.data[].id'`.
   Every combo member must be a provider-prefixed id (`<provider>/<model>`) of an API-key provider or `ollama/<model>`;
   never a bare id, never one from a flagged connection.
   - Codex and Hermes: `omniroute combo create "$FALLBACK_COMBO" --strategy priority --models "<api model>,<cheaper api model>,ollama/$FALLBACK_MODEL"` (drop the last member without a `FALLBACK_MODEL`).
   - Claude Code: `omniroute combo create "$FALLBACK_COMBO-claude" --strategy priority --models "<api model>,<cheaper api model>"`, API-key models with a context window of 100K or more only. Claude Code's local fallback is the separate `claude-ollama` choice.
   - Run `omniroute combo list` and check every member's prefix. If one comes from a flagged provider, stop and fix the combo. Phase 9 creates the OmniRoute profiles only after this passes.
   - Do not use the built-in `auto` model (it can route private code to keyless free providers).
7. Dashboard settings: Quota Preflight Cutoff → 10–15% remaining; Memory → off; Skills → off; Obsidian/Notion context
   sources → not configured; Thinking Budget → `passthrough` (Codex needs it); Compression → off or lite. If the dashboard
   offers a strict free-access policy (VERIFY the name, e.g. `freeAccessPolicy`/`excludeTosAvoid`), turn it on.
   MCP: `omniroute mcp status`, and `omniroute mcp disable` if it is on (110 tools; agents do not need it).
8. Verify: `~/.agents/stack/bin/agentstack doctor` shows `omniroute  inference requires an API key` (PASS) and no
   "reachable on the LAN" line.

## 4. Remove the conflicts

### 4.1 ruflo

Detect:

```bash
claude plugin list | grep -i ruflo; grep -n "Ruflo Integration" ~/.claude/CLAUDE.md
grep -l "hook-handler.cjs\|auto-memory-hook" ~/.claude/settings.json "$CODE_ROOT"/*/.claude/settings*.json 2>/dev/null
grep -l '"claude-flow"\|ruflo@\|@claude-flow/cli' "$CODE_ROOT"/*/.mcp.json 2>/dev/null
grep -ln 'claude-flow/cli\|ruflo' "$CODE_ROOT"/*/CLAUDE.md "$CODE_ROOT"/*/AGENTS.md "$CODE_ROOT"/*/.codex/AGENTS.override.md 2>/dev/null
grep -l 'Bash(node .claude/\*)\|mcp__claude-flow__' "$CODE_ROOT"/*/.claude/settings*.json 2>/dev/null
jq -r '.projects // {} | to_entries[] | select(.value.mcpServers["claude-flow"]) | .key' ~/.claude.json 2>/dev/null
grep -n "ruflo\|claude-flow" ~/.codex/config.toml ~/.gemini/config/mcp_config.json ~/.hermes/config.yaml 2>/dev/null
```

Both modes (back up every file first; **ASK** before editing files inside repos):

1. In each project `.claude/settings.json` found above, remove the hook entries whose command contains
   `.claude/helpers/hook-handler.cjs` or `.claude/helpers/auto-memory-hook.mjs`, and a ruflo `statusLine` (it overrides yours).
2. Project `.mcp.json` entries named `claude-flow` (they run `ruflo@latest` with all 300+ tools and beat the user-scope entry):
   delete the entry if the user owns the repo; if the file is shared with others, leave it and add
   `"disabledMcpjsonServers": ["claude-flow"]` to that repo's `.claude/settings.local.json` instead. Also run
   `(cd "$r" && claude mcp remove claude-flow --scope local)` for repos listed by the `jq` line.
3. Show the user any lines in a repo's CLAUDE.md/AGENTS.md that tell agents to use ruflo memory
   (`npx @claude-flow/cli@latest memory search|store`, memory_store/memory_search) and offer to replace them with one line:
   "Memory: use agentmemory (memory_smart_search / memory_save); see ~/.agents/AGENTS.md". Never rewrite the whole file.
4. `npx -y ruflo@3.56.0 mods uninstall` and `npx -y ruflo@3.56.0 spinner disable`.
5. `mkdir -p ~/.ruflo && echo '{"enabled": false}' > ~/.ruflo/funnel.json`.
6. Delete the `# Ruflo Integration` block from `~/.claude/CLAUDE.md` (show the user the diff).
7. Remove ruflo MCP entries from Codex (`codex mcp remove ruflo`), agy (`mcp_config.json`) and Hermes (`config.yaml`).

`RUFLO_MODE=orchestration`, then:

8. Uninstall ruflo Claude plugins (`claude plugin uninstall <name>@ruflo` for each one listed) so there is one
   registration only, and register the pinned, filtered MCP:
   `claude mcp remove claude-flow --scope user 2>/dev/null; claude mcp add --scope user --env CLAUDE_FLOW_MCP_TOOLS=swarm,agent,task,workflow --env RUFLO_FUNNEL=0 --env RUFLO_NO_AUTO_ENABLE=1 --transport stdio claude-flow -- npx -y ruflo@3.56.0 mcp start`
9. **ASK** before removing `Bash(node .claude/*)` from a repo's `permissions.allow`; keep `mcp__claude-flow__*`.

`RUFLO_MODE=remove`, then:

8. Uninstall every ruflo Claude plugin, `claude mcp remove claude-flow --scope user`.
9. In each ruflo repo, from its root: `npx -y ruflo@3.56.0 cleanup` prints a list and changes nothing. Show it.
   **ASK** per repo. Warn that `--force` deletes `.swarm/` (ruflo's memory database), `.claude-flow/`, `.hive-mind/`,
   `.claude/helpers/`, and any top-level `data/`, `memory/` and `coordination/`. Back up first:
   `bk=(); for p in .swarm .claude-flow .hive-mind .claude/helpers .claude/settings.json claude-flow.config.json .mcp.json data memory coordination; do [ -e "$p" ] && bk+=("$p"); done; [ ${#bk[@]} -gt 0 ] && tar -czf "$B/ruflo-$(basename "$PWD").tgz" "${bk[@]}" && chmod 600 "$B/ruflo-$(basename "$PWD").tgz"`.
   If the repo has its own `data/`, `memory/` or `coordination/`, never use `--force`: delete only `.swarm .claude-flow .hive-mind claude-flow.config.json`
   (and `.claude/helpers` if it holds `hook-handler.cjs`) by hand. Otherwise, after a yes: `npx -y ruflo@3.56.0 cleanup --force --keep-config`
   (`--keep-config` keeps `.claude/settings.json`, which step 1 already cleaned).

Verify: run `agentstack doctor` from inside each ruflo repo: no ruflo warnings. In orchestration mode `claude mcp get claude-flow`
there shows the user scope and `ruflo@3.56.0`.

### 4.2 Hindsight

Detect: `ls ~/.hindsight`, `claude mcp get hindsight`, Hindsight entries in `~/.claude/settings.json`, `~/.codex/hooks.json`,
`~/.gemini/config/hooks.json`, `claude plugin list | grep -i hindsight`, `grep -n provider ~/.hermes/config.yaml`, and the docker line from 1.3.

1. `npx -y @vectorize-io/hindsight-coding-agents@0.8.0 uninstall all` (removes its hooks, MCP entry and skill from Claude Code,
   Codex and agy). VERIFY with `agentstack doctor` afterwards; remove anything left by hand.
2. Legacy plugin: `claude plugin uninstall hindsight-memory@<marketplace>` if listed.
3. Hermes switches its memory provider to agentmemory in Phase 6.5.
4. Stop servers, keeping their data: `docker stop hindsight` if a container runs; embedded daemons run under named profiles,
   so stop each one: `uvx hindsight-embed@latest -p coding-agent daemon stop`, `uvx hindsight-embed@latest -p hermes daemon stop`,
   and `uvx hindsight-embed@latest daemon stop` (VERIFY the profile flag placement with `--help`).
   In `vault-brain` mode the container is replaced in Phase 7.5.

### 4.3 graphify hooks

graphify stays, but its per-tool-call hooks go (codebase-memory-mcp owns code navigation):

1. For each repo whose `.claude/settings.json` has a command containing `hook-guard`: in that repo run `graphify claude uninstall`
   (VERIFY; if the command does not exist, delete those hook entries by hand).
2. In each repo with `.codex/hooks.json` containing `graphify hook-check` (a deliberate no-op), remove that entry.
3. Leave graphify's `## graphify` sections in repo `AGENTS.md`/`CLAUDE.md` unless the user wants them gone.

### 4.4 Other duplicates

- If `obsidian-mind` hooks are present (doctor warns), **ASK** to remove them: they duplicate agentmemory's capture.
- agentmemory wired twice in one agent: Claude as plugin **and** in `~/.claude.json`/`settings.json` hooks, or Codex with global
  hooks in `~/.codex/hooks.json` **and** the plugin. Phases 6.2 and 6.3 keep the plugin only.

## 5. Code layer: codebase-memory-mcp (+ graphify for docs)

### 5.1 codebase-memory-mcp

1. One binary only. `which -a codebase-memory-mcp`, then `--version` on each copy, and
   `grep -rn "codebase-memory-mcp" ~/.claude.json ~/.codex/config.toml ~/.gemini/config/mcp_config.json ~/.hermes/config.yaml` (commands only).
   Mixed builds (npx, uvx, Homebrew, `~/.local/bin`) are refused by its daemon. If there is more than one copy, or a config runs
   it through `npx`/`uvx`, **ASK**, quit all agent sessions, run `"<old copy>" daemon stop` for each, and remove the extras with the
   package manager that installed them (`brew uninstall codebase-memory-mcp`, `npm uninstall -g codebase-memory-mcp`,
   `uv tool uninstall codebase-memory-mcp` or `pip uninstall codebase-memory-mcp`). Never use `codebase-memory-mcp uninstall` for
   this: it removes the agents' config entries.
2. Install or update to 0.11.0+: `curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash -s -- --skip-config`
   (**ASK**: this runs a remote script; show it first if the user wants).
3. `CBM="$HOME/.local/bin/codebase-memory-mcp"` (or `<dir>/codebase-memory-mcp` if `--dir` was used). Check `"$CBM" --version` and
   that `which -a codebase-memory-mcp` prints only that path; fix PATH order in the shell profile if not. Use `"$CBM"` below.
4. agy detection: the installer looks for `~/.gemini/antigravity-cli/` or an `antigravity` binary, not `agy`.
   If agy is installed: `mkdir -p ~/.gemini/antigravity-cli`.
5. Preview: `"$CBM" install --plan > ~/.agents/stack/cbm-plan.json` and summarize the files it will touch for the user.
6. Apply, only for agents that are installed: `"$CBM" install -y --clients=claude,codex,antigravity,hermes`
7. `"$CBM" config set auto_index true && "$CBM" daemon stop`
8. Index: for each repo in `$REPOS`: `"$CBM" cli index_repository --repo-path "$(git -C "$r" rev-parse --show-toplevel)"`.
9. Verify: `"$CBM" cli list_projects --format json` lists the repos; every codebase-memory-mcp `command` in the four agent configs
   equals `$CBM`; in Claude `/mcp` shows `codebase-memory-mcp` with 17 tools; after starting two agents,
   `~/.cache/codebase-memory-mcp/logs/daemon-conflicts.ndjson` gets no new lines. Codex and Hermes approve its hooks in Phase 10.

### 5.2 graphify (docs, papers, media)

1. `uv tool install --reinstall "graphifyy[mcp,ollama,pdf,watch]==0.9.82"` (the package name has two y's; other `graphify*` packages are not the project).
2. Add `export GRAPHIFY_NO_TIPS=1` to the shell profile.
3. `graphify install` (Claude skill; leaves `~/.claude/skills/graphify`) and `graphify install --platform agents` (writes
   `~/.agents/skills/graphify` for Codex, agy and Hermes). Add `"graphify"` to `claude_skip_skills` in `~/.agents/stack/config.json`.
4. Do **not** run `graphify claude install` or `graphify codex install` (they add the hooks removed in 4.3).
5. Optional per repo (**ASK**; the document pass sends docs to the chosen model):
   `OLLAMA_MODEL="$MEMORY_MODEL" graphify extract . --backend ollama && graphify cluster-only . --backend ollama`,
   then `graphify hook install` for free AST-only rebuilds on commit and checkout.

## 6. Session-memory layer: agentmemory

### 6.1 Daemon

1. **Version.** If `AM_OLD_VERSION` is newer than 0.9.30, keep it (read its changelog). If it is older or missing, **ASK**, then
   `npm install -g @agentmemory/agentmemory@0.9.30 @agentmemory/mcp@0.9.30`. Tell the user the first start after an upgrade runs
   data migrations, and that the Phase 1 archives are the way back.
2. **Embedding provider of the existing store** (key names only):
   `grep -E '^(EMBEDDING_PROVIDER|OPENAI_EMBEDDING_[A-Z_]+)=' ~/.agentmemory/.env; grep -oE '^[A-Z_]*API_KEY' ~/.agentmemory/.env`,
   and ask whether the shell agentmemory used to run in exported `OPENAI_API_KEY` (that silently enables OpenAI embeddings).
   - New store, or never had embeddings: `EMBEDDING_PROVIDER=local`.
   - Store with vectors from provider X: keep X, and pin it fully (for OpenAI: `EMBEDDING_PROVIDER=openai` plus the old
     `OPENAI_EMBEDDING_*` values), because the new `OPENAI_BASE_URL` line would otherwise send embeddings to Ollama. Keeping a
     remote provider means memory text keeps going there: tell the user.
   - Moving such a store to `local` is an **ASK** step: it discards the vectors (`AGENTMEMORY_DROP_STALE_INDEX=true` for one start, then remove it).
3. **Config before any start.** Merge `$KIT/templates/agentmemory/env` into `~/.agentmemory/.env` (keep existing keys; apply the
   provider from step 2), replace `__MEMORY_MODEL__` and `__VAULT__`, `mkdir -p "$VAULT/agentmemory"`, `chmod 600 ~/.agentmemory/.env`.
4. **Onboarding** only if `~/.agentmemory/secret` is missing: the user runs it once with a clean environment,
   `env -i HOME="$HOME" PATH="$PATH" TERM="$TERM" agentmemory`, finishes onboarding, then `agentmemory stop`.
   Re-check that `EMBEDDING_PROVIDER` in `.env` still holds the chosen value.
5. **Service.** Stop any agentmemory the user started by hand first, so only one daemon uses the store.
   - macOS: fill in `$KIT/templates/launchd/dev.agentstack.agentmemory.plist` (`__AGENTMEMORY_BIN__` = `command -v agentmemory`,
     `__NODE_DIR__` = `dirname "$(command -v node)"`, `__HOME__` = `$HOME`; add `AGENTMEMORY_DATA_DIR` if `AM_DATA_DIR` is not the
     default; for a legacy `data/state_store.db` set `WorkingDirectory` to its parent folder), save it as
     `~/Library/LaunchAgents/dev.agentstack.agentmemory.plist`, then
     `mkdir -p ~/.agents/stack/logs && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dev.agentstack.agentmemory.plist`.
   - Linux: fill in `$KIT/templates/systemd/agentmemory.service` (set or delete `AGENTMEMORY_DATA_DIR`) →
     `~/.config/systemd/user/agentmemory.service`, then `systemctl --user daemon-reload && systemctl --user enable --now agentmemory`.
6. Verify: `curl -fsS -H "Authorization: Bearer $(cat ~/.agentmemory/secret)" http://localhost:3111/agentmemory/livez`, and the
   viewer at http://localhost:3113 shows the old memories (not an empty store). Restart test:
   `launchctl kickstart -k gui/$(id -u)/dev.agentstack.agentmemory`, then livez again (VERIFY: no port clash with the detached engine).

### 6.2 Claude Code (plugin; one path only)

1. Remove the non-plugin wiring if present: `claude mcp remove agentmemory --scope user`, and hook entries in
   `~/.claude/settings.json` whose command contains `agentmemory`.
2. `claude plugin marketplace add rohitg00/agentmemory`, then `claude plugin install agentmemory@<marketplace name from claude plugin marketplace list>`
   (inside a session: `/plugin marketplace add rohitg00/agentmemory` and `/plugin install agentmemory`). The marketplace serves its
   latest commit, not 0.9.30; note the installed plugin version in the log.
3. Verify in a new session: `/mcp` lists agentmemory, and `/hooks` shows its hooks. Expect 8 tools because of `AGENTMEMORY_TOOLS=core`
   (VERIFY; 54 means the plugin ignores the daemon setting, which is acceptable).

### 6.3 Codex (plugin)

1. Remove the non-plugin wiring (the Phase 1 backup covers both files): `[mcp_servers.agentmemory]` and its `.env` subtable in
   `~/.codex/config.toml`, and every hook entry in `~/.codex/hooks.json` (or an inline `[hooks]` table) whose command contains
   `agentmemory`. Keep all other entries. Check `python3 -m json.tool ~/.codex/hooks.json`.
2. `codex plugin marketplace add rohitg00/agentmemory && codex plugin add agentmemory@agentmemory`
3. The user trusts the plugin hooks in Codex `/hooks` (Phase 10). If the plugin's hooks do not fire on this Codex version, the fallback
   is `agentmemory connect codex --with-hooks --force`, and then do not trust the plugin's hooks. One hook set only.

### 6.4 agy

1. `agentmemory connect antigravity-cli --with-hooks` (writes the MCP entry in `~/.gemini/config/mcp_config.json`, hooks in
   `~/.gemini/config/hooks.json`, and a guideline block in `~/.gemini/GEMINI.md`).
2. Edit the `agentmemory` entry in `~/.gemini/config/mcp_config.json` (back up first): set `"command"` to the absolute path of the
   pinned shim (`command -v agentmemory-mcp`) with `"args": []` instead of `npx -y @agentmemory/mcp`, and set
   `"env": {"AGENTMEMORY_FORCE_PROXY": "1"}`, so a down daemon fails visibly instead of writing to a private fallback store.
   If `~/.agentmemory/standalone.json` is not empty, tell the user: it holds memories written while the daemon was down.
3. **ASK**, then let agy call the memory and code tools without a prompt, so headless runs work. Merge into
   `~/.gemini/antigravity-cli/settings.json` with jq (keep its other keys):
   `"permissions": {"allow": ["mcp(agentmemory/memory_smart_search)", "mcp(agentmemory/memory_recall)", "mcp(agentmemory/memory_save)", "mcp(codebase-memory-mcp/*)"]}`.
   Server names must match the keys in `mcp_config.json`. If the user says no, run the agy drills interactively.
4. Verify: `/mcp` and `/hooks` inside agy.

### 6.5 Hermes (memory provider)

1. `git clone --depth 1 --branch v0.9.30 https://github.com/rohitg00/agentmemory ~/tools/agentmemory`
   (VERIFY the tag name with `git ls-remote --tags`; else clone and check out the 0.9.30 commit).
2. `mkdir -p ~/.hermes/plugins && cp -R ~/tools/agentmemory/integrations/hermes ~/.hermes/plugins/agentmemory`
3. `hermes config set memory.provider agentmemory` (only one external provider can be active; this replaces Hindsight).
4. Do **not** also add agentmemory as an MCP server in Hermes: the provider already gives `memory_recall`, `memory_save` and
   `memory_search` (Hermes has no `memory_smart_search`; the shared rules say so).
5. Tell the user: this provider searches memory before **every** Hermes model call and adds the project profile, with no off switch.
   The alternative is the agentmemory MCP in Hermes instead of the provider, which loses automatic capture. They choose.
6. Verify: `hermes plugins doctor` and `hermes memory status`.

### 6.6 Shell environment

Add to `~/.zshrc` (or `~/.bashrc`):

```bash
export CLAUDE_OBSIDIAN_VAULT="<VAULT as a literal path>"
export GRAPHIFY_NO_TIPS=1
[ -f ~/.agents/stack/secrets.env ] && . ~/.agents/stack/secrets.env
# only if AM_INJECT=true (hooks read it from the environment the agent is launched from):
# export AGENTMEMORY_INJECT_CONTEXT=true
# only if AM_PRECOMPACT_BUDGET is not 1500 (VERIFY the name: grep the installed package for PRE_COMPACT_BUDGET):
# export AGENTMEMORY_PRE_COMPACT_BUDGET=0
```

## 7. Notes layer: Obsidian vault + claude-obsidian

Re-run the Python 3.11 check from 1.1 first; skip steps 1–4 if it fails.

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
   Add its skill names to `claude_skip_skills` (Claude has the plugin versions): `wiki`, `save`, `wiki-ingest`, `wiki-query`,
   `wiki-lint`, `autoresearch`, `canvas`, `defuddle`, `wiki-fold`, `wiki-mode`, `wiki-retrieve`, `wiki-cli`, `obsidian-markdown`,
   `obsidian-bases`, `think`. Hermes can edit skills inside `external_dirs`, so protect the checkout:
   `chmod -R a-w ~/tools/claude-obsidian/skills` (run `chmod -R u+w` before a `git pull`).
5. Claude settings: add `"CLAUDE_OBSIDIAN_VAULT": "<VAULT>"` to the `env` block of `~/.claude/settings.json`.
   Only if `HOT_INJECT=true`, also add `"CLAUDE_OBSIDIAN_SESSION_CONTEXT": "1"` and `"CLAUDE_OBSIDIAN_SESSION_CONTEXT_VAULT": "<VAULT>"`.
   The product treats this as explicit consent; never set it without the user's yes.
6. Generated content gets its own folders, so it never mixes with curated wiki pages: `<VAULT>/agentmemory/` (agentmemory export;
   its export root points there) and `<VAULT>/graphify/<repo>/` (graphify export). Lint with `--exclude 'agentmemory/**' --exclude 'graphify/**'`.
7. Backup: **ASK** whether to use claude-obsidian `checkpoint` commits or the obsidian-git plugin; use only one. If the vault is a
   git repo, add `.obsidian/plugins/obsidian-local-rest-api/data.json` (it holds the REST API key) to the vault's `.gitignore`,
   and ask whether `agentmemory/` and `graphify/` should be ignored too.
8. `OBSIDIAN_MCP=yes` only: the user installs the "Local REST API" community plugin in Obsidian and puts its key into
   `OBSIDIAN_API_KEY` in `secrets.env`. Then, using shell expansion only:
   - Claude: `bash -c '. ~/.agents/stack/secrets.env; claude mcp add --transport http obsidian https://127.0.0.1:27124/mcp/ --header "Authorization: Bearer ${OBSIDIAN_API_KEY}" --scope user'`,
     and add `"mcp__obsidian__vault_delete"` and `"mcp__obsidian__command_execute"` to `permissions.deny` in `~/.claude/settings.json`.
   - Codex: `[mcp_servers.obsidian]` with `url = "https://127.0.0.1:27124/mcp/"`, `bearer_token_env_var = "OBSIDIAN_API_KEY"`, `disabled_tools = ["vault_delete", "command_execute"]`.
   - agy (no env expansion in its config, so the key is stored in plain text there; tell the user):
     `bash -c '. ~/.agents/stack/secrets.env; f=~/.gemini/config/mcp_config.json; jq --arg h "Bearer $OBSIDIAN_API_KEY" ".mcpServers.obsidian={serverUrl:\"https://127.0.0.1:27124/mcp/\",headers:{Authorization:\$h},disabledTools:[\"vault_delete\",\"command_execute\"]}" "$f" > "$f.new" && mv "$f.new" "$f" && chmod 600 "$f"'`
   - Hermes: `mcp_servers.obsidian` with `url`, `headers.Authorization: "Bearer ${OBSIDIAN_API_KEY}"` and `trust: untrusted`;
     `bash -c '. ~/.agents/stack/secrets.env; umask 077; printf "OBSIDIAN_API_KEY=%s\n" "$OBSIDIAN_API_KEY" >> ~/.hermes/.env'`.
   - TLS: trust the plugin's certificate (https://127.0.0.1:27124/obsidian-local-rest-api.crt) in Keychain, or enable its HTTP port
     27123 and use `http://127.0.0.1:27123/mcp/`.

### 7.5 Hindsight vault brain (`HINDSIGHT_MODE=vault-brain` only)

1. Existing container: if `docker ps -a` shows `hindsight`, log `docker inspect hindsight --format '{{json .Mounts}} {{.Config.Image}}'`,
   **ASK**, then `docker stop hindsight && docker rename hindsight hindsight-old-$TS` (keeps every volume; never `docker rm -v`).
   Reuse its `/home/hindsight/.pg0` volume as `HS_VOL` (else `hindsight-data`) and keep its embedding settings: the embedding
   dimension is fixed once data exists.
2. Image: `docker manifest inspect ghcr.io/vectorize-io/hindsight:0.10.3 >/dev/null` (VERIFY the tag exists); if not,
   `docker pull ghcr.io/vectorize-io/hindsight:latest` and pin the digest: `IMG=$(docker inspect --format '{{index .RepoDigests 0}}' ghcr.io/vectorize-io/hindsight:latest)`.
   Use the full image (about 3.7 GB on arm64, 9 GB on amd64). The slim image has no local embedder or reranker.
3. macOS (Docker Desktop):
   ```bash
   docker run -d --name hindsight --restart unless-stopped -p 127.0.0.1:8888:8888 -p 127.0.0.1:9999:9999 \
     -e HINDSIGHT_API_LLM_PROVIDER=ollama -e HINDSIGHT_API_LLM_BASE_URL=http://host.docker.internal:11434/v1 \
     -e HINDSIGHT_API_LLM_MODEL="$MEMORY_MODEL" -e HINDSIGHT_API_LLM_STRICT_SCHEMA=true \
     -e HINDSIGHT_API_RETAIN_MAX_COMPLETION_TOKENS=16000 -e HINDSIGHT_API_MCP_ENABLED_TOOLS=recall,reflect \
     -v "$HS_VOL":/home/hindsight/.pg0 "$IMG"
   ```
   Linux: the container cannot reach Ollama on 127.0.0.1 through `host.docker.internal`. Either run the API without Docker
   (`python3 -m venv ~/.agents/stack/hindsight-venv && ~/.agents/stack/hindsight-venv/bin/pip install hindsight-api==0.10.3`, then start
   `hindsight-api` with `HINDSIGHT_API_HOST=127.0.0.1`, `HINDSIGHT_API_LLM_BASE_URL=http://127.0.0.1:11434/v1` and the other variables above
   as a login service), or use `docker run --network host -e HINDSIGHT_API_HOST=127.0.0.1 -e HINDSIGHT_API_LLM_BASE_URL=http://127.0.0.1:11434/v1 ...`
   without `-p` flags and check with `ss -ltnp | grep -E ':(8888|9999)\b'` that both ports show 127.0.0.1 (if the UI does not, use the venv).
4. One-way sync of the vault into a bank: `npm install -g @vectorize-io/hindsight-obsidian`, then
   `hindsight-obsidian-sync reconcile --vault "$VAULT" --bank obsidian --api-url http://localhost:8888` once; check `docker logs hindsight`
   for errors and that a recall through the MCP returns a vault note. Then run it with `--watch` as a login service (like 6.1).
5. Register the read-mostly MCP in each agent as `hindsight-vault` → `http://localhost:8888/mcp/obsidian/`
   (Claude `--transport http`, Codex `url =`, agy `serverUrl`, Hermes `url:`). Phase 8.1 adds it to the shared rules.
6. After the user confirms everything works, offer `docker rm hindsight-old-$TS` (never with `-v`).

## 8. Rules and skills for every agent

1. Shared rules: render to a temp file, `sed "s#__VAULT__#$VAULT#g" "$KIT/shared/AGENTS.md" > ~/.agents/stack/AGENTS.md.new`
   (literal vault path). In `vault-brain` mode add this row to its "Where knowledge lives" table:
   `| Meaning-based search over the notes | hindsight-vault (recall, reflect) | |`.
   If `~/.agents/AGENTS.md` exists, show `diff -u` and back it up; then move the new file into place.
2. Shared skill: `cp -R "$KIT/shared/skills/agent-handoff" ~/.agents/skills/`
3. Preview, then apply: `~/.agents/stack/bin/agentstack sync --check` and `~/.agents/stack/bin/agentstack sync`.
   This adds `@~/.agents/AGENTS.md` to `~/.claude/CLAUDE.md`, writes managed blocks into `~/.codex/AGENTS.md` (or
   `AGENTS.override.md` if that is in use), `~/.gemini/AGENTS.md` and `~/.hermes/SOUL.md`, and links each skill into
   `~/.claude/skills` (except `claude_skip_skills`) and `~/.gemini/antigravity-cli/skills`. It writes through symlinked files,
   and leaves alone a rules file that is a link to `~/.agents/AGENTS.md`.
4. Hermes `~/.hermes/config.yaml` (edit by hand, back up first; see `$KIT/templates/hermes/omniroute.yaml`):
   `skills.external_dirs: [~/.agents/skills]` and `skills.write_approval: true`. Run `agentstack sync` again; it must report `hermes skills  ok`.
   Then `hermes skills list` must show `agent-handoff` **and** a claude-obsidian skill such as `wiki` (those are symlinks;
   VERIFY Hermes follows them; if not, ask the user whether to copy them into `~/.hermes/skills/`).
5. Claude reads a repo's `AGENTS.md` only when the repo has no `CLAUDE.md`. To make Claude read both, **ASK**, then add to
   `~/.claude/settings.json`: `"pluginConfigs": {"cc-plugin-agents-md@builtin": {"options": {"instructionFiles": "claude-md-and-agents-md"}}}`.
6. agy skills: start `agy` interactively and run `/skills`; it must list `agent-handoff` (the research does not document a
   headless skills listing). VERIFY: if symlinked skills are missing, set `"agy_skills_mode": "copy"` in `config.json`, delete the
   links in `~/.gemini/antigravity-cli/skills/`, and run `agentstack sync` again. In copy mode, sync refreshes the copies it made
   and never overwrites a copy that was edited by hand.

## 9. Usage-limit switcher and fallback profiles

1. Claude hooks and status line: `~/.agents/stack/bin/agentstack install --agent claude --dry-run`, show the diff, then run it
   without `--dry-run`. An existing status line is kept and shown in front of the usage figures; uninstall restores it.
2. Codex SessionStart hook: `~/.agents/stack/bin/agentstack install --agent codex` (trust it in `/hooks` later).
3. agy status line (optional, **ASK**): `~/.agents/stack/bin/agentstack install --agent agy`. It shows agy's remaining quota and
   opens the picker at the thresholds too. VERIFY: agy's status line JSON has no documented folder field, so check once that a
   threshold popup from agy opens in the right repo.
4. `AUTO_CONTINUE=false`: set `"autoContinueAtUsageLimit": false` in `~/.claude/settings.json`.
5. Claude Code on Ollama (only with a `FALLBACK_MODEL`): `ollama launch claude --model "$FALLBACK_MODEL" --yes -- -p "say ok"` must answer.
   Then start `ollama launch claude --model "$FALLBACK_MODEL"` interactively and run `/mcp`: codebase-memory-mcp and agentmemory must
   be listed. VERIFY: an Ollama issue reported MCP tools missing under `ollama launch`. If they are missing, try
   `ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" ANTHROPIC_BASE_URL=http://localhost:11434 claude --model "$FALLBACK_MODEL"`;
   if `/mcp` lists them there, set `"claude_ollama_mode": "env"` in `~/.agents/stack/config.json` and confirm with
   `AGENTSTACK_DRY_RUN=1 ~/.agents/stack/bin/agentstack switch --cwd "$SCRATCH" --pick claude-ollama --no-handoff` (the launcher runs `env ANTHROPIC_... claude --model ...`).
6. Claude Code via OmniRoute (only after 3.2.6 passed):
   ```bash
   bash -c '. ~/.agents/stack/secrets.env; umask 077; sed -e "s#__OMNIROUTE_CLAUDE_KEY__#${OMNIROUTE_CLAUDE_KEY}#" \
     -e "s#__CLAUDE_COMBO__#<FALLBACK_COMBO>-claude#g" -e "s#__FALLBACK_SMALL_MODEL__#<prefixed API-key small model>#" \
     -e "s#__FALLBACK_CONTEXT__#<smallest context window of the combo, 100000-1000000>#" \
     "$KIT/templates/claude/omniroute.settings.json" > ~/.claude/omniroute.settings.json'
   ```
   If the key contains `#`, `&` or `\`, leave `__OMNIROUTE_CLAUDE_KEY__` in the file and let the user paste the key there
   in their own editor. The small model must also be a prefixed API-key id, never a bare `claude-*` id. Test: `claude --settings ~/.claude/omniroute.settings.json -p "say ok"`.
   If you get 400 errors about betas or `context_management`, add `"CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1"` to its env.
7. Codex via OmniRoute: append `$KIT/templates/codex/omniroute-provider.toml` to `~/.codex/config.toml` (only if no
   `[model_providers.omniroute]` exists), save `$KIT/templates/codex/omniroute.config.toml` as `~/.codex/omniroute.config.toml` with
   `$FALLBACK_COMBO`. `OMNIROUTE_CODEX_KEY` comes from `secrets.env` through the shell profile. Test: `codex exec --profile omniroute "say ok"`.
8. Hermes: add the `providers.omniroute` block from `$KIT/templates/hermes/omniroute.yaml`, then
   `bash -c '. ~/.agents/stack/secrets.env; umask 077; printf "OMNIROUTE_HERMES_KEY=%s\n" "$OMNIROUTE_HERMES_KEY" >> ~/.hermes/.env; chmod 600 ~/.hermes/.env'`.
   The user runs `hermes fallback add` and picks the omniroute provider and `$FALLBACK_COMBO`.
   Test: `hermes -z "say ok" --provider custom:omniroute -m "$FALLBACK_COMBO"` (VERIFY the provider name format).
9. agy stays on its own Google login. Do not point it at OmniRoute.
10. Picker test: `~/.agents/stack/bin/agentstack switch --cwd "$SCRATCH" --reason "Setup test"`. A dialog lists the installed agents.
    Pick "Keep using the current agent". The first run on macOS may ask to allow automation; allow it.
11. Launch test: `~/.agents/stack/bin/agentstack switch --cwd "$SCRATCH" --pick codex --reason "Setup test"`. A new terminal opens in
    the scratch repo and Codex starts with the resume prompt. If an agent fails to start, its window stays open with the error.
12. Clean up: `rm -f ~/.agents/stack/state/handoff-request.json ~/.agents/stack/state/fired/*` and `rm -f "$SCRATCH/HANDOFF.md"`.

## 10. Verify end to end

1. `~/.agents/stack/bin/agentstack doctor`: no FAIL lines. Go through every WARN with the user.
   Also `grep -n memories ~/.codex/config.toml` shows nothing or `false` (Codex's own memories stay off).
2. **Manual approvals the user must do** (list them clearly at the end):
   - Codex: open `codex`, run `/hooks`, trust the codebase-memory, agentmemory and agentstack hooks.
   - Hermes: `hermes hooks list` and approve the codebase-memory `pre_llm_call` hook once (interactive), then `hermes hooks doctor`.
   - Obsidian: only for `OBSIDIAN_MCP=yes`, install the Local REST API plugin in the app.
   - OmniRoute dashboard items from 3.2 that the user has not done yet, and filling in `secrets.env`.
3. **Memory round trip.** In Claude Code: "Save a memory: agent-stack drill word is `<pick a random word>`."
   - Codex: `codex exec "Use memory_smart_search for 'agent-stack drill' and print the drill word."`
   - agy: `agy -p "Use memory_smart_search for 'agent-stack drill' and print the drill word." --output-format json --print-timeout 5m < /dev/null 2>/tmp/agy-drill.err`.
     PASS only if `.response` contains the word and `/tmp/agy-drill.err` has no permission or soft-deny notice (exit code 0 alone proves nothing).
   - Hermes: `hermes -z "Use memory_search for 'agent-stack drill' and print the drill word."`
   Each must print the word.
4. **Code graph.** In each agent ask: "Use codebase-memory-mcp search_graph to find the function `<a real function>` in this repo."
5. **Handoff drill** in `$SCRATCH`: in Claude Code started there, "Use the agent-handoff skill to write a handoff for a fake task."
   Then `~/.agents/stack/bin/agentstack switch --cwd "$SCRATCH" --pick codex --from claude --reason drill`. Codex must quote the
   narrative on its first answer. Back in the Claude window, the next prompt must be blocked with a "handed to Codex CLI" message;
   a prompt starting with `reclaim` must go through. Set `status: done` afterwards.
6. **Threshold drill** in `$SCRATCH`:
   `echo '{"model":{"display_name":"Drill"},"workspace":{"current_dir":"'"$SCRATCH"'"},"rate_limits":{"five_hour":{"used_percentage":86,"resets_at":"drill-1"}}}' | ~/.agents/stack/bin/agentstack statusline`
   The picker must appear and name the scratch repo. Clean up as in 9.12.
7. **Status line.** Start Claude Code and send one message. The status line must show `5h NN%` after the first reply. If it never
   does, the `rate_limits` bug applies: the 85% popup cannot fire, but the at-limit path (`StopFailure`) still works. Tell the user and
   check again after a Claude Code update.

## 11. Self-checks for each agent

The user pastes the line into that agent after Phase 10. Each agent checks only its own wiring and fixes only what is listed for it.

**Codex:** `Read agent-stack/SETUP-PLAYBOOK.md section 11 "Codex" and run those checks.`
- `codex mcp list` includes `codebase-memory-mcp`; agentmemory comes from the plugin (`/plugins`); no `[mcp_servers.agentmemory]` and no agentmemory entries in `~/.codex/hooks.json`.
- `/skills` lists `agent-handoff`, `graphify` and the claude-obsidian skills (from `~/.agents/skills`).
- `~/.codex/AGENTS.md` (or `AGENTS.override.md`) contains the `agent-stack:begin` block. `/hooks` shows trusted codebase-memory, agentmemory and agentstack hooks.
- `memory_smart_search "agent-stack drill"` returns the drill memory.
- `codex --profile omniroute` starts if the OmniRoute fallback was set up.

**agy:** `Read agent-stack/SETUP-PLAYBOOK.md section 11 "agy" and run those checks.`
- `/mcp` lists `codebase-memory-mcp` and `agentmemory` (absolute `agentmemory-mcp` command, `AGENTMEMORY_FORCE_PROXY=1`); no `hindsight`.
- `/skills` lists `agent-handoff` (else switch to copy mode, see 8.6).
- `~/.gemini/AGENTS.md` has the `agent-stack:begin` block; `/hooks` shows agentmemory's 4 hooks.
- Memory round trip as in 10.3.

**Hermes:** `Read agent-stack/SETUP-PLAYBOOK.md section 11 "Hermes" and run those checks.`
- `hermes memory status` shows provider `agentmemory`; `hermes mcp list` shows `codebase-memory-mcp` and no `agentmemory`/`hindsight` MCP.
- `hermes skills list` includes `agent-handoff` and `wiki`; `skills.write_approval` is true.
- `~/.hermes/SOUL.md` has the `agent-stack:begin` block. `hermes hooks doctor` is clean.
- The primary provider is not the Anthropic OAuth login. The model's context window is 64K or more (Hermes refuses smaller ones).

**Claude Code on Ollama:** start it the way chosen in 9.5, run `/mcp` (codebase-memory-mcp, agentmemory), and ask it to read
`HANDOFF.md` in `$SCRATCH` after a handoff drill. Small local models handle many tool schemas poorly; a bigger model helps more than
trimming tools.

## 12. Maintenance and rollback

- **Weekly:** `~/.agents/stack/bin/agentstack doctor`.
- **After editing** `~/.agents/AGENTS.md`, or adding, editing or removing a skill in `~/.agents/skills`: `agentstack sync`.
- **Updating a tool:** read its changelog, then:
  - codebase-memory-mcp: `curl -fsSL .../install.sh | bash -s -- --skip-config`, then `"$CBM" install --plan`, review, and
    `"$CBM" install -y --clients=<the same list as in 5.1>`; `which -a` must still show one copy; restart every agent session and
    re-trust Codex hooks if asked.
  - agentmemory: back up the store (as in 1.2), `npm install -g @agentmemory/agentmemory@<v> @agentmemory/mcp@<v>`, restart the service,
    re-run `agentmemory connect antigravity-cli --with-hooks --force` and then repeat 6.4 step 2 (the connector resets the command and
    env), update the Hermes plugin copy from the new tag.
  - graphify: `uv tool upgrade graphifyy`, then `graphify hook install` again in repos that use the git hooks.
  - agentstack: copy the new `bin/agentstack`, run its tests, then `agentstack install --agent claude` and `--agent codex` again (idempotent).
- **Hand a repo back to Claude:** a Claude prompt that starts with `reclaim`, or `agentstack reclaim --cwd <repo>`.
- **Turn the switcher off:** `agentstack uninstall --agent claude`, `--agent codex`, `--agent agy`. Your previous status line comes back.
- **Full rollback:** stop the agentmemory service (`launchctl bootout gui/$(id -u)/dev.agentstack.agentmemory` or
  `systemctl --user disable --now agentmemory`), reinstall `@agentmemory/agentmemory@$AM_OLD_VERSION` if it changed, restore the
  `agentmemory-data-*.tgz` archives to the paths in `agentmemory-data.index`, then restore `configs.tgz` with `tar -xzf configs.tgz -C /`
  after showing the user what it will overwrite. File backups that agentstack itself made are in `~/.agents/stack/backups/files/`.
