from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, Static
from textual.worker import Worker, WorkerState


class AccountItem(Static):
    """A single GitHub account row in the settings list."""

    DEFAULT_CSS = """
    AccountItem {
        height: auto;
        padding: 1 2;
        margin: 0 1 1 1;
        background: $surface-darken-1;
        border: round $primary 30%;
    }
    AccountItem:hover {
        background: $surface-lighten-1;
    }
    .account-header {
        height: 1;
    }
    .account-details {
        height: 1;
        color: $text-muted;
        padding: 0 0 0 2;
    }
    .account-buttons {
        height: 3;
        padding: 1 0 0 2;
    }
    """

    def __init__(self, account_id: str, username: str, repo_count: int,
                 selected_count: int, index: int, **kwargs):
        super().__init__(**kwargs)
        self.account_id = account_id
        self.username = username
        self.repo_count = repo_count
        self.selected_count = selected_count
        self.index = index

    def compose(self) -> ComposeResult:
        label = f"GitHub Account {self.index}"
        yield Static(
            f"[green]OK[/green] [bold]{label}:[/bold] {self.username}  "
            f"[dim]({self.repo_count} repos, {self.selected_count} selected)[/dim]",
            classes="account-header",
        )
        with Horizontal(classes="account-buttons"):
            yield Button("Manage Repos", id=f"manage-{self.account_id}", variant="primary")
            yield Button("Remove", id=f"remove-{self.account_id}", variant="error")


