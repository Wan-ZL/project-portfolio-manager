from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pm.config.models import PMConfig, ProjectConfig
from pm.github.pr import EnhancedPR
from pm.tui.polling import PollingData, PollingUpdate, SmartPoller, _parse_pr
from pm.tui.widgets.project_list import ProjectInfo


def _make_config() -> PMConfig:
    return PMConfig(
        projects={
            "proj-a": ProjectConfig(account="personal", repos=["owner/repo-a", "owner/repo-b"]),
            "proj-b": ProjectConfig(account="personal", repos=["owner/repo-c"]),
        },
    )


def _make_creds() -> dict:
    return {
        "accounts": {
            "personal": {"token": "ghp_test123", "username": "testuser"},
        }
    }


def _make_pr(repo: str, number: int, title: str = "PR") -> EnhancedPR:
    return EnhancedPR(
        repo_id=repo,
        number=number,
        title=title,
        state="open",
        author="testuser",
        created_at=datetime(2026, 3, 25),
        updated_at=datetime(2026, 3, 25),
    )


def _mock_response(json_data, status_code=200, rate_limit=4500):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.headers = {"x-ratelimit-remaining": str(rate_limit)}
    return resp


class TestSmartPollerInit:
    def test_repos_extracted_from_config(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        assert "owner/repo-a" in poller.repos
        assert "owner/repo-b" in poller.repos
        assert "owner/repo-c" in poller.repos
        assert len(poller.repos) == 3

    def test_no_config(self):
        poller = SmartPoller(credentials=_make_creds(), config=None)
        assert poller.repos == []

    def test_no_credentials(self):
        poller = SmartPoller(credentials={}, config=_make_config())
        assert poller.repos == ["owner/repo-a", "owner/repo-b", "owner/repo-c"]

    def test_initial_state(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        assert poller.poll_count == 0
        assert poller.rate_limit_remaining == 5000
        assert not poller.is_rate_limited
        assert not poller.is_rate_critical


class TestRoundRobin:
    def test_round_robin_cycles_through_repos(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        assert poller._repo_index == 0
        indices = []
        for _ in range(6):
            idx = poller._repo_index
            indices.append(idx)
            poller._repo_index = (poller._repo_index + 1) % len(poller._repos)
        assert indices == [0, 1, 2, 0, 1, 2]

    def test_set_repos(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller.set_repos(["a/b", "c/d"])
        assert poller.repos == ["a/b", "c/d"]
        assert poller._repo_index == 0

    def test_set_repos_resets_index_if_out_of_bounds(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._repo_index = 2
        poller.set_repos(["a/b"])
        assert poller._repo_index == 0


class TestTimingLogic:
    @pytest.mark.asyncio
    async def test_first_tick_does_heavy_refresh(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._last_heavy_refresh = 0
        poller._last_full_refresh = 0

        with patch.object(poller, "_heavy_refresh", return_value=PollingUpdate(projects_changed=True)) as mock:
            result = await poller.tick()
            mock.assert_called_once()
            assert result is not None
            assert result.projects_changed

    @pytest.mark.asyncio
    async def test_tick_does_full_refresh_after_30s(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._last_heavy_refresh = time.time()
        poller._last_full_refresh = time.time() - 31

        with patch.object(poller, "_full_refresh", return_value=PollingUpdate(projects_changed=True)) as mock:
            result = await poller.tick()
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_does_single_repo_normally(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._last_heavy_refresh = time.time()
        poller._last_full_refresh = time.time()

        with patch.object(poller, "_poll_one_repo", return_value=None) as mock:
            result = await poller.tick()
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_heavy_refresh_at_60s(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._last_heavy_refresh = time.time() - 61
        poller._last_full_refresh = time.time() - 31

        with patch.object(poller, "_heavy_refresh", return_value=PollingUpdate()) as mock:
            await poller.tick()
            mock.assert_called_once()


class TestRateLimitThrottling:
    @pytest.mark.asyncio
    async def test_critical_rate_limit_skips_tick(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._rate_limit_remaining = 100
        result = await poller.tick()
        assert result is None
        assert poller.is_rate_critical

    @pytest.mark.asyncio
    async def test_low_rate_limit_allows_heavy_but_skips_light(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._rate_limit_remaining = 400
        poller._last_heavy_refresh = time.time()
        poller._last_full_refresh = time.time()

        result = await poller.tick()
        assert result is None

    @pytest.mark.asyncio
    async def test_low_rate_limit_allows_heavy_refresh(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._rate_limit_remaining = 400
        poller._last_heavy_refresh = 0

        with patch.object(poller, "_heavy_refresh", return_value=PollingUpdate()) as mock:
            await poller.tick()
            mock.assert_called_once()

    def test_rate_limit_header_parsing(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        resp = _mock_response([], rate_limit=1234)
        poller._update_rate_limit(resp)
        assert poller.rate_limit_remaining == 1234

    def test_rate_limit_properties(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._rate_limit_remaining = 5000
        assert not poller.is_rate_limited
        assert not poller.is_rate_critical

        poller._rate_limit_remaining = 400
        assert poller.is_rate_limited
        assert not poller.is_rate_critical

        poller._rate_limit_remaining = 100
        assert poller.is_rate_limited
        assert poller.is_rate_critical


class TestForceRefresh:
    @pytest.mark.asyncio
    async def test_force_refresh_resets_timers(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._last_full_refresh = 0
        poller._last_heavy_refresh = 0

        with patch.object(poller, "_do_full_refresh", return_value=PollingUpdate(projects_changed=True)) as mock:
            result = await poller.force_refresh()
            mock.assert_called_once_with(include_heavy=True)
            assert poller._last_full_refresh > 0
            assert poller._last_heavy_refresh > 0

    @pytest.mark.asyncio
    async def test_force_refresh_returns_update(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        expected = PollingUpdate(projects_changed=True)
        with patch.object(poller, "_do_full_refresh", return_value=expected):
            result = await poller.force_refresh()
            assert result.projects_changed


class TestPollingUpdateDetection:
    @pytest.mark.asyncio
    async def test_new_pr_detected(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._data.prs["proj-a"] = [_make_pr("owner/repo-a", 1, "Old PR")]

        pr_json = [{
            "number": 2, "title": "New PR", "state": "open",
            "user": {"login": "test"}, "html_url": "",
            "created_at": "2026-03-25T00:00:00Z",
            "updated_at": "2026-03-25T00:00:00Z",
        }, {
            "number": 1, "title": "Old PR", "state": "open",
            "user": {"login": "test"}, "html_url": "",
            "created_at": "2026-03-25T00:00:00Z",
            "updated_at": "2026-03-25T00:00:00Z",
        }]

        poller._data.projects = [
            ProjectInfo(name="proj-a", account="personal", repos=["owner/repo-a", "owner/repo-b"]),
        ]
        poller._last_heavy_refresh = time.time()
        poller._last_full_refresh = time.time()
        poller._repo_index = 0  # Will poll repo-a

        with patch("httpx.get", return_value=_mock_response(pr_json)):
            result = await poller._poll_one_repo()

        assert result is not None
        assert result.prs_changed.get("proj-a") is True
        assert len(result.new_prs) == 1
        assert result.new_prs[0].number == 2

    @pytest.mark.asyncio
    async def test_closed_pr_detected(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._data.prs["proj-a"] = [
            _make_pr("owner/repo-a", 1, "Will close"),
            _make_pr("owner/repo-a", 2, "Stay open"),
        ]
        poller._data.projects = [
            ProjectInfo(name="proj-a", account="personal", repos=["owner/repo-a", "owner/repo-b"]),
        ]
        poller._repo_index = 0

        pr_json = [{
            "number": 2, "title": "Stay open", "state": "open",
            "user": {"login": "test"}, "html_url": "",
            "created_at": "2026-03-25T00:00:00Z",
            "updated_at": "2026-03-25T00:00:00Z",
        }]

        with patch("httpx.get", return_value=_mock_response(pr_json)):
            result = await poller._poll_one_repo()

        assert result is not None
        assert len(result.closed_prs) == 1
        assert result.closed_prs[0].number == 1

    @pytest.mark.asyncio
    async def test_no_change_returns_none(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._data.prs["proj-a"] = [_make_pr("owner/repo-a", 1, "Existing")]
        poller._data.projects = [
            ProjectInfo(name="proj-a", account="personal", repos=["owner/repo-a", "owner/repo-b"]),
        ]
        poller._repo_index = 0

        pr_json = [{
            "number": 1, "title": "Existing", "state": "open",
            "user": {"login": "test"}, "html_url": "",
            "created_at": "2026-03-25T00:00:00Z",
            "updated_at": "2026-03-25T00:00:00Z",
        }]

        with patch("httpx.get", return_value=_mock_response(pr_json)):
            result = await poller._poll_one_repo()

        assert result is None


class TestCIChangeDetection:
    @pytest.mark.asyncio
    async def test_full_refresh_with_heavy_enriches_prs(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._data.projects = [
            ProjectInfo(name="proj-a", account="personal", repos=["owner/repo-a", "owner/repo-b"]),
            ProjectInfo(name="proj-b", account="personal", repos=["owner/repo-c"]),
        ]

        pr_json = [{
            "number": 10, "title": "Test PR", "state": "open",
            "user": {"login": "test"}, "html_url": "",
            "created_at": "2026-03-25T00:00:00Z",
            "updated_at": "2026-03-25T00:00:00Z",
        }]

        ci_json = {"state": "success"}
        review_json = [{"state": "APPROVED"}]

        def mock_get(url, **kwargs):
            if "/pulls" in url and "/reviews" not in url:
                return _mock_response(pr_json)
            elif "/status" in url:
                return _mock_response(ci_json)
            elif "/reviews" in url:
                return _mock_response(review_json)
            return _mock_response([])

        with patch("httpx.get", side_effect=mock_get):
            result = await poller._do_full_refresh(include_heavy=True)

        assert result.projects_changed
        prs = poller._data.prs.get("proj-a", [])
        if prs:
            assert prs[0].ci_status == "passing"
            assert prs[0].review_status == "approved"


class TestParsePr:
    def test_parse_pr_basic(self):
        data = {
            "number": 42,
            "title": "Fix bug",
            "user": {"login": "alice"},
            "html_url": "https://github.com/owner/repo/pull/42",
            "created_at": "2026-03-25T10:00:00Z",
            "updated_at": "2026-03-25T12:00:00Z",
        }
        pr = _parse_pr("owner/repo", data)
        assert pr.number == 42
        assert pr.title == "Fix bug"
        assert pr.author == "alice"
        assert pr.repo_id == "owner/repo"
        assert pr.state == "open"

    def test_parse_pr_missing_fields(self):
        data = {}
        pr = _parse_pr("owner/repo", data)
        assert pr.number == 0
        assert pr.title == ""
        assert pr.author == ""


class TestPollingData:
    def test_default_values(self):
        data = PollingData()
        assert data.projects == []
        assert data.prs == {}
        assert data.ci_statuses == {}
        assert data.last_updated is None


class TestPollingUpdate:
    def test_default_values(self):
        update = PollingUpdate()
        assert not update.projects_changed
        assert update.prs_changed == {}
        assert update.new_prs == []
        assert update.closed_prs == []
        assert update.ci_changed == {}


class TestStatusText:
    def test_status_when_rate_critical(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._rate_limit_remaining = 100
        text = poller.get_status_text()
        assert "Rate limited" in text

    def test_status_when_rate_low(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._rate_limit_remaining = 400
        text = poller.get_status_text()
        assert "Throttled" in text

    def test_status_with_last_updated(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._data.last_updated = datetime.now()
        text = poller.get_status_text()
        assert "Updated" in text
        assert "ago" in text

    def test_status_initial(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        text = poller.get_status_text()
        assert text == "Live"


class TestNoReposPolling:
    @pytest.mark.asyncio
    async def test_poll_one_repo_with_no_repos(self):
        poller = SmartPoller(credentials=_make_creds(), config=None)
        result = await poller._poll_one_repo()
        assert result is None

    @pytest.mark.asyncio
    async def test_poll_one_repo_no_token(self):
        poller = SmartPoller(credentials={}, config=_make_config())
        result = await poller._poll_one_repo()
        assert result is None


class TestPollCount:
    @pytest.mark.asyncio
    async def test_poll_count_increments(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        assert poller.poll_count == 0

        with patch.object(poller, "_heavy_refresh", return_value=PollingUpdate()):
            await poller.tick()
        assert poller.poll_count == 1

        with patch.object(poller, "_poll_one_repo", return_value=None):
            poller._last_heavy_refresh = time.time()
            poller._last_full_refresh = time.time()
            await poller.tick()
        assert poller.poll_count == 2


class TestApiFailures:
    @pytest.mark.asyncio
    async def test_poll_one_repo_handles_http_error(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._last_heavy_refresh = time.time()
        poller._last_full_refresh = time.time()

        with patch("httpx.get", side_effect=httpx.ConnectError("fail")):
            result = await poller._poll_one_repo()
        assert result is None

    @pytest.mark.asyncio
    async def test_poll_one_repo_handles_non_200(self):
        poller = SmartPoller(credentials=_make_creds(), config=_make_config())
        poller._last_heavy_refresh = time.time()
        poller._last_full_refresh = time.time()

        with patch("httpx.get", return_value=_mock_response([], status_code=403)):
            result = await poller._poll_one_repo()
        assert result is None
