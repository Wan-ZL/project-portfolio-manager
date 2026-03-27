"""Tests for CI status monitoring."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pm.reaction.ci_monitor import CIMonitor, CIState, CheckResult


class TestCheckResult:
    def test_creation(self):
        cr = CheckResult(name="build", state="SUCCESS")
        assert cr.name == "build"
        assert cr.state == "SUCCESS"


class TestCIMonitorGetChecks:
    def setup_method(self):
        self.monitor = CIMonitor()

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_get_checks_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "build", "state": "SUCCESS"},
                {"name": "lint", "state": "SUCCESS"},
                {"name": "test", "state": "FAILURE"},
            ]),
        )

        checks = self.monitor.get_checks(42, "owner/repo")

        assert len(checks) == 3
        assert checks[0].name == "build"
        assert checks[0].state == "SUCCESS"
        assert checks[2].name == "test"
        assert checks[2].state == "FAILURE"

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "gh" in args
        assert "pr" in args
        assert "checks" in args
        assert "42" in args
        assert "--repo" in args
        assert "owner/repo" in args

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_get_checks_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="not found",
        )

        checks = self.monitor.get_checks(99, "owner/repo")
        assert checks == []

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_get_checks_invalid_json(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not json",
        )

        checks = self.monitor.get_checks(42, "owner/repo")
        assert checks == []

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_get_checks_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        checks = self.monitor.get_checks(42, "owner/repo")
        assert checks == []

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_get_checks_empty_response(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
        )

        checks = self.monitor.get_checks(42, "owner/repo")
        assert checks == []

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_get_checks_partial_data(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "build"},  # missing state
                {"state": "SUCCESS"},  # missing name
            ]),
        )

        checks = self.monitor.get_checks(42, "owner/repo")
        assert len(checks) == 2
        assert checks[0].name == "build"
        assert checks[0].state == ""
        assert checks[1].name == ""
        assert checks[1].state == "SUCCESS"


class TestCIMonitorAggregateStatus:
    def setup_method(self):
        self.monitor = CIMonitor()

    def test_no_checks(self):
        assert self.monitor.aggregate_status([]) == CIState.NONE

    def test_all_success(self):
        checks = [
            CheckResult(name="build", state="SUCCESS"),
            CheckResult(name="test", state="SUCCESS"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.PASSING

    def test_any_failure(self):
        checks = [
            CheckResult(name="build", state="SUCCESS"),
            CheckResult(name="test", state="FAILURE"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.FAILING

    def test_any_pending(self):
        checks = [
            CheckResult(name="build", state="SUCCESS"),
            CheckResult(name="test", state="PENDING"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.PENDING

    def test_failure_over_pending(self):
        checks = [
            CheckResult(name="build", state="FAILURE"),
            CheckResult(name="test", state="PENDING"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.FAILING

    def test_skipped_counts_as_passing(self):
        checks = [
            CheckResult(name="build", state="SUCCESS"),
            CheckResult(name="optional", state="SKIPPED"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.PASSING

    def test_neutral_counts_as_passing(self):
        checks = [
            CheckResult(name="build", state="SUCCESS"),
            CheckResult(name="informational", state="NEUTRAL"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.PASSING

    def test_in_progress(self):
        checks = [
            CheckResult(name="build", state="IN_PROGRESS"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.PENDING

    def test_queued(self):
        checks = [
            CheckResult(name="build", state="QUEUED"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.PENDING

    def test_stale_counts_as_passing(self):
        checks = [
            CheckResult(name="build", state="STALE"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.PASSING

    def test_all_skipped(self):
        checks = [
            CheckResult(name="a", state="SKIPPED"),
            CheckResult(name="b", state="SKIPPED"),
        ]
        assert self.monitor.aggregate_status(checks) == CIState.PASSING


class TestCIMonitorGetCIStatus:
    def setup_method(self):
        self.monitor = CIMonitor()

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_get_ci_status_passing(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "build", "state": "SUCCESS"},
                {"name": "test", "state": "SUCCESS"},
            ]),
        )

        status = self.monitor.get_ci_status(42, "owner/repo")
        assert status == CIState.PASSING

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_get_ci_status_failing(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "build", "state": "SUCCESS"},
                {"name": "test", "state": "FAILURE"},
            ]),
        )

        status = self.monitor.get_ci_status(42, "owner/repo")
        assert status == CIState.FAILING

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_get_ci_status_no_checks(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="no checks",
        )

        status = self.monitor.get_ci_status(42, "owner/repo")
        assert status == CIState.NONE

    @patch("pm.reaction.ci_monitor.subprocess.run")
    def test_custom_gh_path(self, mock_run):
        monitor = CIMonitor(gh_path="/custom/gh")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
        )

        monitor.get_checks(42, "owner/repo")
        args = mock_run.call_args[0][0]
        assert args[0] == "/custom/gh"
