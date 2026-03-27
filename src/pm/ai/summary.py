from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# API key file path (with invisible character in filename, matching user's actual path)
API_KEY_FILE = Path("/Users/zelin/Downloads/API Key/\u200eanthropic-api-key.txt")

MODEL = "claude-sonnet-4-5-20250514"


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


def build_summary_prompt(project_name: str, input_data: dict) -> str:
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

    prompt = f"""You are an AI assistant helping a developer manage multiple projects.
Analyze the following data for the project "{project_name}" and generate a structured summary.

## Project Data

### Recent Commits (last 7 days):
{commits_text}

### Open Pull Requests:
{prs_text}

### Open Issues:
{issues_text}

### CI Status: {ci_status}

### Project Instructions:
{instructions or '(none)'}

## Output Format

Please respond in the following JSON format (use mixed Chinese + English technical terms, the user prefers this style):

{{
  "one_line_status": "A single sentence summarizing the project's current state",
  "key_progress": ["Progress item 1", "Progress item 2"],
  "issues_needing_attention": ["Issue 1", "Issue 2"],
  "suggested_next_steps": ["Step 1", "Step 2"]
}}

Keep it concise but informative. Use technical terms in English but explanatory text can mix Chinese and English naturally.
"""
    return prompt


def parse_summary_response(response_text: str) -> dict:
    """Parse the AI response into a structured summary dict."""
    # Try to extract JSON from the response
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
        return {
            "one_line_status": data.get("one_line_status", ""),
            "key_progress": data.get("key_progress", []),
            "issues_needing_attention": data.get("issues_needing_attention", []),
            "suggested_next_steps": data.get("suggested_next_steps", []),
        }
    except (json.JSONDecodeError, ValueError):
        # If JSON parsing fails, return the raw text as one_line_status
        return {
            "one_line_status": text[:200],
            "key_progress": [],
            "issues_needing_attention": [],
            "suggested_next_steps": [],
        }


def format_summary_for_display(summary: dict) -> str:
    """Format a parsed summary dict into Rich markup for TUI display."""
    lines = []

    one_line = summary.get("one_line_status", "")
    if one_line:
        lines.append(f"[bold]{one_line}[/bold]")
        lines.append("")

    progress = summary.get("key_progress", [])
    if progress:
        lines.append("[bold cyan]Key Progress:[/bold cyan]")
        for item in progress:
            lines.append(f"  [green]+[/green] {item}")
        lines.append("")

    issues = summary.get("issues_needing_attention", [])
    if issues:
        lines.append("[bold yellow]Needs Attention:[/bold yellow]")
        for item in issues:
            lines.append(f"  [yellow]![/yellow] {item}")
        lines.append("")

    steps = summary.get("suggested_next_steps", [])
    if steps:
        lines.append("[bold cyan]Suggested Next Steps:[/bold cyan]")
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
                "issues_needing_attention": [],
                "suggested_next_steps": [],
            }

        prompt = build_summary_prompt(project_name, input_data)

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            summary = parse_summary_response(response_text)
        except Exception as e:
            logger.error(f"Failed to generate summary for {project_name}: {e}")
            summary = {
                "one_line_status": f"AI summary generation failed: {e}",
                "key_progress": [],
                "issues_needing_attention": [],
                "suggested_next_steps": [],
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
