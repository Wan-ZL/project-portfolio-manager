from __future__ import annotations

import pytest
from click.testing import CliRunner

from pm.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestStatusCommand:
    def test_status_runs(self, runner):
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "Portfolio Status" in result.output

    def test_status_shows_table(self, runner):
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        # Should have table headers or data
        assert "Project" in result.output or "401K" in result.output


class TestPrsCommand:
    def test_prs_runs(self, runner):
        result = runner.invoke(main, ["prs"])
        assert result.exit_code == 0
        assert "Pull Requests" in result.output

    def test_prs_shows_data_or_setup_message(self, runner):
        result = runner.invoke(main, ["prs"])
        assert result.exit_code == 0
        # Should show PR data or a setup message
        assert "Repo" in result.output or "No config" in result.output or "No open pull requests" in result.output


class TestOverlayCommand:
    def test_overlay_runs(self, runner):
        result = runner.invoke(main, ["overlay"])
        assert result.exit_code == 0
        assert "Coming soon" in result.output

    def test_overlay_help(self, runner):
        result = runner.invoke(main, ["overlay", "--help"])
        assert result.exit_code == 0
        assert "overlay" in result.output.lower() or "desktop" in result.output.lower()


class TestWorkCommand:
    def test_work_requires_args(self, runner):
        result = runner.invoke(main, ["work"])
        assert result.exit_code != 0

    def test_work_help(self, runner):
        result = runner.invoke(main, ["work", "--help"])
        assert result.exit_code == 0
        assert "PROJECT" in result.output
        assert "TASK" in result.output

    def test_work_missing_project(self, runner):
        result = runner.invoke(main, ["work", "nonexistent-project", "do something"])
        assert result.exit_code == 0
        # Should show error about missing project or tmux
        assert ("not found" in result.output.lower() or
                "tmux" in result.output.lower() or
                "error" in result.output.lower() or
                "config" in result.output.lower())


class TestMainCommand:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "PM" in result.output
        assert "Portfolio" in result.output or "portfolio" in result.output

    def test_demo_flag_removed(self, runner):
        result = runner.invoke(main, ["--help"])
        assert "--demo" not in result.output

    def test_subcommands_listed(self, runner):
        result = runner.invoke(main, ["--help"])
        assert "status" in result.output
        assert "prs" in result.output
        assert "overlay" in result.output
        assert "work" in result.output
