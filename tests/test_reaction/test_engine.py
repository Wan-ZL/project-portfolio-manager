"""Tests for the reaction engine — polling loop, state transitions, reaction dispatch."""
from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pm.config.models import (
    DefaultsConfig,
    PMConfig,
    ProjectConfig,
    ReactionConfig,
)
from pm.db.database import Database
from pm.db.models import Session as DBSession
from pm.reaction.actions import notifications
from pm.reaction.ci_monitor import CIMonitor, CIState
from pm.reaction.engine import PRState, ReactionEngine, STATE_TO_REACTION_KEY, _gh_available
from pm.reaction.review_monitor import ReviewMonitor, ReviewStatus
from pm.reaction.tracker import ReactionTracker


def _make_config(
    poll_interval: str = "5s",
    reactions: dict | None = None,
) -> PMConfig:
    """Create a test config."""
    if reactions is None:
        reactions = {
            "ci-failed": ReactionConfig(
                auto=True, action="send-to-agent", retries=3,
                message="CI is failing. Fix it.",
            ),
            "changes-requested": ReactionConfig(
                auto=True, action="send-to-agent", retries=2,
                escalate_after="30m",
            ),
            "approved-and-green": ReactionConfig(
                auto=False, action="notify",
            ),
        }

    return PMConfig(
        projects={
            "test-project": ProjectConfig(
                account="personal",
                repos=["owner/repo"],
                local_path="~/projects/test",
            ),
        },
        defaults=DefaultsConfig(poll_interval=poll_interval),
        reactions=reactions,
    )


