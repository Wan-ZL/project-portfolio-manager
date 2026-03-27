from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, PropertyMock

import pytest

from pm.ai.demo import is_demo_mode


class TestIsDemoMode:
    @patch("pm.config.loader.DEFAULT_CONFIG_PATH", new=Path("/nonexistent/path/config.yaml"))
    @patch("pm.auth.credentials.load_credentials")
    def test_demo_when_no_credentials_no_config(self, mock_creds):
        mock_creds.return_value = {"accounts": {}}
        assert is_demo_mode() is True

    @patch("pm.auth.credentials.load_credentials")
    def test_not_demo_when_credentials_exist(self, mock_creds):
        mock_creds.return_value = {
            "accounts": {
                "personal": {"token": "ghp_test123", "username": "user"},
            }
        }
        assert is_demo_mode() is False

    @patch("pm.config.loader.load_config")
    @patch("pm.auth.credentials.load_credentials")
    def test_demo_when_no_creds_and_placeholder_config(self, mock_creds, mock_load_cfg, tmp_path):
        mock_creds.return_value = {"accounts": {}}

        from pm.config.models import PMConfig, ProjectConfig
        mock_load_cfg.return_value = PMConfig(
            projects={
                "my-project": ProjectConfig(
                    account="personal",
                    repos=["your-username/your-repo"],
                )
            }
        )

        config_file = tmp_path / "config.yaml"
        config_file.write_text("dummy")
        with patch("pm.config.loader.DEFAULT_CONFIG_PATH", new=config_file):
            assert is_demo_mode() is True

    @patch("pm.config.loader.load_config")
    @patch("pm.auth.credentials.load_credentials")
    def test_not_demo_when_no_creds_but_real_projects(self, mock_creds, mock_load_cfg, tmp_path):
        mock_creds.return_value = {"accounts": {}}

        from pm.config.models import PMConfig, ProjectConfig
        mock_load_cfg.return_value = PMConfig(
            projects={
                "website": ProjectConfig(
                    account="personal",
                    repos=["zelin/my-website"],
                )
            }
        )

        config_file = tmp_path / "config.yaml"
        config_file.write_text("dummy")
        with patch("pm.config.loader.DEFAULT_CONFIG_PATH", new=config_file):
            assert is_demo_mode() is False

    @patch("pm.auth.credentials.load_credentials")
    def test_not_demo_with_any_credential_account(self, mock_creds):
        """Even a single account in credentials should disable demo mode."""
        mock_creds.return_value = {
            "accounts": {
                "company": {"token": "ghp_company", "username": "companyuser"},
            }
        }
        assert is_demo_mode() is False
