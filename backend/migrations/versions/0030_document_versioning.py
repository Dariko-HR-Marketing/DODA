"""FR-KNW-009: document versioning — adds the self-referencing
`superseded_by_id` column `doda.domain.knowledge.models.Document`'s own
docstring already flagged as "not modeled yet". Nullable: NULL means
"this is the current version"; set means "a newer version replaced this
one" (pointing at that newer Document's id). `ondelete="SET NULL"` —
deleting the newer version (FR-KNW-005) makes the older one current
again rather than leaving a dangling pointer or cascading the delete
backwards through history, which nothing in this codebase ever intends.

This does not touch `knowledge_document_chunks` or its RLS policy —
retrieval exclusion of a superseded document's chunks (the other half
of FR-KNW-009's acceptance criterion) is enforced by `application.
knowledge_service.search_knowledge` joining `Document` and filtering on
this column, not by a schema-level constraint; a superseded document's
chunks are deliberately NOT deleted (it's still downloadable, just no
longer used as a retrieval source).

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "knowledge_documents"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "superseded_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{TABLE}.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(f"ix_{TABLE}_superseded_by_id", TABLE, ["superseded_by_id"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_superseded_by_id", table_name=TABLE)
    op.drop_column(TABLE, "superseded_by_id")
