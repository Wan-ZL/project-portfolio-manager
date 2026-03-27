from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import Optional

from github import Github, GithubException, RateLimitExceededException

from pm.config.models import PMConfig
from pm.db.database import Database
from pm.db.models import PullRequest, Repo
from pm.github.cache import GitHubCache
from pm.github.pr import EnhancedPR

logger = logging.getLogger(__name__)


class GitHubManager:
    """Multi-account GitHub management"""

    def __init__(self, config: PMConfig, db: Database):
        self.config = config
        self.db = db
        self.cache = GitHubCache(db)
        self.clients: dict[str, Github] = {}

        for name, account in config.accounts.items():
            token = os.environ.get(account.token_env, "")
            if not token:
                # Fallback: check credentials.yaml
                try:
                    from pm.auth.credentials import get_token
                    token = get_token(name) or ""
                except Exception:
                    pass
            if token:
                self.clients[name] = Github(token)
            else:
                logger.warning(f"No token found for account '{name}' (env: {account.token_env})")

    def client_for_account(self, account_name: str) -> Optional[Github]:
        return self.clients.get(account_name)

    def client_for_project(self, project_name: str) -> Optional[Github]:
        project = self.config.projects.get(project_name)
        if not project:
            return None
        return self.client_for_account(project.account)

    def sync_repos(self) -> None:
        for project_name, project in self.config.projects.items():
            for repo_name in project.repos:
                repo = Repo(
                    id=repo_name,
                    account=project.account,
                    project=project_name,
                    last_synced_at=datetime.now(),
                )
                client = self.client_for_account(project.account)
                if client:
                    try:
                        gh_repo = client.get_repo(repo_name)
                        repo.default_branch = gh_repo.default_branch
                    except (GithubException, Exception) as e:
                        logger.warning(f"Failed to fetch repo {repo_name}: {e}")
                self.cache.cache_repo(repo)

    def fetch_open_prs(self, project_name: str) -> list[EnhancedPR]:
        project = self.config.projects.get(project_name)
        if not project:
            return []

        client = self.client_for_account(project.account)
        if not client:
            return []

        prs = []
        for repo_name in project.repos:
            try:
                gh_repo = client.get_repo(repo_name)
                for gh_pr in gh_repo.get_pulls(state="open"):
                    enhanced = self._enhance_pr(gh_pr, repo_name)
                    prs.append(enhanced)
                    self._cache_pr(enhanced)
            except RateLimitExceededException:
                logger.warning(f"Rate limited while fetching PRs for {repo_name}")
                cached = self.cache.get_cached_prs(repo_name)
                for cached_pr in cached:
                    prs.append(self._pr_to_enhanced(cached_pr))
            except (GithubException, Exception) as e:
                logger.warning(f"Failed to fetch PRs for {repo_name}: {e}")
                cached = self.cache.get_cached_prs(repo_name)
                for cached_pr in cached:
                    prs.append(self._pr_to_enhanced(cached_pr))

        return prs

    def fetch_all_open_prs(self) -> list[EnhancedPR]:
        all_prs = []
        for project_name in self.config.projects:
            all_prs.extend(self.fetch_open_prs(project_name))
        return all_prs

    def _enhance_pr(self, gh_pr, repo_name: str) -> EnhancedPR:
        ci_status = "pending"
        review_status = "pending"

        try:
            commit = gh_pr.get_commits().reversed[0]
            statuses = commit.get_combined_status()
            if statuses.state == "success":
                ci_status = "passing"
            elif statuses.state == "failure":
                ci_status = "failing"
        except Exception:
            pass

        try:
            reviews = list(gh_pr.get_reviews())
            if any(r.state == "APPROVED" for r in reviews):
                review_status = "approved"
            elif any(r.state == "CHANGES_REQUESTED" for r in reviews):
                review_status = "changes_requested"
        except Exception:
            pass

        return EnhancedPR(
            repo_id=repo_name,
            number=gh_pr.number,
            title=gh_pr.title or "",
            state="open",
            author=gh_pr.user.login if gh_pr.user else "",
            created_at=gh_pr.created_at or datetime.now(),
            updated_at=gh_pr.updated_at or datetime.now(),
            ci_status=ci_status,
            review_status=review_status,
            url=gh_pr.html_url or "",
            body=gh_pr.body or "",
        )

    def _cache_pr(self, pr: EnhancedPR) -> None:
        db_pr = PullRequest(
            repo_id=pr.repo_id,
            number=pr.number,
            title=pr.title,
            state=pr.state,
            author=pr.author,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
            ci_status=pr.ci_status,
            review_status=pr.review_status,
            unresolved_comments=pr.unresolved_count,
            last_synced_at=datetime.now(),
            needs_attention=pr.needs_attention,
        )
        self.cache.cache_pr(db_pr)

    def _pr_to_enhanced(self, pr: PullRequest) -> EnhancedPR:
        return EnhancedPR(
            repo_id=pr.repo_id,
            number=pr.number,
            title=pr.title or "",
            state=pr.state or "open",
            author=pr.author or "",
            created_at=pr.created_at or datetime.now(),
            updated_at=pr.updated_at or datetime.now(),
            ci_status=pr.ci_status or "pending",
            review_status=pr.review_status or "pending",
            unresolved_count=pr.unresolved_comments,
            is_read=pr.is_read,
            is_starred=pr.is_starred,
            needs_attention=pr.needs_attention,
        )
