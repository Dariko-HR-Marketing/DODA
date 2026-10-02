"""FR-ACT-005's persistent retry promotion job.

An action never returns to READY on its own once record_transient_failure
has moved it to RETRYING — this job is what actually promotes a RETRYING
action whose backoff (next_retry_at) has elapsed back to READY and
re-enqueues its action.ready.v1 outbox message, via
application/action_service.promote_due_retries. No paging/alerting system
exists in this project yet (same honest statement as
verify_audit_chain_job.py/fire_due_reminders_job.py); this is meant to run
on a schedule (cron/systemd timer) frequently enough that a due retry
doesn't sit unpromoted for long — how frequently is an operational/hosting
decision (OD-005), not something this script picks for itself.

Discovers every customer to check via `customer_service.list_all_customer_ids`
— the same RLS-free UserCustomerIndex bootstrap table
verify_audit_chain_job.py/find_stuck_running_actions.py/
fire_due_reminders_job.py already use to discover which customers exist
at all, never for tenant content.
"""

import asyncio
import sys

from doda.application.action_service import promote_due_retries
from doda.application.customer_service import list_all_customer_ids
from doda.db import tenant_scoped_session


async def main() -> int:
    customer_ids = await list_all_customer_ids()

    total_promoted = 0
    for customer_id in customer_ids:
        async with tenant_scoped_session(customer_id) as db:
            promoted = await promote_due_retries(db)

        if promoted:
            total_promoted += len(promoted)
            print(f"customer={customer_id} promoted={len(promoted)}")

    print(f"total_promoted={total_promoted} customers_checked={len(customer_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
