from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


@dataclass
class SessionInfo:
    id: str
    project: str
    task: str
    agent: str
    status: str  # running, paused, completed, failed
    created_at: datetime
    branch: str = ""
    pr_number: int | None = None


class SessionItem(Static):
    """A single session item"""

    DEFAULT_CSS = """
    SessionItem {
        height: 2;
        padding: 0 1;
    }
    SessionItem:hover {
        background: $surface-lighten-1;
    }
    """

    def __init__(self, session: SessionInfo, **kwargs):
        super().__init__(**kwargs)
        self.session_info = session

    def render(self):
        status_icon = {
            "running": "[green]\u25b6[/green]",
            "paused": "[yellow]\u275a\u275a[/yellow]",
            "completed": "[cyan]\u2714[/cyan]",
            "failed": "[red]\u2718[/red]",
        }.get(self.session_info.status, "[dim]?[/dim]")

        pr_info = f" PR #{self.session_info.pr_number}" if self.session_info.pr_number else ""

        return (
            f"{status_icon} [bold]{self.session_info.task}[/bold]{pr_info}\n"
            f"  [dim]{self.session_info.agent} \u2022 {self.session_info.status}[/dim]"
        )


class SessionList(Widget):
    """List of agent sessions"""

    DEFAULT_CSS = """
    SessionList {
        width: 100%;
        height: 100%;
    }
    SessionList > VerticalScroll {
        width: 100%;
        height: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield VerticalScroll()

    def set_sessions(self, sessions: list[SessionInfo]) -> None:
        scroll = self.query_one(VerticalScroll)
        scroll.remove_children()
        if not sessions:
            scroll.mount(Static("[dim]No active sessions[/dim]", classes="empty-state"))
            return
        for s in sessions:
            scroll.mount(SessionItem(s))
