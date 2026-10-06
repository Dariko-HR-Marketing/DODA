"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  downloadJsonFile,
  getMyDataExport,
  listMySessions,
  revokeSession,
  type SessionOut,
} from "@/lib/api";
import { useSession } from "@/lib/useSession";
import {
  Badge,
  Card,
  EmptyState,
  ErrorBanner,
  PageTitle,
  SectionHeading,
  SectionSubtext,
  backLinkClass,
  compactButtonClass,
  dangerLinkClass,
} from "@/components/ui";

export default function SessionsPage() {
  const sessionId = useSession();
  const [sessions, setSessions] = useState<SessionOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const refresh = useCallback(() => {
    if (sessionId === null) return;
    listMySessions(sessionId)
      .then(setSessions)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Yuklab bo'lmadi."));
  }, [sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleRevoke(target: SessionOut) {
    if (sessionId === null) return;
    try {
      await revokeSession(sessionId, target.id);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sessiyani yopib bo'lmadi.");
    }
  }

  async function handleExportData() {
    if (sessionId === null || exporting) return;
    setExporting(true);
    try {
      const data = await getMyDataExport(sessionId);
      downloadJsonFile(`doda-export-${new Date().toISOString().slice(0, 10)}.json`, data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ma'lumotlarni eksport qilib bo'lmadi.");
    } finally {
      setExporting(false);
    }
  }

  if (sessionId === null) return null;

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 space-y-6 p-6">
      <div>
        <Link href="/workspaces" className={backLinkClass}>
          <span aria-hidden="true">&larr;</span> Workspace&apos;lar
        </Link>
      </div>

      <div>
        <PageTitle>Faol sessiyalar</PageTitle>
        <SectionSubtext className="mt-1">
          Boshqa qurilma/brauzerdagi sessiyani shu yerdan uzoqdan yopishingiz mumkin (FR-CTL-002). Joriy
          sessiyani chiqish uchun workspace&apos;lar sahifasidagi &quot;Chiqish&quot;ni ishlating.
        </SectionSubtext>
      </div>

      {error && <ErrorBanner>{error}</ErrorBanner>}

      <Card className="space-y-2">
        <SectionHeading>Ma&apos;lumotlarimni eksport qilish</SectionHeading>
        <SectionSubtext>
          A&apos;zo bo&apos;lgan har bir workspace&apos;dagi o&apos;zingizga tegishli task&apos;lar,
          bildirishnomalar va audit yozuvlarini bitta JSON fayl sifatida yuklab olasiz (FR-CTL-002).
        </SectionSubtext>
        <button onClick={handleExportData} disabled={exporting} className={`${compactButtonClass} bg-gray-900 text-white hover:bg-gray-700 focus-visible:ring-gray-900 dark:bg-gray-50 dark:text-gray-900 dark:hover:bg-gray-200`}>
          {exporting ? "Tayyorlanmoqda..." : "Eksport qilish"}
        </button>
      </Card>

      <ul className="space-y-2">
        {sessions?.map((session) => (
          <li key={session.id}>
            <Card className="flex items-center justify-between !p-3">
              <div>
                <div className="flex items-center gap-2 text-sm text-gray-900 dark:text-gray-100">
                  <span>{new Date(session.created_at).toLocaleString()}</span>
                  {session.is_current && <Badge tone="info">joriy</Badge>}
                  <Badge>{session.auth_strength}</Badge>
                </div>
                <div className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                  oxirgi faollik: {new Date(session.last_seen_at).toLocaleString()}
                </div>
              </div>
              {!session.is_current && (
                <button onClick={() => handleRevoke(session)} className={dangerLinkClass}>
                  Yopish
                </button>
              )}
            </Card>
          </li>
        ))}
      </ul>
      {sessions !== null && sessions.length === 0 && <EmptyState>Faol sessiya yo&apos;q.</EmptyState>}
    </main>
  );
}
