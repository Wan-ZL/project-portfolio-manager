from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EnhancedPR:
    """Enhancement layer: local metadata on top of GitHub API data"""
    repo_id: str
    number: int
    title: str
    state: str  # open, closed, merged
    author: str
    created_at: datetime
    updated_at: datetime
    ci_status: str = "pending"  # passing, failing, pending
    review_status: str = "pending"  # approved, changes_requested, pending
    unresolved_count: int = 0
    is_read: bool = False
    is_starred: bool = False
    needs_attention: bool = False
    url: str = ""
    body: str = ""

    @property
    def status_color(self) -> str:
        if self.state == "merged":
            return "magenta"
        if self.ci_status == "failing":
            return "red"
        if self.review_status == "changes_requested":
            return "yellow"
        if self.ci_status == "passing" and self.review_status == "approved":
            return "green"
        return "cyan"

    @property
    def status_icon(self) -> str:
        if self.state == "merged":
            return "merged"
        if self.ci_status == "failing":
            return "red"
        if self.review_status == "changes_requested":
            return "yellow"
        if self.ci_status == "passing" and self.review_status == "approved":
            return "green"
        return "cyan"
