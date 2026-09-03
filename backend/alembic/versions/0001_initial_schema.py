"""initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-02 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Enable pgvector extension if on PostgreSQL
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # ── 1. Organization ──────────────────────────────────────────────────────────
    op.create_table(
        'organization',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_organization'))
    )
    op.create_index(op.f('ix_organization_created_at'), 'organization', ['created_at'], unique=False)
    op.create_index(op.f('ix_organization_slug'), 'organization', ['slug'], unique=True)

    # ── 2. User ──────────────────────────────────────────────────────────────────
    user_role_enum = sa.Enum('customer', 'agent', 'manager', 'admin', name='user_role')
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('hashed_password', sa.String(length=1024), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', user_role_enum, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_user_organization_id_organization'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user'))
    )
    op.create_index(op.f('ix_user_created_at'), 'user', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.create_index(op.f('ix_user_organization_id'), 'user', ['organization_id'], unique=False)
    op.create_index(op.f('ix_user_role'), 'user', ['role'], unique=False)

    # ── 3. Customer ──────────────────────────────────────────────────────────────
    op.create_table(
        'customer',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan', sa.String(length=50), server_default='Free', nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_customer_user_id_user'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_customer'))
    )
    op.create_index(op.f('ix_customer_created_at'), 'customer', ['created_at'], unique=False)
    op.create_index(op.f('ix_customer_user_id'), 'customer', ['user_id'], unique=True)

    # ── 4. Ticket ────────────────────────────────────────────────────────────────
    ticket_status_enum = sa.Enum('open', 'assigned', 'in_progress', 'waiting_for_customer', 'resolved', 'closed', name='ticket_status')
    ticket_priority_enum = sa.Enum('low', 'medium', 'high', 'critical', name='ticket_priority')
    ticket_category_enum = sa.Enum('billing', 'technical', 'account', 'general', name='ticket_category')

    op.create_table(
        'ticket',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticket_number', sa.String(length=30), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', ticket_status_enum, server_default='open', nullable=False),
        sa.Column('priority', ticket_priority_enum, server_default='medium', nullable=False),
        sa.Column('category', ticket_category_enum, server_default='general', nullable=False),
        sa.Column('ai_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('first_response_due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sla_first_response_breached', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('sla_resolution_breached', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('sla_breached', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('assigned_agent_id', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_agent_id'], ['user.id'], name=op.f('fk_ticket_assigned_agent_id_user'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], name=op.f('fk_ticket_customer_id_customer'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_ticket_organization_id_organization'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ticket'))
    )
    op.create_index(op.f('ix_ticket_assigned_agent_id'), 'ticket', ['assigned_agent_id'], unique=False)
    op.create_index(op.f('ix_ticket_category'), 'ticket', ['category'], unique=False)
    op.create_index(op.f('ix_ticket_created_at'), 'ticket', ['created_at'], unique=False)
    op.create_index(op.f('ix_ticket_customer_id'), 'ticket', ['customer_id'], unique=False)
    op.create_index(op.f('ix_ticket_first_response_due_at'), 'ticket', ['first_response_due_at'], unique=False)
    op.create_index(op.f('ix_ticket_organization_id'), 'ticket', ['organization_id'], unique=False)
    op.create_index(op.f('ix_ticket_priority'), 'ticket', ['priority'], unique=False)
    op.create_index(op.f('ix_ticket_resolution_due_at'), 'ticket', ['resolution_due_at'], unique=False)
    op.create_index(op.f('ix_ticket_sla_breached'), 'ticket', ['sla_breached'], unique=False)
    op.create_index(op.f('ix_ticket_sla_first_response_breached'), 'ticket', ['sla_first_response_breached'], unique=False)
    op.create_index(op.f('ix_ticket_sla_resolution_breached'), 'ticket', ['sla_resolution_breached'], unique=False)
    op.create_index(op.f('ix_ticket_status'), 'ticket', ['status'], unique=False)
    op.create_index(op.f('ix_ticket_ticket_number'), 'ticket', ['ticket_number'], unique=True)

    # ── 5. TicketMessage ─────────────────────────────────────────────────────────
    op.create_table(
        'ticket_message',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_internal', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['sender_id'], ['user.id'], name=op.f('fk_ticket_message_sender_id_user'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ticket_id'], ['ticket.id'], name=op.f('fk_ticket_message_ticket_id_ticket'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ticket_message'))
    )
    op.create_index(op.f('ix_ticket_message_created_at'), 'ticket_message', ['created_at'], unique=False)
    op.create_index(op.f('ix_ticket_message_sender_id'), 'ticket_message', ['sender_id'], unique=False)
    op.create_index(op.f('ix_ticket_message_ticket_id'), 'ticket_message', ['ticket_id'], unique=False)

    # ── 6. KnowledgeArticle ──────────────────────────────────────────────────────
    op.create_table(
        'knowledge_article',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=100), server_default='General', nullable=False),
        sa.Column('is_published', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_knowledge_article_organization_id_organization'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_article'))
    )
    op.create_index(op.f('ix_knowledge_article_category'), 'knowledge_article', ['category'], unique=False)
    op.create_index(op.f('ix_knowledge_article_created_at'), 'knowledge_article', ['created_at'], unique=False)
    op.create_index(op.f('ix_knowledge_article_is_published'), 'knowledge_article', ['is_published'], unique=False)
    op.create_index(op.f('ix_knowledge_article_organization_id'), 'knowledge_article', ['organization_id'], unique=False)
    op.create_index(op.f('ix_knowledge_article_slug'), 'knowledge_article', ['slug'], unique=True)
    op.create_index('ix_knowledge_article_search_vector', 'knowledge_article', ['search_vector'], postgresql_using='gin')

    # ── 7. ActionProposal ────────────────────────────────────────────────────────
    action_status_enum = sa.Enum('pending_approval', 'approved', 'rejected', 'executed', name='action_status')
    action_risk_level_enum = sa.Enum('low', 'high', name='action_risk_level')

    op.create_table(
        'action_proposal',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('tool_name', sa.String(length=100), nullable=False),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('estimated_cost', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('status', action_status_enum, server_default='pending_approval', nullable=False),
        sa.Column('risk_level', action_risk_level_enum, server_default='high', nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['ticket.id'], name=op.f('fk_action_proposal_ticket_id_ticket'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_action_proposal'))
    )
    op.create_index(op.f('ix_action_proposal_created_at'), 'action_proposal', ['created_at'], unique=False)
    op.create_index(op.f('ix_action_proposal_status'), 'action_proposal', ['status'], unique=False)
    op.create_index(op.f('ix_action_proposal_ticket_id'), 'action_proposal', ['ticket_id'], unique=False)
    op.create_index(op.f('ix_action_proposal_tool_name'), 'action_proposal', ['tool_name'], unique=False)

    # ── 8. AIInteraction ─────────────────────────────────────────────────────────
    op.create_table(
        'ai_interaction',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('interaction_type', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), server_default='gpt-3.5-turbo', nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('completion_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('estimated_cost_usd', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('latency_ms', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('user_feedback', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_ai_interaction_organization_id_organization'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ticket_id'], ['ticket.id'], name=op.f('fk_ai_interaction_ticket_id_ticket'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_interaction'))
    )
    op.create_index(op.f('ix_ai_interaction_created_at'), 'ai_interaction', ['created_at'], unique=False)
    op.create_index(op.f('ix_ai_interaction_interaction_type'), 'ai_interaction', ['interaction_type'], unique=False)
    op.create_index(op.f('ix_ai_interaction_organization_id'), 'ai_interaction', ['organization_id'], unique=False)
    op.create_index(op.f('ix_ai_interaction_ticket_id'), 'ai_interaction', ['ticket_id'], unique=False)
    op.create_index(op.f('ix_ai_interaction_user_feedback'), 'ai_interaction', ['user_feedback'], unique=False)

    # ── 9. AutomationRule ────────────────────────────────────────────────────────
    op.create_table(
        'automation_rule',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('event_trigger', sa.String(length=50), nullable=False),
        sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('actions', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_automation_rule_organization_id_organization'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_automation_rule'))
    )
    op.create_index(op.f('ix_automation_rule_created_at'), 'automation_rule', ['created_at'], unique=False)
    op.create_index(op.f('ix_automation_rule_event_trigger'), 'automation_rule', ['event_trigger'], unique=False)
    op.create_index(op.f('ix_automation_rule_organization_id'), 'automation_rule', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_table('automation_rule')
    op.drop_table('ai_interaction')
    op.drop_table('action_proposal')
    op.drop_table('knowledge_article')
    op.drop_table('ticket_message')
    op.drop_table('ticket')
    op.drop_table('customer')
    op.drop_table('user')
    op.drop_table('organization')
