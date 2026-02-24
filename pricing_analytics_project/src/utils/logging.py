"""Lightweight logging utilities and step progress helpers for pipeline scripts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


def _ts() -> str:
    """Handle ts."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_info(message: str) -> None:
    """Log info."""
    print(f"[{_ts()}] INFO  {message}")


def log_warn(message: str) -> None:
    """Log warn."""
    print(f"[{_ts()}] WARN  {message}")


def log_error(message: str) -> None:
    """Log error."""
    print(f"[{_ts()}] ERROR {message}")


@dataclass
class StepLogger:
    total_steps: int
    current_step: int = 0
    task_name: Optional[str] = None

    def step(self, message: str) -> None:
        """Print step progress messages."""
        self.current_step += 1
        label = f"[{self.current_step}/{self.total_steps}]"
        prefix = f"{self.task_name} " if self.task_name else ""
        log_info(f"{prefix}{label} {message}")
