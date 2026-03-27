"""Tests for review comment tracking and fingerprinting."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pm.reaction.review_monitor import (
    ReviewComment,
    ReviewDecision,
    ReviewMonitor,
    ReviewStatus,
    _parse_repo,
    is_bot_user,
)


class TestIsBotUser:
    def test_known_bots(self):
        assert is_bot_user("github-actions[bot]") is True
        assert is_bot_user("dependabot[bot]") is True
        assert is_bot_user("renovate[bot]") is True
        assert is_bot_user("codecov[bot]") is True
        assert is_bot_user("sonarcloud[bot]") is True
        assert is_bot_user("vercel[bot]") is True
        assert is_bot_user("netlify[bot]") is True

    def test_not_bot(self):
        assert is_bot_user("zelin") is False
        assert is_bot_user("octocat") is False
        assert is_bot_user("john-doe") is False

    def test_custom_bot_with_suffix(self):
        assert is_bot_user("my-custom-app[bot]") is True

    def test_case_insensitive(self):
        assert is_bot_user("GitHub-Actions[bot]") is True
        assert is_bot_user("DEPENDABOT[BOT]") is True

    def test_empty_string(self):
        assert is_bot_user("") is False

    def test_none_like(self):
        assert is_bot_user("") is False


class TestParseRepo:
    def test_valid_repo(self):
        assert _parse_repo("owner/repo") == ("owner", "repo")

    def test_repo_with_dots(self):
        assert _parse_repo("org/repo.name") == ("org", "repo.name")

    def test_invalid_repo(self):
        with pytest.raises(ValueError):
            _parse_repo("invalid")


class TestReviewDecision:
    def test_creation(self):
        d = ReviewDecision(user="alice", state="APPROVED", id=123)
        assert d.user == "alice"
        assert d.state == "APPROVED"
        assert d.id == 123


class TestReviewComment:
    def test_creation(self):
        c = ReviewComment(id=1, user="bob", body="fix this", path="src/main.py", line=42)
        assert c.id == 1
        assert c.user == "bob"
        assert c.body == "fix this"
        assert c.path == "src/main.py"
        assert c.line == 42

    def test_defaults(self):
        c = ReviewComment(id=1, user="bob", body="fix")
        assert c.path == ""
        assert c.line is None
        assert c.in_reply_to_id is None


class TestReviewMonitorGetReviewDecisions:
    def setup_method(self):
        self.monitor = ReviewMonitor()

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_get_decisions_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"id": 1, "user": {"login": "alice"}, "state": "APPROVED"},
                {"id": 2, "user": {"login": "bob"}, "state": "CHANGES_REQUESTED"},
            ]),
        )

        decisions = self.monitor.get_review_decisions(42, "owner/repo")
        assert len(decisions) == 2
        assert decisions[0].user == "alice"
        assert decisions[0].state == "APPROVED"
        assert decisions[1].user == "bob"
        assert decisions[1].state == "CHANGES_REQUESTED"

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_filters_out_bots(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"id": 1, "user": {"login": "alice"}, "state": "APPROVED"},
                {"id": 2, "user": {"login": "github-actions[bot]"}, "state": "COMMENTED"},
                {"id": 3, "user": {"login": "dependabot[bot]"}, "state": "APPROVED"},
            ]),
        )

        decisions = self.monitor.get_review_decisions(42, "owner/repo")
        assert len(decisions) == 1
        assert decisions[0].user == "alice"

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_get_decisions_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        decisions = self.monitor.get_review_decisions(42, "owner/repo")
        assert decisions == []

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_get_decisions_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        decisions = self.monitor.get_review_decisions(42, "owner/repo")
        assert decisions == []

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_get_decisions_invalid_json(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")

        decisions = self.monitor.get_review_decisions(42, "owner/repo")
        assert decisions == []


class TestReviewMonitorGetReviewComments:
    def setup_method(self):
        self.monitor = ReviewMonitor()

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_get_comments_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"id": 100, "user": {"login": "alice"}, "body": "fix this", "path": "main.py", "line": 10},
                {"id": 101, "user": {"login": "bob"}, "body": "looks good", "path": "util.py", "line": 20},
            ]),
        )

        comments = self.monitor.get_review_comments(42, "owner/repo")
        assert len(comments) == 2
        assert comments[0].id == 100
        assert comments[0].user == "alice"
        assert comments[0].body == "fix this"
        assert comments[0].path == "main.py"

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_filters_out_bot_comments(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"id": 100, "user": {"login": "alice"}, "body": "fix this"},
                {"id": 101, "user": {"login": "codecov[bot]"}, "body": "coverage report"},
                {"id": 102, "user": {"login": "bob"}, "body": "also this"},
            ]),
        )

        comments = self.monitor.get_review_comments(42, "owner/repo")
        assert len(comments) == 2
        assert comments[0].user == "alice"
        assert comments[1].user == "bob"

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_get_comments_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        comments = self.monitor.get_review_comments(42, "owner/repo")
        assert comments == []

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_get_comments_with_reply_ids(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"id": 100, "user": {"login": "alice"}, "body": "fix this"},
                {"id": 101, "user": {"login": "bob"}, "body": "done", "in_reply_to_id": 100},
            ]),
        )

        comments = self.monitor.get_review_comments(42, "owner/repo")
        assert len(comments) == 2
        assert comments[0].in_reply_to_id is None
        assert comments[1].in_reply_to_id == 100


class TestReviewMonitorFingerprint:
    def setup_method(self):
        self.monitor = ReviewMonitor()

    def test_empty_comments(self):
        assert self.monitor.compute_fingerprint([]) == ""

    def test_single_comment(self):
        comments = [ReviewComment(id=42, user="alice", body="fix")]
        assert self.monitor.compute_fingerprint(comments) == "42"

    def test_multiple_comments_sorted(self):
        comments = [
            ReviewComment(id=300, user="alice", body="a"),
            ReviewComment(id=100, user="bob", body="b"),
            ReviewComment(id=200, user="charlie", body="c"),
        ]
        assert self.monitor.compute_fingerprint(comments) == "100,200,300"

    def test_fingerprint_changes_on_new_comment(self):
        comments_v1 = [
            ReviewComment(id=100, user="alice", body="fix"),
        ]
        comments_v2 = [
            ReviewComment(id=100, user="alice", body="fix"),
            ReviewComment(id=200, user="bob", body="also fix"),
        ]
        fp1 = self.monitor.compute_fingerprint(comments_v1)
        fp2 = self.monitor.compute_fingerprint(comments_v2)
        assert fp1 != fp2

    def test_fingerprint_stable_for_same_comments(self):
        comments = [
            ReviewComment(id=100, user="alice", body="fix"),
            ReviewComment(id=200, user="bob", body="also"),
        ]
        fp1 = self.monitor.compute_fingerprint(comments)
        fp2 = self.monitor.compute_fingerprint(comments)
        assert fp1 == fp2

    def test_skips_zero_id_comments(self):
        comments = [
            ReviewComment(id=0, user="alice", body="fix"),
            ReviewComment(id=100, user="bob", body="also"),
        ]
        assert self.monitor.compute_fingerprint(comments) == "100"


class TestReviewMonitorDetermineState:
    def setup_method(self):
        self.monitor = ReviewMonitor()

    def test_no_decisions(self):
        assert self.monitor.determine_review_state([]) == "pending"

    def test_approved(self):
        decisions = [ReviewDecision(user="alice", state="APPROVED")]
        assert self.monitor.determine_review_state(decisions) == "approved"

    def test_changes_requested(self):
        decisions = [ReviewDecision(user="alice", state="CHANGES_REQUESTED")]
        assert self.monitor.determine_review_state(decisions) == "changes_requested"

    def test_changes_requested_overrides_approved(self):
        decisions = [
            ReviewDecision(user="alice", state="APPROVED"),
            ReviewDecision(user="bob", state="CHANGES_REQUESTED"),
        ]
        assert self.monitor.determine_review_state(decisions) == "changes_requested"

    def test_latest_decision_per_reviewer(self):
        decisions = [
            ReviewDecision(user="alice", state="CHANGES_REQUESTED"),
            ReviewDecision(user="alice", state="APPROVED"),
        ]
        assert self.monitor.determine_review_state(decisions) == "approved"

    def test_dismissed_removes_decision(self):
        decisions = [
            ReviewDecision(user="alice", state="APPROVED"),
            ReviewDecision(user="alice", state="DISMISSED"),
        ]
        assert self.monitor.determine_review_state(decisions) == "pending"

    def test_commented_only(self):
        decisions = [ReviewDecision(user="alice", state="COMMENTED")]
        assert self.monitor.determine_review_state(decisions) == "pending"

    def test_mixed_reviewers(self):
        decisions = [
            ReviewDecision(user="alice", state="APPROVED"),
            ReviewDecision(user="bob", state="COMMENTED"),
        ]
        assert self.monitor.determine_review_state(decisions) == "approved"


class TestReviewMonitorCountUnresolved:
    def setup_method(self):
        self.monitor = ReviewMonitor()

    def test_no_comments(self):
        assert self.monitor.count_unresolved([]) == 0

    def test_single_unresolved(self):
        comments = [ReviewComment(id=100, user="alice", body="fix")]
        assert self.monitor.count_unresolved(comments) == 1

    def test_resolved_with_reply(self):
        comments = [
            ReviewComment(id=100, user="alice", body="fix this"),
            ReviewComment(id=101, user="bob", body="done", in_reply_to_id=100),
        ]
        assert self.monitor.count_unresolved(comments) == 0

    def test_mixed_resolved_unresolved(self):
        comments = [
            ReviewComment(id=100, user="alice", body="fix this"),
            ReviewComment(id=101, user="bob", body="done", in_reply_to_id=100),
            ReviewComment(id=200, user="charlie", body="also fix this"),
        ]
        assert self.monitor.count_unresolved(comments) == 1

    def test_reply_is_not_top_level(self):
        comments = [
            ReviewComment(id=100, user="alice", body="fix"),
            ReviewComment(id=101, user="bob", body="reply", in_reply_to_id=100),
        ]
        # 100 is resolved (has reply), 101 is a reply itself (not top-level)
        assert self.monitor.count_unresolved(comments) == 0

    def test_multiple_unresolved(self):
        comments = [
            ReviewComment(id=100, user="alice", body="fix 1"),
            ReviewComment(id=200, user="bob", body="fix 2"),
            ReviewComment(id=300, user="charlie", body="fix 3"),
        ]
        assert self.monitor.count_unresolved(comments) == 3


class TestReviewMonitorGetStatus:
    def setup_method(self):
        self.monitor = ReviewMonitor()

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_get_review_status_complete(self, mock_run):
        # First call: reviews, second call: comments
        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout=json.dumps([
                    {"id": 1, "user": {"login": "alice"}, "state": "CHANGES_REQUESTED"},
                ]),
            ),
            MagicMock(
                returncode=0,
                stdout=json.dumps([
                    {"id": 100, "user": {"login": "alice"}, "body": "fix line 10", "path": "main.py"},
                    {"id": 101, "user": {"login": "github-actions[bot]"}, "body": "CI report"},
                ]),
            ),
        ]

        status = self.monitor.get_review_status(42, "owner/repo")
        assert status.state == "changes_requested"
        assert len(status.decisions) == 1
        assert len(status.comments) == 1  # bot filtered out
        assert status.unresolved_count == 1
        assert status.fingerprint == "100"

    @patch("pm.reaction.review_monitor.subprocess.run")
    def test_get_review_status_approved(self, mock_run):
        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout=json.dumps([
                    {"id": 1, "user": {"login": "alice"}, "state": "APPROVED"},
                ]),
            ),
            MagicMock(
                returncode=0,
                stdout=json.dumps([]),
            ),
        ]

        status = self.monitor.get_review_status(42, "owner/repo")
        assert status.state == "approved"
        assert status.unresolved_count == 0
        assert status.fingerprint == ""
