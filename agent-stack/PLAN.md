# Agent stack plan: one shared memory for Claude Code, Codex, agy, Hermes and Ollama

Researched 2026-10-09 against the current releases of every tool (versions at the end).
The setup steps are in [SETUP-PLAYBOOK.md](SETUP-PLAYBOOK.md); this file explains the design.

## Short answer

Yes, your tools can share one memory, and the usage-limit popup works too. The rule that makes it
work: **one owner for each kind of knowledge, and every agent connects to the same owners.**

At the moment several of your tools do the same job. agentmemory, Hindsight and ruflo all record
sessions and push memory into the prompt. codebase-memory-mcp and graphify both index code and both
hook into every Grep and Read. When all of them are on, every prompt carries two or three memory
injections, every tool call is recorded twice, and the agents split facts across stores that do
not know about each other. The plan picks one tool per job, turns the duplicates off, and adds a
small glue script (`agentstack`) for the handoff file and the "pick an agent" popup.

```
                 Claude Code      Codex        agy        Hermes     (+ Claude Code on Ollama / OmniRoute)
                      │             │           │            │
   rules + skills ────┴─── ~/.agents/AGENTS.md + ~/.agents/skills (agentstack sync copies them to each agent)
                      │             │           │            │
   ┌──────────────────┼─────────────┼───────────┼────────────┼───────────────────────────────┐
   │ CODE             │ SESSIONS + HANDOFFS     │ NOTES                  │ MODELS               │
   │ codebase-memory- │ agentmemory daemon      │ Obsidian vault         │ OmniRoute gateway    │
   │ mcp (one daemon, │ (:3111, hooks record    │ + claude-obsidian      │ (API keys only)      │
   │ one index)       │ every agent)            │ (curated, readable)    │ + Ollama (local)     │
   │ graphify: docs,  │ HANDOFF.md in each repo │ hindsight: optional    │                      │
   │ papers, media    │                         │ search over the vault  │                      │
   └──────────────────┴─────────────────────────┴────────────────────────┴──────────────────────┘
        agentstack: status line watches Claude usage → popup at 85% / at the limit → new terminal
```

## Verdict for each tool

| Tool | Job in the stack | Verdict | Why |
|---|---|---|---|
| **codebase-memory-mcp** 0.11.0 | Code structure for every agent | **Keep, primary** | One per-user daemon serves all agents from one index, so Codex sees exactly what Claude saw. No LLM calls, no cost. Its installer configures Claude Code, Codex, Antigravity and Hermes. |
| **agentmemory** 0.9.30 | Session memory and handoff record | **Keep, primary** | The only tool here that records automatically in all four agents (Claude plugin: 12 hooks, Codex plugin: 6, agy: 4, Hermes memory provider). Works without an LLM. Every agent working in the same repo writes to the same project. You already use its `memory_*` tools. |
| **Obsidian + claude-obsidian** 2.2.0 | Curated notes and wiki you can read yourself | **Keep** | One vault serves every agent. The skills are plain `SKILL.md`, so Codex, agy and Hermes can use them. Writes are reviewed transactions, so agents cannot silently overwrite pages. |
| **graphify** 0.9.82 | Docs, papers and media graph, `GRAPH_REPORT.md`, Obsidian export | **Keep, demoted** | For code it duplicates codebase-memory-mcp, and its hooks on every Grep/Read compete with codebase-memory-mcp's. Remove the hooks and keep the CLI and skill. Run its document pass on Ollama, not on your Claude quota. |
| **Hindsight** 0.10.3 | Optional: semantic search over the vault | **Remove its hooks; optionally keep the server** | It is a second session-memory system on the same hook events as agentmemory, so capture is doubled, and it calls an LLM on every save. The full image is 3.7–9 GB. A non-interactive install defaults to Hindsight Cloud. Optional "vault brain" mode keeps the server for search and reflect over Obsidian notes, without hooks. |
| **ruflo** 3.56.0 | Optional: Claude-only orchestration | **Out of the memory layer** | It injects ranked memory into every prompt, rewrites Claude's MEMORY.md, exposes 300+ tools, writes to global files, and every config it generates runs `@latest` (releases are daily). Independent audits found many stubbed features. Keep it only as a pinned orchestration MCP if you use swarms; otherwise remove it. |
| **OmniRoute** 3.8.51 | Model gateway for fallback, LLM endpoint for memory tools | **Keep, models only** | Good at fallback chains and quota-aware routing. Turn off its memory, skills and Obsidian features, which would make a fourth memory store. Connect only API keys and local Ollama (see Terms of service). |
| **Ollama** 0.40.2 | Free local fallback, LLM for memory tools | **Keep** | `ollama launch claude` runs Claude Code itself on a local model, so hooks, skills and memory keep working after a switch. Needs a 64K context setting. |

