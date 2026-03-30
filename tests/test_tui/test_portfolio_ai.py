from __future__ import annotations

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.widgets.project_card import ProjectCard

from tests.conftest import make_seeded_app


@pytest.mark.asyncio
async def test_app_launches():
    app = PMApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, PortfolioScreen)


@pytest.mark.asyncio
async def test_default_mode_launches():
    app = PMApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, PortfolioScreen)


# --- AI Summary in cards ---

@pytest.mark.asyncio
async def test_cards_render_with_summaries():
    app = make_seeded_app()
    async with app.run_test() as pilot:
        cards = app.query(ProjectCard)
        assert len(cards) == 4
        for card in cards:
            assert card.project.name != ""


@pytest.mark.asyncio
async def test_ai_summary_loaded():
    app = make_seeded_app()
    async with app.run_test() as pilot:
        store = app.store
        has_ai = any(
            pd.ai_summary is not None
            for pd in store.get_projects_ordered()
        )
        assert has_ai


@pytest.mark.asyncio
async def test_selecting_project_changes_selection():
    app = make_seeded_app()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        await pilot.press("j")
        await pilot.pause()
        assert screen.current_project.name == "Side Project"


@pytest.mark.asyncio
async def test_navigating_projects_updates_selection():
    app = make_seeded_app()
    async with app.run_test() as pilot:
        screen = app.screen
        assert isinstance(screen, PortfolioScreen)
        for i in range(3):
            await pilot.press("j")
            await pilot.pause()
        assert screen.current_project.name == "Internal Tool"


# --- Refresh ('r' key) ---

@pytest.mark.asyncio
async def test_refresh_key_binding():
    app = make_seeded_app()
    async with app.run_test() as pilot:
        await pilot.press("r")
        await pilot.pause()


# --- Navigation ---

@pytest.mark.asyncio
async def test_enter_project():
    app = make_seeded_app()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
        from pm.tui.screens.project import ProjectScreen
        assert isinstance(app.screen, ProjectScreen)


@pytest.mark.asyncio
async def test_enter_and_back():
    app = make_seeded_app()
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
    app = make_seeded_app()
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()


# --- Card widget tests ---

@pytest.mark.asyncio
async def test_cards_have_pr_data():
    app = make_seeded_app()
    async with app.run_test() as pilot:
        cards = app.query(ProjectCard)
        first_card = cards[0]
        assert len(first_card._prs) > 0


@pytest.mark.asyncio
async def test_card_selection_visual():
    app = make_seeded_app()
    async with app.run_test() as pilot:
        cards = list(app.query(ProjectCard))
        assert cards[0].selected is True
        assert cards[1].selected is False

        await pilot.press("j")
        await pilot.pause()
        assert cards[0].selected is False
        assert cards[1].selected is True
