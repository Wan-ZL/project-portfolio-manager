from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    """A single AI suggestion for what to work on next."""
    priority: str  # high, medium, low
    project: str
    action: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "priority": self.priority,
            "project": self.project,
            "action": self.action,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Suggestion:
        return cls(
            priority=data.get("priority", "medium"),
            project=data.get("project", ""),
            action=data.get("action", ""),
            reason=data.get("reason", ""),
        )


def build_suggest_prompt(projects_data: list[dict]) -> str:
    """Build the prompt for AI suggestion generation."""
    projects_text = ""
    for proj in projects_data:
        name = proj.get("name", "unknown")
        summary = proj.get("summary", {})
        one_line = summary.get("one_line_status", "No status") if isinstance(summary, dict) else str(summary)
        urgency = summary.get("urgency", "unknown") if isinstance(summary, dict) else "unknown"
        prs_count = proj.get("open_prs_count", 0)
        sessions_count = proj.get("active_sessions_count", 0)
        failing_ci = proj.get("failing_ci_count", 0)
        changes_requested = proj.get("changes_requested_count", 0)

        projects_text += f"""
### {name}
- Status: {one_line}
- Urgency: {urgency}
- Open PRs: {prs_count}
- Active sessions: {sessions_count}
- PRs with failing CI: {failing_ci}
- PRs with changes requested: {changes_requested}
"""

    prompt = f"""你是一个帮开发者排优先级的助理。根据以下项目状态，生成具体的 next actions。
用中文 + English 技术词混合风格。

## Projects
{projects_text}

## Output Format

Respond with ONLY this JSON (no code blocks, no extra text):

{{
  "suggestions": [
    {{
      "priority": "high/medium/low",
      "project": "project-name",
      "action": "具体要做什么 (必须提到 PR 号/feature 名/具体数字)",
      "reason": "为什么现在要做这个 (说清楚 impact 和 urgency)"
    }}
  ]
}}

Priority rules:
1. HIGH: CI failing (blocks merge), unresolved review comments (blocks others), PRs open > 5 days
2. MEDIUM: PRs approved + CI green (free wins to merge), stale PRs, incomplete tasks
3. LOW: Docs, cleanup, nice-to-haves

Rules:
- Generate 3-6 suggestions, sorted by urgency (high first)
- Each action must be specific enough to act on immediately
- Each reason must explain the concrete impact of doing/not doing it
- 不要说 "建议关注" 或 "需要注意" — 直接说做什么
"""
    return prompt


def parse_suggestions_response(response_text: str) -> list[Suggestion]:
    """Parse the AI response into a list of Suggestion objects."""
    text = response_text.strip()

    # Try to extract JSON from markdown code block
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
        suggestions_data = data.get("suggestions", [])
        return [Suggestion.from_dict(s) for s in suggestions_data]
    except (json.JSONDecodeError, ValueError, KeyError):
        return []


def format_suggestions_for_display(suggestions: list[Suggestion]) -> str:
    """Format suggestions into Rich markup for TUI display."""
    if not suggestions:
        return "[dim]No suggestions available. Press [bold]s[/bold] to generate.[/dim]"

    lines = ["[bold cyan]AI Suggestions - What to work on next:[/bold cyan]", ""]

    priority_icons = {
        "high": "[bold red]!!![/bold red]",
        "medium": "[bold yellow]!![/bold yellow]",
        "low": "[dim]![/dim]",
    }

    for i, s in enumerate(suggestions, 1):
        icon = priority_icons.get(s.priority, "[dim]![/dim]")
        lines.append(
            f"  {icon} [bold]{s.project}[/bold]: {s.action}"
        )
        lines.append(f"      [dim]{s.reason}[/dim]")
        if i < len(suggestions):
            lines.append("")

    return "\n".join(lines)


class AISuggestionEngine:
    """Analyzes all projects and generates prioritized next-step suggestions."""

    def __init__(self, db=None):
        self.db = db
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from pm.ai.summary import _load_api_key
            api_key = _load_api_key()
            if not api_key:
                return None
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic client: {e}")
                return None
        return self._client

    @property
    def available(self) -> bool:
        return self.client is not None

    def generate_suggestions(self, projects_data: list[dict], force: bool = False) -> list[Suggestion]:
        """Generate prioritized suggestions across all projects.

        Args:
            projects_data: List of dicts, each with:
                - name, summary, open_prs_count, active_sessions_count,
                  failing_ci_count, changes_requested_count
            force: If True, bypass cache

        Returns:
            List of Suggestion objects ordered by priority
        """
        # Check cache
        cache_key = "__suggestions__"
        input_hash = hashlib.sha256(
            json.dumps(projects_data, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        if not force and self.db:
            cached = self.db.get_summary(cache_key)
            if cached and cached.input_hash == input_hash and cached.suggestions:
                try:
                    suggestions_data = json.loads(cached.suggestions)
                    return [Suggestion.from_dict(s) for s in suggestions_data]
                except (json.JSONDecodeError, TypeError):
                    pass

        if not self.available:
            return self._generate_rule_based(projects_data)

        prompt = build_suggest_prompt(projects_data)

        try:
            from pm.ai.summary import MODEL
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            suggestions = parse_suggestions_response(response_text)
        except Exception as e:
            logger.error(f"Failed to generate suggestions: {e}")
            suggestions = self._generate_rule_based(projects_data)

        # Cache suggestions
        if self.db:
            try:
                suggestions_json = json.dumps([s.to_dict() for s in suggestions])
                self.db.save_summary(
                    cache_key, "", suggestions_json, input_hash,
                )
            except Exception as e:
                logger.warning(f"Failed to cache suggestions: {e}")

        return suggestions

    def get_cached_suggestions(self) -> list[Suggestion]:
        """Get cached suggestions if available."""
        if not self.db:
            return []
        cached = self.db.get_summary("__suggestions__")
        if cached and cached.suggestions:
            try:
                data = json.loads(cached.suggestions)
                return [Suggestion.from_dict(s) for s in data]
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @staticmethod
    def _generate_rule_based(projects_data: list[dict]) -> list[Suggestion]:
        """Generate simple rule-based suggestions when AI is unavailable."""
        suggestions = []

        for proj in projects_data:
            name = proj.get("name", "unknown")
            failing_ci = proj.get("failing_ci_count", 0)
            changes_requested = proj.get("changes_requested_count", 0)
            open_prs = proj.get("open_prs_count", 0)

            if failing_ci > 0:
                suggestions.append(Suggestion(
                    priority="high",
                    project=name,
                    action=f"Fix {failing_ci} PR(s) with failing CI",
                    reason="CI failures block merging and slow down development",
                ))

            if changes_requested > 0:
                suggestions.append(Suggestion(
                    priority="high",
                    project=name,
                    action=f"Address review comments on {changes_requested} PR(s)",
                    reason="Unresolved review comments need attention",
                ))

            if open_prs > 3:
                suggestions.append(Suggestion(
                    priority="medium",
                    project=name,
                    action=f"Review and merge/close some of the {open_prs} open PRs",
                    reason="Too many open PRs can slow development velocity",
                ))

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 1))

        return suggestions[:6]
