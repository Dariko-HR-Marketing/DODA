import type { FormEvent } from "react";
import type { KillSwitchStatusOut } from "@/lib/api";
import { Card, SectionHeading, compactButtonClass, fieldClassCompact } from "@/components/ui";

interface KillSwitchPanelProps {
  killSwitch: KillSwitchStatusOut | null;
  reason: string;
  onReasonChange: (reason: string) => void;
  engaging: boolean;
  onEngage: (event: FormEvent) => void;
  onDisengage: () => void;
  /** Extra sentence after the reason when engaged — workspace and customer
   * scope word this slightly differently ("Yangi action'lar bloklangan"). */
  blockedNote?: string;
}

/** FR-CTL-003 kill switch, shared between the workspace (workspace_admin
 * scope) and customer (customer_owner scope) pages — same engage/disengage
 * form and banner, differing only in which API calls the caller wires up. */
export function KillSwitchPanel({
  killSwitch,
  reason,
  onReasonChange,
  engaging,
  onEngage,
  onDisengage,
  blockedNote,
}: KillSwitchPanelProps) {
  return (
    <Card as="section">
      <SectionHeading className="mb-3">Kill switch</SectionHeading>
      {killSwitch?.engaged ? (
        <div className="space-y-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-200">
          <p>
            <strong className="font-semibold">Faol.</strong> Sabab: {killSwitch.reason}
            {blockedNote ? `. ${blockedNote}` : ""}
          </p>
          <button onClick={onDisengage} className={`${compactButtonClass} bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-600`}>
            O&apos;chirish
          </button>
        </div>
      ) : (
        <form onSubmit={onEngage} className="flex gap-2">
          <input
            type="text"
            value={reason}
            onChange={(event) => onReasonChange(event.target.value)}
            placeholder="Sabab"
            className={`${fieldClassCompact} flex-1`}
          />
          <button
            type="submit"
            disabled={reason.trim().length === 0 || engaging}
            className={`${compactButtonClass} bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-600`}
          >
            Yoqish
          </button>
        </form>
      )}
    </Card>
  );
}
