# agent-stack

One shared memory for Claude Code, Codex, Antigravity CLI (agy), Hermes Agent and Ollama, plus a
popup that offers to move your work to another agent before Claude's usage limit runs out.

- **[PLAN.md](PLAN.md)**: what each of your tools does in the stack, what gets turned off and why,
  how a handoff works, and the terms-of-service rules that protect your accounts.
- **[SETUP-PLAYBOOK.md](SETUP-PLAYBOOK.md)**: the step-by-step setup, written for an agent to execute.

## Use it

On your own computer, in a clone of this repo:

```bash
claude
```

Then tell Claude Code:

```
Read agent-stack/SETUP-PLAYBOOK.md and run it. Ask me the decisions first.
```

It backs up your configs and your existing memory store, asks about fifteen questions (vault path, what to do with
ruflo and Hindsight, which local model, popup thresholds…), sets everything up, and finishes with a list of the few
things only you can do: trusting hooks in Codex, approving a Hermes hook, OmniRoute dashboard items, and pasting
API keys into `~/.agents/stack/secrets.env` in your own editor (never into the chat).

Afterwards, paste the matching line from playbook section 11 into Codex, agy and Hermes so each one checks its own wiring.

## What you get

| Layer | Owner | Shared by |
|---|---|---|
| Code structure | codebase-memory-mcp (one daemon, one index) | all agents |
| Session memory and handoffs | agentmemory (one daemon, hooks in every agent) + `HANDOFF.md` per repo | all agents |
| Curated notes | Obsidian vault + claude-obsidian skills | all agents |
| Docs, papers, media | graphify | all agents |
| Models and fallback | your own logins first; OmniRoute (API keys) and Ollama (local) as fallback | all agents |
| Rules and skills | `~/.agents/AGENTS.md` and `~/.agents/skills`, copied to each agent by `agentstack sync` | all agents |

## The agentstack command

`bin/agentstack` is a single Python file (standard library only, Python 3.9+). The playbook installs it to
`~/.agents/stack/bin/agentstack`.

| Command | What it does |
|---|---|
| `agentstack statusline` | Claude Code status line: model, 5-hour and weekly usage. Opens the agent picker at 85% and 95% (once per window). Keeps your old status line in front. |
| `agentstack hook stop-failure` | When Claude hits the limit: writes `HANDOFF.md` from git and Claude's last message, opens the picker. |
| `agentstack hook prompt-guard` | Tells the Claude session that crossed the threshold, once, that a handoff is due. After a switch it blocks prompts in that repo, so two agents never edit at once; a message starting with `reclaim` takes the repo back. |
| `agentstack hook session-start` | Claude Code and Codex: injects an open `HANDOFF.md` that agentstack wrote, as data (never a file git tracks). |
| `agentstack handoff` | Creates or refreshes `HANDOFF.md` (keeps the narrative, refreshes the git state, excludes the file from git, archives a finished note). |
| `agentstack reclaim` | Takes a handed-off repo back for Claude Code (same as a `reclaim` message). |
| `agentstack switch` | The picker: Codex, agy, Hermes, Claude Code on Ollama, Claude Code via OmniRoute, Codex via OmniRoute. Opens the choice in a new terminal in the repo with a "read HANDOFF.md, recall memory" prompt. |
| `agentstack sync` | Copies `~/.agents/AGENTS.md` into each agent's rules file and links `~/.agents/skills` into each agent. |
| `agentstack install / uninstall --agent claude\|codex\|agy` | Adds or removes the hooks and status line (backs up the settings file, keeps symlinks and file permissions; uninstall restores your old status line). |
| `agentstack doctor` | Checks services, ports exposed on your network, duplicate memory hooks, rule copies and more. |

Tests: `python3 agent-stack/tests/test_agentstack.py` (40 tests, throwaway HOME, safe to run anywhere).
