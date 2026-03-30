from __future__ import annotations

from datetime import datetime

import pytest

from pm.tui.app import PMApp
from pm.tui.screens.task import TaskScreen
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


def make_session():
    return SessionInfo(
        id="s-001",
        project="Test Project",
        task="Fix auth bug",
        agent="claude-code",
        status="running",
        created_at=datetime(2026, 3, 25, 14, 30),
        branch="pm/fix-auth",
        pr_number=42,
    )


def make_project():
    return ProjectInfo(
        name="Test Project",
        account="Personal",
        repos=["owner/repo"],
        open_prs=2,
        active_sessions=1,
        status="green",
    )


@pytest.mark.asyncio
async def test_task_screen_renders():
    app = PMApp()
    screen = TaskScreen(session=make_session(), project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, TaskScreen)


@pytest.mark.asyncio
async def test_task_screen_has_title():
    app = PMApp()
    screen = TaskScreen(session=make_session(), project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        title = app.query_one("#task-title")
        assert title is not None


@pytest.mark.asyncio
async def test_task_screen_has_info_panel():
    app = PMApp()
    screen = TaskScreen(session=make_session(), project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        info_panel = app.query_one("#task-info-panel")
        assert info_panel is not None


@pytest.mark.asyncio
async def test_task_screen_has_terminal_panel():
    app = PMApp()
    screen = TaskScreen(session=make_session(), project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        terminal = app.query_one("#task-terminal-panel")
        assert terminal is not None


@pytest.mark.asyncio
async def test_task_screen_shows_terminal_output():
    app = PMApp()
    screen = TaskScreen(
        session=make_session(), project=make_project(),
        terminal_output="Hello from agent\nLine 2",
    )
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        output_widget = app.query_one("#terminal-output")
        assert output_widget is not None


@pytest.mark.asyncio
async def test_task_screen_update_terminal():
    app = PMApp()
    screen = TaskScreen(session=make_session(), project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        screen.update_terminal("New output from agent")
        await pilot.pause()
        assert screen._terminal_output == "New output from agent"


@pytest.mark.asyncio
async def test_task_screen_pause_toggle():
    app = PMApp()
    session = make_session()
    screen = TaskScreen(session=session, project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        assert screen._session.status == "running"
        await pilot.press("p")
        await pilot.pause()
        assert screen._session.status == "paused"

        await pilot.press("p")
        await pilot.pause()
        assert screen._session.status == "running"


@pytest.mark.asyncio
async def test_task_screen_kill():
    app = PMApp()
    screen = TaskScreen(session=make_session(), project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

        await pilot.press("k")
        await pilot.pause()
        assert screen._session.status == "killed"


@pytest.mark.asyncio
async def test_task_screen_escape_goes_back():
    app = PMApp()
    screen = TaskScreen(session=make_session(), project=make_project())
    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, TaskScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, TaskScreen)


@pytest.mark.asyncio
async def test_task_screen_session_property():
    session = make_session()
    screen = TaskScreen(session=session, project=make_project())
    assert screen.session.id == "s-001"
    assert screen.session.task == "Fix auth bug"
