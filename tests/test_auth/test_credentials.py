from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

import pytest
import yaml

from pm.auth.credentials import (
    get_token,
    get_username,
    load_credentials,
    save_account,
    save_credentials,
)


@pytest.fixture
def cred_file(tmp_path):
    return tmp_path / "credentials.yaml"


class TestLoadCredentials:
    def test_nonexistent_file(self, tmp_path):
        path = tmp_path / "nonexistent.yaml"
        result = load_credentials(path)
        assert result == {"accounts": {}}

    def test_empty_file(self, cred_file):
        cred_file.write_text("")
        result = load_credentials(cred_file)
        assert result == {"accounts": {}}

    def test_valid_file(self, cred_file):
        data = {
            "accounts": {
                "personal": {"token": "ghp_test123", "username": "testuser"},
            }
        }
        cred_file.write_text(yaml.dump(data))
        result = load_credentials(cred_file)
        assert result["accounts"]["personal"]["token"] == "ghp_test123"
        assert result["accounts"]["personal"]["username"] == "testuser"

    def test_file_without_accounts_key(self, cred_file):
        cred_file.write_text(yaml.dump({"other": "data"}))
        result = load_credentials(cred_file)
        assert "accounts" in result
        assert result["accounts"] == {}


class TestSaveCredentials:
    def test_creates_file(self, cred_file):
        data = {"accounts": {"personal": {"token": "ghp_abc", "username": "user1"}}}
        save_credentials(data, cred_file)
        assert cred_file.exists()

    def test_file_permissions(self, cred_file):
        data = {"accounts": {"personal": {"token": "ghp_abc", "username": "user1"}}}
        save_credentials(data, cred_file)
        mode = os.stat(cred_file).st_mode
        assert mode & stat.S_IRUSR  # owner can read
        assert mode & stat.S_IWUSR  # owner can write
        assert not (mode & stat.S_IRGRP)  # group cannot read
        assert not (mode & stat.S_IROTH)  # others cannot read

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "creds.yaml"
        data = {"accounts": {}}
        save_credentials(data, path)
        assert path.exists()

    def test_roundtrip(self, cred_file):
        data = {
            "accounts": {
                "personal": {"token": "ghp_roundtrip", "username": "roundtrip_user"},
                "company": {"token": "ghp_company", "username": "company_user"},
            }
        }
        save_credentials(data, cred_file)
        loaded = load_credentials(cred_file)
        assert loaded["accounts"]["personal"]["token"] == "ghp_roundtrip"
        assert loaded["accounts"]["company"]["username"] == "company_user"


class TestGetToken:
    def test_get_existing_token(self, cred_file):
        data = {"accounts": {"personal": {"token": "ghp_mytoken", "username": "me"}}}
        cred_file.write_text(yaml.dump(data))
        assert get_token("personal", cred_file) == "ghp_mytoken"

    def test_get_missing_account(self, cred_file):
        data = {"accounts": {"personal": {"token": "ghp_mytoken", "username": "me"}}}
        cred_file.write_text(yaml.dump(data))
        assert get_token("nonexistent", cred_file) is None

    def test_get_from_empty_file(self, tmp_path):
        path = tmp_path / "empty.yaml"
        assert get_token("personal", path) is None


class TestGetUsername:
    def test_get_existing_username(self, cred_file):
        data = {"accounts": {"personal": {"token": "ghp_tok", "username": "zelin"}}}
        cred_file.write_text(yaml.dump(data))
        assert get_username("personal", cred_file) == "zelin"

    def test_get_missing_account(self, cred_file):
        data = {"accounts": {"personal": {"token": "ghp_tok", "username": "zelin"}}}
        cred_file.write_text(yaml.dump(data))
        assert get_username("nonexistent", cred_file) is None


class TestSaveAccount:
    def test_save_new_account(self, cred_file):
        save_account("personal", "ghp_new", "newuser", cred_file)
        loaded = load_credentials(cred_file)
        assert loaded["accounts"]["personal"]["token"] == "ghp_new"
        assert loaded["accounts"]["personal"]["username"] == "newuser"

    def test_save_overwrites_existing(self, cred_file):
        save_account("personal", "ghp_old", "olduser", cred_file)
        save_account("personal", "ghp_new", "newuser", cred_file)
        loaded = load_credentials(cred_file)
        assert loaded["accounts"]["personal"]["token"] == "ghp_new"
        assert loaded["accounts"]["personal"]["username"] == "newuser"

    def test_save_multiple_accounts(self, cred_file):
        save_account("personal", "ghp_p", "puser", cred_file)
        save_account("company", "ghp_c", "cuser", cred_file)
        loaded = load_credentials(cred_file)
        assert "personal" in loaded["accounts"]
        assert "company" in loaded["accounts"]
        assert loaded["accounts"]["personal"]["token"] == "ghp_p"
        assert loaded["accounts"]["company"]["token"] == "ghp_c"

    def test_save_sets_file_permissions(self, cred_file):
        save_account("personal", "ghp_test", "testuser", cred_file)
        mode = os.stat(cred_file).st_mode
        assert not (mode & stat.S_IRGRP)
        assert not (mode & stat.S_IROTH)
