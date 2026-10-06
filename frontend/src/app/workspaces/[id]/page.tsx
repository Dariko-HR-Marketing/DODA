"use client";

import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ApiError,
  archiveWorkspace,
  attachTaskDocument,
  cancelAction,
  cancelTaskReminder,
  changeTaskStatus,
  changeWorkspaceMemberRole,
  confirmTaskReminder,
  createTask,
  deleteDocument,
  detachTaskDocument,
  disengageWorkspaceKillSwitch,
  downloadDocument,
  engageWorkspaceKillSwitch,
  getTaskAttachments,
  getTaskDecisions,
  getTaskHistory,
  getTaskPlan,
  getTaskReminders,
  getWorkspaceKillSwitch,
  listActions,
  listDocuments,
  listMyWorkspaces,
  listNotifications,
  listTasks,
  listWorkspaceAudit,
  listWorkspaceMembers,
  markNotificationRead,
  recordTaskDecision,
  removeWorkspaceMember,
  requestTaskReminder,
  searchDocuments,
  uploadDocument,
  uploadDocumentVersion,
  type ActionOut,
  type AuditEventOut,
  type DocumentChunkOut,
  type DocumentOut,
  type KillSwitchStatusOut,
  type NotificationOut,
  type ReminderOut,
  type TaskAttachmentOut,
  type TaskDecisionOut,
  type TaskHistoryEntryOut,
  type TaskOut,
  type TaskPlanPeriod,
  type TaskStatus,
  type WorkspaceMemberOut,
  type WorkspaceRole,
} from "@/lib/api";
import { KillSwitchPanel } from "@/components/KillSwitchPanel";
import { useSession } from "@/lib/useSession";
import {
  Badge,
  Card,
  EmptyListItem,
  ErrorBanner,
  PageTitle,
  SectionHeading,
  actionLinkClass,
  backLinkClass,
  compactButtonClass,
  compactSecondaryButtonClass,
  dangerLinkClass,
  fieldClassCompact,
  mutedLinkClass,
  primaryButtonClass,
  statusTone,
} from "@/components/ui";

const NEXT_STATUS: Partial<Record<TaskStatus, TaskStatus>> = {
  TODO: "IN_PROGRESS",
  IN_PROGRESS: "DONE",
};

