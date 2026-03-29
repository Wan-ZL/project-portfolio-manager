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
    app = PMApp(demo=True)
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


# --- 3-line card format tests ---

@pytest.mark.asyncio
async def test_card_has_three_lines():
    """Each card should have exactly 3 Static children (line1, line2, line3)."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        from textual.widgets import Static
        cards = list(app.query(ProjectCard))
        assert len(cards) > 0
        for card in cards:
            statics = list(card.query(Static))
            assert len(statics) == 3, f"Card {card.project.name} has {len(statics)} lines, expected 3"


@pytest.mark.asyncio
async def test_card_line1_has_name():
    """Line 1 should contain the project name."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        from textual.widgets import Static
        cards = list(app.query(ProjectCard))
        first_card = cards[0]
        statics = list(first_card.query(Static))
        line1_text = statics[0].renderable
        assert "401K Website" in str(line1_text)


@pytest.mark.asyncio
async def test_card_set_card_data():
    """set_card_data should update the card's _card_data."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        cards = list(app.query(ProjectCard))
        card = cards[0]
        card.set_card_data(
            {"dynamic": "test dynamic", "recommendation": "do X", "last_command_summary": "ran Y"},
            status="running",
            time="2h ago",
        )
        assert card._card_data is not None
        assert card._card_data["dynamic"] == "test dynamic"
        assert card._last_command_status == "running"
        assert card._last_command_time == "2h ago"


@pytest.mark.asyncio
async def test_demo_card_summaries_applied():
    """In demo mode, card data should be populated from DEMO_CARD_SUMMARIES."""
    app = PMApp(demo=True)
    async with app.run_test() as pilot:
        cards = list(app.query(ProjectCard))
        # 401K Website should have card data from demo
        first_card = cards[0]
        assert first_card._card_data is not None
        assert "PR #42" in first_card._card_data.get("dynamic", "")
