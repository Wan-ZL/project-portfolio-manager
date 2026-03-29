from __future__ import annotations

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.widgets.project_card import ProjectCard


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
        cards = app.query(ProjectCard)
        assert len(cards) == 4


@pytest.mark.asyncio
async def test_demo_mode_projects_have_summaries():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        cards = app.query(ProjectCard)
        for card in cards:
            assert card.project.summary != ""


@pytest.mark.asyncio
async def test_demo_mode_first_project_name():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        assert screen.current_project.name == "401K Website"


@pytest.mark.asyncio
async def test_non_demo_mode_launches():
    app = PMApp(demo=False)
    async with app.run_test() as pilot:
        assert app.demo_mode is False
        assert isinstance(app.screen, PortfolioScreen)


# --- AI Summary in cards ---

@pytest.mark.asyncio
async def test_cards_render_with_summaries():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        cards = app.query(ProjectCard)
        assert len(cards) == 4
        # Each card should have project info
        for card in cards:
            assert card.project.name != ""


@pytest.mark.asyncio
async def test_ai_summary_loaded_in_demo():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        # Demo summaries should be populated in the store
        store = app.store
        has_ai = any(
            pd.ai_summary is not None
            for pd in store.get_projects_ordered()
        )
        assert has_ai


@pytest.mark.asyncio
async def test_selecting_project_changes_selection():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        # Navigate to second project
        await pilot.press("j")
        await pilot.pause()
        assert screen.current_project.name == "Side Project"


@pytest.mark.asyncio
async def test_navigating_projects_updates_selection():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        # Navigate through all projects
        for i in range(3):
            await pilot.press("j")
            await pilot.pause()
        assert screen.current_project.name == "Internal Tool"


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

        # Press refresh
        await pilot.press("r")
        await pilot.pause()

        # Should reload demo data in the store
        store = app.store
        has_ai = any(
            pd.ai_summary is not None
            for pd in store.get_projects_ordered()
        )
        assert has_ai


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


# --- Help key ---

@pytest.mark.asyncio
async def test_help_key_shows_help():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        # Should show help screen


# --- Card widget tests ---

@pytest.mark.asyncio
async def test_cards_have_pr_data():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        cards = app.query(ProjectCard)
        # 401K Website card should have PRs
        first_card = cards[0]
        assert len(first_card._prs) > 0


@pytest.mark.asyncio
async def test_card_selection_visual():
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        cards = list(app.query(ProjectCard))
        # First card should be selected
        assert cards[0].selected is True
        assert cards[1].selected is False

        # Navigate down
        await pilot.press("j")
        await pilot.pause()
        assert cards[0].selected is False
        assert cards[1].selected is True