## How each agent connects

| | Rules | Skills | Code graph | Session memory | Notes | Fallback model | Usage signal |
|---|---|---|---|---|---|---|---|
| **Claude Code** | `~/.claude/CLAUDE.md` imports `@~/.agents/AGENTS.md` | links in `~/.claude/skills` | installer (`claude`) | agentmemory plugin | claude-obsidian plugin | Ollama (`ollama launch claude`) or OmniRoute (`claude --settings ~/.claude/omniroute.settings.json`) | status line `rate_limits`, `StopFailure` hook |
| **Codex** | managed block in `~/.codex/AGENTS.md` | reads `~/.agents/skills` natively | installer (`codex`) | agentmemory Codex plugin | claude-obsidian skills | `codex --profile omniroute`, `codex --oss` | `/status`, no hook |
| **agy** | managed block in `~/.gemini/AGENTS.md` | links in `~/.gemini/antigravity-cli/skills` | installer (`antigravity`) | `agentmemory connect antigravity-cli --with-hooks` | claude-obsidian skills | its own Google login only | status line `quota.*.remaining_fraction` |
| **Hermes** | managed block in `~/.hermes/SOUL.md` | `skills.external_dirs: [~/.agents/skills]` | installer (`hermes`) | agentmemory memory-provider plugin | claude-obsidian skills | `fallback_providers` → OmniRoute | `hermes usage`, automatic fallback |
| **Ollama** | (through the agent running on it) | same | same | same | same | is the fallback | none (local) |

Why each rules file is different: Claude reads `CLAUDE.md` (and imports), Codex reads
`~/.codex/AGENTS.md`, agy reads `~/.gemini/AGENTS.md`, and Hermes has no global AGENTS.md (it
loads `SOUL.md`). `agentstack sync` writes the same text into each of them between
`agent-stack:begin/end` markers and leaves the rest of each file alone.

The project key is the git repo folder name. agentmemory derives it the same way in every
agent, and codebase-memory-mcp derives its own key from the absolute path. Both rules hold only
when you **start agents from the repo root**. A second clone or a git worktree counts as a
different project.

## What happens near the limit

1. **Normal work.** Every agent records into agentmemory. codebase-memory-mcp keeps the code
   graph fresh while a session is open.
2. **5-hour usage reaches 85%.** The Claude status line notices and a popup asks:
   *Continue this work in: Codex / agy / Hermes / Claude Code on Ollama / Claude Code via OmniRoute
   / Keep using the current agent.* On your next prompt Claude is told once that a handoff is due.
   It then saves a `handoff:` memory and fills in the narrative of `HANDOFF.md`.
