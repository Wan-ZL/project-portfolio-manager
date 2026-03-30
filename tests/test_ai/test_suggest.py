from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm.ai.suggest import (
    AISuggestionEngine,
    Suggestion,
    build_suggest_prompt,
    format_suggestions_for_display,
    parse_suggestions_response,
)
from pm.db.database import Database


# --- Suggestion dataclass tests ---

def test_suggestion_creation():
    s = Suggestion(
        priority="high",
        project="my-project",
        action="Fix CI",
        reason="CI is blocking merges",
    )
    assert s.priority == "high"
    assert s.project == "my-project"


def test_suggestion_to_dict():
    s = Suggestion(priority="medium", project="proj", action="Review PR", reason="Stale")
    d = s.to_dict()
    assert d["priority"] == "medium"
    assert d["project"] == "proj"
    assert d["action"] == "Review PR"
    assert d["reason"] == "Stale"


def test_suggestion_from_dict():
    data = {
        "priority": "low",
        "project": "proj",
        "action": "Update deps",
        "reason": "Outdated",
    }
    s = Suggestion.from_dict(data)
    assert s.priority == "low"
    assert s.project == "proj"
    assert s.action == "Update deps"


def test_suggestion_from_dict_defaults():
    s = Suggestion.from_dict({})
    assert s.priority == "medium"
    assert s.project == ""
    assert s.action == ""


# --- build_suggest_prompt tests ---

def test_prompt_contains_project_data():
    projects = [
        {
            "name": "my-project",
            "summary": {"one_line_status": "All good", "urgency": "high"},
            "open_prs_count": 5,
            "active_sessions_count": 1,
            "failing_ci_count": 2,
            "changes_requested_count": 1,
        }
    ]
    prompt = build_suggest_prompt(projects)
    assert "my-project" in prompt
    assert "Open PRs: 5" in prompt
    assert "PRs with failing CI: 2" in prompt
    assert "Urgency: high" in prompt


def test_prompt_multiple_projects():
    projects = [
        {"name": "proj-a", "summary": "A", "open_prs_count": 2,
         "active_sessions_count": 0, "failing_ci_count": 0, "changes_requested_count": 0},
        {"name": "proj-b", "summary": "B", "open_prs_count": 3,
         "active_sessions_count": 1, "failing_ci_count": 1, "changes_requested_count": 0},
    ]
    prompt = build_suggest_prompt(projects)
    assert "proj-a" in prompt
    assert "proj-b" in prompt


def test_prompt_requests_json():
    prompt = build_suggest_prompt([])
    assert "JSON" in prompt
    assert "suggestions" in prompt
    assert "priority" in prompt


# --- parse_suggestions_response tests ---

def test_parse_valid_suggestions():
    response = json.dumps({
        "suggestions": [
            {"priority": "high", "project": "proj", "action": "Fix CI", "reason": "Blocked"},
            {"priority": "low", "project": "proj", "action": "Docs", "reason": "Nice-to-have"},
        ]
    })
    suggestions = parse_suggestions_response(response)
    assert len(suggestions) == 2
    assert suggestions[0].priority == "high"
    assert suggestions[1].priority == "low"


def test_parse_suggestions_in_code_block():
    response = '''```json
{
  "suggestions": [
    {"priority": "medium", "project": "proj", "action": "Review", "reason": "Stale"}
  ]
}
```'''
    suggestions = parse_suggestions_response(response)
    assert len(suggestions) == 1
    assert suggestions[0].priority == "medium"


def test_parse_invalid_response():
    suggestions = parse_suggestions_response("Not JSON at all")
    assert suggestions == []


def test_parse_empty_suggestions():
    response = json.dumps({"suggestions": []})
    suggestions = parse_suggestions_response(response)
    assert suggestions == []


# --- format_suggestions_for_display tests ---

def test_format_suggestions():
    suggestions = [
        Suggestion(priority="high", project="proj-a", action="Fix CI", reason="Blocking"),
        Suggestion(priority="medium", project="proj-b", action="Review PR", reason="Waiting"),
    ]
    formatted = format_suggestions_for_display(suggestions)
    assert "proj-a" in formatted
    assert "Fix CI" in formatted
    assert "proj-b" in formatted
    assert "Review PR" in formatted
    assert "Suggestions" in formatted


def test_format_empty_suggestions():
    formatted = format_suggestions_for_display([])
    assert "No suggestions" in formatted


def test_format_priority_icons():
    high = [Suggestion(priority="high", project="p", action="a", reason="r")]
    formatted = format_suggestions_for_display(high)
    assert "!!!" in formatted

    medium = [Suggestion(priority="medium", project="p", action="a", reason="r")]
    formatted = format_suggestions_for_display(medium)
    assert "!!" in formatted

    low = [Suggestion(priority="low", project="p", action="a", reason="r")]
    formatted = format_suggestions_for_display(low)
    assert "!" in formatted


# --- AISuggestionEngine tests ---

@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


def test_engine_creation(db):
    engine = AISuggestionEngine(db=db)
    assert engine.db is db


def test_engine_rule_based_fallback():
    projects_data = [
        {
            "name": "proj-a",
            "open_prs_count": 2,
            "failing_ci_count": 1,
            "changes_requested_count": 0,
            "active_sessions_count": 0,
        },
        {
            "name": "proj-b",
            "open_prs_count": 5,
            "failing_ci_count": 0,
            "changes_requested_count": 2,
            "active_sessions_count": 1,
        },
    ]
    suggestions = AISuggestionEngine._generate_rule_based(projects_data)
    assert len(suggestions) > 0
    # High priority items should come first
    assert suggestions[0].priority == "high"


