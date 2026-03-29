from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pm.github.pr import EnhancedPR
from pm.tui.widgets.project_list import ProjectInfo


def _truncate_at_word(text: str, max_len: int) -> str:
    """Truncate text at a word boundary, adding '...' if truncated."""
    if len(text) <= max_len:
        return text
    truncated = text[: max_len - 3]
    # Find the last space to break at word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "..."


class ProjectCard(Widget):
    """A card widget displaying a project's status in 4 lines."""

    DEFAULT_CSS = """
    ProjectCard {
        width: 100%;
        height: auto;
        margin: 0 1 1 1;
        padding: 1 2;
        border: round $surface-lighten-2;
        background: $surface-darken-1;
    }
    ProjectCard.selected {
        border: round $primary;
        background: $surface;
    }
    ProjectCard:hover {
        background: $surface;
    }
    ProjectCard .card-line1 {
        width: 100%;
        height: 1;
    }
    ProjectCard .card-line2 {
        width: 100%;
        height: auto;
        padding: 0 0 0 2;
    }
    ProjectCard .card-line3 {
        width: 100%;
        height: auto;
        padding: 0 0 0 2;
    }
    ProjectCard .card-line4 {
        width: 100%;
        height: auto;
        color: $text-muted;
        padding: 0 0 0 2;
    }
    """

    selected = reactive(False)

    class Clicked(Message):
        def __init__(self, card: ProjectCard):
            super().__init__()
            self.card = card

    class Activated(Message):
        def __init__(self, card: ProjectCard):
            super().__init__()
            self.card = card

    def __init__(
        self,
        project: ProjectInfo,
        prs: list[EnhancedPR] | None = None,
        ai_summary: dict | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.project = project
        self._prs: list[EnhancedPR] = prs or []
        self._activity: str = ""
        self._ai_summary: dict | None = ai_summary
        self._card_data: dict | None = None
        self._last_command_status: str = ""
        self._last_command_time: str = ""

    def compose(self) -> ComposeResult:
        yield Static(self._render_line1(), classes="card-line1")
        yield Static(self._render_line2(), classes="card-line2")
        yield Static(self._render_line3(), classes="card-line3")
        yield Static(self._render_line4(), classes="card-line4")

    def on_click(self, event: Click) -> None:
        self.post_message(self.Clicked(self))

    def watch_selected(self, value: bool) -> None:
        self.set_class(value, "selected")

    def set_prs(self, prs: list[EnhancedPR]) -> None:
        self._prs = prs
        self._refresh_content()

    def set_activity(self, activity: str) -> None:
        self._activity = activity
        self._refresh_content()

    def set_ai_summary(self, summary: dict) -> None:
        self._ai_summary = summary
        self._refresh_content()

    def set_card_data(self, data: dict, status: str = "", time: str = "") -> None:
        self._card_data = data
        if status:
            self._last_command_status = status
        if time:
            self._last_command_time = time
        self._refresh_content()

    def _refresh_content(self) -> None:
        try:
            statics = list(self.query(Static))
            if len(statics) >= 4:
                statics[0].update(self._render_line1())
                statics[1].update(self._render_line2())
                statics[2].update(self._render_line3())
                statics[3].update(self._render_line4())
        except Exception:
            pass

    def _render_line1(self) -> str:
        p = self.project
        status_dot = {
            "green": "[green]\u25cf[/green]",
            "yellow": "[yellow]\u25cf[/yellow]",
            "red": "[red]\u25cf[/red]",
            "gray": "[dim]\u25cf[/dim]",
        }.get(p.status, "[dim]\u25cf[/dim]")

        pr_badge = f"  [dim]{p.open_prs} PRs[/dim]" if p.open_prs else ""

        status_indicator = {
            "red": "  [red]\u25cf[/red]",
            "yellow": "  [yellow]\u25cf[/yellow]",
            "green": "",
            "gray": "",
        }.get(p.status, "")

        return f"{status_dot} [bold]{p.name}[/bold]{pr_badge}{status_indicator}"

    def _render_line2(self) -> str:
        """Line 2: recent activity (commits + PRs) -- bright/normal color."""
        if self._card_data and self._card_data.get("dynamic"):
            return f"  \U0001f504 {self._card_data['dynamic']}"
        if self._ai_summary and self._ai_summary.get("one_line_status"):
            one_line = self._ai_summary["one_line_status"]
            one_line = _truncate_at_word(one_line, 120)
            return f"  \U0001f504 {one_line}"
        if self.project.summary:
            summary = _truncate_at_word(self.project.summary, 120)
            return f"  \U0001f504 {summary}"
        return "  [dim italic]Generating AI summary...[/dim italic]"

    def _render_line3(self) -> str:
        """Line 3: last user command -- bright/normal color."""
        if self._card_data and self._card_data.get("last_command_summary"):
            summary = self._card_data["last_command_summary"]
            time_str = f" ({self._last_command_time})" if self._last_command_time else ""
            return f'  \U0001f4cb 上次: "{summary}"{time_str}'
        return "  [dim]\U0001f4cb 还没有执行过任务[/dim]"

    def _render_line4(self) -> str:
        """Line 4: AI recommendation -- dim/gray color."""
        if self._card_data and self._card_data.get("recommendation"):
            return f"  [dim]\U0001f4a1 {self._card_data['recommendation']}[/dim]"
        return ""
