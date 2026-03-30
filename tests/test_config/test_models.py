from __future__ import annotations

import pytest

from pm.config.models import AccountConfig, PMConfig


class TestAccountConfig:
    def test_token_env_optional(self):
        """token_env should default to empty string."""
        account = AccountConfig()
        assert account.token_env == ""
        assert account.default is False

    def test_token_source_credentials(self):
        account = AccountConfig(token_source="credentials", default=True)
        assert account.token_source == "credentials"
        assert account.default is True
        assert account.token_env == ""

    def test_token_env_still_works(self):
        account = AccountConfig(token_env="GITHUB_TOKEN", default=True)
        assert account.token_env == "GITHUB_TOKEN"
        assert account.token_source == ""

    def test_both_token_env_and_source(self):
        account = AccountConfig(token_env="GH_TOKEN", token_source="credentials")
        assert account.token_env == "GH_TOKEN"
        assert account.token_source == "credentials"


class TestPMConfigWithCredentials:
    def test_config_with_credentials_account(self):
        data = {
            "accounts": {
                "personal": {
                    "token_source": "credentials",
                    "default": True,
                }
            },
            "projects": {
                "my-proj": {
                    "account": "personal",
                    "repos": ["user/repo"],
                }
            },
        }
        cfg = PMConfig.model_validate(data)
        assert cfg.accounts["personal"].token_source == "credentials"
        assert cfg.accounts["personal"].token_env == ""
        assert cfg.accounts["personal"].default is True

    def test_backward_compatible_with_token_env(self):
        data = {
            "accounts": {
                "personal": {
                    "token_env": "GITHUB_TOKEN",
                    "default": True,
                }
            },
        }
        cfg = PMConfig.model_validate(data)
        assert cfg.accounts["personal"].token_env == "GITHUB_TOKEN"
        assert cfg.accounts["personal"].token_source == ""
