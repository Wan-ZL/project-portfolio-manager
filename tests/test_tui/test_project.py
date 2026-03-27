from __future__ import annotations

from datetime import datetime

import pytest

from pm.github.pr import EnhancedPR
from pm.tui.app import PMApp
from pm.tui.screens.project import ProjectScreen, PRListItem, SessionListItem, InfoTab
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


def make_project():
    return ProjectInfo(
        name="Test Project",
        account="Personal",
        repos=["owner/frontend", "owner/backend"],
        open_prs=3,
        active_sessions=1,
        status="green",
        summary="Test project summary.",
    )


def make_prs():
    return [
        EnhancedPR(
            repo_id="owner/frontend", number=42, title="Fix auth bug",
            state="open", author="ai-bot", ci_status="failing",
            review_status="changes_requested",
            created_at=datetime(2026, 3, 20), updated_at=datetime(2026, 3, 25),
            unresolved_count=3, needs_attention=True,
        ),
        EnhancedPR(
            repo_id="owner/frontend", number=38, title="Add mobile layout",
            state="open", author="user", ci_status="passing",
            review_status="approved",
            created_at=datetime(2026, 3, 18), updated_at=datetime(2026, 3, 24),
        ),
        EnhancedPR(
            repo_id="owner/backend", number=12, title="API update",
            state="open", author="user", ci_status="passing",
            review_status="pending",
            created_at=datetime(2026, 3, 10), updated_at=datetime(2026, 3, 20),
        ),
    ]


def make_sessions():
    return [
        SessionInfo(
            id="s-001", project="Test Project", task="Fix auth bug",
            agent="claude-code", status="running",
            created_at=datetime(2026, 3, 25, 14, 30),
            branch="pm/fix-auth", pr_number=42,
        ),
    ]


@pytest.mark.asyncio
async def test_project_screen_renders():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(),
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        # Verify the screen is mounted
        assert isinstance(app.screen, ProjectScreen)


@pytest.mark.asyncio
async def test_project_screen_has_title():
    app = PMApp()
    screen = ProjectScreen(project=make_project(), prs=make_prs())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        title = app.query_one("#project-title")
        assert title is not None


@pytest.mark.asyncio
async def test_project_screen_has_left_panel_items():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(),
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        # Should have PR items and session items
        pr_items = app.query(PRListItem)
        session_items = app.query(SessionListItem)
        assert len(pr_items) == 3
        assert len(session_items) == 1


@pytest.mark.asyncio
async def test_project_screen_keyboard_navigation():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(),
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        # Navigate down
        await pilot.press("j")
        assert screen._selected_index == 1

        await pilot.press("j")
        assert screen._selected_index == 2


@pytest.mark.asyncio
async def test_project_screen_escape_goes_back():
    app = PMApp()
    screen = ProjectScreen(project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        await pilot.press("escape")
        await pilot.pause()
        # Should have popped back
        assert not isinstance(app.screen, ProjectScreen)


@pytest.mark.asyncio
async def test_project_screen_has_tabs():
    app = PMApp()
    screen = ProjectScreen(project=make_project(), prs=make_prs())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        from textual.widgets import TabbedContent
        tabs = app.query_one("#project-detail-tabs", TabbedContent)
        assert tabs is not None


@pytest.mark.asyncio
async def test_project_screen_info_tab_shows_project():
    app = PMApp()
    screen = ProjectScreen(project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        info_tab = app.query_one("#info-tab-content", InfoTab)
        assert info_tab is not None