3. **You pick an agent.** Best at the 95% popup, after Claude has written the narrative. If you
   pick at the first popup, stop Claude first (Esc); the popup warns you when the narrative is still
   empty. agentstack refreshes the auto-captured part of `HANDOFF.md` (branch, uncommitted changes,
   recent commits, Claude's last message), opens a new terminal in the repo, and starts the agent
   with: *read HANDOFF.md, search shared memory for this project's handoff, check the code graph,
   tell me the next step before changing code.* The note records which agent now owns the repo.
4. **If you hit the hard limit without switching**, the `StopFailure` hook writes `HANDOFF.md`
   from git and Claude's last message, then shows the picker again.
5. **The new agent** sees the handoff. Claude Code and Codex get it injected by a SessionStart
   hook; agy and Hermes follow the shared rule "read HANDOFF.md first". It recalls agentmemory and
   queries the same code graph.
6. **The old Claude session is blocked** in that repo, so two agents never edit the same files.
   If you go back to it, a message starting with `reclaim` takes the repo back (or run
   `agentstack reclaim`). When the new agent writes its own handoff, the block lifts.
7. **When the task is done**, the agent sets `status: done` in `HANDOFF.md`. The next handoff
   archives the finished note to `~/.agents/stack/state/handoff-archive/`.

`HANDOFF.md` is added to `.git/info/exclude`, so it never shows up in commits. agentstack never
writes, reads or injects a `HANDOFF.md` that git tracks, or one it did not write on this machine (it keeps a registry of
the notes it wrote). A cloned repo
that ships its own `HANDOFF.md` cannot slip instructions into your agents this way. Even its own
notes are injected as data ("check this against git"), without the quoted last message.

Watch out: by default Claude Code waits and continues by itself after the limit resets
(`autoContinueAtUsageLimit`). The playbook turns that off while you use the switcher. The owner
block covers the next prompt you type, not a turn Claude continues on its own.

## Hooks that remain after setup

| Agent | Event → what runs |
|---|---|
| Claude Code | SessionStart: codebase-memory reminder, agentmemory, agentstack handoff note · UserPromptSubmit: agentmemory capture, agentstack guard (silent unless a handoff is due or the repo was handed away) · PreToolUse/PostToolUse: codebase-memory context, agentmemory capture · PreCompact: agentmemory (captures, and injects up to 1500 tokens of memory) · Stop/SessionEnd: agentmemory · StopFailure: agentstack · status line: agentstack (your old status line is kept and shown in front) |
| Codex | SessionStart: codebase-memory, agentmemory, agentstack · UserPromptSubmit/PreToolUse/PostToolUse/Stop: agentmemory · PreCompact: agentmemory (injects up to 1500 tokens) |
| agy | PreInvocation/PreToolUse/PostToolUse/Stop: agentmemory · status line: agentstack (optional) |
| Hermes | pre_llm_call: codebase-memory · memory provider: agentmemory (searches memory before every model call and adds the project profile; no off switch while it is the provider) |
| Removed | Hindsight (Claude, Codex, agy, Hermes provider), ruflo hooks and mods, graphify `hook-guard` and its Codex no-op hook |

## Services and ports

| Service | Port | Bind | Started by |
|---|---|---|---|
| OmniRoute API and dashboard | 20128 (live socket 20129) | 127.0.0.1, API key required | `omniroute autostart enable` |
| agentmemory REST/MCP, viewer, engine | 3111, 3113 (3112, 49134) | 127.0.0.1, bearer token in `~/.agentmemory/secret` | launchd / systemd (template here) |
| Ollama | 11434 | 127.0.0.1 | Ollama app / service |
| codebase-memory-mcp | none (stdio + local daemon socket); UI 9749 optional | local | first MCP session |
| Obsidian Local REST API (optional) | 27124 https | 127.0.0.1 | Obsidian app |
| Hindsight (optional vault brain) | 8888 API, 9999 UI | must be 127.0.0.1 (Docker publishes on all interfaces unless told) | Docker |
| graphify MCP over HTTP (not used) | 8080 | 127.0.0.1 | n/a |

## Terms of service and safety

These are the parts that can cost you an account. Quotes are from the providers' own pages
(fetched 2026-10-09).

- **Anthropic.** OAuth login "is intended exclusively for purchasers of Claude Free, Pro, Max,
  Team, and Enterprise subscription plans and is designed to support ordinary use of Claude Code
  and other native Anthropic applications". Also: "developers may not collect, store, or
  intermediate Claude.ai credentials or session tokens", and Anthropic may enforce this "without
  prior notice". So: **do not connect your Claude subscription inside OmniRoute** (its
  `claude`/`cc` providers store the token and imitate the Claude Code client), and do not feed it
  to other agents. That includes Hermes's built-in "Anthropic OAuth" login (`hermes model` →
  Anthropic), which stores your Claude login, routes as Claude Code and bills extra-usage credits.
  Give Hermes an API key, its own ChatGPT login, OmniRoute or Ollama instead. Claude Code on its
  own login is fine. Claude Code pointed at OmniRoute with an OmniRoute key that routes to other
  models or to your own Anthropic API key is allowed: unsupported by Anthropic, not forbidden.
- **Google Antigravity.** Terms §6: "Using third party software, tools, or services to access the
  Service (e.g. using OpenClaw with Antigravity OAuth) is a breach of this Agreement." Mass
  suspensions happened in February 2026. **Never add your Google login to OmniRoute**
  (`antigravity`/`agy` providers) and never use its Antigravity MITM mode. agy stays on its own
  login.
