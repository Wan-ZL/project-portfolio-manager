from __future__ import annotations

from textual.app import App

from pm.tui.screens.help import HelpScreen
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.screens.project import ProjectScreen
from pm.tui.screens.task import TaskScreen


class PMApp(App):
    """Project Portfolio Manager TUI"""

    TITLE = "PPM - Portfolio Manager"

    DEFAULT_CSS = """
    Screen {
        background: $surface;
    }

    Scrollbar {
        background: $surface-darken-1;
        scrollbar-color: $primary 50%;
        scrollbar-color-hover: $primary 80%;
        scrollbar-color-active: $primary;
    }

    .empty-state {
        text-align: center;
        color: $text-muted;
        padding: 2;
    }

    Footer {
        background: $primary-background;
    }

    TabbedContent {
        border: none;
    }

    TabPane {
        padding: 0;
    }

    Tabs {
        background: $surface-darken-1;
    }

    Tab {
        color: $text-muted;
        padding: 0 2;
    }

    Tab.-active {
        color: $text;
        text-style: bold;
    }

    Tab:hover {
        color: $primary-lighten-2;
    }

    Underline > .underline--bar {
        color: $primary 40%;
    }
    """

    SCREENS = {
        "portfolio": PortfolioScreen,
        "project": ProjectScreen,
        "task": TaskScreen,
        "help": HelpScreen,
    }

    def __init__(self, demo: bool = False, **kwargs):
        super().__init__(**kwargs)
        self._demo = demo

    @property
    def demo_mode(self) -> bool:
        return self._demo

    def on_mount(self) -> None:
        self.push_screen(PortfolioScreen())


def run_app(demo: bool = False) -> None:
    from pm.errors import setup_logging
    setup_logging()

    from pm.ai.demo import is_demo_mode
    # Auto-enable demo mode if no config exists
    if not demo and is_demo_mode():
        demo = True
    app = PMApp(demo=demo)
    app.run()
