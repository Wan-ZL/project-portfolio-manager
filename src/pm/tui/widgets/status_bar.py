from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class StatusBar(Widget):
    """Bottom status bar with keyboard shortcuts"""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        width: 100%;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._message = ""

    def compose(self) -> ComposeResult:
        yield Static(self._build_shortcuts(), id="shortcuts")

    def _build_shortcuts(self) -> str:
        shortcuts = [
            ("[bold cyan]j/k[/bold cyan] Navigate", ""),
            ("[bold cyan]Tab[/bold cyan] Switch Tabs", ""),
            ("[bold cyan]Enter[/bold cyan] Open", ""),
            ("[bold cyan]r[/bold cyan] Refresh", ""),
            ("[bold cyan]q[/bold cyan] Quit", ""),
        ]
        return "  ".join(s[0] for s in shortcuts)

    def set_message(self, msg: str) -> None:
        self._message = msg
        try:
            text = f"[bold yellow]{msg}[/bold yellow]" if msg else self._build_shortcuts()
            self.query_one("#shortcuts", Static).update(text)
        except Exception:
            pass
