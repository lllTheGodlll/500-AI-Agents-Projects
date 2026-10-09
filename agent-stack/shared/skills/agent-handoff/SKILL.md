---
name: agent-handoff
description: Write or pick up a cross-agent handoff (HANDOFF.md plus shared memory). Use when the user says handoff, switch agent, or continue in Codex, agy, Hermes or Ollama; when an agent-stack note says usage crossed its threshold; or at session start when HANDOFF.md exists.
---

# Agent handoff

## Write a handoff

1. Collect: the goal, what is done, what remains, the exact next step, how to verify, files touched.
2. Save it to shared memory: `memory_save` (agentmemory), type `workflow`, title `handoff: <task>`,
   project = the repo folder name.
3. From the repo root run `~/.agents/stack/bin/agentstack handoff --from <your agent> --reason "<why>"`.
   It creates `HANDOFF.md` if needed and refreshes the auto-captured git state.
4. Put the same content into the `## Narrative` section of `HANDOFF.md`. Keep it under 40 lines.
5. Tell the user the handoff is ready. To switch now: `~/.agents/stack/bin/agentstack switch --from <your agent>`.

## Pick up a handoff

1. Read `HANDOFF.md` at the repo root: the narrative first, then the auto-captured state.
2. Run `memory_smart_search "handoff <task keywords>"` and `memory_recall` for the project.
3. Look up the files named in the note in the code graph (codebase-memory-mcp).
4. Check the note against `git status` and `git log`; it can be stale.
5. Tell the user the current state and the next step before changing code.
6. When the task is finished, set `status: done` in the header of `HANDOFF.md` and save a closing memory.

## Agents without memory tools

If `memory_save` is not available (for example a small local model without MCP), write the
narrative into `HANDOFF.md` only. The next agent with memory access will store it.
