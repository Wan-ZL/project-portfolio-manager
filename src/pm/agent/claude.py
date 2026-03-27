from __future__ import annotations

from pm.agent.base import Agent, ActivityState, LaunchOptions


class ClaudeCodeAgent(Agent):
    """Claude Code CLI agent implementation (T1)"""

    def name(self) -> str:
        return "claude-code"

    def launch_command(self, opts: LaunchOptions) -> list[str]:
        cmd = ["claude"]
        if opts.prompt:
            cmd.extend(["--prompt", opts.prompt])
        if opts.permissions == "dangerously-skip":
            cmd.append("--dangerously-skip-permissions")
        if opts.model:
            cmd.extend(["--model", opts.model])
        return cmd

    def detect_activity(self, output: str) -> ActivityState:
        if not output or not output.strip():
            return ActivityState.IDLE

        lines = output.strip().splitlines()
        last_lines = "\n".join(lines[-20:]) if len(lines) > 20 else output.strip()

        # Check for exit patterns
        exit_patterns = [
            "has been completed",
            "Task completed",
            "Goodbye!",
            "Session ended",
            "exited with code",
            "Process exited",
        ]
        for pattern in exit_patterns:
            if pattern in last_lines:
                return ActivityState.EXITED

        # Check for waiting input patterns
        # Some patterns match if the last lines end with them
        endswith_patterns = [
            "y/n",
            "Y/n",
            "(y/N)",
            "(Y/n)",
            "? ",
            "> ",
        ]
        for pattern in endswith_patterns:
            if last_lines.rstrip().endswith(pattern):
                return ActivityState.WAITING_INPUT

        # Some patterns match if they appear anywhere in the last few lines
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

        # Check for active patterns
        active_patterns = [
            "Reading",
            "Writing",
            "Editing",
            "Running",
            "Creating",
            "Searching",
            "Analyzing",
            "Thinking",
            "...",
        ]
        for pattern in active_patterns:
            if pattern in last_lines:
                return ActivityState.ACTIVE

        return ActivityState.IDLE

    def supports_worktree(self) -> bool:
        return True