class SettingsScreen(Screen):
    """Settings screen for managing GitHub accounts and app configuration."""

    DEFAULT_CSS = """
    SettingsScreen {
        layout: vertical;
    }

    #settings-title {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $primary-background-darken-1;
        color: $primary-lighten-2;
        text-style: bold;
        border-bottom: solid $primary 40%;
        padding: 0 2;
    }

    #settings-body {
        width: 100%;
        height: 1fr;
        padding: 1 2;
    }

    .settings-section-header {
        text-style: bold;
        color: $primary;
        padding: 1 0;
        height: auto;
    }

    .settings-separator {
        height: 1;
        color: $text-muted;
        padding: 0;
    }

    #add-account-btn {
        margin: 1 1;
    }

    #token-input-container {
        display: none;
        padding: 1 2;
        margin: 0 1;
        background: $surface-darken-2;
        border: round $primary 30%;
        height: auto;
    }

    #token-input-container.visible {
        display: block;
    }

    #token-input {
        width: 100%;
        margin: 1 0;
    }

    #token-status {
        height: auto;
        padding: 0 0 1 0;
    }

    .general-setting {
        height: 1;
        padding: 0 2;
    }

    #settings-footer-hint {
        dock: bottom;
        height: 1;
        background: $primary-background-darken-2;
        color: $text-muted;
        padding: 0 1;
    }

    #no-accounts-hint {
        text-align: center;
        color: $text-muted;
        padding: 2;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("comma", "go_back", "Back", show=False),
    ]

    class AccountsChanged(Message):
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._accounts: list[dict] = []
        self._adding_account = False
        self._verifying = False

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Settings[/bold]  [dim]|  Configure accounts & preferences[/dim]",
            id="settings-title",
        )
        with VerticalScroll(id="settings-body"):
            yield Static("[bold cyan]GitHub Accounts[/bold cyan]", classes="settings-section-header")
            yield Container(id="accounts-list")
            yield Static("", id="no-accounts-hint")
            yield Button("+ Add GitHub Account", id="add-account-btn", variant="success")
            with Container(id="token-input-container"):
                yield Static("", id="token-status")
                yield Input(placeholder="Paste your GitHub token (ghp_...)...", id="token-input", password=True)
                with Horizontal():
                    yield Button("Verify & Save", id="verify-token-btn", variant="primary")
                    yield Button("Cancel", id="cancel-token-btn")
            yield Static("[dim]" + "\u2500" * 50 + "[/dim]", classes="settings-separator")
            yield Static("[bold cyan]General Settings[/bold cyan]", classes="settings-section-header")
            yield Static("", id="general-settings-content")
        yield Static(
            "[bold cyan]Esc[/bold cyan] Back",
            id="settings-footer-hint",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_accounts()
        self._load_general_settings()

    def _load_accounts(self) -> None:
        from pm.auth.credentials import list_accounts
        self._accounts = list_accounts()
        self._rebuild_account_list()

    def _rebuild_account_list(self) -> None:
        container = self.query_one("#accounts-list", Container)
        container.remove_children()

        hint = self.query_one("#no-accounts-hint", Static)

        if not self._accounts:
            hint.update(
                "[dim]No GitHub accounts connected yet.\n"
                "Click [bold]+ Add GitHub Account[/bold] to get started.[/dim]"
            )
            return

        hint.update("")

        for i, acc in enumerate(self._accounts):
            item = AccountItem(
                account_id=acc["id"],
                username=acc["username"],
                repo_count=0,
                selected_count=len(acc.get("selected_repos", [])),
                index=i + 1,
            )
            container.mount(item)

    def _load_general_settings(self) -> None:
        try:
            from pm.config.loader import load_config
            cfg = load_config()
            lines = [
                f"  [bold]AI Model:[/bold]       {cfg.defaults.agent}",
                f"  [bold]Poll Interval:[/bold]  {cfg.defaults.poll_interval}",
                f"  [bold]Branch Prefix:[/bold]  {cfg.defaults.branch_prefix}",
                f"  [bold]Worktree Base:[/bold]  {cfg.defaults.worktree_base}",
            ]
            self.query_one("#general-settings-content", Static).update("\n".join(lines))
        except Exception:
            self.query_one("#general-settings-content", Static).update(
                "  [dim]No config file found. Defaults will be used.[/dim]"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "add-account-btn":
            self._start_add_account()
        elif btn_id == "verify-token-btn":
            self._verify_and_save_token()
        elif btn_id == "cancel-token-btn":
            self._cancel_add_account()
        elif btn_id.startswith("manage-"):
            account_id = btn_id[len("manage-"):]
            self._open_repo_selector(account_id)
        elif btn_id.startswith("remove-"):
            account_id = btn_id[len("remove-"):]
            self._remove_account(account_id)

    def _start_add_account(self) -> None:
        self._adding_account = True
        status = self.query_one("#token-status", Static)

        # Try gh CLI first
        from pm.auth.github_oauth import get_gh_token
        token = get_gh_token()
        if token:
            status.update(
                "[bold green]Detected gh CLI![/bold green] Verifying token..."
            )
            container = self.query_one("#token-input-container")
            container.add_class("visible")
            self._auto_verify_token(token)
            return

        status.update(
            "Paste a GitHub Personal Access Token.\n"
            "Create one at: [link=https://github.com/settings/tokens]github.com/settings/tokens[/link]\n"
            "Required scopes: [bold]repo[/bold], [bold]read:org[/bold]"
        )
        container = self.query_one("#token-input-container")
        container.add_class("visible")
        try:
            self.query_one("#token-input", Input).focus()
        except Exception:
            pass

    def _cancel_add_account(self) -> None:
        self._adding_account = False
        container = self.query_one("#token-input-container")
        container.remove_class("visible")
        self.query_one("#token-status", Static).update("")
        try:
            self.query_one("#token-input", Input).value = ""
        except Exception:
            pass

    def _auto_verify_token(self, token: str) -> None:
        self._verifying = True
        self.run_worker(
            lambda: self._verify_token_sync(token),
            name="verify_token",
            thread=True,
        )

    def _verify_and_save_token(self) -> None:
        if self._verifying:
            return
        try:
            token = self.query_one("#token-input", Input).value.strip()
        except Exception:
            return
        if not token:
            self.query_one("#token-status", Static).update(
                "[red]Please paste a token first.[/red]"
            )
            return
        self._verifying = True
        self.query_one("#token-status", Static).update(
            "[bold yellow]Verifying token...[/bold yellow]"
        )
        self.run_worker(
            lambda: self._verify_token_sync(token),
            name="verify_token",
            thread=True,
        )

    def _verify_token_sync(self, token: str) -> dict | None:
        from pm.auth.github_oauth import validate_token
        return validate_token(token), token

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "verify_token":
            return
        if event.state == WorkerState.SUCCESS:
            self._verifying = False
            result = event.worker.result
            if result is None:
                self.query_one("#token-status", Static).update(
                    "[red]Token validation failed. Check your token and try again.[/red]"
                )
                return
            user_info, token = result
            if user_info is None:
                self.query_one("#token-status", Static).update(
                    "[red]Token validation failed. Check your token and try again.[/red]"
                )
                return

            username = user_info["login"]
            from pm.auth.credentials import next_account_id, save_account
            account_id = next_account_id()
            save_account(account_id, token, username)

            self._cancel_add_account()
            self._load_accounts()
            self.post_message(self.AccountsChanged())

        elif event.state == WorkerState.ERROR:
            self._verifying = False
            self.query_one("#token-status", Static).update(
                "[red]Error verifying token. Please try again.[/red]"
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "token-input":
            self._verify_and_save_token()

    def _remove_account(self, account_id: str) -> None:
        from pm.auth.credentials import remove_account
        remove_account(account_id)
        self._load_accounts()
        self.post_message(self.AccountsChanged())

    def _open_repo_selector(self, account_id: str) -> None:
        from pm.tui.screens.repo_selector import RepoSelectorScreen
        account_data = None
        for acc in self._accounts:
            if acc["id"] == account_id:
                account_data = acc
                break
        if account_data is None:
            return

        from pm.auth.credentials import get_token
        token = get_token(account_id)
        if not token:
            return

        screen = RepoSelectorScreen(
            account_id=account_id,
            username=account_data["username"],
            token=token,
            selected_repos=account_data.get("selected_repos", []),
        )
        self.app.push_screen(screen, callback=self._on_repo_selection_done)

    def _on_repo_selection_done(self, result: list[str] | None) -> None:
        if result is not None:
            self._load_accounts()
            self.post_message(self.AccountsChanged())

    def action_go_back(self) -> None:
        if self._adding_account:
            self._cancel_add_account()
            return
        self.dismiss()
