from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """你是一个简洁的工程状态助理。用中文 + English 技术词混合风格，为一个同时管理多个项目的开发者生成项目状态。

输出 JSON 格式:
{
  "one_line_status": "一句话状态 (必须有具体事实，不能说废话)",
  "key_progress": ["最近的关键进展列表"],
  "needs_attention": ["需要注意/行动的事项"],
  "suggested_next_steps": ["建议的下一步"],
  "urgency": "high/medium/low/idle"
}

一句话状态的规则:
- 必须提到具体事实 (PR 号码, feature 名, 数字)
- 必须指出需要注意什么或什么变了
- 格式: [最近发生了什么] + [现在需要做什么]
- 如果没什么活动: "闲置 X 天 — 上次活动是 [具体事情]"

绝对不能生成的废话:
- "项目进展顺利，active development 在持续"
- "有几个 PR 在 review 中"
- "团队在积极开发中"
- "项目状态良好"

好的例子:
- "Auth refactor 已 merge (PR #42); 2 个 PR CI failing 需要修"
- "闲置 12 天 — 上次是 merge payment integration"
- "3 个 PR 等你 review, 最老的 (#89) 已经开了 6 天"
- "所有 4 个 PR CI 通过 + approved — 可以 merge 了"
"""

# API key file path (with invisible character in filename, matching user's actual path)
API_KEY_FILE = Path("/Users/zelin/Downloads/API Key/\u200eanthropic-api-key.txt")

MODEL = "claude-sonnet-4-20250514"


def _load_api_key() -> str:
    """Load Anthropic API key from env var or fallback file."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key.strip()
    try:
        if API_KEY_FILE.exists():
            return API_KEY_FILE.read_text().strip().splitlines()[0].strip()
    except Exception as e:
        logger.warning(f"Failed to read API key file: {e}")
    return ""


def compute_input_hash(input_data: dict) -> str:
    """Compute SHA256 hash of input data for cache invalidation."""
    serialized = json.dumps(input_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _get_last_session(project_name: str, db) -> Optional[dict]:
    """Get info about the last agent session for a project."""
    if not db:
        return None
    try:
        sessions = db.get_sessions_by_project(project_name)
        if not sessions:
            return None
        sorted_sessions = sorted(
            sessions,
            key=lambda s: s.updated_at or s.created_at or datetime.min,
            reverse=True,
        )
        last = sorted_sessions[0]
        return {
            "task_description": last.task_description or "unknown task",
            "status": last.status or "unknown",
            "updated_at": last.updated_at or last.created_at,
        }
    except Exception:
        return None


def _get_days_since_last_activity(project_name: str, db) -> Optional[int]:
    """Calculate days since last activity from sessions/commits."""
    if not db:
        return None
    try:
        sessions = db.get_sessions_by_project(project_name)
        if not sessions:
            return None
        latest_time = max(
            (s.updated_at or s.created_at or datetime.min for s in sessions),
            default=None,
        )
        if latest_time and latest_time != datetime.min:
            delta = datetime.now() - latest_time
            return delta.days
        return None
    except Exception:
        return None


def _count_other_commits(project_name: str) -> Optional[int]:
    """Placeholder for counting commits by others since last activity.

    Real implementation would use git log. Returns None to indicate
    the data is not available.
    """
    return None


def build_summary_prompt(project_name: str, input_data: dict, db=None) -> str:
    """Build the prompt for AI summary generation."""
    recent_commits = input_data.get("recent_commits", [])
    open_prs = input_data.get("open_prs", [])
    open_issues = input_data.get("open_issues", [])
    ci_status = input_data.get("ci_status", "unknown")
    instructions = input_data.get("instructions", "")

    commits_text = ""
    if recent_commits:
        commits_text = "\n".join(f"  - {c}" for c in recent_commits[:20])
    else:
        commits_text = "  (no recent commits)"

    prs_text = ""
    if open_prs:
        for pr in open_prs[:15]:
            if isinstance(pr, dict):
                prs_text += (
                    f"  - PR #{pr.get('number', '?')}: {pr.get('title', '?')} "
                    f"[CI: {pr.get('ci_status', '?')}, Review: {pr.get('review_status', '?')}]\n"
                )
            else:
                prs_text += f"  - {pr}\n"
    else:
        prs_text = "  (no open PRs)"

    issues_text = ""
    if open_issues:
        for issue in open_issues[:10]:
            if isinstance(issue, dict):
                issues_text += f"  - #{issue.get('number', '?')}: {issue.get('title', '?')}\n"
            else:
                issues_text += f"  - {issue}\n"
    else:
        issues_text = "  (no open issues)"

    # Build activity context
    activity_section = ""
    last_session = _get_last_session(project_name, db)
    days_since = _get_days_since_last_activity(project_name, db)
    other_commits = _count_other_commits(project_name)

    activity_lines = []
    if last_session:
        activity_lines.append(
            f"Your last agent session: {last_session['task_description']} ({last_session['status']})"
        )
    if days_since is not None:
        activity_lines.append(f"Days since your last activity: {days_since}")
    if other_commits is not None:
        activity_lines.append(f"Commits by others since your last activity: {other_commits}")

    if activity_lines:
        activity_section = "\n### Your Recent Activity\n" + "\n".join(f"  - {line}" for line in activity_lines)

    other_activity_section = ""
    if other_commits is not None:
        other_activity_section = f"\n### Activity by Others\n  - Commits by others since your last activity: {other_commits}"

    prompt = f"""## Project Data for "{project_name}"

