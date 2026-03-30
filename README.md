# PM - Project Portfolio Manager

AI-powered multi-project portfolio manager CLI with a beautiful TUI. Manage multiple GitHub repositories across accounts, get AI-generated project summaries, and orchestrate AI coding agents — all from your terminal.

## Features

- **Multi-GitHub Account Support** — Connect personal and company GitHub accounts simultaneously
- **Multi-Repo Project Grouping** — Group multiple repos (frontend + backend) into one project
- **AI Status Summaries** — Claude-powered natural language project status summaries
- **Cross-Project PR Aggregation** — See all open PRs across all projects at a glance
- **AI Next-Step Suggestions** — AI suggests what you should work on next
- **Agent Orchestration** — Spawn Claude Code, Codex, or Gemini agents to work on tasks
- **tmux Session Management** — Each agent runs in an isolated tmux session with git worktree
- **Autonomous PR Fix Loop** — Agents automatically fix CI failures and address review comments
- **Beautiful TUI** — Keyboard-driven interface with mouse support, built with Textual

## Screenshots

<!-- Screenshots placeholder: add terminal screenshots here -->

## Installation

```bash
# With pipx (recommended)
pipx install pm-tool

# With uv
uv tool install pm-tool

# From source
git clone https://github.com/user/project-portfolio-manager.git
cd project-portfolio-manager
uv sync
uv run ppm --demo
```

## Quick Start

```bash
# Launch the TUI in demo mode (no config needed)
ppm --demo

# Create a sample config
ppm config init

# Edit the config
$EDITOR ~/.ppm/config.yaml

# Launch the TUI
ppm

# CLI commands (no TUI)
ppm status          # Print portfolio summary
ppm prs             # List all open PRs
ppm config          # Show current config
ppm work myproject "fix the auth bug"  # Spawn agent from CLI
```

## Configuration

Config file: `~/.pm/config.yaml`

```yaml
accounts:
  personal:
    token_env: GITHUB_TOKEN      # Environment variable name
    default: true
  company:
    token_env: GITHUB_TOKEN_COMPANY

projects:
  my-project:
    account: personal
    repos:
      - owner/frontend
      - owner/backend
    local_path: ~/projects/my-project
    instructions: |
      Project-specific instructions for AI agents.
    assets:
      - ~/designs/mockup.png
    agent: claude-code
    agent_config:
      model: claude-sonnet-4-6
      permissions: dangerously-skip    # YOLO mode

defaults:
  agent: claude-code
  branch_prefix: pm/
  worktree_base: ~/.pm/worktrees
  poll_interval: 30s

reactions:
  ci-failed:
    auto: true
    action: send-to-agent
    retries: 3
  changes-requested:
    auto: true
    action: send-to-agent
    retries: 2
    escalate_after: 30m
  approved-and-green:
    auto: false
    action: notify
```

## Keyboard Shortcuts

### Portfolio View
| Key | Action |
|-----|--------|
| `j` / `k` / Arrow keys | Navigate projects |
| `Tab` / `Shift+Tab` | Switch detail tabs |
| `Enter` | Open project detail |
| `n` | New task for selected project |
| `s` | AI suggest next action |
| `r` | Refresh all data |
| `?` | Help overlay |
| `q` | Quit |

### Project View
| Key | Action |
|-----|--------|
| `j` / `k` / Arrow keys | Navigate PRs and sessions |
| `Tab` / `Shift+Tab` | Switch detail tabs |
| `Enter` | Select / open item |
| `a` | Attach to session |
| `n` | New task |
| `f` | Fix selected PR |
| `m` | Merge selected PR |
| `o` | Open assets in system viewer |
| `Esc` | Back to Portfolio |

### Task View
| Key | Action |
|-----|--------|
| `p` | Pause / resume session |
| `k` | Kill session |
| `r` | Reprompt agent |
| `Ctrl+Q` | Detach (agent keeps running) |
| `Esc` | Back to Project View |

## Supported AI Agents

| Agent | CLI | Status |
|-------|-----|--------|
| Claude Code | `claude` | Supported |
| Codex | `codex` | Supported |
| Gemini | `gemini` | Supported |

## Requirements

- Python 3.12+
- `gh` CLI (for GitHub features) — https://cli.github.com/
- `tmux` (for agent sessions) — `brew install tmux`
- Anthropic API key (for AI summaries) — set `ANTHROPIC_API_KEY` env var

## License

MIT
