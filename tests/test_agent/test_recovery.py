from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm.agent.session import SessionManager
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
    return mgr


@pytest.fixture
def session_mgr(config, tmp_db, mock_worktree_mgr):
    return SessionManager(config, tmp_db, mock_worktree_mgr)


@patch("pm.agent.session.subprocess.run")
def test_recover_tmux_exists_db_running_no_recovery(mock_run, session_mgr, tmp_db):
    """tmux exists and DB says running -> normal, no recovery needed."""
    tmp_db.upsert_session(DBSession(
        id="s-run1", project="test-project", agent="claude-code",
        tmux_session="pm_test_running", status="running",
        created_at=datetime.now(), updated_at=datetime.now(),
    ))

    # tmux lists the session as alive
    mock_run.return_value = MagicMock(
        returncode=0, stdout="pm_test_running\n", stderr=""
    )

    results = session_mgr.recover_sessions()
    assert len(results) == 0

    # Status should still be running
    with tmp_db.get_session() as sess:
        db_s = sess.get(DBSession, "s-run1")
        assert db_s.status == "running"


@patch("pm.agent.session.subprocess.run")
def test_recover_tmux_exists_db_completed_mark_recovered(mock_run, session_mgr, tmp_db):
    """tmux exists but DB says completed -> mark as recovered."""
    tmp_db.upsert_session(DBSession(
        id="s-comp1", project="test-project", agent="claude-code",
        tmux_session="pm_test_completed", status="completed",
        created_at=datetime.now(), updated_at=datetime.now(),
    ))

    mock_run.return_value = MagicMock(
        returncode=0, stdout="pm_test_completed\n", stderr=""
    )

    results = session_mgr.recover_sessions()
    assert len(results) == 1
    assert results[0]["session_id"] == "s-comp1"
    assert results[0]["tmux_name"] == "pm_test_completed"
    assert results[0]["status"] == "recovered"

    with tmp_db.get_session() as sess:
        db_s = sess.get(DBSession, "s-comp1")
        assert db_s.status == "recovered"


@patch("pm.agent.session.subprocess.run")
def test_recover_tmux_exists_db_failed_mark_recovered(mock_run, session_mgr, tmp_db):
    """tmux exists but DB says failed -> mark as recovered."""
    tmp_db.upsert_session(DBSession(
        id="s-fail1", project="test-project", agent="claude-code",
        tmux_session="pm_test_failed", status="failed",
        created_at=datetime.now(), updated_at=datetime.now(),
    ))

    mock_run.return_value = MagicMock(
        returncode=0, stdout="pm_test_failed\n", stderr=""
    )

    results = session_mgr.recover_sessions()
    assert len(results) == 1
    assert results[0]["status"] == "recovered"

    with tmp_db.get_session() as sess:
        db_s = sess.get(DBSession, "s-fail1")
        assert db_s.status == "recovered"


@patch("pm.agent.session.subprocess.run")
def test_recover_tmux_gone_db_running_mark_lost(mock_run, session_mgr, tmp_db):
    """tmux gone but DB says running -> mark as lost."""
    tmp_db.upsert_session(DBSession(
        id="s-lost1", project="test-project", agent="claude-code",
        tmux_session="pm_test_lost", status="running",
        created_at=datetime.now(), updated_at=datetime.now(),
    ))

    # No tmux sessions running
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="no server running"
    )

    results = session_mgr.recover_sessions()
    assert len(results) == 1
    assert results[0]["session_id"] == "s-lost1"
    assert results[0]["status"] == "lost"

    with tmp_db.get_session() as sess:
        db_s = sess.get(DBSession, "s-lost1")
        assert db_s.status == "lost"


@patch("pm.agent.session.subprocess.run")
def test_recover_no_tmux_sessions(mock_run, session_mgr, tmp_db):
    """No tmux sessions at all -> no recovery."""
    mock_run.return_value = MagicMock(
        returncode=1, stdout="", stderr="no server running"
    )

    results = session_mgr.recover_sessions()
    assert len(results) == 0


@patch("pm.agent.session.subprocess.run")
def test_recover_multiple_mixed_states(mock_run, session_mgr, tmp_db):
    """Multiple sessions in different states."""
    # Session 1: running + tmux alive -> no recovery
    tmp_db.upsert_session(DBSession(
        id="s-mix1", project="test-project", agent="claude-code",
        tmux_session="pm_test_alive", status="running",
        created_at=datetime.now(), updated_at=datetime.now(),
    ))
    # Session 2: completed + tmux alive -> recovered
    tmp_db.upsert_session(DBSession(
        id="s-mix2", project="test-project", agent="claude-code",
        tmux_session="pm_test_orphan", status="completed",
        created_at=datetime.now(), updated_at=datetime.now(),
    ))
    # Session 3: running + tmux dead -> lost
    tmp_db.upsert_session(DBSession(
        id="s-mix3", project="test-project", agent="claude-code",
        tmux_session="pm_test_dead", status="running",
        created_at=datetime.now(), updated_at=datetime.now(),
    ))
    # Session 4: completed + tmux dead -> no action needed
    tmp_db.upsert_session(DBSession(
        id="s-mix4", project="test-project", agent="claude-code",
        tmux_session="pm_test_done", status="completed",
        created_at=datetime.now(), updated_at=datetime.now(),
    ))

    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="pm_test_alive\npm_test_orphan\nother_session\n",
        stderr="",
    )

    results = session_mgr.recover_sessions()

    statuses = {r["session_id"]: r["status"] for r in results if r["session_id"]}
    assert statuses.get("s-mix2") == "recovered"
    assert statuses.get("s-mix3") == "lost"
    assert "s-mix1" not in statuses  # no recovery needed
    assert "s-mix4" not in statuses  # completed + no tmux = fine


@patch("pm.agent.session.subprocess.run")
def test_recover_orphan_tmux_no_db_record(mock_run, session_mgr, tmp_db):
    """tmux pm_* session exists but has no DB record at all."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="pm_unknown_session\n",
        stderr="",
    )

    results = session_mgr.recover_sessions()
    assert len(results) == 1
    assert results[0]["session_id"] == ""
    assert results[0]["tmux_name"] == "pm_unknown_session"
    assert results[0]["status"] == "recovered"


@patch("pm.agent.session.subprocess.run")
def test_recover_ignores_non_pm_tmux_sessions(mock_run, session_mgr, tmp_db):
    """Non-pm_* tmux sessions are ignored."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="my_dev_session\nwork_session\n",
        stderr="",
    )

    results = session_mgr.recover_sessions()
    assert len(results) == 0
