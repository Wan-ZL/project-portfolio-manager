from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


@click.group(invoke_without_command=True)
@click.option("--demo", is_flag=True, default=False, help="Launch in demo mode with mock data")
@click.pass_context
def main(ctx, demo):
    """PPM - AI-powered Project Portfolio Manager"""
    if ctx.invoked_subcommand is None:
        from pm.errors import setup_logging
        setup_logging()
        from pm.tui.app import run_app
        run_app(demo=demo)


@main.command()
def status():
    """Show portfolio status summary (no TUI)."""
    console = Console()
    console.print("\n[bold cyan]Portfolio Status[/bold cyan]\n")

    try:
        from pm.config.loader import load_config
        cfg = load_config()
    except Exception:
        cfg = None

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Project", style="bold")
    table.add_column("Account", style="dim")
    table.add_column("Repos", justify="right")
    table.add_column("Agent", justify="center")
    table.add_column("Status", justify="center")

    if cfg and cfg.projects:
        for name, project in cfg.projects.items():
            agent = project.agent or cfg.defaults.agent
            table.add_row(
                name,
                project.account,
                str(len(project.repos)),
                agent,
                "[green]\u25cf[/green]",
            )
    else:
        # Demo/sample data
        projects = [
            ("401K Website", "Personal", "2", "claude-code", "[green]\u25cf[/green]"),
            ("Side Project", "Personal", "1", "claude-code", "[yellow]\u25cf[/yellow]"),
            ("FAA Project", "Company", "2", "claude-code", "[red]\u25cf[/red]"),
            ("Internal Tool", "Company", "1", "claude-code", "[green]\u25cf[/green]"),
        ]
        for name, account, repos, agent, status_icon in projects:
            table.add_row(name, account, repos, agent, status_icon)

    console.print(table)
    console.print()


@main.command()
def prs():
    """List all open PRs across projects."""
    console = Console()
    console.print("\n[bold cyan]Open Pull Requests[/bold cyan]\n")

    try:
        from pm.config.loader import load_config
        cfg = load_config()
        if cfg.projects:
            console.print("[dim]Fetching PRs from GitHub...[/dim]")
            try:
                from pm.db.database import Database
                from pm.github.manager import GitHubManager
                db = Database()
                gh_mgr = GitHubManager(cfg, db)
                all_prs = gh_mgr.fetch_all_open_prs()
                if all_prs:
                    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
                    table.add_column("Repo", style="dim")
                    table.add_column("#", justify="right", style="bold")
                    table.add_column("Title")
                    table.add_column("CI", justify="center")
                    table.add_column("Review", justify="center")
                    table.add_column("Author", style="dim")
                    for pr in all_prs:
                        ci_icon = {"passing": "[green]\u2714[/green]", "failing": "[red]\u2718[/red]"}.get(
                            pr.ci_status, "[yellow]\u25cb[/yellow]"
                        )
                        review_icon = {"approved": "[green]\u2714[/green]",
                                       "changes_requested": "[yellow]\u270e[/yellow]"}.get(
                            pr.review_status, "[dim]\u2026[/dim]"
                        )
                        table.add_row(
                            pr.repo_id, str(pr.number), pr.title,
                            ci_icon, review_icon, pr.author,
                        )
                    console.print(table)
                else:
                    console.print("[dim]No open pull requests found.[/dim]")
                console.print()
                return
            except Exception as e:
                console.print(f"[yellow]Could not fetch live PR data: {e}[/yellow]")
    except Exception:
        pass

    # Fallback sample data
    console.print("[dim]Showing sample data (no config or GitHub connection)[/dim]\n")
    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Repo", style="dim")
    table.add_column("#", justify="right", style="bold")
    table.add_column("Title")
    table.add_column("CI", justify="center")
    table.add_column("Review", justify="center")
    sample = [
        ("owner/401k-frontend", "42", "Fix auth bug", "[red]\u2718[/red]", "[yellow]\u270e[/yellow]"),
        ("owner/401k-frontend", "38", "Mobile responsive", "[green]\u2714[/green]", "[green]\u2714[/green]"),
        ("company-org/faa-main", "89", "Compliance checks", "[red]\u2718[/red]", "[yellow]\u270e[/yellow]"),
    ]
    for repo, num, title, ci, review in sample:
        table.add_row(repo, num, title, ci, review)
    console.print(table)
    console.print()


