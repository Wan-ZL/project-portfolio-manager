from __future__ import annotations

from datetime import datetime
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, TabbedContent, TabPane, Tabs

from pm.github.pr import EnhancedPR
from pm.tui.widgets.pr_list import PRList
from pm.tui.widgets.session_list import SessionInfo, SessionList
from pm.tui.widgets.project_list import ProjectInfo


class StatusPanel(Widget):
    """Project status overview with AI summary integration"""

    DEFAULT_CSS = """
    StatusPanel {
        width: 100%;
        height: 100%;
        padding: 1 2;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._project: Optional[ProjectInfo] = None
        self._ai_summary: Optional[dict] = None
        self._ai_suggestions: list[dict] = []
        self._loading = False

    def compose(self) -> ComposeResult:
        yield VerticalScroll(
            Static("", id="status-title"),
            Static("", id="status-summary"),
            Static("", id="status-ai-detail"),
            Static("", id="status-instructions"),
            Static("", id="status-assets"),
            Static("", id="status-stats"),
            Static("", id="status-suggest"),
            Static("", id="status-notifications"),
        )

    def set_project(self, project: ProjectInfo) -> None:
        self._project = project
        self._update_display()

    def set_ai_summary(self, summary: dict) -> None:
        self._ai_summary = summary
        self._loading = False
        self._update_display()

    def set_ai_suggestions(self, suggestions: list[dict]) -> None:
        self._ai_suggestions = suggestions
        self._update_display()

    def show_loading(self) -> None:
        self._loading = True
        self._update_display()

    def show_suggestions_loading(self) -> None:
        try:
            self.query_one("#status-suggest", Static).update(
                "\n[bold yellow]Generating AI suggestions...[/bold yellow]"
            )
        except Exception:
            pass

    def set_notifications(self, notification_lines: list[str]) -> None:
        """Update the notifications section."""
        try:
            if notification_lines:
                text = "\n[bold red]Notifications:[/bold red]\n" + "\n".join(notification_lines)
            else:
                text = ""
            self.query_one("#status-notifications", Static).update(text)
        except Exception:
            pass

    def _update_display(self) -> None:
        if not self._project:
            return

        p = self._project
        try:
            self.query_one("#status-title", Static).update(
                f"[bold cyan]{p.name}[/bold cyan]"
            )

            # Show AI summary or fallback
            if self._loading:
                self.query_one("#status-summary", Static).update(
                    "\n[bold yellow]Generating AI summary...[/bold yellow]"
                )
                self.query_one("#status-ai-detail", Static).update("")
            elif self._ai_summary:
                from pm.ai.summary import format_summary_for_display
                formatted = format_summary_for_display(self._ai_summary)
                self.query_one("#status-summary", Static).update(f"\n{formatted}")
                self.query_one("#status-ai-detail", Static).update("")
            else:
                summary_text = p.summary or '[dim]No AI summary generated yet. Press [bold]s[/bold] to generate.[/dim]'
                self.query_one("#status-summary", Static).update(f"\n{summary_text}")
                self.query_one("#status-ai-detail", Static).update("")

            # Show instructions if available
            if p.instructions:
                instr_lines = [
                    "\n[bold cyan]Instructions:[/bold cyan]",
                    f"  [dim]{p.instructions.strip()}[/dim]",
                ]
                self.query_one("#status-instructions", Static).update("\n".join(instr_lines))
            else:
                self.query_one("#status-instructions", Static).update("")

            # Show assets if available
            if p.assets:
                import os
                asset_lines = ["\n[bold cyan]Assets:[/bold cyan]"]
                for asset_path in p.assets:
                    expanded = os.path.expanduser(asset_path)
                    exists = os.path.exists(expanded)
                    if exists:
                        size = os.path.getsize(expanded)
                        if size > 1024 * 1024:
                            size_str = f"{size / (1024 * 1024):.1f} MB"
                        elif size > 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        else:
                            size_str = f"{size} B"
                        asset_lines.append(f"  [green]+[/green] {asset_path} [dim]({size_str})[/dim]")
                    else:
                        asset_lines.append(f"  [red]![/red] {asset_path} [dim](not found)[/dim]")
                self.query_one("#status-assets", Static).update("\n".join(asset_lines))
            else:
                self.query_one("#status-assets", Static).update("")

            self.query_one("#status-stats", Static).update(
                f"\n[bold]Repos:[/bold] {len(p.repos)}  "
                f"[bold]Open PRs:[/bold] {p.open_prs}  "
                f"[bold]Sessions:[/bold] {p.active_sessions}"
            )

            # Show AI suggestions
            if self._ai_suggestions:
                from pm.ai.suggest import Suggestion, format_suggestions_for_display
                suggestions = [Suggestion.from_dict(s) for s in self._ai_suggestions]
                formatted = format_suggestions_for_display(suggestions)
                self.query_one("#status-suggest", Static).update(f"\n{formatted}")
            else:
                self.query_one("#status-suggest", Static).update(
                    "\n[dim italic]Press [bold]s[/bold] for AI suggestions on what to work on next.[/dim italic]"
                )
        except Exception:
            pass


class DetailPanel(Widget):
    """Tabbed detail panel with Status, PRs, and Sessions tabs"""

    DEFAULT_CSS = """
    DetailPanel {
        width: 100%;
        height: 100%;
    }
    DetailPanel > TabbedContent {
        width: 100%;
        height: 100%;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_project: Optional[ProjectInfo] = None

    def compose(self) -> ComposeResult:
        with TabbedContent("Status", "PRs", "Sessions", id="detail-tabs"):
            with TabPane("Status", id="tab-status"):
                yield StatusPanel()
            with TabPane("PRs", id="tab-prs"):
                yield PRList()
            with TabPane("Sessions", id="tab-sessions"):
                yield SessionList()

    def set_project(self, project: ProjectInfo) -> None:
        self._current_project = project
        try:
            self.query_one(StatusPanel).set_project(project)
        except Exception:
            pass

    def set_prs(self, prs: list[EnhancedPR]) -> None:
        try:
            self.query_one(PRList).set_prs(prs)
        except Exception:
            pass

    def set_sessions(self, sessions: list[SessionInfo]) -> None:
        try:
            self.query_one(SessionList).set_sessions(sessions)
        except Exception:
            pass

    def set_ai_summary(self, summary: dict) -> None:
        try:
            self.query_one(StatusPanel).set_ai_summary(summary)
        except Exception:
            pass

    def set_ai_suggestions(self, suggestions: list[dict]) -> None:
        try:
            self.query_one(StatusPanel).set_ai_suggestions(suggestions)
        except Exception:
            pass

    def show_summary_loading(self) -> None:
        try:
            self.query_one(StatusPanel).show_loading()
        except Exception:
            pass

    def show_suggestions_loading(self) -> None:
        try:
            self.query_one(StatusPanel).show_suggestions_loading()
        except Exception:
            pass

    def set_notifications(self, notification_lines: list[str]) -> None:
        try:
            self.query_one(StatusPanel).set_notifications(notification_lines)
        except Exception:
            pass

    def action_next_tab(self) -> None:
        try:
            tabs = self.query_one(Tabs)
            tabs.action_next_tab()
        except Exception:
            pass

    def action_prev_tab(self) -> None:
        try:
            tabs = self.query_one(Tabs)
            tabs.action_previous_tab()
        except Exception:
            pass
