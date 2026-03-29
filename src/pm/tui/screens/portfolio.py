from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Static, Footer, Input, Label
from textual.worker import Worker, WorkerState

from pm.github.pr import EnhancedPR
from pm.tui.polling import SmartPoller, PollingUpdate
from pm.tui.widgets.project_card import ProjectCard
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


def _is_demo(screen) -> bool:
    """Check if the app is in demo mode."""
    try:
        return getattr(screen.app, '_demo', False) or getattr(screen.app, 'demo_mode', False)
    except Exception:
        return False


def _get_projects(screen) -> list[ProjectInfo]:
    """Get projects - demo data or from config. Never returns sample/fake data."""
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
    return []


def _get_prs(screen, project_name: str) -> list[EnhancedPR]:
    """Get PRs - demo data or from live cache. Never returns sample/fake data."""
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
    return []


def _get_sessions(screen, project_name: str) -> list[SessionInfo]:
    """Get sessions - demo data or empty. Never returns sample/fake data."""
    if _is_demo(screen):
        from pm.ai.demo import get_demo_sessions
        return get_demo_sessions(project_name)
    return []


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


def _has_selected_repos_or_config() -> bool:
    """Check if user has selected repos or a real config with projects."""
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
    """Get token from credentials.yaml."""
    try:
        from pm.auth.credentials import get_token
        return get_token(account)
    except Exception:
        return None


def _get_account_display_names() -> dict[str, str]:
    """Get display names for accounts from credentials.yaml."""
    try:
        from pm.auth.credentials import load_credentials
        creds = load_credentials()
        accounts = creds.get("accounts", {})
        names = {}
        idx = 1
        for account_id, data in accounts.items():
            display = data.get("display_name", "")
            username = data.get("username", "")
            if display:
                names[account_id] = display
            elif username:
                names[account_id] = f"{username}"
            else:
                names[account_id] = f"GitHub {idx}"
            idx += 1
        return names
    except Exception:
        return {}


def _get_selected_repos_for_account(account_name: str) -> list[str]:
    """Get selected repos for an account from credentials.yaml."""
    try:
        from pm.auth.credentials import get_selected_repos
        return get_selected_repos(account_name)
    except Exception:
        return []


