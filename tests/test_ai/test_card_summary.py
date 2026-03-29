from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm.ai.card_summary import (
    CARD_SUMMARY_SYSTEM_PROMPT,
    CardContext,
    CardSummary,
    CardSummaryGenerator,
    build_card_prompt,
    compute_card_hash,
    generate_fallback,
    parse_card_response,
    _format_time_ago,
    _get_last_session,
)
from pm.db.database import Database


# --- CardContext tests ---

def test_card_context_defaults():
    ctx = CardContext(project_name="test")
    assert ctx.project_name == "test"
    assert ctx.recent_commits == []
    assert ctx.open_prs == []
    assert ctx.recently_merged == []
    assert ctx.open_issues_count == 0
    assert ctx.last_command == ""
    assert ctx.last_command_status == ""
    assert ctx.last_command_time == ""
    assert ctx.last_command_pr is None
    assert ctx.days_since_last_activity == 0


def test_card_context_with_data():
    ctx = CardContext(
        project_name="myproj",
        recent_commits=[{"sha": "abc1234", "message": "fix bug", "author": "dev", "date": "2026-03-25"}],
        open_prs=[{"number": 42, "title": "Fix auth", "ci_status": "failing", "review_status": "pending"}],
        recently_merged=[{"number": 38, "title": "Mobile layout", "merged_at": "2026-03-24"}],
        open_issues_count=5,
        last_command="Fix the auth bug in login flow",
        last_command_status="running",
        last_command_time="2h ago",
        last_command_pr=42,
        days_since_last_activity=3,
    )
    assert ctx.project_name == "myproj"
    assert len(ctx.recent_commits) == 1
    assert ctx.open_prs[0]["number"] == 42
    assert ctx.last_command_pr == 42


# --- CardSummary tests ---

def test_card_summary_to_dict():
    s = CardSummary(dynamic="test dynamic", recommendation="do X", last_command_summary="ran Y")
    d = s.to_dict()
    assert d["dynamic"] == "test dynamic"
    assert d["recommendation"] == "do X"
    assert d["last_command_summary"] == "ran Y"


def test_card_summary_from_dict():
    s = CardSummary.from_dict({"dynamic": "d", "recommendation": "r", "last_command_summary": "l"})
    assert s.dynamic == "d"
    assert s.recommendation == "r"
    assert s.last_command_summary == "l"


def test_card_summary_from_dict_defaults():
    s = CardSummary.from_dict({})
    assert s.dynamic == ""
    assert s.recommendation == ""
    assert s.last_command_summary == ""


# --- compute_card_hash tests ---

def test_hash_deterministic():
    ctx = CardContext(project_name="test", open_issues_count=5)
    h1 = compute_card_hash(ctx)
    h2 = compute_card_hash(ctx)
    assert h1 == h2


def test_hash_changes_with_data():
    ctx1 = CardContext(project_name="test", open_issues_count=5)
    ctx2 = CardContext(project_name="test", open_issues_count=10)
    h1 = compute_card_hash(ctx1)
    h2 = compute_card_hash(ctx2)
    assert h1 != h2


def test_hash_changes_with_commits():
    ctx1 = CardContext(project_name="test")
    ctx2 = CardContext(
        project_name="test",
        recent_commits=[{"sha": "abc", "message": "fix"}],
    )
    assert compute_card_hash(ctx1) != compute_card_hash(ctx2)


def test_hash_length():
    ctx = CardContext(project_name="test")
    h = compute_card_hash(ctx)
    assert len(h) == 16


# --- build_card_prompt tests ---

def test_prompt_contains_project_name():
    ctx = CardContext(project_name="my-project")
    prompt = build_card_prompt("my-project", ctx)
    assert "my-project" in prompt


def test_prompt_contains_commits():
    ctx = CardContext(
        project_name="proj",
        recent_commits=[{"sha": "abc1234", "message": "fix auth bug", "author": "dev", "date": "2026-03-25"}],
    )
    prompt = build_card_prompt("proj", ctx)
    assert "fix auth bug" in prompt
    assert "abc1234" in prompt


def test_prompt_contains_prs():
    ctx = CardContext(
        project_name="proj",
        open_prs=[{"number": 42, "title": "Fix bug", "ci_status": "failing", "review_status": "pending"}],
    )
    prompt = build_card_prompt("proj", ctx)
    assert "#42" in prompt
    assert "Fix bug" in prompt


def test_prompt_contains_merged():
    ctx = CardContext(
        project_name="proj",
        recently_merged=[{"number": 38, "title": "Mobile layout", "merged_at": "2026-03-24"}],
    )
    prompt = build_card_prompt("proj", ctx)
    assert "#38" in prompt
    assert "Mobile layout" in prompt


