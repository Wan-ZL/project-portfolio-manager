from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, Label


@dataclass
class ProjectInfo:
    name: str
    account: str
    repos: list[str] = field(default_factory=list)
    open_prs: int = 0
    active_sessions: int = 0
    status: str = "green"  # green, yellow, red, gray
    summary: str = ""
    has_active_reactions: bool = False
    instructions: str = ""
    assets: list[str] = field(default_factory=list)


class ProjectItem(Static):
    """A single project item in the list"""

    DEFAULT_CSS = """
    ProjectItem {
        height: 3;
        padding: 0 1;
        content-align: left middle;
    }
    ProjectItem.selected {
        background: $accent 30%;
    }
    ProjectItem:hover {
        background: $surface-lighten-2;
    }
    """

    class Clicked(Message):
        def __init__(self, item: ProjectItem):
            super().__init__()
            self.item = item

    selected = reactive(False)

    def __init__(self, project: ProjectInfo, **kwargs):
        super().__init__(**kwargs)
        self.project = project

    def on_click(self, event: Click) -> None:
        self.post_message(self.Clicked(self))

    def render(self):
        status_dot = {
            "green": "[green]\u25cf[/green]",
            "yellow": "[yellow]\u25cf[/yellow]",
            "red": "[red]\u25cf[/red]",
            "gray": "[dim]\u25cf[/dim]",
        }.get(self.project.status, "[dim]\u25cf[/dim]")

        indicator = "[cyan]\u25ba[/cyan] " if self.selected else "  "
        prs_info = f" [dim]PRs:{self.project.open_prs}[/dim]" if self.project.open_prs else ""
        reaction_badge = " [bold magenta]\u26a1[/bold magenta]" if self.project.has_active_reactions else ""

        return f"{indicator}{status_dot} {self.project.name}{prs_info}{reaction_badge}"

    def watch_selected(self, value: bool) -> None:
        self.set_class(value, "selected")


class AccountGroup(Static):
    """Account group header"""

    DEFAULT_CSS = """
    AccountGroup {
        height: 2;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self, account_name: str, **kwargs):
        super().__init__(**kwargs)
        self.account_name = account_name

    def render(self):
        return f"[bold cyan]\u25bc {self.account_name.upper()}[/bold cyan]"


class ProjectList(Widget):
    """Scrollable project list with account grouping"""

    DEFAULT_CSS = """
    ProjectList {
        width: 100%;
        height: 100%;
    }
    ProjectList > VerticalScroll {
        width: 100%;
        height: 100%;
    }
    """

    selected_index = reactive(0)

    class ProjectSelected(Message):
        def __init__(self, project: ProjectInfo):
            super().__init__()
            self.project = project

    class ProjectActivated(Message):
        def __init__(self, project: ProjectInfo):
            super().__init__()
            self.project = project

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._projects: list[ProjectInfo] = []
        self._items: list[ProjectItem] = []

    def compose(self) -> ComposeResult:
        yield VerticalScroll()

    def set_projects(self, projects: list[ProjectInfo]) -> None:
        self._projects = projects
        self._rebuild()

    def _rebuild(self) -> None:
        scroll = self.query_one(VerticalScroll)
        scroll.remove_children()
        self._items = []

        grouped: dict[str, list[ProjectInfo]] = {}
        for p in self._projects:
            grouped.setdefault(p.account, []).append(p)

        for account, projects in grouped.items():
            scroll.mount(AccountGroup(account))
            for proj in projects:
                item = ProjectItem(proj)
                scroll.mount(item)
                self._items.append(item)

        if self._items:
            self.selected_index = 0
            self._update_selection()

    def on_project_item_clicked(self, event: ProjectItem.Clicked) -> None:
        try:
            idx = self._items.index(event.item)
            self.selected_index = idx
            self._update_selection()
        except ValueError:
            pass

    def _update_selection(self) -> None:
        for i, item in enumerate(self._items):
            item.selected = i == self.selected_index
        if self._items and 0 <= self.selected_index < len(self._items):
            project = self._items[self.selected_index].project
            self.post_message(self.ProjectSelected(project))

    def action_cursor_down(self) -> None:
        if self._items and self.selected_index < len(self._items) - 1:
            self.selected_index += 1
            self._update_selection()

    def action_cursor_up(self) -> None:
        if self._items and self.selected_index > 0:
            self.selected_index -= 1
            self._update_selection()

    def action_activate(self) -> None:
        if self._items and 0 <= self.selected_index < len(self._items):
            project = self._items[self.selected_index].project
            self.post_message(self.ProjectActivated(project))

    @property
    def current_project(self) -> Optional[ProjectInfo]:
        if self._items and 0 <= self.selected_index < len(self._items):
            return self._items[self.selected_index].project
        return None
