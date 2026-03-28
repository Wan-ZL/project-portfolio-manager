from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from pm.db.database import Database
from pm.db.models import PullRequest, Repo, ProjectSummary, Session as DBSession, ReactionTracker


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


def test_database_creation(db):
    assert db.db_path.exists()


def test_repo_crud(db):
    repo = Repo(
        id="owner/repo",
        account="personal",
        project="test-project",
        default_branch="main",
        last_synced_at=datetime.now(),
    )
    saved = db.upsert_repo(repo)
    assert saved.id == "owner/repo"

    fetched = db.get_repo("owner/repo")
    assert fetched is not None
    assert fetched.account == "personal"
    assert fetched.project == "test-project"


def test_repo_update(db):
    repo = Repo(id="owner/repo", account="personal", project="proj1")
    db.upsert_repo(repo)

    updated = Repo(id="owner/repo", account="personal", project="proj2", default_branch="develop")
    db.upsert_repo(updated)

    fetched = db.get_repo("owner/repo")
    assert fetched.project == "proj2"
    assert fetched.default_branch == "develop"


def test_get_repos_by_project(db):
    db.upsert_repo(Repo(id="owner/repo1", account="a", project="proj"))
    db.upsert_repo(Repo(id="owner/repo2", account="a", project="proj"))
    db.upsert_repo(Repo(id="owner/repo3", account="a", project="other"))

    repos = db.get_repos_by_project("proj")
    assert len(repos) == 2


def test_get_all_repos(db):
    db.upsert_repo(Repo(id="owner/repo1", account="a", project="proj1"))
    db.upsert_repo(Repo(id="owner/repo2", account="b", project="proj2"))

    repos = db.get_all_repos()
    assert len(repos) == 2


def test_pr_crud(db):
    pr = PullRequest(
        repo_id="owner/repo",
        number=42,
        title="Fix bug",
        state="open",
        author="user",
        ci_status="passing",
        review_status="pending",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    saved = db.upsert_pr(pr)
    assert saved.id is not None
    assert saved.number == 42


def test_get_prs_by_repo(db):
    db.upsert_pr(PullRequest(repo_id="owner/repo", number=1, title="PR1", state="open"))
    db.upsert_pr(PullRequest(repo_id="owner/repo", number=2, title="PR2", state="open"))
    db.upsert_pr(PullRequest(repo_id="owner/repo", number=3, title="PR3", state="closed"))
    db.upsert_pr(PullRequest(repo_id="other/repo", number=4, title="PR4", state="open"))

    open_prs = db.get_prs_by_repo("owner/repo", state="open")
    assert len(open_prs) == 2

    all_prs = db.get_prs_by_repo("owner/repo")
    assert len(all_prs) == 3


def test_get_all_open_prs(db):
    db.upsert_pr(PullRequest(repo_id="r1", number=1, state="open"))
    db.upsert_pr(PullRequest(repo_id="r2", number=2, state="open"))
    db.upsert_pr(PullRequest(repo_id="r3", number=3, state="closed"))

    open_prs = db.get_all_open_prs()
    assert len(open_prs) == 2


def test_session_crud(db):
    session = DBSession(
        id="s-001",
        project="test-proj",
        task_description="Fix auth",
        agent="claude-code",
        status="running",
        created_at=datetime.now(),
    )
    saved = db.upsert_session(session)
    assert saved.id == "s-001"

    sessions = db.get_sessions_by_project("test-proj")
    assert len(sessions) == 1
    assert sessions[0].task_description == "Fix auth"


def test_session_update(db):
    db.upsert_session(DBSession(
        id="s-001", project="proj", agent="claude-code",
        status="running", created_at=datetime.now(),
    ))
    db.upsert_session(DBSession(
        id="s-001", project="proj", agent="claude-code",
        status="completed", updated_at=datetime.now(),
    ))

    sessions = db.get_sessions_by_project("proj")
    assert len(sessions) == 1
    assert sessions[0].status == "completed"


def test_get_active_sessions(db):
    db.upsert_session(DBSession(id="s-001", project="p", agent="a", status="running"))
    db.upsert_session(DBSession(id="s-002", project="p", agent="a", status="paused"))
    db.upsert_session(DBSession(id="s-003", project="p", agent="a", status="running"))

    active = db.get_active_sessions()
    assert len(active) == 2


def test_project_summary_crud(db):
    saved = db.save_summary("proj", "All good", '["fix bug"]', "abc123")
    assert saved.project == "proj"
    assert saved.summary == "All good"

    fetched = db.get_summary("proj")
    assert fetched is not None
    assert fetched.input_hash == "abc123"


def test_project_summary_update(db):
    db.save_summary("proj", "Summary v1", "[]", "hash1")
    db.save_summary("proj", "Summary v2", '["suggestion"]', "hash2")

    fetched = db.get_summary("proj")
    assert fetched.summary == "Summary v2"
    assert fetched.input_hash == "hash2"


def test_reaction_tracker_crud(db):
    tracker = ReactionTracker(
        id="s-001:ci-failed",
        reaction_key="ci-failed",
        attempt_count=1,
        last_attempt_at=datetime.now(),
    )
    saved = db.upsert_reaction_tracker(tracker)
    assert saved.id == "s-001:ci-failed"

    fetched = db.get_reaction_tracker("s-001:ci-failed")
    assert fetched is not None
    assert fetched.attempt_count == 1


def test_reaction_tracker_update(db):
    db.upsert_reaction_tracker(ReactionTracker(
        id="s-001:ci-failed", reaction_key="ci-failed", attempt_count=1,
    ))
    db.upsert_reaction_tracker(ReactionTracker(
        id="s-001:ci-failed", reaction_key="ci-failed", attempt_count=2, escalated=True,
    ))

    fetched = db.get_reaction_tracker("s-001:ci-failed")
    assert fetched.attempt_count == 2
    assert fetched.escalated is True
