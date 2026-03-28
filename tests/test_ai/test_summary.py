from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm.ai.summary import (
    SUMMARY_SYSTEM_PROMPT,
    AISummaryGenerator,
    build_summary_prompt,
    compute_input_hash,
    format_summary_for_display,
    parse_summary_response,
    _get_last_session,
    _get_days_since_last_activity,
    _count_other_commits,
)
from pm.db.database import Database


# --- compute_input_hash tests ---

def test_hash_deterministic():
    data = {"commits": ["fix bug"], "prs": [1, 2]}
    h1 = compute_input_hash(data)
    h2 = compute_input_hash(data)
    assert h1 == h2


def test_hash_changes_with_data():
    data1 = {"commits": ["fix bug"]}
    data2 = {"commits": ["fix bug", "add feature"]}
    h1 = compute_input_hash(data1)
    h2 = compute_input_hash(data2)
    assert h1 != h2


def test_hash_length():
    data = {"key": "value"}
    h = compute_input_hash(data)
    assert len(h) == 16


def test_hash_handles_datetime():
    from datetime import datetime
    data = {"time": datetime(2026, 3, 25)}
    h = compute_input_hash(data)
    assert isinstance(h, str)
    assert len(h) == 16


# --- build_summary_prompt tests ---

def test_prompt_contains_project_name():
    prompt = build_summary_prompt("my-project", {})
    assert "my-project" in prompt


def test_prompt_contains_commits():
    data = {"recent_commits": ["fix auth bug", "update docs"]}
    prompt = build_summary_prompt("proj", data)
    assert "fix auth bug" in prompt
    assert "update docs" in prompt


def test_prompt_contains_prs():
    data = {
        "open_prs": [
            {"number": 42, "title": "Fix bug", "ci_status": "failing", "review_status": "pending"},
        ]
    }
    prompt = build_summary_prompt("proj", data)
    assert "#42" in prompt
    assert "Fix bug" in prompt


def test_prompt_contains_issues():
    data = {
        "open_issues": [
            {"number": 10, "title": "Login timeout"},
        ]
    }
    prompt = build_summary_prompt("proj", data)
    assert "#10" in prompt
    assert "Login timeout" in prompt


def test_prompt_contains_instructions():
    data = {"instructions": "Use TDD approach"}
    prompt = build_summary_prompt("proj", data)
    assert "Use TDD approach" in prompt


def test_prompt_handles_empty_data():
    prompt = build_summary_prompt("proj", {})
    assert "proj" in prompt
    assert "no recent commits" in prompt
    assert "no open PRs" in prompt
    assert "no open issues" in prompt


def test_prompt_requests_json_output():
    # The JSON format is now defined in SUMMARY_SYSTEM_PROMPT
    assert "one_line_status" in SUMMARY_SYSTEM_PROMPT
    assert "key_progress" in SUMMARY_SYSTEM_PROMPT
    assert "needs_attention" in SUMMARY_SYSTEM_PROMPT
    assert "suggested_next_steps" in SUMMARY_SYSTEM_PROMPT
    assert "urgency" in SUMMARY_SYSTEM_PROMPT
    # The user prompt should still contain the project data
    prompt = build_summary_prompt("proj", {})
    assert "JSON" in prompt
    assert "proj" in prompt


# --- parse_summary_response tests ---

def test_parse_valid_json():
    response = json.dumps({
        "one_line_status": "PR #42 auth bug CI failing; 2 PRs ready to merge",
        "key_progress": ["Feature A done"],
        "needs_attention": ["Bug in auth"],
        "suggested_next_steps": ["Fix auth bug"],
        "urgency": "high",
    })
    result = parse_summary_response(response)
    assert result["one_line_status"] == "PR #42 auth bug CI failing; 2 PRs ready to merge"
    assert result["key_progress"] == ["Feature A done"]
    assert result["needs_attention"] == ["Bug in auth"]
    assert result["suggested_next_steps"] == ["Fix auth bug"]
    assert result["urgency"] == "high"


def test_parse_json_in_code_block():
    response = '''Here's the summary:

```json
{
  "one_line_status": "All good",
  "key_progress": ["Done"],
  "needs_attention": [],
  "suggested_next_steps": [],
  "urgency": "low"
}
```

That's the analysis.'''
    result = parse_summary_response(response)
    assert result["one_line_status"] == "All good"
    assert result["key_progress"] == ["Done"]
    assert result["urgency"] == "low"


def test_parse_json_in_generic_code_block():
    response = '''```
{
  "one_line_status": "Status here",
  "key_progress": [],
  "needs_attention": [],
  "suggested_next_steps": ["Do X"],
  "urgency": "medium"
}
```'''
    result = parse_summary_response(response)
    assert result["one_line_status"] == "Status here"
    assert result["suggested_next_steps"] == ["Do X"]
    assert result["urgency"] == "medium"


def test_parse_invalid_json():
    response = "This is not JSON at all, just plain text about the project."
    result = parse_summary_response(response)
    assert result["one_line_status"] != ""
    assert isinstance(result["key_progress"], list)
    assert isinstance(result["needs_attention"], list)
    assert isinstance(result["suggested_next_steps"], list)
    assert result["urgency"] == "medium"


