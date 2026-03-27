from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from pm.config.loader import load_config, save_config
from pm.config.models import (
    AccountConfig,
    AgentConfig,
    DefaultsConfig,
    PMConfig,
    ProjectConfig,
    ReactionConfig,
)


def test_empty_config():
    config = PMConfig()
    assert config.accounts == {}
    assert config.projects == {}
    assert config.defaults.agent == "claude-code"
    assert config.defaults.branch_prefix == "pm/"


def test_account_config():
    account = AccountConfig(token_env="GITHUB_TOKEN", default=True)
    assert account.token_env == "GITHUB_TOKEN"
    assert account.default is True


def test_account_config_defaults():
    account = AccountConfig(token_env="MY_TOKEN")
    assert account.default is False


def test_project_config():
    project = ProjectConfig(
        account="personal",
        repos=["owner/repo1", "owner/repo2"],
        local_path="~/projects/test",
        instructions="Focus on testing.",
    )
    assert project.account == "personal"
    assert len(project.repos) == 2
    assert project.agent_config.model == "claude-sonnet-4-6"


def test_project_config_defaults():
    project = ProjectConfig(account="test")
    assert project.repos == []
    assert project.local_path == ""
    assert project.instructions == ""
    assert project.assets == []
    assert project.agent == ""


def test_defaults_config():
    defaults = DefaultsConfig()
    assert defaults.agent == "claude-code"
    assert defaults.branch_prefix == "pm/"
    assert defaults.worktree_base == "~/.ppm/worktrees"
    assert defaults.poll_interval == "30s"


def test_reaction_config():
    reaction = ReactionConfig(
        auto=True,
        action="send-to-agent",
        retries=3,
        message="Fix CI",
    )
    assert reaction.auto is True
    assert reaction.retries == 3


def test_full_config_from_dict():
    data = {
        "accounts": {
            "personal": {"token_env": "GITHUB_TOKEN", "default": True},
            "company": {"token_env": "COMPANY_TOKEN"},
        },
        "projects": {
            "my-project": {
                "account": "personal",
                "repos": ["owner/frontend", "owner/backend"],
                "local_path": "~/projects/test",
            }
        },
        "defaults": {
            "agent": "claude-code",
            "poll_interval": "60s",
        },
        "reactions": {
            "ci-failed": {
                "auto": True,
                "action": "send-to-agent",
                "retries": 3,
            }
        },
    }
    config = PMConfig.model_validate(data)
    assert "personal" in config.accounts
    assert config.accounts["personal"].default is True
    assert len(config.projects["my-project"].repos) == 2
    assert config.defaults.poll_interval == "60s"
    assert config.reactions["ci-failed"].retries == 3


def test_load_nonexistent_config():
    config = load_config(Path("/nonexistent/path/config.yaml"))
    assert config.accounts == {}
    assert config.projects == {}


def test_load_empty_yaml():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("")
        f.flush()
        config = load_config(Path(f.name))
    assert config.accounts == {}


def test_load_valid_yaml():
    data = {
        "accounts": {
            "personal": {"token_env": "GH_TOKEN", "default": True},
        },
        "projects": {
            "test-proj": {
                "account": "personal",
                "repos": ["owner/repo"],
            }
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        f.flush()
        config = load_config(Path(f.name))
    assert "personal" in config.accounts
    assert config.accounts["personal"].token_env == "GH_TOKEN"
    assert "test-proj" in config.projects


def test_save_and_reload_config():
    config = PMConfig(
        accounts={"test": AccountConfig(token_env="TEST_TOKEN", default=True)},
        projects={
            "proj": ProjectConfig(
                account="test",
                repos=["owner/repo"],
            )
        },
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.yaml"
        save_config(config, path)
        assert path.exists()
        loaded = load_config(path)
        assert "test" in loaded.accounts
        assert loaded.accounts["test"].token_env == "TEST_TOKEN"
        assert "proj" in loaded.projects