### Recent Commits (last 7 days):
{commits_text}

### Open Pull Requests:
{prs_text}

### Open Issues:
{issues_text}

### CI Status: {ci_status}
{activity_section}
{other_activity_section}
### Project Instructions:
{instructions or '(none)'}

Respond with ONLY the JSON object, no markdown code blocks, no extra text."""
    return prompt


def parse_summary_response(response_text: str) -> dict:
    """Parse the AI response into a structured summary dict.

    Handles both new format (needs_attention, urgency) and legacy format
    (issues_needing_attention) for backward compatibility with cached summaries.
    """
    text = response_text.strip()

    # Try to find JSON block in markdown code block
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
        # Support both new "needs_attention" and legacy "issues_needing_attention"
        needs_attention = (
            data.get("needs_attention")
            or data.get("issues_needing_attention")
            or []
        )
        return {
            "one_line_status": data.get("one_line_status", ""),
            "key_progress": data.get("key_progress", []),
            "needs_attention": needs_attention,
            "suggested_next_steps": data.get("suggested_next_steps", []),
            "urgency": data.get("urgency", "medium"),
        }
    except (json.JSONDecodeError, ValueError):
        return {
            "one_line_status": text[:200],
            "key_progress": [],
            "needs_attention": [],
            "suggested_next_steps": [],
            "urgency": "medium",
        }


def format_summary_for_display(summary: dict) -> str:
    """Format a parsed summary dict into Rich markup for TUI display."""
    lines = []

    urgency = summary.get("urgency", "medium")
    urgency_colors = {
        "high": "red",
        "medium": "yellow",
        "low": "green",
        "idle": "dim",
    }
    urgency_labels = {
        "high": "[bold red]HIGH[/bold red]",
        "medium": "[bold yellow]MEDIUM[/bold yellow]",
        "low": "[bold green]LOW[/bold green]",
        "idle": "[dim]IDLE[/dim]",
    }
    status_color = urgency_colors.get(urgency, "yellow")
    urgency_label = urgency_labels.get(urgency, "")

    one_line = summary.get("one_line_status", "")
    if one_line:
        lines.append(f"[bold {status_color}]{one_line}[/bold {status_color}]")
        if urgency_label:
            lines.append(f"  Urgency: {urgency_label}")
        lines.append("")

    progress = summary.get("key_progress", [])
    if progress:
        lines.append("[bold cyan]Key Progress:[/bold cyan]")
        for item in progress:
            lines.append(f"  [green]\u2022[/green] {item}")
        lines.append("")

    # Support both new and legacy field names
    attention = summary.get("needs_attention") or summary.get("issues_needing_attention") or []
    if attention:
        lines.append("[bold yellow]Needs Attention:[/bold yellow]")
        for item in attention:
            lines.append(f"  [yellow]\u26a0[/yellow] {item}")
        lines.append("")

    steps = summary.get("suggested_next_steps", [])
    if steps:
        lines.append("[bold cyan]Next Steps:[/bold cyan]")
        for i, item in enumerate(steps, 1):
            lines.append(f"  [dim]{i}.[/dim] {item}")

    return "\n".join(lines) if lines else "[dim]No summary available[/dim]"


class AISummaryGenerator:
    """Generate natural language project summaries using Claude API."""

    def __init__(self, db=None):
        self.db = db
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

    def generate_summary(self, project_name: str, input_data: dict, force: bool = False) -> dict:
        """Generate an AI summary for a project.

        Args:
            project_name: Name of the project
            input_data: Dict with recent_commits, open_prs, open_issues, ci_status, instructions
            force: If True, bypass cache

        Returns:
            Parsed summary dict with one_line_status, key_progress, issues, steps
        """
        input_hash = compute_input_hash(input_data)

        # Check cache
        if not force and self.db:
            cached = self.db.get_summary(project_name)
            if cached and cached.input_hash == input_hash and cached.summary:
                try:
                    return json.loads(cached.summary)
                except (json.JSONDecodeError, TypeError):
                    pass

        if not self.available:
            return {
                "one_line_status": "AI summary unavailable (no API key configured)",
                "key_progress": [],
                "needs_attention": [],
                "suggested_next_steps": [],
                "urgency": "medium",
            }

        prompt = build_summary_prompt(project_name, input_data, db=self.db)

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SUMMARY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            summary = parse_summary_response(response_text)
        except Exception as e:
            logger.error(f"Failed to generate summary for {project_name}: {e}")
            summary = {
                "one_line_status": f"AI summary generation failed: {e}",
                "key_progress": [],
                "needs_attention": [],
                "suggested_next_steps": [],
                "urgency": "medium",
            }

        # Save to cache
        if self.db:
            try:
                self.db.save_summary(
                    project_name,
                    json.dumps(summary),
                    json.dumps(summary.get("suggested_next_steps", [])),
                    input_hash,
                )
            except Exception as e:
                logger.warning(f"Failed to cache summary: {e}")

        return summary

    def get_cached_summary(self, project_name: str) -> Optional[dict]:
        """Get a cached summary if available."""
        if not self.db:
            return None
        cached = self.db.get_summary(project_name)
        if cached and cached.summary:
            try:
                return json.loads(cached.summary)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def invalidate_cache(self, project_name: str) -> None:
        """Invalidate cache for a project by saving empty hash."""
        if self.db:
            try:
                self.db.save_summary(project_name, "", "[]", "")
            except Exception:
                pass
