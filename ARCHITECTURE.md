# Project Portfolio Manager (pm) — Architecture Plan

## 1. Overview

An AI-powered multi-project portfolio manager CLI tool that gives you a "CTO assistant" view across all your repositories. Built as a beautiful TUI (Terminal UI) that wraps existing AI coding CLIs (Claude Code, Codex, etc.) without reinventing coding functionality.

**Core differentiator**: No existing tool combines multi-GitHub account + multi-repo project grouping + AI-generated natural language summaries in one unified interface.

## 2. Requirements

### Portfolio Layer (P1-P6)
| ID | Requirement | Description |
|---|---|---|
| P1 | Multi-GitHub Account | Connect multiple GitHub accounts (personal + company) simultaneously |
| P2 | Multi-repo Grouping | Multiple repos belong to one project (e.g., frontend + backend = one project) |
| P3 | AI Status Summary | AI generates natural language project status (not cold metrics, human-readable) |
| P4 | Cross-project PR Aggregation | All open PRs across all projects visible at a glance |
| P5 | AI Next-step Suggestions | AI suggests "what should you work on next" and "which project needs attention" |
| P6 | Opening Dashboard | See everything the moment you open the tool |

### Project Layer (J1-J4)
| ID | Requirement | Description |
|---|---|---|
| J1 | Per-project Instructions | Each project has custom instructions/notes |
| J2 | Per-project Assets | Support images and attachments (design mockups, etc.) |
| J3 | Project Detail View | Single project's issues, PRs, branches, recent commits |
| J4 | One-click AI Agent Activation | Select project, input task, spawn AI agent to work |

### Task Layer (T1-T6)
| ID | Requirement | Description |
|---|---|---|
| T1 | Invoke Existing CLI Tools | Call Claude Code CLI (`claude --prompt "..."`), Codex CLI, etc. directly |
| T2 | Worktree Support | Each agent works in isolated git worktree |
| T3 | YOLO Mode | Support `--dangerously-skip-permissions` and similar modes |
| T4 | Auto PR Creation | Agent creates PR automatically when done |
| T5 | Autonomous PR Fix Loop | Monitor PR review comments -> auto fix -> push -> repeat until clean |
| T6 | PR Review Status Tracking | Track unresolved comments, CI status, merge readiness |

### UI/UX (U1-U5)
| ID | Requirement | Description |
|---|---|---|
| U1 | Beautiful TUI | Like claude-squad -- panels, borders, colors, polished |
| U2 | Keyboard Navigation | Arrow keys, shortcuts, tab to switch panels |
| U3 | Mouse Support | If feasible (mouse wheel scroll at minimum) |
| U4 | Panel Layout | Left panel lists, right panel details, bottom input/status |
| U5 | Don't Reinvent | This is a management/orchestration layer, not a coding tool |

### Architecture Principles (A1-A4)
| ID | Principle | Description |
|---|---|---|
| A1 | CLI-first | Pure terminal app, no Electron/Web UI |
| A2 | Plugin-friendly | AI agents are pluggable (Claude Code today, Codex tomorrow) |
| A3 | Config-driven | YAML config for accounts, projects, repos |
| A4 | Local-first | Data stored locally, GitHub tokens stored locally |

## 3. Tech Stack

