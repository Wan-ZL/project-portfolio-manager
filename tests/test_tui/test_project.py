from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from pm.github.pr import EnhancedPR
from pm.tui.app import PMApp
from pm.tui.screens.project import (
    ProjectScreen,
    PRListItem,
    SessionListItem,
    WelcomeBackSection,
    ActivityTimeline,
    SectionHeader,
    _build_welcome_back,
    _build_activity_timeline,
    _time_ago,
)
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


NOW = datetime(2026, 3, 26, 12, 0, 0)


def make_project():
    return ProjectInfo(
        name="Test Project",
        account="Personal",
        repos=["owner/frontend", "owner/backend"],
        open_prs=3,
        active_sessions=1,
        status="green",
        summary="Test project summary.",
        instructions="Focus on mobile responsive design.\nUse Tailwind CSS.",
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


# --- Helper function unit tests ---


class TestTimeAgo:
    def test_just_now(self):
        now = datetime(2026, 3, 26, 12, 0, 0)
        assert _time_ago(now - timedelta(seconds=30), now) == "just now"

    def test_minutes(self):
        now = datetime(2026, 3, 26, 12, 0, 0)
        assert _time_ago(now - timedelta(minutes=5), now) == "5min ago"

    def test_hours(self):
        now = datetime(2026, 3, 26, 12, 0, 0)
        assert _time_ago(now - timedelta(hours=3), now) == "3hr ago"

    def test_days(self):
        now = datetime(2026, 3, 26, 12, 0, 0)
        assert _time_ago(now - timedelta(days=2), now) == "2d ago"


class TestBuildWelcomeBack:
    def test_with_sessions_and_failing_pr(self):
        result = _build_welcome_back("Test", make_sessions(), make_prs(), NOW)
        assert "Fix auth bug" in result["last_action"]
        assert "Agent running" in result["last_action"]
        assert "review comment" in result["while_away"]
        assert "CI failing" in result["while_away"]
        assert "Fix CI" in result["suggestion"]

    def test_no_sessions(self):
        result = _build_welcome_back("Test", [], make_prs(), NOW)
        assert result["last_action"] == ""
        assert result["while_away"] != ""

    def test_no_prs(self):
        result = _build_welcome_back("Test", make_sessions(), [], NOW)
        assert result["while_away"] == "No new events"
        assert "All clear" in result["suggestion"]

    def test_empty(self):
        result = _build_welcome_back("Test", [], [], NOW)
        assert result["last_action"] == ""
        assert result["while_away"] == "No new events"
        assert "All clear" in result["suggestion"]

    def test_approved_pr_suggestion(self):
        prs = [
            EnhancedPR(
                repo_id="owner/repo", number=10, title="Ready PR",
                state="open", author="user", ci_status="passing",
                review_status="approved",
                created_at=datetime(2026, 3, 20), updated_at=datetime(2026, 3, 25),
            ),
        ]
        result = _build_welcome_back("Test", [], prs, NOW)
        assert "Merge PR #10" in result["suggestion"]
        assert "approved" in result["while_away"]


class TestBuildActivityTimeline:
    def test_timeline_from_sessions_and_prs(self):
        events = _build_activity_timeline(make_sessions(), make_prs(), NOW)
        assert len(events) > 0
        # Events should be sorted newest first
        for i in range(len(events) - 1):
            assert events[i]["time"] >= events[i + 1]["time"]

    def test_timeline_limit(self):
        events = _build_activity_timeline(make_sessions(), make_prs(), NOW, limit=2)
        assert len(events) <= 2

    def test_empty_timeline(self):
        events = _build_activity_timeline([], [], NOW)
        assert events == []

    def test_session_creates_agent_event(self):
        sessions = make_sessions()
        events = _build_activity_timeline(sessions, [], NOW)
        agent_events = [e for e in events if e["actor"] == "Agent"]
        assert len(agent_events) == 1
        assert "PR #42" in agent_events[0]["action"]

    def test_ci_failing_event(self):
        prs = [
            EnhancedPR(
                repo_id="owner/repo", number=42, title="Test",
                state="open", author="user", ci_status="failing",
                review_status="pending",
                created_at=datetime(2026, 3, 20), updated_at=datetime(2026, 3, 25),
            ),
        ]
        events = _build_activity_timeline([], prs, NOW)
        ci_events = [e for e in events if e["actor"] == "CI"]
        assert len(ci_events) == 1
        assert "failing" in ci_events[0]["action"]


# --- TUI screen tests ---


@pytest.mark.asyncio
async def test_project_screen_renders():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)