def test_parse_partial_json():
    response = json.dumps({
        "one_line_status": "Partial data",
    })
    result = parse_summary_response(response)
    assert result["one_line_status"] == "Partial data"
    assert result["key_progress"] == []
    assert result["urgency"] == "medium"


def test_parse_legacy_issues_needing_attention():
    """Old cached summaries may use issues_needing_attention instead of needs_attention."""
    response = json.dumps({
        "one_line_status": "Legacy format",
        "key_progress": [],
        "issues_needing_attention": ["Old issue format"],
        "suggested_next_steps": [],
    })
    result = parse_summary_response(response)
    assert result["needs_attention"] == ["Old issue format"]
    assert result["urgency"] == "medium"


def test_parse_urgency_defaults_when_missing():
    response = json.dumps({
        "one_line_status": "No urgency field",
        "key_progress": [],
        "needs_attention": [],
        "suggested_next_steps": [],
    })
    result = parse_summary_response(response)
    assert result["urgency"] == "medium"


# --- format_summary_for_display tests ---

def test_format_full_summary():
    summary = {
        "one_line_status": "PR #42 CI failing, needs fix",
        "key_progress": ["Feature A shipped", "Tests added"],
        "needs_attention": ["CI flaky"],
        "suggested_next_steps": ["Fix CI", "Review PRs"],
        "urgency": "high",
    }
    formatted = format_summary_for_display(summary)
    assert "PR #42 CI failing, needs fix" in formatted
    assert "Feature A shipped" in formatted
    assert "CI flaky" in formatted
    assert "Fix CI" in formatted
    assert "Key Progress" in formatted
    assert "Needs Attention" in formatted
    assert "Next Steps" in formatted
    assert "HIGH" in formatted


def test_format_empty_summary():
    summary = {
        "one_line_status": "",
        "key_progress": [],
        "needs_attention": [],
        "suggested_next_steps": [],
    }
    formatted = format_summary_for_display(summary)
    assert "No summary available" in formatted


def test_format_summary_only_status():
    summary = {
        "one_line_status": "All good",
        "key_progress": [],
        "needs_attention": [],
        "suggested_next_steps": [],
        "urgency": "low",
    }
    formatted = format_summary_for_display(summary)
    assert "All good" in formatted
    assert "LOW" in formatted


def test_format_urgency_colors():
    for urgency, label in [("high", "HIGH"), ("medium", "MEDIUM"), ("low", "LOW"), ("idle", "IDLE")]:
        summary = {
            "one_line_status": "Some status",
            "key_progress": [],
            "needs_attention": [],
            "suggested_next_steps": [],
            "urgency": urgency,
        }
        formatted = format_summary_for_display(summary)
        assert label in formatted


def test_format_legacy_issues_needing_attention():
    """format_summary_for_display should handle old-format summaries."""
    summary = {
        "one_line_status": "Legacy",
        "key_progress": [],
        "issues_needing_attention": ["Old format item"],
        "suggested_next_steps": [],
    }
    formatted = format_summary_for_display(summary)
    assert "Old format item" in formatted
    assert "Needs Attention" in formatted


# --- AISummaryGenerator tests ---

@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


def test_generator_creation(db):
    gen = AISummaryGenerator(db=db)
    assert gen.db is db


def test_generator_no_api_key():
    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.summary.API_KEY_FILE", Path("/nonexistent")):
            gen = AISummaryGenerator(db=None)
            assert not gen.available


def test_generator_returns_unavailable_message_without_key():
    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.summary.API_KEY_FILE", Path("/nonexistent")):
            gen = AISummaryGenerator(db=None)
            result = gen.generate_summary("proj", {"commits": []})
            assert "unavailable" in result["one_line_status"].lower()


def test_generator_uses_cache(db):
    summary_data = {
        "one_line_status": "Cached summary",
        "key_progress": [],
        "needs_attention": [],
        "suggested_next_steps": [],
        "urgency": "low",
    }
    input_data = {"commits": ["a"]}
    from pm.ai.summary import compute_input_hash
    input_hash = compute_input_hash(input_data)
    db.save_summary("proj", json.dumps(summary_data), "[]", input_hash)

    gen = AISummaryGenerator(db=db)
    result = gen.generate_summary("proj", input_data)
    assert result["one_line_status"] == "Cached summary"


def test_generator_cache_miss_on_hash_change(db):
    summary_data = {
        "one_line_status": "Old cached",
        "key_progress": [],
        "needs_attention": [],
        "suggested_next_steps": [],
        "urgency": "medium",
    }
    db.save_summary("proj", json.dumps(summary_data), "[]", "old_hash")

    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.summary.API_KEY_FILE", Path("/nonexistent")):
            gen = AISummaryGenerator(db=db)
            result = gen.generate_summary("proj", {"commits": ["new_data"]})
            assert "unavailable" in result["one_line_status"].lower()


