"""Portfolio card summary pipeline.

Generates 3 fields per project card (displayed across 4 lines):
1. dynamic -- one-line latest activity (commits + PRs combined)
2. recommendation -- one-line AI suggestion (concrete, actionable)
3. last_command_summary -- compressed version of user's last command

All 3 fields generated in ONE API call, cached by input hash.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CARD_SUMMARY_SYSTEM_PROMPT = """你是一个项目状态助理。用中文+English技术词混合风格。根据项目数据生成3个字段:

1. "dynamic" — 最新动态 (15-40字)
   - 必须同时包含 commit 活动和 PR 活动（如果有的话），不要只说其中一个
   - 基于具体事实 (commit message, PR title, issue title)
   - 不要只重复 PR 编号 — 要概括 commit/PR 的内容是什么
   - 如果最近有 merge: "新增 login validation, 修 CSS layout; PR #1 待 review (今天)"
   - 如果 CI failing: "PR #200 CI failing — test_security 未通过, 最近 commit 修了 auth"
   - 如果没活动: "闲置 12 天, 上次 commit: update README"
   - 绝对不能说 "项目进展顺利" 这种废话

2. "recommendation" — 建议下一步 (10-20字)
   - 必须是具体可执行的动作
   - 好: "先修 PR #200 的 CI, 然后 merge PR #15"
   - 好: "处理 issue #42 (login timeout bug)"
   - 坏: "继续开发" "保持关注" (太模糊)

3. "last_command_summary" — 压缩用户上次指令 (15-25字)
   - 保留关键动作和目标
   - 去掉解释、背景、细节
   - 如果原指令已经很短 (<= 40字), 原样返回

输出 JSON: {"dynamic": "...", "recommendation": "...", "last_command_summary": "..."}
"""

# API key file path (with invisible character in filename, matching user's actual path)
API_KEY_FILE = Path("/Users/zelin/Downloads/API Key/\u200eanthropic-api-key.txt")

MODEL = "claude-sonnet-4-20250514"


def _load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key.strip()
    try:
        if API_KEY_FILE.exists():
            return API_KEY_FILE.read_text().strip().splitlines()[0].strip()
    except Exception as e:
        logger.warning(f"Failed to read API key file: {e}")
    return ""


@dataclass
class CardContext:
    project_name: str
    recent_commits: list[dict] = field(default_factory=list)
    open_prs: list[dict] = field(default_factory=list)
    recently_merged: list[dict] = field(default_factory=list)
    open_issues_count: int = 0
    last_command: str = ""
    last_command_status: str = ""
    last_command_time: str = ""
    last_command_pr: int | None = None
    days_since_last_activity: int = 0


@dataclass
class CardSummary:
    dynamic: str = ""
    recommendation: str = ""
    last_command_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "dynamic": self.dynamic,
            "recommendation": self.recommendation,
            "last_command_summary": self.last_command_summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CardSummary:
        return cls(
            dynamic=data.get("dynamic", ""),
            recommendation=data.get("recommendation", ""),
            last_command_summary=data.get("last_command_summary", ""),
        )


def compute_card_hash(context: CardContext) -> str:
    data = {
        "project_name": context.project_name,
        "recent_commits": context.recent_commits,
        "open_prs": context.open_prs,
        "recently_merged": context.recently_merged,
        "open_issues_count": context.open_issues_count,
        "last_command": context.last_command,
        "last_command_status": context.last_command_status,
        "days_since_last_activity": context.days_since_last_activity,
    }
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def build_card_prompt(project_name: str, context: CardContext) -> str:
    commits_text = ""
    if context.recent_commits:
        for c in context.recent_commits[:10]:
            commits_text += f"  - {c.get('sha', '?')}: {c.get('message', '?')} ({c.get('author', '?')}, {c.get('date', '?')})\n"
    else:
        commits_text = "  (no recent commits)\n"

    prs_text = ""
    if context.open_prs:
        for pr in context.open_prs[:10]:
            prs_text += (
                f"  - PR #{pr.get('number', '?')}: {pr.get('title', '?')} "
                f"[CI: {pr.get('ci_status', '?')}, Review: {pr.get('review_status', '?')}]\n"
            )
    else:
        prs_text = "  (no open PRs)\n"

    merged_text = ""
    if context.recently_merged:
        for pr in context.recently_merged[:5]:
            merged_text += f"  - PR #{pr.get('number', '?')}: {pr.get('title', '?')} (merged {pr.get('merged_at', '?')})\n"
    else:
        merged_text = "  (no recently merged PRs)\n"

    last_cmd_text = ""
    if context.last_command:
        last_cmd_text = (
            f"  Command: {context.last_command}\n"
            f"  Status: {context.last_command_status}\n"
            f"  Time: {context.last_command_time}\n"
        )
        if context.last_command_pr:
            last_cmd_text += f"  PR: #{context.last_command_pr}\n"
    else:
        last_cmd_text = "  (no previous command)\n"

    return f"""## Project: "{project_name}"

