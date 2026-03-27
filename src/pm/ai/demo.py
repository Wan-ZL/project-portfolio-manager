"""Demo mode data for showcasing the TUI without real GitHub connections."""
from __future__ import annotations

from datetime import datetime

from pm.github.pr import EnhancedPR
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo


# Pre-generated AI summaries for demo mode
DEMO_SUMMARIES = {
    "401K Website": {
        "one_line_status": "Frontend mobile responsive redesign 80% complete, backend auth module has a login flow bug",
        "key_progress": [
            "Mobile responsive layout PR #38 approved and passing CI",
            "Component refactoring PR #35 under review",
            "Backend API endpoint update ready to merge",
        ],
        "issues_needing_attention": [
            "PR #42 fix auth bug - CI failing, 3 unresolved review comments",
            "Database migration PR #10 still pending review",
        ],
        "suggested_next_steps": [
            "Fix CI on PR #42 (auth bug) - highest priority blocker",
            "Merge PR #38 (mobile layout) - already approved",
            "Review and merge PR #12 (API update) - approved and green",
        ],
    },
    "Side Project": {
        "one_line_status": "Project idle for 2 weeks, dependency update PR waiting for review",
        "key_progress": [
            "Dark mode support PR ready for review",
        ],
        "issues_needing_attention": [
            "Dependency update PR has been open for 14 days - potential security risk",
            "No active development sessions",
        ],
        "suggested_next_steps": [
            "Review and merge dependency update PR #7",
            "Review dark mode PR #5 and provide feedback",
        ],
    },
    "FAA Project": {
        "one_line_status": "CI failing on main branch, compliance documentation blocked on API schema changes",
        "key_progress": [
            "New API validation PR #85 passing all checks",
        ],
        "issues_needing_attention": [
            "PR #89 compliance checks - CI failing, 5 unresolved comments",
            "Compliance documentation blocked on API schema",
            "2 active agent sessions working on fixes",
        ],
        "suggested_next_steps": [
            "Address review comments on PR #89 (compliance) - critical path",
            "Merge PR #85 (API validation) once reviewed",
            "Unblock documentation by finalizing API schema",
        ],
    },
    "Internal Tool": {
        "one_line_status": "Stable, single docs PR approved and ready to merge",
        "key_progress": [
            "README update PR #15 approved and CI green",
            "No outstanding issues",
        ],
        "issues_needing_attention": [],
        "suggested_next_steps": [
            "Merge PR #15 (docs update) - ready to go",
        ],
    },
}

DEMO_SUGGESTIONS = [
    {
        "priority": "high",
        "project": "FAA Project",
        "action": "Fix CI and address 5 review comments on PR #89",
        "reason": "Compliance checks are on the critical path, CI failure blocks the whole team",
    },
    {
        "priority": "high",
        "project": "401K Website",
        "action": "Fix auth bug CI failure on PR #42",
        "reason": "Auth bug in login flow affects end users, 3 review comments unresolved",
    },
    {
        "priority": "medium",
        "project": "401K Website",
        "action": "Merge approved PR #38 (mobile responsive layout)",
        "reason": "Already approved with passing CI, low risk merge to ship mobile improvements",
    },
    {
        "priority": "medium",
        "project": "Side Project",
        "action": "Review and merge dependency update PR #7",
        "reason": "Open for 14 days, may contain security patches that need to ship",
    },
    {
        "priority": "low",
        "project": "Internal Tool",
        "action": "Merge docs PR #15",
        "reason": "Approved and green, quick win to keep the repo clean",
    },
    {
        "priority": "low",
        "project": "FAA Project",
        "action": "Review API validation PR #85",
        "reason": "Ready for review, will unblock documentation work downstream",
    },
]


def get_demo_projects() -> list[ProjectInfo]:
    """Get demo project list with pre-generated summaries."""
    return [
        ProjectInfo(
            name="401K Website",
            account="Personal",
            repos=["owner/401k-frontend", "owner/401k-backend"],
            open_prs=5,
            active_sessions=1,
            status="green",
            summary=(
                "Frontend mobile responsive redesign 80% complete. "
                "Backend auth module has a login flow bug that needs attention."
            ),
            instructions="Focus on mobile responsive design.\nUse Tailwind CSS for styling.",
            assets=["~/designs/401k-mockup.png", "~/designs/401k-flow.pdf"],
        ),
        ProjectInfo(
            name="Side Project",
            account="Personal",
            repos=["owner/side-project"],
            open_prs=2,
            active_sessions=0,
            status="yellow",
            summary=(
                "Project idle for 2 weeks. Dependency update PR waiting for review. "
                "Dark mode support PR ready for feedback."
            ),
        ),
        ProjectInfo(
            name="FAA Project",
            account="Company",
            repos=["company-org/faa-main", "company-org/faa-docs"],
            open_prs=8,
            active_sessions=2,
            status="red",
            summary=(
                "CI failing on compliance checks. 5 unresolved review comments. "
                "Documentation blocked on API schema changes."
            ),
            instructions="Follow FAA compliance guidelines.\nAll changes require compliance review.",
        ),
        ProjectInfo(
            name="Internal Tool",
            account="Company",
            repos=["company-org/internal-tool"],
            open_prs=1,
            active_sessions=0,
            status="green",
            summary=(
                "Stable and up to date. Docs PR approved and ready to merge."
            ),
        ),
    ]


