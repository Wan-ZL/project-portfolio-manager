from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Static, Footer, Input, Label

from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


class TaskScreen(Screen):
    """Task view with live agent terminal output"""

    DEFAULT_CSS = """
    TaskScreen {
        layout: vertical;
    }

    #task-title {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $primary-background-darken-1;
        color: $primary-lighten-2;
        text-style: bold;
        border-bottom: solid $primary 40%;
        padding: 0 2;
    }

    #task-body {
        layout: horizontal;
        height: 1fr;
    }

    #task-info-panel {
        width: 25%;
        min-width: 24;
        border-right: solid $primary 30%;
        background: $surface-darken-1;
        padding: 1 1;
    }

    .info-label {
        color: $text-muted;
        height: 1;
    }

    .info-value {
        color: $text;
        height: 1;
        padding: 0 0 0 1;
    }

    .info-section-header {
        color: $primary;
        text-style: bold;
        height: 2;
        padding: 1 0 0 0;
    }

    #task-terminal-panel {
        width: 75%;
        background: #0c0c0c;
        padding: 0;
    }

    #terminal-scroll {
        width: 100%;
        height: 100%;
    }

    #terminal-output {
        width: 100%;
        padding: 0 1;
        background: #0c0c0c;
        color: #cccccc;
    }

    #reprompt-container {
        dock: bottom;
        height: auto;
        max-height: 5;
        background: $surface-darken-2;
        padding: 0 1;
        display: none;
    }

    #reprompt-container.visible {
        display: block;
    }

    #reprompt-input {
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
        Binding("p", "pause_session", "Pause"),
        Binding("k", "kill_session", "Kill"),
        Binding("r", "reprompt", "Reprompt"),
        Binding("ctrl+q", "detach_session", "Detach"),
    ]

    class GoBack(Message):
        pass

    def __init__(self, session: SessionInfo, project: Optional[ProjectInfo] = None,
                 terminal_output: str = "", **kwargs):
        super().__init__(**kwargs)
        self._session = session
        self._project = project
        self._terminal_output = terminal_output
        self._reprompt_visible = False
        self._poll_timer = None
        self._reaction_status: dict[str, dict] = {}

    def compose(self) -> ComposeResult:
        status_label = self._session.status
        project_name = self._project.name if self._project else self._session.project
        yield Static(
            f"[bold]PPM > {project_name} > {self._session.task}[/bold]  "
            f"[dim]\u2502[/dim]  [{self._status_color}]{status_label}[/{self._status_color}]",
            id="task-title",
        )
        with Horizontal(id="task-body"):
            with Container(id="task-info-panel"):
                yield Static("[bold]Session Info[/bold]", classes="info-section-header")
                yield Static("[dim]Task:[/dim]", classes="info-label")
                yield Static(f"  {self._session.task}", classes="info-value")
                yield Static("[dim]Agent:[/dim]", classes="info-label")
                yield Static(f"  {self._session.agent}", classes="info-value")
                yield Static("[dim]Status:[/dim]", classes="info-label")
                yield Static(
                    f"  [{self._status_color}]{self._session.status}[/{self._status_color}]",
                    id="status-value",
                    classes="info-value",
                )
                yield Static("[dim]Branch:[/dim]", classes="info-label")
                yield Static(f"  {self._session.branch or 'n/a'}", classes="info-value")
                yield Static("[dim]Created:[/dim]", classes="info-label")
                yield Static(
                    f"  {self._session.created_at.strftime('%m/%d %H:%M')}",
                    classes="info-value",
                )
                # PR Status section
                yield Static("[bold]PR Status[/bold]", classes="info-section-header")
                pr_text = f"  #{self._session.pr_number}" if self._session.pr_number else "  none"
                yield Static("[dim]PR:[/dim]", classes="info-label")
                yield Static(pr_text, id="pr-value", classes="info-value")
                # Reaction status section
                yield Static("[bold]Reactions[/bold]", classes="info-section-header")
                yield Static(self._format_reaction_status(), id="reaction-status", classes="info-value")
            with Container(id="task-terminal-panel"):
                with VerticalScroll(id="terminal-scroll"):
                    yield Static(
                        self._terminal_output or "[dim]Waiting for output...[/dim]",
                        id="terminal-output",
                    )
        with Container(id="reprompt-container"):
            yield Label("[bold cyan]Reprompt:[/bold cyan] Send new instruction to agent")
            yield Input(placeholder="Enter new instruction...", id="reprompt-input")
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.set_message(
            "[bold cyan]Esc[/bold cyan] Back  "
            "[bold cyan]p[/bold cyan] Pause  "
            "[bold cyan]k[/bold cyan] Kill  "
            "[bold cyan]r[/bold cyan] Reprompt  "
            "[bold cyan]Ctrl+Q[/bold cyan] Detach"
        )

    def _format_reaction_status(self) -> str:
        """Format reaction status for display."""
        if not self._session.pr_number:
            return "  [dim]No PR — reactions inactive[/dim]"
        lines = []
        for key in ["ci-failed", "changes-requested", "approved-and-green"]:
            info = self._reaction_status.get(key)
            if info:
                count = info.get("attempt_count", 0)
                escalated = info.get("escalated", False)
                if escalated:
                    lines.append(f"  [red]{key}: escalated[/red]")
                elif count > 0:
                    lines.append(f"  [yellow]{key}: {count} retries[/yellow]")
                else:
                    lines.append(f"  [dim]{key}: 0 retries[/dim]")
            else:
                lines.append(f"  [dim]{key}: 0 retries[/dim]")
        return "\n".join(lines) if lines else "  [dim]No reaction data[/dim]"

    def update_reaction_status(self, status: dict[str, dict]) -> None:
        """Update the reaction status display."""
        self._reaction_status = status
        try:
            self.query_one("#reaction-status", Static).update(self._format_reaction_status())
        except Exception:
            pass

    @property
    def _status_color(self) -> str:
        return {
            "running": "green",
            "paused": "yellow",
            "completed": "cyan",
            "failed": "red",
            "exited": "dim",
        }.get(self._session.status, "dim")

    def update_terminal(self, output: str) -> None:
        """Update the terminal output display."""
        self._terminal_output = output
        try:
            self.query_one("#terminal-output", Static).update(output)
            scroll = self.query_one("#terminal-scroll", VerticalScroll)
            scroll.scroll_end(animate=False)
        except Exception:
            pass

    def update_status(self, status: str) -> None:
        """Update the session status display."""
        self._session = SessionInfo(
            id=self._session.id,
            project=self._session.project,
            task=self._session.task,
            agent=self._session.agent,
            status=status,
            created_at=self._session.created_at,
            branch=self._session.branch,
            pr_number=self._session.pr_number,
        )
        try:
            color = self._status_color
            self.query_one("#status-value", Static).update(f"  [{color}]{status}[/{color}]")
        except Exception:
            pass

    def action_go_back(self) -> None:
        if self._reprompt_visible:
            self._hide_reprompt()
            return
        self.app.pop_screen()

    def action_pause_session(self) -> None:
        status_bar = self.query_one(StatusBar)
        if self._session.status == "running":
            self.update_status("paused")
            status_bar.set_message("Session paused")
        elif self._session.status == "paused":
            self.update_status("running")
            status_bar.set_message("Session resumed")

    def action_kill_session(self) -> None:
        self.update_status("completed")
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Session killed")

    def action_reprompt(self) -> None:
        self._show_reprompt()

    def action_detach_session(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Detached from session (agent still running)")
        self.set_timer(1, lambda: self.app.pop_screen())

    def _show_reprompt(self) -> None:
        self._reprompt_visible = True
        container = self.query_one("#reprompt-container")
        container.add_class("visible")
        try:
            self.query_one("#reprompt-input", Input).focus()
        except Exception:
            pass

    def _hide_reprompt(self) -> None:
        self._reprompt_visible = False
        container = self.query_one("#reprompt-container")
        container.remove_class("visible")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "reprompt-input":
            text = event.value.strip()
            if text:
                status_bar = self.query_one(StatusBar)
                status_bar.set_message(f"Sent: {text}")
                event.input.value = ""
                self._hide_reprompt()

    @property
    def session(self) -> SessionInfo:
        return self._session
