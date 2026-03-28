from __future__ import annotations

import json
from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Static, Footer, Input, Label
from textual.worker import Worker, WorkerState

from pm.github.pr import EnhancedPR
from pm.tui.polling import SmartPoller, PollingUpdate
from pm.tui.widgets.detail_panel import DetailPanel
from pm.tui.widgets.project_list import ProjectInfo, ProjectList
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


def get_sample_projects() -> list[ProjectInfo]:
    return [
        ProjectInfo(
            name="401K Website",
            account="Personal",
            repos=["owner/401k-frontend", "owner/401k-backend"],
            open_prs=5,
            active_sessions=1,
            status="green",
            summary=(
                "Frontend development is progressing well. The mobile responsive "
                "redesign is 80% complete. Backend auth module has a bug in the "
                "login flow that needs attention before the next release."
            ),
            instructions="Focus on mobile responsive design.\nUse Tailwind CSS for styling.",
            assets=["~/designs/401k-mockup.png"],
        ),
        ProjectInfo(
            name="Side Project",
            account="Personal",
            repos=["owner/side-project"],
            open_prs=2,
            active_sessions=0,
            status="yellow",
            summary=(
                "Project has been idle for 2 weeks. Two PRs are awaiting review. "
                "Consider prioritizing the dependency update PR to avoid security issues."
            ),
        ),
        ProjectInfo(
            name="FAA Project",
            account="Company",
            repos=["company-org/faa-main", "company-org/faa-docs"],
            open_prs=8,
            active_sessions=2,
            status="red",
            summary=(
                "CI is failing on the main branch. Three PRs have unresolved review "
                "comments. The compliance documentation update is blocked on the "
                "API schema changes."
            ),
            instructions="Follow FAA compliance guidelines.",
        ),
        ProjectInfo(
            name="Internal Tool",
            account="Company",
            repos=["company-org/internal-tool"],
            open_prs=1,
            active_sessions=0,
            status="green",
            summary=(
                "Stable and up to date. The single open PR is a minor docs update "
                "that's approved and ready to merge."
            ),
        ),
    ]


def get_sample_prs(project_name: str) -> list[EnhancedPR]:
    prs_data: dict[str, list[EnhancedPR]] = {
        "401K Website": [
            EnhancedPR(
                repo_id="owner/401k-frontend", number=42, title="Fix auth bug in login flow",
                state="open", author="ai-bot", ci_status="failing", review_status="changes_requested",
                created_at=datetime(2026, 3, 20), updated_at=datetime(2026, 3, 25),
                unresolved_count=3, needs_attention=True,
            ),
            EnhancedPR(
                repo_id="owner/401k-frontend", number=38, title="Add mobile responsive layout",
                state="open", author="ai-bot", ci_status="passing", review_status="approved",
                created_at=datetime(2026, 3, 18), updated_at=datetime(2026, 3, 24),
            ),
            EnhancedPR(
                repo_id="owner/401k-frontend", number=35, title="Refactor component structure",
                state="open", author="zelin", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 15), updated_at=datetime(2026, 3, 22),
            ),
            EnhancedPR(
                repo_id="owner/401k-backend", number=12, title="API endpoint update",
                state="open", author="zelin", ci_status="passing", review_status="approved",
                created_at=datetime(2026, 3, 10), updated_at=datetime(2026, 3, 20),
            ),
            EnhancedPR(
                repo_id="owner/401k-backend", number=10, title="Database migration v2",
                state="open", author="ai-bot", ci_status="pending", review_status="pending",
                created_at=datetime(2026, 3, 8), updated_at=datetime(2026, 3, 19),
            ),
        ],
        "Side Project": [
            EnhancedPR(
                repo_id="owner/side-project", number=7, title="Update dependencies",
                state="open", author="dependabot", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 12), updated_at=datetime(2026, 3, 12),
            ),
            EnhancedPR(
                repo_id="owner/side-project", number=5, title="Add dark mode support",
                state="open", author="zelin", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 5), updated_at=datetime(2026, 3, 10),
            ),
        ],
        "FAA Project": [
            EnhancedPR(
                repo_id="company-org/faa-main", number=89, title="Update compliance checks",
                state="open", author="ai-bot", ci_status="failing", review_status="changes_requested",
                created_at=datetime(2026, 3, 22), updated_at=datetime(2026, 3, 25),
                unresolved_count=5, needs_attention=True,
            ),
            EnhancedPR(
                repo_id="company-org/faa-main", number=85, title="Add new API validation",
                state="open", author="colleague", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 20), updated_at=datetime(2026, 3, 24),
            ),
        ],
        "Internal Tool": [
            EnhancedPR(
                repo_id="company-org/internal-tool", number=15, title="Update README docs",
                state="open", author="zelin", ci_status="passing", review_status="approved",
                created_at=datetime(2026, 3, 24), updated_at=datetime(2026, 3, 25),
            ),
        ],
    }
    return prs_data.get(project_name, [])


