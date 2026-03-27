from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class WorktreeInfo:
    path: str
    branch: str
    commit: str = ""


class WorktreeManager:
    """Git worktree lifecycle management (T2)"""

    def __init__(self, worktree_base: str = "~/.ppm/worktrees"):
        self.worktree_base = Path(worktree_base).expanduser()
        self.worktree_base.mkdir(parents=True, exist_ok=True)

    def create_worktree(self, project: str, branch_name: str, repo_path: str) -> str:
        """Create a git worktree for a project task.

        Returns the worktree path.
        """
        repo_path_obj = Path(repo_path).expanduser()
        if not repo_path_obj.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

        git_dir = repo_path_obj / ".git"
        if not git_dir.exists():
            raise ValueError(f"Not a git repository: {repo_path}")

        worktree_path = self.worktree_base / project / branch_name.replace("/", "_")
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            cwd=str(repo_path_obj),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Branch might already exist, try without -b
            result = subprocess.run(
                ["git", "worktree", "add", str(worktree_path), branch_name],
                cwd=str(repo_path_obj),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to create worktree: {result.stderr.strip()}")

        logger.info(f"Created worktree at {worktree_path} on branch {branch_name}")
        return str(worktree_path)

    def remove_worktree(self, worktree_path: str, repo_path: str) -> None:
        """Remove a git worktree."""
        result = subprocess.run(
            ["git", "worktree", "remove", worktree_path, "--force"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning(f"Failed to remove worktree {worktree_path}: {result.stderr.strip()}")

    def list_worktrees(self, repo_path: str) -> list[WorktreeInfo]:
        """List all worktrees for a repository."""
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []

        worktrees = []
        current: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    worktrees.append(WorktreeInfo(
                        path=current.get("path", ""),
                        branch=current.get("branch", ""),
                        commit=current.get("commit", ""),
                    ))
                current = {"path": line.split(" ", 1)[1]}
            elif line.startswith("HEAD "):
                current["commit"] = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                branch = line.split(" ", 1)[1]
                # Strip refs/heads/ prefix
                if branch.startswith("refs/heads/"):
                    branch = branch[len("refs/heads/"):]
                current["branch"] = branch
            elif line == "":
                pass

        if current:
            worktrees.append(WorktreeInfo(
                path=current.get("path", ""),
                branch=current.get("branch", ""),
                commit=current.get("commit", ""),
            ))

        return worktrees

    def cleanup_orphans(self, repo_path: str, active_paths: set[str]) -> int:
        """Remove worktrees not in the active set. Returns count removed."""
        worktrees = self.list_worktrees(repo_path)
        if not worktrees:
            return 0

        # The first worktree is always the main one
        main_path = worktrees[0].path
        removed = 0
        for wt in worktrees[1:]:
            if wt.path not in active_paths:
                self.remove_worktree(wt.path, repo_path)
                removed += 1
        return removed

    @staticmethod
    def make_branch_name(project: str, description: str) -> str:
        """Generate a branch name from project and task description."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", description.lower()).strip("-")
        slug = slug[:40]  # Limit length
        return f"pm/{project}/{slug}"