| Component | Technology | Reason |
|---|---|---|
| Language | **Python 3.12+** | CSS-based TUI layout, 35+ built-in widgets, fastest development speed, AI generates Python well |
| TUI Framework | **Textual 7.x** | CSS styling system, 35+ widgets, mouse support (pixel-level), web mode, validated by Toad (2.7K stars) and Kagan (48 stars) |
| TUI Rendering | **Rich 14.x** | Terminal rendering primitives underlying Textual |
| CLI Framework | **Click** | Clean Python CLI framework, used by Kagan |
| Database | **SQLite** (via SQLModel + SQLAlchemy) | Local state, validated by Kagan |
| DB Migrations | **Alembic** | Schema versioning |
| GitHub API | **PyGithub** or **ghapi** | REST API, multi-account support |
| GitHub CLI | **gh** (exec) | PR operations, CI checks, issue management |
| AI API | **anthropic** (Python SDK) | Claude API for summaries and suggestions |
| YAML | **PyYAML** + **pydantic** | Config file parsing + validation |
| Git | exec (system binary) | Worktree creation/cleanup |
| tmux | exec (system binary) | Agent session isolation |
| Process Mgmt | **asyncio** + **subprocess** | Async agent process management |
| Testing | **pytest** + Textual's **pilot** testing | TUI automated testing |
| Build | **hatchling** | Python package building |
| Package Manager | **uv** | Fast Python package management |

## 4. Reference Projects

Detailed architecture analysis was done on 10 projects. Key borrowings:

| Project | Stars | What We Borrow |
|---|---|---|
| **claude-squad** | 6.6K | TUI layout (30/70 split) concept, tmux session management pattern, keyboard nav design |
| **Vibe Kanban** | 24K | Executor trait pattern for agents, worktree lifecycle, SQLite schema design |
| **Composio Agent Orchestrator** | 5.5K | Reaction engine (polling state machine + retry + escalation), plugin slot system, PR comment fingerprinting |
| **mani** | 672 | YAML config schema for multi-repo, tag system + boolean expressions, SizedWaitGroup concurrency |
| **CCPM** | 7.8K | GitHub Issues integration pattern, Agent Skills standard, script-first-for-reads principle |
| **spec-kitty** | 971 | FSM lane transitions, acceptance-before-merge pattern, template-based multi-agent support |
| **DevHub** | 10K | Multi-token Octokit management, enhancement layer (local metadata on API data), rate-limit-aware polling |
| **Drift** | ~100 | Weighted health scoring, sparkline via git history, AI diagnosis prompt pattern |
| **Kagan** | 48 | **PRIMARY TUI reference** — Textual TUI kanban, ACP protocol, 14-agent registry pattern, worktree-per-task, TCSS styling |
| **Toad** | 2.7K | **Textual showcase** by Rich/Textual creator — AI coding TUI architecture, ACP integration, concurrent sessions |
| **cc-switch** | 34K | AppType enum dispatch, SSOT+sync pattern, per-app format translation |

## 5. Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    TUI Layer (Textual)                       │  (U1, U2, U3, U4)
│  Portfolio View │ Project View │ Task View │ Agent Terminal  │
├─────────────────────────────────────────────────────────────┤
│                   Command / Action Layer                     │
│  pm status │ pm work │ pm prs │ pm suggest │ pm config      │
├─────────────────┬───────────────────┬───────────────────────┤
│  GitHub Layer   │  Agent Layer      │  AI Summary Layer     │
│  (P1,P4)        │  (T1,T2,T3,T4)   │  (P3,P5)              │
│  Multi-account  │  tmux + worktree  │  Claude API           │
│  Octokit/token  │  Agent interface  │  Natural language     │
├─────────────────┴───────────────────┴───────────────────────┤
│                   Reaction Engine (T5, T6)                   │
│  Polling state machine │ PR monitor │ CI monitor │ Escalate │
├─────────────────────────────────────────────────────────────┤
│                    Data Layer                                │
│  SQLite (local state) │ Config (YAML) │ GitHub API (remote)  │
│  (A4)                 │ (A3)          │                      │
└─────────────────────────────────────────────────────────────┘
```

## 6. Config System (A3, P1, P2)

```yaml
# ~/.pm/config.yaml

accounts:                              # (P1) Multi-GitHub Account
  personal:
    token_env: GITHUB_TOKEN_PERSONAL   # Environment variable name, no plaintext
    default: true
  company:
    token_env: GITHUB_TOKEN_COMPANY

