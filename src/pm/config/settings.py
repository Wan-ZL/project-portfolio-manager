from __future__ import annotations

from pathlib import Path

import yaml


SETTINGS_PATH = Path.home() / ".ppm" / "settings.yaml"

DEFAULT_SETTINGS: dict = {
    "overlay": {
        "enabled": False,
        "show_count": 3,
        "position": "bottom-right",
        "opacity": 70,
    },
    "general": {
        "default_agent": "claude-code",
        "poll_interval": "5s",
    },
}


def load_settings(path: Path | None = None) -> dict:
    settings_path = path or SETTINGS_PATH
    if not settings_path.exists():
        return _deep_copy(DEFAULT_SETTINGS)
    try:
        with open(settings_path) as f:
            raw = yaml.safe_load(f)
        if raw is None:
            return _deep_copy(DEFAULT_SETTINGS)
        merged = _deep_copy(DEFAULT_SETTINGS)
        _deep_merge(merged, raw)
        return merged
    except Exception:
        return _deep_copy(DEFAULT_SETTINGS)


def save_settings(data: dict, path: Path | None = None) -> None:
    settings_path = path or SETTINGS_PATH
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def update_setting(section: str, key: str, value, path: Path | None = None) -> dict:
    settings = load_settings(path)
    if section not in settings:
        settings[section] = {}
    settings[section][key] = value
    save_settings(settings, path)
    return settings


def _deep_copy(d: dict) -> dict:
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _deep_copy(v)
        elif isinstance(v, list):
            result[k] = list(v)
        else:
            result[k] = v
    return result


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
