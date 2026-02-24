"""Configuration helpers for loading environment variables and project parameter files."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_params(path: str = "src/config/params.yaml") -> dict:
    """Load params."""
    params_path = Path(path)
    if not params_path.exists():
        raise FileNotFoundError(f"Missing params file: {params_path}")
    with params_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
