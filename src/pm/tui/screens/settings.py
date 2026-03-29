from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Rule, Select, Static, Switch
from textual.worker import Worker, WorkerState


class AccountItem(Static):
    """A single GitHub account row in the settings list."""

    DEFAULT_CSS = """
    AccountItem {
        height: auto;
        min-height: 5;
        padding: 1 2;
        margin: 0 1 1 1;
        background: $surface-darken-1;
        border: round $primary 30%;
    }
    AccountItem:hover {
        background: $surface-lighten-1;
    }
    .account-header {
        height: auto;
        min-height: 1;
    }
    .account-buttons {
        height: 3;
        margin: 1 0 0 2;
    }
    .account-buttons Button {
        margin: 0 1 0 0;
    }
    .rename-row {
        height: auto;
        padding: 1 0 0 2;
    }
    .rename-row Input {
        width: 30;
    }
    .rename-row Button {
        margin: 0 0 0 1;
    }
    """

    def __init__(self, account_id: str, display_name: str, username: str,
                 repo_count: int, selected_count: int, **kwargs):
        super().__init__(**kwargs)
        self.account_id = account_id
        self.display_name = display_name
        self.username = username
        self.repo_count = repo_count
        self.selected_count = selected_count
        self._renaming = False

    def compose(self) -> ComposeResult:
        yield Static(
            self._header_text(),
            classes="account-header",
            id=f"header-{self.account_id}",
        )
        with Horizontal(classes="account-buttons"):
            yield Button("Rename", id=f"rename-{self.account_id}")
            yield Button("Manage Repos", id=f"manage-{self.account_id}", variant="primary")
            yield Button("Remove", id=f"remove-{self.account_id}", variant="error")
        with Horizontal(classes="rename-row", id=f"rename-row-{self.account_id}"):
            yield Input(
                value=self.display_name,
                placeholder="Enter name...",
                id=f"rename-input-{self.account_id}",
            )
            yield Button("OK", id=f"rename-ok-{self.account_id}", variant="success")
            yield Button("Cancel", id=f"rename-cancel-{self.account_id}")

    def on_mount(self) -> None:
        self._hide_rename_row()

    def _header_text(self) -> str:
        status = f"[green]Connected as {self.username}[/green]"
        repo_info = f"{self.selected_count}/{self.repo_count} selected"
        return (
            f"  {status}  {self.display_name}"
            f"       [dim]{repo_info}[/dim]"
        )

    def update_header(self, display_name: str | None = None,
                      selected_count: int | None = None,
                      repo_count: int | None = None) -> None:
        if display_name is not None:
            self.display_name = display_name
        if selected_count is not None:
            self.selected_count = selected_count
        if repo_count is not None:
            self.repo_count = repo_count
        try:
            header = self.query_one(f"#header-{self.account_id}", Static)
            header.update(self._header_text())
        except Exception:
            pass

    def show_rename_row(self) -> None:
        self._renaming = True
        try:
            row = self.query_one(f"#rename-row-{self.account_id}", Horizontal)
            row.styles.display = "block"
            inp = self.query_one(f"#rename-input-{self.account_id}", Input)
            inp.value = self.display_name
            inp.focus()
        except Exception:
            pass

    def _hide_rename_row(self) -> None:
        self._renaming = False
        try:
            row = self.query_one(f"#rename-row-{self.account_id}", Horizontal)
            row.styles.display = "none"
        except Exception:
            pass

    def hide_rename_row(self) -> None:
        self._hide_rename_row()


