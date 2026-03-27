from __future__ import annotations

from pydantic import BaseModel, Field


class AccountConfig(BaseModel):
    token_env: str
    default: bool = False


class AgentConfig(BaseModel):
    model: str = "claude-sonnet-4-6"
    permissions: str = "default"


class ProjectConfig(BaseModel):
    account: str
    repos: list[str] = Field(default_factory=list)
    local_path: str = ""
    instructions: str = ""
    assets: list[str] = Field(default_factory=list)
    agent: str = ""
    agent_config: AgentConfig = Field(default_factory=AgentConfig)


class DefaultsConfig(BaseModel):
    agent: str = "claude-code"
    branch_prefix: str = "pm/"
    worktree_base: str = "~/.ppm/worktrees"
    poll_interval: str = "30s"


class ReactionConfig(BaseModel):
    auto: bool = True
    action: str = "notify"
    retries: int = 3
    message: str = ""
    escalate_after: str = ""


class PMConfig(BaseModel):
    accounts: dict[str, AccountConfig] = Field(default_factory=dict)
    projects: dict[str, ProjectConfig] = Field(default_factory=dict)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    reactions: dict[str, ReactionConfig] = Field(default_factory=dict)
