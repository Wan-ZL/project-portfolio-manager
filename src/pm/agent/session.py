from __future__ import annotations

import logging
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pm.agent.base import ActivityState, LaunchOptions
from pm.agent.registry import get_agent
from pm.config.models import PMConfig
from pm.db.database import Database
from pm.db.models import Session as DBSession
from pm.worktree.manager import WorktreeManager

logger = logging.getLogger(__name__)


@dataclass
class SessionCreateOptions:
    project: str
    task_description: str
    agent_name: str = "claude-code"
    model: str = ""
    permissions: str = "default"


class SessionManager:
    """tmux session management for agent tasks (T1)"""

    def __init__(self, config: PMConfig, db: Database, worktree_mgr: Optional[WorktreeManager] = None):
        self.config = config
        self.db = db
        self.worktree_mgr = worktree_mgr or WorktreeManager(
            config.defaults.worktree_base
        )

    def create_session(self, opts: SessionCreateOptions) -> DBSession:
        """Create a tmux session with optional worktree and launch agent."""
        agent = get_agent(opts.agent_name)
        if not agent:
            raise ValueError(f"Unknown agent: {opts.agent_name}")

        session_id = f"s-{uuid.uuid4().hex[:8]}"
        slug = self._slugify(opts.task_description)
        tmux_name = f"pm_{self._slugify(opts.project)}_{slug}"
        # tmux session names can't exceed 256 chars, truncate
        tmux_name = tmux_name[:80]

        branch_name = WorktreeManager.make_branch_name(opts.project, opts.task_description)
        worktree_path = ""

        # Create worktree if project has a local_path and agent supports it
        project_config = self.config.projects.get(opts.project)
        local_path = project_config.local_path if project_config else ""
        if local_path and agent.supports_worktree():
            try:
                worktree_path = self.worktree_mgr.create_worktree(
                    opts.project, branch_name, local_path
                )
            except Exception as e:
                logger.warning(f"Failed to create worktree: {e}")

        # Determine work directory
        work_dir = worktree_path or local_path or ""

        # Build agent launch command
        permissions = opts.permissions
        if permissions == "default" and project_config and project_config.agent_config:
            permissions = project_config.agent_config.permissions

        model = opts.model
        if not model and project_config and project_config.agent_config:
            model = project_config.agent_config.model

        launch_opts = LaunchOptions(
            prompt=opts.task_description,
            work_dir=work_dir,
            model=model,
            permissions=permissions,
        )
        agent_cmd = agent.launch_command(launch_opts)

        # Create tmux session
        self._create_tmux_session(tmux_name, work_dir, agent_cmd)

        # Save to database
        db_session = DBSession(
            id=session_id,
            project=opts.project,
            task_description=opts.task_description,
            agent=opts.agent_name,
            tmux_session=tmux_name,
            worktree_path=worktree_path,
            branch=branch_name,
            status="running",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self.db.upsert_session(db_session)
        return db_session

    def list_sessions(self, project: str | None = None) -> list[DBSession]:
        """List sessions, verifying tmux is alive."""
        if project:
            sessions = self.db.get_sessions_by_project(project)
        else:
            sessions = self.db.get_active_sessions()

        active_tmux = self._list_tmux_sessions()
        for s in sessions:
            if s.status == "running" and s.tmux_session not in active_tmux:
                s.status = "exited"
                s.updated_at = datetime.now()
                self.db.upsert_session(s)

        return sessions

    def attach_session(self, session_id: str) -> bool:
        """Attach to a tmux session (for CLI use)."""
        session = self._get_db_session(session_id)
        if not session or not session.tmux_session:
            return False

        result = subprocess.run(
            ["tmux", "attach-session", "-t", session.tmux_session],
            capture_output=False,
        )
        return result.returncode == 0

    def detach_session(self, session_id: str) -> bool:
        """Detach from a tmux session."""
        session = self._get_db_session(session_id)
        if not session or not session.tmux_session:
            return False

        result = subprocess.run(
            ["tmux", "detach-client", "-s", session.tmux_session],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def kill_session(self, session_id: str) -> bool:
        """Kill a tmux session and clean up worktree."""
        session = self._get_db_session(session_id)
        if not session:
            return False

        # Kill tmux session
        if session.tmux_session:
            subprocess.run(
                ["tmux", "kill-session", "-t", session.tmux_session],
                capture_output=True,
                text=True,
            )

        # Clean up worktree
        if session.worktree_path:
            project_config = self.config.projects.get(session.project)
            if project_config and project_config.local_path:
                try:
                    self.worktree_mgr.remove_worktree(
                        session.worktree_path, project_config.local_path
                    )
                except Exception as e:
                    logger.warning(f"Failed to remove worktree: {e}")

        # Update DB
        session.status = "completed"
        session.updated_at = datetime.now()
        self.db.upsert_session(session)
        return True

    def pause_session(self, session_id: str) -> bool:
        """Pause a session by sending Ctrl+C."""
        session = self._get_db_session(session_id)
        if not session or not session.tmux_session:
            return False

        # Send Ctrl+C
        subprocess.run(
            ["tmux", "send-keys", "-t", session.tmux_session, "C-c", ""],
            capture_output=True,
            text=True,
        )

        session.status = "paused"
        session.updated_at = datetime.now()
        self.db.upsert_session(session)
        return True

    def resume_session(self, session_id: str) -> bool:
        """Resume a paused session by relaunching agent."""
        session = self._get_db_session(session_id)
        if not session or not session.tmux_session:
            return False

        agent = get_agent(session.agent)
        if not agent:
            return False

        project_config = self.config.projects.get(session.project)
        model = ""
        permissions = "default"
        if project_config and project_config.agent_config:
            model = project_config.agent_config.model
            permissions = project_config.agent_config.permissions

        launch_opts = LaunchOptions(
            prompt=session.task_description or "",
            work_dir=session.worktree_path or "",
            model=model,
            permissions=permissions,
        )
        agent_cmd = agent.launch_command(launch_opts)
        cmd_str = " ".join(agent_cmd)

        subprocess.run(
            ["tmux", "send-keys", "-t", session.tmux_session, cmd_str, "Enter"],
            capture_output=True,
            text=True,
        )

        session.status = "running"
        session.updated_at = datetime.now()
        self.db.upsert_session(session)
        return True

    def get_session_output(self, session_id: str, lines: int = 500) -> str:
        """Capture terminal output from tmux session."""
        session = self._get_db_session(session_id)
        if not session or not session.tmux_session:
            return ""

        result = subprocess.run(
            ["tmux", "capture-pane", "-p", "-t", session.tmux_session, "-S", f"-{lines}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return ""
        return result.stdout

    def send_to_session(self, session_id: str, text: str) -> bool:
        """Send text to a tmux session."""
        session = self._get_db_session(session_id)
        if not session or not session.tmux_session:
            return False

        result = subprocess.run(
            ["tmux", "send-keys", "-t", session.tmux_session, text, "Enter"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def get_activity_state(self, session_id: str) -> ActivityState:
        """Detect the current activity state of a session."""
        session = self._get_db_session(session_id)
        if not session:
            return ActivityState.EXITED

        agent = get_agent(session.agent)
        if not agent:
            return ActivityState.IDLE

        output = self.get_session_output(session_id)
        return agent.detect_activity(output)

    def _create_tmux_session(self, name: str, work_dir: str, agent_cmd: list[str]) -> None:
        """Create a new tmux session and send the agent command."""
        create_cmd = ["tmux", "new-session", "-d", "-s", name]
        if work_dir:
            create_cmd.extend(["-c", work_dir])

        result = subprocess.run(create_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create tmux session: {result.stderr.strip()}")

        # Send the agent command
        cmd_str = " ".join(agent_cmd)
        subprocess.run(
            ["tmux", "send-keys", "-t", name, cmd_str, "Enter"],
            capture_output=True,
            text=True,
        )

    def _list_tmux_sessions(self) -> set[str]:
        """List currently active tmux sessions."""
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return set()
        return set(result.stdout.strip().splitlines())

    def _get_db_session(self, session_id: str) -> Optional[DBSession]:
        """Get a session from the database."""
        with self.db.get_session() as db_sess:
            return db_sess.get(DBSession, session_id)

    @staticmethod
    def _slugify(text: str) -> str:
        """Create a URL-friendly slug from text."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
        return slug[:30]
