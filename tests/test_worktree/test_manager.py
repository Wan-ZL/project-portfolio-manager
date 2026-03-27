from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm.worktree.manager import WorktreeManager, WorktreeInfo


@pytest.fixture
def mgr():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield WorktreeManager(worktree_base=tmpdir)


def test_manager_creates_base_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir) / "worktrees"
        mgr = WorktreeManager(worktree_base=str(base))
        assert base.exists()


def test_make_branch_name():
    branch = WorktreeManager.make_branch_name("my-project", "Fix the auth bug")
    assert branch.startswith("pm/my-project/")
    assert "fix-the-auth-bug" in branch


def test_make_branch_name_special_chars():
    branch = WorktreeManager.make_branch_name("proj", "Fix!!! multiple   bugs???")
    assert branch.startswith("pm/proj/")
    assert "!" not in branch
    assert "?" not in branch


def test_make_branch_name_length_limit():
    long_desc = "a" * 100
    branch = WorktreeManager.make_branch_name("p", long_desc)
    # The slug portion should be at most 40 chars
    slug = branch.split("/", 2)[-1]
    assert len(slug) <= 40


@patch("pm.worktree.manager.subprocess.run")
def test_create_worktree(mock_run, mgr):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as repo_dir:
        # Create .git dir to simulate a git repo
        (Path(repo_dir) / ".git").mkdir()

        path = mgr.create_worktree("test-proj", "pm/test-proj/fix-bug", repo_dir)
        assert path is not None
        assert "test-proj" in path
        mock_run.assert_called_once()


@patch("pm.worktree.manager.subprocess.run")
def test_create_worktree_fallback_existing_branch(mock_run, mgr):
    # First call fails (branch exists), second succeeds
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="", stderr="branch already exists"),
        MagicMock(returncode=0, stdout="", stderr=""),
    ]

    with tempfile.TemporaryDirectory() as repo_dir:
        (Path(repo_dir) / ".git").mkdir()
        path = mgr.create_worktree("proj", "pm/proj/fix", repo_dir)
        assert path is not None
        assert mock_run.call_count == 2


@patch("pm.worktree.manager.subprocess.run")
def test_create_worktree_both_fail(mock_run, mgr):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fatal error")

    with tempfile.TemporaryDirectory() as repo_dir:
        (Path(repo_dir) / ".git").mkdir()
        with pytest.raises(RuntimeError, match="Failed to create worktree"):
            mgr.create_worktree("proj", "pm/proj/fix", repo_dir)


def test_create_worktree_no_repo(mgr):
    with pytest.raises(FileNotFoundError):
        mgr.create_worktree("proj", "branch", "/nonexistent/path")


def test_create_worktree_not_git_repo(mgr):
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="Not a git repository"):
            mgr.create_worktree("proj", "branch", tmpdir)


@patch("pm.worktree.manager.subprocess.run")
def test_remove_worktree(mock_run, mgr):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    mgr.remove_worktree("/tmp/wt/path", "/tmp/repo")
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "worktree" in args
    assert "remove" in args


@patch("pm.worktree.manager.subprocess.run")
def test_list_worktrees(mock_run, mgr):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=(
            "worktree /tmp/repo\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /tmp/wt/fix-bug\n"
            "HEAD def456\n"
            "branch refs/heads/pm/proj/fix-bug\n"
            "\n"
        ),
        stderr="",
    )

    worktrees = mgr.list_worktrees("/tmp/repo")
    assert len(worktrees) == 2
    assert worktrees[0].path == "/tmp/repo"
    assert worktrees[0].branch == "main"
    assert worktrees[1].path == "/tmp/wt/fix-bug"
    assert worktrees[1].branch == "pm/proj/fix-bug"


@patch("pm.worktree.manager.subprocess.run")
def test_list_worktrees_empty(mock_run, mgr):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not a repo")
    worktrees = mgr.list_worktrees("/tmp/nothing")
    assert worktrees == []


@patch("pm.worktree.manager.subprocess.run")
def test_cleanup_orphans(mock_run, mgr):
    # list call returns two worktrees (first is always main)
    list_result = MagicMock(
        returncode=0,
        stdout=(
            "worktree /tmp/repo\n"
            "HEAD abc\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /tmp/wt/old\n"
            "HEAD def\n"
            "branch refs/heads/pm/old\n"
            "\n"
        ),
        stderr="",
    )
    # remove call succeeds
    remove_result = MagicMock(returncode=0, stdout="", stderr="")
    mock_run.side_effect = [list_result, remove_result]

    # First worktree (/tmp/repo) is skipped as main; /tmp/wt/old is orphaned
    removed = mgr.cleanup_orphans("/tmp/repo", active_paths=set())
    assert removed == 1
