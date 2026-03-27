"""Smart polling for real-time GitHub data updates in the TUI.

Polling schedule:
- 5s:  One repo's PRs (round-robin)
- 30s: Full portfolio stats
- 60s: CI status + review comments (heavy)

Rate-limit aware: slows down when GitHub quota is low.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from pm.config.models import PMConfig
from pm.github.pr import EnhancedPR
from pm.tui.widgets.project_list import ProjectInfo


@dataclass
class PollingData:
    projects: list[ProjectInfo] = field(default_factory=list)
    prs: dict[str, list[EnhancedPR]] = field(default_factory=dict)
    ci_statuses: dict[str, str] = field(default_factory=dict)
    last_updated: datetime | None = None


@dataclass
class PollingUpdate:
    """What changed since last poll."""
    projects_changed: bool = False
    prs_changed: dict[str, bool] = field(default_factory=dict)
    new_prs: list[EnhancedPR] = field(default_factory=list)
    closed_prs: list[EnhancedPR] = field(default_factory=list)
    ci_changed: dict[str, str] = field(default_factory=dict)


def _parse_pr(repo_id: str, pr_data: dict) -> EnhancedPR:
    created = pr_data.get("created_at", "")
    updated = pr_data.get("updated_at", "")
    return EnhancedPR(
        repo_id=repo_id,
        number=pr_data.get("number", 0),
        title=pr_data.get("title", ""),
        state="open",
        author=pr_data.get("user", {}).get("login", ""),
        created_at=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else datetime.now(),
        updated_at=datetime.fromisoformat(updated.replace("Z", "+00:00")) if updated else datetime.now(),
        url=pr_data.get("html_url", ""),
    )


class SmartPoller:
    """Background smart polling for real-time GitHub data updates.

    Polling schedule:
    - 5s:  One repo's PRs (round-robin)
    - 30s: Full portfolio stats
    - 60s: CI status + review comments (heavy)

    Rate-limit aware: slows down when GitHub quota is low.
    """

    INTERVAL_PR = 5
    INTERVAL_FULL = 30
    INTERVAL_HEAVY = 60
    RATE_LIMIT_LOW = 500
    RATE_LIMIT_CRITICAL = 200

    def __init__(self, credentials: dict, config: PMConfig | None = None):
        self._credentials = credentials
        self._config = config
        self._repos: list[str] = []
        self._repo_index: int = 0
        self._rate_limit_remaining: int = 5000
        self._poll_count: int = 0
        self._last_full_refresh: float = 0
        self._last_heavy_refresh: float = 0
        self._data: PollingData = PollingData()
        self._project_repo_map: dict[str, list[str]] = {}
        self._project_account_map: dict[str, str] = {}

        self._init_repos()

    def _init_repos(self) -> None:
        """Build list of all repos to poll from config and credentials."""
        if self._config and self._config.projects:
            for proj_name, proj_cfg in self._config.projects.items():
                for repo in proj_cfg.repos:
                    if repo not in self._repos:
                        self._repos.append(repo)
                self._project_repo_map[proj_name] = list(proj_cfg.repos)
                self._project_account_map[proj_name] = proj_cfg.account

    def _get_token(self, account: str | None = None) -> str | None:
        accounts = self._credentials.get("accounts", {})
        if account and account in accounts:
            return accounts[account].get("token")
        for acc_data in accounts.values():
            token = acc_data.get("token")
            if token:
                return token
        return None

    def _get_headers(self, account: str | None = None) -> dict[str, str]:
        token = self._get_token(account)
        if not token:
            return {}
        return {
            "Authorization": f"token {token}",
            "Accept": "application/json",
        }

    def _update_rate_limit(self, resp: httpx.Response) -> None:
        remaining = resp.headers.get("x-ratelimit-remaining")
        if remaining is not None:
            try:
                self._rate_limit_remaining = int(remaining)
            except (ValueError, TypeError):
                pass

    @property
    def rate_limit_remaining(self) -> int:
        return self._rate_limit_remaining

    @property
    def is_rate_limited(self) -> bool:
        return self._rate_limit_remaining < self.RATE_LIMIT_LOW

    @property
    def is_rate_critical(self) -> bool:
        return self._rate_limit_remaining < self.RATE_LIMIT_CRITICAL

    @property
    def poll_count(self) -> int:
        return self._poll_count

    @property
    def data(self) -> PollingData:
        return self._data

    @property
    def repos(self) -> list[str]:
        return list(self._repos)

    def set_repos(self, repos: list[str]) -> None:
        self._repos = list(repos)
        if self._repo_index >= len(self._repos):
            self._repo_index = 0

    async def tick(self) -> PollingUpdate | None:
        """Called every 5 seconds by the TUI timer.
        Returns PollingUpdate if data changed, None otherwise.
        """
        self._poll_count += 1

        if self._rate_limit_remaining < self.RATE_LIMIT_CRITICAL:
            return None

        now = time.time()

        if now - self._last_heavy_refresh >= self.INTERVAL_HEAVY:
            return await self._heavy_refresh()

        if self._rate_limit_remaining < self.RATE_LIMIT_LOW:
            return None

        if now - self._last_full_refresh >= self.INTERVAL_FULL:
            return await self._full_refresh()

        return await self._poll_one_repo()

    async def force_refresh(self) -> PollingUpdate:
        """Force immediate full refresh (user pressed 'r')."""
        self._last_full_refresh = time.time()
        self._last_heavy_refresh = time.time()
        return await self._do_full_refresh(include_heavy=True)

    async def _poll_one_repo(self) -> PollingUpdate | None:
        """Poll one repo's PRs using round-robin."""
        if not self._repos:
            return None

        repo = self._repos[self._repo_index]
        self._repo_index = (self._repo_index + 1) % len(self._repos)

        account = self._find_account_for_repo(repo)
        headers = self._get_headers(account)
        if not headers:
            return None

        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=headers,
                params={"state": "open", "per_page": 100},
                timeout=15,
            )
            self._update_rate_limit(resp)
            if resp.status_code != 200:
                return None

            new_prs = [_parse_pr(repo, pr_data) for pr_data in resp.json()]
        except Exception:
            return None

        update = PollingUpdate()
        project_name = self._find_project_for_repo(repo)
        if project_name:
            old_prs = self._data.prs.get(project_name, [])
            old_repo_prs = [p for p in old_prs if p.repo_id == repo]
            old_numbers = {p.number for p in old_repo_prs}
            new_numbers = {p.number for p in new_prs}

            detected_new = [p for p in new_prs if p.number not in old_numbers]
            detected_closed = [p for p in old_repo_prs if p.number not in new_numbers]

            if detected_new or detected_closed or len(old_repo_prs) != len(new_prs):
                update.prs_changed[project_name] = True
                update.new_prs.extend(detected_new)
                update.closed_prs.extend(detected_closed)

                other_prs = [p for p in old_prs if p.repo_id != repo]
                self._data.prs[project_name] = other_prs + new_prs
                self._data.last_updated = datetime.now()

                self._update_project_stats(project_name)
                update.projects_changed = True

        if not update.prs_changed and not update.projects_changed:
            return None
        return update

    async def _full_refresh(self) -> PollingUpdate:
        """Full portfolio stats refresh (every 30s)."""
        self._last_full_refresh = time.time()
        return await self._do_full_refresh(include_heavy=False)

    async def _heavy_refresh(self) -> PollingUpdate:
        """Heavy refresh including CI and reviews (every 60s)."""
        self._last_full_refresh = time.time()
        self._last_heavy_refresh = time.time()
        return await self._do_full_refresh(include_heavy=True)

    async def _do_full_refresh(self, include_heavy: bool = False) -> PollingUpdate:
        """Execute a full refresh of all repos."""
        update = PollingUpdate()

        for project_name, repos in self._project_repo_map.items():
            account = self._project_account_map.get(project_name)
            headers = self._get_headers(account)
            if not headers:
                continue

            all_proj_prs: list[EnhancedPR] = []
            for repo in repos:
                try:
                    resp = httpx.get(
                        f"https://api.github.com/repos/{repo}/pulls",
                        headers=headers,
                        params={"state": "open", "per_page": 100},
                        timeout=15,
                    )
                    self._update_rate_limit(resp)
                    if resp.status_code == 200:
                        for pr_data in resp.json():
                            pr = _parse_pr(repo, pr_data)
                            if include_heavy:
                                pr = await self._enrich_pr(repo, pr, headers)
                            all_proj_prs.append(pr)
                except Exception:
                    pass

            old_prs = self._data.prs.get(project_name, [])
            old_numbers = {p.number for p in old_prs}
            new_numbers = {p.number for p in all_proj_prs}

            detected_new = [p for p in all_proj_prs if p.number not in old_numbers]
            detected_closed = [p for p in old_prs if p.number not in new_numbers]

            if detected_new or detected_closed or len(old_prs) != len(all_proj_prs):
                update.prs_changed[project_name] = True
                update.new_prs.extend(detected_new)
                update.closed_prs.extend(detected_closed)

            self._data.prs[project_name] = all_proj_prs
            self._update_project_stats(project_name)

        self._data.last_updated = datetime.now()
        update.projects_changed = True
        return update

    async def _enrich_pr(self, repo: str, pr: EnhancedPR, headers: dict) -> EnhancedPR:
        """Add CI status and review status to a PR (heavy operation)."""
        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{repo}/commits/{pr.number}/status",
                headers=headers,
                timeout=10,
            )
            self._update_rate_limit(resp)
            if resp.status_code == 200:
                state = resp.json().get("state", "pending")
                if state == "success":
                    pr.ci_status = "passing"
                elif state == "failure" or state == "error":
                    pr.ci_status = "failing"
                else:
                    pr.ci_status = "pending"
        except Exception:
            pass

        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{repo}/pulls/{pr.number}/reviews",
                headers=headers,
                timeout=10,
            )
            self._update_rate_limit(resp)
            if resp.status_code == 200:
                reviews = resp.json()
                if reviews:
                    latest = reviews[-1]
                    state = latest.get("state", "").lower()
                    if state == "approved":
                        pr.review_status = "approved"
                    elif state == "changes_requested":
                        pr.review_status = "changes_requested"
                        pr.needs_attention = True
        except Exception:
            pass

        return pr

    def _find_account_for_repo(self, repo: str) -> str | None:
        for proj_name, repos in self._project_repo_map.items():
            if repo in repos:
                return self._project_account_map.get(proj_name)
        return None

    def _find_project_for_repo(self, repo: str) -> str | None:
        for proj_name, repos in self._project_repo_map.items():
            if repo in repos:
                return proj_name
        return None

    def _update_project_stats(self, project_name: str) -> None:
        """Update a project's stats in the projects list."""
        prs = self._data.prs.get(project_name, [])
        pr_count = len(prs)
        has_failing = any(p.ci_status == "failing" for p in prs)

        status = "green"
        if pr_count == 0:
            status = "gray"
        elif has_failing:
            status = "red"
        elif pr_count > 5:
            status = "yellow"

        for i, proj in enumerate(self._data.projects):
            if proj.name == project_name:
                self._data.projects[i] = ProjectInfo(
                    name=proj.name,
                    account=proj.account,
                    repos=proj.repos,
                    open_prs=pr_count,
                    active_sessions=proj.active_sessions,
                    status=status,
                    summary=f"{pr_count} open PRs" if pr_count else "No open PRs",
                    instructions=proj.instructions,
                    assets=proj.assets,
                )
                break

    def get_status_text(self) -> str:
        """Get human-readable polling status for the status bar."""
        if self.is_rate_critical:
            return "Live [yellow]Rate limited[/yellow]"
        if self.is_rate_limited:
            return "Live [yellow]Throttled[/yellow]"
        if self._data.last_updated:
            elapsed = int(time.time() - self._data.last_updated.timestamp())
            return f"Live [green]Updated {elapsed}s ago[/green]"
        return "Live"
