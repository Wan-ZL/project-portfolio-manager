from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from pm.db.database import Database
from pm.db.models import ProjectSummary, Repo
from pm.overlay.data import (
    OverlayProject,
    _extract_one_line,
    _extract_urgency_from_summary,
    _urgency_to_status,
    fetch_overlay_data,
    format_time_ago,
    get_projects_from_db,
    get_projects_from_repos,
    load_overlay_settings,
)


# --- format_time_ago ---

class TestFormatTimeAgo:
    def test_none(self):
        assert format_time_ago(None) == "unknown"

    def test_just_now(self):
        result = format_time_ago(datetime.now() + timedelta(seconds=5))
        assert result == "just now"

    def test_seconds(self):
        result = format_time_ago(datetime.now() - timedelta(seconds=30))
        assert "s ago" in result

    def test_minutes(self):
        result = format_time_ago(datetime.now() - timedelta(minutes=5))
        assert "m ago" in result

    def test_hours(self):
        result = format_time_ago(datetime.now() - timedelta(hours=3))
        assert "hr ago" in result

    def test_yesterday(self):
        result = format_time_ago(datetime.now() - timedelta(hours=30))
        assert result == "yesterday"

    def test_days(self):
        result = format_time_ago(datetime.now() - timedelta(days=12))
        assert "d ago" in result

    def test_months(self):
        result = format_time_ago(datetime.now() - timedelta(days=60))
        assert "mo ago" in result

    def test_years(self):
        result = format_time_ago(datetime.now() - timedelta(days=400))
        assert "yr ago" in result


# --- urgency/status helpers ---

class TestUrgencyToStatus:
    def test_high(self):
        assert _urgency_to_status("high") == "error"

    def test_medium(self):
        assert _urgency_to_status("medium") == "warn"

    def test_low(self):
        assert _urgency_to_status("low") == "ok"

    def test_idle(self):
        assert _urgency_to_status("idle") == "ok"

    def test_unknown(self):
        assert _urgency_to_status("whatever") == "ok"


class TestExtractUrgency:
    def test_none(self):
        assert _extract_urgency_from_summary(None) == "low"

    def test_valid_json(self):
        data = json.dumps({"urgency": "high", "one_line_status": "test"})
        assert _extract_urgency_from_summary(data) == "high"

    def test_missing_urgency_key(self):
        data = json.dumps({"one_line_status": "test"})
        assert _extract_urgency_from_summary(data) == "low"

    def test_invalid_json(self):
        assert _extract_urgency_from_summary("not json") == "low"

    def test_empty_string(self):
        assert _extract_urgency_from_summary("") == "low"


class TestExtractOneLine:
    def test_none(self):
        assert _extract_one_line(None) == "No status available"

    def test_valid_json(self):
        data = json.dumps({"one_line_status": "CI failing", "urgency": "high"})
        assert _extract_one_line(data) == "CI failing"

    def test_missing_key(self):
        data = json.dumps({"urgency": "high"})
        result = _extract_one_line(data)
        assert "urgency" in result  # falls back to str(data)

    def test_plain_text(self):
        assert _extract_one_line("Plain summary text") == "Plain summary text"


# --- settings ---

class TestLoadOverlaySettings:
    def test_defaults_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.yaml"
            settings = load_overlay_settings(path)
            assert settings["enabled"] is False
            assert settings["show_count"] == 3
            assert settings["position"] == "bottom-right"
            assert settings["opacity"] == 70

    def test_custom_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.yaml"
            data = {
                "overlay": {
                    "enabled": True,
                    "show_count": 5,
                    "position": "top-left",
                    "opacity": 50,
                },
            }
            with open(path, "w") as f:
                yaml.dump(data, f)
            settings = load_overlay_settings(path)
            assert settings["enabled"] is True
            assert settings["show_count"] == 5
            assert settings["position"] == "top-left"
            assert settings["opacity"] == 50

    def test_partial_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.yaml"
            data = {"overlay": {"show_count": 10}}
            with open(path, "w") as f:
                yaml.dump(data, f)
            settings = load_overlay_settings(path)
            assert settings["show_count"] == 10
            assert settings["position"] == "bottom-right"  # default


# --- DB integration ---

@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


