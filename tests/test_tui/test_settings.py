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
from pm.tui.screens.settings import SettingsScreen, AccountItem, ProjectGroupItem
from pm.tui.screens.repo_selector import RepoSelectorScreen, RepoItem
from pm.auth.credentials import (
    add_project_group,
    get_display_name,
    list_accounts,
    load_credentials,
    load_project_groups,
    next_account_id,
    remove_account,
    remove_project_group,
    rename_account,
    save_account,
    save_credentials,
    save_project_groups,
    save_selected_repos,
    get_selected_repos,
    update_project_group,
)
from pm.config.settings import (
    load_settings,
    save_settings,
    update_setting,
    DEFAULT_SETTINGS,
)


# ────────────────────── Credential helpers ──────────────────────


@pytest.fixture
def cred_file(tmp_path):
    return tmp_path / "credentials.yaml"


@pytest.fixture
def settings_file(tmp_path):
    return tmp_path / "settings.yaml"


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

    def test_display_name_default(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        result = list_accounts(cred_file)
        assert result[0]["display_name"] == "GitHub 1"

    def test_display_name_custom(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        rename_account("account-1", "Personal", cred_file)
        result = list_accounts(cred_file)
        assert result[0]["display_name"] == "Personal"


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

    def test_remove_preserves_others(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        save_account("account-2", "ghp_b", "bob", cred_file)
        remove_account("account-1", cred_file)
        result = list_accounts(cred_file)
        assert len(result) == 1
        assert result[0]["id"] == "account-2"


class TestRenameAccount:
    def test_rename(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        rename_account("account-1", "Personal", cred_file)
        name = get_display_name("account-1", cred_file)
        assert name == "Personal"

    def test_rename_nonexistent(self, cred_file):
        # Should not raise
        rename_account("account-99", "Name", cred_file)

    def test_rename_preserves_token(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        rename_account("account-1", "Work", cred_file)
        creds = load_credentials(cred_file)
        assert creds["accounts"]["account-1"]["token"] == "ghp_a"
        assert creds["accounts"]["account-1"]["username"] == "alice"

    def test_default_display_name(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        name = get_display_name("account-1", cred_file)
        assert name == "GitHub 1"

    def test_display_name_account_2(self, cred_file):
        save_account("account-2", "ghp_b", "bob", cred_file)
        name = get_display_name("account-2", cred_file)
        assert name == "GitHub 2"


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

    def test_preserves_display_name_on_resave(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        rename_account("account-1", "Work", cred_file)
        save_account("account-1", "ghp_b", "alice", cred_file)
        name = get_display_name("account-1", cred_file)
        assert name == "Work"


# ────────────────────── Project Groups ──────────────────────


class TestProjectGroups:
    def test_empty_by_default(self, cred_file):
        result = load_project_groups(cred_file)
        assert result == {}

    def test_add_group(self, cred_file):
        add_project_group("Web App", ["alice/repo1", "alice/repo2"], cred_file)
        groups = load_project_groups(cred_file)
        assert "Web App" in groups
        assert groups["Web App"] == ["alice/repo1", "alice/repo2"]

    def test_remove_group(self, cred_file):
        add_project_group("Web App", ["alice/repo1"], cred_file)
        remove_project_group("Web App", cred_file)
        groups = load_project_groups(cred_file)
        assert "Web App" not in groups

    def test_update_group(self, cred_file):
        add_project_group("Web App", ["alice/repo1"], cred_file)
        update_project_group("Web App", ["alice/repo1", "bob/repo2"], cred_file)
        groups = load_project_groups(cred_file)
        assert groups["Web App"] == ["alice/repo1", "bob/repo2"]

    def test_multiple_groups(self, cred_file):
        add_project_group("Project A", ["a/r1"], cred_file)
        add_project_group("Project B", ["b/r2"], cred_file)
        groups = load_project_groups(cred_file)
        assert len(groups) == 2
        assert "Project A" in groups
        assert "Project B" in groups

    def test_remove_nonexistent_group(self, cred_file):
        remove_project_group("nonexistent", cred_file)
        groups = load_project_groups(cred_file)
        assert groups == {}

    def test_groups_preserve_accounts(self, cred_file):
        save_account("account-1", "ghp_a", "alice", cred_file)
        add_project_group("Web App", ["alice/repo1"], cred_file)
        result = list_accounts(cred_file)
        assert len(result) == 1
        assert result[0]["username"] == "alice"

    def test_save_and_load_groups(self, cred_file):
        groups = {"G1": ["a/r1", "a/r2"], "G2": ["b/r3"]}
        save_project_groups(groups, cred_file)
        loaded = load_project_groups(cred_file)
        assert loaded == groups


# ────────────────────── Settings YAML ──────────────────────


class TestSettingsYaml:
    def test_default_settings(self, settings_file):
        settings = load_settings(settings_file)
        assert settings["overlay"]["enabled"] is False
        assert settings["overlay"]["show_count"] == 3
        assert settings["overlay"]["position"] == "bottom-right"
        assert settings["overlay"]["opacity"] == 70
        assert settings["general"]["default_agent"] == "claude-code"
        assert settings["general"]["poll_interval"] == "5s"

    def test_save_and_load(self, settings_file):
        data = {
            "overlay": {
                "enabled": True,
                "show_count": 5,
                "position": "top-left",
                "opacity": 50,
            },
            "general": {
                "default_agent": "gpt-4",
                "poll_interval": "10s",
            },
        }
        save_settings(data, settings_file)
        loaded = load_settings(settings_file)
        assert loaded["overlay"]["enabled"] is True
        assert loaded["overlay"]["show_count"] == 5
        assert loaded["overlay"]["position"] == "top-left"
        assert loaded["general"]["default_agent"] == "gpt-4"

    def test_update_setting(self, settings_file):
        update_setting("overlay", "enabled", True, settings_file)
        settings = load_settings(settings_file)
        assert settings["overlay"]["enabled"] is True
        # Other defaults should still be present
        assert settings["overlay"]["show_count"] == 3

    def test_update_preserves_other_keys(self, settings_file):
        update_setting("overlay", "opacity", 50, settings_file)
        update_setting("general", "default_agent", "gpt-4", settings_file)
        settings = load_settings(settings_file)
        assert settings["overlay"]["opacity"] == 50
        assert settings["general"]["default_agent"] == "gpt-4"
        # Defaults should remain
        assert settings["overlay"]["enabled"] is False

    def test_partial_file_gets_defaults(self, settings_file):
        # Write only overlay section
        save_settings({"overlay": {"enabled": True}}, settings_file)
        settings = load_settings(settings_file)
        assert settings["overlay"]["enabled"] is True
        # Missing overlay keys get defaults
        assert settings["overlay"]["show_count"] == 3
        # Missing general section gets defaults
        assert settings["general"]["default_agent"] == "claude-code"


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
async def test_settings_screen_has_four_sections():
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen())
        await pilot.pause()
        headers = app.query(".settings-section-header")
        assert len(headers) == 4


@pytest.mark.asyncio
async def test_settings_screen_has_overlay_container():
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen())
        await pilot.pause()
        container = app.query_one("#overlay-settings-container")
        assert container is not None


@pytest.mark.asyncio
async def test_settings_screen_has_general_container():
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(SettingsScreen())
        await pilot.pause()
        container = app.query_one("#general-settings-container")
        assert container is not None


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


@pytest.mark.asyncio
async def test_repo_selector_has_count_status():
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
        status = app.query_one("#repo-count-status")
        assert status is not None


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
async def test_with_data_shows_portfolio_not_empty():
    """With store data, cards scroll should be visible, not the empty state."""
    from tests.conftest import make_seeded_app
    app = make_seeded_app()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, PortfolioScreen)
        scroll = app.query_one("#cards-scroll")
        assert "hidden" not in scroll.classes
