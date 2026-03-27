from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from pm.agent.session import SessionManager, SessionCreateOptions
from pm.config.models import PMConfig, ProjectConfig, AgentConfig, DefaultsConfig
from pm.db.database import Database
from pm.db.models import Session as DBSession
from pm.worktree.manager import WorktreeManager


@pytest.fixture
def tmp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


@pytest.fixture
def config():
    return PMConfig(
        projects={
            "test-project": ProjectConfig(
                account="personal",
                repos=["owner/repo"],
                local_path="/tmp/fake-repo",
                agent="claude-code",
                agent_config=AgentConfig(
                    model="claude-sonnet-4-6",
                    permissions="dangerously-skip",
                ),
            ),
        },
        defaults=DefaultsConfig(
            agent="claude-code",
            worktree_base="/tmp/worktrees",
        ),
    )


@pytest.fixture
def mock_worktree_mgr():
    mgr = MagicMock(spec=WorktreeManager)
    mgr.create_worktree.return_value = "/tmp/worktrees/test-project/pm_test-project_fix-auth"
    return mgr


@pytest.fixture
def session_mgr(config, tmp_db, mock_worktree_mgr):
    return SessionManager(config, tmp_db, mock_worktree_mgr)


@patch("pm.agent.session.subprocess.run")
def test_create_session(mock_run, session_mgr, tmp_db):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    opts = SessionCreateOptions(
        project="test-project",
        task_description="Fix auth bug",
        agent_name="claude-code",
    )
    session = session_mgr.create_session(opts)

    assert session.id.startswith("s-")
    assert session.project == "test-project"
    assert session.task_description == "Fix auth bug"
    assert session.agent == "claude-code"
    assert session.status == "running"
    assert session.tmux_session is not None
    assert session.branch is not None

    # Verify worktree was created
    session_mgr.worktree_mgr.create_worktree.assert_called_once()

    # Verify tmux session was created
    assert mock_run.call_count >= 2  # new-session + send-keys


@patch("pm.agent.session.subprocess.run")
def test_create_session_saves_to_db(mock_run, session_mgr, tmp_db):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    opts = SessionCreateOptions(
        project="test-project",
        task_description="Fix auth bug",
    )
    session = session_mgr.create_session(opts)

    # Verify saved in DB
    db_sessions = tmp_db.get_sessions_by_project("test-project")
    assert len(db_sessions) == 1
    assert db_sessions[0].id == session.id


@patch("pm.agent.session.subprocess.run")
def test_create_session_unknown_agent(mock_run, session_mgr):
    opts = SessionCreateOptions(
        project="test-project",
        task_description="Do stuff",
        agent_name="nonexistent-agent",
    )
    with pytest.raises(ValueError, match="Unknown agent"):
        session_mgr.create_session(opts)


@patch("pm.agent.session.subprocess.run")
def test_list_sessions_verifies_tmux(mock_run, session_mgr, tmp_db):
    # Pre-populate a running session
    tmp_db.upsert_session(DBSession(
        id="s-test1", project="test-project", agent="claude-code",
        tmux_session="pm_test_fix", status="running",
        created_at=datetime.now(),
    ))

    # tmux lists no sessions (session is dead)
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="no server running")

    sessions = session_mgr.list_sessions(project="test-project")
    assert len(sessions) == 1
    assert sessions[0].status == "exited"


@patch("pm.agent.session.subprocess.run")
def test_list_sessions_alive(mock_run, session_mgr, tmp_db):
    tmp_db.upsert_session(DBSession(
        id="s-test2", project="test-project", agent="claude-code",
        tmux_session="pm_test_fix", status="running",
        created_at=datetime.now(),
    ))

    mock_run.return_value = MagicMock(returncode=0, stdout="pm_test_fix\n", stderr="")

    sessions = session_mgr.list_sessions(project="test-project")
    assert len(sessions) == 1
    assert sessions[0].status == "running"


