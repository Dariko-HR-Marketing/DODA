"""NFR-SCL-001 verification ("Horizontal API va worker; stateless handler" —
"Ikki instansda test") — this requirement's own verification method had only
ever been applied to the two WORKERS (outbox_relay.py, telegram_relay.py;
see test_two_concurrent_relay_workers_never_double_publish_the_same_message
and test_two_concurrent_telegram_relay_workers_never_double_send_the_same_
action). The API half of the same requirement — the FastAPI app itself being
horizontally scalable, with no per-process in-memory state a load balancer's
instance routing could break — had never been measured at all.

This is the honest, scriptable equivalent for the API: it assumes two
independent `uvicorn doda.main:app` processes are already running (different
ports, same Postgres+Redis — exactly the topology a real horizontal
deployment would use), and proves that alternating requests between them
behave identically to talking to a single instance would. If the app secretly
kept session state, a request cache, or a sticky in-process map anywhere,
one of these checks would fail the moment the "wrong" instance is hit.

Requires two running backends and a session seeded via seed_e2e_demo.py (or
any real session/workspace) — same operating convention as
load_test_api.py and verify_audit_chain_job.py: a real, repeatable check
against real running infrastructure, run and read by a person.
"""

import argparse
import asyncio
import uuid

import httpx


async def _get(
    client: httpx.AsyncClient, base_url: str, path: str, headers: dict[str, str]
) -> httpx.Response:
    return await client.get(f"{base_url}{path}", headers=headers)


async def main(base_url_a: str, base_url_b: str, session_id: str, workspace_id: str) -> bool:
    headers = {"Authorization": f"Bearer {session_id}"}
    all_passed = True

    async with httpx.AsyncClient(timeout=30.0) as client:

        def check(name: str, condition: bool) -> None:
            nonlocal all_passed
            all_passed = all_passed and condition
            print(f"{'PASS' if condition else 'FAIL'}  {name}")

        # 1. The same bearer session is accepted by BOTH instances — proves
        # sessions are resolved from the shared DB on every request, never
        # pinned to whichever process first saw them (no sticky in-memory
        # session cache).
        resp_a = await _get(client, base_url_a, "/v1/me/workspaces", headers)
        resp_b = await _get(client, base_url_b, "/v1/me/workspaces", headers)
        check("same session accepted by instance A", resp_a.status_code == 200)
        check("same session accepted by instance B", resp_b.status_code == 200)
        check(
            "both instances agree on the workspace list",
            resp_a.status_code == 200 and resp_a.json() == resp_b.json(),
        )

        # 2. A write on A is immediately visible on B — proves there is no
        # per-process read cache that would make a load-balanced client see
        # stale data depending on which instance it happened to land on.
        title = f"two-instance check {uuid.uuid4()}"
        create_resp = await client.post(
            f"{base_url_a}/v1/workspaces/{workspace_id}/tasks",
            headers=headers,
            json={"title": title},
        )
        check("task created via instance A", create_resp.status_code == 200)
        task_id = create_resp.json()["id"] if create_resp.status_code == 200 else None

        list_resp = await _get(client, base_url_b, f"/v1/workspaces/{workspace_id}/tasks", headers)
        check(
            "task created on A is visible via instance B",
            list_resp.status_code == 200 and any(t["id"] == task_id for t in list_resp.json()),
        )

        # 3. A status change on B is immediately visible via A's own history
        # endpoint — the round trip in the other direction.
        if task_id is not None:
            status_resp = await client.post(
                f"{base_url_b}/v1/workspaces/{workspace_id}/tasks/{task_id}/status",
                headers=headers,
                json={"target_status": "IN_PROGRESS"},
            )
            check("task status changed via instance B", status_resp.status_code == 200)

            history_resp = await _get(
                client, base_url_a, f"/v1/workspaces/{workspace_id}/tasks/{task_id}/history", headers
            )
            check(
                "status change made on B is visible via instance A's history",
                history_resp.status_code == 200
                and any(h["to_status"] == "IN_PROGRESS" for h in history_resp.json()),
            )

        # 4. Revoking the session on A is honored by B on the very next
        # request — proves revocation isn't a per-process check (a
        # stale-instance deny would defeat FR-AUTH-005's own SLA the moment
        # a second instance exists).
        revoke_resp = await client.delete(f"{base_url_a}/v1/sessions/{session_id}", headers=headers)
        check("session revoked via instance A", revoke_resp.status_code == 204)

        post_revoke_resp = await _get(client, base_url_b, "/v1/me/workspaces", headers)
        check(
            "revoked session is rejected by instance B on the very next request",
            post_revoke_resp.status_code == 401,
        )

    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url-a", default="http://localhost:8001")
    parser.add_argument("--base-url-b", default="http://localhost:8002")
    parser.add_argument("--session-id", required=True, help="A live session id (see seed_e2e_demo.py)")
    parser.add_argument("--workspace-id", required=True, help="A workspace the session's user belongs to")
    args = parser.parse_args()

    ok = asyncio.run(main(args.base_url_a, args.base_url_b, args.session_id, args.workspace_id))
    raise SystemExit(0 if ok else 1)
