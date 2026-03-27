from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class ActivityState(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    WAITING_INPUT = "waiting_input"
    EXITED = "exited"


@dataclass
class LaunchOptions:
    prompt: str = ""
    work_dir: str = ""
    model: str = ""
    permissions: str = "default"  # dangerously-skip / default / auto-edit


class Agent(ABC):
    """Base agent interface (A2) — pluggable AI CLI agents"""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def launch_command(self, opts: LaunchOptions) -> list[str]: ...

    @abstractmethod
    def detect_activity(self, output: str) -> ActivityState: ...

    @abstractmethod
    def supports_worktree(self) -> bool: ...
