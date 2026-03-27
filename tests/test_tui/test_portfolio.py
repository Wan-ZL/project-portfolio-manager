from __future__ import annotations

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.widgets.project_list import ProjectList
from pm.tui.widgets.detail_panel import DetailPanel


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
async def test_project_list_renders():
    app = PMApp()
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)
        assert project_list is not None
        assert len(project_list._items) == 4


@pytest.mark.asyncio
async def test_detail_panel_renders():
    app = PMApp()
    async with app.run_test() as pilot:
        detail = app.query_one(DetailPanel)
        assert detail is not None


@pytest.mark.asyncio
async def test_keyboard_navigation_down():
    app = PMApp()
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)
        assert project_list.selected_index == 0

        await pilot.press("j")
        assert project_list.selected_index == 1

        await pilot.press("j")
        assert project_list.selected_index == 2


@pytest.mark.asyncio
async def test_keyboard_navigation_up():
    app = PMApp()
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)

        await pilot.press("j")
        await pilot.press("j")
        assert project_list.selected_index == 2

        await pilot.press("k")
        assert project_list.selected_index == 1


@pytest.mark.asyncio
async def test_keyboard_navigation_bounds():
    app = PMApp()
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)

        # Should not go below 0
        await pilot.press("k")
        assert project_list.selected_index == 0

        # Navigate to end
        for _ in range(10):
            await pilot.press("j")
        assert project_list.selected_index == 3  # 4 items, max index 3


@pytest.mark.asyncio
async def test_tab_switching():
    app = PMApp()
    async with app.run_test() as pilot:
        from textual.widgets import TabbedContent
        tabs = app.query_one(TabbedContent)
        assert tabs is not None
        # Just verify it doesn't crash
        await pilot.press("tab")
        await pilot.press("tab")


@pytest.mark.asyncio
async def test_first_project_selected_on_mount():
    app = PMApp()
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)
        assert project_list.current_project is not None
        assert project_list.current_project.name == "401K Website"


@pytest.mark.asyncio
async def test_quit_binding():
    app = PMApp()
    async with app.run_test() as pilot:
        await pilot.press("q")
        # App should be closing or closed