class TestGetProjectsFromDb:
    def test_no_db_file(self):
        result = get_projects_from_db(Path("/tmp/nonexistent_ppm_test.db"))
        assert result == []

    def test_empty_db(self, db):
        result = get_projects_from_db(db.db_path)
        assert result == []

    def test_with_summaries(self, db):
        summary_data = json.dumps({
            "one_line_status": "PR #42 CI failing",
            "urgency": "high",
        })
        db.save_summary("401K Website", summary_data, "[]", "hash1")

        result = get_projects_from_db(db.db_path)
        assert len(result) == 1
        assert result[0].name == "401K Website"
        assert result[0].status == "error"
        assert result[0].summary == "PR #42 CI failing"

    def test_show_count_limit(self, db):
        for i in range(5):
            data = json.dumps({"one_line_status": f"Project {i}", "urgency": "low"})
            db.save_summary(f"Project {i}", data, "[]", f"hash{i}")

        result = get_projects_from_db(db.db_path, show_count=2)
        assert len(result) == 2

    def test_ordering_by_generated_at(self, db):
        old_data = json.dumps({"one_line_status": "Old", "urgency": "low"})
        db.save_summary("Old Project", old_data, "[]", "hash1")

        new_data = json.dumps({"one_line_status": "New", "urgency": "high"})
        db.save_summary("New Project", new_data, "[]", "hash2")

        result = get_projects_from_db(db.db_path, show_count=10)
        assert len(result) == 2
        # Most recently generated should come first
        assert result[0].name == "New Project"
        assert result[1].name == "Old Project"

    def test_plain_text_summary(self, db):
        db.save_summary("Plain Project", "Everything is fine", "[]", "hash1")
        result = get_projects_from_db(db.db_path)
        assert len(result) == 1
        assert result[0].summary == "Everything is fine"
        assert result[0].status == "ok"  # defaults to low -> ok


class TestGetProjectsFromRepos:
    def test_no_db_file(self):
        result = get_projects_from_repos(Path("/tmp/nonexistent_ppm_test.db"))
        assert result == []

    def test_empty_db(self, db):
        result = get_projects_from_repos(db.db_path)
        assert result == []

    def test_with_repos(self, db):
        db.upsert_repo(Repo(
            id="owner/repo1", account="personal", project="Project A",
            last_synced_at=datetime.now(),
        ))
        db.upsert_repo(Repo(
            id="owner/repo2", account="personal", project="Project B",
            last_synced_at=datetime.now() - timedelta(hours=2),
        ))

        result = get_projects_from_repos(db.db_path)
        assert len(result) == 2
        assert result[0].name == "Project A"
        assert result[0].summary == "No AI summary yet"
        assert result[0].status == "ok"

    def test_groups_repos_by_project(self, db):
        db.upsert_repo(Repo(
            id="owner/frontend", account="a", project="WebApp",
            last_synced_at=datetime.now(),
        ))
        db.upsert_repo(Repo(
            id="owner/backend", account="a", project="WebApp",
            last_synced_at=datetime.now() - timedelta(hours=1),
        ))
        db.upsert_repo(Repo(
            id="other/tool", account="a", project="Tool",
            last_synced_at=datetime.now() - timedelta(days=5),
        ))

        result = get_projects_from_repos(db.db_path, show_count=10)
        assert len(result) == 2
        names = [p.name for p in result]
        assert "WebApp" in names
        assert "Tool" in names

    def test_show_count_limit(self, db):
        for i in range(5):
            db.upsert_repo(Repo(
                id=f"owner/repo{i}", account="a", project=f"P{i}",
                last_synced_at=datetime.now() - timedelta(hours=i),
            ))

        result = get_projects_from_repos(db.db_path, show_count=2)
        assert len(result) == 2


class TestFetchOverlayData:
    def test_no_db_no_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "nope.db"
            settings_path = Path(tmpdir) / "nope.yaml"
            projects, settings = fetch_overlay_data(db_path, settings_path)
            assert projects == []
            assert settings["show_count"] == 3

    def test_with_summaries(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.yaml"
            data = json.dumps({"one_line_status": "All good", "urgency": "low"})
            db.save_summary("TestProj", data, "[]", "h")

            projects, settings = fetch_overlay_data(db.db_path, settings_path)
            assert len(projects) == 1
            assert projects[0].name == "TestProj"

    def test_falls_back_to_repos(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.yaml"
            db.upsert_repo(Repo(
                id="owner/repo", account="a", project="FallbackProj",
                last_synced_at=datetime.now(),
            ))
            projects, settings = fetch_overlay_data(db.db_path, settings_path)
            assert len(projects) == 1
            assert projects[0].name == "FallbackProj"
            assert projects[0].summary == "No AI summary yet"

    def test_settings_show_count_respected(self, db):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.yaml"
            with open(settings_path, "w") as f:
                yaml.dump({"overlay": {"show_count": 1}}, f)

            for i in range(3):
                data = json.dumps({"one_line_status": f"P{i}", "urgency": "low"})
                db.save_summary(f"Proj{i}", data, "[]", f"h{i}")

            projects, settings = fetch_overlay_data(db.db_path, settings_path)
            assert len(projects) == 1
