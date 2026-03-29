"""Tests for the centralized DataStore."""
from __future__ import annotations

from datetime import datetime

import pytest

from pm.github.pr import EnhancedPR
from pm.tui.store import DataStore, ProjectData, StoreState
from pm.tui.widgets.project_list import ProjectInfo
from pm.tui.widgets.session_list import SessionInfo


def _make_project(name: str, account: str = "personal", **kwargs) -> ProjectInfo:
    return ProjectInfo(name=name, account=account, **kwargs)


def _make_pr(repo: str, number: int, title: str = "PR", ci_status: str = "pending") -> EnhancedPR:
    return EnhancedPR(
        repo_id=repo,
        number=number,
        title=title,
        state="open",
        author="testuser",
        created_at=datetime(2026, 3, 25),
        updated_at=datetime(2026, 3, 25),
        ci_status=ci_status,
    )


def _make_session(sid: str, project: str, task: str = "test task") -> SessionInfo:
    return SessionInfo(
        id=sid,
        project=project,
        task=task,
        agent="claude-code",
        status="running",
        created_at=datetime(2026, 3, 25, 14, 30),
    )


class TestSetProjectsPreservesAI:
    def test_card_summary_preserved_on_update(self):
        store = DataStore()
        projects = [_make_project("proj-a"), _make_project("proj-b")]
        store.set_projects(projects)

        store.set_card_summary("proj-a", {"dynamic": "test"}, status="running", time="2h ago")

        new_projects = [
            _make_project("proj-a", open_prs=5),
            _make_project("proj-b", open_prs=3),
        ]
        store.set_projects(new_projects)

        pd = store.get_project("proj-a")
        assert pd is not None
        assert pd.card_summary == {"dynamic": "test"}
        assert pd.card_summary_status == "running"
        assert pd.card_summary_time == "2h ago"
        assert pd.info.open_prs == 5

    def test_ai_summary_preserved_on_update(self):
        store = DataStore()
        projects = [_make_project("proj-a")]
        store.set_projects(projects)

        store.set_ai_summary("proj-a", {"one_line_status": "All good"})

        new_projects = [_make_project("proj-a", open_prs=10)]
        store.set_projects(new_projects)

        pd = store.get_project("proj-a")
        assert pd is not None
        assert pd.ai_summary == {"one_line_status": "All good"}

    def test_card_summary_lost_when_project_removed(self):
        store = DataStore()
        projects = [_make_project("proj-a"), _make_project("proj-b")]
        store.set_projects(projects)
        store.set_card_summary("proj-a", {"dynamic": "test"})

        store.set_projects([_make_project("proj-b")])

        assert store.get_project("proj-a") is None
        pd = store.get_project("proj-b")
        assert pd is not None
        assert pd.card_summary is None

    def test_new_project_has_no_ai_data(self):
        store = DataStore()
        store.set_projects([_make_project("proj-a")])
        store.set_card_summary("proj-a", {"dynamic": "test"})

        store.set_projects([_make_project("proj-a"), _make_project("proj-new")])

        pd_new = store.get_project("proj-new")
        assert pd_new is not None
        assert pd_new.card_summary is None
        assert pd_new.ai_summary is None


class TestSetProjectsWithPRs:
    def test_prs_set_on_initial_load(self):
        store = DataStore()
        projects = [_make_project("proj-a")]
        prs = {"proj-a": [_make_pr("owner/repo", 1), _make_pr("owner/repo", 2)]}
        store.set_projects(projects, prs=prs)

        pd = store.get_project("proj-a")
        assert pd is not None
        assert len(pd.prs) == 2

    def test_prs_updated_on_refresh(self):
        store = DataStore()
        projects = [_make_project("proj-a")]
        prs = {"proj-a": [_make_pr("owner/repo", 1)]}
        store.set_projects(projects, prs=prs)

        new_prs = {"proj-a": [_make_pr("owner/repo", 1), _make_pr("owner/repo", 2)]}
        store.set_projects(projects, prs=new_prs)

        pd = store.get_project("proj-a")
        assert len(pd.prs) == 2

    def test_sessions_set(self):
        store = DataStore()
        projects = [_make_project("proj-a")]
        sessions = {"proj-a": [_make_session("s1", "proj-a")]}
        store.set_projects(projects, sessions=sessions)

        pd = store.get_project("proj-a")
        assert len(pd.sessions) == 1
        assert pd.sessions[0].task == "test task"


