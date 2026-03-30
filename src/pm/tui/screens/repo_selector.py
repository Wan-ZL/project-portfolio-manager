from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.events import Click
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Static
from textual.worker import Worker, WorkerState


class RepoItem(Static):
    """A toggleable repo item with checkbox."""

    DEFAULT_CSS = """
    RepoItem {
        height: 2;
        padding: 0 2;
    }
    RepoItem.selected-item {
        background: $accent 20%;
    }
    RepoItem:hover {
        background: $surface-lighten-1;
    }
    """

    checked = reactive(False)

    def __init__(self, repo_name: str, is_private: bool,
                 open_prs: int = 0, checked: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.repo_name = repo_name
        self.is_private = is_private
        self.open_prs = open_prs
        self.checked = checked

    def on_click(self, event: Click) -> None:
        self.checked = not self.checked

    def render(self) -> str:
        check = "[green]X[/green]" if self.checked else "[ ]"
        visibility = "[dim](private)[/dim]" if self.is_private else "[dim](public)[/dim]"
        pr_info = ""
        if self.open_prs > 0:
            pr_info = f"  [yellow]{self.open_prs} PRs[/yellow]"
        return f"  {check} {self.repo_name}  {visibility}{pr_info}"


class RepoSelectorScreen(Screen):
    """Screen for selecting which repos to include from a GitHub account."""

    DEFAULT_CSS = """
    RepoSelectorScreen {
        layout: vertical;
    }

    #repo-selector-title {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $primary-background-darken-1;
        color: $primary-lighten-2;
        text-style: bold;
        border-bottom: solid $primary 40%;
        padding: 0 2;
    }

    #repo-selector-body {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    #repo-loading {
        text-align: center;
        color: $text-muted;
        padding: 4;
    }

    #repo-actions {
        dock: bottom;
        height: 3;
        padding: 0 2;
        background: $surface-darken-2;
        content-align: center middle;
    }

    #repo-actions Button {
        margin: 0 1;
    }

    #repo-hint {
        dock: bottom;
        height: 1;
        background: $primary-background-darken-2;
        color: $text-muted;
        padding: 0 1;
    }

    #repo-count-status {
        dock: bottom;
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("space", "toggle_current", "Toggle", show=False),
        Binding("a", "select_all", "Select All"),
        Binding("shift+n", "select_none", "Select None"),
        Binding("enter", "save", "Save"),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
    ]

    def __init__(self, account_id: str, username: str, token: str,
                 selected_repos: list[str], **kwargs):
        super().__init__(**kwargs)
        self._account_id = account_id
        self._username = username
        self._token = token
        self._selected_repos = set(selected_repos)
        self._repos: list[dict] = []
        self._repo_items: list[RepoItem] = []
        self._cursor_index = 0

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold]Select Repos for {self._username}[/bold]",
            id="repo-selector-title",
        )
        with VerticalScroll(id="repo-selector-body"):
            yield Static(
                "[bold yellow]Loading repositories from GitHub...[/bold yellow]",
                id="repo-loading",
            )
        yield Static("", id="repo-count-status")
        with Horizontal(id="repo-actions"):
            yield Button("Save Selection", id="save-btn", variant="primary")
            yield Button("Cancel", id="cancel-btn")
        yield Static(
            "[bold cyan]Space[/bold cyan] Toggle  "
            "[bold cyan]a[/bold cyan] Select All  "
            "[bold cyan]N[/bold cyan] Select None  "
            "[bold cyan]Enter[/bold cyan] Save  "
            "[bold cyan]Esc[/bold cyan] Cancel",
            id="repo-hint",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._fetch_repos, name="fetch_repos", thread=True)

    async def _fetch_repos(self) -> list[dict]:
        from pm.auth.github_oauth import discover_repos
        return discover_repos(self._token, max_repos=100)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "fetch_repos":
            return
        if event.state == WorkerState.SUCCESS:
            self._repos = event.worker.result or []
            self._build_repo_list()
        elif event.state == WorkerState.ERROR:
            try:
                self.query_one("#repo-loading", Static).update(
                    "[red]Failed to load repositories. Press Esc to go back.[/red]"
                )
            except Exception:
                pass

    def _build_repo_list(self) -> None:
        body = self.query_one("#repo-selector-body", VerticalScroll)
        body.remove_children()
        self._repo_items = []

        if not self._repos:
            body.mount(Static("[dim]No repositories found for this account.[/dim]"))
            return

        for repo in self._repos:
            full_name = repo.get("full_name", "")
            is_private = repo.get("private", False)
            open_prs = repo.get("open_issues_count", 0)
            is_checked = full_name in self._selected_repos
            item = RepoItem(full_name, is_private, open_prs=open_prs, checked=is_checked)
            body.mount(item)
            self._repo_items.append(item)

        if self._repo_items:
            self._cursor_index = 0
            self._update_cursor()
            self._update_count_status()

    def _update_cursor(self) -> None:
        for i, item in enumerate(self._repo_items):
            item.set_class(i == self._cursor_index, "selected-item")

    def _update_count_status(self) -> None:
        selected = sum(1 for item in self._repo_items if item.checked)
        total = len(self._repo_items)
        try:
            self.query_one("#repo-count-status", Static).update(
                f"  {selected}/{total} repos selected"
            )
        except Exception:
            pass

    def watch_checked(self) -> None:
        self._update_count_status()

    def action_cursor_down(self) -> None:
        if self._repo_items and self._cursor_index < len(self._repo_items) - 1:
            self._cursor_index += 1
            self._update_cursor()

    def action_cursor_up(self) -> None:
        if self._repo_items and self._cursor_index > 0:
            self._cursor_index -= 1
            self._update_cursor()

    def action_toggle_current(self) -> None:
        if self._repo_items and 0 <= self._cursor_index < len(self._repo_items):
            item = self._repo_items[self._cursor_index]
            item.checked = not item.checked
            self._update_count_status()

    def action_select_all(self) -> None:
        for item in self._repo_items:
            item.checked = True
        self._update_count_status()

    def action_select_none(self) -> None:
        for item in self._repo_items:
            item.checked = False
        self._update_count_status()

    def action_save(self) -> None:
        self._do_save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._do_save()
        elif event.button.id == "cancel-btn":
            self.dismiss(None)

    def _do_save(self) -> None:
        selected = [item.repo_name for item in self._repo_items if item.checked]
        from pm.auth.credentials import save_selected_repos
        save_selected_repos(self._account_id, selected)
        self.dismiss(selected)
