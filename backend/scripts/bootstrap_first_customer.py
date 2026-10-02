"""One-off operator tool: give an already-logged-in (real Google OIDC)
User their first Customer + Workspace.

create_customer_with_owner is deliberately NOT exposed over the public API
(see application/customer_service.py's own module docstring — 2.3 lists
self-serve public signup as OUT OF SCOPE for v1). That is correct product
scope, but it leaves a real gap for the FIRST human on a fresh production
deployment: they can complete a real Google login (FR-AUTH-001) and land
on an honestly-empty `/v1/me/workspaces`, with no UI path to create one.
This script is the "operator provisions a Customer" half of that design
that 2.3 assumes exists — it has simply never had a concrete tool before,
because every prior Customer in this project's history was created by a
test fixture or `seed_e2e_demo.py`'s own throwaway User, never a real one.

Deliberately does NOT create a User — it looks one up by display_name
(the Google "name" claim, the only identifying field User carries; see
domain/identity/models.py's own docstring on why no email is stored) and
refuses to guess if that name is ambiguous (more than one match) or
already has a Customer (customer_ids_for_user is non-empty) — the latter
makes a second accidental run a clear, loud no-op rather than a silent
duplicate Customer.
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select

from doda.application.customer_service import create_customer_with_owner, customer_ids_for_user
from doda.application.workspace_service import add_workspace_member, create_workspace
from doda.db import async_session_factory, tenant_scoped_session
from doda.domain.identity.models import User


async def main(display_name: str, customer_name: str, workspace_name: str) -> int:
    async with async_session_factory() as db:
        matches = (await db.scalars(select(User).where(User.display_name == display_name))).all()

    if not matches:
        print(f"No User found with display_name={display_name!r}.", flush=True)
        return 1
    if len(matches) > 1:
        print(
            f"{len(matches)} Users share display_name={display_name!r} "
            f"(ids: {[str(u.id) for u in matches]}) — refusing to guess which one.",
            flush=True,
        )
        return 1

    user = matches[0]
    existing = await customer_ids_for_user(user.id)
    if existing:
        print(
            f"User {user.id} ({display_name!r}) already belongs to "
            f"{len(existing)} customer(s) ({[str(c) for c in existing]}) — "
            "refusing to provision a duplicate. Nothing changed.",
            flush=True,
        )
        return 1

    customer_id = uuid.uuid4()
    actor_id = f"user:{user.id}"
    async with tenant_scoped_session(customer_id) as db:
        _customer, _membership = await create_customer_with_owner(
            db, customer_id=customer_id, name=customer_name, owner_user_id=user.id, actor_id=actor_id
        )
        workspace = await create_workspace(
            db, customer_id=customer_id, name=workspace_name, actor_id=actor_id
        )
        await add_workspace_member(
            db,
            workspace=workspace,
            customer_membership=_membership,
            role="workspace_admin",
            actor_id=actor_id,
        )
        await db.commit()

    print(f"user_id={user.id}", flush=True)
    print(f"customer_id={customer_id}", flush=True)
    print(f"workspace_id={workspace.id}", flush=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--display-name", required=True, help="Exact Google account name, e.g. 'Khikmatullo Turaev'"
    )
    parser.add_argument("--customer-name", required=True)
    parser.add_argument("--workspace-name", required=True)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.display_name, args.customer_name, args.workspace_name)))
