"""FR-KNW-007/FR-CTL-002: conversation deletion ("Working" memory —
"foydalanuvchi har bir memory yozuvini ko'radi va o'chira oladi"). The
original 0013 migration created `conversation_messages.conversation_id`'s
FK with no `ondelete` clause (Postgres default NO ACTION) — confirmed via
a direct `pg_constraint` query against this environment's own real
Postgres (`conversation_messages_conversation_id_fkey`, confdeltype 'a'),
not assumed from reading 0013's source alone. Left as-is, deleting a
`Conversation` row would simply fail with a foreign-key violation the
moment it had any messages — which every real conversation does, since a
message is written before the first provider call even begins
(`conversation_service.stream_message`'s own docstring, step 1).

Per the "migratsiya tarixini buzma" rule (never edit an existing
migration's history — the same discipline 0022 followed for
`notifications`'s CHECK constraint, 0030 for `knowledge_documents`), this
ALTERs the existing constraint via a new migration rather than touching
0013: drop it and recreate with `ondelete="CASCADE"`, so deleting a
Conversation deletes its Message children automatically at the DB level
— `application.conversation_service.delete_conversation` never needs to
delete Message rows itself, matching how
`knowledge_document_chunks.document_id` (0029) already cascades from its
own `Document` parent.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT = "conversation_messages_conversation_id_fkey"
TABLE = "conversation_messages"
REFERENT = "conversation_conversations"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, TABLE, type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT, TABLE, REFERENT, ["conversation_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, TABLE, type_="foreignkey")
    op.create_foreign_key(CONSTRAINT, TABLE, REFERENT, ["conversation_id"], ["id"])
