from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pm.auth.github_oauth import discover_repos


class TestDiscoverRepos:
    @patch("pm.auth.github_oauth.httpx.get")
    def test_discovers_repos(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "name": "repo1",
                "full_name": "user/repo1",
                "description": "A test repo",
                "default_branch": "main",
                "private": False,
                "html_url": "https://github.com/user/repo1",
                "owner": {"login": "user"},
                "pushed_at": "2026-03-25T10:00:00Z",
            },
            {
                "name": "repo2",
                "full_name": "user/repo2",
                "description": None,
                "default_branch": "develop",
                "private": True,
                "html_url": "https://github.com/user/repo2",
                "owner": {"login": "user"},
                "pushed_at": "2026-03-24T10:00:00Z",
            },
        ]
        mock_get.return_value = mock_resp

        repos = discover_repos("ghp_test")
        assert len(repos) == 2
        assert repos[0]["full_name"] == "user/repo1"
        assert repos[0]["private"] is False
        assert repos[0]["owner"] == "user"
        assert repos[1]["full_name"] == "user/repo2"
        assert repos[1]["private"] is True
        assert repos[1]["description"] == ""

    @patch("pm.auth.github_oauth.httpx.get")
    def test_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp

        repos = discover_repos("ghp_test")
        assert repos == []

    @patch("pm.auth.github_oauth.httpx.get")
    def test_api_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        repos = discover_repos("ghp_bad")
        assert repos == []

    @patch("pm.auth.github_oauth.httpx.get")
    def test_network_error(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        repos = discover_repos("ghp_any")
        assert repos == []

    @patch("pm.auth.github_oauth.httpx.get")
    def test_max_repos_limit(self, mock_get):
        # Return 5 repos per page
        page_data = [
            {
                "name": f"repo{i}",
                "full_name": f"user/repo{i}",
                "description": "",
                "default_branch": "main",
                "private": False,
                "html_url": f"https://github.com/user/repo{i}",
                "owner": {"login": "user"},
                "pushed_at": "2026-03-25T10:00:00Z",
            }
            for i in range(5)
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = page_data
        mock_get.return_value = mock_resp

        repos = discover_repos("ghp_test", max_repos=3)
        assert len(repos) == 3

    @patch("pm.auth.github_oauth.httpx.get")
    def test_repos_have_correct_fields(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "name": "my-app",
                "full_name": "org/my-app",
                "description": "My application",
                "default_branch": "main",
                "private": True,
                "html_url": "https://github.com/org/my-app",
                "owner": {"login": "org"},
                "pushed_at": "2026-03-25T10:00:00Z",
            },
        ]
        mock_get.return_value = mock_resp

        repos = discover_repos("ghp_test")
        assert len(repos) == 1
        repo = repos[0]
        assert repo["name"] == "my-app"
        assert repo["full_name"] == "org/my-app"
        assert repo["description"] == "My application"
        assert repo["default_branch"] == "main"
        assert repo["private"] is True
        assert repo["html_url"] == "https://github.com/org/my-app"
        assert repo["owner"] == "org"

    @patch("pm.auth.github_oauth.httpx.get")
    def test_pagination(self, mock_get):
        """Should fetch multiple pages if needed."""
        page1 = [
            {
                "name": f"repo{i}",
                "full_name": f"user/repo{i}",
                "description": "",
                "default_branch": "main",
                "private": False,
                "html_url": f"https://github.com/user/repo{i}",
                "owner": {"login": "user"},
                "pushed_at": "2026-03-25T10:00:00Z",
            }
            for i in range(30)
        ]
        page2 = []  # Empty page signals end

        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = page1

        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = page2

        mock_get.side_effect = [mock_resp1, mock_resp2]

        repos = discover_repos("ghp_test", max_repos=30)
        assert len(repos) == 30
