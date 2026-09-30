"""Action domain — FR-ACT. Root aggregate: Action.

`status` is the authoritative state machine from TRD section 4.2. It must
never be assigned directly — always go through
`doda.domain.action.state_machine.transition()` via the application layer
(doda.application.action_service), so an illegal transition raises instead
of silently corrupting state, and every change gets audited.

`idempotency_key` is unique per (customer, workspace) (FR-ACT-004): a
duplicate propose call with the same key, in the same workspace, must
return the existing Action, never create a second one — see
doda.application.action_service.propose_action. Scoped by workspace, not
just customer: two different workspaces under the same customer choosing
the same caller-supplied key must never collide onto the same Action —
that would let a member of one workspace read another workspace's action
payload and pending approval nonce via the idempotent-replay path.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from doda.domain.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class RiskLevel(enum.StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"
    R5 = "R5"


# R0-R2: policy-only, no human approval (9.1). R3+: preview + approval required.
AUTO_APPROVED_RISK_LEVELS = frozenset({RiskLevel.R0, RiskLevel.R1, RiskLevel.R2})


class ActionStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    DENIED = "DENIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class Action(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "action_actions"
    __table_args__ = (
        UniqueConstraint(
            "customer_id", "workspace_id", "idempotency_key", name="uq_action_workspace_idempotency_key"
        ),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    actor_id: Mapped[str] = mapped_column(String(256))
    tool_name: Mapped[str] = mapped_column(String(128))
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, name="risk_level", native_enum=False, length=2)
    )
    payload: Mapped[dict] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(String(64))
    """sha256 of the canonical payload — see doda.application.hashing.hash_payload.
    Approval binds to this value (9.2); if payload changes, the hash changes
    and any prior approval becomes invalid by construction."""
    idempotency_key: Mapped[str] = mapped_column(String(256))
    status: Mapped[ActionStatus] = mapped_column(
        SAEnum(ActionStatus, name="action_status", native_enum=False, length=32),
        default=ActionStatus.DRAFT,
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    """FR-ACT-005's persistent (cross-cycle) retry budget — how many times
    this action has already gone through FAILED -> RETRYING -> READY.
    Distinct from telegram_relay's own in-process TELEGRAM_SEND_ATTEMPTS,
    which retries within a single connector call and never touches this
    column. See application/action_service.record_transient_failure."""
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    """Set when this action is RETRYING; NULL otherwise. Read by
    application/action_service.promote_due_retries (backend/scripts/
    promote_due_action_retries_job.py) to decide when a RETRYING action
    is due to become READY again."""