@main.group(invoke_without_command=True)
@click.pass_context
def config(ctx):
    """Show or manage configuration."""
    if ctx.invoked_subcommand is None:
        _show_config()


def _show_config():
    console = Console()
    try:
        from pm.config.loader import load_config
        cfg = load_config()
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        console.print("[dim]Run `ppm config init` to create a sample config.[/dim]")
        return

    console.print("\n[bold cyan]PM Configuration[/bold cyan]\n")

    if cfg.accounts:
        console.print("[bold]Accounts:[/bold]")
        for name, account in cfg.accounts.items():
            default_marker = " [green](default)[/green]" if account.default else ""
            if account.token_source == "credentials":
                source_info = "source=credentials"
            elif account.token_env:
                source_info = f"token_env={account.token_env}"
            else:
                source_info = "no token configured"
            console.print(f"  {name}: {source_info}{default_marker}")
    else:
        console.print("[dim]No accounts configured[/dim]")

    console.print()

    if cfg.projects:
        console.print("[bold]Projects:[/bold]")
        for name, project in cfg.projects.items():
            console.print(f"  [bold]{name}[/bold] (account: {project.account})")
            for repo in project.repos:
                console.print(f"    - {repo}")
            if project.instructions:
                console.print(f"    [dim]Instructions: {project.instructions.strip()[:60]}...[/dim]")
            if project.assets:
                console.print(f"    [dim]Assets: {len(project.assets)} file(s)[/dim]")
    else:
        console.print("[dim]No projects configured[/dim]")

    console.print()

    console.print("[bold]Defaults:[/bold]")
    console.print(f"  Agent: {cfg.defaults.agent}")
    console.print(f"  Branch prefix: {cfg.defaults.branch_prefix}")
    console.print(f"  Worktree base: {cfg.defaults.worktree_base}")
    console.print(f"  Poll interval: {cfg.defaults.poll_interval}")
    console.print()


@config.command("init")
def config_init():
    """Create a sample config file at ~/.ppm/config.yaml."""
    from pathlib import Path
    console = Console()
    config_path = Path.home() / ".ppm" / "config.yaml"

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        console.print("[dim]Delete it first if you want to recreate.[/dim]")
        return

    sample = """\
# ============================================================
# PPM Configuration (项目 Portfolio 管理器)
# ============================================================
# 文档: https://github.com/user/project-portfolio-manager
#
# 快速开始:
#   1. 添加 GitHub accounts (下面配置 token)
#   2. 添加你的 projects (repos 分组)
#   3. 运行 `ppm` 启动 TUI dashboard
#
# 获取 GitHub Token 的两种方式:
#   方式 1 (推荐): 运行 `ppm auth login` 在浏览器中授权
#   方式 2 (手动): 访问 https://github.com/settings/tokens
#                  创建 token，勾选 repo 和 read:org 权限
#                  然后设置环境变量: export GITHUB_TOKEN=ghp_xxxxx
# ============================================================

accounts:
  # 个人 GitHub 账号
  personal:
    token_env: GITHUB_TOKEN       # 环境变量名 (不是 token 本身!)
    default: true                 # 默认使用这个账号

  # 如果有公司 GitHub 账号，取消注释:
  # company:
  #   token_env: GITHUB_TOKEN_COMPANY

projects:
  # 示例项目 — 替换成你自己的 repo
  my-project:
    account: personal             # 使用哪个 GitHub 账号
    repos:                        # 属于这个项目的 repo 列表
      - your-username/your-repo   # 格式: owner/repo-name
      # - your-username/your-repo-backend  # 多个 repo 可以归到同一个项目
    local_path: ~/projects/my-project  # 本地代码路径 (用于 worktree)
    instructions: |               # 项目特定的 AI 指令
      在这里写你对这个项目的备注和指令。
      AI 会参考这些信息来生成 summary 和建议。
    agent: claude-code            # 默认 AI agent (claude-code / codex / gemini)
    agent_config:
      model: claude-sonnet-4-6    # AI model
      permissions: default        # default / dangerously-skip (YOLO mode)

defaults:
  agent: claude-code
  branch_prefix: ppm/            # worktree branch 前缀
  worktree_base: ~/.ppm/worktrees
  poll_interval: 30s             # Reaction engine 轮询间隔

# PR 自动修复配置 (Reaction Engine)
reactions:
  ci-failed:                     # CI 失败时
    auto: true                   # 自动发消息给 agent
    action: send-to-agent
    retries: 3                   # 最多重试 3 次
    message: "CI is failing. Run gh pr checks, fix issues, push."
  changes-requested:             # Review 要求修改时
    auto: true
    action: send-to-agent
    retries: 2
    escalate_after: 30m          # 30分钟后升级通知你
  approved-and-green:            # PR 通过审核 + CI 通过
    auto: false                  # 不自动 merge，通知你
    action: notify
"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(sample)
    console.print(f"[green]Created sample config at {config_path}[/green]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Edit the config: [cyan]nano {config_path}[/cyan]")
    console.print("  2. Set up GitHub auth: [cyan]ppm auth login[/cyan] (推荐)")
    console.print("     或手动设置: [dim]export GITHUB_TOKEN=ghp_xxxxx[/dim]")
    console.print("  3. Launch dashboard: [cyan]ppm[/cyan]")


@main.group(invoke_without_command=True)
@click.pass_context
def auth(ctx):
    """Manage GitHub authentication."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@auth.command()
