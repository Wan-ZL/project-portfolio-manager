from __future__ import annotations

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.help import HelpScreen
from pm.tui.screens.portfolio import PortfolioScreen


@pytest.mark.asyncio
async def test_help_screen_composes():
    """Help screen should compose without errors."""
    app = PMApp()
    async with app.run_test() as pilot:
        # Push help screen
        app.push_screen(HelpScreen())
        await pilot.pause()
        # Should be showing HelpScreen
        assert isinstance(app.screen, HelpScreen)


@pytest.mark.asyncio
async def test_help_screen_has_title():
    """Help screen should have a title."""
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        title = app.query_one("#help-title")
        assert title is not None


@pytest.mark.asyncio
async def test_help_screen_has_version():
    """Help screen should show version."""
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        version_widget = app.query_one("#help-version")
        assert version_widget is not None


@pytest.mark.asyncio
async def test_help_screen_has_shortcuts():
    """Help screen should list shortcuts."""
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        # Should have section headers
        sections = app.query(".help-section-header")
        assert len(sections) >= 3  # Portfolio, Project, Task sections

        # Should have shortcut rows
        shortcuts = app.query(".help-shortcut-row")
        assert len(shortcuts) >= 10


@pytest.mark.asyncio
async def test_help_screen_dismiss_with_escape():
    """Help screen should dismiss on Escape."""
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


@pytest.mark.asyncio
async def test_help_screen_dismiss_with_question_mark():
    """Help screen should dismiss on ? key."""
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("question_mark")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


@pytest.mark.asyncio
async def test_help_screen_dismiss_with_q():
    """Help screen should dismiss on q key."""
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("q")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


@pytest.mark.asyncio
async def test_help_screen_has_footer():
    """Help screen should have a footer with dismiss instructions."""
    app = PMApp()
    async with app.run_test() as pilot:
        app.push_screen(HelpScreen())
        await pilot.pause()
        footer = app.query_one("#help-footer")
        assert footer is not None


@pytest.mark.asyncio
async def test_portfolio_question_mark_opens_help():
    """Pressing ? in Portfolio view should open the help screen."""
    app = PMApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, PortfolioScreen)

        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
