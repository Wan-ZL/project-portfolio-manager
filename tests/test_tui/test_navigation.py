from __future__ import annotations

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.screens.project import ProjectScreen
from pm.tui.screens.task import TaskScreen

from tests.conftest import make_seeded_app


@pytest.mark.asyncio
async def test_portfolio_to_project_navigation():
    """Test: Portfolio View --Enter--> Project View"""
    app = make_seeded_app()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, PortfolioScreen)

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ProjectScreen)


@pytest.mark.asyncio
async def test_project_to_portfolio_navigation():
    """Test: Project View --Esc--> Portfolio View"""
    app = make_seeded_app()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_navigate_to_different_projects():
    """Test navigating to different projects"""
    app = make_seeded_app()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)
        assert app.screen.project.name == "401K Website"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PortfolioScreen)

        await pilot.press("j")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)
        assert app.screen.project.name == "Side Project"


@pytest.mark.asyncio
async def test_project_to_task_navigation():
    """Test: Project View --Enter on session--> Task View"""
    app = make_seeded_app()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        # Navigate to the session item (after 5 PRs)
        for _ in range(5):
            await pilot.press("j")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, TaskScreen)


@pytest.mark.asyncio
async def test_task_to_project_navigation():
    """Test: Task View --Esc--> Project View"""
    app = make_seeded_app()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        for _ in range(5):
            await pilot.press("j")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TaskScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)


@pytest.mark.asyncio
async def test_full_navigation_flow():
    """Test: Portfolio -> Project -> Task -> Project -> Portfolio"""
    app = make_seeded_app()
    async with app.run_test() as pilot:
        # 1. Portfolio
        assert isinstance(app.screen, PortfolioScreen)

        # 2. Portfolio -> Project
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        # 3. Project -> Task (navigate to session)
        for _ in range(5):
            await pilot.press("j")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TaskScreen)

        # 4. Task -> Project
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        # 5. Project -> Portfolio
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PortfolioScreen)
