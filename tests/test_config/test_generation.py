from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from pm.config.loader import generate_config_from_repos, has_real_projects, load_config
from pm.config.models import PMConfig, AccountConfig, ProjectConfig


class TestHasRealProjects:
    def test_empty_config(self):
        cfg = PMConfig()
        assert has_real_projects(cfg) is False

    def test_sample_placeholder_project(self):
        cfg = PMConfig(
            projects={
                "my-project": ProjectConfig(
                    account="personal",
                    repos=["your-username/your-repo"],
                )
            }
        )
        assert has_real_projects(cfg) is False

    def test_sample_placeholder_no_repos(self):
        cfg = PMConfig(
            projects={
                "my-project": ProjectConfig(
                    account="personal",
                    repos=[],
                )
            }
        )
        assert has_real_projects(cfg) is False

    def test_real_project(self):
        cfg = PMConfig(
            projects={
                "website": ProjectConfig(
                    account="personal",
                    repos=["zelin/my-website"],
                )
            }
        )
        assert has_real_projects(cfg) is True

    def test_multiple_projects_with_placeholder(self):
        """If there's more than just my-project, it's real."""
        cfg = PMConfig(
            projects={
                "my-project": ProjectConfig(
                    account="personal",
                    repos=["your-username/your-repo"],
                ),
                "real-project": ProjectConfig(
                    account="personal",
                    repos=["zelin/real-repo"],
                ),
            }
        )
        assert has_real_projects(cfg) is True

    def test_my_project_with_real_repo(self):
        """my-project but with real (non-placeholder) repos."""
        cfg = PMConfig(
            projects={
                "my-project": ProjectConfig(
                    account="personal",
                    repos=["zelin/real-repo"],
                )
            }
        )
        assert has_real_projects(cfg) is True


class TestGenerateConfigFromRepos:
    def test_generates_valid_yaml(self):
        repos = [
            {
                "name": "repo1",
                "full_name": "user/repo1",
                "description": "Test",
                "default_branch": "main",
                "private": False,
                "html_url": "https://github.com/user/repo1",
                "owner": "user",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"
            generate_config_from_repos(repos, "personal", path)

            assert path.exists()
            cfg = load_config(path)
            assert "personal" in cfg.accounts
            assert cfg.accounts["personal"].token_source == "credentials"
            assert "user" in cfg.projects
            assert "user/repo1" in cfg.projects["user"].repos

    def test_groups_by_owner(self):
        repos = [
            {"name": "repo1", "full_name": "user/repo1", "owner": "user",
             "description": "", "default_branch": "main", "private": False, "html_url": ""},
            {"name": "repo2", "full_name": "user/repo2", "owner": "user",
             "description": "", "default_branch": "main", "private": False, "html_url": ""},
            {"name": "lib1", "full_name": "org/lib1", "owner": "org",
             "description": "", "default_branch": "main", "private": True, "html_url": ""},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"
            generate_config_from_repos(repos, "personal", path)

            cfg = load_config(path)
            assert "user" in cfg.projects
            assert "org" in cfg.projects
            assert len(cfg.projects["user"].repos) == 2
            assert len(cfg.projects["org"].repos) == 1

    def test_creates_parent_dirs(self):
        repos = [
            {"name": "repo1", "full_name": "user/repo1", "owner": "user",
             "description": "", "default_branch": "main", "private": False, "html_url": ""},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dir" / "config.yaml"
            generate_config_from_repos(repos, "personal", path)
            assert path.exists()

    def test_empty_repos_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"
            generate_config_from_repos([], "personal", path)

            assert path.exists()
            cfg = load_config(path)
            assert "personal" in cfg.accounts
            assert len(cfg.projects) == 0

    def test_generated_config_has_defaults(self):
        repos = [
            {"name": "repo1", "full_name": "user/repo1", "owner": "user",
             "description": "", "default_branch": "main", "private": False, "html_url": ""},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"
            generate_config_from_repos(repos, "personal", path)

            cfg = load_config(path)
            assert cfg.defaults.agent == "claude-code"
            assert cfg.defaults.branch_prefix == "ppm/"

    def test_account_uses_credentials_source(self):
        repos = [
            {"name": "repo1", "full_name": "user/repo1", "owner": "user",
             "description": "", "default_branch": "main", "private": False, "html_url": ""},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"
            generate_config_from_repos(repos, "myaccount", path)

            cfg = load_config(path)
            assert "myaccount" in cfg.accounts
            assert cfg.accounts["myaccount"].token_source == "credentials"
            assert cfg.accounts["myaccount"].default is True