const OTHER_ROLE: Record<WorkspaceRole, WorkspaceRole> = {
  member: "workspace_admin",
  workspace_admin: "member",
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

interface DecisionDraft {
  variant: string;
  tradeoff: string;
  decision: string;
  reason: string;
}

const EMPTY_DECISION_DRAFT: DecisionDraft = { variant: "", tradeoff: "", decision: "", reason: "" };

export default function WorkspacePage() {
  const params = useParams<{ id: string }>();
  const workspaceId = params.id;
  const sessionId = useSession();
  const router = useRouter();

  const [workspaceName, setWorkspaceName] = useState<string | null>(null);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatusOut | null>(null);
  const [killSwitchReason, setKillSwitchReason] = useState("");
  const [engagingKillSwitch, setEngagingKillSwitch] = useState(false);
  const [tasks, setTasks] = useState<TaskOut[] | null>(null);
  const [actions, setActions] = useState<ActionOut[] | null>(null);
  const [notifications, setNotifications] = useState<NotificationOut[] | null>(null);
  const [members, setMembers] = useState<WorkspaceMemberOut[] | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEventOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDueDate, setNewTaskDueDate] = useState("");
  const [creatingTask, setCreatingTask] = useState(false);
  const [planPeriod, setPlanPeriod] = useState<TaskPlanPeriod>("daily");
  const [plan, setPlan] = useState<TaskOut[] | null>(null);
  const [archivingWorkspace, setArchivingWorkspace] = useState(false);
  const [openTaskHistory, setOpenTaskHistory] = useState<Record<string, TaskHistoryEntryOut[]>>({});
  const [openTaskDecisions, setOpenTaskDecisions] = useState<Record<string, TaskDecisionOut[]>>({});
  const [decisionDrafts, setDecisionDrafts] = useState<Record<string, DecisionDraft>>({});
  const [recordingDecisionFor, setRecordingDecisionFor] = useState<string | null>(null);
  const [openTaskReminders, setOpenTaskReminders] = useState<Record<string, ReminderOut[]>>({});
  const [reminderDrafts, setReminderDrafts] = useState<Record<string, string>>({});
  const [requestingReminderFor, setRequestingReminderFor] = useState<string | null>(null);
  const [openTaskAttachments, setOpenTaskAttachments] = useState<Record<string, TaskAttachmentOut[]>>({});
  const [attachDrafts, setAttachDrafts] = useState<Record<string, string>>({});
  const [attachingFor, setAttachingFor] = useState<string | null>(null);
  const [detachingAttachmentId, setDetachingAttachmentId] = useState<string | null>(null);
  const [traceIdInput, setTraceIdInput] = useState("");
  const [appliedTraceId, setAppliedTraceId] = useState("");
  const [cancellingActionId, setCancellingActionId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentOut[] | null>(null);
  const [uploadingDocument, setUploadingDocument] = useState(false);
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);
  const documentFileInputRef = useRef<HTMLInputElement>(null);
  const [documentSearchQuery, setDocumentSearchQuery] = useState("");
  const [documentSearchResults, setDocumentSearchResults] = useState<DocumentChunkOut[] | null>(null);
  const [searchingDocuments, setSearchingDocuments] = useState(false);
  // FR-KNW-009: one shared hidden file input, re-targeted per click
  // rather than one ref per row (the document list is rendered
  // dynamically, so a fixed set of refs doesn't fit).
  const versionFileInputRef = useRef<HTMLInputElement>(null);
  const [versionTargetDocumentId, setVersionTargetDocumentId] = useState<string | null>(null);
  const [versioningDocumentId, setVersioningDocumentId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (sessionId === null) return;
    // Purely a page-title lookup (same /v1/me/workspaces the workspaces
    // list already reads workspace_name from) — this page has no
    // dedicated "get one workspace" endpoint, so this is the cheapest way
    // to show which workspace the user is actually looking at.
    listMyWorkspaces(sessionId)
      .then((list) => {
        const match = list.find((w) => w.workspace_id === workspaceId);
        if (match) setWorkspaceName(match.workspace_name);
      })
      .catch(() => {});
    getWorkspaceKillSwitch(sessionId, workspaceId).then(setKillSwitch).catch(() => {});
    listTasks(sessionId, workspaceId)
      .then(setTasks)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Yuklab bo'lmadi."));
    listActions(sessionId, workspaceId).then(setActions).catch(() => {});
    listNotifications(sessionId, workspaceId).then(setNotifications).catch(() => {});
    listWorkspaceMembers(sessionId, workspaceId).then(setMembers).catch(() => {});
    listWorkspaceAudit(sessionId, workspaceId, appliedTraceId || undefined)
      .then(setAuditEvents)
      .catch(() => {});
    listDocuments(sessionId, workspaceId).then(setDocuments).catch(() => {});
  }, [sessionId, workspaceId, appliedTraceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const refreshPlan = useCallback(() => {
    if (sessionId === null) return;
    getTaskPlan(sessionId, workspaceId, planPeriod)
      .then(setPlan)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Rejani yuklab bo'lmadi."));
  }, [sessionId, workspaceId, planPeriod]);

  useEffect(() => {
    refreshPlan();
  }, [refreshPlan]);

  async function handleCreateTask(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || newTaskTitle.trim().length === 0 || creatingTask) return;
    setCreatingTask(true);
    try {
      // <input type="datetime-local"> has no timezone of its own — treated
      // as local time, which Date's own constructor already assumes, so
      // toISOString() below correctly converts it to UTC for the backend.
      const dueDate = newTaskDueDate.trim().length > 0 ? new Date(newTaskDueDate).toISOString() : null;
      await createTask(sessionId, workspaceId, newTaskTitle.trim(), dueDate);
      setNewTaskTitle("");
      setNewTaskDueDate("");
      refresh();
      refreshPlan();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Task yaratib bo'lmadi.");
    } finally {
      setCreatingTask(false);
    }
  }

  async function handleUploadDocument(event: FormEvent) {
    event.preventDefault();
    const file = documentFileInputRef.current?.files?.[0];
    if (sessionId === null || !file || uploadingDocument) return;
    setUploadingDocument(true);
    try {
      await uploadDocument(sessionId, workspaceId, file);
      if (documentFileInputRef.current) documentFileInputRef.current.value = "";
      refresh();
    } catch (err) {
      // FR-KNW-001: a rejected upload (wrong type, too large, content
      // doesn't match its declared type) surfaces its own specific
      // reason here rather than a generic failure message.
      setError(err instanceof ApiError ? err.message : "Faylni yuklab bo'lmadi.");
    } finally {
      setUploadingDocument(false);
    }
  }

  async function handleDownloadDocument(doc: DocumentOut) {
    if (sessionId === null) return;
    try {
      await downloadDocument(sessionId, workspaceId, doc.id, doc.filename);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Faylni yuklab bo'lmadi.");
    }
  }

  async function handleDeleteDocument(doc: DocumentOut) {
    if (sessionId === null || deletingDocumentId !== null) return;
    setDeletingDocumentId(doc.id);
    try {
      await deleteDocument(sessionId, workspaceId, doc.id);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Faylni o'chirib bo'lmadi.");
    } finally {
      setDeletingDocumentId(null);
    }
  }

  function handleVersionButtonClick(doc: DocumentOut) {
    if (versioningDocumentId !== null) return;
    setVersionTargetDocumentId(doc.id);
    versionFileInputRef.current?.click();
  }

  async function handleVersionFileSelected(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    const targetId = versionTargetDocumentId;
    // Reset so picking the same filename again still fires onChange.
    event.target.value = "";
    if (sessionId === null || !file || targetId === null) return;
    setVersioningDocumentId(targetId);
    try {
      await uploadDocumentVersion(sessionId, workspaceId, targetId, file);
      refresh();
    } catch (err) {
      // FR-KNW-009: versioning an already-superseded document returns a
      // specific DOCUMENT_ALREADY_SUPERSEDED message here, not generic.
      setError(err instanceof ApiError ? err.message : "Yangi versiya yuklab bo'lmadi.");
    } finally {
      setVersioningDocumentId(null);
      setVersionTargetDocumentId(null);
    }
  }

  async function handleSearchDocuments(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || searchingDocuments || documentSearchQuery.trim() === "") return;
    setSearchingDocuments(true);
    try {
      setDocumentSearchResults(await searchDocuments(sessionId, workspaceId, documentSearchQuery));
    } catch (err) {
      // FR-KNW-003: no embedding provider configured surfaces its own
      // clear 503 message here, not a generic failure.
      setError(err instanceof ApiError ? err.message : "Qidiruvni bajarib bo'lmadi.");
    } finally {
      setSearchingDocuments(false);
    }
  }

  function handleClearDocumentSearch() {
    setDocumentSearchQuery("");
    setDocumentSearchResults(null);
  }

  async function handleCancelAction(action: ActionOut) {
    if (sessionId === null || cancellingActionId !== null) return;
    setCancellingActionId(action.id);
    try {
      await cancelAction(sessionId, workspaceId, action.id);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action'ni bekor qilib bo'lmadi.");
    } finally {
      setCancellingActionId(null);
    }
  }

  async function handleAdvanceTask(task: TaskOut) {
    if (sessionId === null) return;
    const next = NEXT_STATUS[task.status];
    if (!next) return;
    try {
      await changeTaskStatus(sessionId, workspaceId, task.id, next);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Task holatini o'zgartirib bo'lmadi.");
    }
  }

  async function toggleTaskHistory(task: TaskOut) {
    if (sessionId === null) return;
    if (openTaskHistory[task.id] !== undefined) {
      setOpenTaskHistory((prev) => {
        const next = { ...prev };
        delete next[task.id];
        return next;
      });
      return;
    }
    try {
      const history = await getTaskHistory(sessionId, workspaceId, task.id);
      setOpenTaskHistory((prev) => ({ ...prev, [task.id]: history }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Tarixni yuklab bo'lmadi.");
    }
  }

  async function toggleTaskDecisions(task: TaskOut) {
    if (sessionId === null) return;
    if (openTaskDecisions[task.id] !== undefined) {
      setOpenTaskDecisions((prev) => {
        const next = { ...prev };
        delete next[task.id];
        return next;
      });
      return;
    }
    try {
      const decisions = await getTaskDecisions(sessionId, workspaceId, task.id);
      setOpenTaskDecisions((prev) => ({ ...prev, [task.id]: decisions }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Qarorlarni yuklab bo'lmadi.");
    }
  }

  function updateDecisionDraft(taskId: string, field: keyof DecisionDraft, value: string) {
    setDecisionDrafts((prev) => ({
      ...prev,
      [taskId]: { ...(prev[taskId] ?? EMPTY_DECISION_DRAFT), [field]: value },
    }));
  }

  async function handleRecordDecision(task: TaskOut) {
    if (sessionId === null || recordingDecisionFor !== null) return;
    const draft = decisionDrafts[task.id] ?? EMPTY_DECISION_DRAFT;
    if (![draft.variant, draft.tradeoff, draft.decision, draft.reason].every((v) => v.trim().length > 0)) {
      return;
    }
    setRecordingDecisionFor(task.id);
    try {
      // FR-TASK-003: this always inserts a new version, it never edits an
      // earlier decision — re-fetching below shows the full history,
      // oldest first, including the one just recorded.
      await recordTaskDecision(sessionId, workspaceId, task.id, draft);
      setDecisionDrafts((prev) => ({ ...prev, [task.id]: EMPTY_DECISION_DRAFT }));
      const decisions = await getTaskDecisions(sessionId, workspaceId, task.id);
      setOpenTaskDecisions((prev) => ({ ...prev, [task.id]: decisions }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Qarorni saqlab bo'lmadi.");
    } finally {
      setRecordingDecisionFor(null);
    }
  }

  async function toggleTaskReminders(task: TaskOut) {
    if (sessionId === null) return;
    if (openTaskReminders[task.id] !== undefined) {
      setOpenTaskReminders((prev) => {
        const next = { ...prev };
        delete next[task.id];
        return next;
      });
      return;
    }
    try {
      const reminders = await getTaskReminders(sessionId, workspaceId, task.id);
      setOpenTaskReminders((prev) => ({ ...prev, [task.id]: reminders }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eslatmalarni yuklab bo'lmadi.");
    }
  }

  async function handleRequestReminder(task: TaskOut) {
    if (sessionId === null || requestingReminderFor !== null) return;
    const remindAt = reminderDrafts[task.id];
    if (!remindAt) return;
    setRequestingReminderFor(task.id);
    try {
      // FR-TASK-005: this only creates a PENDING_CONFIRMATION request —
      // it never fires or notifies anyone until confirmed below.
      await requestTaskReminder(sessionId, workspaceId, task.id, new Date(remindAt).toISOString());
      setReminderDrafts((prev) => ({ ...prev, [task.id]: "" }));
      const reminders = await getTaskReminders(sessionId, workspaceId, task.id);
      setOpenTaskReminders((prev) => ({ ...prev, [task.id]: reminders }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eslatma so'rovini yuborib bo'lmadi.");
    } finally {
      setRequestingReminderFor(null);
    }
  }

  async function handleConfirmReminder(task: TaskOut, reminder: ReminderOut) {
    if (sessionId === null) return;
    try {
      // Echoes back the reminder's own current remind_at — the exact
      // time is what's being confirmed, not just the id.
      await confirmTaskReminder(sessionId, workspaceId, task.id, reminder.id, reminder.remind_at);
      const reminders = await getTaskReminders(sessionId, workspaceId, task.id);
      setOpenTaskReminders((prev) => ({ ...prev, [task.id]: reminders }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eslatmani tasdiqlab bo'lmadi.");
    }
  }

  async function handleCancelReminder(task: TaskOut, reminder: ReminderOut) {
    if (sessionId === null) return;
    try {
      await cancelTaskReminder(sessionId, workspaceId, task.id, reminder.id);
      const reminders = await getTaskReminders(sessionId, workspaceId, task.id);
      setOpenTaskReminders((prev) => ({ ...prev, [task.id]: reminders }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eslatmani bekor qilib bo'lmadi.");
    }
  }

  async function toggleTaskAttachments(task: TaskOut) {
    if (sessionId === null) return;
    if (openTaskAttachments[task.id] !== undefined) {
      setOpenTaskAttachments((prev) => {
        const next = { ...prev };
        delete next[task.id];
        return next;
      });
      return;
    }
    try {
      const attachments = await getTaskAttachments(sessionId, workspaceId, task.id);
      setOpenTaskAttachments((prev) => ({ ...prev, [task.id]: attachments }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ilovalarni yuklab bo'lmadi.");
    }
  }

  async function handleAttachDocument(task: TaskOut) {
    if (sessionId === null || attachingFor !== null) return;
    const documentId = attachDrafts[task.id];
    if (!documentId) return;
    setAttachingFor(task.id);
    try {
      const attachment = await attachTaskDocument(sessionId, workspaceId, task.id, documentId);
      setAttachDrafts((prev) => ({ ...prev, [task.id]: "" }));
      setOpenTaskAttachments((prev) => ({
        ...prev,
        [task.id]: [...(prev[task.id] ?? []), attachment],
      }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Faylni task'ga bog'lab bo'lmadi.");
    } finally {
      setAttachingFor(null);
    }
  }

  async function handleDetachDocument(task: TaskOut, attachment: TaskAttachmentOut) {
    if (sessionId === null || detachingAttachmentId !== null) return;
    setDetachingAttachmentId(attachment.id);
    try {
      await detachTaskDocument(sessionId, workspaceId, task.id, attachment.id);
      setOpenTaskAttachments((prev) => ({
        ...prev,
        [task.id]: (prev[task.id] ?? []).filter((a) => a.id !== attachment.id),
      }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bog'lanishni uzib bo'lmadi.");
    } finally {
      setDetachingAttachmentId(null);
    }
  }

  async function handleToggleMemberRole(member: WorkspaceMemberOut) {
    if (sessionId === null || member.membership_id === null) return;
    try {
      await changeWorkspaceMemberRole(
        sessionId,
        workspaceId,
        member.membership_id,
        OTHER_ROLE[member.role as WorkspaceRole],
      );
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Rolni o'zgartirib bo'lmadi.");
    }
  }

  async function handleRemoveMember(member: WorkspaceMemberOut) {
    if (sessionId === null || member.membership_id === null) return;
    try {
      await removeWorkspaceMember(sessionId, workspaceId, member.membership_id);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "A'zoni chiqarib bo'lmadi.");
    }
  }

  async function handleMarkRead(notification: NotificationOut) {
    if (sessionId === null) return;
    await markNotificationRead(sessionId, workspaceId, notification.id).catch(() => {});
    refresh();
  }

  async function handleEngageKillSwitch(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || killSwitchReason.trim().length === 0 || engagingKillSwitch) return;
    setEngagingKillSwitch(true);
    try {
      await engageWorkspaceKillSwitch(sessionId, workspaceId, killSwitchReason.trim());
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
      await disengageWorkspaceKillSwitch(sessionId, workspaceId);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kill switch'ni o'chirib bo'lmadi.");
    }
  }

  async function handleArchiveWorkspace() {
    if (sessionId === null || archivingWorkspace) return;
    // Archiving removes this workspace from GET /v1/me/workspaces and this
    // page immediately denies access to it (get_workspace_context) — the
    // only way back is the customer page's "Arxivlangan workspace'lar"
    // list, so this needs an explicit, unmissable confirmation up front.
    if (!window.confirm("Bu workspace'ni arxivlashni tasdiqlaysizmi? Uni faqat customer sahifasidan tiklash mumkin bo'ladi.")) {
      return;
    }
    setArchivingWorkspace(true);
    try {
      await archiveWorkspace(sessionId, workspaceId);
      router.replace("/workspaces");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Workspace'ni arxivlab bo'lmadi.");
      setArchivingWorkspace(false);
    }
  }

  if (sessionId === null) return null;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 space-y-8 p-6">
      <div className="flex items-center justify-between">
        <Link href="/workspaces" className={backLinkClass}>
          <span aria-hidden="true">&larr;</span> Workspace&apos;lar
        </Link>
        <div className="flex items-center gap-4">
          <Link
            href={`/workspaces/${workspaceId}/chat`}
            className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline dark:text-blue-400 dark:hover:text-blue-300"
          >
            Chat
          </Link>
          <button onClick={handleArchiveWorkspace} disabled={archivingWorkspace} className={dangerLinkClass}>
            Workspace&apos;ni arxivlash
          </button>
        </div>
      </div>

      <PageTitle>{workspaceName ?? "Workspace"}</PageTitle>

      <KillSwitchPanel
        killSwitch={killSwitch}
        reason={killSwitchReason}
        onReasonChange={setKillSwitchReason}
        engaging={engagingKillSwitch}
        onEngage={handleEngageKillSwitch}
        onDisengage={handleDisengageKillSwitch}
        blockedNote="Yangi action'lar bloklangan"
      />

      {error && <ErrorBanner>{error}</ErrorBanner>}

      <Card as="section">
        <SectionHeading className="mb-3">Task&apos;lar</SectionHeading>
        <form onSubmit={handleCreateTask} className="mb-3 flex flex-wrap gap-2">
          <input
            type="text"
            value={newTaskTitle}
            onChange={(event) => setNewTaskTitle(event.target.value)}
            placeholder="Yangi task nomi"
            className={`${fieldClassCompact} min-w-[12rem] flex-1`}
          />
          <input
            type="datetime-local"
            aria-label="Muddat (ixtiyoriy)"
            value={newTaskDueDate}
            onChange={(event) => setNewTaskDueDate(event.target.value)}
            className={fieldClassCompact}
          />
          <button type="submit" disabled={newTaskTitle.trim().length === 0 || creatingTask} className={primaryButtonClass}>
            Qo&apos;shish
          </button>
        </form>

        <div
          data-testid="task-plan"
          className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-950/40"
        >
          <div className="mb-2 flex items-center gap-2">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200">Reja</h3>
            <select
              aria-label="Reja davri"
              value={planPeriod}
              onChange={(event) => setPlanPeriod(event.target.value as TaskPlanPeriod)}
              className="rounded border border-gray-200 bg-white px-1.5 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-900/10 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
            >
              <option value="daily">Kunlik</option>
              <option value="weekly">Haftalik</option>
            </select>
          </div>
          <ul className="space-y-1">
            {plan?.map((task) => (
              <li key={task.id} className="flex items-center justify-between text-xs">
                <span className="text-gray-700 dark:text-gray-300">{task.title}</span>
                <span className="text-gray-500 dark:text-gray-400">
                  {task.due_date ? new Date(task.due_date).toLocaleString() : ""}
                </span>
              </li>
            ))}
          </ul>
          {plan !== null && plan.length === 0 && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Bu davr uchun muddatli task yo&apos;q.
            </p>
          )}
        </div>
        <ul data-testid="task-list" className="space-y-2">
          {tasks?.map((task) => (
            <li
              key={task.id}
              className="rounded-lg border border-gray-200 px-3 py-2.5 dark:border-gray-800"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span
                  className={
                    task.status === "DONE"
                      ? "text-gray-400 line-through dark:text-gray-500"
                      : "text-gray-900 dark:text-gray-100"
                  }
                >
                  {task.title}
                </span>
                <div className="flex flex-wrap items-center gap-3">
                  <Badge tone={statusTone(task.status)}>{task.status}</Badge>
                  {NEXT_STATUS[task.status] && (
                    <button onClick={() => handleAdvanceTask(task)} className={actionLinkClass}>
                      {NEXT_STATUS[task.status]} qilish
                    </button>
                  )}
                  <button onClick={() => toggleTaskHistory(task)} className={mutedLinkClass}>
                    {openTaskHistory[task.id] !== undefined ? "Tarixni yashirish" : "Tarix"}
                  </button>
                  <button onClick={() => toggleTaskDecisions(task)} className={mutedLinkClass}>
                    {openTaskDecisions[task.id] !== undefined ? "Qarorlarni yashirish" : "Qarorlar"}
                  </button>
                  <button onClick={() => toggleTaskReminders(task)} className={mutedLinkClass}>
                    {openTaskReminders[task.id] !== undefined ? "Eslatmalarni yashirish" : "Eslatmalar"}
                  </button>
                  <button onClick={() => toggleTaskAttachments(task)} className={mutedLinkClass}>
                    {openTaskAttachments[task.id] !== undefined ? "Fayllarni yashirish" : "Bog'langan fayllar"}
                  </button>
                </div>
              </div>
              {openTaskHistory[task.id] !== undefined && (
                <ul className="mt-2 space-y-1 border-t border-gray-100 pt-2 dark:border-gray-800">
                  {openTaskHistory[task.id].map((entry) => (
                    <li key={entry.id} className="text-xs text-gray-500 dark:text-gray-400">
                      {entry.from_status ?? "—"} &rarr; {entry.to_status} ({entry.actor_id},{" "}
                      {new Date(entry.created_at).toLocaleString()})
                    </li>
                  ))}
                  {openTaskHistory[task.id].length === 0 && (
                    <EmptyListItem>Tarix bo&apos;sh.</EmptyListItem>
                  )}
                </ul>
              )}
              {openTaskDecisions[task.id] !== undefined && (
                <div className="mt-2 space-y-2 border-t border-gray-100 pt-2 dark:border-gray-800">
                  <ul className="space-y-1">
                    {openTaskDecisions[task.id].map((entry) => (
                      <li key={entry.id} className="text-xs text-gray-500 dark:text-gray-400">
                        <span className="font-medium text-gray-700 dark:text-gray-200">{entry.decision}</span>{" "}
                        —{" "}
                        {entry.variant} ({entry.actor_id}, {new Date(entry.created_at).toLocaleString()})
                        <div className="text-gray-500 dark:text-gray-500">
                          {entry.tradeoff} · {entry.reason}
                        </div>
                      </li>
                    ))}
                    {openTaskDecisions[task.id].length === 0 && (
                      <EmptyListItem>Hali qaror yozilmagan.</EmptyListItem>
                    )}
                  </ul>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      handleRecordDecision(task);
                    }}
                    className="space-y-1.5"
                  >
                    <input
                      aria-label="Variant"
                      placeholder="Variant"
                      value={decisionDrafts[task.id]?.variant ?? ""}
                      onChange={(event) => updateDecisionDraft(task.id, "variant", event.target.value)}
                      className={`${fieldClassCompact} w-full`}
                    />
                    <input
                      aria-label="Kelishuv (tradeoff)"
                      placeholder="Tradeoff"
                      value={decisionDrafts[task.id]?.tradeoff ?? ""}
                      onChange={(event) => updateDecisionDraft(task.id, "tradeoff", event.target.value)}
                      className={`${fieldClassCompact} w-full`}
                    />
                    <input
                      aria-label="Qaror"
                      placeholder="Qaror"
                      value={decisionDrafts[task.id]?.decision ?? ""}
                      onChange={(event) => updateDecisionDraft(task.id, "decision", event.target.value)}
                      className={`${fieldClassCompact} w-full`}
                    />
                    <input
                      aria-label="Sabab"
                      placeholder="Sabab"
                      value={decisionDrafts[task.id]?.reason ?? ""}
                      onChange={(event) => updateDecisionDraft(task.id, "reason", event.target.value)}
                      className={`${fieldClassCompact} w-full`}
                    />
                    <button
                      type="submit"
                      disabled={recordingDecisionFor === task.id}
                      className={actionLinkClass}
                    >
                      Qaror yozish
                    </button>
                  </form>
                </div>
              )}
              {openTaskReminders[task.id] !== undefined && (
                <div className="mt-2 space-y-2 border-t border-gray-100 pt-2 dark:border-gray-800">
                  <ul data-testid="reminder-list" className="space-y-1">
                    {openTaskReminders[task.id].map((reminder) => (
                      <li key={reminder.id} className="text-xs text-gray-500 dark:text-gray-400">
                        {new Date(reminder.remind_at).toLocaleString()} — {reminder.status}
                        {reminder.status === "PENDING_CONFIRMATION" && (
                          <>
                            {" "}
                            <button
                              onClick={() => handleConfirmReminder(task, reminder)}
                              className={actionLinkClass}
                            >
                              Tasdiqlash
                            </button>{" "}
                            <button
                              onClick={() => handleCancelReminder(task, reminder)}
                              className={dangerLinkClass}
                            >
                              Bekor qilish
                            </button>
                          </>
                        )}
                        {reminder.status === "CONFIRMED" && (
                          <>
                            {" "}
                            <button
                              onClick={() => handleCancelReminder(task, reminder)}
                              className={dangerLinkClass}
                            >
                              Bekor qilish
                            </button>
                          </>
                        )}
                      </li>
                    ))}
                    {openTaskReminders[task.id].length === 0 && (
                      <EmptyListItem>Hali eslatma yo&apos;q.</EmptyListItem>
                    )}
                  </ul>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      handleRequestReminder(task);
                    }}
                    className="flex flex-wrap items-center gap-2"
                  >
                    <input
                      aria-label="Eslatma vaqti"
                      type="datetime-local"
                      value={reminderDrafts[task.id] ?? ""}
                      onChange={(event) =>
                        setReminderDrafts((prev) => ({ ...prev, [task.id]: event.target.value }))
                      }
                      className={fieldClassCompact}
                    />
                    <button
                      type="submit"
                      disabled={requestingReminderFor === task.id || !reminderDrafts[task.id]}
                      className={actionLinkClass}
                    >
                      Eslatma so&apos;rash
                    </button>
                  </form>
                </div>
              )}
              {openTaskAttachments[task.id] !== undefined && (
                <div className="mt-2 space-y-2 border-t border-gray-100 pt-2 dark:border-gray-800">
                  <ul data-testid="attachment-list" className="space-y-1">
                    {openTaskAttachments[task.id].map((attachment) => (
                      <li key={attachment.id} className="text-xs text-gray-500 dark:text-gray-400">
                        {attachment.broken ? (
                          <span className="font-medium text-red-600 dark:text-red-400">
                            Uzilgan havola (fayl o&apos;chirilgan)
                          </span>
                        ) : (
                          <>
                            {attachment.filename}
                            {attachment.size_bytes !== null && ` (${formatFileSize(attachment.size_bytes)})`}
                          </>
                        )}{" "}
                        <button
                          onClick={() => handleDetachDocument(task, attachment)}
                          disabled={detachingAttachmentId === attachment.id}
                          className={dangerLinkClass}
                        >
                          Uzish
                        </button>
                      </li>
                    ))}
                    {openTaskAttachments[task.id].length === 0 && (
                      <EmptyListItem>Hech qanday fayl bog&apos;lanmagan.</EmptyListItem>
                    )}
                  </ul>
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      handleAttachDocument(task);
                    }}
                    className="flex flex-wrap items-center gap-2"
                  >
                    <select
                      aria-label="Bog'lanadigan fayl"
                      value={attachDrafts[task.id] ?? ""}
                      onChange={(event) =>
                        setAttachDrafts((prev) => ({ ...prev, [task.id]: event.target.value }))
                      }
                      className={fieldClassCompact}
                    >
                      <option value="">Fayl tanlang...</option>
                      {documents?.map((doc) => (
                        <option key={doc.id} value={doc.id}>
                          {doc.filename}
                        </option>
                      ))}
                    </select>
                    <button
                      type="submit"
                      disabled={attachingFor === task.id || !attachDrafts[task.id]}
                      className={actionLinkClass}
                    >
                      Bog&apos;lash
                    </button>
                  </form>
                </div>
              )}
            </li>
          ))}
          {tasks !== null && tasks.length === 0 && <EmptyListItem>Hali task yo&apos;q.</EmptyListItem>}
        </ul>
      </Card>

      <Card as="section">
        <SectionHeading className="mb-3">Fayllar</SectionHeading>
        <form onSubmit={handleUploadDocument} className="mb-3 flex flex-wrap items-center gap-2">
          <input
            ref={documentFileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.txt,.png,.jpg,.jpeg"
            aria-label="Yuklanadigan fayl"
            className="text-sm text-gray-700 dark:text-gray-300"
          />
          <button type="submit" disabled={uploadingDocument} className={compactButtonClass + " bg-blue-600 text-white hover:bg-blue-700 focus-visible:ring-blue-600"}>
            Yuklash
          </button>
        </form>
        <form onSubmit={handleSearchDocuments} className="mb-3 flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={documentSearchQuery}
            onChange={(e) => setDocumentSearchQuery(e.target.value)}
            placeholder="Fayllar ichidan qidirish..."
            aria-label="Fayllar ichidan qidirish"
            className={`${fieldClassCompact} w-64`}
          />
          <button
            type="submit"
            disabled={searchingDocuments || documentSearchQuery.trim() === ""}
            className={`${compactButtonClass} bg-gray-700 text-white hover:bg-gray-600 focus-visible:ring-gray-700`}
          >
            Qidirish
          </button>
          {documentSearchResults !== null && (
            <button type="button" onClick={handleClearDocumentSearch} className={actionLinkClass}>
              Tozalash
            </button>
          )}
        </form>
        {documentSearchResults !== null && (
          <ul data-testid="document-search-results" className="mb-4 space-y-2">
            {documentSearchResults.map((chunk) => (
              <li
                key={chunk.id}
                className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700 dark:border-gray-800 dark:bg-gray-950/40 dark:text-gray-300"
              >
                {chunk.content}
              </li>
            ))}
            {documentSearchResults.length === 0 && <EmptyListItem>Hech narsa topilmadi.</EmptyListItem>}
          </ul>
        )}
        <input
          ref={versionFileInputRef}
          type="file"
          accept=".pdf,.docx,.xlsx,.txt,.png,.jpg,.jpeg"
          aria-label="Yangi versiya fayli"
          className="hidden"
          onChange={handleVersionFileSelected}
        />
        <ul data-testid="document-list" className="space-y-2">
          {documents?.map((doc) => (
            <li
              key={doc.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-800"
            >
              <div className="flex flex-col">
                <span className="text-gray-900 dark:text-gray-100">
                  {doc.filename}
                  {doc.superseded_by_id !== null && (
                    <span
                      data-testid="document-superseded-badge"
                      className="ml-2 inline-flex items-center rounded-full bg-gray-200 px-1.5 py-0.5 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                    >
                      Almashtirilgan
                    </span>
                  )}
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {doc.content_type} · {formatFileSize(doc.size_bytes)}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <button type="button" onClick={() => handleDownloadDocument(doc)} className={actionLinkClass}>
                  Yuklab olish
                </button>
                {doc.superseded_by_id === null && (
                  <button
                    type="button"
                    onClick={() => handleVersionButtonClick(doc)}
                    disabled={versioningDocumentId === doc.id}
                    className={actionLinkClass}
                  >
                    Yangi versiya yuklash
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleDeleteDocument(doc)}
                  disabled={deletingDocumentId === doc.id}
                  className={dangerLinkClass}
                >
                  O&apos;chirish
                </button>
              </div>
            </li>
          ))}
          {documents !== null && documents.length === 0 && <EmptyListItem>Hali fayl yo&apos;q.</EmptyListItem>}
        </ul>
      </Card>

      <Card as="section">
        <SectionHeading className="mb-3">Action&apos;lar</SectionHeading>
        <ul className="space-y-2">
          {actions?.map((action) => (
            <li
              key={action.id}
              className="rounded-lg border border-gray-200 px-3 py-2.5 text-sm dark:border-gray-800"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex flex-col">
                  <span className="text-gray-900 dark:text-gray-100">{action.tool_name}</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">risk: {action.risk_level}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Badge tone={statusTone(action.status)}>{action.status}</Badge>
                  {/* FR-ACT-009: READY cancels outright, RUNNING requests a
                      reversal (COMPENSATING) — the backend decides which,
                      this button just calls the one cancel endpoint. */}
                  {(action.status === "READY" || action.status === "RUNNING") && (
                    <button
                      type="button"
                      onClick={() => handleCancelAction(action)}
                      disabled={cancellingActionId === action.id}
                      className={dangerLinkClass}
                    >
                      Bekor qilish
                    </button>
                  )}
                </div>
              </div>
              {/* FR-ACT-002: dry-run preview shown for every action, R3+ included. */}
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{action.preview}</p>
            </li>
          ))}
          {actions !== null && actions.length === 0 && <EmptyListItem>Hali action yo&apos;q.</EmptyListItem>}
        </ul>
      </Card>

      <Card as="section">
        <SectionHeading className="mb-3">Bildirishnomalar</SectionHeading>
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
        <SectionHeading className="mb-3">A&apos;zolar</SectionHeading>
        <ul className="space-y-1">
          {members?.map((member) => (
            <li
              key={member.membership_id ?? member.user_id}
              className="flex items-center justify-between gap-2 py-1 text-sm"
            >
              <span className="text-gray-900 dark:text-gray-100">{member.display_name}</span>
              <div className="flex items-center gap-3">
                <Badge>{member.role}</Badge>
                {member.membership_id !== null && (
                  <>
                    <button onClick={() => handleToggleMemberRole(member)} className={actionLinkClass}>
                      {OTHER_ROLE[member.role as WorkspaceRole]} qilish
                    </button>
                    <button onClick={() => handleRemoveMember(member)} className={dangerLinkClass}>
                      Chiqarish
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card as="section">
        <SectionHeading className="mb-3">Audit</SectionHeading>
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
        </form>
        <ul className="space-y-2">
          {auditEvents?.map((event) => (
            <li
              key={event.id}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm dark:border-gray-800"
            >
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
