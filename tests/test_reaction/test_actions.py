"""Tests for reaction actions — send-to-agent, notify, auto-merge."""
from __future__ import annotations

import subprocess
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from pm.reaction.actions import (
    CI_FAILURE_MESSAGE,
    CHANGES_REQUESTED_MESSAGE,
    Notification,
    NotificationQueue,
    auto_merge,
    notify_user,
    notifications,
    send_to_agent,
)


class TestNotification:
    def test_creation(self):
        n = Notification(session_id="s-001", message="test", level="warning")
        assert n.session_id == "s-001"
        assert n.message == "test"
        assert n.level == "warning"
        assert n.read is False
        assert isinstance(n.created_at, datetime)

    def test_default_level(self):
        n = Notification(session_id="s-001", message="test")
        assert n.level == "info"


class TestNotificationQueue:
    def test_push_and_get(self):
        q = NotificationQueue()
        n = Notification(session_id="s-001", message="hello")
        q.push(n)

        all_items = q.get_all()
        assert len(all_items) == 1
        assert all_items[0].message == "hello"

    def test_push_order_newest_first(self):
        q = NotificationQueue()
        q.push(Notification(session_id="s-001", message="first"))
        q.push(Notification(session_id="s-001", message="second"))

        all_items = q.get_all()
        assert all_items[0].message == "second"
        assert all_items[1].message == "first"

    def test_max_size(self):
        q = NotificationQueue(max_size=3)
        for i in range(5):
            q.push(Notification(session_id="s-001", message=f"msg-{i}"))

        assert len(q) == 3

    def test_get_unread(self):
        q = NotificationQueue()
        q.push(Notification(session_id="s-001", message="unread"))
        n2 = Notification(session_id="s-001", message="read", read=True)
        q.push(n2)

        unread = q.get_unread()
        assert len(unread) == 1
        assert unread[0].message == "unread"

    def test_mark_all_read(self):
        q = NotificationQueue()
        q.push(Notification(session_id="s-001", message="a"))
        q.push(Notification(session_id="s-001", message="b"))

        assert q.unread_count == 2
        q.mark_all_read()
        assert q.unread_count == 0

    def test_clear(self):
        q = NotificationQueue()
        q.push(Notification(session_id="s-001", message="a"))
        q.clear()

        assert len(q) == 0

    def test_unread_count(self):
        q = NotificationQueue()
        assert q.unread_count == 0
        q.push(Notification(session_id="s-001", message="a"))
        assert q.unread_count == 1
        q.push(Notification(session_id="s-001", message="b"))
        assert q.unread_count == 2


class TestSendToAgent:
    @patch("pm.reaction.actions.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = send_to_agent("pm_test_session", "Fix the bug")
        assert result is True

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["tmux", "send-keys", "-t", "pm_test_session", "Fix the bug", "Enter"]

    @patch("pm.reaction.actions.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="session not found")

        result = send_to_agent("pm_nonexistent", "Fix the bug")
        assert result is False

    @patch("pm.reaction.actions.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=10)

        result = send_to_agent("pm_test", "Fix")
        assert result is False

    @patch("pm.reaction.actions.subprocess.run")
    def test_tmux_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        result = send_to_agent("pm_test", "Fix")
        assert result is False

    def test_empty_session_name(self):
        result = send_to_agent("", "Fix")
        assert result is False

    @patch("pm.reaction.actions.subprocess.run")
    def test_ci_failure_message_content(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        send_to_agent("pm_test", CI_FAILURE_MESSAGE)
        args = mock_run.call_args[0][0]
        assert "CI is failing" in args[4]

    @patch("pm.reaction.actions.subprocess.run")
    def test_changes_requested_message_content(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        send_to_agent("pm_test", CHANGES_REQUESTED_MESSAGE)
        args = mock_run.call_args[0][0]
        assert "review comments" in args[4]


class TestNotifyUser:
    def setup_method(self):
        notifications.clear()

    def test_notify_adds_to_queue(self):
        notify_user("s-001", "Test notification")

        all_items = notifications.get_all()
        assert len(all_items) == 1
        assert all_items[0].session_id == "s-001"
        assert all_items[0].message == "Test notification"

    def test_notify_default_level(self):
        notify_user("s-001", "Test", level="warning")

        all_items = notifications.get_all()
        assert all_items[0].level == "warning"

    def test_notify_error_level(self):
        notify_user("s-001", "Error", level="error")

        all_items = notifications.get_all()
        assert all_items[0].level == "error"

    def test_multiple_notifications(self):
        notify_user("s-001", "First")
        notify_user("s-002", "Second")

        assert notifications.unread_count == 2


class TestAutoMerge:
    @patch("pm.reaction.actions.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = auto_merge(42, "owner/repo")
        assert result is True

        args = mock_run.call_args[0][0]
        assert "gh" in args
        assert "pr" in args
        assert "merge" in args
        assert "42" in args
        assert "--repo" in args
        assert "owner/repo" in args
        assert "--auto" in args
        assert "--squash" in args

    @patch("pm.reaction.actions.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="merge conflict")

        result = auto_merge(42, "owner/repo")
        assert result is False

    @patch("pm.reaction.actions.subprocess.run")
    def test_merge_strategy(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        auto_merge(42, "owner/repo", strategy="rebase")
        args = mock_run.call_args[0][0]
        assert "--rebase" in args

    @patch("pm.reaction.actions.subprocess.run")
    def test_merge_strategy_merge(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        auto_merge(42, "owner/repo", strategy="merge")
        args = mock_run.call_args[0][0]
        assert "--merge" in args

    @patch("pm.reaction.actions.subprocess.run")
    def test_invalid_strategy_defaults_to_squash(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        auto_merge(42, "owner/repo", strategy="invalid")
        args = mock_run.call_args[0][0]
        assert "--squash" in args

    @patch("pm.reaction.actions.subprocess.run")
    def test_custom_gh_path(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        auto_merge(42, "owner/repo", gh_path="/custom/gh")
        args = mock_run.call_args[0][0]
        assert args[0] == "/custom/gh"

    @patch("pm.reaction.actions.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        result = auto_merge(42, "owner/repo")
        assert result is False

    @patch("pm.reaction.actions.subprocess.run")
    def test_gh_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        result = auto_merge(42, "owner/repo")
        assert result is False


class TestMessageConstants:
    def test_ci_failure_message(self):
        assert "CI is failing" in CI_FAILURE_MESSAGE
        assert "gh pr checks" in CI_FAILURE_MESSAGE

    def test_changes_requested_message(self):
        assert "review comments" in CHANGES_REQUESTED_MESSAGE
        assert "gh pr view" in CHANGES_REQUESTED_MESSAGE
