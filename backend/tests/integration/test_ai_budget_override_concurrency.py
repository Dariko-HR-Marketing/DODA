"""Proves set_customer_ai_budget_override survives two concurrent calls for
a customer with NO override row yet — e.g. a double-click on the customer
page's "Saqlash" button, or two admins setting limits at the same moment.

Same TOCTOU shape as the kill-switch engage and notification-preference
races already fixed elsewhere in this codebase: `session.get(...)` sees
None, so both callers try to INSERT, and the loser's unique-PK violation
must be caught and converted into an update rather than reaching the
caller as a raw IntegrityError. This is "last write wins" semantics (like
notification preference, not kill switch) — each caller wants ITS OWN
soft/hard cap applied, not a shared "ensure an override exists" outcome.
"""

import asyncio
import uuid

from sqlalchemy import select

from doda.application.ai_budget_service import set_customer_ai_budget_override
from doda.db import tenant_scoped_session
from doda.domain.ai_usage.models import CustomerAIBudgetOverride
from tests.integration.conftest import commit_and_return, two_racing_sessions


async def test_two_concurrent_first_time_overrides_for_the_same_customer_both_succeed(
    db_available: bool,
) -> None:
    customer_id = uuid.uuid4()

    cm1, session1, cm2, session2 = await two_racing_sessions(customer_id)

    def set_override(session, soft_cap_usd, hard_cap_usd):
        return set_customer_ai_budget_override(
            session,
            customer_id=customer_id,
            actor_id="user:racer",
            soft_cap_usd=soft_cap_usd,
            hard_cap_usd=hard_cap_usd,
        )

    # Neither call raises — no IntegrityError reaches the caller.
    overrides = await asyncio.gather(
        commit_and_return(cm1, set_override(session1, 5.0, 10.0)),
        commit_and_return(cm2, set_override(session2, 15.0, 30.0)),
    )
    reported = [(o.soft_cap_cents, o.hard_cap_cents) for o in overrides]
    assert reported == [(500, 1000), (1500, 3000)]  # each call reports its own intended values

    async with tenant_scoped_session(customer_id) as session:
        rows = (
            (
                await session.execute(
                    select(CustomerAIBudgetOverride).where(
                        CustomerAIBudgetOverride.customer_id == customer_id
                    )
                )
            )
            .scalars()
            .all()
        )

    # Exactly one row — the customer_id primary key's intent — not two.
    assert len(rows) == 1
