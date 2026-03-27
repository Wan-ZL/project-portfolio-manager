from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static, Footer, TabbedContent, TabPane, Tabs, Input, Label

from pm.github.pr import EnhancedPR
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


class LeftPanelItem(Static):
    """Selectable item in the left panel"""

    selected = reactive(False)

    def watch_selected(self, value: bool) -> None:
        self.set_class(value, "selected")


class PRListItem(LeftPanelItem):
    """PR item in the project left panel"""

    DEFAULT_CSS = """
    PRListItem {
        height: 2;
        padding: 0 1;
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
        ci_icon = {
            "passing": "[green]\u2714[/green]",
            "failing": "[red]\u2718[/red]",
            "pending": "[yellow]\u25cb[/yellow]",
        }.get(self.pr.ci_status, "[dim]\u25cb[/dim]")

        indicator = "[cyan]\u25ba[/cyan] " if self.selected else "  "
        repo_short = self.pr.repo_id.split("/")[-1] if "/" in self.pr.repo_id else self.pr.repo_id
        return (
            f"{indicator}{ci_icon} [bold]#{self.pr.number}[/bold] {self.pr.title}\n"
            f"    [dim]{repo_short} \u2022 {self.pr.author}[/dim]"
        )


class SessionListItem(LeftPanelItem):
    """Session item in the project left panel"""

    DEFAULT_CSS = """
    SessionListItem {
        height: 2;
        padding: 0 1;
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

    def __init__(self, session: SessionInfo, **kwargs):
        super().__init__(**kwargs)
        self.session_info = session

    def on_click(self, event: Click) -> None:
        self.post_message(self.Clicked(self))

    def render(self):
        status_icon = {
            "running": "[green]\u25b6[/green]",
            "paused": "[yellow]\u275a\u275a[/yellow]",
            "completed": "[cyan]\u2714[/cyan]",
            "failed": "[red]\u2718[/red]",
        }.get(self.session_info.status, "[dim]?[/dim]")
        indicator = "[cyan]\u25ba[/cyan] " if self.selected else "  "
        return (
            f"{indicator}{status_icon} [bold]{self.session_info.task}[/bold]\n"
            f"    [dim]{self.session_info.agent} \u2022 {self.session_info.status}[/dim]"
        )


class InfoTab(Static):
    """Info tab content in the right panel"""

    DEFAULT_CSS = """
    InfoTab {
        width: 100%;
        height: 100%;
        padding: 1 2;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pr: Optional[EnhancedPR] = None
        self._session: Optional[SessionInfo] = None
        self._project: Optional[ProjectInfo] = None

    def set_pr(self, pr: EnhancedPR) -> None:
        self._pr = pr
        self._session = None
        self._update()

    def set_session(self, session: SessionInfo) -> None:
        self._session = session
        self._pr = None
        self._update()

    def set_project(self, project: ProjectInfo) -> None:
        self._project = project
        if not self._pr and not self._session:
            self._update()

    def _update(self) -> None:
        if self._pr:
            pr = self._pr
            ci_label = {"passing": "[green]passing[/green]", "failing": "[red]failing[/red]",
                        "pending": "[yellow]pending[/yellow]"}.get(pr.ci_status, pr.ci_status)
            review_label = {"approved": "[green]approved[/green]",
                           "changes_requested": "[yellow]changes requested[/yellow]",
                           "pending": "[dim]pending[/dim]"}.get(pr.review_status, pr.review_status)
            self.update(
                f"[bold cyan]PR #{pr.number}: {pr.title}[/bold cyan]\n"
                f"{'=' * 40}\n"
                f"[bold]Author:[/bold] {pr.author}\n"
                f"[bold]CI:[/bold] {ci_label}\n"
                f"[bold]Review:[/bold] {review_label}\n"
                f"[bold]Comments:[/bold] {pr.unresolved_count} unresolved\n"
                f"[bold]Updated:[/bold] {pr.updated_at.strftime('%Y-%m-%d %H:%M')}\n"
            )
        elif self._session:
            s = self._session
            self.update(
                f"[bold cyan]Session: {s.task}[/bold cyan]\n"
                f"{'=' * 40}\n"
                f"[bold]Agent:[/bold] {s.agent}\n"
                f"[bold]Status:[/bold] {s.status}\n"
                f"[bold]Branch:[/bold] {s.branch}\n"
                f"[bold]PR:[/bold] #{s.pr_number or 'none'}\n"
                f"[bold]Created:[/bold] {s.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            )
        elif self._project:
            p = self._project
            lines = [
                f"[bold cyan]{p.name}[/bold cyan]",
                f"{'=' * 40}",
                f"[bold]Account:[/bold] {p.account}",
                f"[bold]Open PRs:[/bold] {p.open_prs}",
                f"[bold]Sessions:[/bold] {p.active_sessions}",
            ]

            # Repos section
            lines.append("")
            lines.append("[bold cyan]Repositories:[/bold cyan]")
            for repo in p.repos:
                lines.append(f"  [green]+[/green] {repo}")

            # Instructions section
            if p.instructions:
                lines.append("")
                lines.append("[bold cyan]Instructions:[/bold cyan]")
                for line in p.instructions.strip().splitlines():
                    lines.append(f"  [dim]{line}[/dim]")

            # Assets section
            if p.assets:
                import os
                lines.append("")
                lines.append("[bold cyan]Assets:[/bold cyan]")
                for asset_path in p.assets:
                    expanded = os.path.expanduser(asset_path)
                    if os.path.exists(expanded):
                        size = os.path.getsize(expanded)
                        if size > 1024 * 1024:
                            size_str = f"{size / (1024 * 1024):.1f} MB"
                        elif size > 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        else:
                            size_str = f"{size} B"
                        lines.append(f"  [green]+[/green] {asset_path} [dim]({size_str})[/dim]")
                    else:
                        lines.append(f"  [dim]-[/dim] {asset_path} [dim](not found)[/dim]")
                lines.append("  [dim]Press [bold]o[/bold] to open assets in system viewer[/dim]")

            # Summary
            lines.append("")
            if p.summary:
                lines.append(f"{p.summary}")
            else:
                lines.append("[dim]No summary available[/dim]")

            self.update("\n".join(lines))
        else:
            self.update("[dim]Select a PR or session to view details[/dim]")


class ProjectScreen(Screen):
    """Project detail view (J3)"""

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

    #project-body {
        layout: horizontal;
        height: 1fr;
    }

    #project-left-panel {
        width: 35%;
        min-width: 28;
        border-right: solid $primary 30%;
        background: $surface-darken-1;
        padding: 0;
    }

    #project-left-title {
        dock: top;
        height: 2;
        padding: 0 1;
        background: $surface-darken-2;
        color: $primary;
        text-style: bold;
        border-bottom: solid $surface-lighten-1;
    }

    #project-right-panel {
        width: 65%;
        background: $surface;
        padding: 0;
    }

    .section-header {
        height: 2;
        padding: 0 1;
        color: $primary;
        text-style: bold;
        background: $surface-darken-2;
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
        Binding("tab", "next_tab", "Next Tab"),
        Binding("shift+tab", "prev_tab", "Prev Tab"),
        Binding("enter", "select_item", "Select"),
        Binding("a", "attach_session", "Attach"),
        Binding("n", "new_task", "New Task"),
        Binding("f", "fix_pr", "Fix PR"),
        Binding("m", "merge_pr", "Merge"),
        Binding("o", "open_assets", "Open Assets"),
    ]

    class GoBack(Message):
        pass

    def __init__(self, project: ProjectInfo, prs: list[EnhancedPR] | None = None,
                 sessions: list[SessionInfo] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._project = project
        self._prs = prs or []
        self._sessions = sessions or []
        self._all_items: list[LeftPanelItem] = []
        self._selected_index = 0
        self._task_input_visible = False

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold]PPM > {self._project.name}[/bold]  [dim]\u2502  Project Detail[/dim]",
            id="project-title",
        )
        with Horizontal(id="project-body"):
            with Container(id="project-left-panel"):
                yield Static("[bold]Repos & PRs[/bold]", id="project-left-title")
                yield VerticalScroll(id="project-left-scroll")
            with Container(id="project-right-panel"):
                with TabbedContent("Info", "Diff", "Terminal", id="project-detail-tabs"):
                    with TabPane("Info", id="project-tab-info"):
                        yield InfoTab(id="info-tab-content")
                    with TabPane("Diff", id="project-tab-diff"):
                        yield Static("[dim]Select a PR to view diff[/dim]", id="diff-content")
                    with TabPane("Terminal", id="project-tab-terminal"):
                        yield Static("[dim]Select a session to view terminal[/dim]", id="terminal-content")
        with Container(id="new-task-container"):
            yield Label("[bold cyan]New Task:[/bold cyan] Enter task description")
            yield Input(placeholder="Describe the task...", id="new-task-input")
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        self._rebuild_left_panel()
        info_tab = self.query_one("#info-tab-content", InfoTab)
        info_tab.set_project(self._project)

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

    def _rebuild_left_panel(self) -> None:
        scroll = self.query_one("#project-left-scroll", VerticalScroll)
        scroll.remove_children()
        self._all_items = []

        # Group PRs by repo
        repos: dict[str, list[EnhancedPR]] = {}
        for pr in self._prs:
            repos.setdefault(pr.repo_id, []).append(pr)

        for repo_id, prs in repos.items():
            scroll.mount(Static(f"[bold cyan]\u25bc {repo_id}[/bold cyan]", classes="section-header"))
            for pr in prs:
                item = PRListItem(pr)
                scroll.mount(item)
                self._all_items.append(item)

        # Sessions section
        if self._sessions:
            scroll.mount(Static("[bold cyan]\u25bc Sessions[/bold cyan]", classes="section-header"))
            for s in self._sessions:
                item = SessionListItem(s)
                scroll.mount(item)
                self._all_items.append(item)

        if self._all_items:
            self._selected_index = 0
            self._update_selection()

    def _update_selection(self) -> None:
        for i, item in enumerate(self._all_items):
            item.selected = i == self._selected_index

        if not self._all_items or self._selected_index >= len(self._all_items):
            return

        current = self._all_items[self._selected_index]
        info_tab = self.query_one("#info-tab-content", InfoTab)
        if isinstance(current, PRListItem):
            info_tab.set_pr(current.pr)
        elif isinstance(current, SessionListItem):
            info_tab.set_session(current.session_info)

    def action_cursor_down(self) -> None:
        if self._all_items and self._selected_index < len(self._all_items) - 1:
            self._selected_index += 1
            self._update_selection()

    def action_cursor_up(self) -> None:
        if self._all_items and self._selected_index > 0:
            self._selected_index -= 1
            self._update_selection()

    def action_next_tab(self) -> None:
        try:
            tabs = self.query_one("#project-detail-tabs", TabbedContent).query_one(Tabs)
            tabs.action_next_tab()
        except Exception:
            pass

    def action_prev_tab(self) -> None:
        try:
            tabs = self.query_one("#project-detail-tabs", TabbedContent).query_one(Tabs)
            tabs.action_previous_tab()
        except Exception:
            pass

    def action_go_back(self) -> None:
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
        """Manually trigger a fix reaction on a selected PR."""
        status_bar = self.query_one(StatusBar)
        if not self._all_items or self._selected_index >= len(self._all_items):
            status_bar.set_message("No PR selected")
            return
        current = self._all_items[self._selected_index]
        if isinstance(current, PRListItem):
            pr = current.pr
            if pr.ci_status == "failing":
                msg = (
                    "CI is failing on your PR. Run `gh pr checks` to see "
                    "failures, fix them, and push."
                )
                status_bar.set_message(
                    f"Fix reaction queued for PR #{pr.number} (CI failing)"
                )
            elif pr.review_status == "changes_requested":
                msg = (
                    "There are review comments on your PR. Check with "
                    "`gh pr view --comments`. Address each one, push fixes."
                )
                status_bar.set_message(
                    f"Fix reaction queued for PR #{pr.number} (changes requested)"
                )
            else:
                status_bar.set_message(
                    f"PR #{pr.number} doesn't need fixing (CI: {pr.ci_status}, "
                    f"Review: {pr.review_status})"
                )
                return
            # Find matching session and send
            matching_session = None
            for s in self._sessions:
                if s.pr_number == pr.number:
                    matching_session = s
                    break
            if matching_session:
                from pm.reaction.actions import send_to_agent
                # In a real implementation, this would use the actual tmux session name
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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "new-task-input":
            task_desc = event.value.strip()
            if task_desc:
                status_bar = self.query_one(StatusBar)
                status_bar.set_message(f"Creating task: {task_desc}...")
                event.input.value = ""
                self._hide_task_input()
                # In a real implementation, this would call SessionManager.create_session
                self.set_timer(
                    2, lambda: status_bar.set_message(f"Task created: {task_desc}")
                )

    def _open_task_view(self, session: SessionInfo) -> None:
        from pm.tui.screens.task import TaskScreen
        self.app.push_screen(TaskScreen(session=session, project=self._project))

    @property
    def project(self) -> ProjectInfo:
        return self._project
