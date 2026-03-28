from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from pm.tui.app import PMApp
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.screens.settings import SettingsScreen, AccountItem
from pm.tui.screens.repo_selector import RepoSelectorScreen, RepoItem
from pm.auth.credentials import (
    list_accounts,
    load_credentials,
    next_account_id,
    remove_account,
    save_account,
    save_credentials,
    save_selected_repos,
    get_selected_repos,
)


# ────────────────────── Credential helpers ──────────────────────


@pytest.fixture
def cred_file(tmp_path):
    return tmp_path / "credentials.yaml"


class TestListAccounts:
    def test_empty(self, cred_file):
        result = list_accounts(cred_file)
        assert result == []

    def test_single_account(self, cred_file):
        save_account("account-1", "ghp_abc", "alice", cred_file)
        result = list_accounts(cred_file)
        assert len(result) == 1
        assert result[0]["id"] == "account-1"
        assert result[0]["username"] == "alice"
        assert result[0]["has_token"] is True

    def test_multiple_accounts(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        save_account("account-2", "ghp_b", "bob", cred_file)
        result = list_accounts(cred_file)
        assert len(result) == 2
        ids = {a["id"] for a in result}
        assert ids == {"account-1", "account-2"}


class TestNextAccountId:
    def test_first_account(self, cred_file):
        assert next_account_id(cred_file) == "account-1"

    def test_increments(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        assert next_account_id(cred_file) == "account-2"

    def test_fills_gap(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        save_account("account-3", "ghp_c", "charlie", cred_file)
        # account-2 is free
        assert next_account_id(cred_file) == "account-2"


class TestRemoveAccount:
    def test_remove_existing(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        remove_account("account-1", cred_file)
        result = list_accounts(cred_file)
        assert len(result) == 0

    def test_remove_nonexistent(self, cred_file):
        # Should not raise
        remove_account("account-99", cred_file)


class TestSelectedRepos:
    def test_save_and_get(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        save_selected_repos("account-1", ["alice/repo1", "alice/repo2"], cred_file)
        result = get_selected_repos("account-1", cred_file)
        assert result == ["alice/repo1", "alice/repo2"]

    def test_empty_by_default(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        result = get_selected_repos("account-1", cred_file)
        assert result == []

    def test_preserves_selected_repos_on_resave(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        save_selected_repos("account-1", ["alice/repo1"], cred_file)
        # Re-saving the account should preserve selected_repos
        save_account("account-1", "ghp_b", "alice", cred_file)
        result = get_selected_repos("account-1", cred_file)
        assert result == ["alice/repo1"]

    def test_nonexistent_account(self, cred_file):
        result = get_selected_repos("nonexistent", cred_file)
        assert result == []


# ────────────────────── TUI: Settings Screen ──────────────────────


@pytest.mark.asyncio
async def test_settings_screen_renders():
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen())
        await pilot.pause()
        assert isinstance(app.screen, SettingsScreen)


@pytest.mark.asyncio
async def test_settings_screen_has_title():
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen())
        await pilot.pause()
        title = app.query_one("#settings-title")
        assert title is not None


@pytest.mark.asyncio
async def test_settings_screen_has_add_button():
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen())
        await pilot.pause()
        btn = app.query_one("#add-account-btn")
        assert btn is not None


@pytest.mark.asyncio
async def test_settings_screen_escape_goes_back():
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen())
        await pilot.pause()
        assert isinstance(app.screen, SettingsScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, SettingsScreen)


@pytest.mark.asyncio
async def test_settings_screen_shows_general_settings():
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen())
        await pilot.pause()
        content = app.query_one("#general-settings-content")
        assert content is not None


# ────────────────────── TUI: Repo Selector Screen ──────────────────────


@pytest.mark.asyncio
async def test_repo_selector_renders():
    app = PMApp()
    screen = RepoSelectorScreen(
        account_id="account-1",
        username="alice",
        token="ghp_fake",
        selected_repos=["alice/repo1"],
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, RepoSelectorScreen)


@pytest.mark.asyncio
async def test_repo_selector_has_title():
    app = PMApp()
    screen = RepoSelectorScreen(
        account_id="account-1",
        username="alice",
        token="ghp_fake",
        selected_repos=[],
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        title = app.query_one("#repo-selector-title")
        assert title is not None


@pytest.mark.asyncio
async def test_repo_selector_escape_cancels():
    app = PMApp()
    screen = RepoSelectorScreen(
        account_id="account-1",
        username="alice",
        token="ghp_fake",
        selected_repos=[],
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, RepoSelectorScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, RepoSelectorScreen)


# ────────────────────── TUI: Portfolio empty state ──────────────────────


@pytest.mark.asyncio
async def test_portfolio_has_empty_state_container():
    """Portfolio should have an empty state container."""
    app = PMApp()
    async with app.run_test() as pilot:
        container = app.query_one("#empty-state-container")
        assert container is not None


@pytest.mark.asyncio
async def test_comma_opens_settings_from_portfolio():
    """Pressing comma in Portfolio should open Settings screen."""
    app = PMApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, PortfolioScreen)

        await pilot.press("comma")
        await pilot.pause()
        assert isinstance(app.screen, SettingsScreen)


@pytest.mark.asyncio
async def test_demo_mode_shows_portfolio_not_empty():
    """In demo mode, portfolio body should be visible, not the empty state."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, PortfolioScreen)
        body = app.query_one("#portfolio-body")
        assert "hidden" not in body.classes