def _make_session(
    session_id: str = "s-001",
    project: str = "test-project",
    pr_number: int = 42,
    status: str = "running",
    tmux_session: str = "pm_test_fix-auth",
) -> DBSession:
    return DBSession(
        id=session_id,
        project=project,
        task_description="Fix auth bug",
        agent="claude-code",
        tmux_session=tmux_session,
        pr_number=pr_number,
        status=status,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class TestPRState:
    def test_enum_values(self):
        assert PRState.OPEN.value == "open"
        assert PRState.CI_FAILING.value == "ci_failing"
        assert PRState.CHANGES_REQUESTED.value == "changes_requested"
        assert PRState.APPROVED_GREEN.value == "approved_green"
        assert PRState.MERGED.value == "merged"
        assert PRState.UNKNOWN.value == "unknown"


class TestStateToReactionKey:
    def test_mapping(self):
        assert STATE_TO_REACTION_KEY[PRState.CI_FAILING] == "ci-failed"
        assert STATE_TO_REACTION_KEY[PRState.CHANGES_REQUESTED] == "changes-requested"
        assert STATE_TO_REACTION_KEY[PRState.APPROVED_GREEN] == "approved-and-green"

    def test_open_not_mapped(self):
        assert PRState.OPEN not in STATE_TO_REACTION_KEY


class TestReactionEngineInit:
    def test_default_init(self):
        config = _make_config()
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")

        engine = ReactionEngine(config=config, db=db)
        assert engine.config is config
        assert engine.db is db
        assert engine.running is False
        assert isinstance(engine.ci_monitor, CIMonitor)
        assert isinstance(engine.review_monitor, ReviewMonitor)
        assert isinstance(engine.tracker, ReactionTracker)

    def test_poll_interval(self):
        config = _make_config(poll_interval="10s")
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        assert engine.poll_interval == 10.0

    def test_poll_interval_default(self):
        config = _make_config(poll_interval="")
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        assert engine.poll_interval == 30.0

    def test_poll_interval_minutes(self):
        config = _make_config(poll_interval="2m")
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        assert engine.poll_interval == 120.0


class TestReactionEngineStartStop:
    @pytest.mark.asyncio
    @patch("pm.reaction.engine._gh_available", return_value=True)
    async def test_start_stop(self, mock_gh):
        config = _make_config()
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        await engine.start()
        assert engine.running is True

        await engine.stop()
        assert engine.running is False

    @pytest.mark.asyncio
    @patch("pm.reaction.engine._gh_available", return_value=False)
    async def test_start_without_gh(self, mock_gh):
        config = _make_config()
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        await engine.start()
        assert engine.running is False

    @pytest.mark.asyncio
    @patch("pm.reaction.engine._gh_available", return_value=True)
    async def test_start_idempotent(self, mock_gh):
        config = _make_config()
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        await engine.start()
        first_task = engine._poll_task
        await engine.start()
        assert engine._poll_task is first_task

        await engine.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        config = _make_config()
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        # Should not raise
        await engine.stop()


class TestReactionEnginePollOnce:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.db = Database(db_path=Path(self._tmpdir) / "test.db")
        self.config = _make_config()

        self.ci_monitor = MagicMock(spec=CIMonitor)
        self.review_monitor = MagicMock(spec=ReviewMonitor)

        self.engine = ReactionEngine(
            config=self.config,
            db=self.db,
            ci_monitor=self.ci_monitor,
            review_monitor=self.review_monitor,
        )
        notifications.clear()

    @pytest.mark.asyncio
    async def test_no_active_sessions(self):
        transitions = await self.engine.poll_once()
        assert transitions == []

    @pytest.mark.asyncio
    async def test_session_without_pr(self):
        session = _make_session(pr_number=None)
        self.db.upsert_session(session)

        transitions = await self.engine.poll_once()
        assert transitions == []

    @pytest.mark.asyncio
    async def test_detect_ci_failing(self):
        session = _make_session()
        self.db.upsert_session(session)

        self.ci_monitor.get_ci_status.return_value = CIState.FAILING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="pending", fingerprint="",
        )

        with patch("pm.reaction.actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            transitions = await self.engine.poll_once()

        assert len(transitions) == 1
        assert transitions[0] == ("s-001", PRState.CI_FAILING)

    @pytest.mark.asyncio
    async def test_detect_changes_requested(self):
        session = _make_session()
        self.db.upsert_session(session)

        self.ci_monitor.get_ci_status.return_value = CIState.PASSING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="changes_requested", fingerprint="100,200",
        )

        with patch("pm.reaction.actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            transitions = await self.engine.poll_once()

        assert len(transitions) == 1
        assert transitions[0] == ("s-001", PRState.CHANGES_REQUESTED)

    @pytest.mark.asyncio
    async def test_detect_approved_green(self):
        session = _make_session()
        self.db.upsert_session(session)

        self.ci_monitor.get_ci_status.return_value = CIState.PASSING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="approved", fingerprint="",
        )

        transitions = await self.engine.poll_once()
        assert len(transitions) == 1
        assert transitions[0] == ("s-001", PRState.APPROVED_GREEN)

    @pytest.mark.asyncio
    async def test_no_transition_same_state(self):
        session = _make_session()
        self.db.upsert_session(session)

        self.ci_monitor.get_ci_status.return_value = CIState.PASSING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="pending", fingerprint="",
        )

        transitions = await self.engine.poll_once()
        assert len(transitions) == 1
        assert transitions[0] == ("s-001", PRState.OPEN)

        # Second poll with same state -> no transition
        transitions = await self.engine.poll_once()
        assert len(transitions) == 0

    @pytest.mark.asyncio
    async def test_ci_failing_sends_to_agent(self):
        session = _make_session()
        self.db.upsert_session(session)

        self.ci_monitor.get_ci_status.return_value = CIState.FAILING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="pending", fingerprint="",
        )

        with patch("pm.reaction.actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            await self.engine.poll_once()

            # Verify tmux send-keys was called
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "tmux"
            assert args[1] == "send-keys"
            assert "pm_test_fix-auth" in args

    @pytest.mark.asyncio
    async def test_approved_green_no_auto(self):
        session = _make_session()
        self.db.upsert_session(session)

        self.ci_monitor.get_ci_status.return_value = CIState.PASSING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="approved", fingerprint="",
        )

        with patch("pm.reaction.actions.subprocess.run") as mock_run:
            await self.engine.poll_once()
            # approved-and-green has auto=False in test config
            mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_escalation_after_retries(self):
        session = _make_session()
        self.db.upsert_session(session)

        self.ci_monitor.get_ci_status.return_value = CIState.FAILING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="pending", fingerprint="",
        )

        # Pre-fill tracker to max retries
        for _ in range(3):
            self.engine.tracker.record_attempt("s-001", "ci-failed")

        with patch("pm.reaction.actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            await self.engine.poll_once()

            # Should NOT send to agent (escalated instead)
            mock_run.assert_not_called()

        # Should have a notification
        assert notifications.unread_count >= 1
        notifs = notifications.get_unread()
        assert any("Escalation" in n.message for n in notifs)

    @pytest.mark.asyncio
    async def test_state_transition_resets_old_tracker(self):
        session = _make_session()
        self.db.upsert_session(session)

        # First: CI failing
        self.ci_monitor.get_ci_status.return_value = CIState.FAILING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="pending", fingerprint="",
        )
        with patch("pm.reaction.actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            await self.engine.poll_once()

        # Record some attempts
        self.engine.tracker.record_attempt("s-001", "ci-failed")

        # Now: CI passes, changes requested
        self.ci_monitor.get_ci_status.return_value = CIState.PASSING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="changes_requested", fingerprint="100",
        )
        with patch("pm.reaction.actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            await self.engine.poll_once()

        # Old tracker should be reset
        t = self.engine.tracker.get_tracker("s-001", "ci-failed")
        assert t.attempt_count == 0

    @pytest.mark.asyncio
    async def test_multiple_sessions(self):
        session1 = _make_session(session_id="s-001", pr_number=42, tmux_session="pm_s1")
        session2 = _make_session(session_id="s-002", pr_number=43, tmux_session="pm_s2")
        self.db.upsert_session(session1)
        self.db.upsert_session(session2)

        self.ci_monitor.get_ci_status.return_value = CIState.PASSING
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="pending", fingerprint="",
        )

        transitions = await self.engine.poll_once()
        assert len(transitions) == 2

    @pytest.mark.asyncio
    async def test_session_error_doesnt_stop_others(self):
        session1 = _make_session(session_id="s-001", pr_number=42)
        session2 = _make_session(session_id="s-002", pr_number=43)
        self.db.upsert_session(session1)
        self.db.upsert_session(session2)

        # First session causes error, second works
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Test error")
            return CIState.PASSING

        self.ci_monitor.get_ci_status.side_effect = side_effect
        self.review_monitor.get_review_status.return_value = ReviewStatus(
            state="pending", fingerprint="",
        )

        transitions = await self.engine.poll_once()
        assert len(transitions) == 1


