"""Reaction Engine — Polling state machine for PR monitoring (T5, T6)."""
from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime
from enum import Enum
from typing import Optional

from pm.config.models import PMConfig, ReactionConfig
from pm.db.database import Database
from pm.db.models import Session as DBSession
from pm.reaction.actions import (
    CI_FAILURE_MESSAGE,
    CHANGES_REQUESTED_MESSAGE,
    auto_merge,
    notify_user,
    send_to_agent,
)
from pm.reaction.ci_monitor import CIMonitor, CIState
from pm.reaction.review_monitor import ReviewMonitor
from pm.reaction.tracker import ReactionTracker, parse_duration

logger = logging.getLogger(__name__)


class PRState(str, Enum):
    """Possible PR states as determined by the reaction engine."""
    OPEN = "open"
    CI_FAILING = "ci_failing"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED_GREEN = "approved_green"
    MERGED = "merged"
    UNKNOWN = "unknown"


# Map PRState to reaction config key
STATE_TO_REACTION_KEY = {
    PRState.CI_FAILING: "ci-failed",
    PRState.CHANGES_REQUESTED: "changes-requested",
    PRState.APPROVED_GREEN: "approved-and-green",
}


def _gh_available() -> bool:
    """Check if gh CLI is installed."""
    return shutil.which("gh") is not None


