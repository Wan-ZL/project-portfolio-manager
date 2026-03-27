from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

VERSION = "0.1.0"


class HelpScreen(ModalScreen):
    """Help overlay showing keyboard shortcuts and info."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    #help-dialog {
        width: 72;
        max-height: 80%;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }

    #help-title {
        text-align: center;
        text-style: bold;
        color: $primary-lighten-2;
        padding: 0 0 1 0;
    }

    #help-version {
        text-align: center;
        color: $text-muted;
        padding: 0 0 1 0;
    }

    .help-section-header {
        text-style: bold;
        color: $primary;
        padding: 1 0 0 0;
    }

    .help-shortcut-row {
        padding: 0 0 0 2;
    }

    #help-footer {
        text-align: center;
        color: $text-muted;
        padding: 1 0 0 0;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_help", "Close"),
        Binding("question_mark", "dismiss_help", "Close"),
        Binding("q", "dismiss_help", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Static(
                "[bold]PPM - Project Portfolio Manager[/bold]",
                id="help-title",
            )
            yield Static(
                f"[dim]Version {VERSION}  |  AI-powered multi-project management[/dim]",
                id="help-version",
            )
            with VerticalScroll():
                # Portfolio View
                yield Static("[bold cyan]Portfolio View[/bold cyan]", classes="help-section-header")
                yield Static("  [bold]j / k / Up / Down[/bold]   Navigate projects", classes="help-shortcut-row")
                yield Static("  [bold]Tab / Shift+Tab[/bold]     Switch detail tabs", classes="help-shortcut-row")
                yield Static("  [bold]Enter[/bold]               Open project detail", classes="help-shortcut-row")
                yield Static("  [bold]n[/bold]                   New task for selected project", classes="help-shortcut-row")
                yield Static("  [bold]s[/bold]                   AI suggest next action", classes="help-shortcut-row")
                yield Static("  [bold]r[/bold]                   Refresh all data", classes="help-shortcut-row")
                yield Static("  [bold]?[/bold]                   Toggle this help", classes="help-shortcut-row")
                yield Static("  [bold]q[/bold]                   Quit", classes="help-shortcut-row")

                # Project View
                yield Static("[bold cyan]Project View[/bold cyan]", classes="help-section-header")
                yield Static("  [bold]j / k / Up / Down[/bold]   Navigate PRs & sessions", classes="help-shortcut-row")
                yield Static("  [bold]Tab / Shift+Tab[/bold]     Switch detail tabs", classes="help-shortcut-row")
                yield Static("  [bold]Enter[/bold]               Select / open item", classes="help-shortcut-row")
                yield Static("  [bold]a[/bold]                   Attach to session", classes="help-shortcut-row")
                yield Static("  [bold]n[/bold]                   New task for this project", classes="help-shortcut-row")
                yield Static("  [bold]f[/bold]                   Fix selected PR (send to agent)", classes="help-shortcut-row")
                yield Static("  [bold]m[/bold]                   Merge selected PR", classes="help-shortcut-row")
                yield Static("  [bold]o[/bold]                   Open asset in system viewer", classes="help-shortcut-row")
                yield Static("  [bold]Esc[/bold]                 Back to Portfolio", classes="help-shortcut-row")

                # Task View
                yield Static("[bold cyan]Task View[/bold cyan]", classes="help-section-header")
                yield Static("  [bold]p[/bold]                   Pause / resume session", classes="help-shortcut-row")
                yield Static("  [bold]k[/bold]                   Kill session", classes="help-shortcut-row")
                yield Static("  [bold]r[/bold]                   Reprompt agent", classes="help-shortcut-row")
                yield Static("  [bold]Ctrl+Q[/bold]              Detach (agent keeps running)", classes="help-shortcut-row")
                yield Static("  [bold]Esc[/bold]                 Back to Project View", classes="help-shortcut-row")

                # General
                yield Static("[bold cyan]General[/bold cyan]", classes="help-section-header")
                yield Static("  [bold]Mouse click[/bold]         Select project / switch tabs", classes="help-shortcut-row")
                yield Static("  [bold]Mouse wheel[/bold]         Scroll lists and content", classes="help-shortcut-row")

            yield Static(
                "[dim]Press [bold]Esc[/bold] or [bold]?[/bold] to close[/dim]",
                id="help-footer",
            )

    def action_dismiss_help(self) -> None:
        self.dismiss()