def test_prompt_contains_last_command():
    ctx = CardContext(
        project_name="proj",
        last_command="Fix auth bug",
        last_command_status="running",
        last_command_time="2h ago",
        last_command_pr=42,
    )
    prompt = build_card_prompt("proj", ctx)
    assert "Fix auth bug" in prompt
    assert "running" in prompt
    assert "#42" in prompt


def test_prompt_handles_empty_data():
    ctx = CardContext(project_name="proj")
    prompt = build_card_prompt("proj", ctx)
    assert "proj" in prompt
    assert "no recent commits" in prompt
    assert "no open PRs" in prompt
    assert "no previous command" in prompt


def test_prompt_requests_json_output():
    ctx = CardContext(project_name="proj")
    prompt = build_card_prompt("proj", ctx)
    assert "JSON" in prompt


# --- parse_card_response tests ---

def test_parse_valid_json():
    response = json.dumps({
        "dynamic": "PR #42 auth bug CI failing",
        "recommendation": "Fix PR #42 CI",
        "last_command_summary": "Fix auth bug",
    })
    result = parse_card_response(response)
    assert result["dynamic"] == "PR #42 auth bug CI failing"
    assert result["recommendation"] == "Fix PR #42 CI"
    assert result["last_command_summary"] == "Fix auth bug"


def test_parse_json_in_code_block():
    response = '''```json
{
  "dynamic": "All good",
  "recommendation": "Merge PR #15",
  "last_command_summary": "Update docs"
}
```'''
    result = parse_card_response(response)
    assert result["dynamic"] == "All good"
    assert result["recommendation"] == "Merge PR #15"


def test_parse_json_in_generic_code_block():
    response = '''```
{
  "dynamic": "Status here",
  "recommendation": "Do X",
  "last_command_summary": ""
}
```'''
    result = parse_card_response(response)
    assert result["dynamic"] == "Status here"
    assert result["recommendation"] == "Do X"


def test_parse_invalid_json():
    response = "This is not JSON at all"
    result = parse_card_response(response)
    assert result["dynamic"] != ""
    assert result["recommendation"] == ""
    assert result["last_command_summary"] == ""


def test_parse_partial_json():
    response = json.dumps({"dynamic": "Partial data"})
    result = parse_card_response(response)
    assert result["dynamic"] == "Partial data"
    assert result["recommendation"] == ""
    assert result["last_command_summary"] == ""


def test_parse_empty_response():
    result = parse_card_response("")
    assert result["dynamic"] == ""


# --- generate_fallback tests ---

def test_fallback_with_prs():
    ctx = CardContext(
        project_name="proj",
        open_prs=[{"number": 42, "title": "Fix auth bug", "ci_status": "failing"}],
    )
    result = generate_fallback(ctx)
    assert "42" in result["dynamic"]
    assert "CI" in result["recommendation"]


def test_fallback_with_commits():
    ctx = CardContext(
        project_name="proj",
        recent_commits=[{"sha": "abc", "message": "update docs"}],
    )
    result = generate_fallback(ctx)
    assert "update docs" in result["dynamic"]
    assert "可以开始新任务" in result["recommendation"]


def test_fallback_idle():
    ctx = CardContext(project_name="proj", days_since_last_activity=12)
    result = generate_fallback(ctx)
    assert "12" in result["dynamic"]
    assert "闲置" in result["dynamic"]


def test_fallback_failing_ci():
    ctx = CardContext(
        project_name="proj",
        open_prs=[
            {"number": 10, "title": "Good PR", "ci_status": "passing"},
            {"number": 42, "title": "Bad PR", "ci_status": "failing"},
        ],
    )
    result = generate_fallback(ctx)
    assert "42" in result["recommendation"]


def test_fallback_last_command_short():
    ctx = CardContext(project_name="proj", last_command="fix bug")
    result = generate_fallback(ctx)
    assert result["last_command_summary"] == "fix bug"


def test_fallback_last_command_long():
    long_cmd = "A" * 100
    ctx = CardContext(project_name="proj", last_command=long_cmd)
    result = generate_fallback(ctx)
    assert len(result["last_command_summary"]) == 40


def test_fallback_no_last_command():
    ctx = CardContext(project_name="proj")
    result = generate_fallback(ctx)
    assert result["last_command_summary"] == ""


# --- CardSummaryGenerator tests ---

@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield Database(db_path)


def test_generator_creation(db):
    gen = CardSummaryGenerator(db=db)
    assert gen.db is db


def test_generator_no_api_key():
    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.card_summary.API_KEY_FILE", Path("/nonexistent")):
            gen = CardSummaryGenerator(db=None)
            assert not gen.available


def test_generator_uses_fallback_without_key():
    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.card_summary.API_KEY_FILE", Path("/nonexistent")):
            gen = CardSummaryGenerator(db=None)
            ctx = CardContext(
                project_name="proj",
                open_prs=[{"number": 42, "title": "Fix bug", "ci_status": "passing"}],
            )
            result = gen.generate("proj", ctx)
            assert "42" in result["dynamic"]


