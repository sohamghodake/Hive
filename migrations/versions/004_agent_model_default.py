"""drop the stale server default on agents.model

Revision ID: 004
Revises: 003
Create Date: 2026-10-28

Migration 001 defaulted agents.model to 'claude-sonnet-4-20250514', a model the
Groq client cannot call. The application always sets the model (from LLM_MODEL
via api.config), so the database no longer carries a second, divergent default.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("agents", "model", server_default=None)


def downgrade() -> None:
    op.alter_column("agents", "model", server_default="claude-sonnet-4-20250514")
