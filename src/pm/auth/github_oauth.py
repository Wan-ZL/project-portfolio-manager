from __future__ import annotations

import shutil
import subprocess

import click
import httpx

from pm.auth.credentials import save_account

TOKEN_SCOPES_URL = "https://github.com/settings/tokens/new?scopes=repo,read:org&description=PPM+Portfolio+Manager"
GITHUB_API_URL = "https://api.github.com"


def validate_token(token: str) -> dict | None:
    """Validate a GitHub token and return user info.

    Returns dict with 'login' and 'public_repos' on success, None on failure.
    """
    try:
        resp = httpx.get(
            f"{GITHUB_API_URL}/user",
            headers={"Authorization": f"token {token}", "Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "login": data.get("login", ""),
                "public_repos": data.get("public_repos", 0),
            }
        return None
    except httpx.HTTPError:
        return None


def get_gh_token() -> str | None:
    """Try to get token from gh CLI."""
    gh_path = shutil.which("gh")
    if not gh_path:
        return None
    try:
        result = subprocess.run(
            [gh_path, "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            token = result.stdout.strip()
            if token:
                return token
        return None
    except (subprocess.TimeoutExpired, OSError):
        return None


def login_with_gh(account: str) -> bool:
    """Login using gh CLI token. Returns True on success."""
    token = get_gh_token()
    if token is None:
        return False

    click.echo("Detected gh CLI...")
    user_info = validate_token(token)
    if user_info is None:
        click.echo("Token from gh CLI is invalid or expired.")
        return False

    username = user_info["login"]
    click.echo(f'GitHub token acquired (via gh auth)')
    click.echo(f'Verified: user "{username}"')
    save_account(account, token, username)
    click.echo(f"Token saved to ~/.ppm/credentials.yaml")
    click.echo(f'Account "{account}" configured!')
    return True


def login_with_manual_token(account: str) -> bool:
    """Guide user to create and paste a Personal Access Token. Returns True on success."""
    click.echo("gh CLI not detected.\n")
    click.echo("Follow these steps to get a GitHub Token:")
    click.echo(f"  1. Open in browser: {TOKEN_SCOPES_URL}")
    click.echo("  2. Token name: PPM Portfolio Manager")
    click.echo("  3. Select scopes: repo, read:org")
    click.echo('  4. Click "Generate token"')
    click.echo("  5. Copy the generated token (ghp_xxxxx)\n")

    token = click.prompt("Paste your GitHub Token", hide_input=True)
    if not token or not token.strip():
        click.echo("No token provided.")
        return False

    token = token.strip()
    user_info = validate_token(token)
    if user_info is None:
        click.echo("Token validation failed. Please check the token and try again.")
        return False

    username = user_info["login"]
    click.echo(f'Token verified! User: "{username}"')
    save_account(account, token, username)
    click.echo("Saved to ~/.ppm/credentials.yaml")
    click.echo(f'Account "{account}" configured!\n')
    click.echo("Next step: edit ~/.ppm/config.yaml to add your projects")
    return True
