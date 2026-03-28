from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from pm.config.settings import load_settings
from pm.db.database import DEFAULT_DB_PATH, Database
from pm.db.models import ProjectSummary


@dataclass
class OverlayProject:
    name: str
    status: str  # "ok", "warn", "error"
    summary: str
    last_activity: str  # "3hr ago", "yesterday", "12d ago"


def format_time_ago(dt: Optional[datetime]) -> str:
    if dt is None:
        return "unknown"
    now = datetime.now()
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}hr ago"
    days = hours // 24
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    return f"{days // 365}yr ago"


def _urgency_to_status(urgency: str) -> str:
    mapping = {
        "high": "error",
        "medium": "warn",
        "low": "ok",
        "idle": "ok",
    }
    return mapping.get(urgency, "ok")


def _extract_urgency_from_summary(summary_json: Optional[str]) -> str:
    if not summary_json:
        return "low"
    try:
        data = json.loads(summary_json)
        if isinstance(data, dict):
            return data.get("urgency", "low")
    except (json.JSONDecodeError, TypeError):
        pass
    return "low"


def _extract_one_line(summary_json: Optional[str]) -> str:
    if not summary_json:
        return "No status available"
    try:
        data = json.loads(summary_json)
        if isinstance(data, dict):
            return data.get("one_line_status", str(data))
        return str(data)
    except (json.JSONDecodeError, TypeError):
        # Plain text summary
        return summary_json


def load_overlay_settings(settings_path: Path | None = None) -> dict:
    settings = load_settings(settings_path)
    overlay = settings.get("overlay", {})
    return {
        "enabled": overlay.get("enabled", False),
        "show_count": overlay.get("show_count", 3),
        "position": overlay.get("position", "bottom-right"),
        "opacity": overlay.get("opacity", 70),
    }


def get_projects_from_db(
    db_path: Path | None = None,
    show_count: int = 3,
) -> list[OverlayProject]:
    path = db_path or DEFAULT_DB_PATH
    if not path.exists():
        return []

    try:
        db = Database(path)
    except Exception:
        return []

    projects: list[OverlayProject] = []
    try:
        with db.get_session() as session:
            from sqlmodel import select
            stmt = select(ProjectSummary)
            summaries = list(session.exec(stmt).all())
    except Exception:
        return []

    if not summaries:
        return []

    # Sort by generated_at descending (most recently updated first)
    summaries.sort(key=lambda s: s.generated_at or datetime.min, reverse=True)

    for ps in summaries[:show_count]:
        urgency = _extract_urgency_from_summary(ps.summary)
        one_line = _extract_one_line(ps.summary)
        last_activity = format_time_ago(ps.generated_at)

        projects.append(OverlayProject(
            name=ps.project,
            status=_urgency_to_status(urgency),
            summary=one_line,
            last_activity=last_activity,
        ))

    return projects


def get_projects_from_repos(db_path: Path | None = None, show_count: int = 3) -> list[OverlayProject]:
    """Fallback: build overlay data from repos table when no summaries exist."""
    path = db_path or DEFAULT_DB_PATH
    if not path.exists():
        return []

    try:
        db = Database(path)
    except Exception:
        return []

    projects: list[OverlayProject] = []
    try:
        repos = db.get_all_repos()
    except Exception:
        return []

    if not repos:
        return []

    # Group repos by project
    by_project: dict[str, datetime | None] = {}
    for repo in repos:
        existing = by_project.get(repo.project)
        if existing is None or (repo.last_synced_at and (existing is None or repo.last_synced_at > existing)):
            by_project[repo.project] = repo.last_synced_at

    # Sort by last_synced_at descending
    sorted_projects = sorted(
        by_project.items(),
        key=lambda x: x[1] or datetime.min,
        reverse=True,
    )

    for name, last_synced in sorted_projects[:show_count]:
        projects.append(OverlayProject(
            name=name,
            status="ok",
            summary="No AI summary yet",
            last_activity=format_time_ago(last_synced),
        ))

    return projects


def fetch_overlay_data(
    db_path: Path | None = None,
    settings_path: Path | None = None,
) -> tuple[list[OverlayProject], dict]:
    settings = load_overlay_settings(settings_path)
    show_count = settings["show_count"]

    projects = get_projects_from_db(db_path, show_count)
    if not projects:
        projects = get_projects_from_repos(db_path, show_count)

    return projects, settings