def get_sample_sessions(project_name: str) -> list[SessionInfo]:
    sessions_data: dict[str, list[SessionInfo]] = {
        "401K Website": [
            SessionInfo(
                id="s-001", project="401K Website", task="Fix auth bug",
                agent="claude-code", status="running",
                created_at=datetime(2026, 3, 25, 14, 30),
                branch="pm/fix-auth", pr_number=42,
            ),
        ],
        "FAA Project": [
            SessionInfo(
                id="s-002", project="FAA Project", task="Update compliance",
                agent="claude-code", status="running",
                created_at=datetime(2026, 3, 25, 10, 0),
                branch="pm/compliance", pr_number=89,
            ),
            SessionInfo(
                id="s-003", project="FAA Project", task="Fix CI pipeline",
                agent="claude-code", status="paused",
                created_at=datetime(2026, 3, 24, 16, 0),
                branch="pm/fix-ci",
            ),
        ],
    }
    return sessions_data.get(project_name, [])


def _is_demo(screen) -> bool:
    """Check if the app is in demo mode."""
    try:
        return getattr(screen.app, '_demo', False) or getattr(screen.app, 'demo_mode', False)
    except Exception:
        return False


def _get_projects(screen) -> list[ProjectInfo]:
    """Get projects - demo or sample data."""
    if _is_demo(screen):
        from pm.ai.demo import get_demo_projects
        return get_demo_projects()
    # Try to load real projects from config
    try:
        from pm.config.loader import load_config
        cfg = load_config()
        if cfg.projects:
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
            return projects
    except Exception:
        pass
    return get_sample_projects()


def _get_prs(screen, project_name: str) -> list[EnhancedPR]:
    """Get PRs - demo or sample data."""
    if _is_demo(screen):
        from pm.ai.demo import get_demo_prs
        return get_demo_prs(project_name)
    # Check live data cache on the screen
    try:
        live_prs = getattr(screen, '_live_prs', {})
        if project_name in live_prs:
            return live_prs[project_name]
    except Exception:
        pass
    return get_sample_prs(project_name)


def _get_sessions(screen, project_name: str) -> list[SessionInfo]:
    """Get sessions - demo or sample data."""
    if _is_demo(screen):
        from pm.ai.demo import get_demo_sessions
        return get_demo_sessions(project_name)
    return get_sample_sessions(project_name)


def _get_ai_summary(screen, project_name: str) -> dict | None:
    """Get AI summary for a project (from demo data or cache)."""
    if _is_demo(screen):
        from pm.ai.demo import DEMO_SUMMARIES
        return DEMO_SUMMARIES.get(project_name)
    return None


def _get_ai_suggestions(screen) -> list[dict] | None:
    """Get AI suggestions (from demo data or cache)."""
    if _is_demo(screen):
        from pm.ai.demo import DEMO_SUGGESTIONS
        return DEMO_SUGGESTIONS
    return None


def _has_credentials() -> bool:
    """Check if user has stored credentials."""
    try:
        from pm.auth.credentials import load_credentials
        creds = load_credentials()
        return bool(creds.get("accounts", {}))
    except Exception:
        return False


