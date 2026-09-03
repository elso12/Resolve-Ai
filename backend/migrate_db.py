"""
ResolveAI — Database Migration Runner

Programmatically executes Alembic database migrations up to head.
Supports both PostgreSQL (production / staging / CI) and SQLite (local dev).
"""

from __future__ import annotations

import os
from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def run_migrations(target_revision: str = "head") -> None:
    """
    Execute Alembic migrations programmatically up to the specified target revision.

    Args:
        target_revision: Target revision string (default: "head").
    """
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(backend_dir, "alembic.ini")

    if not os.path.exists(ini_path):
        raise FileNotFoundError(f"Alembic configuration file not found at: {ini_path}")

    alembic_cfg = Config(ini_path)

    # Inject application database URL into the Alembic configuration
    db_url = str(settings.DATABASE_URL)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    masked_target = db_url.split("@")[-1] if "@" in db_url else db_url
    logger.info("migration_starting", target_revision=target_revision, database=masked_target)

    try:
        command.upgrade(alembic_cfg, target_revision)
        logger.info("migration_success", target_revision=target_revision)
    except Exception as exc:
        logger.error("migration_failed", error=str(exc))
        raise


if __name__ == "__main__":
    run_migrations()
