"""FR-KNW-002: chunk/embed/index pipeline storage. Same RLS shape as
knowledge_documents (0024): customer_id + workspace_id, FORCE ROW LEVEL
SECURITY, tenant_isolation policy. `vector` extension was already
created by migration 0001 (`CREATE EXTENSION IF NOT EXISTS vector`) but
never used until now.

EMBEDDING_DIMENSIONS=3072 is gemini-embedding-2's own output size,
verified against the real API and against this exact deployment's
pgvector 0.6.0 (which accepts vector columns well above this — the
2000-dimension figure sometimes quoted for pgvector is an ivfflat INDEX
limit, not a storage limit; no index is created here, a full scan is
fine at v1 scale, and FR-KNW-003's retrieval work can add one later if
needed).

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "knowledge_document_chunks"
EMBEDDING_DIMENSIONS = 3072


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
    )
    op.create_index(f"ix_{TABLE}_customer_id", TABLE, ["customer_id"])
    op.create_index(f"ix_{TABLE}_workspace_id", TABLE, ["workspace_id"])
    op.create_index(f"ix_{TABLE}_document_id", TABLE, ["document_id"])

    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {TABLE}
        USING (customer_id = current_setting('app.current_customer_id', true)::uuid)
        WITH CHECK (customer_id = current_setting('app.current_customer_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {TABLE}")
    op.drop_table(TABLE)
