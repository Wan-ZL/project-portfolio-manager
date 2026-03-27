"""Review comment tracking and fingerprinting via gh CLI (T6)."""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

BOT_SUFFIXES = [
    "[bot]",
]

BOT_USERNAMES = {
    "github-actions[bot]",
    "dependabot[bot]",
    "renovate[bot]",
    "codecov[bot]",
    "sonarcloud[bot]",
    "vercel[bot]",
    "netlify[bot]",
}


def is_bot_user(username: str) -> bool:
    """Check if a username belongs to a bot."""
    if not username:
        return False
    lower = username.lower()
    if lower in BOT_USERNAMES:
        return True
    for suffix in BOT_SUFFIXES:
        if lower.endswith(suffix):
            return True
    return False


@dataclass
class ReviewDecision:
    user: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    id: int = 0


@dataclass
class ReviewComment:
    id: int
    user: str
    body: str
    path: str = ""
    line: int | None = None
    in_reply_to_id: int | None = None


@dataclass
class ReviewStatus:
    """Aggregated review status for a PR."""
    state: str  # approved, changes_requested, pending
    decisions: list[ReviewDecision] = field(default_factory=list)
    comments: list[ReviewComment] = field(default_factory=list)
    unresolved_count: int = 0
    fingerprint: str = ""


class ReviewMonitor:
    """Monitors review decisions and inline comments for PRs."""

    def __init__(self, gh_path: str = "gh"):
        self.gh_path = gh_path

    def get_review_decisions(self, pr_number: int, repo: str) -> list[ReviewDecision]:
        """Get review decisions (APPROVED, CHANGES_REQUESTED, etc.) for a PR."""
        owner, repo_name = _parse_repo(repo)
        try:
            result = subprocess.run(
                [
                    self.gh_path, "api",
                    f"repos/{owner}/{repo_name}/pulls/{pr_number}/reviews",
                    "--jq", ".",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(
                    f"gh api reviews failed for {repo}#{pr_number}: {result.stderr.strip()}"
                )
                return []

            data = json.loads(result.stdout)
            decisions = []
            for review in data:
                user = review.get("user", {}).get("login", "")
                state = review.get("state", "")
                review_id = review.get("id", 0)
                if not is_bot_user(user):
                    decisions.append(ReviewDecision(
                        user=user,
                        state=state,
                        id=review_id,
                    ))
            return decisions
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout getting reviews for {repo}#{pr_number}")
            return []
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Error parsing reviews for {repo}#{pr_number}: {e}")
            return []

    def get_review_comments(self, pr_number: int, repo: str) -> list[ReviewComment]:
        """Get inline review comments for a PR, filtering out bots."""
        owner, repo_name = _parse_repo(repo)
        try:
            result = subprocess.run(
                [
                    self.gh_path, "api",
                    f"repos/{owner}/{repo_name}/pulls/{pr_number}/comments",
                    "--jq", ".",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(
                    f"gh api comments failed for {repo}#{pr_number}: {result.stderr.strip()}"
                )
                return []

            data = json.loads(result.stdout)
            comments = []
            for comment in data:
                user = comment.get("user", {}).get("login", "")
                if is_bot_user(user):
                    continue
                comments.append(ReviewComment(
                    id=comment.get("id", 0),
                    user=user,
                    body=comment.get("body", ""),
                    path=comment.get("path", ""),
                    line=comment.get("line"),
                    in_reply_to_id=comment.get("in_reply_to_id"),
                ))
            return comments
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout getting comments for {repo}#{pr_number}")
            return []
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Error parsing comments for {repo}#{pr_number}: {e}")
            return []

    def compute_fingerprint(self, comments: list[ReviewComment]) -> str:
        """Compute a fingerprint from comment IDs to detect changes.

        Sorted comment IDs joined as a string. Any change in comments
        (new, deleted, resolved) will produce a different fingerprint.
        """
        ids = sorted(c.id for c in comments if c.id)
        return ",".join(str(i) for i in ids)

    def determine_review_state(self, decisions: list[ReviewDecision]) -> str:
        """Determine overall review state from individual decisions.

        Uses the latest non-dismissed decision per reviewer.
        """
        if not decisions:
            return "pending"

        # Get latest decision per reviewer (last one wins)
        latest: dict[str, str] = {}
        for d in decisions:
            if d.state == "DISMISSED":
                latest.pop(d.user, None)
            else:
                latest[d.user] = d.state

        if not latest:
            return "pending"

        states = set(latest.values())

        if "CHANGES_REQUESTED" in states:
            return "changes_requested"
        if "APPROVED" in states:
            return "approved"
        return "pending"

    def count_unresolved(self, comments: list[ReviewComment]) -> int:
        """Count unresolved comments (top-level comments without replies).

        A comment is considered unresolved if it has no reply from
        a different user. This is a heuristic since GitHub's resolved
        state is not available through this API endpoint.
        """
        # Build set of comment IDs that are replies
        reply_targets = set()
        for c in comments:
            if c.in_reply_to_id is not None:
                reply_targets.add(c.in_reply_to_id)

        # Top-level comments (not a reply themselves)
        top_level = [c for c in comments if c.in_reply_to_id is None]

        # Unresolved = top-level comments that have no replies
        unresolved = [c for c in top_level if c.id not in reply_targets]
        return len(unresolved)

    def get_review_status(self, pr_number: int, repo: str) -> ReviewStatus:
        """Get complete review status for a PR."""
        decisions = self.get_review_decisions(pr_number, repo)
        comments = self.get_review_comments(pr_number, repo)
        state = self.determine_review_state(decisions)
        fingerprint = self.compute_fingerprint(comments)
        unresolved = self.count_unresolved(comments)

        return ReviewStatus(
            state=state,
            decisions=decisions,
            comments=comments,
            unresolved_count=unresolved,
            fingerprint=fingerprint,
        )


def _parse_repo(repo: str) -> tuple[str, str]:
    """Parse owner/repo into (owner, repo_name)."""
    parts = repo.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid repo format, expected owner/repo: {repo}")
    return parts[0], parts[1]
