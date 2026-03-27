from __future__ import annotations

import json
from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Static, Footer, Input, Label
from textual.worker import Worker, WorkerState

from pm.github.pr import EnhancedPR
from pm.tui.widgets.detail_panel import DetailPanel
from pm.tui.widgets.project_list import ProjectInfo, ProjectList
from pm.tui.widgets.session_list import SessionInfo
from pm.tui.widgets.status_bar import StatusBar


def get_sample_projects() -> list[ProjectInfo]:
    return [
        ProjectInfo(
            name="401K Website",
            account="Personal",
            repos=["owner/401k-frontend", "owner/401k-backend"],
            open_prs=5,
            active_sessions=1,
            status="green",
            summary=(
                "Frontend development is progressing well. The mobile responsive "
                "redesign is 80% complete. Backend auth module has a bug in the "
                "login flow that needs attention before the next release."
            ),
            instructions="Focus on mobile responsive design.\nUse Tailwind CSS for styling.",
            assets=["~/designs/401k-mockup.png"],
        ),
        ProjectInfo(
            name="Side Project",
            account="Personal",
            repos=["owner/side-project"],
            open_prs=2,
            active_sessions=0,
            status="yellow",
            summary=(
                "Project has been idle for 2 weeks. Two PRs are awaiting review. "
                "Consider prioritizing the dependency update PR to avoid security issues."
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
                "CI is failing on the main branch. Three PRs have unresolved review "
                "comments. The compliance documentation update is blocked on the "
                "API schema changes."
            ),
            instructions="Follow FAA compliance guidelines.",
        ),
        ProjectInfo(
            name="Internal Tool",
            account="Company",
            repos=["company-org/internal-tool"],
            open_prs=1,
            active_sessions=0,
            status="green",
            summary=(
                "Stable and up to date. The single open PR is a minor docs update "
                "that's approved and ready to merge."
            ),
        ),
    ]


def get_sample_prs(project_name: str) -> list[EnhancedPR]:
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


def get_sample_sessions(project_name: str) -> list[SessionInfo]:
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


def _is_demo(screen) -> bool:
    """Check if the app is in demo mode."""
    try:
        return getattr(screen.app, '_demo', False) or getattr(screen.app, 'demo_mode', False)
    except Exception:
        return False


def _get_projects(screen) -> list[ProjectInfo]:
    """Get projects - demo or sample data."""
    if _is_demo(screen):
        from pm.ai.demo import get_demo_projects
        return get_demo_projects()
    return get_sample_projects()


def _get_prs(screen, project_name: str) -> list[EnhancedPR]:
    """Get PRs - demo or sample data."""
    if _is_demo(screen):
        from pm.ai.demo import get_demo_prs
        return get_demo_prs(project_name)
    return get_sample_prs(project_name)


def _get_sessions(screen, project_name: str) -> list[SessionInfo]:
    """Get sessions - demo or sample data."""
    if _is_demo(screen):
        from pm.ai.demo import get_demo_sessions
        return get_demo_sessions(project_name)
    return get_sample_sessions(project_name)


def _get_ai_summary(screen, project_name: str) -> dict | None:
    """Get AI summary for a project (from demo data or cache)."""
    if _is_demo(screen):
        from pm.ai.demo import DEMO_SUMMARIES
        return DEMO_SUMMARIES.get(project_name)
    return None


def _get_ai_suggestions(screen) -> list[dict] | None:
    """Get AI suggestions (from demo data or cache)."""
    if _is_demo(screen):
        from pm.ai.demo import DEMO_SUGGESTIONS
        return DEMO_SUGGESTIONS
    return None