class ReactionEngine:
    """Async polling state machine that monitors PRs and triggers reactions.

    For each active session with a PR:
    1. Check CI status via gh pr checks
    2. Check review status via gh api
    3. Determine PR state transition
    4. Execute configured reaction (send-to-agent, notify, auto-merge)
    """

    def __init__(
        self,
        config: PMConfig,
        db: Database,
        ci_monitor: Optional[CIMonitor] = None,
        review_monitor: Optional[ReviewMonitor] = None,
        tracker: Optional[ReactionTracker] = None,
    ):
        self.config = config
        self.db = db
        self.ci_monitor = ci_monitor or CIMonitor()
        self.review_monitor = review_monitor or ReviewMonitor()
        self.tracker = tracker or ReactionTracker(db)
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._session_states: dict[str, PRState] = {}
        self._session_fingerprints: dict[str, str] = {}

    @property
    def poll_interval(self) -> float:
        """Get polling interval in seconds from config."""
        interval_str = self.config.defaults.poll_interval
        td = parse_duration(interval_str)
        seconds = td.total_seconds()
        return seconds if seconds > 0 else 30.0

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the polling loop."""
        if self._running:
            return

        if not _gh_available():
            logger.warning("gh CLI not found, reaction engine disabled")
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(f"Reaction engine started (interval={self.poll_interval}s)")

    async def stop(self) -> None:
        """Stop the polling loop cleanly."""
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        self._poll_task = None
        logger.info("Reaction engine stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reaction engine poll: {e}")

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

    async def poll_once(self) -> list[tuple[str, PRState]]:
        """Run one polling cycle. Returns list of (session_id, new_state) transitions."""
        sessions = self._get_active_sessions_with_pr()
        transitions = []

        loop = asyncio.get_event_loop()
        for session in sessions:
            try:
                new_state = await loop.run_in_executor(
                    None, self._determine_state, session
                )
                old_state = self._session_states.get(session.id, PRState.UNKNOWN)

                if new_state != old_state:
                    logger.info(
                        f"Session {session.id} PR state: {old_state.value} -> {new_state.value}"
                    )
                    self._session_states[session.id] = new_state
                    await self._handle_transition(session, old_state, new_state)
                    transitions.append((session.id, new_state))
                else:
                    # Even without transition, check for fingerprint changes (new comments)
                    await self._check_fingerprint_change(session, new_state)

            except Exception as e:
                logger.warning(f"Error processing session {session.id}: {e}")

        return transitions

    def _get_active_sessions_with_pr(self) -> list[DBSession]:
        """Get all running sessions that have a PR number."""
        sessions = self.db.get_active_sessions()
        return [s for s in sessions if s.pr_number and s.status == "running"]

    def _determine_state(self, session: DBSession) -> PRState:
        """Determine the current PR state for a session."""
        repo = self._get_repo_for_session(session)
        if not repo:
            return PRState.UNKNOWN

        pr_number = session.pr_number

        # Check CI status
        ci_state = self.ci_monitor.get_ci_status(pr_number, repo)

        # Check review status
        review_status = self.review_monitor.get_review_status(pr_number, repo)

        # Store fingerprint
        self._session_fingerprints[session.id] = review_status.fingerprint

        # Determine combined state
        if ci_state == CIState.FAILING:
            return PRState.CI_FAILING

        if review_status.state == "changes_requested":
            return PRState.CHANGES_REQUESTED

        if ci_state == CIState.PASSING and review_status.state == "approved":
            return PRState.APPROVED_GREEN

        return PRState.OPEN

    def _get_repo_for_session(self, session: DBSession) -> Optional[str]:
        """Get the repository name for a session.

        Looks up the first repo associated with the session's project.
        """
        project_config = self.config.projects.get(session.project)
        if not project_config or not project_config.repos:
            return None
        return project_config.repos[0]

    async def _handle_transition(
        self, session: DBSession, old_state: PRState, new_state: PRState
    ) -> None:
        """Handle a PR state transition."""
        # Reset old state tracker if transitioning away from it
        old_key = STATE_TO_REACTION_KEY.get(old_state)
        new_key = STATE_TO_REACTION_KEY.get(new_state)
        if old_key and old_key != new_key:
            self.tracker.reset_tracker(session.id, old_key)

        if not new_key:
            return

        reaction_config = self.config.reactions.get(new_key)
        if not reaction_config:
            return

        if not reaction_config.auto:
            return

        await self._execute_reaction(session, new_key, reaction_config)

    async def _check_fingerprint_change(
        self, session: DBSession, current_state: PRState
    ) -> None:
        """Check if comments changed (new fingerprint) and re-trigger if needed."""
        if current_state != PRState.CHANGES_REQUESTED:
            return

        repo = self._get_repo_for_session(session)
        if not repo:
            return

        loop = asyncio.get_event_loop()
        review_status = await loop.run_in_executor(
            None, self.review_monitor.get_review_status, session.pr_number, repo
        )
        old_fp = self._session_fingerprints.get(session.id, "")
        new_fp = review_status.fingerprint

        if old_fp and new_fp and old_fp != new_fp:
            logger.info(f"Session {session.id}: comment fingerprint changed")
            self._session_fingerprints[session.id] = new_fp

            reaction_key = "changes-requested"
            reaction_config = self.config.reactions.get(reaction_key)
            if reaction_config and reaction_config.auto:
                # Reset tracker since new comments appeared
                self.tracker.reset_tracker(session.id, reaction_key)
                await self._execute_reaction(session, reaction_key, reaction_config)

    async def _execute_reaction(
        self,
        session: DBSession,
        reaction_key: str,
        reaction_config: ReactionConfig,
    ) -> None:
        """Execute a reaction action for a session."""
        # Check escalation
        should_escalate = self.tracker.should_escalate(
            session.id,
            reaction_key,
            reaction_config.retries,
            reaction_config.escalate_after,
        )

        if should_escalate:
            if not self.tracker.is_escalated(session.id, reaction_key):
                self.tracker.mark_escalated(session.id, reaction_key)
                notify_user(
                    session.id,
                    f"Escalation: {reaction_key} for session {session.id} "
                    f"(PR #{session.pr_number}). "
                    f"Exceeded {reaction_config.retries} retries. "
                    f"Manual intervention needed.",
                    level="error",
                )
            return

        action = reaction_config.action

        if action == "send-to-agent":
            message = reaction_config.message or self._default_message(reaction_key)
            if session.tmux_session:
                success = send_to_agent(session.tmux_session, message)
                if success:
                    self.tracker.record_attempt(session.id, reaction_key)
                else:
                    notify_user(
                        session.id,
                        f"Failed to send fix command to agent for session {session.id}",
                        level="warning",
                    )

        elif action == "notify":
            notify_user(
                session.id,
                f"PR #{session.pr_number}: {reaction_key}",
                level="info",
            )
            self.tracker.record_attempt(session.id, reaction_key)

        elif action == "auto-merge":
            repo = self._get_repo_for_session(session)
            if repo and session.pr_number:
                success = auto_merge(session.pr_number, repo)
                if success:
                    notify_user(
                        session.id,
                        f"Auto-merge enabled for PR #{session.pr_number}",
                        level="info",
                    )
                else:
                    notify_user(
                        session.id,
                        f"Failed to auto-merge PR #{session.pr_number}",
                        level="warning",
                    )
                self.tracker.record_attempt(session.id, reaction_key)

    @staticmethod
    def _default_message(reaction_key: str) -> str:
        """Get default message for a reaction key."""
        messages = {
            "ci-failed": CI_FAILURE_MESSAGE,
            "changes-requested": CHANGES_REQUESTED_MESSAGE,
        }
        return messages.get(reaction_key, f"Action needed: {reaction_key}")

    def get_session_state(self, session_id: str) -> PRState:
        """Get the current PR state for a session."""
        return self._session_states.get(session_id, PRState.UNKNOWN)

    def get_session_reaction_status(self, session_id: str) -> dict:
        """Get reaction status for a session (for TUI display)."""
        state = self.get_session_state(session_id)
        tracker_status = self.tracker.get_status(session_id)
        return {
            "pr_state": state.value,
            "trackers": tracker_status,
        }
