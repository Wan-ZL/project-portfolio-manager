from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from pm.github.pr import EnhancedPR
from pm.tui.widgets.project_list import ProjectInfo


class ProjectCard(Widget):
    """A card widget displaying a project's status, summary, and top PRs."""

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
    ProjectCard .card-header {
        width: 100%;
        height: 1;
    }
    ProjectCard .card-summary {
        width: 100%;
        height: auto;
        color: $text-muted;
        padding: 0 0 0 2;
    }
    ProjectCard .card-prs {
        width: 100%;
        height: auto;
        padding: 0 0 0 2;
    }
    ProjectCard .card-activity {
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

    def __init__(self, project: ProjectInfo, prs: list[EnhancedPR] | None = None, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self._prs: list[EnhancedPR] = prs or []
        self._activity: str = ""

    def compose(self) -> ComposeResult:
        yield Static(self._render_header(), classes="card-header")
        yield Static(self._render_summary(), classes="card-summary")
        yield Static(self._render_prs(), classes="card-prs")
        yield Static(self._render_activity(), classes="card-activity")

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

    def _refresh_content(self) -> None:
        try:
            statics = list(self.query(Static))
            if len(statics) >= 4:
                statics[0].update(self._render_header())
                statics[1].update(self._render_summary())
                statics[2].update(self._render_prs())
                statics[3].update(self._render_activity())
        except Exception:
            pass

    def _render_header(self) -> str:
        p = self.project
        status_dot = {
            "green": "[green]\u25cf[/green]",
            "yellow": "[yellow]\u25cf[/yellow]",
            "red": "[red]\u25cf[/red]",
            "gray": "[dim]\u25cf[/dim]",
        }.get(p.status, "[dim]\u25cf[/dim]")

        pr_badge = f"  [dim]{p.open_prs} PRs[/dim]" if p.open_prs else ""

        status_label = {
            "red": "  [red]\u25cf[/red]",
            "yellow": "  [yellow]\u25cf[/yellow]",
            "green": "",
            "gray": "",
        }.get(p.status, "")

        return f"{status_dot} [bold]{p.name}[/bold]{pr_badge}{status_label}"

    def _render_summary(self) -> str:
        if not self.project.summary:
            return ""
        # Truncate to one line for card view
        summary = self.project.summary
        if len(summary) > 120:
            summary = summary[:117] + "..."
        return f"[dim italic]{summary}[/dim italic]"

    def _render_prs(self) -> str:
        if not self._prs:
            return ""

        lines = []
        show_prs = self._prs[:5]
        for i, pr in enumerate(show_prs):
            ci_icon = {
                "passing": "[green]\u25cf[/green]",
                "failing": "[red]\u25cf[/red]",
                "pending": "[yellow]\u25cf[/yellow]",
            }.get(pr.ci_status, "[dim]\u25cf[/dim]")

            review_label = {
                "approved": "[green]approved[/green]",
                "changes_requested": "[yellow]changes_requested[/yellow]",
                "pending": "[dim]pending[/dim]",
            }.get(pr.review_status, f"[dim]{pr.review_status}[/dim]")

            connector = "\u2514" if i == len(show_prs) - 1 else "\u251c"
            lines.append(
                f"  {connector} PR [bold]#{pr.number}[/bold]  {pr.title[:40]:<40}  "
                f"CI:{ci_icon}  Review:{review_label}"
            )

        if len(self._prs) > 5:
            lines.append(f"  [dim]  ... and {len(self._prs) - 5} more[/dim]")

        return "\n".join(lines)

    def _render_activity(self) -> str:
        if not self._activity:
            return ""
        return self._activity
