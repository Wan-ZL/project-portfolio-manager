from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class StatusBar(Widget):
    """Bottom status bar with keyboard shortcuts and polling status"""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        width: 100%;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    #status-left {
        width: 1fr;
    }
    #status-right {
        width: auto;
        text-align: right;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._message = ""
        self._polling_status = ""

    def compose(self) -> ComposeResult:
        yield Static(self._build_shortcuts(), id="shortcuts")

    def _build_shortcuts(self) -> str:
        shortcuts = [
            ("[bold cyan]j/k[/bold cyan] Navigate", ""),
            ("[bold cyan]Tab[/bold cyan] Switch Tabs", ""),
            ("[bold cyan]Enter[/bold cyan] Open", ""),
            ("[bold cyan]r[/bold cyan] Refresh", ""),
            ("[bold cyan],[/bold cyan] Settings", ""),
            ("[bold cyan]q[/bold cyan] Quit", ""),
        ]
        base = "  ".join(s[0] for s in shortcuts)
        if self._polling_status:
            return f"{base}  [dim]|[/dim]  {self._polling_status}"
        return base

    def set_message(self, msg: str) -> None:
        self._message = msg
        try:
            text = f"[bold yellow]{msg}[/bold yellow]" if msg else self._build_shortcuts()
            self.query_one("#shortcuts", Static).update(text)
        except Exception:
            pass

    def set_polling_status(self, status: str) -> None:
        self._polling_status = status
        if not self._message:
            try:
                self.query_one("#shortcuts", Static).update(self._build_shortcuts())
            except Exception:
                pass