class TestReactionEngineAutoMerge:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.db = Database(db_path=Path(self._tmpdir) / "test.db")
        notifications.clear()

    @pytest.mark.asyncio
    async def test_auto_merge_when_configured(self):
        config = _make_config(reactions={
            "approved-and-green": ReactionConfig(
                auto=True, action="auto-merge", retries=1,
            ),
        })

        ci_monitor = MagicMock(spec=CIMonitor)
        review_monitor = MagicMock(spec=ReviewMonitor)
        engine = ReactionEngine(
            config=config, db=self.db,
            ci_monitor=ci_monitor, review_monitor=review_monitor,
        )

        session = _make_session()
        self.db.upsert_session(session)

        ci_monitor.get_ci_status.return_value = CIState.PASSING
        review_monitor.get_review_status.return_value = ReviewStatus(
            state="approved", fingerprint="",
        )

        with patch("pm.reaction.actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            transitions = await engine.poll_once()

        assert len(transitions) == 1
        assert transitions[0] == ("s-001", PRState.APPROVED_GREEN)

        # Check auto-merge was called
        assert notifications.unread_count >= 1


class TestReactionEngineSessionState:
    def test_get_session_state_unknown(self):
        config = _make_config()
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        assert engine.get_session_state("nonexistent") == PRState.UNKNOWN

    def test_get_session_reaction_status(self):
        config = _make_config()
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        status = engine.get_session_reaction_status("s-001")
        assert status["pr_state"] == "unknown"
        assert isinstance(status["trackers"], dict)


class TestReactionEngineRepoLookup:
    def test_get_repo_for_session(self):
        config = _make_config()
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        session = _make_session(project="test-project")
        repo = engine._get_repo_for_session(session)
        assert repo == "owner/repo"

    def test_get_repo_unknown_project(self):
        config = _make_config()
        tmpdir = tempfile.mkdtemp()
        db = Database(db_path=Path(tmpdir) / "test.db")
        engine = ReactionEngine(config=config, db=db)

        session = _make_session(project="nonexistent")
        repo = engine._get_repo_for_session(session)
        assert repo is None


class TestReactionEngineDefaultMessages:
    def test_ci_failed_message(self):
        assert "CI" in ReactionEngine._default_message("ci-failed")

    def test_changes_requested_message(self):
        assert "review" in ReactionEngine._default_message("changes-requested")

    def test_unknown_key(self):
        msg = ReactionEngine._default_message("unknown-key")
        assert "unknown-key" in msg
