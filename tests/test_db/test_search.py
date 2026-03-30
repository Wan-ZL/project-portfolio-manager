from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from pm.db.database import Database
from pm.db.models import Session as DBSession


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


def _make_session(id: str, project: str, task: str, agent: str = "claude-code",
                  branch: str = "") -> DBSession:
    return DBSession(
        id=id,
        project=project,
        task_description=task,
        agent=agent,
        branch=branch,
        status="running",
        created_at=datetime.now(),
    )


def test_fts_table_creation(db):
    from sqlalchemy import text
    with db.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='session_search'")
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "session_search"


def test_index_session(db):
    session = _make_session("s-001", "myproject", "Fix auth bug", branch="feature/auth")
    db.upsert_session(session)
    db.index_session(session)

    from sqlalchemy import text
    with db.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT session_id, project, task_description FROM session_search")
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "s-001"
    assert rows[0][1] == "myproject"
    assert rows[0][2] == "Fix auth bug"


def test_index_session_update(db):
    session = _make_session("s-001", "myproject", "Fix auth bug")
    db.upsert_session(session)
    db.index_session(session)

    session.task_description = "Fix auth bug v2"
    db.index_session(session)

    from sqlalchemy import text
    with db.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT task_description FROM session_search WHERE session_id = 's-001'")
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "Fix auth bug v2"


def test_search_by_keyword(db):
    s1 = _make_session("s-001", "proj-a", "Fix authentication bug")
    s2 = _make_session("s-002", "proj-a", "Add CI pipeline")
    s3 = _make_session("s-003", "proj-b", "Refactor database layer")
    for s in [s1, s2, s3]:
        db.upsert_session(s)
        db.index_session(s)

    results = db.search_sessions("authentication")
    assert len(results) == 1
    assert results[0].id == "s-001"


def test_search_multiple_results(db):
    s1 = _make_session("s-001", "proj-a", "Fix auth bug")
    s2 = _make_session("s-002", "proj-a", "Fix CI pipeline")
    s3 = _make_session("s-003", "proj-b", "Refactor database layer")
    for s in [s1, s2, s3]:
        db.upsert_session(s)
        db.index_session(s)

    results = db.search_sessions("Fix")
    assert len(results) == 2
    result_ids = {r.id for r in results}
    assert result_ids == {"s-001", "s-002"}


def test_search_with_project_filter(db):
    s1 = _make_session("s-001", "proj-a", "Fix auth bug")
    s2 = _make_session("s-002", "proj-b", "Fix CI pipeline")
    for s in [s1, s2]:
        db.upsert_session(s)
        db.index_session(s)

    results = db.search_sessions("Fix", project="proj-a")
    assert len(results) == 1
    assert results[0].id == "s-001"


def test_search_no_results(db):
    s1 = _make_session("s-001", "proj-a", "Fix auth bug")
    db.upsert_session(s1)
    db.index_session(s1)

    results = db.search_sessions("nonexistent")
    assert len(results) == 0


def test_search_empty_query(db):
    s1 = _make_session("s-001", "proj-a", "Fix auth bug")
    db.upsert_session(s1)
    db.index_session(s1)

    results = db.search_sessions("")
    assert len(results) == 0

    results = db.search_sessions("   ")
    assert len(results) == 0


def test_search_by_branch(db):
    s1 = _make_session("s-001", "proj-a", "Fix auth bug", branch="feature/auth-fix")
    s2 = _make_session("s-002", "proj-a", "Add tests", branch="feature/tests")
    for s in [s1, s2]:
        db.upsert_session(s)
        db.index_session(s)

    results = db.search_sessions("auth")
    assert len(results) == 1
    assert results[0].id == "s-001"


def test_search_by_agent(db):
    s1 = _make_session("s-001", "proj-a", "Fix stuff", agent="claude-code")
    s2 = _make_session("s-002", "proj-a", "Build feature", agent="codex")
    for s in [s1, s2]:
        db.upsert_session(s)
        db.index_session(s)

    results = db.search_sessions("codex")
    assert len(results) == 1
    assert results[0].id == "s-002"


def test_reindex_sessions(db):
    s1 = _make_session("s-001", "proj-a", "Fix auth bug")
    s2 = _make_session("s-002", "proj-b", "Add CI pipeline")
    for s in [s1, s2]:
        db.upsert_session(s)

    count = db.reindex_sessions()
    assert count == 2

    results = db.search_sessions("auth")
    assert len(results) == 1
    assert results[0].id == "s-001"

    results = db.search_sessions("CI")
    assert len(results) == 1
    assert results[0].id == "s-002"


def test_reindex_clears_stale_entries(db):
    s1 = _make_session("s-001", "proj-a", "Fix auth bug")
    db.upsert_session(s1)
    db.index_session(s1)

    results = db.search_sessions("auth")
    assert len(results) == 1

    db.reindex_sessions()

    results = db.search_sessions("auth")
    assert len(results) == 1


def test_search_special_characters(db):
    s1 = _make_session("s-001", "proj-a", "Fix bug in user's profile page")
    s2 = _make_session("s-002", "proj-a", "Update README.md & docs")
    for s in [s1, s2]:
        db.upsert_session(s)
        db.index_session(s)

    results = db.search_sessions("profile")
    assert len(results) == 1
    assert results[0].id == "s-001"

    results = db.search_sessions("docs")
    assert len(results) == 1
    assert results[0].id == "s-002"


def test_search_with_quotes_in_query(db):
    s1 = _make_session("s-001", "proj-a", "Fix the login flow")
    db.upsert_session(s1)
    db.index_session(s1)

    results = db.search_sessions('login')
    assert len(results) == 1


def test_search_multi_word_query(db):
    s1 = _make_session("s-001", "proj-a", "Fix auth bug in login flow")
    s2 = _make_session("s-002", "proj-a", "Fix CSS layout bug")
    s3 = _make_session("s-003", "proj-a", "Add auth middleware")
    for s in [s1, s2, s3]:
        db.upsert_session(s)
        db.index_session(s)

    results = db.search_sessions("auth bug")
    assert len(results) == 1
    assert results[0].id == "s-001"