def test_generator_force_bypasses_cache(db):
    summary_data = {
        "one_line_status": "Cached",
        "key_progress": [],
        "needs_attention": [],
        "suggested_next_steps": [],
        "urgency": "low",
    }
    input_data = {"commits": ["a"]}
    input_hash = compute_input_hash(input_data)
    db.save_summary("proj", json.dumps(summary_data), "[]", input_hash)

    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.summary.API_KEY_FILE", Path("/nonexistent")):
            gen = AISummaryGenerator(db=db)
            result = gen.generate_summary("proj", input_data, force=True)
            assert "unavailable" in result["one_line_status"].lower()


def test_generator_full_flow_with_mock_api(db):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "one_line_status": "PR #42 auth bug CI failing; merge PR #38 mobile layout",
        "key_progress": ["Progress 1"],
        "needs_attention": ["Issue 1"],
        "suggested_next_steps": ["Step 1"],
        "urgency": "high",
    }))]
    mock_client.messages.create.return_value = mock_response

    gen = AISummaryGenerator(db=db)
    gen._client = mock_client

    result = gen.generate_summary("test-proj", {"commits": ["fix"]})

    assert result["one_line_status"] == "PR #42 auth bug CI failing; merge PR #38 mobile layout"
    assert result["key_progress"] == ["Progress 1"]
    assert result["needs_attention"] == ["Issue 1"]
    assert result["urgency"] == "high"

    # Verify saved to cache
    cached = db.get_summary("test-proj")
    assert cached is not None
    assert cached.input_hash is not None


def test_generator_handles_api_error(db):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")

    gen = AISummaryGenerator(db=db)
    gen._client = mock_client

    result = gen.generate_summary("proj", {"commits": []})
    assert "failed" in result["one_line_status"].lower()


def test_get_cached_summary(db):
    summary_data = {"one_line_status": "From cache", "key_progress": [], "needs_attention": [], "suggested_next_steps": [], "urgency": "low"}
    db.save_summary("proj", json.dumps(summary_data), "[]", "hash1")

    gen = AISummaryGenerator(db=db)
    result = gen.get_cached_summary("proj")
    assert result is not None
    assert result["one_line_status"] == "From cache"


def test_get_cached_summary_none(db):
    gen = AISummaryGenerator(db=db)
    result = gen.get_cached_summary("nonexistent")
    assert result is None


def test_invalidate_cache(db):
    db.save_summary("proj", "data", "[]", "hash1")

    gen = AISummaryGenerator(db=db)
    gen.invalidate_cache("proj")

    cached = db.get_summary("proj")
    assert cached.input_hash == ""


# --- System prompt tests ---

def test_system_prompt_rejects_vague_language():
    assert "项目进展顺利" in SUMMARY_SYSTEM_PROMPT
    assert "项目状态良好" in SUMMARY_SYSTEM_PROMPT
    assert "绝对不能" in SUMMARY_SYSTEM_PROMPT


def test_system_prompt_has_good_examples():
    assert "PR #42" in SUMMARY_SYSTEM_PROMPT
    assert "闲置" in SUMMARY_SYSTEM_PROMPT
    assert "merge" in SUMMARY_SYSTEM_PROMPT


def test_system_prompt_defines_urgency():
    assert "high/medium/low/idle" in SUMMARY_SYSTEM_PROMPT


# --- Helper function tests ---

def test_get_last_session_no_db():
    assert _get_last_session("proj", None) is None


def test_get_last_session_no_sessions(db):
    result = _get_last_session("proj", db)
    assert result is None


def test_get_days_since_last_activity_no_db():
    assert _get_days_since_last_activity("proj", None) is None


def test_get_days_since_last_activity_no_sessions(db):
    result = _get_days_since_last_activity("proj", db)
    assert result is None


def test_count_other_commits_placeholder():
    assert _count_other_commits("proj") is None


def test_build_prompt_with_activity_data():
    """When db has sessions, prompt includes activity section."""
    mock_db = MagicMock()
    mock_session = MagicMock()
    mock_session.task_description = "Fix auth bug"
    mock_session.status = "completed"
    mock_session.updated_at = datetime(2026, 3, 20, 10, 0)
    mock_session.created_at = datetime(2026, 3, 20, 9, 0)
    mock_db.get_sessions_by_project.return_value = [mock_session]

    prompt = build_summary_prompt("proj", {}, db=mock_db)
    assert "Your Recent Activity" in prompt
    assert "Fix auth bug" in prompt
    assert "completed" in prompt


def test_build_prompt_without_db():
    """Without db, prompt should still work but without activity section."""
    prompt = build_summary_prompt("proj", {})
    assert "proj" in prompt
    assert "Your Recent Activity" not in prompt


def test_generator_api_call_uses_system_prompt(db):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "one_line_status": "test",
        "key_progress": [],
        "needs_attention": [],
        "suggested_next_steps": [],
        "urgency": "low",
    }))]
    mock_client.messages.create.return_value = mock_response

    gen = AISummaryGenerator(db=db)
    gen._client = mock_client

    gen.generate_summary("proj", {"commits": ["a"]})

    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs.kwargs.get("system") == SUMMARY_SYSTEM_PROMPT