class TestPollRefresh:
    def test_skips_when_no_changes(self):
        store = DataStore()
        projects = [_make_project("proj-a")]
        prs = {"proj-a": [_make_pr("owner/repo", 1, "PR One")]}
        store.set_projects(projects, prs=prs)

        changed = store.poll_refresh(projects, prs)
        assert changed is False

    def test_detects_new_pr(self):
        store = DataStore()
        projects = [_make_project("proj-a")]
        prs = {"proj-a": [_make_pr("owner/repo", 1, "PR One")]}
        store.set_projects(projects, prs=prs)

        new_prs = {"proj-a": [
            _make_pr("owner/repo", 1, "PR One"),
            _make_pr("owner/repo", 2, "PR Two"),
        ]}
        changed = store.poll_refresh(projects, new_prs)
        assert changed is True

    def test_detects_removed_pr(self):
        store = DataStore()
        projects = [_make_project("proj-a")]
        prs = {"proj-a": [_make_pr("owner/repo", 1), _make_pr("owner/repo", 2)]}
        store.set_projects(projects, prs=prs)

        new_prs = {"proj-a": [_make_pr("owner/repo", 1)]}
        changed = store.poll_refresh(projects, new_prs)
        assert changed is True

    def test_detects_ci_status_change(self):
        store = DataStore()
        projects = [_make_project("proj-a")]
        prs = {"proj-a": [_make_pr("owner/repo", 1, "PR", ci_status="pending")]}
        store.set_projects(projects, prs=prs)

        new_prs = {"proj-a": [_make_pr("owner/repo", 1, "PR", ci_status="passing")]}
        changed = store.poll_refresh(projects, new_prs)
        assert changed is True

    def test_preserves_card_summary_on_poll(self):
        store = DataStore()
        projects = [_make_project("proj-a")]
        prs = {"proj-a": [_make_pr("owner/repo", 1)]}
        store.set_projects(projects, prs=prs)
        store.set_card_summary("proj-a", {"dynamic": "important"})

        new_prs = {"proj-a": [_make_pr("owner/repo", 1), _make_pr("owner/repo", 2)]}
        store.poll_refresh(projects, new_prs)

        pd = store.get_project("proj-a")
        assert pd.card_summary == {"dynamic": "important"}


class TestGetProject:
    def test_returns_correct_data(self):
        store = DataStore()
        store.set_projects([_make_project("proj-a"), _make_project("proj-b")])

        pd = store.get_project("proj-a")
        assert pd is not None
        assert pd.info.name == "proj-a"

    def test_returns_none_for_missing(self):
        store = DataStore()
        store.set_projects([_make_project("proj-a")])
        assert store.get_project("proj-x") is None


class TestGetProjectsOrdered:
    def test_returns_in_order(self):
        store = DataStore()
        store.set_projects([
            _make_project("proj-c"),
            _make_project("proj-a"),
            _make_project("proj-b"),
        ])

        ordered = store.get_projects_ordered()
        names = [pd.info.name for pd in ordered]
        assert names == ["proj-c", "proj-a", "proj-b"]

    def test_empty_store(self):
        store = DataStore()
        assert store.get_projects_ordered() == []


class TestUpdatePrs:
    def test_updates_existing_project_prs(self):
        store = DataStore()
        store.set_projects([_make_project("proj-a")])

        store.update_prs({"proj-a": [_make_pr("r", 1), _make_pr("r", 2)]})

        pd = store.get_project("proj-a")
        assert len(pd.prs) == 2

    def test_ignores_unknown_project(self):
        store = DataStore()
        store.set_projects([_make_project("proj-a")])
        store.update_prs({"proj-x": [_make_pr("r", 1)]})
        assert store.get_project("proj-x") is None


class TestSetCardSummary:
    def test_sets_card_data(self):
        store = DataStore()
        store.set_projects([_make_project("proj-a")])
        store.set_card_summary("proj-a", {"dynamic": "test"}, status="done", time="1h ago")

        pd = store.get_project("proj-a")
        assert pd.card_summary == {"dynamic": "test"}
        assert pd.card_summary_status == "done"
        assert pd.card_summary_time == "1h ago"

    def test_ignores_unknown_project(self):
        store = DataStore()
        store.set_projects([_make_project("proj-a")])
        store.set_card_summary("proj-x", {"dynamic": "test"})
        assert store.get_project("proj-x") is None


class TestForceRefresh:
    def test_updates_all_data(self):
        store = DataStore()
        store.set_projects([_make_project("proj-a")])
        store.set_card_summary("proj-a", {"dynamic": "keep me"})

        new_projects = [_make_project("proj-a", open_prs=10)]
        new_prs = {"proj-a": [_make_pr("r", 1), _make_pr("r", 2)]}
        store.force_refresh(new_projects, new_prs)

        pd = store.get_project("proj-a")
        assert pd.info.open_prs == 10
        assert len(pd.prs) == 2
        assert pd.card_summary == {"dynamic": "keep me"}


class TestStoreState:
    def test_default_values(self):
        state = StoreState()
        assert state.projects == {}
        assert state.project_order == []
        assert state.selected_project == ""
        assert state.is_loading is False
        assert state.error_message == ""