- **OpenAI.** "Sign in with ChatGPT" partners may use your plan (Hermes Agent is a partner).
  OmniRoute's `codex` provider replays Codex's login and OmniRoute's own docs say that session "is
  not authorized for proxy/router use". Its `codex-app-server` provider is a gray area (one
  personal account at most). Pooling several accounts to stretch limits breaks OpenAI's terms.
  Keep Codex on its own login and put API keys in OmniRoute. Log Hermes in with its own
  device-code flow rather than importing `~/.codex/auth.json`: Codex refresh tokens are single use,
  so a shared copy can log one of them out.
- **OmniRoute defaults are open.** npm installs listen on all interfaces with no API key, so
  anyone on your Wi-Fi could spend every connected account. The playbook binds it to 127.0.0.1 and
  requires keys. Its `auto` model is pre-wired to free providers that its own catalog flags "avoid".
  Use an explicit combo instead.
- **Hindsight.** A non-interactive install (for example one run by Claude Code) defaults to
  Hindsight Cloud and uploads transcripts. Its MCP endpoint has no auth by default.
- **agentmemory** sends memory text to whatever LLM key it finds in its environment. If you start
  it from a shell that exports `OPENAI_API_KEY`, your memories go to OpenAI. The launchd and systemd
  services here start it with an empty environment (`env -i`) plus the few variables it needs.
- **Memory is untrusted data.** Anything an earlier session saved can contain prompt injection,
  including a web page an agent fetched (hooks record tool output). Memory also arrives without
  being asked for: before compaction in Claude and Codex, and on every model call in Hermes. The
  shared rules tell every agent to treat all of it as data and check it against the code.
- **API keys never go through chat.** The playbook creates an empty `~/.agents/stack/secrets.env`
  (mode 600). You paste the keys there in your own editor, and the agent fills config files from
  it by shell expansion, so keys never appear in the chat, the setup log or a memory.
- **Backups first.** Phase 1 archives every config file it touches and the agentmemory memory store
  itself (with the daemon stopped), before any install or upgrade.

## Decisions you will be asked during setup

| # | Question | Default |
|---|---|---|
| 1 | Obsidian vault path | your existing vault, else `~/Vaults/AgentBrain` |
| 2 | ruflo | keep as Claude-only orchestration MCP, memory off (or remove) |
| 3 | Hindsight | remove hooks and stop the server, keeping its data (or "vault brain" mode: search over the vault, no hooks) |
| 4 | Local fallback model (by RAM) | under 24 GB: no local coding fallback (API models via OmniRoute instead; optionally `qwen3:8b`, weak for coding) · about 24 GB: `gemma4` or `qwen3.5` · 32 GB+: `qwen3-coder:30b` or `gpt-oss:20b` |
| 5 | Popup thresholds | 85% and 95% of the 5-hour window, 90% of the weekly window |
| 6 | OmniRoute fallback combo, and what to do with risky connections found | API-key models first, `ollama/<model>` last; remove subscription logins |
| 7 | Claude auto-continue after the limit resets | off while you use the switcher |
| 8 | agentmemory auto-injection | at session start: off (the handoff note and the "search first" rule cover it). Before compaction (Claude, Codex, up to 1500 tokens): on, can be set to 0. Hermes provider: always on while it is the provider |
| 9 | claude-obsidian `hot.md` injection in Claude | off (avoids a third injected block) |
| 10 | Which repos to index now | the repos you are working on |
| – | Claude's own auto memory (`~/.claude/projects/<p>/memory/`) | not asked: stays on as a Claude-only cache; the shared rules say durable facts also go to agentmemory |

## Built-in memories of each agent

Each agent also has a private memory that the others cannot read: Claude Code's auto memory (on by
default), Codex memories (off by default; keep them off), and Hermes's `MEMORY.md`/`USER.md`
(always on; the agentmemory provider mirrors their writes into agentmemory). They stay as private
caches. The shared rules tell every agent to save durable facts with `memory_save` too, so a switch
never loses them.

## Not verified here (the playbook checks these on your machine)

- agy: whether symlinked skill folders load (fallback: copy mode), and the flag that starts an
  interactive session with a prompt (until checked, the picker copies the prompt to your clipboard).
- agentmemory: the JSON fields of `POST /agentmemory/remember` (agentstack's extra save is best
  effort), and whether `AGENTMEMORY_TOOLS=core` in `.env` also trims the plugin's tool list.
