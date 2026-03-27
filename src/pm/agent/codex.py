from __future__ import annotations

from pm.agent.base import Agent, ActivityState, LaunchOptions


class CodexAgent(Agent):
    """OpenAI Codex CLI agent implementation"""

    def name(self) -> str:
        return "codex"

    def launch_command(self, opts: LaunchOptions) -> list[str]:
        cmd = ["codex"]
        if opts.prompt:
            cmd.extend(["--prompt", opts.prompt])
        if opts.permissions == "dangerously-skip":
            cmd.append("--auto-yes")
        if opts.model:
            cmd.extend(["--model", opts.model])
        return cmd

    def detect_activity(self, output: str) -> ActivityState:
        if not output or not output.strip():
            return ActivityState.IDLE

        lines = output.strip().splitlines()
        last_lines = "\n".join(lines[-20:]) if len(lines) > 20 else output.strip()

        exit_patterns = ["Done", "Completed", "exited"]
        for pattern in exit_patterns:
            if pattern in last_lines:
                return ActivityState.EXITED

        input_patterns = ["? ", "> ", "y/n"]
        for pattern in input_patterns:
            if last_lines.rstrip().endswith(pattern):
                return ActivityState.WAITING_INPUT

        return ActivityState.ACTIVE

    def supports_worktree(self) -> bool:
        return True
