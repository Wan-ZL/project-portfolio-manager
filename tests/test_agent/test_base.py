from __future__ import annotations

import pytest

from pm.agent.base import Agent, ActivityState, LaunchOptions
from pm.agent.claude import ClaudeCodeAgent
from pm.agent.codex import CodexAgent
from pm.agent.registry import AGENT_REGISTRY, get_agent, list_agents, register_agent


def test_activity_state_enum():
    assert ActivityState.ACTIVE.value == "active"
    assert ActivityState.IDLE.value == "idle"
    assert ActivityState.WAITING_INPUT.value == "waiting_input"
    assert ActivityState.EXITED.value == "exited"


def test_launch_options_defaults():
    opts = LaunchOptions()
    assert opts.prompt == ""
    assert opts.work_dir == ""
    assert opts.model == ""
    assert opts.permissions == "default"


def test_launch_options_custom():
    opts = LaunchOptions(
        prompt="Fix the bug",
        work_dir="/tmp/work",
        model="claude-sonnet-4-6",
        permissions="dangerously-skip",
    )
    assert opts.prompt == "Fix the bug"
    assert opts.work_dir == "/tmp/work"
    assert opts.model == "claude-sonnet-4-6"
    assert opts.permissions == "dangerously-skip"


def test_agent_abc_cannot_instantiate():
    with pytest.raises(TypeError):
        Agent()


def test_registry_has_agents():
    assert "claude-code" in AGENT_REGISTRY
    assert "codex" in AGENT_REGISTRY


def test_get_agent_exists():
    agent = get_agent("claude-code")
    assert agent is not None
    assert agent.name() == "claude-code"


def test_get_agent_nonexistent():
    agent = get_agent("nonexistent-agent")
    assert agent is None


def test_list_agents():
    agents = list_agents()
    assert "claude-code" in agents
    assert "codex" in agents


def test_register_custom_agent():
    class CustomAgent(Agent):
        def name(self) -> str:
            return "custom-agent"

        def launch_command(self, opts: LaunchOptions) -> list[str]:
            return ["custom", "--prompt", opts.prompt]

        def detect_activity(self, output: str) -> ActivityState:
            return ActivityState.ACTIVE

        def supports_worktree(self) -> bool:
            return False

    custom = CustomAgent()
    register_agent(custom)

    assert "custom-agent" in AGENT_REGISTRY
    fetched = get_agent("custom-agent")
    assert fetched is not None
    assert fetched.name() == "custom-agent"
    assert not fetched.supports_worktree()

    # Clean up
    del AGENT_REGISTRY["custom-agent"]


def test_claude_agent_is_agent_subclass():
    agent = ClaudeCodeAgent()
    assert isinstance(agent, Agent)


def test_codex_agent_is_agent_subclass():
    agent = CodexAgent()
    assert isinstance(agent, Agent)