### Recent Commits:
{commits_text}
### Open PRs:
{prs_text}
### Recently Merged:
{merged_text}
### Open Issues: {context.open_issues_count}

### Days Since Last Activity: {context.days_since_last_activity}

### Last User Command:
{last_cmd_text}
Respond with ONLY the JSON object, no markdown code blocks, no extra text."""


def parse_card_response(response_text: str) -> dict:
    text = response_text.strip()

    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    try:
        data = json.loads(text)
        return {
            "dynamic": data.get("dynamic", ""),
            "recommendation": data.get("recommendation", ""),
            "last_command_summary": data.get("last_command_summary", ""),
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "dynamic": text[:60] if text else "",
            "recommendation": "",
            "last_command_summary": "",
        }


def generate_fallback(context: CardContext, reason: str = "no API key") -> dict:
    """Return error indicator when AI generation fails."""
    return {
        "dynamic": f"⚠️ AI 生成失败 ({reason})",
        "recommendation": "",
        "last_command_summary": context.last_command[:40] if context.last_command else "",
    }


class CardSummaryGenerator:
    def __init__(self, db=None):
        self.db = db
        self._cache: dict[str, dict] = {}
        self._client = None
        self._api_key = ""

    @property
    def client(self):
        if self._client is None:
            self._api_key = _load_api_key()
            if not self._api_key:
                return None
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")
                return None
        return self._client

    @property
    def available(self) -> bool:
        return self.client is not None

    def generate(self, project_name: str, context: CardContext) -> dict:
        input_hash = compute_card_hash(context)

        # Check memory cache
        cached = self._cache.get(project_name)
        if cached and cached["hash"] == input_hash:
            return cached["data"]

        # Check DB cache
        if self.db:
            try:
                db_cached = self.db.get_summary(f"__card__{project_name}")
                if db_cached and db_cached.input_hash == input_hash and db_cached.summary:
                    data = json.loads(db_cached.summary)
                    self._cache[project_name] = {"hash": input_hash, "data": data}
                    return data
            except Exception:
                pass

        # If no AI available, show error
        if not self.available:
            data = generate_fallback(context, reason="no API key")
            self._cache[project_name] = {"hash": input_hash, "data": data}
            return data

        # Generate via AI
        data = self._call_ai(project_name, context)

        # Save to both caches
        self._cache[project_name] = {"hash": input_hash, "data": data}
        if self.db:
            try:
                self.db.save_summary(
                    f"__card__{project_name}",
                    json.dumps(data),
                    "",
                    input_hash,
                )
            except Exception as e:
                logger.warning(f"Failed to cache card summary: {e}")

        return data

    def _call_ai(self, project_name: str, context: CardContext) -> dict:
        prompt = build_card_prompt(project_name, context)
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=CARD_SUMMARY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            return parse_card_response(response_text)
        except Exception as e:
            logger.error(f"Failed to generate card summary for {project_name}: {e}")
            return generate_fallback(context, reason=str(e)[:50])


# --- Data collection functions ---

def _format_time_ago(dt: datetime | None) -> str:
    if not dt:
        return "unknown"
    try:
        delta = datetime.now() - dt
    except TypeError:
        delta = datetime.now() - dt.replace(tzinfo=None)
    if delta.days > 0:
        return f"{delta.days}d ago"
    elif delta.seconds >= 3600:
        return f"{delta.seconds // 3600}h ago"
    else:
        return "just now"


def _fetch_recent_commits(repos: list[str], token: str, limit: int = 10) -> list[dict]:
    import httpx
    headers = {"Authorization": f"token {token}", "Accept": "application/json"}
    commits: list[dict] = []
    for repo in repos:
        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{repo}/commits",
                headers=headers,
                params={"per_page": limit},
                timeout=10,
            )
            if resp.status_code == 200:
                for c in resp.json()[:limit]:
                    commits.append({
                        "sha": c["sha"][:7],
                        "message": c["commit"]["message"].split("\n")[0],
                        "author": c["commit"]["author"]["name"],
                        "date": c["commit"]["author"]["date"],
                    })
        except Exception:
            pass
    return sorted(commits, key=lambda c: c.get("date", ""), reverse=True)[:limit]


def _fetch_open_prs(repos: list[str], token: str) -> list[dict]:
    import httpx
    headers = {"Authorization": f"token {token}", "Accept": "application/json"}
    prs: list[dict] = []
    for repo in repos:
        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=headers,
                params={"state": "open", "per_page": 20},
                timeout=10,
            )
            if resp.status_code == 200:
                for pr in resp.json():
                    prs.append({
                        "number": pr.get("number", 0),
                        "title": pr.get("title", ""),
                        "ci_status": "pending",
                        "review_status": "pending",
                    })
        except Exception:
            pass
    return prs


def _fetch_merged_prs(repos: list[str], token: str, limit: int = 5) -> list[dict]:
    import httpx
    headers = {"Authorization": f"token {token}", "Accept": "application/json"}
    merged: list[dict] = []
    for repo in repos:
        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=headers,
                params={"state": "closed", "per_page": limit, "sort": "updated", "direction": "desc"},
                timeout=10,
            )
            if resp.status_code == 200:
                for pr in resp.json():
                    if pr.get("merged_at"):
                        merged.append({
                            "number": pr.get("number", 0),
                            "title": pr.get("title", ""),
                            "merged_at": pr.get("merged_at", ""),
                        })
        except Exception:
            pass
    return merged[:limit]


def _count_open_issues(repos: list[str], token: str) -> int:
    import httpx
    headers = {"Authorization": f"token {token}", "Accept": "application/json"}
    count = 0
    for repo in repos:
        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{repo}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                count += resp.json().get("open_issues_count", 0)
        except Exception:
            pass
    return count


def _get_last_session(project_name: str, db) -> dict:
    if not db:
        return {}
    try:
        sessions = db.get_sessions_by_project(project_name)
        if not sessions:
            return {}
        sorted_sessions = sorted(
            sessions,
            key=lambda s: s.updated_at or s.created_at or datetime.min,
            reverse=True,
        )
        last = sorted_sessions[0]
        return {
            "command": last.task_description or "",
            "status": last.status or "",
            "time": _format_time_ago(last.updated_at or last.created_at),
            "pr": last.pr_number,
        }
    except Exception:
        return {}


def collect_card_context(
    project_name: str,
    repos: list[str],
    token: str,
    db=None,
) -> CardContext:
    commits = _fetch_recent_commits(repos, token, limit=10) if token else []
    open_prs = _fetch_open_prs(repos, token) if token else []
    merged_prs = _fetch_merged_prs(repos, token, limit=5) if token else []
    issues_count = _count_open_issues(repos, token) if token else 0
    last_session = _get_last_session(project_name, db)

    # Calculate days since last activity
    days_since = 0
    if commits:
        try:
            latest_date = commits[0].get("date", "")
            if latest_date:
                if isinstance(latest_date, str):
                    latest_dt = datetime.fromisoformat(latest_date.replace("Z", "+00:00"))
                    delta = datetime.now(latest_dt.tzinfo) - latest_dt
                else:
                    delta = datetime.now() - latest_date
                days_since = max(0, delta.days)
        except Exception:
            pass

    return CardContext(
        project_name=project_name,
        recent_commits=commits,
        open_prs=open_prs,
        recently_merged=merged_prs,
        open_issues_count=issues_count,
        last_command=last_session.get("command", ""),
        last_command_status=last_session.get("status", ""),
        last_command_time=last_session.get("time", ""),
        last_command_pr=last_session.get("pr"),
        days_since_last_activity=days_since,
    )
