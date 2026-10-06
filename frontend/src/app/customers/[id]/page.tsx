"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ApiError,
  changeCustomerMemberRole,
  clearAiBudgetLimits,
  clearMyAiPreference,
  disengageCustomerKillSwitch,
  downloadJsonFile,
  engageCustomerKillSwitch,
  getAiBudgetLimits,
  getAiBudgetStatus,
  getAiFallbackSetting,
  getAiUsageReport,
  getCustomerAuditEvidencePackage,
  getCustomerKillSwitch,
  getMyAiPreference,
  inviteCustomerMember,
  listArchivedWorkspaces,
  listCustomerAudit,
  listCustomerMembers,
  listCustomerNotifications,
  listMyCustomers,
  listNotificationPreferences,
  listProviderStatuses,
  markCustomerNotificationRead,
  removeCustomerMember,
  restoreWorkspace,
  setAiBudgetLimits,
  setAiFallbackSetting,
  setMyAiPreference,
  setNotificationPreference,
  setProviderEnabled,
  testProviderConnection,
  verifyCustomerAuditChain,
  AI_PROVIDERS,
  type AiBudgetLimitsOut,
  type AiBudgetStatusOut,
  type AiFallbackSettingOut,
  type AiPreferenceOut,
  type AiProvider,
  type AiUsageReportRowOut,
  type AuditChainVerificationOut,
  type AuditEventOut,
  type CustomerMemberOut,
  type CustomerRole,
  type KillSwitchStatusOut,
  type NotificationOut,
  type NotificationPreferenceOut,
  type NotificationType,
  type ProviderStatusOut,
  type WorkspaceOut,
} from "@/lib/api";
import { KillSwitchPanel } from "@/components/KillSwitchPanel";
import { useSession } from "@/lib/useSession";
import {
  Card,
  EmptyListItem,
  ErrorBanner,
  PageTitle,
  SectionHeading,
  actionLinkClass,
  backLinkClass,
  compactSecondaryButtonClass,
  dangerLinkClass,
  fieldClassCompact,
  mutedLinkClass,
  primaryButtonClass,
} from "@/components/ui";

const CUSTOMER_ROLES: CustomerRole[] = ["customer_owner", "member", "auditor"];
const ALWAYS_ON_NOTIFICATION_TYPE: NotificationType = "SECURITY_ALERT";

