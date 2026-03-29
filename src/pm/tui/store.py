"""Centralized data store for the TUI.

Single source of truth for all project data. All updates mutate the store;
UI reads from the store. AI card summaries survive card rebuilds because
set_projects() preserves them for projects that exist in both old and new lists.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from pm.github.pr import EnhancedPR
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo

logger = logging.getLogger(__name__)


@dataclass
class ProjectData:
    info: ProjectInfo
    prs: list[EnhancedPR] = field(default_factory=list)
    sessions: list[SessionInfo] = field(default_factory=list)
    card_summary: dict | None = None
    card_summary_status: str = ""
    card_summary_time: str = ""
    ai_summary: dict | None = None


@dataclass
class StoreState:
    projects: dict[str, ProjectData] = field(default_factory=dict)
    project_order: list[str] = field(default_factory=list)
    selected_project: str = ""
    is_loading: bool = False
    error_message: str = ""


def _has_credentials() -> bool:
    try:
        from pm.auth.credentials import load_credentials
        creds = load_credentials()
        return bool(creds.get("accounts", {}))
    except Exception:
        return False


def _has_selected_repos_or_config() -> bool:
    try:
        from pm.config.loader import load_config, has_real_projects
        cfg = load_config()
        if has_real_projects(cfg):
            return True
    except Exception:
        pass
    try:
        from pm.auth.credentials import load_credentials
        creds = load_credentials()
        for acct_data in creds.get("accounts", {}).values():
            if acct_data.get("selected_repos"):
                return True
    except Exception:
        pass
    return False


def _get_credential_token(account: str = "personal") -> str | None:
    try:
        from pm.auth.credentials import get_token
        return get_token(account)
    except Exception:
        return None


def _get_selected_repos_for_account(account_name: str) -> list[str]:
    try:
        from pm.auth.credentials import get_selected_repos
        return get_selected_repos(account_name)
    except Exception:
        return []


def _fetch_prs_for_repos(
    repo_names: list[str], headers: dict
) -> list[EnhancedPR]:
    import httpx
    prs: list[EnhancedPR] = []
    for repo_name in repo_names:
        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{repo_name}/pulls",
                headers=headers,
                params={"state": "open", "per_page": 100},
                timeout=15,
            )
            if resp.status_code == 200:
                for pr_data in resp.json():
                    prs.append(EnhancedPR(
                        repo_id=repo_name,
                        number=pr_data.get("number", 0),
                        title=pr_data.get("title", ""),
                        state="open",
                        author=pr_data.get("user", {}).get("login", ""),
                        created_at=datetime.fromisoformat(
                            pr_data["created_at"].replace("Z", "+00:00")
                        ) if pr_data.get("created_at") else datetime.now(),
                        updated_at=datetime.fromisoformat(
                            pr_data["updated_at"].replace("Z", "+00:00")
                        ) if pr_data.get("updated_at") else datetime.now(),
                        url=pr_data.get("html_url", ""),
                    ))
        except Exception:
            pass
    return prs


def _fetch_live_projects_and_prs() -> tuple[list[ProjectInfo], dict[str, list[EnhancedPR]]]:
    from pm.auth.credentials import load_credentials

    creds = load_credentials()
    accounts = creds.get("accounts", {})
    if not accounts:
        return [], {}

    from pm.config.loader import load_config, has_real_projects
    cfg = load_config()

    projects: list[ProjectInfo] = []
    all_prs: dict[str, list[EnhancedPR]] = {}

    if has_real_projects(cfg):
        for account_name in accounts:
            token = accounts[account_name].get("token", "")
            if not token:
                continue

            selected = _get_selected_repos_for_account(account_name)
            import httpx
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/json",
            }

            for proj_name, proj_cfg in cfg.projects.items():
                if proj_cfg.account != account_name:
                    continue
                if selected:
                    repos_to_fetch = [r for r in proj_cfg.repos if r in selected]
                else:
                    repos_to_fetch = list(proj_cfg.repos)

                if not repos_to_fetch:
                    continue

                proj_prs = _fetch_prs_for_repos(repos_to_fetch, headers)
                pr_count = len(proj_prs)

                status = "green"
                if pr_count == 0:
                    status = "gray"
                elif pr_count > 5:
                    status = "yellow"

                all_prs[proj_name] = proj_prs
                projects.append(ProjectInfo(
                    name=proj_name,
                    account=proj_cfg.account,
                    repos=repos_to_fetch,
                    open_prs=pr_count,
                    active_sessions=0,
                    status=status,
                    summary=f"{pr_count} open PRs" if pr_count else "No open PRs",
                    instructions=proj_cfg.instructions,
                    assets=list(proj_cfg.assets),
                ))
    else:
        from pm.auth.credentials import load_project_groups
        project_groups = load_project_groups()

        if project_groups:
            for group_name, group_repos in project_groups.items():
                if not group_repos:
                    continue
                group_prs: list[EnhancedPR] = []
                for account_name, account_data in accounts.items():
                    token = account_data.get("token", "")
                    if not token:
                        continue
                    selected = _get_selected_repos_for_account(account_name)
                    repos_in_group = [r for r in group_repos if r in selected]
                    if not repos_in_group:
                        continue
                    import httpx
                    headers = {
                        "Authorization": f"token {token}",
                        "Accept": "application/json",
                    }
                    group_prs.extend(_fetch_prs_for_repos(repos_in_group, headers))

                pr_count = len(group_prs)
                status = "green"
                if pr_count == 0:
                    status = "gray"
                elif pr_count > 5:
                    status = "yellow"

                all_prs[group_name] = group_prs
                group_account = ""
                for account_name, account_data in accounts.items():
                    selected = _get_selected_repos_for_account(account_name)
                    if any(r in selected for r in group_repos):
                        group_account = account_name
                        break

                projects.append(ProjectInfo(
                    name=group_name,
                    account=group_account,
                    repos=group_repos,
                    open_prs=pr_count,
                    active_sessions=0,
                    status=status,
                    summary=f"{pr_count} open PRs across {len(group_repos)} repos",
                ))
        else:
            for account_name, account_data in accounts.items():
                token = account_data.get("token", "")
                if not token:
                    continue

                selected = _get_selected_repos_for_account(account_name)
                if not selected:
                    continue

                import httpx
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/json",
                }

                for repo_full_name in selected:
                    repo_name = repo_full_name.split("/")[1] if "/" in repo_full_name else repo_full_name
                    proj_prs = _fetch_prs_for_repos([repo_full_name], headers)
                    pr_count = len(proj_prs)

                    status = "green"
                    if pr_count == 0:
                        status = "gray"
                    elif pr_count > 5:
                        status = "yellow"

                    all_prs[repo_name] = proj_prs
                    projects.append(ProjectInfo(
                        name=repo_name,
                        account=account_name,
                        repos=[repo_full_name],
                        open_prs=pr_count,
                        active_sessions=0,
                        status=status,
                        summary=f"{pr_count} open PRs",
                    ))

    return projects, all_prs


def _build_loading_placeholders() -> list[ProjectInfo]:
    try:
        from pm.config.loader import load_config, has_real_projects
        cfg = load_config()
        if has_real_projects(cfg) and cfg.projects:
            projects = []
            for name, project in cfg.projects.items():
                projects.append(ProjectInfo(
                    name=name,
                    account=project.account,
                    repos=list(project.repos),
                    open_prs=0,
                    active_sessions=0,
                    status="gray",
                    summary="Loading...",
                    instructions=project.instructions,
                    assets=list(project.assets),
                ))
            if projects:
                return projects
    except Exception:
        pass
    try:
        from pm.auth.credentials import load_credentials
        creds = load_credentials()
        placeholders = []
        for account_id, data in creds.get("accounts", {}).items():
            for repo in data.get("selected_repos", []):
                repo_name = repo.split("/")[-1] if "/" in repo else repo
                placeholders.append(ProjectInfo(
                    name=repo_name,
                    account=account_id,
                    repos=[repo],
                    open_prs=0,
                    active_sessions=0,
                    status="gray",
                    summary="Loading...",
                ))
        return placeholders
    except Exception:
        return []


class DataStore:
    def __init__(self, app=None):
        self._app = app
        self._state = StoreState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> StoreState:
        return self._state

    def set_projects(
        self,
        projects: list[ProjectInfo],
        prs: dict[str, list[EnhancedPR]] | None = None,
        sessions: dict[str, list[SessionInfo]] | None = None,
    ) -> None:
        old = dict(self._state.projects)
        new_projects: dict[str, ProjectData] = {}
        order: list[str] = []

        for p in projects:
            preserved = old.get(p.name)
            new_projects[p.name] = ProjectData(
                info=p,
                prs=prs.get(p.name, []) if prs else (preserved.prs if preserved else []),
                sessions=(
                    sessions.get(p.name, []) if sessions
                    else (preserved.sessions if preserved else [])
                ),
                card_summary=preserved.card_summary if preserved else None,
                card_summary_status=preserved.card_summary_status if preserved else "",
                card_summary_time=preserved.card_summary_time if preserved else "",
                ai_summary=preserved.ai_summary if preserved else None,
            )
            order.append(p.name)

        self._state.projects = new_projects
        self._state.project_order = order

    def update_prs(self, prs: dict[str, list[EnhancedPR]]) -> None:
        for name, pr_list in prs.items():
            if name in self._state.projects:
                self._state.projects[name].prs = pr_list

    def set_card_summary(
        self, project_name: str, data: dict, status: str = "", time: str = ""
    ) -> None:
        if project_name in self._state.projects:
            pd = self._state.projects[project_name]
            pd.card_summary = data
            pd.card_summary_status = status
            pd.card_summary_time = time

    def set_ai_summary(self, project_name: str, summary: dict) -> None:
        if project_name in self._state.projects:
            self._state.projects[project_name].ai_summary = summary

    def poll_refresh(
        self,
        new_projects: list[ProjectInfo],
        new_prs: dict[str, list[EnhancedPR]],
    ) -> bool:
        old_pr_keys = self._get_pr_fingerprint()

        self.set_projects(new_projects, prs=new_prs)

        new_pr_keys = self._get_pr_fingerprint()
        return old_pr_keys != new_pr_keys

    def _get_pr_fingerprint(self) -> frozenset:
        items = set()
        for name, pd in self._state.projects.items():
            for pr in pd.prs:
                items.add((name, pr.number, pr.title, pr.ci_status, pr.review_status))
        return frozenset(items)

    def force_refresh(
        self,
        projects: list[ProjectInfo],
        prs: dict[str, list[EnhancedPR]],
    ) -> None:
        self.set_projects(projects, prs=prs)

    def get_project(self, name: str) -> ProjectData | None:
        return self._state.projects.get(name)

    def get_projects_ordered(self) -> list[ProjectData]:
        result = []
        for name in self._state.project_order:
            pd = self._state.projects.get(name)
            if pd:
                result.append(pd)
        return result

    def load_initial(self) -> str:
        if not _has_credentials():
            return "no_credentials"

        if not _has_selected_repos_or_config():
            return "no_repos"

        placeholders = _build_loading_placeholders()
        if placeholders:
            self.set_projects(placeholders)
        return "has_repos"

    def fetch_live(self) -> tuple[list[ProjectInfo], dict[str, list[EnhancedPR]]]:
        return _fetch_live_projects_and_prs()

    def has_credentials(self) -> bool:
        return _has_credentials()

    def has_selected_repos_or_config(self) -> bool:
        return _has_selected_repos_or_config()
