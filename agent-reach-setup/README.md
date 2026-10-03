# Agent Reach: one-time setup for every project

[Agent Reach](https://github.com/lllTheGodlll/Agent-Reach) gives Claude Code read/search access to the
web, YouTube, GitHub, RSS, Twitter/X, Reddit, Bilibili, and more. It is an **installer + health checker**:
it installs the right upstream tools (yt-dlp, gh, mcporter/Exa, …) and drops a **skill** into
`~/.claude/skills/agent-reach/`. Claude Code loads skills from that folder in **every project**, so you
install it once per machine, not once per repo.

`setup-agent-reach.sh` does the whole install and is safe to re-run (it also upgrades).

## 1. Your own computer (macOS / Linux): do this once

Needs Homebrew (macOS) and either `uv` or `pipx`. If you have neither: `brew install uv`.

```bash
curl -fsSL https://raw.githubusercontent.com/lllTheGodlll/500-AI-Agents-Projects/claude/amazing-bohr-1z7a2a/agent-reach-setup/setup-agent-reach.sh | bash
```

(After this folder is merged to `main`, swap `claude/amazing-bohr-1z7a2a` for `main` in that URL.)

Then, once:

```bash
gh auth login          # unlocks GitHub issues/PRs/forks (public repos work without it)
agent-reach doctor     # shows which channels are ready
```

Open Claude Code in any project and ask e.g. "what does this YouTube video say: <url>". It uses the
`agent-reach` skill automatically.

## 2. Claude Code on the web (cloud sessions)

Cloud containers are thrown away after each session, so the install has to run at the start of every
session. The environment's **Setup script** does that for every repo that uses the environment:

1. In a session, open the cloud environment menu in the title bar → **Edit**.
2. **Setup script**: paste the contents of `setup-agent-reach.sh`.
3. **Network access**: Agent Reach has to reach the open internet. The default policy blocks the hosts it
   needs (tested: `r.jina.ai`, `mcp.exa.ai`, YouTube, `api.bilibili.com`, `www.v2ex.com`, `xueqiu.com`
   all returned 403). Pick **Full**, or **Custom** with those hosts added (keep the package-manager defaults).
   Docs: https://code.claude.com/docs/en/cloud-environments#network-access
4. Start a new session. The skill shows up as `agent-reach`.

## Optional channels

Add credentials only for what you use (a secondary account is safer for cookie-based logins):

| You want | Run |
|---|---|
| Twitter/X search | `agent-reach install --system --channels=twitter` then `agent-reach configure twitter-cookies` |
| Reddit, Facebook, Instagram, XiaoHongShu (desktop) | `agent-reach install --system --channels=opencli` + the OpenCLI Chrome extension |
| Reddit (server) | `agent-reach install --system --channels=reddit` then `rdt login` |
| Bilibili full | `agent-reach install --system --channels=bilibili` |
| Podcast transcripts (Xiaoyuzhou) | `agent-reach configure groq-key` (free key from console.groq.com) |
| Everything | `agent-reach install --system --channels=all` |

For cloud sessions, set `AGENT_REACH_CHANNELS=twitter,reddit` (etc.) as an environment variable and the
setup script installs them too.

## Everyday commands

| Command | What it does |
|---|---|
| `agent-reach doctor` | Which channels work and which backend each one uses |
| `agent-reach check-update` | Is there a newer version? |
| `bash setup-agent-reach.sh` | Upgrade everything (re-run the setup) |
| `agent-reach skill --uninstall` | Remove the skill from Claude Code |
| `uv tool uninstall agent-reach` | Remove the CLI |

Files live in `~/.agent-reach/` (config, cookies) and `~/.claude/skills/agent-reach/` (the skill).
Nothing is written into your project folders.

## Notes

- **Fork vs upstream**: the script installs from your fork. Keep it current with GitHub's **Sync fork**
  button, or run with `AGENT_REACH_SOURCE=git+https://github.com/Panniantong/Agent-Reach`.
- The `doctor` output is in Chinese only; the skill Claude reads is installed in English
  (`AGENT_REACH_LANG=zh` switches it).
- `doctor` does not live-test every channel, so a ✅ can still fail if the network blocks the site.
