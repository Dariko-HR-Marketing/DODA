import type { ComponentPropsWithoutRef, ElementType, ReactNode } from "react";

/** Joins classNames, skipping falsy values — the only "utility" this file
 * needs; pulling in a dependency for this would be overkill. */
export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

// ---- Form controls -------------------------------------------------------
//
// These are plain className strings, not wrapper components: every input/
// select/button across the app keeps its exact tag, id, aria-label,
// placeholder and type — several of those are load-bearing for Playwright
// selectors (`#session-id`, `button[type="submit"]`, `input[aria-label=...]`,
// `getByLabel(...)`) and for native label association. A wrapper component
// risks changing that DOM shape; a shared className string cannot.

export const fieldClass = cx(
  "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900",
  "placeholder:text-gray-400",
  "focus:border-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900/10",
  "disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400",
  "dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500",
  "dark:focus:border-gray-100 dark:focus:ring-gray-100/10",
);

/** Same treatment, smaller — for controls nested inside list rows
 * (decision drafts, reminder pickers, member-role selects, …). */
export const fieldClassCompact = cx(
  "rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-sm text-gray-900",
  "placeholder:text-gray-400",
  "focus:border-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900/10",
  "disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400",
  "dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500",
  "dark:focus:border-gray-100 dark:focus:ring-gray-100/10",
);

const buttonBase = cx(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-medium transition-colors",
  "disabled:cursor-not-allowed disabled:opacity-50",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
);

export const primaryButtonClass = cx(
  buttonBase,
  "px-4 py-2 text-sm bg-gray-900 text-white shadow-sm hover:bg-gray-700",
  "focus-visible:ring-gray-900 dark:bg-gray-50 dark:text-gray-900 dark:hover:bg-gray-200 dark:focus-visible:ring-gray-100",
);

export const secondaryButtonClass = cx(
  buttonBase,
  "px-4 py-2 text-sm border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
  "focus-visible:ring-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800",
);

export const dangerButtonClass = cx(
  buttonBase,
  "px-4 py-2 text-sm bg-red-600 text-white shadow-sm hover:bg-red-700",
  "focus-visible:ring-red-600",
);

/** Compact variant of the solid buttons above, for banners/inline rows that
 * don't need a full-size call to action (e.g. kill switch engage, exports).
 * Combine with a color pairing (e.g. "bg-blue-600 text-white hover:bg-blue-700
 * focus-visible:ring-blue-600") at the call site. */
export const compactButtonClass = cx(buttonBase, "px-3 py-1.5 text-xs");

/** The compact, outlined "secondary" button — filters, "test connection",
 * "verify chain" and similarly low-stakes inline actions. */
export const compactSecondaryButtonClass = cx(
  compactButtonClass,
  "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 focus-visible:ring-gray-400",
  "dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800",
);

/** Text-styled inline actions (list-row links like "Chiqarish"/"Yopish") —
 * kept visually lighter than a real button since that's what these are:
 * secondary actions inside an already-dense row. */
export const actionLinkClass = cx(
  "rounded text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline",
  "disabled:cursor-not-allowed disabled:opacity-50 disabled:no-underline",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40",
  "dark:text-blue-400 dark:hover:text-blue-300",
);

export const dangerLinkClass = cx(
  "rounded text-xs font-medium text-red-600 hover:text-red-700 hover:underline",
  "disabled:cursor-not-allowed disabled:opacity-50 disabled:no-underline",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/40",
  "dark:text-red-400 dark:hover:text-red-300",
);

export const mutedLinkClass = cx(
  "rounded text-xs font-medium text-gray-500 hover:text-gray-800 hover:underline",
  "disabled:cursor-not-allowed disabled:opacity-50",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400/40",
  "dark:text-gray-400 dark:hover:text-gray-200",
);

// ---- Layout ---------------------------------------------------------------

type CardProps<T extends ElementType> = {
  as?: T;
  className?: string;
  children: ReactNode;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "className" | "children">;

/** The one visual "surface" used everywhere: a white (dark: slate) rounded
 * panel with a hairline border and a soft shadow. `as` lets each call site
 * keep whatever tag it semantically needs — several E2E specs locate a
 * section by tag + text (`page.locator("section", { hasText: ... })`), so
 * this must never silently become a `<div>`. */
export function Card<T extends ElementType = "div">({ as, className, children, ...rest }: CardProps<T>) {
  const Tag = (as ?? "div") as ElementType;
  return (
    <Tag
      className={cx(
        "rounded-xl border border-gray-200 bg-white p-4 shadow-sm sm:p-5",
        "dark:border-gray-800 dark:bg-gray-900",
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export function PageTitle({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <h1 className={cx("text-2xl font-bold tracking-tight text-gray-900 dark:text-gray-50", className)}>
      {children}
    </h1>
  );
}

export function SectionHeading({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <h2 className={cx("text-base font-semibold text-gray-900 dark:text-gray-50", className)}>{children}</h2>
  );
}

export function SectionSubtext({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("text-sm text-gray-500 dark:text-gray-400", className)}>{children}</p>;
}

/** The dashed-border "nothing here yet" placeholder used in every list. */
export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-gray-300 px-4 py-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
      {children}
    </p>
  );
}

/** Same empty-state treatment, but as an `<li>` — for the many lists here
 * that render their "nothing yet" message as a row of their own `<ul>`
 * rather than a sibling paragraph (keeps the DOM valid: a `<ul>`'s only
 * legal children are `<li>`s). */
export function EmptyListItem({ children }: { children: ReactNode }) {
  return <li className="px-1 py-2 text-sm text-gray-500 dark:text-gray-400">{children}</li>;
}

export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300"
    >
      {children}
    </div>
  );
}

export const backLinkClass = cx(
  "inline-flex items-center gap-1 text-sm font-medium text-gray-500 hover:text-gray-900",
  "dark:text-gray-400 dark:hover:text-gray-100",
);

// ---- Status badges ---------------------------------------------------------

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300",
  info: "bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  success: "bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-300",
  warning: "bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  danger: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
};

/** Status chip — same `<span>`-with-exact-text shape every status badge
 * already used (several E2E specs do `getByText("READY", { exact: true })`
 * against it), just with the tone colored in instead of flat gray. */
export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", TONE_CLASSES[tone], className)}>
      {children}
    </span>
  );
}

const DANGER_STATUSES = new Set([
  "FAILED",
  "CANCELLED",
  "REJECTED",
  "DENIED",
  "EXPIRED",
]);
const SUCCESS_STATUSES = new Set(["DONE", "SUCCEEDED", "CONFIRMED", "COMPENSATED", "READY", "FIRED"]);
const WARNING_STATUSES = new Set([
  "AWAITING_APPROVAL",
  "PENDING_CONFIRMATION",
  "RUNNING",
  "VALIDATING",
  "RETRYING",
  "COMPENSATING",
  "DRAFT",
]);
const INFO_STATUSES = new Set(["IN_PROGRESS"]);

/** Maps a known status/enum string to a Badge tone. Deliberately a lookup
 * over the exact literal values this app's APIs actually return (TaskStatus,
 * ActionStatus, ReminderStatus) rather than a substring heuristic — e.g.
 * COMPENSATING (in flight) and COMPENSATED (done) differ only by suffix, so
 * guessing from substrings would color them the same. */
export function statusTone(value: string): Tone {
  if (DANGER_STATUSES.has(value)) return "danger";
  if (SUCCESS_STATUSES.has(value)) return "success";
  if (WARNING_STATUSES.has(value)) return "warning";
  if (INFO_STATUSES.has(value)) return "info";
  return "neutral";
}
