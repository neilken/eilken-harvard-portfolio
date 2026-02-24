"""Database connection and SQL execution helpers for PostgreSQL access."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def load_env() -> None:
    """Load env."""
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)


def get_db_config(admin: bool = False) -> dict[str, str]:
    """Get db config."""
    load_env()
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "db": os.getenv("POSTGRES_DB", "pricing"),
        "user": os.getenv("POSTGRES_ADMIN_USER" if admin else "POSTGRES_USER", "postgres" if admin else "pricing_app"),
        "password": os.getenv(
            "POSTGRES_ADMIN_PASSWORD" if admin else "POSTGRES_PASSWORD",
            "postgres_pw" if admin else "pricing_app_pw",
        ),
    }


def sqlalchemy_url(admin: bool = False) -> str:
    """Handle sqlalchemy url."""
    cfg = get_db_config(admin=admin)
    return f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['db']}"


def get_engine(admin: bool = False) -> Engine:
    """Get engine."""
    return create_engine(sqlalchemy_url(admin=admin), future=True)
