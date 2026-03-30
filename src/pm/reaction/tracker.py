"""Retry and escalation tracking for the reaction engine (T5)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from pm.db.database import Database
from pm.db.models import ReactionTracker as ReactionTrackerModel

logger = logging.getLogger(__name__)


def parse_duration(duration_str: str) -> timedelta:
    """Parse a duration string like '30m', '1h', '90s' into a timedelta.

    Supported formats: Xs (seconds), Xm (minutes), Xh (hours)
    """
    if not duration_str:
        return timedelta(0)

    match = re.match(r"^(\d+)\s*(s|m|h)$", duration_str.strip().lower())
    if not match:
        # Try plain integer as seconds
        try:
            return timedelta(seconds=int(duration_str))
        except ValueError:
            return timedelta(0)

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return timedelta(seconds=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    return timedelta(0)


class ReactionTracker:
    """Tracks retry attempts and escalation state per session+reaction_key."""

    def __init__(self, db: Database):
        self.db = db

    def get_tracker(self, session_id: str, reaction_key: str) -> ReactionTrackerModel:
        """Get or create a tracker for a session+reaction combination."""
        tracker_id = f"{session_id}:{reaction_key}"
        existing = self.db.get_reaction_tracker(tracker_id)
        if existing:
            return existing
        return ReactionTrackerModel(
            id=tracker_id,
            reaction_key=reaction_key,
            attempt_count=0,
            escalated=False,
        )

    def record_attempt(self, session_id: str, reaction_key: str) -> ReactionTrackerModel:
        """Record an attempt for a session+reaction."""
        tracker = self.get_tracker(session_id, reaction_key)
        tracker.attempt_count += 1
        now = datetime.now()
        if tracker.first_attempt_at is None:
            tracker.first_attempt_at = now
        tracker.last_attempt_at = now
        self.db.upsert_reaction_tracker(tracker)
        return tracker

    def should_escalate(
        self,
        session_id: str,
        reaction_key: str,
        max_retries: int,
        escalate_after: str = "",
    ) -> bool:
        """Check if a reaction should be escalated.

        Escalation happens when:
        1. attempt_count >= max_retries, OR
        2. escalate_after duration has elapsed since first attempt
        """
        tracker = self.get_tracker(session_id, reaction_key)

        # Check retry count
        if tracker.attempt_count >= max_retries:
            return True

        # Check escalation timeout from the first attempt, not the last
        first_at = tracker.first_attempt_at or tracker.last_attempt_at
        if escalate_after and first_at:
            timeout = parse_duration(escalate_after)
            if timeout.total_seconds() > 0:
                elapsed = datetime.now() - first_at
                if elapsed >= timeout:
                    return True

        return False

    def is_escalated(self, session_id: str, reaction_key: str) -> bool:
        """Check if a reaction has already been escalated."""
        tracker = self.get_tracker(session_id, reaction_key)
        return tracker.escalated

    def mark_escalated(self, session_id: str, reaction_key: str) -> ReactionTrackerModel:
        """Mark a reaction as escalated."""
        tracker = self.get_tracker(session_id, reaction_key)
        tracker.escalated = True
        tracker.last_attempt_at = datetime.now()
        self.db.upsert_reaction_tracker(tracker)
        return tracker

    def reset_tracker(self, session_id: str, reaction_key: str) -> None:
        """Reset a tracker (e.g., when the state changes to a non-failing state)."""
        tracker_id = f"{session_id}:{reaction_key}"
        existing = self.db.get_reaction_tracker(tracker_id)
        if existing:
            existing.attempt_count = 0
            existing.escalated = False
            existing.first_attempt_at = None
            existing.last_attempt_at = None
            self.db.upsert_reaction_tracker(existing)

    def get_status(self, session_id: str) -> dict[str, dict]:
        """Get all tracker statuses for a session.

        Returns dict mapping reaction_key -> {attempt_count, escalated, last_attempt_at}
        """
        result = {}
        for key in ["ci-failed", "changes-requested", "approved-and-green"]:
            tracker_id = f"{session_id}:{key}"
            tracker = self.db.get_reaction_tracker(tracker_id)
            if tracker:
                result[key] = {
                    "attempt_count": tracker.attempt_count,
                    "escalated": tracker.escalated,
                    "last_attempt_at": tracker.last_attempt_at,
                }
        return result