projects:                              # (P2) Multi-repo Grouping
  401k-website:
    account: personal
    repos:
      - owner/401k-frontend
      - owner/401k-backend
    local_path: ~/projects/401k
    instructions: |                    # (J1) Per-project Instructions
      Focus on mobile responsive design.
      Use Tailwind CSS for styling.
    assets:                            # (J2) Images/attachments
      - ~/designs/401k-mockup.png
    agent: claude-code                 # Default agent for this project
    agent_config:
      model: claude-sonnet-4-6
      permissions: dangerously-skip    # (T3) YOLO mode

  faa-project:
    account: company
    repos:
      - company-org/faa-main
      - company-org/faa-docs
    local_path: ~/projects/faa
    instructions: |
      Follow FAA compliance guidelines.

defaults:
  agent: claude-code
  branch_prefix: pm/
  worktree_base: ~/.pm/worktrees      # (T2) Worktree location
  poll_interval: 30s                   # Reaction engine polling

reactions:                             # (T5) PR fix loop config
  ci-failed:
    auto: true
    action: send-to-agent
    retries: 3
    message: "CI is failing. Run gh pr checks, fix issues, push."
  changes-requested:
    auto: true
    action: send-to-agent
    retries: 2
    escalate_after: 30m
  approved-and-green:
    auto: false
    action: notify
```

## 7. Database Schema (A4)

```sql
-- SQLite schema (~/.pm/pm.db)

CREATE TABLE repos (
    id TEXT PRIMARY KEY,          -- owner/repo
    account TEXT NOT NULL,
    project TEXT NOT NULL,
    default_branch TEXT,
    last_synced_at DATETIME
);

