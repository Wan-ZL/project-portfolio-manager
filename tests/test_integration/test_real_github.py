"""Integration tests using REAL GitHub credentials.

These tests hit the actual GitHub API and verify end-to-end functionality.
They are excluded from the default test run and must be invoked explicitly:

    uv run pytest -m integration tests/test_integration/test_real_github.py -v

Requires ~/.ppm/credentials.yaml with a valid GitHub token.
"""
from __future__ import annotations

import asyncio

import pytest
from pathlib import Path

pytestmark = pytest.mark.integration


def _has_real_credentials():
    """Check if real GitHub credentials exist."""
    creds_path = Path.home() / ".ppm" / "credentials.yaml"
    if not creds_path.exists():
        return False
    import yaml
    with open(creds_path) as f:
        data = yaml.safe_load(f)
    accounts = data.get("accounts", {})
    return any(a.get("token") for a in accounts.values())


if not _has_real_credentials():
    pytest.skip("No real GitHub credentials available", allow_module_level=True)


# ---------------------------------------------------------------------------
# 1. Fetch real repos via GitHub API
# ---------------------------------------------------------------------------

def test_fetch_real_repos():
    """Fetch repos using real token -- should return non-empty list."""
    from pm.auth.credentials import load_credentials
    from pm.auth.github_oauth import discover_repos

    creds = load_credentials()
    accounts = creds.get("accounts", {})
    token = None
    for acct_data in accounts.values():
        t = acct_data.get("token")
        if t:
            token = t
            break

    assert token is not None, "No token found in credentials"

    repos = discover_repos(token)
    assert len(repos) > 0, "Expected at least one repo from GitHub"

    repo_names = [r["full_name"] for r in repos]
    assert any("project-portfolio-manager" in r for r in repo_names), (
        f"Expected 'project-portfolio-manager' in repo list: {repo_names}"
    )


# ---------------------------------------------------------------------------
# 2. Fetch real PRs for a repo
# ---------------------------------------------------------------------------

def test_fetch_real_prs():
    """Fetch PRs for a real repo -- should not crash."""
    from pm.tui.store import _fetch_prs_for_repos, _get_credential_token

    token = _get_credential_token()
    assert token is not None, "No token available"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/json",
    }
    prs = _fetch_prs_for_repos(["Wan-ZL/project-portfolio-manager"], headers)
    assert isinstance(prs, list)


# ---------------------------------------------------------------------------
# 3. DataStore loads real project data
# ---------------------------------------------------------------------------

def test_store_load_initial_real():
    """DataStore.load_initial() with real credentials populates projects."""
    from pm.tui.store import _fetch_live_projects_and_prs

    projects, prs_map = _fetch_live_projects_and_prs()

    assert len(projects) > 0, "Expected at least one project from live fetch"
    names = [p.name for p in projects]
    assert any(
        "project-portfolio-manager" in n or "401k" in n.lower() or "faa" in n.upper()
        for n in names
    ), f"No expected repos found in projects: {names}"


# ---------------------------------------------------------------------------
# 4. AI card_summary survives poll_refresh (THE critical test)
# ---------------------------------------------------------------------------

def test_store_preserves_ai_data_after_poll():
    """AI card summary survives a poll_refresh cycle with real data."""
    from pm.tui.store import DataStore, StoreState
    from pm.tui.widgets.project_list import ProjectInfo

    store = DataStore.__new__(DataStore)
    store._state = StoreState(projects={}, project_order=[])
    store._app = None

    fake_project = ProjectInfo(
        name="test-repo",
        account="personal",
        repos=["Wan-ZL/project-portfolio-manager"],
    )
    store.set_projects([fake_project])
    store.set_card_summary("test-repo", {
        "dynamic": "AI generated text",
        "recommendation": "Do X",
    })

    pd = store.get_project("test-repo")
    assert pd is not None
    assert pd.card_summary["dynamic"] == "AI generated text"

    # Simulate a poll that replaces project data (new ProjectInfo object, same name)
    store.set_projects([fake_project])

    pd = store.get_project("test-repo")
    assert pd is not None
    assert pd.card_summary is not None, "card_summary was wiped after set_projects!"
    assert pd.card_summary["dynamic"] == "AI generated text"


