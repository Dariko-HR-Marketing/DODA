"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, listMySessions } from "@/lib/api";
import { storeSessionId } from "@/lib/session";
import { ErrorBanner } from "@/components/ui";

// The one thing this page exists for: the backend's real Google login
// flow (api/auth.py's /v1/auth/google/callback) redirects the browser
// here with ?session_id=<uuid> once it has minted a real Session row —
// this is the client-side half of that handoff, storing the same raw
// session UUID the dev/test /login form stores (see session.ts).
export default function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // Read synchronously at render time rather than inside the effect, so
  // the "missing session_id" case needs no setState call at all — same
  // sentinel-value-over-extra-state approach useSession.ts already
  // established for avoiding react-hooks/set-state-in-effect.
  const sessionId = searchParams.get("session_id");
  const [asyncError, setAsyncError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  // Render's free-tier backend spins down when idle and can take up to
  // ~50s to wake on its first request (see deploy/README.md) — the
  // request this page makes right after the OAuth redirect is exactly
  // that first request. A plain network-level failure here (not a real
  // backend rejection) is far more likely to be a cold start than an
  // actual outage, so retry for a bounded window instead of immediately
  // showing a scary error for what's usually a ~50s wait. A real
  // rejection (ApiError — the backend answered but said no) is never
  // retried; that's a definitive answer, not a transient blip.
  const RETRY_WINDOW_MS = 60_000;
  const RETRY_INTERVAL_MS = 5_000;

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    let cancelled = false;
    const startedAt = Date.now();

    const attempt = async (): Promise<void> => {
      try {
        // Same "is this really a live session" check the dev/test login
        // form does — confirms the backend's own redirect handed us
        // something real before trusting it client-side.
        await listMySessions(sessionId);
        if (!cancelled) {
          storeSessionId(sessionId);
          router.replace("/workspaces");
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        if (err instanceof ApiError) {
          setAsyncError(err.message);
          return;
        }
        if (Date.now() - startedAt >= RETRY_WINDOW_MS) {
          setAsyncError("Backend'ga ulanib bo'lmadi.");
          return;
        }
        setIsRetrying(true);
        await new Promise((resolve) => setTimeout(resolve, RETRY_INTERVAL_MS));
        if (!cancelled) {
          await attempt();
        }
      }
    };

    void attempt();

    return () => {
      cancelled = true;
    };
  }, [sessionId, router]);

  const error = sessionId ? asyncError : "session_id parametri topilmadi. Qaytadan urinib ko'ring.";

  if (error) {
    return (
      <div className="w-full max-w-sm space-y-4 text-center">
        <ErrorBanner>{error}</ErrorBanner>
        <a
          href="/login"
          className="inline-block text-sm font-medium text-gray-900 underline hover:text-gray-600 dark:text-gray-100 dark:hover:text-gray-300"
        >
          Qaytadan kirish
        </a>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 text-center">
      <svg
        aria-hidden="true"
        className="h-6 w-6 animate-spin text-gray-400 dark:text-gray-500"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {isRetrying
          ? "Kirish tasdiqlanmoqda... (server uyg'onayotgan bo'lishi mumkin, biroz kuting)"
          : "Kirish tasdiqlanmoqda..."}
      </p>
    </div>
  );
}
