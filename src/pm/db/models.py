from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Repo(SQLModel, table=True):
    __tablename__ = "repos"

    id: str = Field(primary_key=True)  # owner/repo
    account: str
    project: str
    default_branch: Optional[str] = None
    last_synced_at: Optional[datetime] = None


class PullRequest(SQLModel, table=True):
    __tablename__ = "pull_requests"

    id: Optional[int] = Field(default=None, primary_key=True)
    repo_id: str
    number: int
    title: Optional[str] = None
    state: Optional[str] = None  # open, closed, merged
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ci_status: Optional[str] = None  # passing, failing, pending
    review_status: Optional[str] = None  # approved, changes_requested, pending
    unresolved_comments: int = 0
    last_synced_at: Optional[datetime] = None
    is_read: bool = False
    is_starred: bool = False
    needs_attention: bool = False


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(primary_key=True)
    project: str
    task_description: Optional[str] = None
    agent: str
    tmux_session: Optional[str] = None
    worktree_path: Optional[str] = None
    branch: Optional[str] = None
    pr_number: Optional[int] = None
    status: Optional[str] = None  # running, paused, completed, failed
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProjectSummary(SQLModel, table=True):
    __tablename__ = "project_summaries"

    project: str = Field(primary_key=True)
    summary: Optional[str] = None
    suggestions: Optional[str] = None  # JSON array
    generated_at: Optional[datetime] = None
    input_hash: Optional[str] = None


class ReactionTracker(SQLModel, table=True):
    __tablename__ = "reaction_tracker"

    id: str = Field(primary_key=True)  # session_id:reaction_key
    reaction_key: Optional[str] = None
    attempt_count: int = 0
    last_attempt_at: Optional[datetime] = None
    escalated: bool = False
