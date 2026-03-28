from __future__ import annotations

from datetime import datetime

import pytest

from pm.github.pr import EnhancedPR
from pm.tui.app import PMApp
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.screens.project import ProjectScreen, PRListItem, SessionListItem
from pm.tui.widgets.project_card import ProjectCard
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo


def make_project():
    return ProjectInfo(
        name="Test Project",
        account="Personal",
        repos=["owner/frontend", "owner/backend"],
        open_prs=2,
        active_sessions=1,
        status="green",
        summary="Test summary.",
    )


def make_prs():
    return [
        EnhancedPR(
            repo_id="owner/frontend", number=42, title="Fix auth bug",
            state="open", author="ai-bot", ci_status="failing",
            review_status="changes_requested",
            created_at=datetime(2026, 3, 20), updated_at=datetime(2026, 3, 25),
        ),
        EnhancedPR(
            repo_id="owner/frontend", number=38, title="Add mobile layout",
            state="open", author="user", ci_status="passing",
            review_status="approved",
            created_at=datetime(2026, 3, 18), updated_at=datetime(2026, 3, 24),
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
async def test_project_card_has_click_handler():
    """ProjectCard should have Clicked message class."""
    assert hasattr(ProjectCard, "Clicked")


@pytest.mark.asyncio
async def test_pr_list_item_has_click_handler():
    """PRListItem should have Clicked message class."""
    assert hasattr(PRListItem, "Clicked")


@pytest.mark.asyncio
async def test_session_list_item_has_click_handler():
    """SessionListItem should have Clicked message class."""
    assert hasattr(SessionListItem, "Clicked")


@pytest.mark.asyncio
async def test_portfolio_project_cards_exist():
    """Portfolio should have clickable ProjectCard widgets."""
    app = PMApp()
    async with app.run_test() as pilot:
        cards = app.query(ProjectCard)
        assert len(cards) == 4


@pytest.mark.asyncio
async def test_project_view_pr_items_clickable():
    """Project view should have clickable PRListItem widgets."""
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(),
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        pr_items = app.query(PRListItem)
        assert len(pr_items) == 2


@pytest.mark.asyncio
async def test_project_view_session_items_clickable():
    """Project view should have clickable SessionListItem widgets."""
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(),
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        session_items = app.query(SessionListItem)
        assert len(session_items) == 1


@pytest.mark.asyncio
async def test_project_click_handler_method_exists():
    """ProjectScreen should have on_pr_list_item_clicked handler."""
    screen = ProjectScreen(project=make_project())
    assert hasattr(screen, "on_pr_list_item_clicked")
    assert hasattr(screen, "on_session_list_item_clicked")


@pytest.mark.asyncio
async def test_portfolio_vertical_scroll_present():
    """Portfolio view should have scrollable containers for mouse wheel."""
    app = PMApp()
    async with app.run_test() as pilot:
        from textual.containers import VerticalScroll
        scrolls = app.query(VerticalScroll)
        assert len(scrolls) >= 1
