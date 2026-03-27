from __future__ import annotations

from pathlib import Path

import yaml

from pm.config.models import PMConfig

DEFAULT_CONFIG_PATH = Path.home() / ".ppm" / "config.yaml"


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
