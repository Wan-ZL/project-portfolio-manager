"""Tests for retry counting, escalation logic, and DB persistence."""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm.db.database import Database
from pm.db.models import ReactionTracker as ReactionTrackerModel
from pm.reaction.tracker import ReactionTracker, parse_duration


class TestParseDuration:
    def test_seconds(self):
        assert parse_duration("30s") == timedelta(seconds=30)

    def test_minutes(self):
        assert parse_duration("5m") == timedelta(minutes=5)

    def test_hours(self):
        assert parse_duration("1h") == timedelta(hours=1)

    def test_empty_string(self):
        assert parse_duration("") == timedelta(0)

    def test_invalid_string(self):
        assert parse_duration("abc") == timedelta(0)

    def test_plain_integer(self):
        assert parse_duration("60") == timedelta(seconds=60)

    def test_case_insensitive(self):
        assert parse_duration("30S") == timedelta(seconds=30)
        assert parse_duration("5M") == timedelta(minutes=5)

    def test_with_spaces(self):
        assert parse_duration("  30s  ") == timedelta(seconds=30)

    def test_zero(self):
        assert parse_duration("0s") == timedelta(0)

    def test_large_value(self):
        assert parse_duration("3600s") == timedelta(hours=1)


class TestReactionTracker:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.db = Database(db_path=Path(self._tmpdir) / "test.db")
        self.tracker = ReactionTracker(self.db)

    def test_get_tracker_new(self):
        t = self.tracker.get_tracker("s-001", "ci-failed")
        assert t.id == "s-001:ci-failed"
        assert t.reaction_key == "ci-failed"
        assert t.attempt_count == 0
        assert t.escalated is False

    def test_get_tracker_existing(self):
        # Create first
        model = ReactionTrackerModel(
            id="s-001:ci-failed",
            reaction_key="ci-failed",
            attempt_count=2,
            escalated=False,
        )
        self.db.upsert_reaction_tracker(model)

        # Get
        t = self.tracker.get_tracker("s-001", "ci-failed")
        assert t.attempt_count == 2

    def test_record_attempt(self):
        t = self.tracker.record_attempt("s-001", "ci-failed")
        assert t.attempt_count == 1
        assert t.last_attempt_at is not None

        t = self.tracker.record_attempt("s-001", "ci-failed")
        assert t.attempt_count == 2

    def test_record_attempt_persists(self):
        self.tracker.record_attempt("s-001", "ci-failed")
        self.tracker.record_attempt("s-001", "ci-failed")

        # Re-read from DB
        t = self.tracker.get_tracker("s-001", "ci-failed")
        assert t.attempt_count == 2

    def test_should_escalate_by_retries(self):
        self.tracker.record_attempt("s-001", "ci-failed")
        self.tracker.record_attempt("s-001", "ci-failed")
        self.tracker.record_attempt("s-001", "ci-failed")

        assert self.tracker.should_escalate("s-001", "ci-failed", max_retries=3) is True

    def test_should_not_escalate_under_retries(self):
        self.tracker.record_attempt("s-001", "ci-failed")
        self.tracker.record_attempt("s-001", "ci-failed")

        assert self.tracker.should_escalate("s-001", "ci-failed", max_retries=3) is False

    def test_should_escalate_by_timeout(self):
        # Record an attempt in the past
        t = self.tracker.record_attempt("s-001", "changes-requested")
        # Manually set first_attempt_at to the past (escalation measures from first attempt)
        model = self.db.get_reaction_tracker("s-001:changes-requested")
        model.first_attempt_at = datetime.now() - timedelta(minutes=31)
        model.last_attempt_at = datetime.now() - timedelta(minutes=31)
        self.db.upsert_reaction_tracker(model)

        assert self.tracker.should_escalate(
            "s-001", "changes-requested",
            max_retries=10,
            escalate_after="30m",
        ) is True

    def test_should_not_escalate_within_timeout(self):
        self.tracker.record_attempt("s-001", "changes-requested")

        assert self.tracker.should_escalate(
            "s-001", "changes-requested",
            max_retries=10,
            escalate_after="30m",
        ) is False

    def test_should_escalate_no_attempts(self):
        assert self.tracker.should_escalate("s-001", "ci-failed", max_retries=3) is False

    def test_is_escalated(self):
        assert self.tracker.is_escalated("s-001", "ci-failed") is False
        self.tracker.mark_escalated("s-001", "ci-failed")
        assert self.tracker.is_escalated("s-001", "ci-failed") is True

    def test_mark_escalated(self):
        t = self.tracker.mark_escalated("s-001", "ci-failed")
        assert t.escalated is True

        # Verify persistence
        model = self.db.get_reaction_tracker("s-001:ci-failed")
        assert model.escalated is True

    def test_reset_tracker(self):
        self.tracker.record_attempt("s-001", "ci-failed")
        self.tracker.record_attempt("s-001", "ci-failed")
        self.tracker.mark_escalated("s-001", "ci-failed")

        self.tracker.reset_tracker("s-001", "ci-failed")

        t = self.tracker.get_tracker("s-001", "ci-failed")
        assert t.attempt_count == 0
        assert t.escalated is False
        assert t.last_attempt_at is None

    def test_reset_nonexistent_tracker(self):
        # Should not raise
        self.tracker.reset_tracker("s-999", "ci-failed")

    def test_get_status(self):
        self.tracker.record_attempt("s-001", "ci-failed")
        self.tracker.record_attempt("s-001", "ci-failed")

        status = self.tracker.get_status("s-001")
        assert "ci-failed" in status
        assert status["ci-failed"]["attempt_count"] == 2
        assert status["ci-failed"]["escalated"] is False

    def test_get_status_empty(self):
        status = self.tracker.get_status("s-999")
        assert status == {}

    def test_multiple_reaction_keys(self):
        self.tracker.record_attempt("s-001", "ci-failed")
        self.tracker.record_attempt("s-001", "changes-requested")
        self.tracker.record_attempt("s-001", "changes-requested")

        t1 = self.tracker.get_tracker("s-001", "ci-failed")
        t2 = self.tracker.get_tracker("s-001", "changes-requested")

        assert t1.attempt_count == 1
        assert t2.attempt_count == 2

    def test_different_sessions(self):
        self.tracker.record_attempt("s-001", "ci-failed")
        self.tracker.record_attempt("s-002", "ci-failed")
        self.tracker.record_attempt("s-002", "ci-failed")

        t1 = self.tracker.get_tracker("s-001", "ci-failed")
        t2 = self.tracker.get_tracker("s-002", "ci-failed")

        assert t1.attempt_count == 1
        assert t2.attempt_count == 2
