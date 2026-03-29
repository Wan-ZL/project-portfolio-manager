from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Static, Footer, Input, Label
from textual.worker import Worker, WorkerState

from pm.github.pr import EnhancedPR
from pm.tui.widgets.project_card import ProjectCard
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


def _get_account_display_names() -> dict[str, str]:
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
        self._poll_timer: Timer | None = None
        self._cards: list[ProjectCard] = []
        self._selected_index: int = 0

    BINDINGS = [
        Binding("q", "quit_app", "Quit"),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("enter", "enter_project", "Open"),
        Binding("n", "new_task", "New Task"),
        Binding("s", "open_settings", "Settings"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
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
                "and connect your GitHub account.\n",
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
        store = self.app.store

        result = store.load_initial()
        if result == "no_credentials":
            self._show_empty_state()
        elif result == "no_repos":
            self._show_no_repos_state()
        else:
            self._show_cards_view()
            self._render_cards()
            self._start_live_loading()

        self._show_recovery_notification()

    def _show_recovery_notification(self) -> None:
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
        empty_text = self.query_one("#empty-state-text", Static)
        empty_text.update(
            "\n\n"
            "[bold cyan]No repos selected[/bold cyan]\n\n"
            "Press [bold][s][/bold] to open Settings and choose repos.\n"
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

    # --- Render cards from store ---

    def _render_cards(self) -> None:
        store = self.app.store
        selected_name = ""
        if self._cards and 0 <= self._selected_index < len(self._cards):
            selected_name = self._cards[self._selected_index].project.name

        scroll = self.query_one("#cards-scroll", VerticalScroll)
        scroll.remove_children()
        self._cards = []

        ordered = store.get_projects_ordered()
        if not ordered:
            return

        display_names = _get_account_display_names()
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

        grouped: dict[str, list] = {}
        for pd in ordered:
            grouped.setdefault(pd.info.account, []).append(pd)

        for account, pds in grouped.items():
            display = display_names.get(account, "")
            if not display:
                display = username_map.get(account, "")
            if not display:
                display = account
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

            for pd in pds:
                card = ProjectCard(pd.info, prs=pd.prs, ai_summary=pd.ai_summary)
                if pd.card_summary:
                    card.set_card_data(
                        pd.card_summary,
                        status=pd.card_summary_status,
                        time=pd.card_summary_time,
                    )
                scroll.mount(card)
                self._cards.append(card)

        # Restore selection by name
        if selected_name:
            self._selected_index = next(
                (i for i, c in enumerate(self._cards) if c.project.name == selected_name),
                0,
            )
        elif self._cards:
            self._selected_index = 0

        if self._cards:
            self._update_selection()

    # --- Selection ---

    def _update_selection(self) -> None:
        for i, card in enumerate(self._cards):
            card.selected = i == self._selected_index
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

    # --- Polling (simple 30s timer) ---

    def _start_polling(self) -> None:
        if self._poll_timer is not None:
            return
        self._poll_timer = self.set_interval(30, self._poll_tick)

    async def _poll_tick(self) -> None:
        self.run_worker(self._poll_worker, name="poll", thread=True)

    async def _poll_worker(self) -> tuple[list[ProjectInfo], dict[str, list[EnhancedPR]]] | None:
        try:
            projects, prs = self.app.store.fetch_live()
            if projects:
                return projects, prs
        except Exception:
            pass
        return None

    def _stop_polling(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    # --- Live loading ---

    def _start_live_loading(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Fetching live data from GitHub...")
        self.run_worker(self._fetch_live_data_worker, name="live_fetch", thread=True)

    async def _fetch_live_data_worker(self) -> tuple[list[ProjectInfo], dict[str, list[EnhancedPR]]]:
        return self.app.store.fetch_live()

    # --- Card summaries (AI) ---

    def _start_card_summaries(self) -> None:
        self.run_worker(self._card_summaries_worker, name="card_summaries", thread=True)

    async def _card_summaries_worker(self) -> list[tuple[str, dict, str, str]]:
        from pm.ai.card_summary import CardSummaryGenerator, collect_card_context
        from pm.tui.store import _get_credential_token

        results: list[tuple[str, dict, str, str]] = []
        token = _get_credential_token() or ""
        generator = CardSummaryGenerator(db=None)

        for pd in self.app.store.get_projects_ordered():
            try:
                context = collect_card_context(
                    pd.info.name,
                    pd.info.repos,
                    token,
                    db=None,
                )
                summary = generator.generate(pd.info.name, context)
                results.append((
                    pd.info.name,
                    summary,
                    context.last_command_status,
                    context.last_command_time,
                ))
            except Exception:
                pass
        return results

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
        self.app.push_screen(ProjectScreen(project_name=project.name))

    def action_refresh(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Refreshing... (cache invalidated)")
        store = self.app.store

        if store.has_credentials():
            self._show_cards_view()
            result = store.load_initial()
            if result == "no_repos":
                self._show_no_repos_state()
                self.set_timer(2, lambda: status_bar.set_message(""))
            else:
                self._render_cards()
                self._start_live_loading()
        else:
            self.set_timer(2, lambda: status_bar.set_message(""))

    def action_open_settings(self) -> None:
        from pm.tui.screens.settings import SettingsScreen
        self.app.push_screen(SettingsScreen(), callback=self._on_settings_closed)

    def _on_settings_closed(self, result=None) -> None:
        store = self.app.store
        if store.has_credentials():
            if store.has_selected_repos_or_config():
                self._show_cards_view()
                store.load_initial()
                self._render_cards()
                self._start_live_loading()
            else:
                self._show_no_repos_state()
        else:
            self._show_empty_state()

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
        if event.worker.name == "poll" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result is not None:
                projects, prs = result
                changed = self.app.store.poll_refresh(projects, prs)
                if changed:
                    self._render_cards()
            return

        if event.worker.name == "poll" and event.state == WorkerState.ERROR:
            return

        if event.worker.name == "card_summaries" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result:
                store = self.app.store
                for name, data, status, time_str in result:
                    store.set_card_summary(name, data, status=status, time=time_str)
                self._render_cards()
            return

        if event.worker.name == "card_summaries" and event.state == WorkerState.ERROR:
            return

        if event.worker.name == "live_fetch" and event.state == WorkerState.SUCCESS:
            result = event.worker.result
            if result:
                projects, prs_map = result
                if projects:
                    self.app.store.set_projects(projects, prs=prs_map)
                    self._render_cards()
                    status_bar = self.query_one(StatusBar)
                    total_prs = sum(len(prs) for prs in prs_map.values())
                    status_bar.set_message(
                        f"Loaded {len(projects)} projects, {total_prs} open PRs"
                    )
                    self.set_timer(3, lambda: status_bar.set_message(""))
                    self._start_polling()
                    self._start_card_summaries()
                    return
            scroll = self.query_one("#cards-scroll", VerticalScroll)
            scroll.remove_children()
            self._cards = []
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
            scroll = self.query_one("#cards-scroll", VerticalScroll)
            scroll.remove_children()
            self._cards = []
            scroll.mount(Static(
                "[yellow]Could not connect to GitHub.[/yellow]\n"
                "Press [bold][r][/bold] to retry.",
                classes="empty-state",
            ))
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("Failed to fetch GitHub data")
            self.set_timer(3, lambda: status_bar.set_message(""))
            return


# Keep these importable for backward compatibility (used by tests)
def _has_credentials() -> bool:
    from pm.tui.store import _has_credentials as _hc
    return _hc()


def _fetch_live_projects_and_prs():
    from pm.tui.store import _fetch_live_projects_and_prs as _flp
    return _flp()
