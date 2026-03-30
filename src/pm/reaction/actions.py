"""Reaction actions — send-to-agent, notify, auto-merge (T5)."""
from __future__ import annotations

import logging
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    """A notification for the user."""
    session_id: str
    message: str
    level: str = "info"  # info, warning, error
    created_at: datetime = field(default_factory=datetime.now)
    read: bool = False


class NotificationQueue:
    """Thread-safe notification queue for TUI display."""

    def __init__(self, max_size: int = 100):
        self._queue: deque[Notification] = deque(maxlen=max_size)
        self._lock = threading.RLock()

    def push(self, notification: Notification) -> None:
        with self._lock:
            self._queue.appendleft(notification)

    def get_all(self) -> list[Notification]:
        with self._lock:
            return list(self._queue)

    def get_unread(self) -> list[Notification]:
        with self._lock:
            return [n for n in self._queue if not n.read]

    def mark_all_read(self) -> None:
        with self._lock:
            for n in self._queue:
                n.read = True

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    @property
    def unread_count(self) -> int:
        with self._lock:
            return sum(1 for n in self._queue if not n.read)

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)


# Global notification queue for the application
notifications = NotificationQueue()


def send_to_agent(tmux_session: str, message: str) -> bool:
    """Send a message to an agent running in a tmux session.

    Uses tmux send-keys to send text followed by Enter.

    Args:
        tmux_session: The tmux session name
        message: The message to send

    Returns:
        True if the command succeeded, False otherwise
    """
    if not tmux_session:
        logger.warning("Cannot send to agent: no tmux session name")
        return False

    try:
        result = subprocess.run(
            ["tmux", "send-keys", "-t", tmux_session, message, "Enter"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.warning(
                f"Failed to send to tmux session {tmux_session}: {result.stderr.strip()}"
            )
            return False
        logger.info(f"Sent message to tmux session {tmux_session}")
        return True
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout sending to tmux session {tmux_session}")
        return False
    except FileNotFoundError:
        logger.error("tmux not found")
        return False
    except Exception as e:
        logger.warning(f"Error sending to tmux session {tmux_session}: {e}")
        return False


def notify_user(session_id: str, message: str, level: str = "warning") -> None:
    """Add a notification to the global notification queue.

    Args:
        session_id: The session that triggered this notification
        message: The notification message
        level: Severity level (info, warning, error)
    """
    notification = Notification(
        session_id=session_id,
        message=message,
        level=level,
    )
    notifications.push(notification)
    logger.info(f"Notification [{level}] for session {session_id}: {message}")


def auto_merge(pr_number: int, repo: str, strategy: str = "squash",
               gh_path: str = "gh") -> bool:
    """Auto-merge a PR using gh CLI.

    Args:
        pr_number: The PR number to merge
        repo: Repository in owner/repo format
        strategy: Merge strategy (squash, merge, rebase)
        gh_path: Path to gh CLI

    Returns:
        True if the merge command succeeded, False otherwise
    """
    strategy_flag = f"--{strategy}" if strategy in ("squash", "merge", "rebase") else "--squash"

    try:
        result = subprocess.run(
            [
                gh_path, "pr", "merge",
                str(pr_number),
                "--repo", repo,
                "--auto",
                strategy_flag,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(
                f"Failed to auto-merge {repo}#{pr_number}: {result.stderr.strip()}"
            )
            return False
        logger.info(f"Auto-merge enabled for {repo}#{pr_number}")
        return True
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout auto-merging {repo}#{pr_number}")
        return False
    except FileNotFoundError:
        logger.error(f"{gh_path} not found")
        return False
    except Exception as e:
        logger.warning(f"Error auto-merging {repo}#{pr_number}: {e}")
        return False


# Pre-built messages for common reactions
CI_FAILURE_MESSAGE = (
    "CI is failing on your PR. Run `gh pr checks` to see failures, fix them, and push."
)

CHANGES_REQUESTED_MESSAGE = (
    "There are review comments on your PR. Check with `gh pr view --comments`. "
    "Address each one, push fixes."
)
