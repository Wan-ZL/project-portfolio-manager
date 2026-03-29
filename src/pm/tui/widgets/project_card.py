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

    def set_ai_summary(self, summary: dict) -> None:
        self._ai_summary = summary
        self._refresh_content()

    def _render_summary(self) -> str:
        # Prefer AI one-line summary if available
        if self._ai_summary and self._ai_summary.get("one_line_status"):
            one_line = self._ai_summary["one_line_status"]
            one_line = _truncate_at_word(one_line, 120)
            return f"[dim italic]{one_line}[/dim italic]"
        if not self.project.summary:
            return ""
        summary = _truncate_at_word(self.project.summary, 120)
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
                "changes_requested": "[yellow]changes[/yellow]",
                "pending": "[dim]pending[/dim]",
            }.get(pr.review_status, f"[dim]{pr.review_status}[/dim]")

            title = _truncate_at_word(pr.title, 40)

            connector = "\u2514" if i == len(show_prs) - 1 else "\u251c"
            lines.append(
                f"  {connector} PR [bold]#{pr.number}[/bold]  {title:<40}  "
                f"CI: {ci_icon}  [dim]|[/dim]  Review: {review_label}"
            )

        if len(self._prs) > 5:
            lines.append(f"  [dim]  ... and {len(self._prs) - 5} more[/dim]")

        return "\n".join(lines)

    def _render_activity(self) -> str:
        if self._activity:
            return self._activity
        # Generate activity from PRs if available
        if self._prs:
            latest = max(self._prs, key=lambda p: p.updated_at)
            from datetime import datetime
            now = datetime.now()
            try:
                delta = now - latest.updated_at.replace(tzinfo=None)
            except TypeError:
                delta = now - latest.updated_at
            if delta.days > 0:
                ago = f"{delta.days}d ago"
            elif delta.seconds >= 3600:
                ago = f"{delta.seconds // 3600}h ago"
            else:
                ago = "just now"
            title = _truncate_at_word(latest.title, 50)
            return f"[dim]Recent: PR #{latest.number} {title} ({ago})[/dim]"
        return ""
