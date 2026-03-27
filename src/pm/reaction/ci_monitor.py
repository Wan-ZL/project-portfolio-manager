"""CI status monitoring via gh CLI (T5)."""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CIState(str, Enum):
    PASSING = "passing"
    FAILING = "failing"
    PENDING = "pending"
    NONE = "none"


@dataclass
class CheckResult:
    name: str
    state: str  # raw state from gh: SUCCESS, FAILURE, PENDING, etc.


class CIMonitor:
    """Monitors CI status for pull requests using gh CLI."""

    def __init__(self, gh_path: str = "gh"):
        self.gh_path = gh_path

    def get_checks(self, pr_number: int, repo: str) -> list[CheckResult]:
        """Get CI check results for a PR.

        Args:
            pr_number: The PR number
            repo: Repository in owner/repo format

        Returns:
            List of CheckResult objects
        """
        try:
            result = subprocess.run(
                [
                    self.gh_path, "pr", "checks",
                    str(pr_number),
                    "--repo", repo,
                    "--json", "name,state",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning(
                    f"gh pr checks failed for {repo}#{pr_number}: {result.stderr.strip()}"
                )
                return []

            data = json.loads(result.stdout)
            return [
                CheckResult(name=check.get("name", ""), state=check.get("state", ""))
                for check in data
            ]
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout getting checks for {repo}#{pr_number}")
            return []
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Error parsing checks for {repo}#{pr_number}: {e}")
            return []

    def aggregate_status(self, checks: list[CheckResult]) -> CIState:
        """Aggregate individual check states into an overall CI status.

        Rules:
            - No checks -> NONE
            - Any FAILURE -> FAILING
            - Any PENDING (and no failures) -> PENDING
            - All SUCCESS -> PASSING
        """
        if not checks:
            return CIState.NONE

        states = {c.state.upper() for c in checks}

        if "FAILURE" in states:
            return CIState.FAILING
        if "PENDING" in states or "QUEUED" in states or "IN_PROGRESS" in states:
            return CIState.PENDING
        if states <= {"SUCCESS", "SKIPPED", "NEUTRAL", "STALE"}:
            return CIState.PASSING

        return CIState.PENDING

    def get_ci_status(self, pr_number: int, repo: str) -> CIState:
        """Get aggregated CI status for a PR.

        Returns CIState enum value.
        """
        checks = self.get_checks(pr_number, repo)
        return self.aggregate_status(checks)