def _get_credential_token(account: str = "personal") -> str | None:
    """Get token from credentials.yaml."""
    try:
        from pm.auth.credentials import get_token
        return get_token(account)
    except Exception:
        return None


def _fetch_live_projects_and_prs() -> tuple[list[ProjectInfo], dict[str, list[EnhancedPR]]]:
    """Fetch real projects and PRs from GitHub using stored credentials.

    Returns (projects, {project_name: [prs]}).
    Works with or without a config file. Without config, auto-discovers repos.
    """
    from pm.auth.credentials import load_credentials
    from pm.auth.github_oauth import discover_repos

    creds = load_credentials()
    accounts = creds.get("accounts", {})
    if not accounts:
        return [], {}

    # Try loading config first
    from pm.config.loader import load_config, has_real_projects
    cfg = load_config()

    projects: list[ProjectInfo] = []
    all_prs: dict[str, list[EnhancedPR]] = {}

    if has_real_projects(cfg):
        # Use config-based projects
        for account_name in accounts:
            token = accounts[account_name].get("token", "")
            if not token:
                continue

            import httpx
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/json",
            }

            for proj_name, proj_cfg in cfg.projects.items():
                if proj_cfg.account != account_name:
                    continue
                proj_prs: list[EnhancedPR] = []
                for repo_name in proj_cfg.repos:
                    try:
                        resp = httpx.get(
                            f"https://api.github.com/repos/{repo_name}/pulls",
                            headers=headers,
                            params={"state": "open", "per_page": 100},
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            for pr_data in resp.json():
                                proj_prs.append(EnhancedPR(
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

                pr_count = len(proj_prs)
                has_failing = False  # Would need checks API for real status

                status = "green"
                if pr_count == 0:
                    status = "gray"
                elif pr_count > 5:
                    status = "yellow"

                all_prs[proj_name] = proj_prs
                projects.append(ProjectInfo(
                    name=proj_name,
                    account=proj_cfg.account,
                    repos=list(proj_cfg.repos),
                    open_prs=pr_count,
                    active_sessions=0,
                    status=status,
                    summary=f"{pr_count} open PRs" if pr_count else "No open PRs",
                    instructions=proj_cfg.instructions,
                    assets=list(proj_cfg.assets),
                ))
    else:
        # No real config: auto-discover repos from GitHub
        for account_name, account_data in accounts.items():
            token = account_data.get("token", "")
            if not token:
                continue

            repos = discover_repos(token)
            if not repos:
                continue

            username = account_data.get("username", "")
            import httpx
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/json",
            }

            # Group repos by owner
            grouped: dict[str, list[dict]] = {}
            for repo in repos:
                owner = repo.get("owner", "unknown")
                grouped.setdefault(owner, []).append(repo)

            for owner, owner_repos in grouped.items():
                proj_prs: list[EnhancedPR] = []
                repo_names = []
                for repo in owner_repos:
                    full_name = repo["full_name"]
                    repo_names.append(full_name)
                    try:
                        resp = httpx.get(
                            f"https://api.github.com/repos/{full_name}/pulls",
                            headers=headers,
                            params={"state": "open", "per_page": 100},
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            for pr_data in resp.json():
                                proj_prs.append(EnhancedPR(
                                    repo_id=full_name,
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

                pr_count = len(proj_prs)
                status = "green" if pr_count == 0 else ("yellow" if pr_count > 5 else "green")
                if pr_count == 0:
                    status = "gray"

                all_prs[owner] = proj_prs
                projects.append(ProjectInfo(
                    name=owner,
                    account=account_name,
                    repos=repo_names,
                    open_prs=pr_count,
                    active_sessions=0,
                    status=status,
                    summary=f"{pr_count} open PRs across {len(repo_names)} repos",
                ))

    return projects, all_prs


class PortfolioScreen(Screen):
    DEFAULT_CSS = """
    PortfolioScreen {
        layout: vertical;
    }

    #portfolio-title {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $primary-background-darken-1;
        color: $primary-lighten-2;
        text-style: bold;
        border-bottom: solid $primary 40%;
        padding: 0 2;
    }

    #empty-state-container {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        display: none;
    }

    #empty-state-container.visible {
        display: block;
    }

    #empty-state-text {
        text-align: center;
        color: $text-muted;
        width: auto;
        height: auto;
        padding: 4 8;
    }

    #portfolio-body {
        layout: horizontal;
        height: 1fr;
    }

    #portfolio-body.hidden {
        display: none;
    }

    #left-panel {
        width: 30%;
        min-width: 24;
        border-right: solid $primary 30%;
        background: $surface-darken-1;
        padding: 0;
    }

    #left-panel-title {
        dock: top;
        height: 2;
        padding: 0 1;
        background: $surface-darken-2;
        color: $primary;
        text-style: bold;
        border-bottom: solid $surface-lighten-1;
    }

    #right-panel {
        width: 70%;
        background: $surface;
        padding: 0;
    }

    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-background-darken-2;
        color: $text;
        padding: 0 1;
    }

    #portfolio-new-task-container {
        dock: bottom;
        height: auto;
        max-height: 5;
        background: $surface-darken-2;
        padding: 0 1;
        display: none;
    }

    #portfolio-new-task-container.visible {
        display: block;
    }

    #portfolio-new-task-input {
        width: 100%;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task_input_visible = False
        self._ai_summaries: dict[str, dict] = {}
        self._ai_suggestions: list[dict] = []
        self._loading_summary = False
        self._loading_suggestions = False
        self._live_prs: dict[str, list[EnhancedPR]] = {}
        self._live_loading = False
        self._poller: SmartPoller | None = None
        self._poll_timer: Timer | None = None

    BINDINGS = [
        Binding("q", "quit_app", "Quit"),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("tab", "next_tab", "Next Tab"),
        Binding("shift+tab", "prev_tab", "Prev Tab"),
        Binding("enter", "enter_project", "Open"),
        Binding("n", "new_task", "New Task"),
        Binding("s", "suggest", "Suggest"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
        Binding("comma", "open_settings", "Settings"),
        Binding("d", "toggle_demo", "Demo", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Portfolio Manager[/bold]  [dim]\u2502  Your projects at a glance[/dim]",
            id="portfolio-title",
        )
        yield Container(
            Static(
                "\n\n"
                "[bold cyan]Welcome to PPM![/bold cyan]\n\n"
                "No GitHub accounts connected yet.\n\n"
                "Press [bold][,][/bold] to open Settings\n"
                "and connect your first GitHub account.\n\n"
                "Or press [bold][d][/bold] to view demo data.\n",
                id="empty-state-text",
            ),
            id="empty-state-container",
        )
        with Horizontal(id="portfolio-body"):
            with Container(id="left-panel"):
                yield Static("[bold]Projects[/bold]", id="left-panel-title")
                yield ProjectList()
            with Container(id="right-panel"):
                yield DetailPanel()
        with Container(id="portfolio-new-task-container"):
            yield Label("[bold cyan]New Task:[/bold cyan] Enter task description for current project")
            yield Input(placeholder="Describe the task...", id="portfolio-new-task-input")
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        if _is_demo(self):
            self._show_portfolio_view()
            projects = _get_projects(self)
            project_list = self.query_one(ProjectList)
            project_list.set_projects(projects)
            from pm.ai.demo import DEMO_SUMMARIES, DEMO_SUGGESTIONS
            self._ai_summaries = dict(DEMO_SUMMARIES)
            self._ai_suggestions = list(DEMO_SUGGESTIONS)
        elif _has_credentials():
            self._show_portfolio_view()
            projects = _get_projects(self)
            project_list = self.query_one(ProjectList)
            project_list.set_projects(projects)
            self._start_live_loading()
        else:
            self._show_empty_state()

    def _show_empty_state(self) -> None:
        empty = self.query_one("#empty-state-container")
        empty.add_class("visible")
        body = self.query_one("#portfolio-body")
        body.add_class("hidden")

    def _show_portfolio_view(self) -> None:
        empty = self.query_one("#empty-state-container")
        empty.remove_class("visible")
        body = self.query_one("#portfolio-body")
        body.remove_class("hidden")

    def _start_polling(self) -> None:
        """Initialize and start the smart poller."""
        if self._poller is not None:
            return
        try:
            from pm.auth.credentials import load_credentials
            from pm.config.loader import load_config, has_real_projects
            creds = load_credentials()
            if not creds.get("accounts"):
                return
            cfg = load_config()
            if not has_real_projects(cfg):
                cfg = None
            self._poller = SmartPoller(credentials=creds, config=cfg)
            if self._data_has_projects():
                self._poller._data.projects = list(self._get_current_projects())
                self._poller._data.prs = dict(self._live_prs)
            self._poll_timer = self.set_interval(5, self._poll_tick)
        except Exception:
            pass

    def _data_has_projects(self) -> bool:
        try:
            project_list = self.query_one(ProjectList)
            return bool(project_list._projects)
        except Exception:
            return False

    def _get_current_projects(self) -> list[ProjectInfo]:
        try:
            project_list = self.query_one(ProjectList)
            return list(project_list._projects)
        except Exception:
            return []

    async def _poll_tick(self) -> None:
        """Called every 5 seconds by the timer to poll GitHub."""
        if self._poller is None or self._live_loading:
            return
        self.run_worker(self._poll_worker, name="poll_tick", thread=True)

    async def _poll_worker(self) -> PollingUpdate | None:
        """Worker to run a single poll tick."""
        if self._poller is None:
            return None
        return await self._poller.tick()

    def _apply_polling_update(self, update: PollingUpdate) -> None:
        """Apply a polling update to the TUI."""
        if update.projects_changed and self._poller:
            self._live_prs = dict(self._poller.data.prs)
            if self._poller.data.projects:
                project_list = self.query_one(ProjectList)
                project_list.set_projects(self._poller.data.projects)

        if update.new_prs:
            names = ", ".join(f"#{p.number}" for p in update.new_prs[:3])
            extra = f" +{len(update.new_prs) - 3} more" if len(update.new_prs) > 3 else ""
            status_bar = self.query_one(StatusBar)
            status_bar.set_message(f"New PRs: {names}{extra}")
            self.set_timer(5, lambda: status_bar.set_message(""))

        self._update_polling_status()

    def _update_polling_status(self) -> None:
        """Update the status bar with polling info."""
        if self._poller is None:
            return
        try:
            status_bar = self.query_one(StatusBar)
            status_bar.set_polling_status(self._poller.get_status_text())
        except Exception:
            pass

    def _stop_polling(self) -> None:
        """Stop the poller and timer."""
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        self._poller = None

    def _start_live_loading(self) -> None:
        """Start background loading of live GitHub data."""
        self._live_loading = True
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Fetching live data from GitHub...")
        self.run_worker(self._fetch_live_data_worker, name="live_fetch", thread=True)

    async def _fetch_live_data_worker(self) -> tuple[list[ProjectInfo], dict[str, list[EnhancedPR]]]:
        """Worker to fetch live data from GitHub."""
        return _fetch_live_projects_and_prs()

    def _start_background_loading(self) -> None:
        """Start background loading of data. Uses Workers to avoid blocking."""
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Loading project data...")
        self.set_timer(1, lambda: status_bar.set_message(""))

    def on_project_list_project_selected(self, event: ProjectList.ProjectSelected) -> None:
        detail = self.query_one(DetailPanel)
        detail.set_project(event.project)
        detail.set_prs(_get_prs(self, event.project.name))
        detail.set_sessions(_get_sessions(self, event.project.name))

        # Update status panel with AI summary
        ai_summary = self._ai_summaries.get(event.project.name)
        if ai_summary:
            detail.set_ai_summary(ai_summary)
        detail.set_ai_suggestions(self._ai_suggestions)

    def on_project_list_project_activated(self, event: ProjectList.ProjectActivated) -> None:
        from pm.tui.screens.project import ProjectScreen
        prs = _get_prs(self, event.project.name)
        sessions = _get_sessions(self, event.project.name)
        self.app.push_screen(ProjectScreen(
            project=event.project, prs=prs, sessions=sessions,
        ))

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_cursor_down(self) -> None:
        self.query_one(ProjectList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ProjectList).action_cursor_up()

    def action_next_tab(self) -> None:
        self.query_one(DetailPanel).action_next_tab()

    def action_prev_tab(self) -> None:
        self.query_one(DetailPanel).action_prev_tab()

    def action_enter_project(self) -> None:
        project_list = self.query_one(ProjectList)
        if project_list.current_project:
            project_list.action_activate()

    def action_refresh(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Refreshing... (cache invalidated)")

        # Invalidate AI summaries
        self._ai_summaries.clear()
        self._ai_suggestions.clear()
        self._live_prs.clear()

        # Re-load AI data
        if _is_demo(self):
            from pm.ai.demo import DEMO_SUMMARIES, DEMO_SUGGESTIONS
            self._ai_summaries = dict(DEMO_SUMMARIES)
            self._ai_suggestions = list(DEMO_SUGGESTIONS)
            # Reload data
            projects = _get_projects(self)
            project_list = self.query_one(ProjectList)
            project_list.set_projects(projects)
            self.set_timer(2, lambda: status_bar.set_message(""))
        elif _has_credentials():
            if self._poller is not None:
                self.run_worker(self._force_refresh_worker, name="force_refresh", thread=True)
            else:
                self._start_live_loading()
        else:
            # Reload data
            projects = _get_projects(self)
            project_list = self.query_one(ProjectList)
            project_list.set_projects(projects)
            self.set_timer(2, lambda: status_bar.set_message(""))

    async def _force_refresh_worker(self) -> PollingUpdate | None:
        """Worker for force refresh via 'r' key."""
        if self._poller is None:
            return None
        return await self._poller.force_refresh()

    def action_suggest(self) -> None:
        status_bar = self.query_one(StatusBar)
        detail = self.query_one(DetailPanel)

        if _is_demo(self):
            from pm.ai.demo import DEMO_SUGGESTIONS
            self._ai_suggestions = list(DEMO_SUGGESTIONS)
            detail.set_ai_suggestions(self._ai_suggestions)
            status_bar.set_message("AI suggestions loaded")
            self.set_timer(3, lambda: status_bar.set_message(""))
        else:
            if self._loading_suggestions:
                status_bar.set_message("Already generating suggestions...")
                return

            self._loading_suggestions = True
            status_bar.set_message("Generating AI suggestions...")
            detail.show_suggestions_loading()

            self.run_worker(self._generate_suggestions_worker, thread=True)

    async def _generate_suggestions_worker(self) -> list[dict]:
        """Worker to generate AI suggestions in background."""
        try:
            from pm.ai.suggest import AISuggestionEngine
            engine = AISuggestionEngine()

            projects = _get_projects(self)
            projects_data = []
            for p in projects:
                prs = _get_prs(self, p.name)
                projects_data.append({
                    "name": p.name,
                    "summary": self._ai_summaries.get(p.name, {}),
                    "open_prs_count": len(prs),
                    "active_sessions_count": p.active_sessions,
                    "failing_ci_count": sum(1 for pr in prs if pr.ci_status == "failing"),
                    "changes_requested_count": sum(1 for pr in prs if pr.review_status == "changes_requested"),
                })

            suggestions = engine.generate_suggestions(projects_data)
            return [s.to_dict() for s in suggestions]
        except Exception as e:
            return []

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        # Handle poll tick completion
        if event.worker.name == "poll_tick" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result is not None:
                self._apply_polling_update(result)
            else:
                self._update_polling_status()
            return

        if event.worker.name == "poll_tick" and event.state == WorkerState.ERROR:
            return

        # Handle force refresh completion
        if event.worker.name == "force_refresh" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result is not None:
                self._apply_polling_update(result)
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("Refresh complete")
            self.set_timer(3, lambda: status_bar.set_message(""))
            return

        if event.worker.name == "force_refresh" and event.state == WorkerState.ERROR:
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("Force refresh failed")
            self.set_timer(3, lambda: status_bar.set_message(""))
            return

        # Handle live data fetch completion
        if event.worker.name == "live_fetch" and event.state == WorkerState.SUCCESS:
            self._live_loading = False
            result = event.worker.result
            if result:
                projects, prs_map = result
                if projects:
                    self._live_prs = prs_map
                    project_list = self.query_one(ProjectList)
                    project_list.set_projects(projects)
                    status_bar = self.query_one(StatusBar)
                    total_prs = sum(len(prs) for prs in prs_map.values())
                    status_bar.set_message(
                        f"Loaded {len(projects)} projects, {total_prs} open PRs"
                    )
                    self.set_timer(3, lambda: status_bar.set_message(""))
                    self._start_polling()
                    return
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("Could not fetch live data")
            self.set_timer(3, lambda: status_bar.set_message(""))
            self._start_polling()
            return

        if event.worker.name == "live_fetch" and event.state == WorkerState.ERROR:
            self._live_loading = False
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("Failed to fetch GitHub data")
            self.set_timer(3, lambda: status_bar.set_message(""))
            self._start_polling()
            return

        if event.state == WorkerState.SUCCESS and self._loading_suggestions:
            self._loading_suggestions = False
            result = event.worker.result
            if result:
                self._ai_suggestions = result
                try:
                    detail = self.query_one(DetailPanel)
                    detail.set_ai_suggestions(self._ai_suggestions)
                except Exception:
                    pass
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("AI suggestions ready")
            self.set_timer(3, lambda: status_bar.set_message(""))

    def action_new_task(self) -> None:
        project_list = self.query_one(ProjectList)
        if not project_list.current_project:
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("No project selected")
            return
        self._task_input_visible = True
        container = self.query_one("#portfolio-new-task-container")
        container.add_class("visible")
        try:
            self.query_one("#portfolio-new-task-input", Input).focus()
        except Exception:
            pass

    def _hide_task_input(self) -> None:
        self._task_input_visible = False
        container = self.query_one("#portfolio-new-task-container")
        container.remove_class("visible")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "portfolio-new-task-input":
            task_desc = event.value.strip()
            if task_desc:
                status_bar = self.query_one(StatusBar)
                project_list = self.query_one(ProjectList)
                project_name = project_list.current_project.name if project_list.current_project else "unknown"
                status_bar.set_message(f"Creating task for {project_name}: {task_desc}...")
                event.input.value = ""
                self._hide_task_input()
                self.set_timer(
                    2, lambda: status_bar.set_message(f"Task created: {task_desc}")
                )

    def on_unmount(self) -> None:
        self._stop_polling()

    def action_open_settings(self) -> None:
        from pm.tui.screens.settings import SettingsScreen
        self.app.push_screen(SettingsScreen(), callback=self._on_settings_closed)

    def _on_settings_closed(self, result=None) -> None:
        # Reload accounts and refresh display
        if _has_credentials():
            self._show_portfolio_view()
            self._live_prs.clear()
            self._start_live_loading()
        else:
            self._show_empty_state()

    def action_toggle_demo(self) -> None:
        # Switch to demo mode from empty state
        self._show_portfolio_view()
        from pm.ai.demo import get_demo_projects, DEMO_SUMMARIES, DEMO_SUGGESTIONS
        projects = get_demo_projects()
        project_list = self.query_one(ProjectList)
        project_list.set_projects(projects)
        self._ai_summaries = dict(DEMO_SUMMARIES)
        self._ai_suggestions = list(DEMO_SUGGESTIONS)
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Demo mode activated")
        self.set_timer(3, lambda: status_bar.set_message(""))

    def action_help(self) -> None:
        from pm.tui.screens.help import HelpScreen
        self.app.push_screen(HelpScreen())
