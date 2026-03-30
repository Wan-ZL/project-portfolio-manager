from __future__ import annotations

import pytest

from pm.agent.base import ActivityState, LaunchOptions
from pm.agent.gemini import GeminiAgent
from pm.agent.registry import get_agent, list_agents


@pytest.fixture
def agent():
    return GeminiAgent()


def test_agent_name(agent):
    assert agent.name() == "gemini"


def test_supports_worktree(agent):
    assert agent.supports_worktree() is True


# --- launch_command tests ---

def test_basic_command(agent):
    opts = LaunchOptions(prompt="Fix the bug")
    cmd = agent.launch_command(opts)
    assert cmd == ["gemini", "-p", "Fix the bug"]


def test_command_with_model(agent):
    opts = LaunchOptions(prompt="Fix it", model="gemini-pro")
    cmd = agent.launch_command(opts)
    assert cmd == ["gemini", "-p", "Fix it", "--model", "gemini-pro"]


def test_command_no_prompt(agent):
    opts = LaunchOptions()
    cmd = agent.launch_command(opts)
    assert cmd == ["gemini"]


def test_command_no_yolo_flag(agent):
    opts = LaunchOptions(prompt="Test", permissions="dangerously-skip")
    cmd = agent.launch_command(opts)
    # Gemini doesn't have a dangerously-skip flag
    assert "--dangerously-skip-permissions" not in cmd
    assert cmd[0] == "gemini"


# --- detect_activity tests ---

def test_detect_empty_output(agent):
    assert agent.detect_activity("") == ActivityState.IDLE
    assert agent.detect_activity("   ") == ActivityState.IDLE


def test_detect_active_reading(agent):
    output = "Some previous lines\nReading src/auth/login.ts"
    assert agent.detect_activity(output) == ActivityState.ACTIVE


def test_detect_active_generating(agent):
    output = "Processing request...\nGenerating code"
    assert agent.detect_activity(output) == ActivityState.ACTIVE


def test_detect_active_thinking(agent):
    output = "Thinking about the solution..."
    assert agent.detect_activity(output) == ActivityState.ACTIVE


def test_detect_active_ellipsis(agent):
    output = "Working on it..."
    assert agent.detect_activity(output) == ActivityState.ACTIVE


def test_detect_exited_done(agent):
    output = "All work Done"
    assert agent.detect_activity(output) == ActivityState.EXITED


def test_detect_exited_completed(agent):
    output = "Task Completed"
    assert agent.detect_activity(output) == ActivityState.EXITED


def test_detect_exited_goodbye(agent):
    output = "Goodbye"
    assert agent.detect_activity(output) == ActivityState.EXITED


def test_detect_waiting_input_yn(agent):
    output = "Do you want to proceed? y/n"
    assert agent.detect_activity(output) == ActivityState.WAITING_INPUT


def test_detect_waiting_input_question(agent):
    output = "Would you like to continue?"
    assert agent.detect_activity(output) == ActivityState.WAITING_INPUT


def test_detect_idle_generic(agent):
    output = "Some random text that matches nothing"
    assert agent.detect_activity(output) == ActivityState.IDLE


def test_detect_activity_uses_last_lines(agent):
    lines = ["Reading file..."] + ["Just some text"] * 30
    output = "\n".join(lines)
    assert agent.detect_activity(output) == ActivityState.IDLE


# --- Registry integration tests ---

def test_gemini_in_registry():
    assert "gemini" in list_agents()


def test_get_gemini_agent():
    agent = get_agent("gemini")
    assert agent is not None
    assert agent.name() == "gemini"


def test_all_three_agents_registered():
    agents = list_agents()
    assert "claude-code" in agents
    assert "codex" in agents
    assert "gemini" in agents
