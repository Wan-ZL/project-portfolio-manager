from __future__ import annotations

import os
import stat
from pathlib import Path

import yaml


CREDENTIALS_PATH = Path.home() / ".ppm" / "credentials.yaml"


def load_credentials(path: Path | None = None) -> dict:
    cred_path = path or CREDENTIALS_PATH
    if not cred_path.exists():
        return {"accounts": {}}
    with open(cred_path) as f:
        raw = yaml.safe_load(f)
    if raw is None:
        return {"accounts": {}}
    if "accounts" not in raw:
        raw["accounts"] = {}
    return raw


def save_credentials(data: dict, path: Path | None = None) -> None:
    cred_path = path or CREDENTIALS_PATH
    cred_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cred_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    # Restrict file permissions to owner only (0o600)
    os.chmod(cred_path, stat.S_IRUSR | stat.S_IWUSR)


def get_token(account: str = "personal", path: Path | None = None) -> str | None:
    creds = load_credentials(path)
    account_data = creds.get("accounts", {}).get(account, {})
    return account_data.get("token")


def get_username(account: str = "personal", path: Path | None = None) -> str | None:
    creds = load_credentials(path)
    account_data = creds.get("accounts", {}).get(account, {})
    return account_data.get("username")


def get_selected_repos(account: str, path: Path | None = None) -> list[str]:
    creds = load_credentials(path)
    account_data = creds.get("accounts", {}).get(account, {})
    return account_data.get("selected_repos", [])


def save_selected_repos(account: str, repos: list[str], path: Path | None = None) -> None:
    creds = load_credentials(path)
    if account in creds.get("accounts", {}):
        creds["accounts"][account]["selected_repos"] = repos
        save_credentials(creds, path)


def save_account(account: str, token: str, username: str, path: Path | None = None) -> None:
    creds = load_credentials(path)
    existing = creds["accounts"].get(account, {})
    creds["accounts"][account] = {
        "token": token,
        "username": username,
        "display_name": existing.get("display_name", ""),
        "selected_repos": existing.get("selected_repos", []),
    }
    save_credentials(creds, path)


def remove_account(account: str, path: Path | None = None) -> None:
    creds = load_credentials(path)
    if account in creds.get("accounts", {}):
        del creds["accounts"][account]
        save_credentials(creds, path)


def rename_account(account: str, new_name: str, path: Path | None = None) -> None:
    creds = load_credentials(path)
    if account in creds.get("accounts", {}):
        creds["accounts"][account]["display_name"] = new_name
        save_credentials(creds, path)


def get_display_name(account: str, path: Path | None = None) -> str:
    creds = load_credentials(path)
    account_data = creds.get("accounts", {}).get(account, {})
    name = account_data.get("display_name", "")
    if name:
        return name
    # Generate default based on account id number
    num = account.replace("account-", "")
    return f"GitHub {num}"


def list_accounts(path: Path | None = None) -> list[dict]:
    creds = load_credentials(path)
    accounts = creds.get("accounts", {})
    result = []
    for name, data in accounts.items():
        num = name.replace("account-", "")
        display = data.get("display_name", "") or f"GitHub {num}"
        result.append({
            "id": name,
            "username": data.get("username", "unknown"),
            "has_token": bool(data.get("token")),
            "selected_repos": data.get("selected_repos", []),
            "display_name": display,
        })
    return result


def next_account_id(path: Path | None = None) -> str:
    creds = load_credentials(path)
    accounts = creds.get("accounts", {})
    idx = 1
    while f"account-{idx}" in accounts:
        idx += 1
    return f"account-{idx}"


def load_project_groups(path: Path | None = None) -> dict[str, list[str]]:
    creds = load_credentials(path)
    groups = creds.get("project_groups", {})
    result = {}
    for name, data in groups.items():
        if isinstance(data, dict):
            result[name] = data.get("repos", [])
        elif isinstance(data, list):
            result[name] = data
        else:
            result[name] = []
    return result


def save_project_groups(groups: dict[str, list[str]], path: Path | None = None) -> None:
    creds = load_credentials(path)
    creds["project_groups"] = {
        name: {"repos": repos} for name, repos in groups.items()
    }
    save_credentials(creds, path)


def add_project_group(name: str, repos: list[str], path: Path | None = None) -> None:
    groups = load_project_groups(path)
    groups[name] = repos
    save_project_groups(groups, path)


def remove_project_group(name: str, path: Path | None = None) -> None:
    groups = load_project_groups(path)
    if name in groups:
        del groups[name]
        save_project_groups(groups, path)


def update_project_group(name: str, repos: list[str], path: Path | None = None) -> None:
    groups = load_project_groups(path)
    groups[name] = repos
    save_project_groups(groups, path)
