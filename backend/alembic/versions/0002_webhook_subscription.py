"""webhook_subscription

Revision ID: 0002_webhook_subscription
Revises: 0001_initial_schema
Create Date: 2026-09-03 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_webhook_subscription"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_col = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()

    op.create_table(
        "webhook_subscription",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("target_url", sa.String(length=1024), nullable=False),
        sa.Column("secret_key", sa.String(length=255), nullable=False),
        sa.Column("events", json_col, server_default="[]", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_webhook_subscription_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_subscription")),
    )
    op.create_index(
        op.f("ix_webhook_subscription_organization_id"),
        "webhook_subscription",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_subscription_created_at"),
        "webhook_subscription",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("webhook_subscription")
