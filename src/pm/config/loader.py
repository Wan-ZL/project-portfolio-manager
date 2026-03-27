from __future__ import annotations

from pathlib import Path

import yaml

from pm.config.models import PMConfig

DEFAULT_CONFIG_PATH = Path.home() / ".ppm" / "config.yaml"

# Placeholder project name used in sample config
SAMPLE_PROJECT_NAME = "my-project"
SAMPLE_REPO_PREFIX = "your-username/"


def load_config(path: Path | None = None) -> PMConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return PMConfig()
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    if raw is None:
        return PMConfig()
    return PMConfig.model_validate(raw)


def save_config(config: PMConfig, path: Path | None = None) -> None:
    config_path = path or DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)


def ensure_config_dir() -> Path:
    config_dir = Path.home() / ".ppm"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def has_real_projects(config: PMConfig) -> bool:
    """Check if config has real projects (not just the sample placeholder)."""
    if not config.projects:
        return False
    project_names = list(config.projects.keys())
    if len(project_names) == 1 and project_names[0] == SAMPLE_PROJECT_NAME:
        project = config.projects[SAMPLE_PROJECT_NAME]
        if not project.repos or all(r.startswith(SAMPLE_REPO_PREFIX) for r in project.repos):
            return False
    return True


def generate_config_from_repos(
    repos: list[dict],
    account: str,
    path: Path | None = None,
) -> None:
    """Generate a config.yaml from discovered GitHub repos.

    Groups repos by owner/org, creating one project per owner.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Group repos by owner
    grouped: dict[str, list[dict]] = {}
    for repo in repos:
        owner = repo.get("owner", "unknown")
        grouped.setdefault(owner, []).append(repo)

    # Build YAML content with comments
    lines = [
        "# ============================================================",
        "# PPM Configuration - Auto-generated from GitHub repos",
        "# ============================================================",
        "# Re-generate anytime: ppm auth login",
        "# Edit freely: add instructions, assets, agent_config per project",
        "# ============================================================",
        "",
        "accounts:",
        f"  {account}:",
        "    token_source: credentials",
        "    default: true",
        "",
    ]

    if grouped:
        lines.append("projects:")
        for owner, owner_repos in grouped.items():
            project_name = owner
            lines.append(f"  {project_name}:")
            lines.append(f"    account: {account}")
            lines.append("    repos:")
            for repo in owner_repos:
                lines.append(f"      - {repo['full_name']}")
            lines.append("")
    else:
        lines.append("projects: {}")
        lines.append("")

    lines.extend([
        "defaults:",
        "  agent: claude-code",
        "  branch_prefix: ppm/",
        "  worktree_base: ~/.ppm/worktrees",
        "  poll_interval: 30s",
        "",
    ])

    config_path.write_text("\n".join(lines) + "\n")
