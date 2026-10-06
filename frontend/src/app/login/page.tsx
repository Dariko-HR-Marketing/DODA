"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { API_BASE_URL, ApiError, listMySessions } from "@/lib/api";
import { storeSessionId } from "@/lib/session";
import { Card, ErrorBanner, fieldClass, primaryButtonClass, secondaryButtonClass } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      // The only "is this a real, unexpired, unrevoked session" check
      // available client-side: try it against a real endpoint and see if
      // the backend accepts it.
      await listMySessions(sessionId.trim());
      storeSessionId(sessionId.trim());
      router.push("/workspaces");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Backend'ga ulanib bo'lmadi.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-gray-50">DODA</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Shaxsiy AI operatsion tizimi</p>
        </div>

        <Card className="space-y-5">
          <a
            href={`${API_BASE_URL}/v1/auth/google/login`}
            className={`${secondaryButtonClass} w-full gap-2`}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 shrink-0">
              <path
                fill="#4285F4"
                d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.3h6.47c-.29 1.48-1.14 2.73-2.4 3.58v2.98h3.86c2.26-2.08 3.56-5.16 3.56-8.59z"
              />
              <path
                fill="#34A853"
                d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-2.98c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.12-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"
              />
              <path
                fill="#FBBC05"
                d="M5.27 14.31a7.17 7.17 0 0 1 0-4.62V6.6H1.29a11.98 11.98 0 0 0 0 10.8l3.98-3.09z"
              />
              <path
                fill="#EA4335"
                d="M12 4.75c1.76 0 3.34.6 4.58 1.78l3.43-3.43C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.6l3.98 3.09C6.22 6.87 8.87 4.75 12 4.75z"
              />
            </svg>
            Google orqali kirish
          </a>

          <div className="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400">
            <div className="h-px flex-1 bg-gray-200 dark:bg-gray-800" />
            yoki
            <div className="h-px flex-1 bg-gray-200 dark:bg-gray-800" />
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
            <strong className="font-semibold">Dev/test kirish.</strong> Bu forma session_service orqali
            to&apos;g&apos;ridan-to&apos;g&apos;ri yaratilgan xom session UUID
            qabul qiladi — real login uchun yuqoridagi &quot;Google orqali
            kirish&quot; tugmasidan foydalaning.
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label
                className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300"
                htmlFor="session-id"
              >
                Session ID
              </label>
              <input
                id="session-id"
                name="session-id"
                type="text"
                required
                value={sessionId}
                onChange={(event) => setSessionId(event.target.value)}
                placeholder="00000000-0000-0000-0000-000000000000"
                className={`${fieldClass} font-mono`}
              />
            </div>
            {error && <ErrorBanner>{error}</ErrorBanner>}
            <button
              type="submit"
              disabled={submitting || sessionId.trim().length === 0}
              className={`${primaryButtonClass} w-full`}
            >
              {submitting ? "Tekshirilmoqda..." : "Kirish"}
            </button>
          </form>
        </Card>
      </div>
    </main>
  );
}
