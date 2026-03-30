"""Shared test fixtures and helpers."""
from __future__ import annotations

from datetime import datetime

from pm.github.pr import EnhancedPR
from pm.tui.app import PMApp
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo


MOCK_PROJECTS = [
    ProjectInfo(
        name="401K Website", account="Personal",
        repos=["owner/401k-frontend", "owner/401k-backend"],
        open_prs=5, active_sessions=1, status="green",
        summary="Frontend mobile responsive redesign.",
    ),
    ProjectInfo(
        name="Side Project", account="Personal",
        repos=["owner/side-project"],
        open_prs=2, active_sessions=0, status="yellow",
        summary="Idle for 2 weeks.",
    ),
    ProjectInfo(
        name="FAA Project", account="Company",
        repos=["company-org/faa-main", "company-org/faa-docs"],
        open_prs=8, active_sessions=2, status="red",
        summary="CI failing on compliance checks.",
    ),
    ProjectInfo(
        name="Internal Tool", account="Company",
        repos=["company-org/internal-tool"],
        open_prs=1, active_sessions=0, status="green",
        summary="Stable and up to date.",
    ),
]

MOCK_PRS = {
    "401K Website": [
        EnhancedPR(
            repo_id="owner/401k-frontend", number=42, title="Fix auth bug",
            state="open", author="ai-bot", ci_status="failing",
            review_status="changes_requested",
            created_at=datetime(2026, 3, 20), updated_at=datetime(2026, 3, 25),
        ),
        EnhancedPR(
            repo_id="owner/401k-frontend", number=38, title="Add mobile layout",
            state="open", author="ai-bot", ci_status="passing",
            review_status="approved",
            created_at=datetime(2026, 3, 18), updated_at=datetime(2026, 3, 24),
        ),
        EnhancedPR(
            repo_id="owner/401k-frontend", number=35, title="Refactor components",
            state="open", author="zelin", ci_status="passing",
            review_status="pending",
            created_at=datetime(2026, 3, 15), updated_at=datetime(2026, 3, 22),
        ),
        EnhancedPR(
            repo_id="owner/401k-backend", number=12, title="API endpoint update",
            state="open", author="zelin", ci_status="passing",
            review_status="approved",
            created_at=datetime(2026, 3, 10), updated_at=datetime(2026, 3, 20),
        ),
        EnhancedPR(
            repo_id="owner/401k-backend", number=10, title="Database migration v2",
            state="open", author="ai-bot", ci_status="pending",
            review_status="pending",
            created_at=datetime(2026, 3, 8), updated_at=datetime(2026, 3, 19),
        ),
    ],
    "Side Project": [
        EnhancedPR(
            repo_id="owner/side-project", number=7, title="Update dependencies",
            state="open", author="dependabot", ci_status="passing",
            review_status="pending",
            created_at=datetime(2026, 3, 12), updated_at=datetime(2026, 3, 12),
        ),
    ],
    "FAA Project": [
        EnhancedPR(
            repo_id="company-org/faa-main", number=89, title="Update compliance",
            state="open", author="ai-bot", ci_status="failing",
            review_status="changes_requested",
            created_at=datetime(2026, 3, 22), updated_at=datetime(2026, 3, 25),
        ),
    ],
    "Internal Tool": [
        EnhancedPR(
            repo_id="company-org/internal-tool", number=15, title="Update README",
            state="open", author="zelin", ci_status="passing",
            review_status="approved",
            created_at=datetime(2026, 3, 24), updated_at=datetime(2026, 3, 25),
        ),
    ],
}

MOCK_SESSIONS = {
    "401K Website": [
        SessionInfo(
            id="s-001", project="401K Website", task="Fix auth bug",
            agent="claude-code", status="running",
            created_at=datetime(2026, 3, 25, 14, 30),
            branch="pm/fix-auth", pr_number=42,
        ),
    ],
    "FAA Project": [
        SessionInfo(
            id="s-002", project="FAA Project", task="Update compliance",
            agent="claude-code", status="running",
            created_at=datetime(2026, 3, 25, 10, 0),
            branch="pm/compliance", pr_number=89,
        ),
    ],
}


def make_seeded_app() -> PMApp:
    """Create a PMApp with mock data pre-seeded in the store.

    The store's load_initial and fetch_live are patched so on_mount
    uses our mock data instead of hitting real credentials/GitHub.
    """
    app = PMApp()

    # Seed the store
    app.store.set_projects(MOCK_PROJECTS, prs=MOCK_PRS, sessions=MOCK_SESSIONS)
    app.store.set_ai_summary("401K Website", {"one_line_status": "PR #42 auth bug CI failing"})

    # Patch load_initial to use our seeded data (returns "has_repos" so cards render)
    original_load_initial = app.store.load_initial

    def mock_load_initial():
        # Data is already set, just return "has_repos"
        return "has_repos"

    app.store.load_initial = mock_load_initial

    # Patch fetch_live to return our data (prevents live GitHub calls)
    def mock_fetch_live():
        return MOCK_PROJECTS, MOCK_PRS

    app.store.fetch_live = mock_fetch_live

    return app
