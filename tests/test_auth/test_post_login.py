from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
import yaml

from pm.auth.github_oauth import _post_login_discover


class TestPostLoginDiscover:
    @patch("pm.auth.github_oauth.discover_repos")
    def test_no_repos_found(self, mock_discover):
        mock_discover.return_value = []
        # Should not crash
        _post_login_discover("personal", "ghp_test", "user")

    @patch("pm.auth.github_oauth.click.confirm")
    @patch("pm.auth.github_oauth.discover_repos")
    def test_shows_discovered_repos(self, mock_discover, mock_confirm):
        mock_discover.return_value = [
            {
                "name": "repo1",
                "full_name": "user/repo1",
                "private": False,
                "owner": "user",
            },
            {
                "name": "repo2",
                "full_name": "org/repo2",
                "private": True,
                "owner": "org",
            },
        ]
        mock_confirm.return_value = False  # Decline config generation

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                _post_login_discover("personal", "ghp_test", "user")

        mock_discover.assert_called_once_with("ghp_test")

    @patch("pm.config.loader.generate_config_from_repos")
    @patch("pm.auth.github_oauth.click.confirm")
    @patch("pm.auth.github_oauth.discover_repos")
    def test_generates_config_when_accepted(self, mock_discover, mock_confirm, mock_gen):
        mock_discover.return_value = [
            {
                "name": "repo1",
                "full_name": "user/repo1",
                "private": False,
                "owner": "user",
            },
        ]
        mock_confirm.return_value = True

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                _post_login_discover("personal", "ghp_test", "user")

        mock_gen.assert_called_once()

    @patch("pm.auth.github_oauth.click.confirm")
    @patch("pm.auth.github_oauth.discover_repos")
    def test_skips_config_when_declined(self, mock_discover, mock_confirm):
        mock_discover.return_value = [
            {
                "name": "repo1",
                "full_name": "user/repo1",
                "private": False,
                "owner": "user",
            },
        ]
        mock_confirm.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                _post_login_discover("personal", "ghp_test", "user")

    @patch("pm.auth.github_oauth.click.confirm")
    @patch("pm.auth.github_oauth.discover_repos")
    def test_asks_overwrite_when_config_exists(self, mock_discover, mock_confirm):
        mock_discover.return_value = [
            {
                "name": "repo1",
                "full_name": "user/repo1",
                "private": False,
                "owner": "user",
            },
        ]
        mock_confirm.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake existing config
            ppm_dir = Path(tmpdir) / ".ppm"
            ppm_dir.mkdir()
            config_file = ppm_dir / "config.yaml"
            config_file.write_text("existing config")

            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                _post_login_discover("personal", "ghp_test", "user")

        mock_confirm.assert_called_once()
        confirm_msg = str(mock_confirm.call_args)
        assert "overwrite" in confirm_msg.lower() or "Overwrite" in confirm_msg
