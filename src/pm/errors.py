"""Error handling and logging setup for PM."""
from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

LOG_FILE = Path.home() / ".ppm" / "pm.log"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging to both file and stderr."""
    root_logger = logging.getLogger("pm")
    # Prevent duplicate handlers on repeated calls
    if root_logger.handlers:
        return

    log_dir = LOG_FILE.parent
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger.setLevel(level)

    # File handler
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)


def check_gh_available() -> bool:
    """Check if gh CLI is installed."""
    return shutil.which("gh") is not None


def check_tmux_available() -> bool:
    """Check if tmux is installed."""
    return shutil.which("tmux") is not None


def check_dependencies() -> dict[str, bool]:
    """Check availability of external dependencies.

    Returns a dict mapping dependency name to availability boolean.
    """
    return {
        "gh": check_gh_available(),
        "tmux": check_tmux_available(),
    }


def format_missing_deps(deps: dict[str, bool]) -> list[str]:
    """Format missing dependency warnings."""
    warnings = []
    if not deps.get("gh"):
        warnings.append(
            "gh CLI not found. GitHub features (PRs, issues) will be disabled. "
            "Install: https://cli.github.com/"
        )
    if not deps.get("tmux"):
        warnings.append(
            "tmux not found. Agent session features will be disabled. "
            "Install: brew install tmux (macOS) or apt install tmux (Linux)"
        )
    return warnings
