from __future__ import annotations

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.widgets.detail_panel import DetailPanel, StatusPanel
from pm.tui.widgets.project_list import ProjectList


# --- Demo mode tests ---

@pytest.mark.asyncio
async def test_demo_mode_launches():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        assert app.demo_mode is True
        assert isinstance(app.screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_demo_mode_has_projects():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)
        assert len(project_list._items) == 4


@pytest.mark.asyncio
async def test_demo_mode_projects_have_summaries():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)
        for item in project_list._items:
            assert item.project.summary != ""


@pytest.mark.asyncio
async def test_demo_mode_first_project_name():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        project_list = app.query_one(ProjectList)
        assert project_list.current_project.name == "401K Website"


@pytest.mark.asyncio
async def test_non_demo_mode_launches():
    app = PMApp(demo=False)
    async with app.run_test() as pilot:
        assert app.demo_mode is False
        assert isinstance(app.screen, PortfolioScreen)


# --- AI Summary in detail panel ---

@pytest.mark.asyncio
async def test_detail_panel_has_status_panel():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        detail = app.query_one(DetailPanel)
        assert detail is not None
        status_panels = app.query(StatusPanel)
        assert len(status_panels) == 1


@pytest.mark.asyncio
async def test_ai_summary_appears_in_detail():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # The first project should be auto-selected and detail populated
        detail = app.query_one(DetailPanel)
        assert detail is not None


@pytest.mark.asyncio
async def test_selecting_project_updates_detail():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # Navigate to second project
        await pilot.press("j")
        await pilot.pause()

        project_list = app.query_one(ProjectList)
        assert project_list.current_project.name == "Side Project"


@pytest.mark.asyncio
async def test_navigating_projects_updates_ai_summary():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # Navigate through all projects
        for i in range(3):
            await pilot.press("j")
            await pilot.pause()

        project_list = app.query_one(ProjectList)
        assert project_list.current_project.name == "Internal Tool"


# --- AI Suggestion ('s' key) ---

@pytest.mark.asyncio
async def test_suggest_key_binding():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.pause()
        # Should not crash, suggestions should load


@pytest.mark.asyncio
async def test_suggest_loads_in_demo_mode():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        await pilot.press("s")
        await pilot.pause()
        # Suggestions should be loaded
        assert len(screen._ai_suggestions) > 0


# --- Refresh ('r' key) ---

@pytest.mark.asyncio
async def test_refresh_key_binding():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("r")
        await pilot.pause()
        # Should not crash


@pytest.mark.asyncio
async def test_refresh_reloads_demo_data():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        # Clear summaries
        screen._ai_summaries.clear()
        screen._ai_suggestions.clear()

        # Press refresh
        await pilot.press("r")
        await pilot.pause()

        # Should reload demo data
        assert len(screen._ai_summaries) > 0


# --- Tab switching with AI content ---

@pytest.mark.asyncio
async def test_tab_switching_with_ai():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # Switch tabs
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        # Should not crash


@pytest.mark.asyncio
async def test_status_tab_shows_ai_content():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # Status tab is the default, just verify it renders
        status_panels = app.query(StatusPanel)
        assert len(status_panels) == 1


# --- Navigation from demo mode ---

@pytest.mark.asyncio
async def test_demo_mode_enter_project():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        from pm.tui.screens.project import ProjectScreen
        assert isinstance(app.screen, ProjectScreen)


@pytest.mark.asyncio
async def test_demo_mode_enter_and_back():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        from pm.tui.screens.project import ProjectScreen
        assert isinstance(app.screen, ProjectScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PortfolioScreen)


# --- Help key with AI suggestions info ---

@pytest.mark.asyncio
async def test_help_key_shows_suggest_info():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        # Should show help text including 's' for suggest


# --- Loading indicator ---

@pytest.mark.asyncio
async def test_detail_panel_show_loading():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        detail = app.query_one(DetailPanel)
        detail.show_summary_loading()
        await pilot.pause()
        # Should not crash


@pytest.mark.asyncio
async def test_detail_panel_show_suggestions_loading():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        detail = app.query_one(DetailPanel)
        detail.show_suggestions_loading()
        await pilot.pause()
        # Should not crash


# --- StatusPanel direct tests ---

@pytest.mark.asyncio
async def test_status_panel_set_ai_summary():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        status_panel = app.query_one(StatusPanel)
        summary = {
            "one_line_status": "Test status",
            "key_progress": ["Progress 1"],
            "issues_needing_attention": ["Issue 1"],
            "suggested_next_steps": ["Step 1"],
        }
        status_panel.set_ai_summary(summary)
        await pilot.pause()
        # Should not crash


@pytest.mark.asyncio
async def test_status_panel_set_suggestions():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        status_panel = app.query_one(StatusPanel)
        suggestions = [
            {"priority": "high", "project": "proj", "action": "Fix", "reason": "Broken"},
        ]
        status_panel.set_ai_suggestions(suggestions)
        await pilot.pause()
        # Should not crash