@click.option("--account", default="personal", help="Account name in config")
def login(account):
    """Connect a GitHub account.

    Tries these methods in order:
    1. If `gh` CLI is installed -> uses `gh auth token`
    2. Otherwise -> prompts for a Personal Access Token
    """
    from pm.auth.github_oauth import login_with_gh, login_with_manual_token

    if login_with_gh(account):
        return
    login_with_manual_token(account)


@auth.command()
def status():
    """Show current authentication status."""
    from pm.auth.credentials import load_credentials

    console = Console()
    creds = load_credentials()
    accounts = creds.get("accounts", {})
    if not accounts:
        console.print("[dim]No accounts configured. Run `ppm auth login` to connect.[/dim]")
        return

    console.print("\n[bold cyan]Authentication Status[/bold cyan]\n")
    for name, data in accounts.items():
        username = data.get("username", "unknown")
        has_token = bool(data.get("token"))
        token_preview = data.get("token", "")[:8] + "..." if has_token else "none"
        console.print(f'  {name}: user="{username}" token={token_preview}')
    console.print()


@main.command()
@click.argument("project")
@click.argument("task")
def work(project, task):
    """Spawn an agent to work on a task (no TUI needed).

    PROJECT is the project name from your config.
    TASK is the task description to send to the agent.
    """
    console = Console()

    from pm.errors import check_tmux_available
    if not check_tmux_available():
        console.print("[red]tmux is required for agent sessions. Install tmux first.[/red]")
        return

    try:
        from pm.config.loader import load_config
        cfg = load_config()
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return

    if project not in cfg.projects:
        console.print(f"[red]Project '{project}' not found in config.[/red]")
        console.print(f"[dim]Available: {', '.join(cfg.projects.keys()) or 'none'}[/dim]")
        return

    project_cfg = cfg.projects[project]
    agent_name = project_cfg.agent or cfg.defaults.agent

    console.print(f"[bold cyan]Spawning agent for {project}[/bold cyan]")
    console.print(f"  Task: {task}")
    console.print(f"  Agent: {agent_name}")

    try:
        from pm.db.database import Database
        from pm.agent.session import SessionManager, SessionCreateOptions
        db = Database()
        mgr = SessionManager(cfg, db)
        opts = SessionCreateOptions(
            project=project,
            task_description=task,
            agent_name=agent_name,
        )
        session = mgr.create_session(opts)
        console.print(f"  Session: [green]{session.id}[/green]")
        console.print(f"  tmux: {session.tmux_session}")
        if session.worktree_path:
            console.print(f"  Worktree: {session.worktree_path}")
        console.print(f"\n[dim]Attach with: tmux attach -t {session.tmux_session}[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to create session: {e}[/red]")


if __name__ == "__main__":
    main()
