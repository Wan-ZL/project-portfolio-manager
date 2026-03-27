"""Full integration test: launch in demo mode and navigate through all views."""
from __future__ import annotations

from datetime import datetime

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.help import HelpScreen
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.screens.project import ProjectScreen, PRListItem, SessionListItem, InfoTab
from pm.tui.screens.task import TaskScreen
from pm.tui.widgets.detail_panel import DetailPanel, StatusPanel
from pm.tui.widgets.project_list import ProjectList
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


@pytest.mark.asyncio
async def test_demo_launches_portfolio():
    """Demo mode should launch with PortfolioScreen."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_demo_has_four_projects():
    """Demo mode should have 4 projects loaded."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)
        assert len(project_list._items) == 4


@pytest.mark.asyncio
async def test_demo_first_project_is_401k():
    """First project should be 401K Website."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)
        assert project_list.current_project.name == "401K Website"


@pytest.mark.asyncio
async def test_demo_ai_summaries_loaded():
    """AI summaries should be pre-loaded in demo mode."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        # Demo summaries should be populated
        assert len(screen._ai_summaries) > 0


@pytest.mark.asyncio
async def test_demo_ai_suggestions_loaded():
    """AI suggestions should be pre-loaded in demo mode."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        assert len(screen._ai_suggestions) > 0


@pytest.mark.asyncio
async def test_demo_navigate_down_through_projects():
    """Navigate down through all projects."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)

        await pilot.press("j")
        assert project_list.selected_index == 1
        assert project_list.current_project.name == "Side Project"

        await pilot.press("j")
        assert project_list.selected_index == 2
        assert project_list.current_project.name == "FAA Project"

        await pilot.press("j")
        assert project_list.selected_index == 3
        assert project_list.current_project.name == "Internal Tool"


@pytest.mark.asyncio
async def test_demo_enter_project_view():
    """Enter should open ProjectScreen."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)
        assert app.screen.project.name == "401K Website"


@pytest.mark.asyncio
async def test_demo_project_view_has_prs():
    """Project view should show PRs."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        pr_items = app.query(PRListItem)
        assert len(pr_items) >= 1


@pytest.mark.asyncio
async def test_demo_project_view_has_sessions():
    """Project view should show sessions for 401K."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        session_items = app.query(SessionListItem)
        assert len(session_items) >= 1


@pytest.mark.asyncio
async def test_demo_project_view_back_to_portfolio():
    """Escape in project view goes back to portfolio."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_demo_navigate_to_session():
    """Navigate to a session and open task view."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # Enter 401K Website
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        # Navigate to session item (after PRs)
        screen = app.screen
        pr_count = len([i for i in screen._all_items if isinstance(i, PRListItem)])
        for _ in range(pr_count):
            await pilot.press("j")

        # Enter the session
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TaskScreen)


@pytest.mark.asyncio
async def test_demo_task_view_back():
    """Back from task view returns to project view."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()

        # Navigate to session
        screen = app.screen
        pr_count = len([i for i in screen._all_items if isinstance(i, PRListItem)])
        for _ in range(pr_count):
            await pilot.press("j")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TaskScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)


@pytest.mark.asyncio
async def test_demo_full_navigation_flow():
    """Full navigation: Portfolio -> Project -> Task -> back -> back."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # Start in portfolio
        assert isinstance(app.screen, PortfolioScreen)

        # Enter project
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        # Navigate to session and enter
        screen = app.screen
        pr_count = len([i for i in screen._all_items if isinstance(i, PRListItem)])
        for _ in range(pr_count):
            await pilot.press("j")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TaskScreen)

        # Back to project
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        # Back to portfolio
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_demo_tab_switching():
    """Tab switching should work in portfolio view."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # Should not crash
        await pilot.press("tab")
        await pilot.press("tab")
        await pilot.press("shift+tab")


@pytest.mark.asyncio
async def test_demo_help_overlay():
    """? should open help overlay in demo mode."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_demo_detail_panel_shows_summary():
    """Detail panel should show AI summary content."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        detail = app.query_one(DetailPanel)
        assert detail is not None
        # StatusPanel should exist
        status_panel = app.query_one(StatusPanel)
        assert status_panel is not None


@pytest.mark.asyncio
async def test_demo_refresh_works():
    """Refresh should work without errors."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("r")
        await pilot.pause()
        # Should still be on portfolio
        assert isinstance(app.screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_demo_suggest_works():
    """Suggest key should load suggestions."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.pause()
        assert isinstance(app.screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_demo_project_view_keyboard_nav():
    """Keyboard navigation in project view."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ProjectScreen)

        # Navigate items
        await pilot.press("j")
        assert screen._selected_index == 1

        await pilot.press("k")
        assert screen._selected_index == 0


@pytest.mark.asyncio
async def test_demo_task_view_pause():
    """Task view pause/resume should work."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()

        # Navigate to session
        screen = app.screen
        pr_count = len([i for i in screen._all_items if isinstance(i, PRListItem)])
        for _ in range(pr_count):
            await pilot.press("j")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TaskScreen)

        task_screen = app.screen
        assert task_screen.session.status == "running"

        await pilot.press("p")
        assert task_screen.session.status == "paused"

        await pilot.press("p")
        assert task_screen.session.status == "running"


@pytest.mark.asyncio
async def test_demo_views_render_correctly():
    """All views should render without exceptions."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # Portfolio renders
        assert app.query_one(ProjectList) is not None
        assert app.query_one(DetailPanel) is not None
        assert app.query_one(StatusBar) is not None

        # Project renders
        await pilot.press("enter")
        await pilot.pause()
        assert app.query_one("#project-title") is not None
        assert app.query_one(InfoTab) is not None
        assert app.query_one(StatusBar) is not None

        # Back to portfolio
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PortfolioScreen)
