"""resize embeddings for local bge-small model; ivfflat -> hnsw

Revision ID: 002
Revises: 001
Create Date: 2026-10-02

The original column was sized for 1536-dim OpenAI embeddings but nothing ever
wrote to it. Embeddings now come from BAAI/bge-small-en-v1.5 (384 dims) run
locally via fastembed.

ivfflat is replaced by HNSW: ivfflat builds its clusters from the rows present
at CREATE INDEX time, and this index was created on an empty table, so its
lists were meaningless. HNSW needs no training data and has better recall at
this scale.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embeddings_vector")
    op.execute("DELETE FROM embeddings")
    op.execute("ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(384) USING NULL")
    op.execute(
        "CREATE INDEX ix_embeddings_hnsw ON embeddings USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_embeddings_doc_chunk ON embeddings (document_id, chunk_index)"
    )
    # Every document needs (re)indexing with the new model; the API backfills
    # anything with embedded = false on startup.
    op.execute("UPDATE documents SET embedded = false")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_embeddings_doc_chunk")
    op.execute("DROP INDEX IF EXISTS ix_embeddings_hnsw")
    op.execute("DELETE FROM embeddings")
    op.execute("ALTER TABLE embeddings ALTER COLUMN embedding TYPE vector(1536) USING NULL")
    op.execute(
        "CREATE INDEX ix_embeddings_vector ON embeddings "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.execute("UPDATE documents SET embedded = false")
