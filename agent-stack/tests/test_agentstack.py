#!/usr/bin/env python3
"""Tests for agent-stack/bin/agentstack. Run: python3 agent-stack/tests/test_agentstack.py

Everything runs against a throwaway HOME with stub agent commands, so it is safe on a real machine.
"""

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "bin" / "agentstack"
SHARED_RULES = HERE.parent / "shared" / "AGENTS.md"


class StackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.home.mkdir()
        self.stack = self.home / ".agents" / "stack"
        self.bin = root / "bin"
        self.bin.mkdir()
        for name in ("codex", "agy", "hermes", "ollama", "claude"):
            stub = self.bin / name
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        self.repo = root / "work" / "demo-repo"
        self.repo.mkdir(parents=True)
        self.git("init", "-q")
        (self.repo / "app.py").write_text("print('hi')\n")
        self.git("add", "app.py")
        self.git("commit", "-q", "-m", "first commit")
        (self.repo / "app.py").write_text("print('changed')\n")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@e", HOME=str(self.home))
        subprocess.run(["git", "-C", str(self.repo)] + list(args), check=True, env=env,
                       capture_output=True)

    def env(self, **extra):
        env = {
            "HOME": str(self.home),
            "PATH": "%s:%s" % (self.bin, os.environ.get("PATH", "/usr/bin:/bin")),
            "AGENTSTACK_NO_SPAWN": "1",
            "AGENTSTACK_DRY_RUN": "1",
            "LANG": "C.UTF-8",
        }
        env.update(extra)
        return env

    def run_cmd(self, args, stdin=None, **extra):
        proc = subprocess.run([sys.executable, str(SCRIPT)] + args, input=stdin, capture_output=True,
                              text=True, env=self.env(**extra), cwd=str(self.repo), timeout=60)
        self.assertNotIn("Traceback", proc.stderr, proc.stderr)
        return proc

    def status_json(self, pct, resets="1760000000", session="s1"):
        return json.dumps({
            "session_id": session, "transcript_path": "",
            "model": {"display_name": "Opus"}, "workspace": {"current_dir": str(self.repo)},
            "rate_limits": {"five_hour": {"used_percentage": pct, "resets_at": resets},
                            "seven_day": {"used_percentage": 10, "resets_at": "1760500000"}},
        })

    # -- status line -------------------------------------------------------------------------

    def test_statusline_without_rate_limits(self):
        proc = self.run_cmd(["statusline"], stdin=json.dumps({"model": {"display_name": "Opus"}}))
        self.assertEqual(proc.stdout.strip(), "Opus")
        self.assertFalse((self.stack / "state" / "handoff-request.json").exists())

    def test_statusline_garbage_input_never_fails(self):
        proc = self.run_cmd(["statusline"], stdin="not json")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "agent-stack")

    def test_statusline_threshold_fires_once_per_window_and_level(self):
        proc = self.run_cmd(["statusline"], stdin=self.status_json(72))
        self.assertIn("5h 72%", proc.stdout)
        self.assertFalse((self.stack / "state" / "handoff-request.json").exists())
        self.run_cmd(["statusline"], stdin=self.status_json(90))
        flags = sorted(p.name for p in (self.stack / "state" / "fired").iterdir())
        self.assertEqual(len(flags), 1)
        self.assertTrue(flags[0].endswith("-85.flag"))
        request = json.loads((self.stack / "state" / "handoff-request.json").read_text())
        self.assertEqual(request["agent"], "claude")
        self.assertEqual(Path(request["repo_root"]).resolve(), self.repo.resolve())
        self.run_cmd(["statusline"], stdin=self.status_json(91))
        self.assertEqual(len(list((self.stack / "state" / "fired").iterdir())), 1)
        self.run_cmd(["statusline"], stdin=self.status_json(96))
        self.assertEqual(len(list((self.stack / "state" / "fired").iterdir())), 2)
        self.run_cmd(["statusline"], stdin=self.status_json(86, resets="1760018000"))  # new window
        self.assertEqual(len(list((self.stack / "state" / "fired").iterdir())), 3)
        log = (self.stack / "logs" / "agentstack.log").read_text()
        self.assertIn("spawn suppressed: switch", log)

    def test_statusline_chains_existing_command(self):
        self.stack.mkdir(parents=True)
        (self.stack / "config.json").write_text(json.dumps({"statusline_chain": {"claude": "echo MINE"}}))
        proc = self.run_cmd(["statusline"], stdin=self.status_json(10))
        self.assertTrue(proc.stdout.startswith("MINE · Opus 5h 10%"), proc.stdout)

    def test_agy_statusline(self):
        data = {"quota": {"gemini": {"remaining_fraction": 0.1, "reset_time": "2026-10-09T20:00:00Z"},
                          "claude": {"remaining_fraction": 0.6}}, "cwd": str(self.repo)}
        proc = self.run_cmd(["statusline", "--agent", "agy"], stdin=json.dumps(data))
        self.assertIn("agy gemini 10% left", proc.stdout)
        request = json.loads((self.stack / "state" / "handoff-request.json").read_text())
        self.assertEqual(request["agent"], "agy")

    # -- hooks -------------------------------------------------------------------------------

    def test_prompt_guard_once_per_session(self):
        self.run_cmd(["statusline"], stdin=self.status_json(88))
        hook_in = json.dumps({"session_id": "s1", "cwd": str(self.repo), "prompt": "go on"})
        out = self.run_cmd(["hook", "prompt-guard"], stdin=hook_in).stdout
        data = json.loads(out)
        ctx = data["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("88%", ctx)
        self.assertIn("HANDOFF.md", ctx)
        self.assertEqual(self.run_cmd(["hook", "prompt-guard"], stdin=hook_in).stdout.strip(), "")
        other = json.dumps({"session_id": "s2", "cwd": str(self.repo)})
        self.assertIn("additionalContext", self.run_cmd(["hook", "prompt-guard"], stdin=other).stdout)

    def test_prompt_guard_silent_without_request(self):
        out = self.run_cmd(["hook", "prompt-guard"], stdin=json.dumps({"session_id": "s1"})).stdout
        self.assertEqual(out.strip(), "")

    def test_stop_failure_writes_handoff(self):
        transcript = self.repo.parent / "t.jsonl"
        transcript.write_text("\n".join([
            json.dumps({"type": "user", "message": {"content": "do it"}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "I refactored app.py; tests next."}]}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}}),
        ]) + "\n")
        hook_in = json.dumps({"error": "rate_limit", "session_id": "abc-123", "transcript_path": str(transcript),
                              "cwd": str(self.repo), "last_assistant_message": "API Error: rate limit"})
        self.run_cmd(["hook", "stop-failure"], stdin=hook_in)
        text = (self.repo / "HANDOFF.md").read_text()
        self.assertIn("# Handoff: demo-repo", text)
        self.assertRegex(text, r"(?m)^status: open$")
        self.assertRegex(text, r"(?m)^from: claude$")
        self.assertIn("I refactored app.py; tests next.", text)
        self.assertIn("claude --resume abc-123", text)
        self.assertIn("M app.py", text)
        self.assertEqual(text.count("<!-- agent-stack:auto:begin -->"), 1)
        exclude = (self.repo / ".git" / "info" / "exclude").read_text()
        self.assertIn("/HANDOFF.md", exclude)
        status = subprocess.run(["git", "-C", str(self.repo), "status", "--short"], capture_output=True, text=True).stdout
        self.assertNotIn("HANDOFF.md", status)

    def test_stop_failure_ignores_other_errors(self):
        hook_in = json.dumps({"error": "server_error", "cwd": str(self.repo)})
        self.run_cmd(["hook", "stop-failure"], stdin=hook_in)
        self.assertFalse((self.repo / "HANDOFF.md").exists())

    def test_handoff_refresh_keeps_narrative(self):
        self.run_cmd(["handoff", "--cwd", str(self.repo), "--from", "claude", "--reason", "first"])
        path = self.repo / "HANDOFF.md"
        text = path.read_text().replace("- Goal:", "- Goal: ship the login page")
        path.write_text(text)
        self.run_cmd(["handoff", "--cwd", str(self.repo), "--from", "codex", "--reason", "second"])
        text = path.read_text()
        self.assertIn("- Goal: ship the login page", text)
        self.assertRegex(text, r"(?m)^from: codex$")
        self.assertRegex(text, r"(?m)^reason: second$")
        self.assertEqual(text.count("<!-- agent-stack:auto:begin -->"), 1)
        self.assertEqual(len(re.findall(r"(?m)^status:", text)), 1)
        exclude = (self.repo / ".git" / "info" / "exclude").read_text()
        self.assertEqual(exclude.count("/HANDOFF.md"), 1)

    def test_handoff_leaves_tracked_unmanaged_file_alone(self):
        (self.repo / "HANDOFF.md").write_text("team doc\n")
        self.git("add", "HANDOFF.md")
        self.git("commit", "-q", "-m", "doc")
        proc = self.run_cmd(["handoff", "--cwd", str(self.repo)])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual((self.repo / "HANDOFF.md").read_text(), "team doc\n")

    def test_session_start_injects_open_handoff_only(self):
        self.run_cmd(["handoff", "--cwd", str(self.repo), "--from", "claude", "--reason", "limit"])
        hook_in = json.dumps({"cwd": str(self.repo), "source": "startup", "session_id": "x"})
        out = self.run_cmd(["hook", "session-start", "--agent", "codex"], stdin=hook_in).stdout
        data = json.loads(out)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("from claude", data["hookSpecificOutput"]["additionalContext"])
        same = json.dumps({"cwd": str(self.repo), "source": "resume"})
        self.assertEqual(self.run_cmd(["hook", "session-start", "--agent", "claude"], stdin=same).stdout.strip(), "")
        path = self.repo / "HANDOFF.md"
        path.write_text(re.sub(r"(?m)^status: open$", "status: done", path.read_text()))
        self.assertEqual(self.run_cmd(["hook", "session-start", "--agent", "codex"], stdin=hook_in).stdout.strip(), "")

    # -- switch ------------------------------------------------------------------------------

    def test_switch_dry_run_writes_launcher(self):
        proc = self.run_cmd(["switch", "--cwd", str(self.repo), "--reason", "test", "--pick", "codex"])
        self.assertIn("dry run, launcher written", proc.stdout)
        launcher = Path(re.search(r"launcher written: (\S+)", proc.stdout).group(1))
        body = launcher.read_text()
        self.assertIn("cd %s" % self.repo.resolve(), body.replace("'", ""))
        self.assertIn("exec codex 'Continue the work in this repository (project: demo-repo).", body)
        self.assertTrue((self.repo / "HANDOFF.md").exists())

    def test_switch_commands_per_choice(self):
        expected = {
            "hermes": "exec hermes chat -q",
            "claude-ollama": "exec ollama launch claude --model qwen3-coder:30b --",
            "agy": "exec agy",
        }
        for choice, fragment in expected.items():
            proc = self.run_cmd(["switch", "--cwd", str(self.repo), "--pick", choice, "--no-handoff"])
            self.assertIn(fragment, proc.stdout, choice)

    def test_switch_keep_does_nothing(self):
        proc = self.run_cmd(["switch", "--cwd", str(self.repo), "--pick", "keep"])
        self.assertEqual(proc.returncode, 0)
        self.assertFalse((self.repo / "HANDOFF.md").exists())

    # -- sync --------------------------------------------------------------------------------

    def prepare_shared(self):
        agents = self.home / ".agents"
        (agents / "skills" / "agent-handoff").mkdir(parents=True)
        (agents / "skills" / "agent-handoff" / "SKILL.md").write_text("---\nname: agent-handoff\ndescription: x\n---\n")
        (agents / "skills" / "wiki").mkdir()
        (agents / "skills" / "wiki" / "SKILL.md").write_text("---\nname: wiki\ndescription: y\n---\n")
        (agents / "AGENTS.md").write_text(SHARED_RULES.read_text())
        for d in (".claude", ".codex", ".gemini", ".hermes"):
            (self.home / d).mkdir()
        (self.home / ".claude" / "CLAUDE.md").write_text("# my rules\n")
        (self.home / ".codex" / "AGENTS.md").write_text("For structural codebase exploration, use the codebase-memory skill.\n")
        (self.home / ".hermes" / "config.yaml").write_text("skills:\n  external_dirs:\n    - ~/.agents/skills\n")
        self.stack.mkdir(parents=True, exist_ok=True)
        (self.stack / "config.json").write_text(json.dumps({"claude_skip_skills": ["wiki"]}))

    def test_sync_is_idempotent(self):
        self.prepare_shared()
        first = self.run_cmd(["sync"]).stdout
        self.assertIn("linked", first)
        second = self.run_cmd(["sync"]).stdout
        self.assertNotIn("updated", second)
        self.assertNotIn("linked", second)
        claude_md = (self.home / ".claude" / "CLAUDE.md").read_text()
        self.assertTrue(claude_md.startswith("@~/.agents/AGENTS.md\n"))
        self.assertIn("# my rules", claude_md)
        codex = (self.home / ".codex" / "AGENTS.md").read_text()
        self.assertIn("codebase-memory skill", codex)
        self.assertEqual(codex.count("<!-- agent-stack:begin -->"), 1)
        self.assertTrue((self.home / ".gemini" / "AGENTS.md").read_text().count("agent-stack:begin") == 1)
        self.assertTrue((self.home / ".hermes" / "SOUL.md").is_file())
        self.assertTrue((self.home / ".claude" / "skills" / "agent-handoff").is_symlink())
        self.assertFalse((self.home / ".claude" / "skills" / "wiki").exists())  # skipped
        self.assertTrue((self.home / ".gemini" / "antigravity-cli" / "skills" / "wiki").is_symlink())

    def test_sync_updates_changed_rules_and_drops_dangling_links(self):
        self.prepare_shared()
        self.run_cmd(["sync"])
        rules = self.home / ".agents" / "AGENTS.md"
        rules.write_text(rules.read_text() + "\n- extra rule\n")
        out = self.run_cmd(["sync"]).stdout
        self.assertIn("updated", out)
        self.assertIn("- extra rule", (self.home / ".codex" / "AGENTS.md").read_text())
        import shutil
        shutil.rmtree(str(self.home / ".agents" / "skills" / "agent-handoff"))
        out = self.run_cmd(["sync"]).stdout
        self.assertIn("removed dangling link", out)
        self.assertFalse(os.path.lexists(str(self.home / ".claude" / "skills" / "agent-handoff")))

    def test_sync_check_changes_nothing(self):
        self.prepare_shared()
        self.run_cmd(["sync", "--check"])
        self.assertFalse((self.home / ".hermes" / "SOUL.md").exists())
        self.assertEqual((self.home / ".claude" / "CLAUDE.md").read_text(), "# my rules\n")

    # -- install -----------------------------------------------------------------------------

    def test_install_and_uninstall_claude_round_trip(self):
        settings = self.home / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        original = {
            "statusLine": {"type": "command", "command": "~/my-status.sh"},
            "hooks": {"SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": "other-tool start"}]}]},
            "env": {"FOO": "1"},
        }
        settings.write_text(json.dumps(original))
        self.run_cmd(["install", "--agent", "claude"])
        data = json.loads(settings.read_text())
        self.assertIn("agentstack", data["statusLine"]["command"])
        self.assertEqual(len(data["hooks"]["SessionStart"]), 2)
        self.assertEqual(data["hooks"]["StopFailure"][0]["matcher"], "rate_limit")
        config = json.loads((self.stack / "config.json").read_text())
        self.assertEqual(config["statusline_chain"]["claude"], "~/my-status.sh")
        again = self.run_cmd(["install", "--agent", "claude"]).stdout
        self.assertIn("already installed", again)
        self.run_cmd(["uninstall", "--agent", "claude"])
        self.assertEqual(json.loads(settings.read_text()), original)

    def test_install_refuses_unparseable_settings(self):
        settings = self.home / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{ broken")
        proc = subprocess.run([sys.executable, str(SCRIPT), "install", "--agent", "claude"], capture_output=True,
                              text=True, env=self.env())
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(settings.read_text(), "{ broken")

    def test_install_codex_hooks(self):
        self.run_cmd(["install", "--agent", "codex"])
        data = json.loads((self.home / ".codex" / "hooks.json").read_text())
        self.assertIn("session-start --agent codex", data["hooks"]["SessionStart"][0]["hooks"][0]["command"])
        self.run_cmd(["uninstall", "--agent", "codex"])
        self.assertEqual(json.loads((self.home / ".codex" / "hooks.json").read_text()), {})

    def test_install_dry_run_writes_nothing(self):
        self.run_cmd(["install", "--agent", "claude", "--dry-run"])
        self.assertFalse((self.home / ".claude" / "settings.json").exists())

    # -- doctor and shared files -------------------------------------------------------------

    def test_doctor_runs(self):
        self.prepare_shared()
        proc = self.run_cmd(["doctor"])
        self.assertIn("rules", proc.stdout)
        self.assertIn(proc.returncode, (0, 1))

    def test_shared_rules_are_hermes_safe(self):
        text = SHARED_RULES.read_text()
        self.assertIsNone(re.search(r"<!--[^>]*(ignore|override|system|secret|hidden)", text, re.I))
        self.assertLess(len(text.encode()), 8 * 1024)


if __name__ == "__main__":
    unittest.main(verbosity=2)
