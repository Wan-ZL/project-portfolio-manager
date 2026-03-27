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


def save_account(account: str, token: str, username: str, path: Path | None = None) -> None:
    creds = load_credentials(path)
    creds["accounts"][account] = {
        "token": token,
        "username": username,
    }
    save_credentials(creds, path)