def test_generator_memory_cache_hit():
    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.card_summary.API_KEY_FILE", Path("/nonexistent")):
            gen = CardSummaryGenerator(db=None)
            ctx = CardContext(project_name="proj", open_issues_count=3)

            result1 = gen.generate("proj", ctx)
            result2 = gen.generate("proj", ctx)
            assert result1 == result2
            assert "proj" in gen._cache


def test_generator_memory_cache_miss_on_change():
    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.card_summary.API_KEY_FILE", Path("/nonexistent")):
            gen = CardSummaryGenerator(db=None)

            ctx1 = CardContext(project_name="proj", open_issues_count=3)
            result1 = gen.generate("proj", ctx1)

            ctx2 = CardContext(project_name="proj", open_issues_count=10)
            result2 = gen.generate("proj", ctx2)

            # Should be different because input changed
            assert gen._cache["proj"]["data"] == result2


def test_generator_db_cache_hit(db):
    from pm.ai.card_summary import compute_card_hash
    ctx = CardContext(project_name="proj", open_issues_count=5)
    input_hash = compute_card_hash(ctx)

    data = {"dynamic": "cached", "recommendation": "do X", "last_command_summary": ""}
    db.save_summary("__card__proj", json.dumps(data), "", input_hash)

    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.card_summary.API_KEY_FILE", Path("/nonexistent")):
            gen = CardSummaryGenerator(db=db)
            result = gen.generate("proj", ctx)
            assert result["dynamic"] == "cached"


def test_generator_db_cache_miss_on_hash_change(db):
    db.save_summary("__card__proj", json.dumps({"dynamic": "old"}), "", "old_hash")

    with patch.dict("os.environ", {}, clear=True):
        with patch("pm.ai.card_summary.API_KEY_FILE", Path("/nonexistent")):
            gen = CardSummaryGenerator(db=db)
            ctx = CardContext(project_name="proj", open_issues_count=99)
            result = gen.generate("proj", ctx)
            # Should NOT be "old" since hash changed; fallback used
            assert result["dynamic"] != "old"


def test_generator_saves_to_db(db):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "dynamic": "saved to db",
        "recommendation": "do X",
        "last_command_summary": "",
    }))]
    mock_client.messages.create.return_value = mock_response

    gen = CardSummaryGenerator(db=db)
    gen._client = mock_client

    ctx = CardContext(project_name="proj", open_issues_count=5)
    gen.generate("proj", ctx)

    cached = db.get_summary("__card__proj")
    assert cached is not None
    assert cached.summary is not None


def test_generator_full_flow_with_mock_api(db):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "dynamic": "PR #42 CI failing",
        "recommendation": "Fix PR #42 CI",
        "last_command_summary": "Fix auth bug",
    }))]
    mock_client.messages.create.return_value = mock_response

    gen = CardSummaryGenerator(db=db)
    gen._client = mock_client

    ctx = CardContext(project_name="test-proj", open_issues_count=3)
    result = gen.generate("test-proj", ctx)

    assert result["dynamic"] == "PR #42 CI failing"
    assert result["recommendation"] == "Fix PR #42 CI"
    assert result["last_command_summary"] == "Fix auth bug"

    # Verify saved to cache
    cached = db.get_summary("__card__test-proj")
    assert cached is not None


def test_generator_handles_api_error(db):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API error")

    gen = CardSummaryGenerator(db=db)
    gen._client = mock_client

    ctx = CardContext(project_name="proj", open_issues_count=3)
    result = gen.generate("proj", ctx)
    # Should fall back to deterministic fallback
    assert isinstance(result["dynamic"], str)


def test_generator_api_call_uses_system_prompt(db):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "dynamic": "test",
        "recommendation": "do X",
        "last_command_summary": "",
    }))]
    mock_client.messages.create.return_value = mock_response

    gen = CardSummaryGenerator(db=db)
    gen._client = mock_client

    ctx = CardContext(project_name="proj", open_issues_count=1)
    gen.generate("proj", ctx)

    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs.kwargs.get("system") == CARD_SUMMARY_SYSTEM_PROMPT


# --- System prompt tests ---

def test_system_prompt_rejects_vague_language():
    assert "项目进展顺利" in CARD_SUMMARY_SYSTEM_PROMPT
    assert "太模糊" in CARD_SUMMARY_SYSTEM_PROMPT


def test_system_prompt_has_good_examples():
    assert "PR #42" in CARD_SUMMARY_SYSTEM_PROMPT
    assert "闲置" in CARD_SUMMARY_SYSTEM_PROMPT
    assert "merge" in CARD_SUMMARY_SYSTEM_PROMPT


