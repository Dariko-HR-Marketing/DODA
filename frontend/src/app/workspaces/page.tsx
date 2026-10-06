"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ApiError,
  listMyCustomers,
  listMyWorkspaces,
  revokeSession,
  type MyCustomerOut,
  type MyWorkspaceOut,
} from "@/lib/api";
import { clearStoredSessionId } from "@/lib/session";
import { useSession } from "@/lib/useSession";
import { Badge, Card, EmptyState, ErrorBanner, PageTitle, SectionHeading } from "@/components/ui";

export default function WorkspacesPage() {
  const router = useRouter();
  const sessionId = useSession();
  const [workspaces, setWorkspaces] = useState<MyWorkspaceOut[] | null>(null);
  const [customers, setCustomers] = useState<MyCustomerOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (sessionId === null) return;
    listMyWorkspaces(sessionId)
      .then(setWorkspaces)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Yuklab bo'lmadi."));
    // Customer-scoped access is listed separately on purpose: a customer with
    // no workspaces, or a member who holds no workspace role at all (an
    // auditor — read-only by design), produces no row above, yet the customer
    // page is exactly where their access lives (audit view, notification
    // preferences, kill switch, archived workspaces).
    listMyCustomers(sessionId)
      .then(setCustomers)
      .catch(() => setCustomers([]));
  }, [sessionId]);

  async function logOut() {
    // "Chiqish" must actually revoke the session server-side (FR-AUTH-005),
    // not just forget it client-side — otherwise the raw session UUID
    // (Authorization: Bearer <id>) still works via direct API calls until
    // its natural idle/absolute timeout, even after the user believes
    // they've logged out. Clear local storage regardless of whether the
    // revoke call succeeds (e.g. offline) — the user must never be stuck
    // unable to leave the logged-in screen because of a network error.
    if (sessionId !== null) {
      await revokeSession(sessionId, sessionId).catch(() => {});
    }
    clearStoredSessionId();
    router.push("/login");
  }

  if (sessionId === null) return null;

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 space-y-8 p-6">
      <div className="flex items-center justify-between">
        <PageTitle>Mening workspace&apos;larim</PageTitle>
        <div className="flex items-center gap-4">
          <Link
            href="/sessions"
            className="text-sm font-medium text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
          >
            Sessiyalar
          </Link>
          <button
            onClick={logOut}
            className="text-sm font-medium text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
          >
            Chiqish
          </button>
        </div>
      </div>

      {error && <ErrorBanner>{error}</ErrorBanner>}
      {workspaces === null && !error && (
        <p className="text-sm text-gray-500 dark:text-gray-400">Yuklanmoqda...</p>
      )}

      <div>
        <ul className="space-y-2">
          {workspaces?.map((workspace) => (
            <li key={workspace.workspace_id}>
              <Card className="flex items-center justify-between gap-4 !p-4 transition-shadow hover:shadow-md">
                <Link
                  href={`/workspaces/${workspace.workspace_id}`}
                  className="min-w-0 flex-1 font-medium text-gray-900 hover:text-gray-600 dark:text-gray-50 dark:hover:text-gray-300"
                >
                  {workspace.workspace_name}
                </Link>
                <div className="flex shrink-0 items-center gap-3">
                  <Link
                    href={`/customers/${workspace.customer_id}`}
                    className="text-sm text-gray-500 hover:text-gray-900 hover:underline dark:text-gray-400 dark:hover:text-gray-100"
                  >
                    {workspace.customer_name}
                  </Link>
                  <Badge>{workspace.role}</Badge>
                </div>
              </Card>
            </li>
          ))}
        </ul>
        {workspaces !== null && workspaces.length === 0 && (
          <EmptyState>Siz hech qanday workspace&apos;ga a&apos;zo emassiz.</EmptyState>
        )}
      </div>

      {customers !== null && customers.length > 0 && (
        <section>
          <SectionHeading className="mb-3">Customer&apos;larim</SectionHeading>
          <ul className="space-y-2">
            {customers.map((customer) => (
              <li key={customer.customer_id}>
                <Card className="flex items-center justify-between gap-4 !p-4 transition-shadow hover:shadow-md">
                  <Link
                    href={`/customers/${customer.customer_id}`}
                    className="min-w-0 flex-1 font-medium text-gray-900 hover:text-gray-600 dark:text-gray-50 dark:hover:text-gray-300"
                  >
                    {customer.customer_name}
                  </Link>
                  <Badge>{customer.role}</Badge>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
