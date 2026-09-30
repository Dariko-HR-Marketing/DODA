"""FR-ACT-005's persistent half: closing telegram_relay.py's own
documented gap ("no cross-cycle circuit breaker, no use of the domain's
FAILED -> RETRYING -> READY chain") by giving Action a bounded,
persistent retry budget instead of only the connector's in-process
TELEGRAM_SEND_ATTEMPTS.

`retry_count` (NOT NULL, default 0 so every existing row backfills
cleanly) and `next_retry_at` (nullable — NULL except while an action is
RETRYING) are read/written by application/action_service.
record_transient_failure/promote_due_retries, not by any connector
directly.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "action_actions",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "action_actions",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("action_actions", "next_retry_at")
    op.drop_column("action_actions", "retry_count")