def test_engine_rule_based_empty():
    suggestions = AISuggestionEngine._generate_rule_based([])
    assert suggestions == []


def test_engine_rule_based_no_issues():
    projects_data = [
        {
            "name": "proj",
            "open_prs_count": 1,
            "failing_ci_count": 0,
            "changes_requested_count": 0,
            "active_sessions_count": 0,
        },
    ]
    suggestions = AISuggestionEngine._generate_rule_based(projects_data)
    assert len(suggestions) == 0


def test_engine_rule_based_ci_failure():
    projects_data = [
        {
            "name": "proj",
            "open_prs_count": 3,
            "failing_ci_count": 2,
            "changes_requested_count": 0,
            "active_sessions_count": 0,
        },
    ]
    suggestions = AISuggestionEngine._generate_rule_based(projects_data)
    assert any(s.priority == "high" and "CI" in s.action for s in suggestions)


def test_engine_rule_based_changes_requested():
    projects_data = [
        {
            "name": "proj",
            "open_prs_count": 3,
            "failing_ci_count": 0,
            "changes_requested_count": 3,
            "active_sessions_count": 0,
        },
    ]
    suggestions = AISuggestionEngine._generate_rule_based(projects_data)
    assert any(s.priority == "high" and "review" in s.action.lower() for s in suggestions)


def test_engine_rule_based_many_prs():
    projects_data = [
        {
            "name": "proj",
            "open_prs_count": 10,
            "failing_ci_count": 0,
            "changes_requested_count": 0,
            "active_sessions_count": 0,
        },
    ]
    suggestions = AISuggestionEngine._generate_rule_based(projects_data)
    assert any(s.priority == "medium" and "merge" in s.action.lower() for s in suggestions)


def test_engine_no_api_key(db):
    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.summary.API_KEY_FILE", Path("/nonexistent")):
            engine = AISuggestionEngine(db=db)
            result = engine.generate_suggestions([
                {"name": "p", "open_prs_count": 1, "failing_ci_count": 1,
                 "changes_requested_count": 0, "active_sessions_count": 0},
            ])
            # Falls back to rule-based
            assert isinstance(result, list)


def test_engine_caches_suggestions(db):
    projects_data = [
        {"name": "p", "open_prs_count": 2, "failing_ci_count": 1,
         "changes_requested_count": 0, "active_sessions_count": 0},
    ]

    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.summary.API_KEY_FILE", Path("/nonexistent")):
            engine = AISuggestionEngine(db=db)
            result1 = engine.generate_suggestions(projects_data)
            assert len(result1) > 0

            # Second call should use cache
            result2 = engine.generate_suggestions(projects_data)
            assert len(result2) == len(result1)


def test_engine_get_cached_suggestions(db):
    # Pre-populate cache
    suggestions_data = [
        {"priority": "high", "project": "proj", "action": "Fix", "reason": "Broken"},
    ]
    db.save_summary("__ppm_internal__suggestions__", "", json.dumps(suggestions_data), "hash1")

    engine = AISuggestionEngine(db=db)
    result = engine.get_cached_suggestions()
    assert len(result) == 1
    assert result[0].priority == "high"


def test_engine_get_cached_suggestions_empty(db):
    engine = AISuggestionEngine(db=db)
    result = engine.get_cached_suggestions()
    assert result == []


def test_engine_full_flow_with_mock_api(db):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "suggestions": [
            {"priority": "high", "project": "proj", "action": "Fix CI", "reason": "Blocking"},
        ]
    }))]
    mock_client.messages.create.return_value = mock_response

    engine = AISuggestionEngine(db=db)
    engine._client = mock_client

    result = engine.generate_suggestions([
        {"name": "proj", "open_prs_count": 3, "failing_ci_count": 1,
         "changes_requested_count": 0, "active_sessions_count": 0},
    ])

    assert len(result) == 1
    assert result[0].priority == "high"
    assert result[0].action == "Fix CI"


def test_engine_handles_api_error(db):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")

    engine = AISuggestionEngine(db=db)
    engine._client = mock_client

    result = engine.generate_suggestions([
        {"name": "proj", "open_prs_count": 3, "failing_ci_count": 2,
         "changes_requested_count": 0, "active_sessions_count": 0},
    ])
    # Should fall back to rule-based
    assert isinstance(result, list)
    assert len(result) > 0


def test_engine_rule_based_max_suggestions():
    projects_data = [
        {"name": f"proj-{i}", "open_prs_count": 10,
         "failing_ci_count": 3, "changes_requested_count": 2,
         "active_sessions_count": 0}
        for i in range(10)
    ]
    suggestions = AISuggestionEngine._generate_rule_based(projects_data)
    assert len(suggestions) <= 6


def test_engine_rule_based_priority_ordering():
    projects_data = [
        {"name": "low-proj", "open_prs_count": 5,
         "failing_ci_count": 0, "changes_requested_count": 0, "active_sessions_count": 0},
        {"name": "high-proj", "open_prs_count": 2,
         "failing_ci_count": 2, "changes_requested_count": 0, "active_sessions_count": 0},
    ]
    suggestions = AISuggestionEngine._generate_rule_based(projects_data)
    if len(suggestions) >= 2:
        priorities = [s.priority for s in suggestions]
        assert priorities.index("high") < priorities.index("medium")