def _fetch_prs_for_repos(
    repo_names: list[str], headers: dict
) -> list[EnhancedPR]:
    """Fetch open PRs for a list of repos."""
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
    """Fetch real projects and PRs from GitHub using stored credentials.

    Returns (projects, {project_name: [prs]}).
    Respects selected_repos from credentials.yaml.
    Works with or without a config file. Without config, groups by owner.
    """
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
        # Use config-based projects, filtered by selected_repos
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
                # Filter repos to only selected ones (if selections exist)
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
        # No real config: check for project groups first, then show per-repo
        from pm.auth.credentials import load_project_groups
        project_groups = load_project_groups()

        if project_groups:
            # Use project groups: one card per group
            for group_name, group_repos in project_groups.items():
                if not group_repos:
                    continue
                # Find tokens for the repos in this group
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
                # Use the first account that has repos in this group
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
            # No project groups: each selected repo becomes its own card
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

    #cards-scroll {
        height: 1fr;
        padding: 1 2;
    }

    #cards-scroll.hidden {
        display: none;
    }

    .account-header {
        width: 100%;
        height: 2;
        padding: 0 1;
        color: $primary;
        text-style: bold;
        margin: 1 1 0 1;
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
        self._cards: list[ProjectCard] = []
        self._selected_index: int = 0
        self._projects: list[ProjectInfo] = []

    BINDINGS = [
        Binding("q", "quit_app", "Quit"),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("enter", "enter_project", "Open"),
        Binding("n", "new_task", "New Task"),
        Binding("s", "open_settings", "Settings"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
        Binding("d", "toggle_demo", "Demo", show=False),
        Binding("ctrl+p", "noop", "", show=False),
    ]

    def action_noop(self) -> None:
        pass

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]PPM[/bold]  [dim]\u2502  Your projects at a glance[/dim]",
            id="portfolio-title",
        )
        yield Container(
            Static(
                "\n\n"
                "[bold cyan]Welcome to PPM![/bold cyan]\n\n"
                "No GitHub accounts connected yet.\n\n"
                "Press [bold][s][/bold] to open Settings\n"
                "and connect your GitHub account.\n\n"
                "Press [bold][d][/bold] to view demo data.\n",
                id="empty-state-text",
            ),
            id="empty-state-container",
        )
        yield VerticalScroll(id="cards-scroll")
        with Container(id="portfolio-new-task-container"):
            yield Label("[bold cyan]New Task:[/bold cyan] Enter task description for current project")
            yield Input(placeholder="Describe the task...", id="portfolio-new-task-input")
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        if _is_demo(self):
            self._show_cards_view()
            projects = _get_projects(self)
            self._set_projects(projects)
            from pm.ai.demo import DEMO_SUMMARIES, DEMO_SUGGESTIONS
            self._ai_summaries = dict(DEMO_SUMMARIES)
            self._ai_suggestions = list(DEMO_SUGGESTIONS)
        elif _has_credentials():
            has_selections = _has_selected_repos_or_config()
            self._show_cards_view()
            if has_selections:
                placeholders = self._build_loading_placeholders()
                self._set_projects(placeholders)
                self._start_live_loading()
            else:
                self._show_no_repos_state()
        else:
            self._show_empty_state()

        self._show_recovery_notification()

    def _show_recovery_notification(self) -> None:
        """Show notification if sessions were recovered on startup."""
        try:
            recovered = getattr(self.app, '_recovered_sessions', [])
            if not recovered:
                return
            recovered_count = sum(1 for r in recovered if r["status"] == "recovered")
            lost_count = sum(1 for r in recovered if r["status"] == "lost")
            parts = []
            if recovered_count:
                parts.append(f"Recovered {recovered_count} agent session(s) that were running while PPM was closed")
            if lost_count:
                parts.append(f"{lost_count} session(s) were lost (tmux ended)")
            if parts:
                status_bar = self.query_one(StatusBar)
                status_bar.set_message(" | ".join(parts))
                self.set_timer(8, lambda: status_bar.set_message(""))
        except Exception:
            pass

    def _show_empty_state(self) -> None:
        empty = self.query_one("#empty-state-container")
        empty.add_class("visible")
        scroll = self.query_one("#cards-scroll")
        scroll.add_class("hidden")

    def _show_no_repos_state(self) -> None:
        """Show message when credentials exist but no repos are selected."""
        empty_text = self.query_one("#empty-state-text", Static)
        empty_text.update(
            "\n\n"
            "[bold cyan]No repos selected[/bold cyan]\n\n"
            "Press [bold][s][/bold] to open Settings and choose repos.\n\n"
            "Press [bold][d][/bold] to view demo data.\n"
        )
        empty = self.query_one("#empty-state-container")
        empty.add_class("visible")
        scroll = self.query_one("#cards-scroll")
        scroll.add_class("hidden")

    def _show_cards_view(self) -> None:
        empty = self.query_one("#empty-state-container")
        empty.remove_class("visible")
        scroll = self.query_one("#cards-scroll")
        scroll.remove_class("hidden")

    def _build_loading_placeholders(self) -> list[ProjectInfo]:
        """Create placeholder cards from selected repos/config with 'Loading...' state."""
        # First try config-based projects
        projects = _get_projects(self)
        if projects:
            return projects
        # Fall back to building from credentials selected_repos
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

    def _set_projects(self, projects: list[ProjectInfo]) -> None:
        """Build the card list grouped by account."""
        self._projects = projects
        scroll = self.query_one("#cards-scroll", VerticalScroll)
        scroll.remove_children()
        self._cards = []

        # Get display names for accounts
        display_names = _get_account_display_names()
        # Also map usernames to display names for fallback
        username_map: dict[str, str] = {}
        try:
            from pm.auth.credentials import load_credentials
            creds = load_credentials()
            for acct_id, data in creds.get("accounts", {}).items():
                uname = data.get("username", "")
                if uname:
                    username_map[uname] = display_names.get(acct_id, uname)
        except Exception:
            pass

        # Group by account
        grouped: dict[str, list[ProjectInfo]] = {}
        for p in projects:
            grouped.setdefault(p.account, []).append(p)

        for account, account_projects in grouped.items():
            # Resolve display name: check direct match, then username map
            display = display_names.get(account, "")
            if not display:
                display = username_map.get(account, "")
            if not display:
                display = account
            # Try to get username for the parenthetical
            username = ""
            try:
                from pm.auth.credentials import load_credentials
                creds = load_credentials()
                acct_data = creds.get("accounts", {}).get(account, {})
                username = acct_data.get("username", "")
            except Exception:
                pass
            if username and username != display:
                header_text = f"[bold cyan]\u25bc {display} ({username})[/bold cyan]"
            else:
                header_text = f"[bold cyan]\u25bc {display}[/bold cyan]"
            scroll.mount(Static(header_text, classes="account-header"))
            for proj in account_projects:
                prs = _get_prs(self, proj.name)
                ai_summary = _get_ai_summary(self, proj.name)
                card = ProjectCard(proj, prs=prs, ai_summary=ai_summary)
                scroll.mount(card)
                self._cards.append(card)

        if self._cards:
            self._selected_index = 0
            self._update_selection()

        # Trigger card summary generation for demo mode
        if _is_demo(self) and self._cards:
            self._apply_demo_card_data()

    def _apply_demo_card_data(self) -> None:
        """Apply demo card data to cards in demo mode."""
        from pm.ai.demo import DEMO_CARD_SUMMARIES
        for card in self._cards:
            card_data = DEMO_CARD_SUMMARIES.get(card.project.name)
            if card_data:
                card.set_card_data(
                    card_data.get("data", {}),
                    status=card_data.get("status", ""),
                    time=card_data.get("time", ""),
                )

    def _start_card_summaries(self) -> None:
        """Generate AI summaries for all cards in background."""
        self.run_worker(self._card_summaries_worker, name="card_summaries", thread=True)

    async def _card_summaries_worker(self) -> list[tuple[str, dict, str, str]]:
        """Collect context and generate card summaries for all cards."""
        from pm.ai.card_summary import CardSummaryGenerator, collect_card_context

        results: list[tuple[str, dict, str, str]] = []
        token = _get_credential_token() or ""
        generator = CardSummaryGenerator(db=None)

        for card in self._cards:
            try:
                context = collect_card_context(
                    card.project.name,
                    card.project.repos,
                    token,
                    db=None,
                )
                summary = generator.generate(card.project.name, context)
                results.append((
                    card.project.name,
                    summary,
                    context.last_command_status,
                    context.last_command_time,
                ))
            except Exception:
                pass
        return results

    def _update_selection(self) -> None:
        for i, card in enumerate(self._cards):
            card.selected = i == self._selected_index
        # Scroll selected card into view
        if self._cards and 0 <= self._selected_index < len(self._cards):
            self._cards[self._selected_index].scroll_visible()

    @property
    def current_project(self) -> ProjectInfo | None:
        if self._cards and 0 <= self._selected_index < len(self._cards):
            return self._cards[self._selected_index].project
        return None

    def on_project_card_clicked(self, event: ProjectCard.Clicked) -> None:
        try:
            idx = self._cards.index(event.card)
            self._selected_index = idx
            self._update_selection()
        except ValueError:
            pass

    # --- Polling ---

    def _start_polling(self) -> None:
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
            if self._projects:
                self._poller._data.projects = list(self._projects)
                self._poller._data.prs = dict(self._live_prs)
            self._poll_timer = self.set_interval(5, self._poll_tick)
        except Exception:
            pass

    async def _poll_tick(self) -> None:
        if self._poller is None or self._live_loading:
            return
        self.run_worker(self._poll_worker, name="poll_tick", thread=True)

    async def _poll_worker(self) -> PollingUpdate | None:
        if self._poller is None:
            return None
        return await self._poller.tick()

    def _apply_polling_update(self, update: PollingUpdate) -> None:
        if update.projects_changed and self._poller:
            self._live_prs = dict(self._poller.data.prs)
            if self._poller.data.projects:
                self._set_projects(self._poller.data.projects)

        if update.new_prs:
            names = ", ".join(f"#{p.number}" for p in update.new_prs[:3])
            extra = f" +{len(update.new_prs) - 3} more" if len(update.new_prs) > 3 else ""
            status_bar = self.query_one(StatusBar)
            status_bar.set_message(f"New PRs: {names}{extra}")
            self.set_timer(5, lambda: status_bar.set_message(""))

        self._update_polling_status()

    def _update_polling_status(self) -> None:
        if self._poller is None:
            return
        try:
            status_bar = self.query_one(StatusBar)
            status_bar.set_polling_status(self._poller.get_status_text())
        except Exception:
            pass

    def _stop_polling(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None
        self._poller = None

    # --- Live loading ---

    def _start_live_loading(self) -> None:
        self._live_loading = True
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Fetching live data from GitHub...")
        self.run_worker(self._fetch_live_data_worker, name="live_fetch", thread=True)

    async def _fetch_live_data_worker(self) -> tuple[list[ProjectInfo], dict[str, list[EnhancedPR]]]:
        return _fetch_live_projects_and_prs()

    def _start_background_loading(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Loading project data...")
        self.set_timer(1, lambda: status_bar.set_message(""))

    # --- Actions ---

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_cursor_down(self) -> None:
        if self._cards and self._selected_index < len(self._cards) - 1:
            self._selected_index += 1
            self._update_selection()

    def action_cursor_up(self) -> None:
        if self._cards and self._selected_index > 0:
            self._selected_index -= 1
            self._update_selection()

    def action_enter_project(self) -> None:
        if not self._cards or self._selected_index >= len(self._cards):
            return
        project = self._cards[self._selected_index].project
        from pm.tui.screens.project import ProjectScreen
        prs = _get_prs(self, project.name)
        sessions = _get_sessions(self, project.name)
        self.app.push_screen(ProjectScreen(
            project=project, prs=prs, sessions=sessions,
        ))

    def action_refresh(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Refreshing... (cache invalidated)")

        self._ai_summaries.clear()
        self._ai_suggestions.clear()
        self._live_prs.clear()

        if _is_demo(self):
            from pm.ai.demo import DEMO_SUMMARIES, DEMO_SUGGESTIONS
            self._ai_summaries = dict(DEMO_SUMMARIES)
            self._ai_suggestions = list(DEMO_SUGGESTIONS)
            projects = _get_projects(self)
            self._set_projects(projects)
            self.set_timer(2, lambda: status_bar.set_message(""))
        elif _has_credentials():
            if self._poller is not None:
                self.run_worker(self._force_refresh_worker, name="force_refresh", thread=True)
            else:
                self._show_cards_view()
                placeholders = self._build_loading_placeholders()
                self._set_projects(placeholders)
                self._start_live_loading()
        else:
            self.set_timer(2, lambda: status_bar.set_message(""))

    async def _force_refresh_worker(self) -> PollingUpdate | None:
        if self._poller is None:
            return None
        return await self._poller.force_refresh()

    def action_open_settings(self) -> None:
        from pm.tui.screens.settings import SettingsScreen
        self.app.push_screen(SettingsScreen(), callback=self._on_settings_closed)

    def _on_settings_closed(self, result=None) -> None:
        if _has_credentials():
            has_selections = _has_selected_repos_or_config()
            if has_selections:
                self._show_cards_view()
                self._live_prs.clear()
                placeholders = self._build_loading_placeholders()
                self._set_projects(placeholders)
                self._start_live_loading()
            else:
                self._show_no_repos_state()
        else:
            self._show_empty_state()

    def action_toggle_demo(self) -> None:
        self._show_cards_view()
        from pm.ai.demo import get_demo_projects, DEMO_SUMMARIES, DEMO_SUGGESTIONS
        projects = get_demo_projects()
        self._set_projects(projects)
        self._ai_summaries = dict(DEMO_SUMMARIES)
        self._ai_suggestions = list(DEMO_SUGGESTIONS)
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Demo mode activated")
        self.set_timer(3, lambda: status_bar.set_message(""))

    def action_help(self) -> None:
        from pm.tui.screens.help import HelpScreen
        self.app.push_screen(HelpScreen())

    def action_new_task(self) -> None:
        if not self.current_project:
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
                project_name = self.current_project.name if self.current_project else "unknown"
                status_bar.set_message(f"Creating task for {project_name}: {task_desc}...")
                event.input.value = ""
                self._hide_task_input()
                self.set_timer(
                    2, lambda: status_bar.set_message(f"Task created: {task_desc}")
                )

    def on_unmount(self) -> None:
        self._stop_polling()

    # --- Worker state handling ---

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name == "poll_tick" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result is not None:
                self._apply_polling_update(result)
            else:
                self._update_polling_status()
            return

        if event.worker.name == "poll_tick" and event.state == WorkerState.ERROR:
            return

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

        if event.worker.name == "card_summaries" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result:
                card_map = {card.project.name: card for card in self._cards}
                for name, data, status, time_str in result:
                    card = card_map.get(name)
                    if card:
                        card.set_card_data(data, status=status, time=time_str)
            return

        if event.worker.name == "card_summaries" and event.state == WorkerState.ERROR:
            return

        if event.worker.name == "live_fetch" and event.state == WorkerState.SUCCESS:
            self._live_loading = False
            result = event.worker.result
            if result:
                projects, prs_map = result
                if projects:
                    self._live_prs = prs_map
                    self._set_projects(projects)
                    status_bar = self.query_one(StatusBar)
                    total_prs = sum(len(prs) for prs in prs_map.values())
                    status_bar.set_message(
                        f"Loaded {len(projects)} projects, {total_prs} open PRs"
                    )
                    self.set_timer(3, lambda: status_bar.set_message(""))
                    self._start_polling()
                    self._start_card_summaries()
                    return
            # Clear loading placeholders and show error
            scroll = self.query_one("#cards-scroll", VerticalScroll)
            scroll.remove_children()
            self._cards = []
            self._projects = []
            scroll.mount(Static(
                "[yellow]Could not connect to GitHub.[/yellow]\n"
                "Press [bold][r][/bold] to retry.",
                classes="empty-state",
            ))
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("Could not fetch live data")
            self.set_timer(3, lambda: status_bar.set_message(""))
            self._start_polling()
            return

        if event.worker.name == "live_fetch" and event.state == WorkerState.ERROR:
            self._live_loading = False
            # Clear loading placeholders and show error
            scroll = self.query_one("#cards-scroll", VerticalScroll)
            scroll.remove_children()
            self._cards = []
            self._projects = []
            scroll.mount(Static(
                "[yellow]Could not connect to GitHub.[/yellow]\n"
                "Press [bold][r][/bold] to retry.",
                classes="empty-state",
            ))
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("Failed to fetch GitHub data")
            self.set_timer(3, lambda: status_bar.set_message(""))
            return

        if event.state == WorkerState.SUCCESS and self._loading_suggestions:
            self._loading_suggestions = False
            result = event.worker.result
            if result:
                self._ai_suggestions = result
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("AI suggestions ready")
            self.set_timer(3, lambda: status_bar.set_message(""))
