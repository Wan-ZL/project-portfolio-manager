from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static, Footer, Input, Label

from pm.github.pr import EnhancedPR
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


def _time_ago(dt: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}hr ago"
    days = hours // 24
    return f"{days}d ago"


def _build_welcome_back(
    project_name: str,
    sessions: list[SessionInfo],
    prs: list[EnhancedPR],
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now()
    result: dict = {"last_action": "", "while_away": "", "suggestion": ""}

    # Last action: find the most recent session
    if sessions:
        latest = max(sessions, key=lambda s: s.created_at)
        ago = _time_ago(latest.created_at, now)
        status_verb = {
            "running": "Agent running",
            "completed": "Agent completed",
            "paused": "Agent paused",
            "failed": "Agent failed",
        }.get(latest.status, latest.status)
        result["last_action"] = (
            f"Last session ({ago}): sent \"{latest.task}\" -> {status_verb}"
        )

    # While away: check PR events
    away_items = []
    review_prs = [p for p in prs if p.review_status == "changes_requested"]
    if review_prs:
        total_comments = sum(p.unresolved_count for p in review_prs)
        pr_nums = ", ".join(f"#{p.number}" for p in review_prs)
        away_items.append(
            f"PR {pr_nums} received {total_comments} review comment(s)"
        )

    failing_prs = [p for p in prs if p.ci_status == "failing"]
    if failing_prs:
        pr_nums = ", ".join(f"#{p.number}" for p in failing_prs)
        away_items.append(f"CI failing on PR {pr_nums}")

    approved_prs = [
        p for p in prs
        if p.ci_status == "passing" and p.review_status == "approved"
    ]
    if approved_prs:
        pr_nums = ", ".join(f"#{p.number}" for p in approved_prs)
        away_items.append(f"PR {pr_nums} approved and ready to merge")

    result["while_away"] = "; ".join(away_items) if away_items else "No new events"

    # Suggestion
    if failing_prs:
        pr = failing_prs[0]
        result["suggestion"] = f"Fix CI on PR #{pr.number}"
    elif review_prs:
        pr = review_prs[0]
        result["suggestion"] = f"Address review comments on PR #{pr.number}"
    elif approved_prs:
        pr = approved_prs[0]
        result["suggestion"] = f"Merge PR #{pr.number} (approved + CI passing)"
    else:
        result["suggestion"] = "All clear! Start a new task."

    return result


def _build_activity_timeline(
    sessions: list[SessionInfo],
    prs: list[EnhancedPR],
    now: datetime | None = None,
    limit: int = 10,
) -> list[dict]:
    now = now or datetime.now()
    events: list[dict] = []

    for s in sessions:
        events.append({
            "time": s.created_at,
            "actor": "You",
            "action": f"sent task \"{s.task}\"",
            "type": "session",
        })
        if s.pr_number:
            events.append({
                "time": s.created_at + timedelta(minutes=5),
                "actor": "Agent",
                "action": f"created PR #{s.pr_number}",
                "type": "agent",
            })

    for pr in prs:
        if pr.ci_status == "failing":
            events.append({
                "time": pr.updated_at,
                "actor": "CI",
                "action": f"PR #{pr.number} failing",
                "type": "ci",
            })
        if pr.review_status == "changes_requested":
            events.append({
                "time": pr.updated_at,
                "actor": "Reviewer",
                "action": f"{pr.unresolved_count} comment(s) on PR #{pr.number}",
                "type": "review",
            })
        if pr.review_status == "approved":
            events.append({
                "time": pr.updated_at,
                "actor": "Reviewer",
                "action": f"approved PR #{pr.number}",
                "type": "review",
            })

    events.sort(key=lambda e: e["time"], reverse=True)
    return events[:limit]


class SelectableItem(Static):
    """Base selectable item in the scrollable view"""

    selected = reactive(False)

    def watch_selected(self, value: bool) -> None:
        self.set_class(value, "selected")


class PRListItem(SelectableItem):
    """PR item in the project view"""

    DEFAULT_CSS = """
    PRListItem {
        height: auto;
        min-height: 3;
        padding: 0 2;
    }
    PRListItem.selected {
        background: $accent 30%;
    }
    PRListItem:hover {
        background: $surface-lighten-1;
    }
    """

    class Clicked(Message):
        def __init__(self, item: PRListItem):
            super().__init__()
            self.item = item

    def __init__(self, pr: EnhancedPR, **kwargs):
        super().__init__(**kwargs)
        self.pr = pr

    def on_click(self, event: Click) -> None:
        self.post_message(self.Clicked(self))

    def render(self):
        ci_map = {
            "passing": ("[green]\u2714[/green]", "[green]passing[/green]"),
            "failing": ("[red]\u2718[/red]", "[red]failing[/red]"),
            "pending": ("[yellow]\u25cb[/yellow]", "[yellow]pending[/yellow]"),
        }
        ci_icon, ci_label = ci_map.get(self.pr.ci_status, ("[dim]\u25cb[/dim]", self.pr.ci_status))

        review_map = {
            "approved": "[green]approved[/green]",
            "changes_requested": "[yellow]changes_requested[/yellow]",
            "pending": "[dim]pending[/dim]",
        }
        review_label = review_map.get(self.pr.review_status, self.pr.review_status)

        status_icon = {
            "passing": "\U0001f7e2",
            "failing": "\U0001f534",
            "pending": "\U0001f7e1",
        }.get(self.pr.ci_status, "\u25cb")

        indicator = "[cyan]\u25ba[/cyan] " if self.selected else "  "
        repo_short = self.pr.repo_id.split("/")[-1] if "/" in self.pr.repo_id else self.pr.repo_id

        ready = ""
        if self.pr.ci_status == "passing" and self.pr.review_status == "approved":
            ready = "  [bold green]Ready to merge \u2713[/bold green]"

        comments_line = ""
        if self.pr.unresolved_count > 0:
            comments_line = f"\n   [dim]\U0001f4ac {self.pr.unresolved_count} unresolved comment(s)[/dim]"

        return (
            f"{indicator}{status_icon} [bold]PR #{self.pr.number}[/bold]  {self.pr.title}"
            f"    [dim]{repo_short}[/dim]\n"
            f"   CI: {ci_label}  |  Review: {review_label}{ready}"
            f"{comments_line}"
        )


class SessionListItem(SelectableItem):
    """Session item in the project view"""

    DEFAULT_CSS = """
    SessionListItem {
        height: 2;
        padding: 0 2;
    }
    SessionListItem.selected {
        background: $accent 30%;
    }
    SessionListItem:hover {
        background: $surface-lighten-1;
    }
    """

    class Clicked(Message):
        def __init__(self, item: SessionListItem):
            super().__init__()
            self.item = item

    def __init__(self, session: SessionInfo, now: datetime | None = None, **kwargs):
        super().__init__(**kwargs)
        self.session_info = session
        self._now = now

    def on_click(self, event: Click) -> None:
        self.post_message(self.Clicked(self))

    def render(self):
        status_icon = {
            "running": "\U0001f7e2",
            "paused": "\u23f8",
            "completed": "[cyan]\u2714[/cyan]",
            "failed": "[red]\u2718[/red]",
            "recovered": "[bold magenta]\u21bb[/bold magenta]",
            "lost": "[red]\u2620[/red]",
        }.get(self.session_info.status, "[dim]?[/dim]")
        indicator = "[cyan]\u25ba[/cyan] " if self.selected else "  "
        duration = _time_ago(self.session_info.created_at, self._now)
        branch = f"  branch: {self.session_info.branch}" if self.session_info.branch else ""
        return (
            f"{indicator}{status_icon} [bold]{self.session_info.task}[/bold]"
            f"  [dim]({self.session_info.status}, {duration})[/dim]"
            f"{branch}  [dim]{self.session_info.agent}[/dim]"
        )


class WelcomeBackSection(Static):
    """Welcome Back collapsible section"""

    DEFAULT_CSS = """
    WelcomeBackSection {
        height: auto;
        padding: 1 2;
        margin: 1 2 0 2;
        border: round $primary 60%;
        background: $surface-darken-1;
    }
    WelcomeBackSection.dismissed {
        display: none;
    }
    """

    def __init__(self, welcome_data: dict, **kwargs):
        super().__init__(**kwargs)
        self._data = welcome_data

    def render(self):
        lines = ["[bold cyan]Welcome Back[/bold cyan]"]
        if self._data.get("last_action"):
            lines.append(f"  {self._data['last_action']}")
        if self._data.get("while_away"):
            lines.append(f"  While away: {self._data['while_away']}")
        if self._data.get("suggestion"):
            lines.append(f"  \U0001f4a1 Suggestion: {self._data['suggestion']}")
        return "\n".join(lines)


class ActivityTimeline(Static):
    """Activity timeline section"""

    DEFAULT_CSS = """
    ActivityTimeline {
        height: auto;
        padding: 1 2;
    }
    """

    def __init__(self, events: list[dict], now: datetime | None = None, **kwargs):
        super().__init__(**kwargs)
        self._events = events
        self._now = now

    def render(self):
        if not self._events:
            return "[dim]No recent activity[/dim]"

        lines = []
        for event in self._events:
            ago = _time_ago(event["time"], self._now)
            actor = event["actor"]
            action = event["action"]

            actor_style = {
                "You": "[bold cyan]",
                "Agent": "[bold green]",
                "CI": "[bold red]",
                "Reviewer": "[bold yellow]",
            }.get(actor, "[dim]")
            close_style = actor_style.replace("[", "[/")

            lines.append(
                f"  [dim]{ago:<12}[/dim] {actor_style}{actor}{close_style}: {action}"
            )
        return "\n".join(lines)


class SectionHeader(Static):
    """Section header with title and optional count"""

    DEFAULT_CSS = """
    SectionHeader {
        height: 2;
        padding: 0 2;
        color: $primary;
        text-style: bold;
        border-bottom: solid $primary 30%;
        margin: 1 0 0 0;
    }
    """


class ProjectScreen(Screen):
    """Project detail view - single scrollable page with sections"""

    CSS_PATH = str(Path(__file__).parent.parent / "styles" / "project.tcss")

    DEFAULT_CSS = """
    ProjectScreen {
        layout: vertical;
    }

    #project-title {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $primary-background-darken-1;
        color: $primary-lighten-2;
        text-style: bold;
        border-bottom: solid $primary 40%;
        padding: 0 2;
    }

    #project-scroll {
        height: 1fr;
    }

    #instructions-section {
        height: auto;
        padding: 1 2;
        margin: 0 2;
        background: $surface-darken-1;
    }

    #new-task-container {
        dock: bottom;
        height: auto;
        max-height: 5;
        background: $surface-darken-2;
        padding: 0 1;
        display: none;
    }

    #new-task-container.visible {
        display: block;
    }

    #new-task-input {
        width: 100%;
    }

    #search-container {
        dock: bottom;
        height: auto;
        max-height: 3;
        background: $surface-darken-2;
        padding: 0 1;
        display: none;
    }

    #search-container.visible {
        display: block;
    }

    #search-input {
        width: 100%;
    }

    #search-results-count {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        display: none;
    }

    #search-results-count.visible {
        display: block;
    }

    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-background-darken-2;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("enter", "select_item", "Select"),
        Binding("a", "attach_session", "Attach"),
        Binding("n", "new_task", "New Task"),
        Binding("f", "fix_pr", "Fix PR"),
        Binding("m", "merge_pr", "Merge"),
        Binding("o", "open_assets", "Open Assets"),
        Binding("d", "dismiss_welcome", "Dismiss Welcome", show=False),
        Binding("slash", "search_sessions", "Search", show=True),
    ]

    class GoBack(Message):
        pass

    def __init__(self, project_name: str = "", project: ProjectInfo | None = None,
                 prs: list[EnhancedPR] | None = None,
                 sessions: list[SessionInfo] | None = None, now: datetime | None = None,
                 **kwargs):
        super().__init__(**kwargs)
        self._project_name = project_name or (project.name if project else "")
        self._project = project
        self._prs = prs
        self._sessions = sessions
        self._now = now
        self._all_items: list[SelectableItem] = []
        self._selected_index = 0
        self._task_input_visible = False
        self._search_visible = False
        self._search_query = ""

    def _resolve_data(self) -> None:
        if self._project is None:
            try:
                pd = self.app.store.get_project(self._project_name)
                if pd:
                    self._project = pd.info
                    if self._prs is None:
                        self._prs = pd.prs
                    if self._sessions is None:
                        self._sessions = pd.sessions
            except Exception:
                pass
        if self._project is None:
            self._project = ProjectInfo(name=self._project_name, account="")
        if self._prs is None:
            self._prs = []
        if self._sessions is None:
            self._sessions = []

    def compose(self) -> ComposeResult:
        self._resolve_data()

        yield Static(
            f"[bold]PPM > {self._project.name}[/bold]",
            id="project-title",
        )
        with VerticalScroll(id="project-scroll"):
            welcome_data = _build_welcome_back(
                self._project.name, self._sessions, self._prs, self._now,
            )
            yield WelcomeBackSection(welcome_data, id="welcome-back")

            open_prs = [p for p in self._prs if p.state == "open"]
            yield SectionHeader(
                f"Pull Requests ({len(open_prs)} open)",
                id="pr-section-header",
            )
            for pr in self._prs:
                yield PRListItem(pr)

            yield SectionHeader(
                f"Agent Sessions ({len(self._sessions)})",
                id="sessions-section-header",
            )
            if self._sessions:
                for s in self._sessions:
                    yield SessionListItem(s, now=self._now)
            else:
                yield Static(
                    "  [dim]No active sessions[/dim]",
                    classes="empty-state",
                )

            yield SectionHeader("Recent Activity", id="activity-section-header")
            events = _build_activity_timeline(
                self._sessions, self._prs, self._now,
            )
            yield ActivityTimeline(events, now=self._now, id="activity-timeline")

            if self._project.instructions:
                yield SectionHeader("Instructions", id="instructions-header")
                yield Static(
                    f"  [dim]{self._project.instructions}[/dim]",
                    id="instructions-section",
                )

        with Container(id="search-container"):
            yield Label("[bold cyan]/[/bold cyan] Search sessions")
            yield Input(placeholder="Search sessions...", id="search-input")
        yield Static("", id="search-results-count")
        with Container(id="new-task-container"):
            yield Label("[bold cyan]New Task:[/bold cyan] Enter task description")
            yield Input(placeholder="Describe the task...", id="new-task-input")
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        self._all_items = list(self.query(PRListItem)) + list(self.query(SessionListItem))
        if self._all_items:
            self._selected_index = 0
            self._update_selection()

    def on_pr_list_item_clicked(self, event: PRListItem.Clicked) -> None:
        try:
            idx = self._all_items.index(event.item)
            self._selected_index = idx
            self._update_selection()
        except ValueError:
            pass

    def on_session_list_item_clicked(self, event: SessionListItem.Clicked) -> None:
        try:
            idx = self._all_items.index(event.item)
            self._selected_index = idx
            self._update_selection()
        except ValueError:
            pass

    def _update_selection(self) -> None:
        for i, item in enumerate(self._all_items):
            item.selected = i == self._selected_index

    def action_cursor_down(self) -> None:
        if self._all_items and self._selected_index < len(self._all_items) - 1:
            self._selected_index += 1
            self._update_selection()

    def action_cursor_up(self) -> None:
        if self._all_items and self._selected_index > 0:
            self._selected_index -= 1
            self._update_selection()

    def action_go_back(self) -> None:
        if self._search_visible:
            self._hide_search()
            return
        if self._task_input_visible:
            self._hide_task_input()
            return
        self.app.pop_screen()

    def action_select_item(self) -> None:
        if not self._all_items or self._selected_index >= len(self._all_items):
            return
        current = self._all_items[self._selected_index]
        if isinstance(current, SessionListItem):
            self._open_task_view(current.session_info)

    def action_attach_session(self) -> None:
        if not self._all_items or self._selected_index >= len(self._all_items):
            return
        current = self._all_items[self._selected_index]
        if isinstance(current, SessionListItem):
            self._open_task_view(current.session_info)

    def action_new_task(self) -> None:
        self._show_task_input()

    def action_fix_pr(self) -> None:
        status_bar = self.query_one(StatusBar)
        if not self._all_items or self._selected_index >= len(self._all_items):
            status_bar.set_message("No PR selected")
            return
        current = self._all_items[self._selected_index]
        if isinstance(current, PRListItem):
            pr = current.pr
            if pr.ci_status == "failing":
                status_bar.set_message(
                    f"Fix reaction queued for PR #{pr.number} (CI failing)"
                )
            elif pr.review_status == "changes_requested":
                status_bar.set_message(
                    f"Fix reaction queued for PR #{pr.number} (changes requested)"
                )
            else:
                status_bar.set_message(
                    f"PR #{pr.number} doesn't need fixing (CI: {pr.ci_status}, "
                    f"Review: {pr.review_status})"
                )
                return
            matching_session = None
            for s in self._sessions:
                if s.pr_number == pr.number:
                    matching_session = s
                    break
            if matching_session:
                from pm.reaction.actions import send_to_agent
                if pr.ci_status == "failing":
                    fix_msg = (
                        "CI is failing on your PR. Run `gh pr checks` to see "
                        "failures, fix them, and push."
                    )
                else:
                    fix_msg = (
                        "There are review comments on your PR. Check with "
                        "`gh pr view --comments`. Address each one, push fixes."
                    )
                send_to_agent(matching_session.tmux_session or "", fix_msg)
                status_bar.set_message(
                    f"Sent fix command to session '{matching_session.task}' "
                    f"for PR #{pr.number}"
                )
            else:
                status_bar.set_message(
                    f"No active session found for PR #{pr.number}. "
                    f"Create a new task first."
                )
            self.set_timer(3, lambda: status_bar.set_message(""))
        else:
            status_bar.set_message("Select a PR to trigger fix")

    def action_merge_pr(self) -> None:
        status_bar = self.query_one(StatusBar)
        if not self._all_items or self._selected_index >= len(self._all_items):
            status_bar.set_message("No PR selected")
            return
        current = self._all_items[self._selected_index]
        if isinstance(current, PRListItem):
            status_bar.set_message(f"Merge PR #{current.pr.number} - not yet implemented")
        else:
            status_bar.set_message("Select a PR to merge")

    def action_open_assets(self) -> None:
        status_bar = self.query_one(StatusBar)
        if not self._project.assets:
            status_bar.set_message("No assets configured for this project")
            self.set_timer(3, lambda: status_bar.set_message(""))
            return
        import os
        import subprocess
        import sys
        opened = 0
        for asset_path in self._project.assets:
            expanded = os.path.expanduser(asset_path)
            if os.path.exists(expanded):
                try:
                    if sys.platform == "darwin":
                        subprocess.Popen(["open", expanded], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif sys.platform == "linux":
                        subprocess.Popen(["xdg-open", expanded], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    opened += 1
                except Exception:
                    pass
        if opened:
            status_bar.set_message(f"Opened {opened} asset(s) in system viewer")
        else:
            status_bar.set_message("No existing assets to open")
        self.set_timer(3, lambda: status_bar.set_message(""))

    def action_dismiss_welcome(self) -> None:
        try:
            welcome = self.query_one("#welcome-back", WelcomeBackSection)
            welcome.add_class("dismissed")
        except Exception:
            pass

    def _show_task_input(self) -> None:
        self._task_input_visible = True
        container = self.query_one("#new-task-container")
        container.add_class("visible")
        try:
            self.query_one("#new-task-input", Input).focus()
        except Exception:
            pass

    def _hide_task_input(self) -> None:
        self._task_input_visible = False
        container = self.query_one("#new-task-container")
        container.remove_class("visible")

    def action_search_sessions(self) -> None:
        self._show_search()

    def _show_search(self) -> None:
        self._search_visible = True
        container = self.query_one("#search-container")
        container.add_class("visible")
        try:
            self.query_one("#search-input", Input).focus()
        except Exception:
            pass

    def _hide_search(self) -> None:
        self._search_visible = False
        container = self.query_one("#search-container")
        container.remove_class("visible")
        results_label = self.query_one("#search-results-count", Static)
        results_label.remove_class("visible")
        try:
            self.query_one("#search-input", Input).value = ""
        except Exception:
            pass
        self._restore_all_sessions()

    def _filter_sessions(self, query: str) -> None:
        self._search_query = query
        query_lower = query.lower()
        session_items = list(self.query(SessionListItem))
        visible_count = 0
        for item in session_items:
            info = item.session_info
            searchable = " ".join([
                info.task or "",
                info.agent or "",
                info.branch or "",
                info.status or "",
            ]).lower()
            if query_lower in searchable:
                item.display = True
                visible_count += 1
            else:
                item.display = False

        results_label = self.query_one("#search-results-count", Static)
        results_label.update(f"  [dim]{visible_count} result(s)[/dim]")
        results_label.add_class("visible")

        self._all_items = (
            list(self.query(PRListItem))
            + [s for s in self.query(SessionListItem) if s.display]
        )
        if self._all_items:
            self._selected_index = min(self._selected_index, len(self._all_items) - 1)
        else:
            self._selected_index = 0
        self._update_selection()

    def _restore_all_sessions(self) -> None:
        for item in self.query(SessionListItem):
            item.display = True
        self._all_items = list(self.query(PRListItem)) + list(self.query(SessionListItem))
        if self._all_items:
            self._selected_index = min(self._selected_index, len(self._all_items) - 1)
        self._update_selection()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input" and self._search_visible:
            query = event.value.strip()
            if query:
                self._filter_sessions(query)
            else:
                self._restore_all_sessions()
                results_label = self.query_one("#search-results-count", Static)
                results_label.remove_class("visible")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self._hide_search()
            return
        if event.input.id == "new-task-input":
            task_desc = event.value.strip()
            if task_desc:
                status_bar = self.query_one(StatusBar)
                status_bar.set_message(f"Creating task: {task_desc}...")
                event.input.value = ""
                self._hide_task_input()
                self.set_timer(
                    2, lambda: status_bar.set_message(f"Task created: {task_desc}")
                )

    def _open_task_view(self, session: SessionInfo) -> None:
        from pm.tui.screens.task import TaskScreen
        self.app.push_screen(TaskScreen(session=session, project=self._project))

    @property
    def project(self) -> ProjectInfo:
        return self._project