- Hermes: the exact `fallback_providers` entry for a named custom provider (the playbook uses
  `hermes fallback add`).
- `ollama launch claude` keeping your MCP servers (one Ollama issue says it did not); check `/mcp`.
- The Claude status line's `rate_limits` field. Several bug reports say it goes missing on some Max
  accounts. If it never shows, the 85% popup cannot fire, but the at-limit `StopFailure` path still
  works.
- Whether Claude's Stop hooks fire when a session is cut off by the limit (agentmemory's last turn
  may be missing; `HANDOFF.md` covers it).
- OmniRoute model IDs for your accounts (read them from `GET /v1/models`).
- That the `AGENTSTACK_OWNER` marker survives `ollama launch claude` into Claude's hooks (the owner
  block relies on it for Claude sessions agentstack starts).
- Which folder agy's status line command runs in (its JSON has no documented working-directory
  field; the agy popup uses the command's own folder).
- The names `AGENTMEMORY_PRE_COMPACT_BUDGET` and `AGENTMEMORY_CAPTURE_DENY`, and whether the hooks
  read them from the agent's environment or from agentmemory's `.env`.

## Files in this folder

| File | What it is |
|---|---|
| `SETUP-PLAYBOOK.md` | Step-by-step setup for an agent to execute (Claude Code recommended) |
| `bin/agentstack` | The glue: status line, hooks, handoff file, owner guard and `reclaim`, picker and launcher, rules/skills sync, install/uninstall, doctor |
| `tests/test_agentstack.py` | 49 tests on a throwaway HOME (pass on Python 3.9 and 3.13) |
| `shared/AGENTS.md` | The shared rules every agent gets (`__VAULT__` is filled in at setup) |
| `shared/skills/agent-handoff/SKILL.md` | Cross-agent skill: write or pick up a handoff |
| `templates/` | agentmemory `.env`, launchd/systemd service, OmniRoute hardening, Claude/Codex/Hermes fallback profiles |

## Versions checked (2026-10-09)

Claude Code 2.1.295 · Codex CLI 0.162.0 · Antigravity CLI 1.3.2 · Hermes Agent v2026.9.24 ·
Ollama 0.40.2 · codebase-memory-mcp 0.11.0 · agentmemory 0.9.30 · graphify (graphifyy) 0.9.82 ·
ruflo 3.56.0 · claude-obsidian 2.2.0 · Hindsight 0.10.3 (coding-agents 0.8.0) · OmniRoute 3.8.51.
Several of these release weekly or daily. The playbook pins versions and tells the agent to read
the changelog before using anything newer.

## Main sources

- Claude Code docs: hooks, status line, memory, MCP, LLM gateway, legal and compliance — https://code.claude.com/docs/en/hooks · /statusline · /memory · /mcp · /llm-gateway · /legal-and-compliance
- Codex docs: AGENTS.md, skills, hooks, MCP, config — https://learn.chatgpt.com/docs/agent-configuration/agents-md.md · /build-skills.md · /hooks.md · /extend/mcp
- Antigravity CLI docs and terms — https://antigravity.google/docs/cli/install · /docs/mcp · /docs/skills · /docs/hooks · /docs/rules · https://antigravity.google/terms
- Hermes Agent docs — https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers · /mcp · /skills · /context-files · /fallback-providers
- Ollama — https://docs.ollama.com/integrations/claude-code · /api/anthropic-compatibility · /context-length
- codebase-memory-mcp — https://github.com/DeusData/codebase-memory-mcp
- agentmemory — https://github.com/rohitg00/agentmemory
- graphify — https://github.com/Graphify-Labs/graphify
- ruflo — https://github.com/ruvnet/ruflo (and issues #1514, #1744)
- claude-obsidian — https://github.com/AgriciDaniel/claude-obsidian
- Hindsight — https://github.com/vectorize-io/hindsight · https://hindsight.vectorize.io/sdks/integrations/coding-agents
- OmniRoute — https://github.com/diegosouzapw/OmniRoute (docs/security/INFERENCE_AUTH_POSTURE.md, docs/reference/FREE_TIERS.md)
- OpenAI Sign in with ChatGPT — https://learn.chatgpt.com/docs/sign-in-with-chatgpt.md