export default function CustomerPage() {
  const params = useParams<{ id: string }>();
  const customerId = params.id;
  const sessionId = useSession();

  const [customerName, setCustomerName] = useState<string | null>(null);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatusOut | null>(null);
  const [killSwitchReason, setKillSwitchReason] = useState("");
  const [members, setMembers] = useState<CustomerMemberOut[] | null>(null);
  const [newMemberUserId, setNewMemberUserId] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<CustomerRole>("member");
  const [engagingKillSwitch, setEngagingKillSwitch] = useState(false);
  const [invitingMember, setInvitingMember] = useState(false);
  const [notifications, setNotifications] = useState<NotificationOut[] | null>(null);
  const [preferences, setPreferences] = useState<NotificationPreferenceOut[] | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEventOut[] | null>(null);
  const [chainVerification, setChainVerification] = useState<AuditChainVerificationOut | null>(null);
  const [verifyingChain, setVerifyingChain] = useState(false);
  const [exportingEvidence, setExportingEvidence] = useState(false);
  const [archivedWorkspaces, setArchivedWorkspaces] = useState<WorkspaceOut[] | null>(null);
  const [restoringWorkspaceId, setRestoringWorkspaceId] = useState<string | null>(null);
  const [providerStatuses, setProviderStatuses] = useState<ProviderStatusOut[] | null>(null);
  const [budgetStatus, setBudgetStatus] = useState<AiBudgetStatusOut | null>(null);
  const [usageReport, setUsageReport] = useState<AiUsageReportRowOut[] | null>(null);
  const [budgetLimits, setBudgetLimits] = useState<AiBudgetLimitsOut | null>(null);
  const [softCapInput, setSoftCapInput] = useState("");
  const [hardCapInput, setHardCapInput] = useState("");
  const [savingBudgetLimits, setSavingBudgetLimits] = useState(false);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [fallbackSetting, setFallbackSetting] = useState<AiFallbackSettingOut | null>(null);
  const [togglingFallback, setTogglingFallback] = useState(false);
  const [myAiPreference, setMyAiPreferenceState] = useState<AiPreferenceOut | null>(null);
  const [myAiProviderChoice, setMyAiProviderChoice] = useState<AiProvider>("OPENAI");
  const [myAiModelChoice, setMyAiModelChoice] = useState("");
  const [savingMyAiPreference, setSavingMyAiPreference] = useState(false);
  const [traceIdInput, setTraceIdInput] = useState("");
  const [appliedTraceId, setAppliedTraceId] = useState("");
  const [error, setError] = useState<string | null>(null);
  // refresh() re-fetches this page's whole state after ANY mutation (kill
  // switch, member changes, etc.), not just budget-limit ones — its
  // getAiBudgetLimits() call used to unconditionally overwrite
  // softCapInput/hardCapInput on every one of those, so an in-flight
  // refresh() triggered by an unrelated action (e.g. engaging the kill
  // switch) could land after the user had already started typing into the
  // budget-cap fields and silently wipe them back to "" — a real,
  // reproducible race, not a flake (caught by two consecutive E2E runs
  // failing at the same step with "budget caps must be positive", which is
  // exactly what submitting the wiped, empty inputs as 0/0 produces). Only
  // populate the inputs from the server on the very first load; later
  // refreshes leave whatever the user is editing alone.
  const budgetLimitsLoadedRef = useRef(false);

  const refresh = useCallback(() => {
    if (sessionId === null) return;
    // Name comes from /v1/me/customers, not /v1/me/workspaces: the latter is
    // workspace-shaped, so for a member holding no workspace role (an auditor,
    // read-only by design) or a customer with no unarchived workspaces it has
    // no row to read the name from, and this page — the only place their access
    // lives — would head itself "Customer".
    listMyCustomers(sessionId)
      .then((customers) => {
        const match = customers.find((c) => c.customer_id === customerId);
        if (match) setCustomerName(match.customer_name);
      })
      .catch(() => {});
    getCustomerKillSwitch(sessionId, customerId).then(setKillSwitch).catch(() => {});
    listCustomerMembers(sessionId, customerId)
      .then(setMembers)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Yuklab bo'lmadi."));
    listCustomerNotifications(sessionId, customerId).then(setNotifications).catch(() => {});
    listNotificationPreferences(sessionId, customerId).then(setPreferences).catch(() => {});
    listCustomerAudit(sessionId, customerId, appliedTraceId || undefined)
      .then(setAuditEvents)
      .catch(() => {});
    // CustomerOwner-only (authorize_view_archived_workspaces) — a plain
    // member/auditor gets 403 here, so this fails silently like the other
    // optional sections above rather than surfacing a spurious error.
    listArchivedWorkspaces(sessionId, customerId).then(setArchivedWorkspaces).catch(() => {});
    listProviderStatuses(sessionId, customerId).then(setProviderStatuses).catch(() => {});
    getAiFallbackSetting(sessionId, customerId).then(setFallbackSetting).catch(() => {});
    // CustomerOwner/Auditor-only (authorize_view_ai_budget) — fails
    // silently for a plain member, same as archived workspaces above.
    getAiBudgetStatus(sessionId, customerId).then(setBudgetStatus).catch(() => {});
    getAiUsageReport(sessionId, customerId).then(setUsageReport).catch(() => {});
    getAiBudgetLimits(sessionId, customerId)
      .then((limits) => {
        setBudgetLimits(limits);
        if (!budgetLimitsLoadedRef.current) {
          budgetLimitsLoadedRef.current = true;
          setSoftCapInput(limits.soft_cap_usd !== null ? String(limits.soft_cap_usd) : "");
          setHardCapInput(limits.hard_cap_usd !== null ? String(limits.hard_cap_usd) : "");
        }
      })
      .catch(() => {});
    getMyAiPreference(sessionId, customerId).then(setMyAiPreferenceState).catch(() => {});
  }, [sessionId, customerId, appliedTraceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleEngageKillSwitch(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || killSwitchReason.trim().length === 0 || engagingKillSwitch) return;
    setEngagingKillSwitch(true);
    try {
      await engageCustomerKillSwitch(sessionId, customerId, killSwitchReason.trim());
      setKillSwitchReason("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kill switch'ni yoqib bo'lmadi.");
    } finally {
      setEngagingKillSwitch(false);
    }
  }

  async function handleDisengageKillSwitch() {
    if (sessionId === null) return;
    try {
      await disengageCustomerKillSwitch(sessionId, customerId);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kill switch'ni o'chirib bo'lmadi.");
    }
  }

  async function handleInviteMember(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || newMemberUserId.trim().length === 0 || invitingMember) return;
    setInvitingMember(true);
    try {
      await inviteCustomerMember(sessionId, customerId, newMemberUserId.trim(), newMemberRole);
      setNewMemberUserId("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "A'zo qo'shib bo'lmadi.");
    } finally {
      setInvitingMember(false);
    }
  }

  async function handleChangeMemberRole(member: CustomerMemberOut, role: CustomerRole) {
    if (sessionId === null || role === member.role) return;
    try {
      await changeCustomerMemberRole(sessionId, customerId, member.membership_id, role);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Rolni o'zgartirib bo'lmadi.");
    }
  }

  async function handleRemoveMember(member: CustomerMemberOut) {
    if (sessionId === null) return;
    try {
      await removeCustomerMember(sessionId, customerId, member.membership_id);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "A'zoni chiqarib bo'lmadi.");
    }
  }

  async function handleRestoreWorkspace(workspace: WorkspaceOut) {
    if (sessionId === null || restoringWorkspaceId !== null) return;
    setRestoringWorkspaceId(workspace.id);
    try {
      await restoreWorkspace(sessionId, workspace.id);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Workspace'ni tiklab bo'lmadi.");
    } finally {
      setRestoringWorkspaceId(null);
    }
  }

  async function handleVerifyChain() {
    if (sessionId === null || verifyingChain) return;
    setVerifyingChain(true);
    try {
      const result = await verifyCustomerAuditChain(sessionId, customerId);
      setChainVerification(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Zanjirni tekshirib bo'lmadi.");
    } finally {
      setVerifyingChain(false);
    }
  }

  async function handleExportEvidencePackage() {
    if (sessionId === null || exportingEvidence || appliedTraceId === "") return;
    setExportingEvidence(true);
    try {
      // FR-AUD-005: exports exactly the currently-filtered trace_id's
      // audit trail, bundled with a per-event hash recomputation and the
      // whole-customer chain-verification result — see the backend's own
      // EvidencePackage docstring for what each proves.
      const pkg = await getCustomerAuditEvidencePackage(sessionId, customerId, appliedTraceId);
      downloadJsonFile(`doda-evidence-${appliedTraceId}.json`, pkg);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Evidence paketini eksport qilib bo'lmadi.");
    } finally {
      setExportingEvidence(false);
    }
  }

  async function handleMarkRead(notification: NotificationOut) {
    if (sessionId === null) return;
    await markCustomerNotificationRead(sessionId, customerId, notification.id).catch(() => {});
    refresh();
  }

  async function handleToggleProviderEnabled(provider: ProviderStatusOut) {
    if (sessionId === null) return;
    try {
      await setProviderEnabled(sessionId, customerId, provider.provider, !provider.enabled);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Provayderni o'zgartirib bo'lmadi.");
    }
  }

  async function handleTestProviderConnection(provider: ProviderStatusOut) {
    if (sessionId === null || testingProvider !== null) return;
    setTestingProvider(provider.provider);
    try {
      await testProviderConnection(sessionId, customerId, provider.provider);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ulanishni tekshirib bo'lmadi.");
    } finally {
      setTestingProvider(null);
    }
  }

  async function handleToggleFallback() {
    if (sessionId === null || fallbackSetting === null || togglingFallback) return;
    setTogglingFallback(true);
    try {
      const updated = await setAiFallbackSetting(sessionId, customerId, !fallbackSetting.enabled);
      setFallbackSetting(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Fallback sozlamasini o'zgartirib bo'lmadi.");
    } finally {
      setTogglingFallback(false);
    }
  }

  async function handleSetBudgetLimits(event: FormEvent) {
    event.preventDefault();
    const soft = Number(softCapInput);
    const hard = Number(hardCapInput);
    if (sessionId === null || savingBudgetLimits || !Number.isFinite(soft) || !Number.isFinite(hard)) return;
    setSavingBudgetLimits(true);
    try {
      const updated = await setAiBudgetLimits(sessionId, customerId, soft, hard);
      setBudgetLimits(updated);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Byudjet limitlarini saqlab bo'lmadi.");
    } finally {
      setSavingBudgetLimits(false);
    }
  }

  async function handleClearBudgetLimits() {
    if (sessionId === null || savingBudgetLimits) return;
    setSavingBudgetLimits(true);
    try {
      await clearAiBudgetLimits(sessionId, customerId);
      setBudgetLimits({ soft_cap_usd: null, hard_cap_usd: null });
      setSoftCapInput("");
      setHardCapInput("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Byudjet limitlarini tozalab bo'lmadi.");
    } finally {
      setSavingBudgetLimits(false);
    }
  }

  async function handleSetMyAiPreference(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || savingMyAiPreference) return;
    setSavingMyAiPreference(true);
    try {
      const updated = await setMyAiPreference(
        sessionId,
        customerId,
        myAiProviderChoice,
        myAiModelChoice.trim().length > 0 ? myAiModelChoice.trim() : null,
      );
      setMyAiPreferenceState(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "AI afzalligini saqlab bo'lmadi.");
    } finally {
      setSavingMyAiPreference(false);
    }
  }

  async function handleClearMyAiPreference() {
    if (sessionId === null || savingMyAiPreference) return;
    setSavingMyAiPreference(true);
    try {
      await clearMyAiPreference(sessionId, customerId);
      setMyAiPreferenceState({ provider: null, model: null });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "AI afzalligini tozalab bo'lmadi.");
    } finally {
      setSavingMyAiPreference(false);
    }
  }

  async function handleTogglePreference(preference: NotificationPreferenceOut) {
    if (sessionId === null || preference.notification_type === ALWAYS_ON_NOTIFICATION_TYPE) return;
    try {
      await setNotificationPreference(
        sessionId,
        customerId,
        preference.notification_type,
        !preference.enabled,
      );
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sozlamani o'zgartirib bo'lmadi.");
    }
  }

  if (sessionId === null) return null;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 space-y-8 p-6">
      <div>
        <Link href="/workspaces" className={backLinkClass}>
          <span aria-hidden="true">&larr;</span> Workspace&apos;lar
        </Link>
      </div>

      <PageTitle>{customerName ?? "Customer"}</PageTitle>

      {error && <ErrorBanner>{error}</ErrorBanner>}

      <KillSwitchPanel
        killSwitch={killSwitch}
        reason={killSwitchReason}
        onReasonChange={setKillSwitchReason}
        engaging={engagingKillSwitch}
        onEngage={handleEngageKillSwitch}
        onDisengage={handleDisengageKillSwitch}
      />

      <Card as="section">
        <SectionHeading className="mb-3">A&apos;zolar</SectionHeading>
        <form onSubmit={handleInviteMember} className="mb-3 flex flex-wrap gap-2">
          <input
            type="text"
            value={newMemberUserId}
            onChange={(event) => setNewMemberUserId(event.target.value)}
            placeholder="User ID (UUID)"
            className="min-w-[14rem] flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900/10 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
          />
          <select
            aria-label="Yangi a'zo roli"
            value={newMemberRole}
            onChange={(event) => setNewMemberRole(event.target.value as CustomerRole)}
            className="rounded-lg border border-gray-300 bg-white px-2.5 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900/10 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
          >
            {CUSTOMER_ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
          <button type="submit" disabled={newMemberUserId.trim().length === 0 || invitingMember} className={primaryButtonClass}>
            Qo&apos;shish
          </button>
        </form>
        <ul className="space-y-1">
          {members?.map((member) => (
            <li key={member.membership_id} className="flex items-center justify-between gap-2 py-1 text-sm">
              <span className="text-gray-900 dark:text-gray-100">{member.display_name}</span>
              <div className="flex items-center gap-2">
                <select
                  aria-label={`${member.display_name} roli`}
                  value={member.role}
                  onChange={(event) => handleChangeMemberRole(member, event.target.value as CustomerRole)}
                  className="rounded-full border border-gray-200 bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-900/10 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
                >
                  {CUSTOMER_ROLES.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
                <button onClick={() => handleRemoveMember(member)} className={dangerLinkClass}>
                  Chiqarish
                </button>
              </div>
            </li>
          ))}
          {members !== null && members.length === 0 && <EmptyListItem>A&apos;zo yo&apos;q.</EmptyListItem>}
        </ul>
      </Card>

      <Card as="section">
        <SectionHeading className="mb-3">AI provayderlar</SectionHeading>
        {budgetStatus !== null && (
          <div
            className={`mb-3 rounded-lg border p-3 text-sm ${
              budgetStatus.over_soft_budget
                ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"
                : "border-gray-200 text-gray-700 dark:border-gray-800 dark:text-gray-300"
            }`}
          >
            <span className="font-medium">{budgetStatus.year_month} AI byudjeti:</span>{" "}
            ${budgetStatus.spent_usd.toFixed(2)} / ${budgetStatus.hard_cap_usd.toFixed(2)}
            {budgetStatus.over_soft_budget && (
              <span> — oylik byudjetning katta qismi sarflandi (soft cap: ${budgetStatus.soft_cap_usd.toFixed(2)}).</span>
            )}
          </div>
        )}
        {usageReport !== null && usageReport.length > 0 && (
          <div className="mb-3 overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-800">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Workspace, provayder va model bo&apos;yicha AI xarajati</caption>
              <thead className="bg-gray-50 text-xs text-gray-500 dark:bg-gray-950/40 dark:text-gray-400">
                <tr>
                  <th scope="col" className="px-3 py-2">
                    Workspace
                  </th>
                  <th scope="col" className="px-3 py-2">
                    Provayder
                  </th>
                  <th scope="col" className="px-3 py-2">
                    Model
                  </th>
                  <th scope="col" className="px-3 py-2 text-right">
                    Xarajat
                  </th>
                  <th scope="col" className="px-3 py-2 text-right">
                    So&apos;rovlar
                  </th>
                </tr>
              </thead>
              <tbody>
                {usageReport.map((row) => (
                  <tr
                    key={`${row.workspace_id}-${row.provider}-${row.model}`}
                    className="border-t border-gray-200 text-gray-800 dark:border-gray-800 dark:text-gray-200"
                  >
                    <td className="px-3 py-2">{row.workspace_name}</td>
                    <td className="px-3 py-2">{row.provider}</td>
                    <td className="px-3 py-2">{row.model}</td>
                    <td className="px-3 py-2 text-right">${row.cost_usd.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right">{row.event_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {/* FR-ADM-005: set/clear this customer's own AI budget caps —
            no row (budgetLimits.soft_cap_usd === null) means the
            deployment-wide default from the banner above still applies. */}
        <form onSubmit={handleSetBudgetLimits} className="mb-3 flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-1.5 text-gray-700 dark:text-gray-300">
            Soft cap ($)
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={softCapInput}
              onChange={(e) => setSoftCapInput(e.target.value)}
              className={`${fieldClassCompact} w-24`}
            />
          </label>
          <label className="flex items-center gap-1.5 text-gray-700 dark:text-gray-300">
            Hard cap ($)
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={hardCapInput}
              onChange={(e) => setHardCapInput(e.target.value)}
              className={`${fieldClassCompact} w-24`}
            />
          </label>
          <button type="submit" disabled={savingBudgetLimits} className={compactSecondaryButtonClass + " border-blue-200 bg-blue-600 text-white hover:bg-blue-700 dark:border-blue-900"}>
            Saqlash
          </button>
          {budgetLimits?.soft_cap_usd !== null && budgetLimits?.soft_cap_usd !== undefined && (
            <button type="button" onClick={handleClearBudgetLimits} disabled={savingBudgetLimits} className={dangerLinkClass}>
              Standart qiymatga qaytarish
            </button>
          )}
        </form>
        <ul className="space-y-2">
          {providerStatuses?.map((provider) => (
            <li
              key={provider.provider}
              className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-800"
            >
              <div className="flex flex-col">
                <span className="font-medium text-gray-900 dark:text-gray-100">{provider.provider}</span>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {provider.configured ? "sozlangan" : "kalit yo'q"}
                  {provider.verified_at !== null &&
                    (provider.verified_ok
                      ? " · tekshirilgan: ishlaydi"
                      : ` · tekshirilgan: ${provider.verified_error ?? "xato"}`)}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => handleTestProviderConnection(provider)}
                  disabled={testingProvider !== null}
                  className={actionLinkClass}
                >
                  {testingProvider === provider.provider ? "Tekshirilmoqda..." : "Ulanishni tekshirish"}
                </button>
                <button onClick={() => handleToggleProviderEnabled(provider)} className={mutedLinkClass}>
                  {provider.enabled ? "O'chirish" : "Yoqish"}
                </button>
              </div>
            </li>
          ))}
          {providerStatuses !== null && providerStatuses.length === 0 && (
            <EmptyListItem>Provayder ma&apos;lumoti yo&apos;q.</EmptyListItem>
          )}
        </ul>
        {fallbackSetting !== null && (
          <div className="mt-3 flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-800">
            <div className="flex flex-col">
              <span className="text-gray-900 dark:text-gray-100">Avtomatik fallback</span>
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Vaqtinchalik provayder xatosida (timeout/rate-limit) boshqa provayderga avtomatik o&apos;tish.
                Standart — o&apos;chirilgan.
              </span>
            </div>
            <button onClick={handleToggleFallback} disabled={togglingFallback} className={actionLinkClass}>
              {fallbackSetting.enabled ? "O'chirish" : "Yoqish"}
            </button>
          </div>
        )}

        {myAiPreference !== null && (
          <form onSubmit={handleSetMyAiPreference} className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-gray-500 dark:text-gray-400">
              Mening AI afzalligim ({myAiPreference.provider ?? "tizim standart"}
              {myAiPreference.model ? ` / ${myAiPreference.model}` : ""}):
            </span>
            <select
              aria-label="Mening AI provayderim"
              value={myAiProviderChoice}
              onChange={(event) => setMyAiProviderChoice(event.target.value as AiProvider)}
              className={fieldClassCompact}
            >
              {AI_PROVIDERS.map((provider) => (
                <option key={provider} value={provider}>
                  {provider}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={myAiModelChoice}
              onChange={(event) => setMyAiModelChoice(event.target.value)}
              placeholder="model (ixtiyoriy)"
              className={`${fieldClassCompact} w-32`}
            />
            <button type="submit" disabled={savingMyAiPreference} className={actionLinkClass}>
              Saqlash
            </button>
            {myAiPreference.provider !== null && (
              <button
                type="button"
                onClick={handleClearMyAiPreference}
                disabled={savingMyAiPreference}
                className={dangerLinkClass}
              >
                Tizim standartga qaytarish
              </button>
            )}
          </form>
        )}
      </Card>

      {archivedWorkspaces !== null && archivedWorkspaces.length > 0 && (
        <Card as="section">
          <SectionHeading className="mb-3">Arxivlangan workspace&apos;lar</SectionHeading>
          <ul className="space-y-1">
            {archivedWorkspaces.map((workspace) => (
              <li key={workspace.id} className="flex items-center justify-between gap-2 py-1 text-sm">
                <span className="text-gray-500 dark:text-gray-400">{workspace.name}</span>
                <button
                  onClick={() => handleRestoreWorkspace(workspace)}
                  disabled={restoringWorkspaceId === workspace.id}
                  className={actionLinkClass}
                >
                  Tiklash
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card as="section">
        <SectionHeading className="mb-3">Bildirishnoma sozlamalari</SectionHeading>
        <ul className="space-y-1">
          {preferences?.map((preference) => (
            <li key={preference.notification_type} className="flex items-center justify-between gap-2 py-1 text-sm">
              <span className="text-gray-900 dark:text-gray-100">{preference.notification_type}</span>
              {preference.notification_type === ALWAYS_ON_NOTIFICATION_TYPE ? (
                <span className="text-xs text-gray-500 dark:text-gray-400">doim yoqilgan</span>
              ) : (
                <button onClick={() => handleTogglePreference(preference)} className={actionLinkClass}>
                  {preference.enabled ? "O'chirish" : "Yoqish"}
                </button>
              )}
            </li>
          ))}
        </ul>
      </Card>

      <Card as="section">
        <SectionHeading className="mb-3">Bildirishnomalar (barcha workspace)</SectionHeading>
        <ul className="space-y-2">
          {notifications?.map((notification) => (
            <li
              key={notification.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-800"
            >
              <span className={notification.read_at ? "text-gray-400 dark:text-gray-500" : "text-gray-900 dark:text-gray-100"}>
                {notification.notification_type} — {notification.reference_type}
              </span>
              {!notification.read_at && (
                <button onClick={() => handleMarkRead(notification)} className={actionLinkClass}>
                  O&apos;qildi deb belgilash
                </button>
              )}
            </li>
          ))}
          {notifications !== null && notifications.length === 0 && (
            <EmptyListItem>Bildirishnoma yo&apos;q.</EmptyListItem>
          )}
        </ul>
      </Card>

      <Card as="section">
        <div className="mb-3 flex items-center justify-between gap-2">
          <SectionHeading>Audit</SectionHeading>
          <button onClick={handleVerifyChain} disabled={verifyingChain} className={compactSecondaryButtonClass}>
            {verifyingChain ? "Tekshirilmoqda..." : "Zanjirni tekshirish"}
          </button>
        </div>
        {chainVerification && (
          <div
            className={`mb-3 rounded-lg border p-3 text-sm ${
              chainVerification.ok
                ? "border-green-200 bg-green-50 text-green-900 dark:border-green-900/50 dark:bg-green-950/30 dark:text-green-200"
                : "border-red-200 bg-red-50 text-red-900 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-200"
            }`}
          >
            {chainVerification.ok ? (
              <p>
                Zanjir sog&apos;lom — {chainVerification.checked_count} ta yozuv tekshirildi, buzilish
                topilmadi.
              </p>
            ) : (
              <p>
                {chainVerification.violations.length} ta buzilish topildi ({chainVerification.checked_count}{" "}
                ta yozuvdan)!
              </p>
            )}
          </div>
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setAppliedTraceId(traceIdInput.trim());
          }}
          className="mb-3 flex flex-wrap gap-2"
        >
          <input
            type="text"
            value={traceIdInput}
            onChange={(event) => setTraceIdInput(event.target.value)}
            placeholder="trace_id bo'yicha filtrlash"
            className={`${fieldClassCompact} min-w-[14rem] flex-1 font-mono`}
          />
          <button type="submit" className={compactSecondaryButtonClass}>
            Filtr
          </button>
          {appliedTraceId !== "" && (
            <button
              type="button"
              onClick={() => {
                setTraceIdInput("");
                setAppliedTraceId("");
              }}
              className={dangerLinkClass}
            >
              Tozalash
            </button>
          )}
          {appliedTraceId !== "" && (
            <button
              type="button"
              onClick={handleExportEvidencePackage}
              disabled={exportingEvidence}
              className={compactSecondaryButtonClass}
            >
              {exportingEvidence ? "Eksport qilinmoqda..." : "Evidence eksport"}
            </button>
          )}
        </form>
        <ul className="space-y-2">
          {auditEvents?.map((event) => (
            <li key={event.id} className="rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-800">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-gray-900 dark:text-gray-100">{event.event_type}</span>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {new Date(event.occurred_at).toLocaleString()}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2 text-xs text-gray-500 dark:text-gray-400">
                <span>{event.actor_id}</span>
                <button
                  onClick={() => {
                    setTraceIdInput(event.trace_id);
                    setAppliedTraceId(event.trace_id);
                  }}
                  className="rounded font-mono text-gray-500 hover:text-blue-600 hover:underline dark:text-gray-400 dark:hover:text-blue-400"
                  title="Shu trace_id bo'yicha filtrlash"
                >
                  {event.trace_id}
                </button>
              </div>
            </li>
          ))}
          {auditEvents !== null && auditEvents.length === 0 && (
            <EmptyListItem>Audit yozuvi yo&apos;q.</EmptyListItem>
          )}
        </ul>
      </Card>
    </main>
  );
}