def test_system_prompt_defines_three_fields():
    assert "dynamic" in CARD_SUMMARY_SYSTEM_PROMPT
    assert "recommendation" in CARD_SUMMARY_SYSTEM_PROMPT
    assert "last_command_summary" in CARD_SUMMARY_SYSTEM_PROMPT


# --- _format_time_ago tests ---

def test_format_time_ago_days():
    dt = datetime(2026, 3, 20)
    with patch("pm.ai.card_summary.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 25)
        mock_dt.min = datetime.min
        result = _format_time_ago(dt)
    assert "5d ago" in result


def test_format_time_ago_none():
    result = _format_time_ago(None)
    assert result == "unknown"


# --- _get_last_session tests ---

def test_get_last_session_no_db():
    result = _get_last_session("proj", None)
    assert result == {}


def test_get_last_session_no_sessions(db):
    result = _get_last_session("proj", db)
    assert result == {}


def test_get_last_session_with_data():
    mock_db = MagicMock()
    mock_session = MagicMock()
    mock_session.task_description = "Fix auth bug"
    mock_session.status = "completed"
    mock_session.updated_at = datetime(2026, 3, 25, 10, 0)
    mock_session.created_at = datetime(2026, 3, 25, 9, 0)
    mock_session.pr_number = 42
    mock_db.get_sessions_by_project.return_value = [mock_session]

    result = _get_last_session("proj", mock_db)
    assert result["command"] == "Fix auth bug"
    assert result["status"] == "completed"
    assert result["pr"] == 42


# --- _fetch_recent_commits tests (mock httpx) ---

def test_fetch_recent_commits_success():
    from pm.ai.card_summary import _fetch_recent_commits

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "sha": "abc1234567890",
            "commit": {
                "message": "fix auth bug\ndetails",
                "author": {"name": "dev", "date": "2026-03-25T10:00:00Z"},
            },
        },
        {
            "sha": "def4567890123",
            "commit": {
                "message": "update docs",
                "author": {"name": "dev", "date": "2026-03-24T10:00:00Z"},
            },
        },
    ]

    with patch("httpx.get", return_value=mock_response):
        commits = _fetch_recent_commits(["owner/repo"], "fake-token", limit=10)

    assert len(commits) == 2
    assert commits[0]["sha"] == "abc1234"
    assert commits[0]["message"] == "fix auth bug"


def test_fetch_recent_commits_failure():
    from pm.ai.card_summary import _fetch_recent_commits

    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("httpx.get", return_value=mock_response):
        commits = _fetch_recent_commits(["owner/repo"], "bad-token")

    assert commits == []


def test_fetch_recent_commits_exception():
    from pm.ai.card_summary import _fetch_recent_commits

    with patch("httpx.get", side_effect=Exception("network error")):
        commits = _fetch_recent_commits(["owner/repo"], "token")

    assert commits == []


# --- _fetch_open_prs tests ---

def test_fetch_open_prs_success():
    from pm.ai.card_summary import _fetch_open_prs

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"number": 42, "title": "Fix bug"},
        {"number": 43, "title": "Add feature"},
    ]

    with patch("httpx.get", return_value=mock_response):
        prs = _fetch_open_prs(["owner/repo"], "fake-token")

    assert len(prs) == 2
    assert prs[0]["number"] == 42


def test_fetch_open_prs_failure():
    from pm.ai.card_summary import _fetch_open_prs

    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("httpx.get", return_value=mock_response):
        prs = _fetch_open_prs(["owner/repo"], "token")

    assert prs == []


# --- collect_card_context tests ---

def test_collect_card_context_no_token():
    from pm.ai.card_summary import collect_card_context
    ctx = collect_card_context("proj", ["owner/repo"], "", db=None)
    assert ctx.project_name == "proj"
    assert ctx.recent_commits == []
    assert ctx.open_prs == []


def test_collect_card_context_with_mock_data():
    from pm.ai.card_summary import collect_card_context

    with patch("pm.ai.card_summary._fetch_recent_commits") as mock_commits, \
         patch("pm.ai.card_summary._fetch_open_prs") as mock_prs, \
         patch("pm.ai.card_summary._fetch_merged_prs") as mock_merged, \
         patch("pm.ai.card_summary._count_open_issues") as mock_issues:

        mock_commits.return_value = [{"sha": "abc", "message": "fix", "author": "dev", "date": "2026-03-25"}]
        mock_prs.return_value = [{"number": 42, "title": "Fix"}]
        mock_merged.return_value = []
        mock_issues.return_value = 3

        ctx = collect_card_context("proj", ["owner/repo"], "token", db=None)

    assert len(ctx.recent_commits) == 1
    assert len(ctx.open_prs) == 1
    assert ctx.open_issues_count == 3
