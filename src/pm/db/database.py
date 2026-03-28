from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel, select

from pm.db.models import PullRequest, Repo, ProjectSummary, Session as DBSession, ReactionTracker

DEFAULT_DB_PATH = Path.home() / ".ppm" / "ppm.db"

_FTS_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS session_search
USING fts5(session_id, project, task_description, agent, branch);
"""


class Database:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        SQLModel.metadata.create_all(self.engine)
        self._create_fts_table()

    def _create_fts_table(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(text(_FTS_CREATE))
            conn.commit()

    def get_session(self) -> Session:
        return Session(self.engine)

    # Repo CRUD
    def upsert_repo(self, repo: Repo) -> Repo:
        with self.get_session() as session:
            existing = session.get(Repo, repo.id)
            if existing:
                existing.account = repo.account
                existing.project = repo.project
                existing.default_branch = repo.default_branch
                existing.last_synced_at = repo.last_synced_at
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            session.add(repo)
            session.commit()
            session.refresh(repo)
            return repo

    def get_repo(self, repo_id: str) -> Optional[Repo]:
        with self.get_session() as session:
            return session.get(Repo, repo_id)

    def get_repos_by_project(self, project: str) -> list[Repo]:
        with self.get_session() as session:
            statement = select(Repo).where(Repo.project == project)
            return list(session.exec(statement).all())

    def get_all_repos(self) -> list[Repo]:
        with self.get_session() as session:
            return list(session.exec(select(Repo)).all())

    # PullRequest CRUD
    def upsert_pr(self, pr: PullRequest) -> PullRequest:
        with self.get_session() as session:
            if pr.id:
                existing = session.get(PullRequest, pr.id)
                if existing:
                    for field_name in ["repo_id", "number", "title", "state", "author",
                                       "created_at", "updated_at", "ci_status", "review_status",
                                       "unresolved_comments", "last_synced_at", "needs_attention"]:
                        val = getattr(pr, field_name)
                        if val is not None:
                            setattr(existing, field_name, val)
                    session.add(existing)
                    session.commit()
                    session.refresh(existing)
                    return existing
            session.add(pr)
            session.commit()
            session.refresh(pr)
            return pr

    def get_prs_by_repo(self, repo_id: str, state: str | None = None) -> list[PullRequest]:
        with self.get_session() as session:
            stmt = select(PullRequest).where(PullRequest.repo_id == repo_id)
            if state:
                stmt = stmt.where(PullRequest.state == state)
            return list(session.exec(stmt).all())

    def get_all_open_prs(self) -> list[PullRequest]:
        with self.get_session() as session:
            stmt = select(PullRequest).where(PullRequest.state == "open")
            return list(session.exec(stmt).all())

    # Session CRUD
    def upsert_session(self, db_session: DBSession) -> DBSession:
        with self.get_session() as session:
            existing = session.get(DBSession, db_session.id)
            if existing:
                for field_name in ["project", "task_description", "agent", "tmux_session",
                                   "worktree_path", "branch", "pr_number", "status", "updated_at"]:
                    val = getattr(db_session, field_name)
                    if val is not None:
                        setattr(existing, field_name, val)
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            session.add(db_session)
            session.commit()
            session.refresh(db_session)
            return db_session

    def get_sessions_by_project(self, project: str) -> list[DBSession]:
        with self.get_session() as session:
            stmt = select(DBSession).where(DBSession.project == project)
            return list(session.exec(stmt).all())

    def get_active_sessions(self) -> list[DBSession]:
        with self.get_session() as session:
            stmt = select(DBSession).where(DBSession.status == "running")
            return list(session.exec(stmt).all())

    def get_all_sessions(self) -> list[DBSession]:
        with self.get_session() as session:
            return list(session.exec(select(DBSession)).all())

    # ProjectSummary CRUD
    def get_summary(self, project: str) -> Optional[ProjectSummary]:
        with self.get_session() as session:
            return session.get(ProjectSummary, project)

    def save_summary(self, project: str, summary: str, suggestions: str, input_hash: str) -> ProjectSummary:
        with self.get_session() as session:
            existing = session.get(ProjectSummary, project)
            if existing:
                existing.summary = summary
                existing.suggestions = suggestions
                existing.generated_at = datetime.now()
                existing.input_hash = input_hash
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            ps = ProjectSummary(
                project=project,
                summary=summary,
                suggestions=suggestions,
                generated_at=datetime.now(),
                input_hash=input_hash,
            )
            session.add(ps)
            session.commit()
            session.refresh(ps)
            return ps

    # ReactionTracker CRUD
    def get_reaction_tracker(self, tracker_id: str) -> Optional[ReactionTracker]:
        with self.get_session() as session:
            return session.get(ReactionTracker, tracker_id)

    def upsert_reaction_tracker(self, tracker: ReactionTracker) -> ReactionTracker:
        with self.get_session() as session:
            existing = session.get(ReactionTracker, tracker.id)
            if existing:
                existing.attempt_count = tracker.attempt_count
                existing.last_attempt_at = tracker.last_attempt_at
                existing.escalated = tracker.escalated
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            session.add(tracker)
            session.commit()
            session.refresh(tracker)
            return tracker

    # FTS Session Search
    def index_session(self, db_session: DBSession) -> None:
        with self.engine.connect() as conn:
            conn.execute(
                text("DELETE FROM session_search WHERE session_id = :sid"),
                {"sid": db_session.id},
            )
            conn.execute(
                text(
                    "INSERT INTO session_search "
                    "(session_id, project, task_description, agent, branch) "
                    "VALUES (:sid, :project, :task, :agent, :branch)"
                ),
                {
                    "sid": db_session.id,
                    "project": db_session.project or "",
                    "task": db_session.task_description or "",
                    "agent": db_session.agent or "",
                    "branch": db_session.branch or "",
                },
            )
            conn.commit()

    def search_sessions(self, query: str, project: str | None = None) -> list[DBSession]:
        safe_query = query.replace('"', '""')
        terms = safe_query.split()
        fts_query = " ".join(f'"{t}"' for t in terms if t)
        if not fts_query:
            return []

        if project:
            sql = (
                "SELECT session_id FROM session_search "
                "WHERE session_search MATCH :q AND project = :project"
            )
            params = {"q": fts_query, "project": project}
        else:
            sql = "SELECT session_id FROM session_search WHERE session_search MATCH :q"
            params = {"q": fts_query}

        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()

        session_ids = [r[0] for r in rows]
        if not session_ids:
            return []

        with self.get_session() as session:
            stmt = select(DBSession).where(DBSession.id.in_(session_ids))  # type: ignore[union-attr]
            return list(session.exec(stmt).all())

    def reindex_sessions(self) -> int:
        with self.engine.connect() as conn:
            conn.execute(text("DELETE FROM session_search"))
            conn.commit()

        all_sessions = self.get_all_sessions()
        for s in all_sessions:
            self.index_session(s)
        return len(all_sessions)
