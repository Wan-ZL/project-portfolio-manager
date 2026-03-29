from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from pm.tui.screens.help import HelpScreen
from pm.tui.screens.portfolio import PortfolioScreen
from pm.tui.screens.project import ProjectScreen
from pm.tui.screens.settings import SettingsScreen
from pm.tui.screens.task import TaskScreen


class PMApp(App):
    """Project Portfolio Manager TUI"""

    TITLE = "PPM"

    BINDINGS = [
        Binding("comma", "open_settings", "Settings", show=False),
        Binding("ctrl+p", "noop", "", show=False),
    ]

    COMMAND_PALETTE_BINDING = "ctrl+shift+p"

    def action_noop(self) -> None:
        pass

    def __init__(self, demo: bool = False, **kwargs):
        super().__init__(**kwargs)
        self._demo = demo
        self._recovered_sessions: list[dict] = []

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
        "settings": SettingsScreen,
    }

    @property
    def demo_mode(self) -> bool:
        return self._demo

    def on_mount(self) -> None:
        if not self._demo:
            self._run_crash_recovery()
        self.push_screen(PortfolioScreen())

    def _run_crash_recovery(self) -> None:
        """Detect orphaned tmux sessions from a previous crash."""
        try:
            from pm.config.loader import load_config
            from pm.db.database import Database
            from pm.agent.session import SessionManager

            config = load_config()
            db = Database()
            mgr = SessionManager(config, db)
            self._recovered_sessions = mgr.recover_sessions()
        except Exception:
            self._recovered_sessions = []

    def action_open_settings(self) -> None:
        # Don't open settings if already on settings screen
        if isinstance(self.screen, SettingsScreen):
            return
        self.push_screen(SettingsScreen(), callback=self._on_settings_closed)

    def _on_settings_closed(self, result=None) -> None:
        # Refresh portfolio data after settings changes
        if isinstance(self.screen, PortfolioScreen):
            self.screen.action_refresh()


def run_app(demo: bool = False) -> None:
    from pm.errors import setup_logging
    setup_logging()

    # Only auto-enable demo if explicitly requested via --demo flag.
    # Without --demo, the TUI will show an empty state with guidance
    # to connect a GitHub account via Settings (comma key).
    app = PMApp(demo=demo)
    app.run()
