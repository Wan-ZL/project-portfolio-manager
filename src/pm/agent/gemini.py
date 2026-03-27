from __future__ import annotations

from pm.agent.base import Agent, ActivityState, LaunchOptions


class GeminiAgent(Agent):
    """Google Gemini CLI agent implementation"""

    def name(self) -> str:
        return "gemini"

    def launch_command(self, opts: LaunchOptions) -> list[str]:
        cmd = ["gemini"]
        if opts.prompt:
            cmd.extend(["-p", opts.prompt])
        if opts.model:
            cmd.extend(["--model", opts.model])
        return cmd

    def detect_activity(self, output: str) -> ActivityState:
        if not output or not output.strip():
            return ActivityState.IDLE

        lines = output.strip().splitlines()
        last_lines = "\n".join(lines[-20:]) if len(lines) > 20 else output.strip()

        exit_patterns = [
            "Done",
            "Completed",
            "Goodbye",
            "Session ended",
            "exited",
        ]
        for pattern in exit_patterns:
            if pattern in last_lines:
                return ActivityState.EXITED

        input_patterns = ["? ", "> ", "y/n", "(Y/n)", "(y/N)"]
        for pattern in input_patterns:
            if last_lines.rstrip().endswith(pattern):
                return ActivityState.WAITING_INPUT

        contains_patterns = [
            "Do you want to",
            "Would you like",
            "Press Enter",
            "Waiting for input",
        ]
        last_few = "\n".join(lines[-5:]) if len(lines) > 5 else last_lines
        for pattern in contains_patterns:
            if pattern in last_few:
                return ActivityState.WAITING_INPUT

        active_patterns = [
            "Reading",
            "Writing",
            "Editing",
            "Running",
            "Searching",
            "Analyzing",
            "Thinking",
            "Generating",
            "Processing",
            "...",
        ]
        for pattern in active_patterns:
            if pattern in last_lines:
                return ActivityState.ACTIVE

        return ActivityState.IDLE

    def supports_worktree(self) -> bool:
        return True