class PortfolioScreen(Screen):
    DEFAULT_CSS = """
    PortfolioScreen {
        layout: vertical;
    }

    #portfolio-title {
        dock: top;
        height: 3;
        content-align: center middle;
        background: $primary-background-darken-1;
        color: $primary-lighten-2;
        text-style: bold;
        border-bottom: solid $primary 40%;
        padding: 0 2;
    }

    #portfolio-body {
        layout: horizontal;
        height: 1fr;
    }

    #left-panel {
        width: 30%;
        min-width: 24;
        border-right: solid $primary 30%;
        background: $surface-darken-1;
        padding: 0;
    }

    #left-panel-title {
        dock: top;
        height: 2;
        padding: 0 1;
        background: $surface-darken-2;
        color: $primary;
        text-style: bold;
        border-bottom: solid $surface-lighten-1;
    }

    #right-panel {
        width: 70%;
        background: $surface;
        padding: 0;
    }

    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-background-darken-2;
        color: $text;
        padding: 0 1;
    }

    #portfolio-new-task-container {
        dock: bottom;
        height: auto;
        max-height: 5;
        background: $surface-darken-2;
        padding: 0 1;
        display: none;
    }

    #portfolio-new-task-container.visible {
        display: block;
    }

    #portfolio-new-task-input {
        width: 100%;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task_input_visible = False
        self._ai_summaries: dict[str, dict] = {}
        self._ai_suggestions: list[dict] = []
        self._loading_summary = False
        self._loading_suggestions = False

    BINDINGS = [
        Binding("q", "quit_app", "Quit"),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("tab", "next_tab", "Next Tab"),
        Binding("shift+tab", "prev_tab", "Prev Tab"),
        Binding("enter", "enter_project", "Open"),
        Binding("n", "new_task", "New Task"),
        Binding("s", "suggest", "Suggest"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]Portfolio Manager[/bold]  [dim]\u2502  Your projects at a glance[/dim]",
            id="portfolio-title",
        )
        with Horizontal(id="portfolio-body"):
            with Container(id="left-panel"):
                yield Static("[bold]Projects[/bold]", id="left-panel-title")
                yield ProjectList()
            with Container(id="right-panel"):
                yield DetailPanel()
        with Container(id="portfolio-new-task-container"):
            yield Label("[bold cyan]New Task:[/bold cyan] Enter task description for current project")
            yield Input(placeholder="Describe the task...", id="portfolio-new-task-input")
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        projects = _get_projects(self)
        project_list = self.query_one(ProjectList)
        project_list.set_projects(projects)

        # Pre-load AI summaries for demo mode
        if _is_demo(self):
            from pm.ai.demo import DEMO_SUMMARIES, DEMO_SUGGESTIONS
            self._ai_summaries = dict(DEMO_SUMMARIES)
            self._ai_suggestions = list(DEMO_SUGGESTIONS)
        else:
            # Background loading placeholder for real mode
            self._start_background_loading()

    def _start_background_loading(self) -> None:
        """Start background loading of data. Uses Workers to avoid blocking."""
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Loading project data...")
        # In a real implementation with GitHub API, this would use self.run_worker()
        # For now, just clear the loading message
        self.set_timer(1, lambda: status_bar.set_message(""))

    def on_project_list_project_selected(self, event: ProjectList.ProjectSelected) -> None:
        detail = self.query_one(DetailPanel)
        detail.set_project(event.project)
        detail.set_prs(_get_prs(self, event.project.name))
        detail.set_sessions(_get_sessions(self, event.project.name))

        # Update status panel with AI summary
        ai_summary = self._ai_summaries.get(event.project.name)
        if ai_summary:
            detail.set_ai_summary(ai_summary)
        detail.set_ai_suggestions(self._ai_suggestions)

    def on_project_list_project_activated(self, event: ProjectList.ProjectActivated) -> None:
        from pm.tui.screens.project import ProjectScreen
        prs = _get_prs(self, event.project.name)
        sessions = _get_sessions(self, event.project.name)
        self.app.push_screen(ProjectScreen(
            project=event.project, prs=prs, sessions=sessions,
        ))

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_cursor_down(self) -> None:
        self.query_one(ProjectList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(ProjectList).action_cursor_up()

    def action_next_tab(self) -> None:
        self.query_one(DetailPanel).action_next_tab()

    def action_prev_tab(self) -> None:
        self.query_one(DetailPanel).action_prev_tab()

    def action_enter_project(self) -> None:
        project_list = self.query_one(ProjectList)
        if project_list.current_project:
            project_list.action_activate()

    def action_refresh(self) -> None:
        status_bar = self.query_one(StatusBar)
        status_bar.set_message("Refreshing... (cache invalidated)")

        # Invalidate AI summaries
        self._ai_summaries.clear()
        self._ai_suggestions.clear()

        # Reload data
        projects = _get_projects(self)
        project_list = self.query_one(ProjectList)
        project_list.set_projects(projects)

        # Re-load AI data
        if _is_demo(self):
            from pm.ai.demo import DEMO_SUMMARIES, DEMO_SUGGESTIONS
            self._ai_summaries = dict(DEMO_SUMMARIES)
            self._ai_suggestions = list(DEMO_SUGGESTIONS)

        self.set_timer(2, lambda: status_bar.set_message(""))

    def action_suggest(self) -> None:
        status_bar = self.query_one(StatusBar)
        detail = self.query_one(DetailPanel)

        if _is_demo(self):
            from pm.ai.demo import DEMO_SUGGESTIONS
            self._ai_suggestions = list(DEMO_SUGGESTIONS)
            detail.set_ai_suggestions(self._ai_suggestions)
            status_bar.set_message("AI suggestions loaded")
            self.set_timer(3, lambda: status_bar.set_message(""))
        else:
            if self._loading_suggestions:
                status_bar.set_message("Already generating suggestions...")
                return

            self._loading_suggestions = True
            status_bar.set_message("Generating AI suggestions...")
            detail.show_suggestions_loading()

            self.run_worker(self._generate_suggestions_worker, thread=True)

    async def _generate_suggestions_worker(self) -> list[dict]:
        """Worker to generate AI suggestions in background."""
        try:
            from pm.ai.suggest import AISuggestionEngine
            engine = AISuggestionEngine()

            projects = _get_projects(self)
            projects_data = []
            for p in projects:
                prs = _get_prs(self, p.name)
                projects_data.append({
                    "name": p.name,
                    "summary": self._ai_summaries.get(p.name, {}),
                    "open_prs_count": len(prs),
                    "active_sessions_count": p.active_sessions,
                    "failing_ci_count": sum(1 for pr in prs if pr.ci_status == "failing"),
                    "changes_requested_count": sum(1 for pr in prs if pr.review_status == "changes_requested"),
                })

            suggestions = engine.generate_suggestions(projects_data)
            return [s.to_dict() for s in suggestions]
        except Exception as e:
            return []

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS and self._loading_suggestions:
            self._loading_suggestions = False
            result = event.worker.result
            if result:
                self._ai_suggestions = result
                try:
                    detail = self.query_one(DetailPanel)
                    detail.set_ai_suggestions(self._ai_suggestions)
                except Exception:
                    pass
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("AI suggestions ready")
            self.set_timer(3, lambda: status_bar.set_message(""))

    def action_new_task(self) -> None:
        project_list = self.query_one(ProjectList)
        if not project_list.current_project:
            status_bar = self.query_one(StatusBar)
            status_bar.set_message("No project selected")
            return
        self._task_input_visible = True
        container = self.query_one("#portfolio-new-task-container")
        container.add_class("visible")
        try:
            self.query_one("#portfolio-new-task-input", Input).focus()
        except Exception:
            pass

    def _hide_task_input(self) -> None:
        self._task_input_visible = False
        container = self.query_one("#portfolio-new-task-container")
        container.remove_class("visible")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "portfolio-new-task-input":
            task_desc = event.value.strip()
            if task_desc:
                status_bar = self.query_one(StatusBar)
                project_list = self.query_one(ProjectList)
                project_name = project_list.current_project.name if project_list.current_project else "unknown"
                status_bar.set_message(f"Creating task for {project_name}: {task_desc}...")
                event.input.value = ""
                self._hide_task_input()
                self.set_timer(
                    2, lambda: status_bar.set_message(f"Task created: {task_desc}")
                )

    def action_help(self) -> None:
        from pm.tui.screens.help import HelpScreen
        self.app.push_screen(HelpScreen())