CREATE TABLE pull_requests (
    id INTEGER PRIMARY KEY,
    repo_id TEXT NOT NULL,
    number INTEGER NOT NULL,
    title TEXT,
    state TEXT,                    -- open, closed, merged
    author TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    ci_status TEXT,                -- passing, failing, pending
    review_status TEXT,            -- approved, changes_requested, pending
    unresolved_comments INTEGER DEFAULT 0,
    last_synced_at DATETIME,
    is_read BOOLEAN DEFAULT FALSE,
    is_starred BOOLEAN DEFAULT FALSE,
    needs_attention BOOLEAN DEFAULT FALSE
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    task_description TEXT,
    agent TEXT NOT NULL,
    tmux_session TEXT,
    worktree_path TEXT,
    branch TEXT,
    pr_number INTEGER,
    status TEXT,                   -- running, paused, completed, failed
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE project_summaries (
    project TEXT PRIMARY KEY,
    summary TEXT,
    suggestions TEXT,              -- JSON array
    generated_at DATETIME,
    input_hash TEXT
);

CREATE TABLE reaction_tracker (
    id TEXT PRIMARY KEY,           -- session_id:reaction_key
    reaction_key TEXT,
    attempt_count INTEGER DEFAULT 0,
    last_attempt_at DATETIME,
    escalated BOOLEAN DEFAULT FALSE
);
```

## 8. TUI Design — Three Views

### 8.1 Portfolio View (P6 — Opening Dashboard)

```
┌─ Portfolio Manager ─────────────────────────────────────────────┐
│                                                                  │
│  ┌─ Projects (30%) ──────┐  ┌─ Detail (70%) ───────────────┐   │
│  │                        │  │                               │   │
│  │  ▼ Personal Account    │  │  [Status] [PRs] [Sessions]   │   │
│  │    ● 401K Website  🟢  │  │                               │   │
│  │    ○ Side Project  🟡  │  │  401K Website                 │   │
│  │                        │  │  ─────────────────────────    │   │
│  │  ▼ Company Account     │  │  AI: Frontend development     │   │
│  │    ○ FAA Project   🔴  │  │  nearing completion. Backend  │   │
│  │    ○ Internal Tool 🟢  │  │  auth has a bug that needs    │   │
│  │                        │  │  fixing.                      │   │
│  │                        │  │                               │   │
│  │                        │  │  PRs: 5 open (2 need review)  │   │
│  │                        │  │  Sessions: 1 running          │   │
│  │                        │  │                               │   │
│  │                        │  │  Suggest: Fix auth bug first, │   │
│  │                        │  │  then do mobile responsive    │   │
│  │                        │  │                               │   │
│  └────────────────────────┘  └───────────────────────────────┘   │
│                                                                  │
│  [n] New Task  [w] Work  [r] Refresh  [s] Suggest  [?] Help    │
│  > _                                                             │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 Project View (J3 — Single Project Detail)

```
┌─ PM > 401K Website ─────────────────────────────────────────────┐
│                                                                  │
│  ┌─ Repos & PRs (35%) ──────┐  ┌─ Detail (65%) ────────────┐   │
│  │                            │  │                           │   │
│  │  📦 owner/401k-frontend    │  │  [Info] [Diff] [Terminal] │   │
│  │    PR #42 fix auth ⬤🔴CI  │  │                           │   │
│  │    PR #38 add mobile 🟢   │  │  PR #42: fix auth bug     │   │
│  │    PR #35 refactor 🟡     │  │  ─────────────────────    │   │
│  │                            │  │  Author: bot              │   │
│  │  📦 owner/401k-backend     │  │  CI: ❌ failing (2 checks)│   │
│  │    PR #12 api update 🟢   │  │  Review: changes_requested│   │
│  │    (no more open PRs)      │  │  Comments: 3 unresolved   │   │
│  │                            │  │                           │   │
│  │  ── Sessions ──            │  │  Latest comment:          │   │
│  │    🤖 fix-auth (running)   │  │  "Please handle the null  │   │
│  │    🤖 mobile-ui (paused)   │  │   case on line 42"        │   │
│  │                            │  │                           │   │
│  │  ── Issues (5 open) ──     │  │  Instructions:            │   │
│  │    #18 Login timeout       │  │  "Focus on mobile         │   │
│  │    #15 CSS broken on iOS   │  │   responsive design..."   │   │
│  │    #12 API rate limit      │  │                           │   │
│  └────────────────────────────┘  └───────────────────────────┘   │
│                                                                  │
│  [n] New Task  [a] Attach  [f] Fix PR  [m] Merge  [Esc] Back   │
│  > _                                                             │
└──────────────────────────────────────────────────────────────────┘
```

### 8.3 Task View (T1 — Agent Session)

```
┌─ PM > 401K Website > fix-auth-bug [running] ────────────────────┐
│                                                                  │
│  ┌─ Session Info (25%) ──┐  ┌─ Agent Terminal (75%) ─────────┐  │
│  │                        │  │                                 │  │
│  │  Task: fix auth bug    │  │  $ claude --prompt "Fix the     │  │
│  │  Agent: claude-code    │  │  auth bug in login flow..."     │  │
│  │  Model: sonnet-4-6     │  │                                 │  │
│  │  Branch: pm/fix-auth   │  │  ● Reading src/auth/login.ts   │  │
│  │  Worktree: ~/.pm/wt/.. │  │  ● Found null check missing    │  │
│  │  Started: 2min ago     │  │    on line 42                   │  │
│  │  Status: 🟢 active     │  │  ● Editing src/auth/login.ts   │  │
│  │                        │  │  ● Running tests...             │  │
│  │  ── PR Status ──       │  │    ✓ 23 passed                  │  │
│  │  PR: #42               │  │    ✗ 1 failed                   │  │
│  │  CI: 🔴 failing        │  │  ● Fixing test failure...       │  │
│  │  Review: pending       │  │  ● Running tests...             │  │
│  │  Comments: 0           │  │    ✓ 24 passed                  │  │
│  │                        │  │  ● Creating PR...               │  │
│  │  ── Reactions ──       │  │                                 │  │
│  │  ci-failed: 0/3 retry  │  │  > Waiting for input...         │  │
│  │  changes_req: 0/2      │  │                                 │  │
│  │                        │  │                                 │  │
│  └────────────────────────┘  └─────────────────────────────────┘  │
│                                                                  │
│  [Ctrl+Q] Detach  [p] Pause  [k] Kill  [r] Reprompt  [Esc] Back │
└──────────────────────────────────────────────────────────────────┘
```

### Navigation Flow

```
Portfolio View ──Enter──> Project View ──Enter/a──> Task View
     ↑                        ↑                        ↑
   [q] quit                [Esc] back               [Esc] back
                                                    [Ctrl+Q] detach only
```

## 9. Core Module Design

### 9.1 GitHub Integration (P1, P4, T6)

Reference: DevHub (multi-token, enhancement layer) + Composio (PR state machine)

```python
# Multi-account GitHub client (P1)
# Reference: DevHub (multi-token, enhancement layer) + Composio (PR state machine)

from github import Github
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class EnhancedPR:
    """Enhancement layer: local metadata on top of GitHub API data (T6)"""
    repo_id: str
    number: int
    title: str
    state: str                    # open, closed, merged
    author: str
    created_at: datetime
    updated_at: datetime
    ci_status: str = "pending"    # passing, failing, pending
    review_status: str = "pending"  # approved, changes_requested, pending
    unresolved_count: int = 0
    is_read: bool = False
    is_starred: bool = False
    needs_attention: bool = False

class GitHubManager:
    """Multi-account GitHub management (P1)"""

    def __init__(self, config: Config, db: Database):
        self.clients: dict[str, Github] = {}  # account_name -> client
        self.db = db
        for name, account in config.accounts.items():
            token = os.environ.get(account.token_env, "")
            self.clients[name] = Github(token)

    def client_for_project(self, project: str) -> Github:
        account = self.config.projects[project].account
        return self.clients[account]

    async def all_open_prs(self) -> list[EnhancedPR]:
        """Aggregate all open PRs across all projects (P4)"""
        prs = []
        for project in self.config.projects.values():
            client = self.client_for_project(project.name)
            for repo_name in project.repos:
                repo = client.get_repo(repo_name)
                for pr in repo.get_pulls(state="open"):
                    enhanced = self._enhance_pr(pr, project.name)
                    prs.append(enhanced)
        return prs
```

**Polling strategy** (reference: DevHub):
- Dynamic interval based on GitHub rate limit headers
- Foreground: 30s, background: 5min
- ETag/If-None-Match to minimize API usage
- Force refresh on user action

### 9.2 Agent Layer (T1, T2, T3, T4, A2)

Reference: claude-squad (tmux + PTY) + Composio (agent interface) + Kagan (registry)

```python
# Agent interface — pluggable AI CLIs (A2)
# Reference: Kagan (registry pattern) + Composio (agent interface)

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class LaunchOptions:
    prompt: str = ""
    work_dir: str = ""
    model: str = ""
    permissions: str = "default"  # dangerously-skip (T3) / default / auto-edit

class Agent(ABC):
    """Base agent interface (A2)"""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def launch_command(self, opts: LaunchOptions) -> list[str]: ...

    @abstractmethod
    def detect_activity(self, output: str) -> str: ...  # active/idle/exited

class ClaudeCodeAgent(Agent):
    """Claude Code CLI implementation (T1)"""

    def name(self) -> str:
        return "claude-code"

    def launch_command(self, opts: LaunchOptions) -> list[str]:
        cmd = ["claude"]
        if opts.prompt:
            cmd.extend(["--prompt", opts.prompt])
        if opts.permissions == "dangerously-skip":
            cmd.append("--dangerously-skip-permissions")  # (T3)
        if opts.model:
            cmd.extend(["--model", opts.model])
        return cmd

# Agent Registry (A2) — inspired by Kagan's AGENT_BACKENDS dict
AGENT_REGISTRY: dict[str, Agent] = {
    "claude-code": ClaudeCodeAgent(),
    "codex": CodexAgent(),
    "gemini": GeminiAgent(),
}
```

**Session lifecycle** (reference: claude-squad):
- Each session = 1 tmux session + 1 git worktree
- tmux capture-pane every 500ms for output monitoring
- Worktree path: `~/.pm/worktrees/{project}/{session_id}`
- Branch naming: `pm/{project}/{short_description}`

### 9.3 Reaction Engine (T5, T6)

Reference: Composio (polling state machine + reaction config + fingerprint change detection)

```python
# Reaction engine — polling state machine (T5)
# Reference: Composio (polling + retry + escalation + fingerprinting)

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ReactionTracker:
    attempt_count: int = 0
    last_attempt_at: datetime | None = None
    escalated: bool = False

class ReactionEngine:
    """Autonomous PR fix loop (T5, T6)"""

    def __init__(self, config: Config, sessions: SessionManager, github: GitHubManager):
        self.config = config
        self.sessions = sessions
        self.github = github
        self.trackers: dict[str, ReactionTracker] = {}  # session:key -> tracker

    async def poll(self):
        """Poll every 30s (configurable)"""
        for session in self.sessions.active_with_pr():
            new_state = await self._determine_state(session)
            if new_state != session.last_state:
                reaction = self.config.reactions.get(new_state)
                if not reaction:
                    continue
                tracker = self._get_tracker(session.id, new_state)
                if tracker.attempt_count >= reaction.retries:
                    await self._escalate(session, new_state)  # notify user
                else:
                    await self._execute_reaction(session, reaction)  # send to agent
                    tracker.attempt_count += 1

    def _comment_fingerprint(self, pr: EnhancedPR) -> str:
        """Fingerprint-based change detection (reference: Composio)"""
        ids = sorted(pr.unresolved_comment_ids())
        return ",".join(str(id) for id in ids)
```

### 9.4 AI Summary Layer (P3, P5)

Reference: Drift (AI diagnosis prompt pattern)

```python
# AI project summaries (P3, P5)
# Reference: Drift (AI diagnosis prompt pattern)

import anthropic
import hashlib
import json

class AISummaryGenerator:
    """Generate natural language project summaries using Claude API"""

    def __init__(self, config: Config, github: GitHubManager, db: Database):
        self.client = anthropic.Anthropic()
        self.github = github
        self.db = db
        self.config = config

    async def generate_summary(self, project: str) -> dict:
        # Collect input data
        input_data = {
            "recent_commits": await self.github.recent_commits(project, days=7),
            "open_prs": await self.github.open_prs(project),
            "open_issues": await self.github.open_issues(project),
            "ci_status": await self.github.ci_status(project),
            "instructions": self.config.projects[project].instructions,
        }

        # Hash-based caching — only regenerate when input changes
        input_hash = hashlib.sha256(json.dumps(input_data, default=str).encode()).hexdigest()[:16]
        cached = self.db.get_summary(project)
        if cached and cached.input_hash == input_hash:
            return cached

        # Call Claude API (P3)
        response = self.client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": self._build_prompt(project, input_data)}],
        )

        summary = self._parse_summary(response.content[0].text)
        self.db.save_summary(project, summary, input_hash)
        return summary
```

## 10. Project Structure

```
pm/
├── src/
│   └── pm/
│       ├── __init__.py
│       ├── cli.py                   # Click CLI entry point
│       ├── config/
│       │   ├── __init__.py
│       │   ├── loader.py            # YAML config loader (A3)
│       │   └── models.py            # Pydantic config models + validation
│       ├── github/
│       │   ├── __init__.py
│       │   ├── manager.py           # Multi-account GitHub client (P1)
│       │   ├── pr.py                # PR fetching + enhancement (P4, T6)
│       │   └── cache.py             # SQLite cache layer
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── base.py              # Agent ABC interface (A2)
│       │   ├── claude.py            # Claude Code implementation (T1)
│       │   ├── codex.py             # Codex implementation
│       │   ├── registry.py          # Agent registry
│       │   └── session.py           # tmux session management
│       ├── worktree/
│       │   ├── __init__.py
│       │   └── manager.py           # Git worktree lifecycle (T2)
│       ├── reaction/
│       │   ├── __init__.py
│       │   ├── engine.py            # Polling state machine (T5)
│       │   ├── tracker.py           # Retry/escalation tracking
│       │   └── actions.py           # send-to-agent, notify, auto-merge
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── summary.py           # AI project summaries (P3)
│       │   └── suggest.py           # AI next-step suggestions (P5)
│       ├── db/
│       │   ├── __init__.py
│       │   ├── database.py          # SQLite setup via SQLModel
│       │   └── models.py            # SQLModel data models
│       └── tui/
│           ├── __init__.py
│           ├── app.py               # Main Textual App (U1)
│           ├── screens/
│           │   ├── portfolio.py     # Portfolio View screen
│           │   ├── project.py       # Project View screen
│           │   └── task.py          # Task View screen (agent terminal)
│           ├── widgets/
│           │   ├── project_list.py  # Left panel widget
│           │   ├── detail_panel.py  # Right panel with tabs
│           │   ├── pr_list.py       # PR list widget
│           │   ├── session_list.py  # Agent sessions widget
│           │   └── status_bar.py    # Bottom status bar
│           ├── styles/
│           │   ├── app.tcss         # Main app styles
│           │   ├── portfolio.tcss   # Portfolio view styles
│           │   ├── project.tcss     # Project view styles
│           │   └── task.tcss        # Task view styles
│           └── keys.py              # Keyboard bindings (U2)
├── tests/
│   ├── test_tui/
│   │   ├── test_portfolio_view.py   # Textual pilot tests
│   │   ├── test_project_view.py
│   │   └── test_task_view.py
│   ├── test_github/
│   │   └── test_manager.py
│   ├── test_agent/
│   │   └── test_session.py
│   └── test_reaction/
│       └── test_engine.py
├── pyproject.toml                    # Project config (hatchling)
├── README.md
└── ARCHITECTURE.md
```

## 11. Key Dependencies

| Purpose | Library | Reference |
|---|---|---|
| TUI framework | textual >= 7.0, < 8.0 | Kagan, Toad |
| Terminal rendering | rich >= 14.0 | Textual dependency |
| CLI framework | click | Kagan |
| GitHub API | PyGithub | DevHub concept |
| GitHub CLI | gh (system binary) | Composio, CCPM |
| Database ORM | sqlmodel + sqlalchemy | Kagan |
| DB migrations | alembic | Kagan |
| AI API | anthropic >= 0.40 | Drift |
| Config validation | pydantic >= 2.0 | spec-kitty |
| YAML parsing | pyyaml | mani concept |
| Async | asyncio (stdlib) | Built-in |
| Process management | subprocess (stdlib) | Built-in |
| Testing | pytest + textual[dev] (pilot) | Textual built-in |
| E2E testing | playwright (optional) | Kagan |
| Build system | hatchling | Kagan |
| Package manager | uv | Modern Python standard |

## 12. Core Workflows

### Opening Dashboard (P6)
```
$ pm
→ Load config.yaml
→ Parallel fetch all accounts' GitHub data (P1)
→ Check SQLite cache, only fetch changed data
→ Background generate AI summaries (P3, hash-based caching)
→ Display Portfolio View (P6)
```

### Spawning AI Agent (T1, T2, T3, T4)
```
User presses [n] in TUI
→ Select project (or use currently selected)
→ Input task description: "fix the auth bug in login flow"
→ pm automatically:
   1. Create git worktree: ~/.pm/worktrees/401k/fix-auth-bug (T2)
   2. Create tmux session: pm_401k_fix-auth-bug
   3. Generate prompt (with project instructions + task description) (J1)
   4. Execute: claude --prompt "..." --dangerously-skip-permissions (T1, T3)
   5. Start polling session output (500ms)
   6. When agent completes, auto-create PR (T4)
   7. Reaction engine starts monitoring PR (T5)
```

### PR Fix Loop (T5, T6)
```
Reaction Engine polling (30s):
→ Detect PR #42 CI failing
→ Lookup reaction config: ci-failed → send-to-agent, retries: 3
→ Send via tmux send-keys: "CI is failing. Fix and push."
→ Agent fixes → pushes → CI reruns
→ If still failing → retry (max 3 times)
→ Exceeds retries → notify user: "PR #42 CI keeps failing, needs your attention"
→ If CI passes + approved → notify: "PR #42 ready to merge"
```

## 13. Implementation Phases

### Phase 1: Core Skeleton (可以看)
- [ ] Project scaffolding (uv init, hatchling + click setup, Textual app scaffold)
- [ ] Config YAML loader + validation (A3)
- [ ] Portfolio TUI skeleton — left panel project list + right panel (U1, U4)
- [ ] Multi-account GitHub data fetching (P1)
- [ ] PR aggregation display (P4)
- [ ] Keyboard navigation (U2)
- [ ] SQLite setup + migrations (A4)

### Phase 2: Agent Integration (可以干活)
- [ ] Agent interface + Claude Code implementation (T1, A2)
- [ ] tmux session management (T1)
- [ ] Worktree creation/cleanup (T2)
- [ ] Spawn agent from TUI input (J4)
- [ ] Session list + attach/detach
- [ ] Task View with live tmux capture
- [ ] YOLO mode support (T3)

### Phase 3: AI Enhancement (核心价值)
- [ ] AI project summary generation (P3)
- [ ] AI next-step suggestions (P5)
- [ ] Hash-based summary caching
- [ ] Opening dashboard with AI content (P6)

### Phase 4: Automation Loop (高级功能)
- [ ] Reaction engine — polling state machine (T5)
- [ ] CI status monitoring (T5)
- [ ] Review comment tracking + fingerprinting (T6)
- [ ] send-to-agent action via tmux (T5)
- [ ] Retry + escalation logic (T5)
- [ ] Auto-merge option (T5)

### Phase 5: Polish (完善)
- [ ] Per-project instructions display (J1)
- [ ] Per-project assets/images (J2)
- [ ] Project View detail (J3)
- [ ] More agent implementations — Codex, Gemini (A2)
- [ ] Full mouse support — click, scroll, hover (U3)
- [ ] Help overlay
- [ ] Error handling + edge cases
- [ ] PyPI publishing via hatchling + uv

## 14. Keyboard Shortcuts

### Portfolio View
| Key | Action |
|---|---|
| j/k or Up/Down | Navigate projects |
| Tab | Switch detail tabs (Status/PRs/Sessions) |
| Enter | Enter project detail |
| n | New task -> input prompt -> spawn agent |
| w | Quick work -> select project + input -> spawn |
| r | Force refresh all data |
| s | AI suggest next action |
| ? | Help overlay |
| q | Quit |

### Project View
| Key | Action |
|---|---|
| j/k or Up/Down | Navigate PRs/sessions/issues |
| Tab | Switch detail tabs (Info/Diff/Terminal) |
| Enter or a | Attach to selected session |
| n | New task for this project |
| f | Start PR fix loop for selected PR |
| m | Merge selected PR |
| Esc | Back to Portfolio View |

### Task View
| Key | Action |
|---|---|
| Ctrl+Q | Detach from session (agent keeps running) |
| p | Pause session |
| k | Kill session |
| r | Reprompt (send new instruction to agent) |
| Esc | Back to Project View |

---

*Generated: 2026-03-27*
*Updated: 2026-03-27 — Tech stack changed from Go + Bubble Tea to Python + Textual*
*Based on architecture analysis of 10 reference projects with 22 parallel research agents*
*Language decision informed by comparative analysis across Go, Python, TypeScript, and Rust TUI ecosystems*