def get_demo_prs(project_name: str) -> list[EnhancedPR]:
    """Get demo PRs for a project."""
    prs_data: dict[str, list[EnhancedPR]] = {
        "401K Website": [
            EnhancedPR(
                repo_id="owner/401k-frontend", number=42, title="Fix auth bug in login flow",
                state="open", author="ai-bot", ci_status="failing", review_status="changes_requested",
                created_at=datetime(2026, 3, 20), updated_at=datetime(2026, 3, 25),
                unresolved_count=3, needs_attention=True,
            ),
            EnhancedPR(
                repo_id="owner/401k-frontend", number=38, title="Add mobile responsive layout",
                state="open", author="ai-bot", ci_status="passing", review_status="approved",
                created_at=datetime(2026, 3, 18), updated_at=datetime(2026, 3, 24),
            ),
            EnhancedPR(
                repo_id="owner/401k-frontend", number=35, title="Refactor component structure",
                state="open", author="zelin", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 15), updated_at=datetime(2026, 3, 22),
            ),
            EnhancedPR(
                repo_id="owner/401k-backend", number=12, title="API endpoint update",
                state="open", author="zelin", ci_status="passing", review_status="approved",
                created_at=datetime(2026, 3, 10), updated_at=datetime(2026, 3, 20),
            ),
            EnhancedPR(
                repo_id="owner/401k-backend", number=10, title="Database migration v2",
                state="open", author="ai-bot", ci_status="pending", review_status="pending",
                created_at=datetime(2026, 3, 8), updated_at=datetime(2026, 3, 19),
            ),
        ],
        "Side Project": [
            EnhancedPR(
                repo_id="owner/side-project", number=7, title="Update dependencies",
                state="open", author="dependabot", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 12), updated_at=datetime(2026, 3, 12),
            ),
            EnhancedPR(
                repo_id="owner/side-project", number=5, title="Add dark mode support",
                state="open", author="zelin", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 5), updated_at=datetime(2026, 3, 10),
            ),
        ],
        "FAA Project": [
            EnhancedPR(
                repo_id="company-org/faa-main", number=89, title="Update compliance checks",
                state="open", author="ai-bot", ci_status="failing", review_status="changes_requested",
                created_at=datetime(2026, 3, 22), updated_at=datetime(2026, 3, 25),
                unresolved_count=5, needs_attention=True,
            ),
            EnhancedPR(
                repo_id="company-org/faa-main", number=85, title="Add new API validation",
                state="open", author="colleague", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 20), updated_at=datetime(2026, 3, 24),
            ),
            EnhancedPR(
                repo_id="company-org/faa-main", number=82, title="Fix rate limiter",
                state="open", author="ai-bot", ci_status="passing", review_status="approved",
                created_at=datetime(2026, 3, 18), updated_at=datetime(2026, 3, 23),
            ),
            EnhancedPR(
                repo_id="company-org/faa-main", number=78, title="Refactor error handling",
                state="open", author="colleague", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 15), updated_at=datetime(2026, 3, 22),
            ),
            EnhancedPR(
                repo_id="company-org/faa-docs", number=23, title="Update API documentation",
                state="open", author="zelin", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 21), updated_at=datetime(2026, 3, 25),
            ),
            EnhancedPR(
                repo_id="company-org/faa-docs", number=21, title="Add compliance guide",
                state="open", author="ai-bot", ci_status="pending", review_status="pending",
                created_at=datetime(2026, 3, 19), updated_at=datetime(2026, 3, 24),
            ),
            EnhancedPR(
                repo_id="company-org/faa-docs", number=19, title="Fix broken links",
                state="open", author="colleague", ci_status="passing", review_status="approved",
                created_at=datetime(2026, 3, 17), updated_at=datetime(2026, 3, 23),
            ),
            EnhancedPR(
                repo_id="company-org/faa-docs", number=17, title="Update README",
                state="open", author="zelin", ci_status="passing", review_status="pending",
                created_at=datetime(2026, 3, 14), updated_at=datetime(2026, 3, 20),
            ),
        ],
        "Internal Tool": [
            EnhancedPR(
                repo_id="company-org/internal-tool", number=15, title="Update README docs",
                state="open", author="zelin", ci_status="passing", review_status="approved",
                created_at=datetime(2026, 3, 24), updated_at=datetime(2026, 3, 25),
            ),
        ],
    }
    return prs_data.get(project_name, [])


def get_demo_sessions(project_name: str) -> list[SessionInfo]:
    """Get demo sessions for a project."""
    sessions_data: dict[str, list[SessionInfo]] = {
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
            SessionInfo(
                id="s-003", project="FAA Project", task="Fix CI pipeline",
                agent="claude-code", status="paused",
                created_at=datetime(2026, 3, 24, 16, 0),
                branch="pm/fix-ci",
            ),
        ],
    }
    return sessions_data.get(project_name, [])


def is_demo_mode() -> bool:
    """Check if demo mode should be active.

    Returns False if:
    - credentials.yaml has a valid account (even without config), OR
    - config.yaml exists AND has real projects (not just the sample placeholder)
    Returns True only if no credentials exist AND (no config OR config is placeholder-only).
    """
    from pm.auth.credentials import load_credentials
    creds = load_credentials()
    accounts = creds.get("accounts", {})
    if accounts:
        # User has credentials, they want real data
        return False

    from pm.config.loader import DEFAULT_CONFIG_PATH, load_config, has_real_projects
    if not DEFAULT_CONFIG_PATH.exists():
        return True

    cfg = load_config()
    return not has_real_projects(cfg)
