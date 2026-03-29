"""Tests for live mode: TUI loads real data when credentials exist."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.portfolio import (
    PortfolioScreen,
    _has_credentials,
    _fetch_live_projects_and_prs,
)
from pm.tui.widgets.project_card import ProjectCard
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.status_bar import StatusBar
from pm.github.pr import EnhancedPR


class TestHasCredentials:
    @patch("pm.auth.credentials.load_credentials")
    def test_has_credentials_true(self, mock_creds):
        mock_creds.return_value = {
            "accounts": {"personal": {"token": "ghp_test", "username": "user"}}
        }
        assert _has_credentials() is True

    @patch("pm.auth.credentials.load_credentials")
    def test_has_credentials_false(self, mock_creds):
        mock_creds.return_value = {"accounts": {}}
        assert _has_credentials() is False

    @patch("pm.auth.credentials.load_credentials")
    def test_has_credentials_error(self, mock_creds):
        mock_creds.side_effect = Exception("file error")
        assert _has_credentials() is False


class TestFetchLiveProjectsAndPrs:
    @patch("pm.auth.credentials.load_credentials")
    def test_no_credentials_returns_empty(self, mock_creds):
        mock_creds.return_value = {"accounts": {}}
        projects, prs = _fetch_live_projects_and_prs()
        assert projects == []
        assert prs == {}

    @patch("pm.config.loader.load_config")
    @patch("pm.auth.credentials.load_credentials")
    def test_with_config_and_credentials(self, mock_creds, mock_cfg):
        mock_creds.return_value = {
            "accounts": {"personal": {"token": "ghp_test", "username": "user"}}
        }
        from pm.config.models import PMConfig, AccountConfig, ProjectConfig
        mock_cfg.return_value = PMConfig(
            accounts={"personal": AccountConfig(token_source="credentials", default=True)},
            projects={
                "myproject": ProjectConfig(
                    account="personal",
                    repos=["user/repo1"],
                )
            },
        )

        # Mock httpx.get at the module level where it's imported
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "number": 1,
                "title": "Test PR",
                "state": "open",
                "user": {"login": "user"},
                "created_at": "2026-03-25T10:00:00Z",
                "updated_at": "2026-03-25T12:00:00Z",
                "html_url": "https://github.com/user/repo1/pull/1",
            }
        ]

        import httpx as httpx_mod
        with patch.object(httpx_mod, "get", return_value=mock_resp):
            projects, prs = _fetch_live_projects_and_prs()

        assert len(projects) == 1
        assert projects[0].name == "myproject"
        assert projects[0].open_prs == 1
        assert "myproject" in prs
        assert len(prs["myproject"]) == 1
        assert prs["myproject"][0].title == "Test PR"

    @patch("pm.config.loader.load_config")
    @patch("pm.auth.credentials.load_credentials")
    def test_auto_discovers_without_config(self, mock_creds, mock_cfg):
        mock_creds.return_value = {
            "accounts": {
                "personal": {
                    "token": "ghp_test",
                    "username": "user",
                    "selected_repos": ["user/repo1"],
                },
            }
        }
        from pm.config.models import PMConfig
        mock_cfg.return_value = PMConfig()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        import httpx as httpx_mod
        with patch.object(httpx_mod, "get", return_value=mock_resp):
            projects, prs = _fetch_live_projects_and_prs()

        # Each selected repo becomes its own card, named by repo name (not owner)
        assert len(projects) == 1
        assert projects[0].name == "repo1"
        assert "user/repo1" in projects[0].repos

    @patch("pm.auth.credentials.load_project_groups")
    @patch("pm.config.loader.load_config")
    @patch("pm.auth.credentials.load_credentials")
    def test_auto_discovers_multiple_repos_as_separate_cards(self, mock_creds, mock_cfg, mock_groups):
        mock_creds.return_value = {
            "accounts": {
                "account-1": {
                    "token": "ghp_test",
                    "username": "user",
                    "selected_repos": ["user/repo1", "user/repo2", "org/repo3"],
                },
            }
        }
        mock_groups.return_value = {}
        from pm.config.models import PMConfig
        mock_cfg.return_value = PMConfig()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        import httpx as httpx_mod
        with patch.object(httpx_mod, "get", return_value=mock_resp):
            projects, prs = _fetch_live_projects_and_prs()

        assert len(projects) == 3
        names = {p.name for p in projects}
        assert names == {"repo1", "repo2", "repo3"}

    @patch("pm.auth.credentials.load_project_groups")
    @patch("pm.config.loader.load_config")
    @patch("pm.auth.credentials.load_credentials")
    def test_project_groups_create_grouped_cards(self, mock_creds, mock_cfg, mock_groups):
        mock_creds.return_value = {
            "accounts": {
                "account-1": {
                    "token": "ghp_test",
                    "username": "user",
                    "selected_repos": ["user/repo1", "user/repo2"],
                },
            }
        }
        mock_groups.return_value = {
            "My Group": ["user/repo1", "user/repo2"],
        }
        from pm.config.models import PMConfig
        mock_cfg.return_value = PMConfig()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        import httpx as httpx_mod
        with patch.object(httpx_mod, "get", return_value=mock_resp):
            projects, prs = _fetch_live_projects_and_prs()

        assert len(projects) == 1
        assert projects[0].name == "My Group"
        assert projects[0].repos == ["user/repo1", "user/repo2"]


class TestTUILiveMode:
    @pytest.mark.asyncio
    @patch("pm.tui.screens.portfolio._has_credentials", return_value=False)
    @patch("pm.tui.screens.portfolio._is_demo", return_value=False)
    async def test_no_credentials_shows_empty_state(self, mock_demo, mock_creds):
        """Without credentials and not in demo mode, show empty state."""
        app = PMApp(demo=False)
        async with app.run_test() as pilot:
            # Empty state should be visible
            empty = app.query_one("#empty-state-container")
            assert "visible" in empty.classes
            # Cards scroll should be hidden
            scroll = app.query_one("#cards-scroll")
            assert "hidden" in scroll.classes

    @pytest.mark.asyncio
    async def test_demo_flag_shows_demo_data(self):
        """With --demo flag, always show demo data."""
        app = PMApp(demo=True)
        async with app.run_test() as pilot:
            cards = app.query(ProjectCard)
            assert len(cards) == 4
            screen = app.screen
            assert isinstance(screen, PortfolioScreen)
            assert screen.current_project.name == "401K Website"