class ProjectGroupItem(Static):
    """A single project group row."""

    DEFAULT_CSS = """
    ProjectGroupItem {
        height: auto;
        padding: 1 2;
        margin: 0 1 1 1;
        background: $surface-darken-1;
        border: round $primary 30%;
    }
    ProjectGroupItem:hover {
        background: $surface-lighten-1;
    }
    .group-buttons {
        height: 3;
        padding: 1 0 0 2;
    }
    .group-buttons Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(self, group_name: str, repos: list[str], **kwargs):
        super().__init__(**kwargs)
        self.group_name = group_name
        self.repos = repos

    def compose(self) -> ComposeResult:
        yield Static(self._render_text(), id=f"group-content-{self.group_name}")
        with Horizontal(classes="group-buttons"):
            yield Button("Edit", id=f"edit-group-{self.group_name}", variant="primary")
            yield Button("Remove", id=f"remove-group-{self.group_name}", variant="error")

    def _render_text(self) -> str:
        lines = [f"  [bold]{self.group_name}[/bold]"]
        for i, repo in enumerate(self.repos):
            if i == len(self.repos) - 1:
                lines.append(f"       [dim]{repo}[/dim]")
            else:
                lines.append(f"       [dim]{repo}[/dim]")
        if not self.repos:
            lines.append("       [dim italic]No repos[/dim italic]")
        return "\n".join(lines)


class SettingsScreen(Screen):
    """Settings screen for managing GitHub accounts and app configuration."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    class AccountsChanged(Message):
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._accounts: list[dict] = []
        self._adding_account = False
        self._verifying = False
        self._creating_group = False
        self._editing_group: str | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Settings[/bold]  [dim]|  Configure accounts & preferences[/dim]",
            id="settings-title",
        )
        with VerticalScroll(id="settings-body"):
            # Section 1: GitHub Accounts
            yield Static("[bold cyan]GitHub Accounts[/bold cyan]", classes="settings-section-header")
            yield Rule(line_style="heavy")
            yield Container(id="accounts-list")
            yield Static("", id="no-accounts-hint")
            yield Button("+ Add GitHub Account", id="add-account-btn", variant="success")
            with Container(id="token-input-container"):
                yield Static("", id="token-status")
                yield Input(
                    placeholder="Paste your GitHub token (ghp_...)...",
                    id="token-input",
                    password=True,
                )
                with Horizontal(id="token-buttons"):
                    yield Button("Verify & Save", id="verify-token-btn", variant="primary")
                    yield Button("Cancel", id="cancel-token-btn")

            # Section 2: Project Groups
            yield Rule(line_style="heavy")
            yield Static("[bold cyan]Project Groups[/bold cyan]", classes="settings-section-header")
            yield Static("[dim]Group related repos into projects for better organization.[/dim]",
                         classes="settings-section-hint")
            yield Container(id="project-groups-list")
            yield Button("+ Create Project Group", id="create-group-btn", variant="success")
            with Container(id="group-create-container"):
                yield Input(
                    placeholder="Group name...",
                    id="group-name-input",
                )
                yield Static("[dim]Select repos for this group:[/dim]", id="group-repo-hint")
                yield Container(id="group-repo-checkboxes")
                with Horizontal(id="group-create-buttons"):
                    yield Button("Save Group", id="save-group-btn", variant="primary")
                    yield Button("Cancel", id="cancel-group-btn")

            # Section 3: General Settings
            yield Rule(line_style="heavy")
            yield Static("[bold cyan]General Settings[/bold cyan]", classes="settings-section-header")
            yield Container(id="general-settings-container")

            # Section 4: Desktop Overlay
            yield Rule(line_style="heavy")
            yield Static("[bold cyan]Desktop Overlay[/bold cyan]", classes="settings-section-header")
            yield Container(id="overlay-settings-container")

        yield Footer()

    def on_mount(self) -> None:
        self._load_accounts()
        self._load_project_groups()
        self._load_general_settings()
        self._load_overlay_settings()

    # -- Account loading ---------------------------------------------------

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

        for acc in self._accounts:
            selected = acc.get("selected_repos", [])
            item = AccountItem(
                account_id=acc["id"],
                display_name=acc["display_name"],
                username=acc["username"],
                repo_count=len(selected),
                selected_count=len(selected),
            )
            container.mount(item)

        # Kick off background repo count fetch for each account
        for acc in self._accounts:
            self._fetch_repo_count(acc["id"])

    def _fetch_repo_count(self, account_id: str) -> None:
        from pm.auth.credentials import get_token
        token = get_token(account_id)
        if not token:
            return
        self.run_worker(
            lambda t=token, aid=account_id: self._count_repos_sync(t, aid),
            name=f"count_repos_{account_id}",
            thread=True,
        )

    def _count_repos_sync(self, token: str, account_id: str) -> tuple[str, int]:
        from pm.auth.github_oauth import discover_repos
        repos = discover_repos(token, max_repos=200)
        return account_id, len(repos)

    # -- General Settings --------------------------------------------------

    def _load_general_settings(self) -> None:
        container = self.query_one("#general-settings-container", Container)
        container.remove_children()

        from pm.config.settings import load_settings
        settings = load_settings()
        general = settings.get("general", {})

        agent = general.get("default_agent", "claude-code")
        poll = general.get("poll_interval", "5s")

        row1 = Horizontal(classes="setting-edit-row", id="general-agent-row")
        container.mount(row1)
        row1.mount(Static("  Default Agent: ", classes="setting-label"))
        row1.mount(Input(value=agent, id="general-agent-input", placeholder="e.g. claude-code"))

        row2 = Horizontal(classes="setting-edit-row", id="general-poll-row")
        container.mount(row2)
        row2.mount(Static("  Poll Interval: ", classes="setting-label"))
        row2.mount(Input(value=poll, id="general-poll-input", placeholder="e.g. 5s, 30s"))

    # -- Overlay Settings --------------------------------------------------

    def _load_overlay_settings(self) -> None:
        container = self.query_one("#overlay-settings-container", Container)
        container.remove_children()

        from pm.config.settings import load_settings
        settings = load_settings()
        overlay = settings.get("overlay", {})

        enabled = overlay.get("enabled", False)
        show_count = overlay.get("show_count", 3)
        position = overlay.get("position", "bottom-right")
        opacity = overlay.get("opacity", 70)

        row_enable = Horizontal(classes="overlay-row", id="overlay-enable-row")
        container.mount(row_enable)
        row_enable.mount(Static("  Enable overlay: ", classes="setting-label"))
        sw = Switch(value=enabled, id="overlay-enabled-switch")
        row_enable.mount(sw)

        row_count = Horizontal(classes="overlay-row", id="overlay-count-row")
        container.mount(row_count)
        row_count.mount(Static("  Show projects:  ", classes="setting-label"))
        row_count.mount(Input(value=str(show_count), id="overlay-count-input", placeholder="3"))

        row_pos = Horizontal(classes="overlay-row", id="overlay-pos-row")
        container.mount(row_pos)
        row_pos.mount(Static("  Position:       ", classes="setting-label"))
        positions = [
            ("Bottom-right", "bottom-right"),
            ("Bottom-left", "bottom-left"),
            ("Top-right", "top-right"),
            ("Top-left", "top-left"),
        ]
        sel = Select(
            options=positions,
            value=position,
            id="overlay-position-select",
        )
        row_pos.mount(sel)

        row_opacity = Horizontal(classes="overlay-row", id="overlay-opacity-row")
        container.mount(row_opacity)
        row_opacity.mount(Static("  Opacity:        ", classes="setting-label"))
        row_opacity.mount(Input(value=str(opacity), id="overlay-opacity-input", placeholder="70"))

    # -- Project Groups ----------------------------------------------------

    def _load_project_groups(self) -> None:
        container = self.query_one("#project-groups-list", Container)
        container.remove_children()

        from pm.auth.credentials import load_project_groups
        groups = load_project_groups()

        if not groups:
            container.mount(Static(
                "[dim]No project groups yet. Create one to organize repos.[/dim]",
                id="no-groups-hint",
            ))
            return

        for name, repos in groups.items():
            item = ProjectGroupItem(group_name=name, repos=repos)
            container.mount(item)

    def _get_all_repos(self) -> list[str]:
        all_repos = []
        for acc in self._accounts:
            for repo in acc.get("selected_repos", []):
                if repo not in all_repos:
                    all_repos.append(repo)
        return all_repos

    def _show_group_create_form(self, group_name: str = "", selected_repos: list[str] | None = None) -> None:
        self._creating_group = True
        container = self.query_one("#group-create-container")
        container.add_class("visible")

        name_input = self.query_one("#group-name-input", Input)
        name_input.value = group_name
        if not group_name:
            name_input.focus()

        checkbox_container = self.query_one("#group-repo-checkboxes", Container)
        checkbox_container.remove_children()

        all_repos = self._get_all_repos()
        selected = set(selected_repos or [])

        if not all_repos:
            checkbox_container.mount(Static(
                "[dim italic]No repos available. Add a GitHub account and select repos first.[/dim italic]"
            ))
            return

        for repo in all_repos:
            checked = repo in selected
            check_mark = "[green]X[/green]" if checked else "[ ]"
            btn = Button(
                f"{check_mark} {repo}",
                id=f"group-repo-toggle-{repo.replace('/', '--')}",
                classes="group-repo-btn",
            )
            if checked:
                btn.add_class("repo-checked")
            checkbox_container.mount(btn)

    def _hide_group_create_form(self) -> None:
        self._creating_group = False
        self._editing_group = None
        container = self.query_one("#group-create-container")
        container.remove_class("visible")
        self.query_one("#group-name-input", Input).value = ""
        self.query_one("#group-repo-checkboxes", Container).remove_children()

    def _save_group(self) -> None:
        name = self.query_one("#group-name-input", Input).value.strip()
        if not name:
            return

        selected_repos = []
        checkbox_container = self.query_one("#group-repo-checkboxes", Container)
        for btn in checkbox_container.query(Button):
            if btn.has_class("repo-checked"):
                repo_id = (btn.id or "").replace("group-repo-toggle-", "").replace("--", "/")
                selected_repos.append(repo_id)

        from pm.auth.credentials import add_project_group
        if self._editing_group and self._editing_group != name:
            from pm.auth.credentials import remove_project_group
            remove_project_group(self._editing_group)
        add_project_group(name, selected_repos)

        self._hide_group_create_form()
        self._load_project_groups()

    # -- Add Account Flow --------------------------------------------------

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
            if btn_id.startswith("remove-group-"):
                group_name = btn_id[len("remove-group-"):]
                self._remove_group(group_name)
            else:
                account_id = btn_id[len("remove-"):]
                self._confirm_remove_account(account_id)
        elif btn_id.startswith("rename-ok-"):
            account_id = btn_id[len("rename-ok-"):]
            self._do_rename(account_id)
        elif btn_id.startswith("rename-cancel-"):
            account_id = btn_id[len("rename-cancel-"):]
            self._cancel_rename(account_id)
        elif btn_id.startswith("rename-") and not btn_id.startswith("rename-ok-") and not btn_id.startswith("rename-cancel-") and not btn_id.startswith("rename-input-"):
            account_id = btn_id[len("rename-"):]
            self._start_rename(account_id)
        elif btn_id == "confirm-remove-yes":
            self._do_remove_confirmed()
        elif btn_id == "confirm-remove-no":
            self._cancel_remove()
        elif btn_id == "create-group-btn":
            self._show_group_create_form()
        elif btn_id == "save-group-btn":
            self._save_group()
        elif btn_id == "cancel-group-btn":
            self._hide_group_create_form()
        elif btn_id.startswith("edit-group-"):
            group_name = btn_id[len("edit-group-"):]
            self._edit_group(group_name)
        elif btn_id.startswith("group-repo-toggle-"):
            self._toggle_group_repo(event.button)

    def _toggle_group_repo(self, btn: Button) -> None:
        repo_id = (btn.id or "").replace("group-repo-toggle-", "").replace("--", "/")
        if btn.has_class("repo-checked"):
            btn.remove_class("repo-checked")
            btn.label = f"[ ] {repo_id}"
        else:
            btn.add_class("repo-checked")
            btn.label = f"[green]X[/green] {repo_id}"

    def _edit_group(self, group_name: str) -> None:
        from pm.auth.credentials import load_project_groups
        groups = load_project_groups()
        repos = groups.get(group_name, [])
        self._editing_group = group_name
        self._show_group_create_form(group_name=group_name, selected_repos=repos)

    def _remove_group(self, group_name: str) -> None:
        from pm.auth.credentials import remove_project_group
        remove_project_group(group_name)
        self._load_project_groups()

    def _start_add_account(self) -> None:
        self._adding_account = True
        status = self.query_one("#token-status", Static)

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

    def _verify_token_sync(self, token: str) -> tuple:
        from pm.auth.github_oauth import validate_token
        return validate_token(token), token

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        worker_name = event.worker.name or ""

        if worker_name.startswith("count_repos_"):
            if event.state == WorkerState.SUCCESS:
                result = event.worker.result
                if result:
                    account_id, count = result
                    for item in self.query(AccountItem):
                        if item.account_id == account_id:
                            item.update_header(repo_count=count)
                            break
            return

        if worker_name != "verify_token":
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

            self._open_repo_selector(account_id)

        elif event.state == WorkerState.ERROR:
            self._verifying = False
            self.query_one("#token-status", Static).update(
                "[red]Error verifying token. Please try again.[/red]"
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "token-input":
            self._verify_and_save_token()
        elif event.input.id and event.input.id.startswith("rename-input-"):
            account_id = event.input.id[len("rename-input-"):]
            self._do_rename(account_id)
        elif event.input.id == "group-name-input":
            self._save_group()

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id or ""
        if input_id == "general-agent-input":
            value = event.value.strip()
            if value:
                from pm.config.settings import update_setting
                update_setting("general", "default_agent", value)
        elif input_id == "general-poll-input":
            value = event.value.strip()
            if value:
                from pm.config.settings import update_setting
                update_setting("general", "poll_interval", value)
        elif input_id == "overlay-count-input":
            try:
                value = int(event.value.strip())
                from pm.config.settings import update_setting
                update_setting("overlay", "show_count", value)
            except (ValueError, TypeError):
                pass
        elif input_id == "overlay-opacity-input":
            try:
                value = max(0, min(100, int(event.value.strip())))
                from pm.config.settings import update_setting
                update_setting("overlay", "opacity", value)
            except (ValueError, TypeError):
                pass

    # -- Rename ------------------------------------------------------------

    def _start_rename(self, account_id: str) -> None:
        for item in self.query(AccountItem):
            if item.account_id == account_id:
                item.show_rename_row()
                break

    def _do_rename(self, account_id: str) -> None:
        try:
            inp = self.query_one(f"#rename-input-{account_id}", Input)
            new_name = inp.value.strip()
        except Exception:
            return
        if not new_name:
            return

        from pm.auth.credentials import rename_account
        rename_account(account_id, new_name)

        for item in self.query(AccountItem):
            if item.account_id == account_id:
                item.update_header(display_name=new_name)
                item.hide_rename_row()
                break

        for acc in self._accounts:
            if acc["id"] == account_id:
                acc["display_name"] = new_name
                break

    def _cancel_rename(self, account_id: str) -> None:
        for item in self.query(AccountItem):
            if item.account_id == account_id:
                item.hide_rename_row()
                break

    # -- Remove ------------------------------------------------------------

    def _confirm_remove_account(self, account_id: str) -> None:
        self._pending_remove_id = account_id
        display = account_id
        for acc in self._accounts:
            if acc["id"] == account_id:
                display = f"{acc['display_name']} ({acc['username']})"
                break

        hint = self.query_one("#no-accounts-hint", Static)
        hint.update(
            f"[bold red]Remove account {display}?[/bold red]\n"
            f"This will delete the token and all settings for this account."
        )
        container = self.query_one("#accounts-list", Container)
        with container.batch():
            row = Horizontal(id="confirm-remove-row")
            container.mount(row)
            row.mount(Button("Yes, Remove", id="confirm-remove-yes", variant="error"))
            row.mount(Button("Cancel", id="confirm-remove-no"))

    def _do_remove_confirmed(self) -> None:
        account_id = getattr(self, "_pending_remove_id", None)
        if account_id:
            from pm.auth.credentials import remove_account
            remove_account(account_id)
        self._pending_remove_id = None
        self._cleanup_confirm_row()
        self._load_accounts()
        self.post_message(self.AccountsChanged())

    def _cancel_remove(self) -> None:
        self._pending_remove_id = None
        self._cleanup_confirm_row()
        hint = self.query_one("#no-accounts-hint", Static)
        hint.update("")

    def _cleanup_confirm_row(self) -> None:
        try:
            row = self.query_one("#confirm-remove-row", Horizontal)
            row.remove()
        except Exception:
            pass

    # -- Repo Selector -----------------------------------------------------

    def _open_repo_selector(self, account_id: str) -> None:
        from pm.tui.screens.repo_selector import RepoSelectorScreen
        account_data = None
        for acc in self._accounts:
            if acc["id"] == account_id:
                account_data = acc
                break
        if account_data is None:
            from pm.auth.credentials import list_accounts
            self._accounts = list_accounts()
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

    # -- Overlay Settings Save ---------------------------------------------

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "overlay-enabled-switch":
            from pm.config.settings import update_setting
            update_setting("overlay", "enabled", event.value)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "overlay-position-select":
            from pm.config.settings import update_setting
            update_setting("overlay", "position", str(event.value))

    # -- Navigation --------------------------------------------------------

    def action_go_back(self) -> None:
        if self._adding_account:
            self._cancel_add_account()
            return
        if self._creating_group:
            self._hide_group_create_form()
            return
        self.dismiss()
