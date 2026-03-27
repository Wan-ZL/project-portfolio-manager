from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm.ai.summary import (
    AISummaryGenerator,
    build_summary_prompt,
    compute_input_hash,
    format_summary_for_display,
    parse_summary_response,
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
    prompt = build_summary_prompt("proj", {})
    assert "JSON" in prompt
    assert "one_line_status" in prompt
    assert "key_progress" in prompt
    assert "issues_needing_attention" in prompt
    assert "suggested_next_steps" in prompt


# --- parse_summary_response tests ---

def test_parse_valid_json():
    response = json.dumps({
        "one_line_status": "Project is on track",
        "key_progress": ["Feature A done"],
        "issues_needing_attention": ["Bug in auth"],
        "suggested_next_steps": ["Fix auth bug"],
    })
    result = parse_summary_response(response)
    assert result["one_line_status"] == "Project is on track"
    assert result["key_progress"] == ["Feature A done"]
    assert result["issues_needing_attention"] == ["Bug in auth"]
    assert result["suggested_next_steps"] == ["Fix auth bug"]


def test_parse_json_in_code_block():
    response = '''Here's the summary:

```json
{
  "one_line_status": "All good",
  "key_progress": ["Done"],
  "issues_needing_attention": [],
  "suggested_next_steps": []
}
```

That's the analysis.'''
    result = parse_summary_response(response)
    assert result["one_line_status"] == "All good"
    assert result["key_progress"] == ["Done"]


def test_parse_json_in_generic_code_block():
    response = '''```
{
  "one_line_status": "Status here",
  "key_progress": [],
  "issues_needing_attention": [],
  "suggested_next_steps": ["Do X"]
}
```'''
    result = parse_summary_response(response)
    assert result["one_line_status"] == "Status here"
    assert result["suggested_next_steps"] == ["Do X"]


def test_parse_invalid_json():
    response = "This is not JSON at all, just plain text about the project."
    result = parse_summary_response(response)
    assert result["one_line_status"] != ""
    assert isinstance(result["key_progress"], list)
    assert isinstance(result["issues_needing_attention"], list)
    assert isinstance(result["suggested_next_steps"], list)


def test_parse_partial_json():
    response = json.dumps({
        "one_line_status": "Partial data",
    })
    result = parse_summary_response(response)
    assert result["one_line_status"] == "Partial data"
    assert result["key_progress"] == []


# --- format_summary_for_display tests ---

def test_format_full_summary():
    summary = {
        "one_line_status": "Project is healthy",
        "key_progress": ["Feature A shipped", "Tests added"],
        "issues_needing_attention": ["CI flaky"],
        "suggested_next_steps": ["Fix CI", "Review PRs"],
    }
    formatted = format_summary_for_display(summary)
    assert "Project is healthy" in formatted
    assert "Feature A shipped" in formatted
    assert "CI flaky" in formatted
    assert "Fix CI" in formatted
    assert "Key Progress" in formatted
    assert "Needs Attention" in formatted
    assert "Suggested Next Steps" in formatted


def test_format_empty_summary():
    summary = {
        "one_line_status": "",
        "key_progress": [],
        "issues_needing_attention": [],
        "suggested_next_steps": [],
    }
    formatted = format_summary_for_display(summary)
    assert "No summary available" in formatted


def test_format_summary_only_status():
    summary = {
        "one_line_status": "All good",
        "key_progress": [],
        "issues_needing_attention": [],
        "suggested_next_steps": [],
    }
    formatted = format_summary_for_display(summary)
    assert "All good" in formatted


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
    # Pre-populate cache
    summary_data = {
        "one_line_status": "Cached summary",
        "key_progress": [],
        "issues_needing_attention": [],
        "suggested_next_steps": [],
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
        "issues_needing_attention": [],
        "suggested_next_steps": [],
    }
    db.save_summary("proj", json.dumps(summary_data), "[]", "old_hash")

    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.summary.API_KEY_FILE", Path("/nonexistent")):
            gen = AISummaryGenerator(db=db)
            result = gen.generate_summary("proj", {"commits": ["new_data"]})
            # Should NOT return cached since hash changed
            assert "unavailable" in result["one_line_status"].lower()


def test_generator_force_bypasses_cache(db):
    summary_data = {
        "one_line_status": "Cached",
        "key_progress": [],
        "issues_needing_attention": [],
        "suggested_next_steps": [],
    }
    input_data = {"commits": ["a"]}
    input_hash = compute_input_hash(input_data)
    db.save_summary("proj", json.dumps(summary_data), "[]", input_hash)

    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.summary.API_KEY_FILE", Path("/nonexistent")):
            gen = AISummaryGenerator(db=db)
            result = gen.generate_summary("proj", input_data, force=True)
            # Should bypass cache and try API (fails, returns unavailable)
            assert "unavailable" in result["one_line_status"].lower()


def test_generator_full_flow_with_mock_api(db):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "one_line_status": "AI generated status",
        "key_progress": ["Progress 1"],
        "issues_needing_attention": ["Issue 1"],
        "suggested_next_steps": ["Step 1"],
    }))]
    mock_client.messages.create.return_value = mock_response

    gen = AISummaryGenerator(db=db)
    gen._client = mock_client

    result = gen.generate_summary("test-proj", {"commits": ["fix"]})

    assert result["one_line_status"] == "AI generated status"
    assert result["key_progress"] == ["Progress 1"]

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
    summary_data = {"one_line_status": "From cache", "key_progress": [], "issues_needing_attention": [], "suggested_next_steps": []}
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
