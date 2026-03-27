from __future__ import annotations

import pytest

from pm.agent.base import ActivityState, LaunchOptions
from pm.agent.claude import ClaudeCodeAgent


@pytest.fixture
def agent():
    return ClaudeCodeAgent()


def test_agent_name(agent):
    assert agent.name() == "claude-code"


def test_supports_worktree(agent):
    assert agent.supports_worktree() is True


# --- launch_command tests ---

def test_basic_command(agent):
    opts = LaunchOptions(prompt="Fix the bug")
    cmd = agent.launch_command(opts)
    assert cmd == ["claude", "--prompt", "Fix the bug"]


def test_command_with_model(agent):
    opts = LaunchOptions(prompt="Fix it", model="claude-sonnet-4-6")
    cmd = agent.launch_command(opts)
    assert cmd == ["claude", "--prompt", "Fix it", "--model", "claude-sonnet-4-6"]


def test_command_with_yolo_mode(agent):
    opts = LaunchOptions(prompt="Do it", permissions="dangerously-skip")
    cmd = agent.launch_command(opts)
    assert "--dangerously-skip-permissions" in cmd
    assert "--prompt" in cmd


def test_command_default_permissions(agent):
    opts = LaunchOptions(prompt="Test")
    cmd = agent.launch_command(opts)
    assert "--dangerously-skip-permissions" not in cmd


def test_command_no_prompt(agent):
    opts = LaunchOptions()
    cmd = agent.launch_command(opts)
    assert cmd == ["claude"]


def test_command_all_options(agent):
    opts = LaunchOptions(
        prompt="Fix auth bug",
        model="claude-sonnet-4-6",
        permissions="dangerously-skip",
    )
    cmd = agent.launch_command(opts)
    assert cmd[0] == "claude"
    assert "--prompt" in cmd
    assert "Fix auth bug" in cmd
    assert "--dangerously-skip-permissions" in cmd
    assert "--model" in cmd
    assert "claude-sonnet-4-6" in cmd


# --- detect_activity tests ---

def test_detect_empty_output(agent):
    assert agent.detect_activity("") == ActivityState.IDLE
    assert agent.detect_activity("   ") == ActivityState.IDLE


def test_detect_active_reading(agent):
    output = "Some previous lines\nReading src/auth/login.ts"
    assert agent.detect_activity(output) == ActivityState.ACTIVE


def test_detect_active_writing(agent):
    output = "Analyzing code...\nWriting changes to file"
    assert agent.detect_activity(output) == ActivityState.ACTIVE


def test_detect_active_running(agent):
    output = "Running tests..."
    assert agent.detect_activity(output) == ActivityState.ACTIVE


def test_detect_active_thinking(agent):
    output = "Let me think about this\nThinking about the solution"
    assert agent.detect_activity(output) == ActivityState.ACTIVE


def test_detect_exited_task_completed(agent):
    output = "All done!\nTask completed"
    assert agent.detect_activity(output) == ActivityState.EXITED


def test_detect_exited_goodbye(agent):
    output = "Finished work\nGoodbye!"
    assert agent.detect_activity(output) == ActivityState.EXITED


def test_detect_exited_session_ended(agent):
    output = "Session ended"
    assert agent.detect_activity(output) == ActivityState.EXITED


def test_detect_waiting_input_yn(agent):
    output = "Do you want to proceed? y/n"
    assert agent.detect_activity(output) == ActivityState.WAITING_INPUT


def test_detect_waiting_input_question(agent):
    output = "Would you like to continue?"
    # "Would you like" triggers WAITING_INPUT for the last lines
    assert agent.detect_activity(output) == ActivityState.WAITING_INPUT


def test_detect_idle_generic(agent):
    output = "Some random text that matches nothing"
    assert agent.detect_activity(output) == ActivityState.IDLE


def test_detect_activity_uses_last_lines(agent):
    # Active pattern in early lines, but idle in recent lines
    lines = ["Reading file..."] + ["Just some text"] * 30
    output = "\n".join(lines)
    # The last 20 lines don't have active patterns
    assert agent.detect_activity(output) == ActivityState.IDLE
