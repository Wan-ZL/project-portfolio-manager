from __future__ import annotations

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.widgets.project_card import ProjectCard


@pytest.mark.asyncio
async def test_app_launches():
    app = PMApp()
    async with app.run_test() as pilot:
        assert app.screen is not None


@pytest.mark.asyncio
async def test_portfolio_screen_mounted():
    app = PMApp()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_project_cards_render():
    app = PMApp()
    async with app.run_test() as pilot:
        cards = app.query(ProjectCard)
        assert len(cards) == 4


@pytest.mark.asyncio
async def test_keyboard_navigation_down():
    app = PMApp()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        assert screen._selected_index == 0

        await pilot.press("j")
        assert screen._selected_index == 1

        await pilot.press("j")
        assert screen._selected_index == 2


@pytest.mark.asyncio
async def test_keyboard_navigation_up():
    app = PMApp()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)

        await pilot.press("j")
        await pilot.press("j")
        assert screen._selected_index == 2

        await pilot.press("k")
        assert screen._selected_index == 1


@pytest.mark.asyncio
async def test_keyboard_navigation_bounds():
    app = PMApp()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)

        # Should not go below 0
        await pilot.press("k")
        assert screen._selected_index == 0

        # Navigate to end
        for _ in range(10):
            await pilot.press("j")
        assert screen._selected_index == 3  # 4 items, max index 3


@pytest.mark.asyncio
async def test_first_project_selected_on_mount():
    app = PMApp()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        assert screen.current_project is not None
        assert screen.current_project.name == "401K Website"


@pytest.mark.asyncio
async def test_quit_binding():
    app = PMApp()
    async with app.run_test() as pilot:
        await pilot.press("q")
        # App should be closing or closed