@patch("pm.agent.session.subprocess.run")
def test_kill_session(mock_run, session_mgr, tmp_db):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    tmp_db.upsert_session(DBSession(
        id="s-kill", project="test-project", agent="claude-code",
        tmux_session="pm_test_kill", worktree_path="/tmp/wt",
        status="running", created_at=datetime.now(),
    ))

    result = session_mgr.kill_session("s-kill")
    assert result is True

    # Verify tmux kill was called
    tmux_calls = [c for c in mock_run.call_args_list if "kill-session" in str(c)]
    assert len(tmux_calls) == 1


@patch("pm.agent.session.subprocess.run")
def test_kill_nonexistent_session(mock_run, session_mgr, tmp_db):
    result = session_mgr.kill_session("s-nonexistent")
    assert result is False


@patch("pm.agent.session.subprocess.run")
def test_pause_session(mock_run, session_mgr, tmp_db):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    tmp_db.upsert_session(DBSession(
        id="s-pause", project="test-project", agent="claude-code",
        tmux_session="pm_test_pause", status="running",
        created_at=datetime.now(),
    ))

    result = session_mgr.pause_session("s-pause")
    assert result is True

    # Verify Ctrl+C was sent
    send_calls = [c for c in mock_run.call_args_list if "send-keys" in str(c)]
    assert len(send_calls) >= 1


@patch("pm.agent.session.subprocess.run")
def test_resume_session(mock_run, session_mgr, tmp_db):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    tmp_db.upsert_session(DBSession(
        id="s-resume", project="test-project", agent="claude-code",
        tmux_session="pm_test_resume", task_description="Fix bug",
        status="paused", created_at=datetime.now(),
    ))

    result = session_mgr.resume_session("s-resume")
    assert result is True

    # Check DB status updated
    with tmp_db.get_session() as sess:
        db_session = sess.get(DBSession, "s-resume")
        assert db_session.status == "running"


@patch("pm.agent.session.subprocess.run")
def test_get_session_output(mock_run, session_mgr, tmp_db):
    mock_run.return_value = MagicMock(returncode=0, stdout="Hello from tmux\nLine 2\n", stderr="")

    tmp_db.upsert_session(DBSession(
        id="s-output", project="test-project", agent="claude-code",
        tmux_session="pm_test_output", status="running",
        created_at=datetime.now(),
    ))

    output = session_mgr.get_session_output("s-output")
    assert "Hello from tmux" in output


@patch("pm.agent.session.subprocess.run")
def test_send_to_session(mock_run, session_mgr, tmp_db):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    tmp_db.upsert_session(DBSession(
        id="s-send", project="test-project", agent="claude-code",
        tmux_session="pm_test_send", status="running",
        created_at=datetime.now(),
    ))

    result = session_mgr.send_to_session("s-send", "Fix the tests please")
    assert result is True

    # Verify send-keys was called with the text
    send_calls = [c for c in mock_run.call_args_list if "send-keys" in str(c)]
    assert len(send_calls) >= 1


def test_slugify():
    assert SessionManager._slugify("Fix auth bug") == "fix-auth-bug"
    assert SessionManager._slugify("Hello World!!!") == "hello-world"
    assert len(SessionManager._slugify("a" * 100)) <= 30


@patch("pm.agent.session.subprocess.run")
def test_session_uses_project_agent_config(mock_run, session_mgr, tmp_db):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    opts = SessionCreateOptions(
        project="test-project",
        task_description="Fix auth",
    )
    session = session_mgr.create_session(opts)

    # The tmux send-keys call should include --dangerously-skip-permissions
    # because the project config has permissions: dangerously-skip
    send_calls = [c for c in mock_run.call_args_list if "send-keys" in str(c)]
    assert len(send_calls) >= 1
    cmd_arg = str(send_calls[-1])
    assert "dangerously-skip-permissions" in cmd_arg