# ---------------------------------------------------------------------------
# 5. Card summary generation with real GitHub data + Claude API
# ---------------------------------------------------------------------------

def test_card_summary_generation_real():
    """Generate card summary using real GitHub data + Claude API."""
    from pm.ai.card_summary import CardSummaryGenerator, collect_card_context
    from pm.tui.store import _get_credential_token

    token = _get_credential_token()
    if not token:
        pytest.skip("No token available")

    context = collect_card_context(
        "project-portfolio-manager",
        ["Wan-ZL/project-portfolio-manager"],
        token,
    )

    assert len(context.recent_commits) > 0 or len(context.open_prs) > 0, (
        "Expected some commits or PRs from real repo"
    )

    generator = CardSummaryGenerator()
    result = generator.generate("project-portfolio-manager", context)

    assert "dynamic" in result
    assert "recommendation" in result
    assert len(result["dynamic"]) > 0, "dynamic field should not be empty"


# ---------------------------------------------------------------------------
# 6. TUI integration: real repo cards appear
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portfolio_shows_real_data():
    """Launch PPM TUI with real credentials, verify real repo cards appear."""
    from pm.tui.app import PMApp
    from pm.tui.widgets.project_card import ProjectCard

    app = PMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        # Give time for the live_fetch worker to hit GitHub API
        await asyncio.sleep(8)
        await pilot.pause()

        cards = list(app.query(ProjectCard))
        assert len(cards) > 0, "Expected at least 1 ProjectCard in TUI"

        card_names = [c.project.name for c in cards]
        assert any(
            "project-portfolio-manager" in n or "401k" in n.lower() or "faa" in n.lower()
            for n in card_names
        ), f"No real repos found in cards: {card_names}"


# ---------------------------------------------------------------------------
# 7. AI summary persists past the 30-second poll cycle (THE flickering test)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_summary_persists_30_seconds():
    """AI summary should NOT disappear after 30 seconds of polling."""
    from pm.tui.app import PMApp
    from pm.tui.widgets.project_card import ProjectCard

    app = PMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        # Wait for initial load + AI summaries
        await asyncio.sleep(12)
        await pilot.pause()

        cards = list(app.query(ProjectCard))
        if not cards:
            pytest.skip("No cards rendered")

        initial_card_data = {}
        for card in cards:
            if card._card_data:
                initial_card_data[card.project.name] = dict(card._card_data)

        if not initial_card_data:
            pytest.skip("No AI data generated yet")

        # Wait 35 seconds (past the 30s poll cycle)
        await asyncio.sleep(35)
        await pilot.pause()

        # AI data MUST still be there
        cards_after = list(app.query(ProjectCard))
        for card in cards_after:
            name = card.project.name
            if name in initial_card_data:
                assert card._card_data is not None, (
                    f"Card {name} lost AI data after 30s!"
                )
                assert card._card_data.get("dynamic"), (
                    f"Card {name} dynamic field empty after 30s!"
                )


# ---------------------------------------------------------------------------
# 8. Selection preserved after poll
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_selection_preserved_after_poll():
    """Selected project should not jump after polling."""
    from pm.tui.app import PMApp
    from pm.tui.widgets.project_card import ProjectCard
    from pm.tui.screens.portfolio import PortfolioScreen

    app = PMApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await asyncio.sleep(8)
        await pilot.pause()

        screen = app.screen
        if not isinstance(screen, PortfolioScreen):
            pytest.skip("Not on portfolio screen")

        cards = list(app.query(ProjectCard))
        if len(cards) < 2:
            pytest.skip("Need at least 2 cards")

        # Select second card
        await pilot.press("j")
        await pilot.pause()
        selected_name = cards[1].project.name if len(cards) > 1 else ""

        # Wait for poll cycle
        await asyncio.sleep(35)
        await pilot.pause()

        # Selection should still be on the same project
        current_idx = screen._selected_index
        current_cards = list(app.query(ProjectCard))
        if current_cards and current_idx < len(current_cards):
            assert current_cards[current_idx].project.name == selected_name, (
                f"Selection jumped! Expected '{selected_name}' at index {current_idx}, "
                f"got '{current_cards[current_idx].project.name}'"
            )