@pytest.mark.asyncio
async def test_project_screen_has_title():
    app = PMApp()
    screen = ProjectScreen(project=make_project(), prs=make_prs(), now=NOW)
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        title = app.query_one("#project-title")
        assert title is not None


@pytest.mark.asyncio
async def test_project_screen_has_welcome_back():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        welcome = app.query_one("#welcome-back", WelcomeBackSection)
        assert welcome is not None


@pytest.mark.asyncio
async def test_project_screen_has_activity_timeline():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        timeline = app.query_one("#activity-timeline", ActivityTimeline)
        assert timeline is not None


@pytest.mark.asyncio
async def test_project_screen_has_pr_items():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        pr_items = app.query(PRListItem)
        assert len(pr_items) == 3


@pytest.mark.asyncio
async def test_project_screen_has_session_items():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        session_items = app.query(SessionListItem)
        assert len(session_items) == 1


@pytest.mark.asyncio
async def test_project_screen_has_section_headers():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        headers = app.query(SectionHeader)
        # PR section, Sessions section, Activity section, Instructions section
        assert len(headers) >= 3


@pytest.mark.asyncio
async def test_project_screen_keyboard_navigation():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        # Navigate down through PR items
        await pilot.press("j")
        assert screen._selected_index == 1

        await pilot.press("j")
        assert screen._selected_index == 2

        # Navigate to session item (index 3)
        await pilot.press("j")
        assert screen._selected_index == 3


@pytest.mark.asyncio
async def test_project_screen_escape_goes_back():
    app = PMApp()
    screen = ProjectScreen(project=make_project(), now=NOW)
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, ProjectScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ProjectScreen)


@pytest.mark.asyncio
async def test_project_screen_enter_on_session_opens_task():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        # Navigate to session item (3 PRs + 1 session, session is at index 3)
        for _ in range(3):
            await pilot.press("j")
        await pilot.pause()
        assert screen._selected_index == 3

        await pilot.press("enter")
        await pilot.pause()

        from pm.tui.screens.task import TaskScreen
        assert isinstance(app.screen, TaskScreen)


@pytest.mark.asyncio
async def test_project_screen_dismiss_welcome():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        welcome = app.query_one("#welcome-back", WelcomeBackSection)
        assert "dismissed" not in welcome.classes

        await pilot.press("d")
        await pilot.pause()
        assert "dismissed" in welcome.classes


@pytest.mark.asyncio
async def test_project_screen_instructions_displayed():
    app = PMApp()
    project = make_project()
    screen = ProjectScreen(project=project, now=NOW)
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        instr = app.query_one("#instructions-section")
        assert instr is not None


@pytest.mark.asyncio
async def test_project_screen_no_instructions():
    app = PMApp()
    project = make_project()
    project.instructions = ""
    screen = ProjectScreen(project=project, now=NOW)
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        results = app.query("#instructions-section")
        assert len(results) == 0


@pytest.mark.asyncio
async def test_project_screen_no_sessions_shows_empty():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=[], now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        session_items = app.query(SessionListItem)
        assert len(session_items) == 0


@pytest.mark.asyncio
async def test_project_screen_scrollable():
    app = PMApp()
    screen = ProjectScreen(
        project=make_project(), prs=make_prs(), sessions=make_sessions(), now=NOW,
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        scroll = app.query_one("#project-scroll")
        assert scroll is not None
