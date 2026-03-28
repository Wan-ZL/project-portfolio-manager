from __future__ import annotations

import click
from rich.console import Console
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


@main.command()
def overlay():
    """Launch the desktop overlay."""
    click.echo("Coming soon")


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
