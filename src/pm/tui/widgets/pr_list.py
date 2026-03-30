from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from pm.github.pr import EnhancedPR


class PRItem(Static):
    """A single PR item"""

    DEFAULT_CSS = """
    PRItem {
        height: 2;
        padding: 0 1;
    }
    PRItem:hover {
        background: $surface-lighten-1;
    }
    """

    def __init__(self, pr: EnhancedPR, **kwargs):
        super().__init__(**kwargs)
        self.pr = pr

    def render(self):
        ci_icon = {
            "passing": "[green]\u2714[/green]",
            "failing": "[red]\u2718[/red]",
            "pending": "[yellow]\u25cb[/yellow]",
        }.get(self.pr.ci_status, "[dim]\u25cb[/dim]")

        review_icon = {
            "approved": "[green]\u2714[/green]",
            "changes_requested": "[yellow]\u270e[/yellow]",
            "pending": "[dim]\u2026[/dim]",
        }.get(self.pr.review_status, "[dim]\u2026[/dim]")

        repo_short = self.pr.repo_id.split("/")[-1] if "/" in self.pr.repo_id else self.pr.repo_id

        return (
            f"{ci_icon} {review_icon} [bold]#{self.pr.number}[/bold] {self.pr.title}\n"
            f"  [dim]{repo_short} \u2022 {self.pr.author} \u2022 {self.pr.updated_at.strftime('%m/%d')}[/dim]"
        )


class PRList(Widget):
    """List of pull requests"""

    DEFAULT_CSS = """
    PRList {
        width: 100%;
        height: 100%;
    }
    PRList > VerticalScroll {
        width: 100%;
        height: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield VerticalScroll()

    def set_prs(self, prs: list[EnhancedPR]) -> None:
        scroll = self.query_one(VerticalScroll)
        scroll.remove_children()
        if not prs:
            scroll.mount(Static("[dim]No open pull requests[/dim]", classes="empty-state"))
            return
        for pr in prs:
            scroll.mount(PRItem(pr))
