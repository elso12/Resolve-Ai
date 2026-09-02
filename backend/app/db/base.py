"""
ResolveAI — SQLAlchemy Declarative Base & Mixins

Provides the shared ``Base`` class for all ORM models and a
``TimestampMixin`` that automatically tracks creation / mutation
timestamps in UTC.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
)

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

# ── SQLite Compatibility Compilers for Postgres Types ─────────────────────────
@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
    return "TEXT"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
    return "TEXT"


# ── Naming conventions ───────────────────────────────────────────────────────
# Explicit naming conventions prevent ambiguous constraint names and make
# Alembic auto-generation deterministic.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Application-wide declarative base.

    All models inherit from this class to share metadata, naming
    conventions, and the table-name derivation strategy.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Automatically derive ``__tablename__`` from the class name
    # (e.g. ``UserAccount`` → ``user_account``).
    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """Convert CamelCase class name to snake_case table name."""
        name: str = cls.__name__
        chars: list[str] = []
        for i, ch in enumerate(name):
            if ch.isupper() and i > 0:
                chars.append("_")
            chars.append(ch.lower())
        return "".join(chars)


class TimestampMixin:
    """
    Mixin that adds ``created_at`` and ``updated_at`` columns.

    Both columns are timezone-aware and default to the database server's
    ``now()`` function so that timestamps remain consistent even when
    application servers have clock drift.
    """

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
