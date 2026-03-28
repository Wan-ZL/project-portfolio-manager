from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pm.auth.github_oauth import (
    get_gh_token,
    login_with_gh,
    login_with_manual_token,
    validate_token,
)


@pytest.fixture
def cred_file(tmp_path):
    return tmp_path / "credentials.yaml"


class TestValidateToken:
    @patch("pm.auth.github_oauth.httpx.get")
    def test_valid_token(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "testuser", "public_repos": 10}
        mock_get.return_value = mock_resp

        result = validate_token("ghp_valid")
        assert result is not None
        assert result["login"] == "testuser"
        assert result["public_repos"] == 10
        mock_get.assert_called_once()

    @patch("pm.auth.github_oauth.httpx.get")
    def test_invalid_token(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        result = validate_token("ghp_invalid")
        assert result is None

    @patch("pm.auth.github_oauth.httpx.get")
    def test_network_error(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        result = validate_token("ghp_any")
        assert result is None


class TestGetGhToken:
    @patch("pm.auth.github_oauth.shutil.which")
    def test_gh_not_installed(self, mock_which):
        mock_which.return_value = None
        assert get_gh_token() is None

    @patch("pm.auth.github_oauth.subprocess.run")
    @patch("pm.auth.github_oauth.shutil.which")
    def test_gh_returns_token(self, mock_which, mock_run):
        mock_which.return_value = "/usr/local/bin/gh"
        mock_run.return_value = MagicMock(returncode=0, stdout="ghp_abc123\n")

        result = get_gh_token()
        assert result == "ghp_abc123"

    @patch("pm.auth.github_oauth.subprocess.run")
    @patch("pm.auth.github_oauth.shutil.which")
    def test_gh_auth_fails(self, mock_which, mock_run):
        mock_which.return_value = "/usr/local/bin/gh"
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = get_gh_token()
        assert result is None

    @patch("pm.auth.github_oauth.subprocess.run")
    @patch("pm.auth.github_oauth.shutil.which")
    def test_gh_empty_output(self, mock_which, mock_run):
        mock_which.return_value = "/usr/local/bin/gh"
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = get_gh_token()
        assert result is None

    @patch("pm.auth.github_oauth.subprocess.run")
    @patch("pm.auth.github_oauth.shutil.which")
    def test_gh_timeout(self, mock_which, mock_run):
        import subprocess
        mock_which.return_value = "/usr/local/bin/gh"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=10)

        result = get_gh_token()
        assert result is None


class TestLoginWithGh:
    @patch("pm.auth.github_oauth.save_account")
    @patch("pm.auth.github_oauth.validate_token")
    @patch("pm.auth.github_oauth.get_gh_token")
    def test_success(self, mock_get_gh, mock_validate, mock_save):
        mock_get_gh.return_value = "ghp_fromgh"
        mock_validate.return_value = {"login": "ghuser", "public_repos": 5}

        result = login_with_gh("personal")
        assert result is True
        mock_save.assert_called_once_with("personal", "ghp_fromgh", "ghuser")

    @patch("pm.auth.github_oauth.get_gh_token")
    def test_gh_not_available(self, mock_get_gh):
        mock_get_gh.return_value = None
        result = login_with_gh("personal")
        assert result is False

    @patch("pm.auth.github_oauth.validate_token")
    @patch("pm.auth.github_oauth.get_gh_token")
    def test_invalid_gh_token(self, mock_get_gh, mock_validate):
        mock_get_gh.return_value = "ghp_expired"
        mock_validate.return_value = None

        result = login_with_gh("personal")
        assert result is False


class TestLoginWithManualToken:
    @patch("pm.auth.github_oauth.save_account")
    @patch("pm.auth.github_oauth.validate_token")
    @patch("pm.auth.github_oauth.click.prompt")
    def test_success(self, mock_prompt, mock_validate, mock_save):
        mock_prompt.return_value = "ghp_manual123"
        mock_validate.return_value = {"login": "manualuser", "public_repos": 3}

        result = login_with_manual_token("personal")
        assert result is True
        mock_save.assert_called_once_with("personal", "ghp_manual123", "manualuser")

    @patch("pm.auth.github_oauth.validate_token")
    @patch("pm.auth.github_oauth.click.prompt")
    def test_invalid_token(self, mock_prompt, mock_validate):
        mock_prompt.return_value = "invalid_token"
        mock_validate.return_value = None

        result = login_with_manual_token("personal")
        assert result is False

    @patch("pm.auth.github_oauth.click.prompt")
    def test_empty_input(self, mock_prompt):
        mock_prompt.return_value = ""
        result = login_with_manual_token("personal")
        assert result is False


