from __future__ import annotations

from pm.agent.base import Agent
from pm.agent.claude import ClaudeCodeAgent
from pm.agent.codex import CodexAgent
from pm.agent.gemini import GeminiAgent

AGENT_REGISTRY: dict[str, Agent] = {
    "claude-code": ClaudeCodeAgent(),
    "codex": CodexAgent(),
    "gemini": GeminiAgent(),
}


def get_agent(name: str) -> Agent | None:
    return AGENT_REGISTRY.get(name)


def list_agents() -> list[str]:
    return list(AGENT_REGISTRY.keys())


def register_agent(agent: Agent) -> None:
    AGENT_REGISTRY[agent.name()] = agent
