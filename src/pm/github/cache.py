from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from pm.db.database import Database
from pm.db.models import PullRequest, Repo


class GitHubCache:
    """SQLite caching layer for GitHub data"""

    def __init__(self, db: Database, cache_ttl_seconds: int = 300):
        self.db = db
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)

    def is_stale(self, last_synced: Optional[datetime]) -> bool:
        if last_synced is None:
            return True
        return datetime.now() - last_synced > self.cache_ttl

    def get_cached_prs(self, repo_id: str) -> list[PullRequest]:
        return self.db.get_prs_by_repo(repo_id, state="open")

    def cache_pr(self, pr: PullRequest) -> PullRequest:
        pr.last_synced_at = datetime.now()
        return self.db.upsert_pr(pr)

    def get_cached_repo(self, repo_id: str) -> Optional[Repo]:
        return self.db.get_repo(repo_id)

    def cache_repo(self, repo: Repo) -> Repo:
        repo.last_synced_at = datetime.now()
        return self.db.upsert_repo(repo)

    def needs_refresh(self, repo_id: str) -> bool:
        repo = self.get_cached_repo(repo_id)
        if repo is None:
            return True
        return self.is_stale(repo.last_synced_at)
