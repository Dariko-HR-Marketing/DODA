"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ApiError,
  clearWorkspaceAiPreference,
  createConversation,
  deleteConversation,
  getWorkspaceAiPreference,
  getWorkspaceLanguageSetting,
  listConversationMessages,
  listConversations,
  regenerateConversationMessage,
  searchConversations,
  setWorkspaceAiPreference,
  setWorkspaceLanguageSetting,
  streamConversationMessage,
  switchConversationLanguage,
  switchConversationProvider,
  AI_LANGUAGES,
  AI_PROVIDERS,
  type AiLanguage,
  type AiPreferenceOut,
  type AiProvider,
  type ChatMode,
  type ConversationOut,
  type MessageOut,
  type WorkspaceLanguageSettingOut,
} from "@/lib/api";
import { useSession } from "@/lib/useSession";
import {
  Card,
  ErrorBanner,
  actionLinkClass,
  backLinkClass,
  compactSecondaryButtonClass,
  dangerLinkClass,
  fieldClass,
  fieldClassCompact,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui";

const CHAT_MODES: ChatMode[] = ["FAST", "STANDARD", "DEEP"];

export default function ChatPage() {
  const params = useParams<{ id: string }>();
  const workspaceId = params.id;
  const sessionId = useSession();

  const [conversations, setConversations] = useState<ConversationOut[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageOut[] | null>(null);
  const [composerText, setComposerText] = useState("");
  const [mode, setMode] = useState<ChatMode>("STANDARD");
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [creatingConversation, setCreatingConversation] = useState(false);
  const [deletingConversation, setDeletingConversation] = useState(false);
  const [pinProvider, setPinProvider] = useState<AiProvider>("OPENAI");
  const [pinModel, setPinModel] = useState("");
  const [pinning, setPinning] = useState(false);
  const [pinLanguage, setPinLanguage] = useState<AiLanguage>("UZ");
  const [pinningLanguage, setPinningLanguage] = useState(false);
  const [workspacePreference, setWorkspacePreferenceState] = useState<AiPreferenceOut | null>(null);
  const [workspaceProviderChoice, setWorkspaceProviderChoice] = useState<AiProvider>("OPENAI");
  const [workspaceModelChoice, setWorkspaceModelChoice] = useState("");
  const [savingWorkspacePreference, setSavingWorkspacePreference] = useState(false);
  const [workspaceLanguageSetting, setWorkspaceLanguageSettingState] =
    useState<WorkspaceLanguageSettingOut | null>(null);
  const [workspaceLanguageChoice, setWorkspaceLanguageChoice] = useState<AiLanguage>("UZ");
  const [savingWorkspaceLanguage, setSavingWorkspaceLanguage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  // Guards against a stale listConversationMessages() response (kicked off
  // for a conversation the user has since navigated away from, e.g. a
  // handleSend() finally-block refresh for A still in flight when the user
  // clicks "new conversation" and switches to B) overwriting the messages
  // that are correctly displayed for whatever conversation is current by
  // the time it resolves.
  const messagesRequestIdRef = useRef(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<MessageOut[] | null>(null);
  const [searching, setSearching] = useState(false);

  const selected = conversations?.find((c) => c.id === selectedId) ?? null;
  // FR-CONV-007: editing is only offered on the conversation's own latest
  // USER message — matches RegenerationTargetNotLatestError's scoping on
  // the backend exactly, so the UI never invites a request it knows will
  // be rejected (same "don't offer what the backend will reject" posture
  // as the Actions cancel button, which only shows for cancellable states).
  const lastUserMessageId = messages?.findLast((m) => m.role === "USER")?.id ?? null;

  const refreshConversations = useCallback(() => {
    if (sessionId === null) return;
    listConversations(sessionId, workspaceId)
      .then((list) => {
        setConversations(list);
        setSelectedId((current) => current ?? list[0]?.id ?? null);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Suhbatlarni yuklab bo'lmadi."));
  }, [sessionId, workspaceId]);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    if (sessionId === null) return;
    getWorkspaceAiPreference(sessionId, workspaceId).then(setWorkspacePreferenceState).catch(() => {});
  }, [sessionId, workspaceId]);

  useEffect(() => {
    if (sessionId === null) return;
    getWorkspaceLanguageSetting(sessionId, workspaceId).then(setWorkspaceLanguageSettingState).catch(() => {});
  }, [sessionId, workspaceId]);

  const refreshMessages = useCallback(() => {
    if (sessionId === null || selectedId === null) return;
    const requestId = ++messagesRequestIdRef.current;
    listConversationMessages(sessionId, workspaceId, selectedId)
      .then((list) => {
        if (messagesRequestIdRef.current === requestId) setMessages(list);
      })
      .catch((err) => {
        if (messagesRequestIdRef.current === requestId) {
          setError(err instanceof ApiError ? err.message : "Xabarlarni yuklab bo'lmadi.");
        }
      });
  }, [sessionId, workspaceId, selectedId]);

  useEffect(() => {
    refreshMessages();
  }, [refreshMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText, pendingUserText]);

  async function handleNewConversation() {
    if (sessionId === null || creatingConversation) return;
    setCreatingConversation(true);
    try {
      const conversation = await createConversation(sessionId, workspaceId);
      setConversations((prev) => [conversation, ...(prev ?? [])]);
      setSelectedId(conversation.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Suhbat yaratib bo'lmadi.");
    } finally {
      setCreatingConversation(false);
    }
  }

  async function handleDeleteConversation(conversationId: string) {
    if (sessionId === null || deletingConversation) return;
    if (!window.confirm("Bu suhbatni butunlay o'chirishni tasdiqlaysizmi? Bu amalni qaytarib bo'lmaydi.")) {
      return;
    }
    setDeletingConversation(true);
    try {
      await deleteConversation(sessionId, workspaceId, conversationId);
      setConversations((prev) => prev?.filter((c) => c.id !== conversationId) ?? null);
      setSelectedId((current) => (current === conversationId ? null : current));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Suhbatni o'chirib bo'lmadi.");
    } finally {
      setDeletingConversation(false);
    }
  }

  // Every "pin"/"set"/"clear" preference handler below shares the same
  // shape (skip if already in flight -> flip a busy flag -> await one
  // call -> update local state, or fall back to a handler-specific error
  // message -> always clear the busy flag) — consolidated so each handler
  // states only what varies: the busy flag and the actual call.
  async function runGuarded(
    busy: boolean,
    setBusy: (value: boolean) => void,
    action: () => Promise<void>,
    fallbackMessage: string,
  ): Promise<void> {
    if (busy) return;
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : fallbackMessage);
    } finally {
      setBusy(false);
    }
  }

  async function handlePinProvider(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || selectedId === null) return;
    await runGuarded(
      pinning,
      setPinning,
      async () => {
        const updated = await switchConversationProvider(
          sessionId,
          workspaceId,
          selectedId,
          pinProvider,
          pinModel.trim().length > 0 ? pinModel.trim() : null,
        );
        setConversations((prev) => prev?.map((c) => (c.id === updated.id ? updated : c)) ?? null);
      },
      "Provayderni o'rnatib bo'lmadi.",
    );
  }

  async function handlePinLanguage(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || selectedId === null) return;
    await runGuarded(
      pinningLanguage,
      setPinningLanguage,
      async () => {
        const updated = await switchConversationLanguage(sessionId, workspaceId, selectedId, pinLanguage);
        setConversations((prev) => prev?.map((c) => (c.id === updated.id ? updated : c)) ?? null);
      },
      "Tilni o'rnatib bo'lmadi.",
    );
  }

  async function handleClearPinnedLanguage() {
    if (sessionId === null || selectedId === null) return;
    await runGuarded(
      pinningLanguage,
      setPinningLanguage,
      async () => {
        const updated = await switchConversationLanguage(sessionId, workspaceId, selectedId, null);
        setConversations((prev) => prev?.map((c) => (c.id === updated.id ? updated : c)) ?? null);
      },
      "Tilni tozalab bo'lmadi.",
    );
  }

  async function handleSetWorkspacePreference(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null) return;
    await runGuarded(
      savingWorkspacePreference,
      setSavingWorkspacePreference,
      async () => {
        const updated = await setWorkspaceAiPreference(
          sessionId,
          workspaceId,
          workspaceProviderChoice,
          workspaceModelChoice.trim().length > 0 ? workspaceModelChoice.trim() : null,
        );
        setWorkspacePreferenceState(updated);
      },
      "Workspace AI afzalligini saqlab bo'lmadi.",
    );
  }

  async function handleClearWorkspacePreference() {
    if (sessionId === null) return;
    await runGuarded(
      savingWorkspacePreference,
      setSavingWorkspacePreference,
      async () => {
        await clearWorkspaceAiPreference(sessionId, workspaceId);
        setWorkspacePreferenceState({ provider: null, model: null });
      },
      "Workspace AI afzalligini tozalab bo'lmadi.",
    );
  }

  async function handleSetWorkspaceLanguage(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null) return;
    await runGuarded(
      savingWorkspaceLanguage,
      setSavingWorkspaceLanguage,
      async () => {
        const updated = await setWorkspaceLanguageSetting(sessionId, workspaceId, workspaceLanguageChoice);
        setWorkspaceLanguageSettingState(updated);
      },
      "Workspace tilini saqlab bo'lmadi.",
    );
  }

  async function handleClearWorkspaceLanguage() {
    if (sessionId === null) return;
    await runGuarded(
      savingWorkspaceLanguage,
      setSavingWorkspaceLanguage,
      async () => {
        const updated = await setWorkspaceLanguageSetting(sessionId, workspaceId, null);
        setWorkspaceLanguageSettingState(updated);
      },
      "Workspace tilini tozalab bo'lmadi.",
    );
  }

  function handleStartEdit(message: MessageOut) {
    if (sending) return;
    setEditingMessageId(message.id);
    setComposerText(message.content);
  }

  function handleCancelEdit() {
    setEditingMessageId(null);
    setComposerText("");
  }

  async function handleSend(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || selectedId === null || sending || composerText.trim().length === 0) return;
    const content = composerText.trim();
    const regeneratingMessageId = editingMessageId;
    setComposerText("");
    setEditingMessageId(null);
    setPendingUserText(content);
    setStreamingText("");
    setSending(true);
    setError(null);
    const controller = new AbortController();
    abortControllerRef.current = controller;
    try {
      // FR-CONV-007: editing the latest user message reuses this exact
      // send loop, just pointed at regenerateConversationMessage instead
      // of streamConversationMessage — both return the same TurnChunk
      // shape, so nothing below this branch needs to know which happened.
      const turns =
        regeneratingMessageId !== null
          ? regenerateConversationMessage(
              sessionId,
              workspaceId,
              selectedId,
              regeneratingMessageId,
              content,
              mode,
              controller.signal,
            )
          : streamConversationMessage(sessionId, workspaceId, selectedId, content, mode, controller.signal);
      for await (const chunk of turns) {
        if (chunk.kind === "text" || chunk.kind === "tool_status") {
          setStreamingText((prev) => (prev ?? "") + chunk.text);
        } else if (chunk.kind === "error") {
          setError(chunk.message);
        }
        // "done" carries the persisted final message, but the simplest,
        // least-duplicative source of truth is re-fetching the real list
        // below once the stream ends — same pattern as every other page's
        // refresh() after a mutation, rather than hand-reconciling state.
      }
    } catch (err) {
      // FR-CONV-002: an aborted fetch (our own Cancel button below) is
      // not a failure — the backend already reconciled the budget and
      // stopped generating; showing it as an error would be misleading.
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setError(err instanceof ApiError ? err.message : "Suhbat davomida xato yuz berdi.");
      }
    } finally {
      abortControllerRef.current = null;
      setSending(false);
      setPendingUserText(null);
      setStreamingText(null);
      refreshMessages();
    }
  }

  function handleCancel() {
    abortControllerRef.current?.abort();
  }

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (sessionId === null || searching) return;
    setSearching(true);
    try {
      const results = await searchConversations(sessionId, workspaceId, searchQuery);
      setSearchResults(results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Qidiruvda xato yuz berdi.");
    } finally {
      setSearching(false);
    }
  }

  function handleClearSearch() {
    setSearchQuery("");
    setSearchResults(null);
  }

  function handleJumpToSearchResult(conversationId: string) {
    setSelectedId(conversationId);
    handleClearSearch();
  }

  if (sessionId === null) return null;

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5 p-6">
      <div className="flex items-center justify-between">
        <Link href={`/workspaces/${workspaceId}`} className={backLinkClass}>
          <span aria-hidden="true">&larr;</span> Workspace
        </Link>
        <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-50">Chat</h1>
      </div>

      {error && <ErrorBanner>{error}</ErrorBanner>}

      <form onSubmit={handleSearch} className="flex items-center gap-2">
        <input
          type="text"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Suhbat tarixini qidirish..."
          className={`${fieldClass} flex-1`}
        />
        <button type="submit" disabled={searching} className={compactSecondaryButtonClass}>
          Qidirish
        </button>
        {searchResults !== null && (
          <button type="button" onClick={handleClearSearch} className={actionLinkClass}>
            Tozalash
          </button>
        )}
      </form>

      {searchResults !== null && (
        <Card className="!p-2">
          {searchResults.length === 0 ? (
            <p className="px-2 py-1 text-sm text-gray-500 dark:text-gray-400">Hech narsa topilmadi.</p>
          ) : (
            <ul className="space-y-1">
              {searchResults.map((message) => (
                <li key={message.id}>
                  <button
                    type="button"
                    onClick={() => handleJumpToSearchResult(message.conversation_id)}
                    className="w-full rounded-lg p-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    <span className="line-clamp-2 text-gray-800 dark:text-gray-200">{message.content}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {(workspacePreference !== null || workspaceLanguageSetting !== null) && (
        <Card className="flex flex-col gap-3 !p-3 text-xs sm:flex-row sm:items-center sm:gap-6">
          {workspacePreference !== null && (
            <form onSubmit={handleSetWorkspacePreference} className="flex flex-wrap items-center gap-2">
              <span className="text-gray-500 dark:text-gray-400">
                Workspace standart AI ({workspacePreference.provider ?? "tizim standart"}
                {workspacePreference.model ? ` / ${workspacePreference.model}` : ""}):
              </span>
              <select
                aria-label="Workspace AI provayderi"
                value={workspaceProviderChoice}
                onChange={(event) => setWorkspaceProviderChoice(event.target.value as AiProvider)}
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
                value={workspaceModelChoice}
                onChange={(event) => setWorkspaceModelChoice(event.target.value)}
                placeholder="model (ixtiyoriy)"
                className={`${fieldClassCompact} w-32`}
              />
              <button type="submit" disabled={savingWorkspacePreference} className={actionLinkClass}>
                Saqlash
              </button>
              {workspacePreference.provider !== null && (
                <button
                  type="button"
                  onClick={handleClearWorkspacePreference}
                  disabled={savingWorkspacePreference}
                  className={dangerLinkClass}
                >
                  Tizim standartga qaytarish
                </button>
              )}
            </form>
          )}

          {workspaceLanguageSetting !== null && (
            <form onSubmit={handleSetWorkspaceLanguage} className="flex flex-wrap items-center gap-2">
              <span className="text-gray-500 dark:text-gray-400">
                Workspace standart tili ({workspaceLanguageSetting.language ?? "o'rnatilmagan"}):
              </span>
              <select
                aria-label="Workspace standart tili"
                value={workspaceLanguageChoice}
                onChange={(event) => setWorkspaceLanguageChoice(event.target.value as AiLanguage)}
                className={fieldClassCompact}
              >
                {AI_LANGUAGES.map((language) => (
                  <option key={language} value={language}>
                    {language}
                  </option>
                ))}
              </select>
              <button type="submit" disabled={savingWorkspaceLanguage} className={actionLinkClass}>
                Saqlash
              </button>
              {workspaceLanguageSetting.language !== null && (
                <button
                  type="button"
                  onClick={handleClearWorkspaceLanguage}
                  disabled={savingWorkspaceLanguage}
                  className={dangerLinkClass}
                >
                  O&apos;rnatilmagan holatga qaytarish
                </button>
              )}
            </form>
          )}
        </Card>
      )}

      <div className="flex min-h-0 flex-1 gap-6">
        <aside className="w-52 shrink-0 space-y-3">
          <button onClick={handleNewConversation} disabled={creatingConversation} className={`${primaryButtonClass} w-full`}>
            Yangi suhbat
          </button>
          <ul className="space-y-1">
            {conversations?.map((conversation) => (
              <li key={conversation.id} className="flex items-center gap-1">
                <button
                  onClick={() => setSelectedId(conversation.id)}
                  className={`min-w-0 flex-1 truncate rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors ${
                    conversation.id === selectedId
                      ? "bg-gray-900 font-medium text-white dark:bg-gray-100 dark:text-gray-900"
                      : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
                  }`}
                >
                  {conversation.title ?? "Suhbat"}
                </button>
                <button
                  onClick={() => handleDeleteConversation(conversation.id)}
                  disabled={deletingConversation}
                  aria-label="Suhbatni o'chirish"
                  title="Suhbatni o'chirish"
                  className="shrink-0 rounded-md px-1.5 py-1 text-xs text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:text-gray-500 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                >
                  ✕
                </button>
              </li>
            ))}
            {conversations !== null && conversations.length === 0 && (
              <li className="px-1 text-xs text-gray-500 dark:text-gray-400">Hali suhbat yo&apos;q.</li>
            )}
          </ul>
        </aside>

        <section className="flex min-h-0 flex-1 flex-col gap-4">
          {selected === null ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Suhbat tanlang yoki yangisini yarating.
            </p>
          ) : (
            <>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
                <form onSubmit={handlePinProvider} className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-gray-500 dark:text-gray-400">Provayder:</span>
                  <select
                    aria-label="Suhbat provayderi"
                    value={pinProvider}
                    onChange={(event) => setPinProvider(event.target.value as AiProvider)}
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
                    value={pinModel}
                    onChange={(event) => setPinModel(event.target.value)}
                    placeholder="model (ixtiyoriy)"
                    className={`${fieldClassCompact} w-32`}
                  />
                  <button type="submit" disabled={pinning} className={actionLinkClass}>
                    Pin qilish
                  </button>
                  <span className="text-gray-500 dark:text-gray-500">
                    {selected.pinned_provider
                      ? `hozirgi: ${selected.pinned_provider}${selected.pinned_model ? " / " + selected.pinned_model : ""}`
                      : "hozirgi: tizim standart"}
                  </span>
                </form>

                <form onSubmit={handlePinLanguage} className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-gray-500 dark:text-gray-400">Til:</span>
                  <select
                    aria-label="Suhbat tili"
                    value={pinLanguage}
                    onChange={(event) => setPinLanguage(event.target.value as AiLanguage)}
                    className={fieldClassCompact}
                  >
                    {AI_LANGUAGES.map((language) => (
                      <option key={language} value={language}>
                        {language}
                      </option>
                    ))}
                  </select>
                  <button type="submit" disabled={pinningLanguage} className={actionLinkClass}>
                    Pin qilish
                  </button>
                  <span className="text-gray-500 dark:text-gray-500">
                    {selected.pinned_language
                      ? `hozirgi: ${selected.pinned_language}`
                      : "hozirgi: avtomatik aniqlash"}
                  </span>
                  {selected.pinned_language !== null && (
                    <button
                      type="button"
                      onClick={handleClearPinnedLanguage}
                      disabled={pinningLanguage}
                      className={dangerLinkClass}
                    >
                      Avtomatikka qaytarish
                    </button>
                  )}
                </form>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950/40">
                {messages?.map((message) => (
                  <div key={message.id} className={message.role === "USER" ? "text-right" : "text-left"}>
                    <div
                      className={`inline-block max-w-[80%] rounded-xl px-3 py-2 text-sm ${
                        message.role === "USER"
                          ? "bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900"
                          : message.role === "TOOL"
                            ? "bg-gray-50 text-gray-500 italic dark:bg-gray-900 dark:text-gray-400"
                            : "bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100"
                      }`}
                    >
                      {message.content}
                      {message.role === "ASSISTANT" && message.provider && (
                        <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          {message.provider}
                          {message.model ? ` / ${message.model}` : ""}
                        </div>
                      )}
                    </div>
                    {message.role === "USER" && message.id === lastUserMessageId && !sending && (
                      <div>
                        <button
                          type="button"
                          onClick={() => handleStartEdit(message)}
                          className="text-xs text-gray-500 hover:text-gray-900 hover:underline dark:text-gray-400 dark:hover:text-gray-100"
                        >
                          Tahrirlash
                        </button>
                      </div>
                    )}
                  </div>
                ))}
                {pendingUserText !== null && (
                  <div className="text-right">
                    <div className="inline-block max-w-[80%] rounded-xl bg-gray-900 px-3 py-2 text-sm text-white dark:bg-gray-100 dark:text-gray-900">
                      {pendingUserText}
                    </div>
                  </div>
                )}
                {streamingText !== null && (
                  <div className="text-left">
                    <div className="inline-block max-w-[80%] rounded-xl bg-gray-100 px-3 py-2 text-sm text-gray-900 dark:bg-gray-800 dark:text-gray-100">
                      {streamingText.length > 0 ? streamingText : "..."}
                    </div>
                  </div>
                )}
                {messages !== null && messages.length === 0 && pendingUserText === null && (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Hali xabar yo&apos;q. Suhbatni boshlang.
                  </p>
                )}
                <div ref={bottomRef} />
              </div>

              {editingMessageId !== null && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Oxirgi xabaringizni tahrirlayapsiz — yuborilganda yangi javob generatsiya qilinadi,
                  eskisi o&apos;chirilmaydi.
                </p>
              )}
              <form onSubmit={handleSend} className="flex flex-wrap gap-2">
                <select
                  aria-label="Chat rejimi"
                  value={mode}
                  onChange={(event) => setMode(event.target.value as ChatMode)}
                  className={fieldClass}
                  disabled={sending}
                >
                  {CHAT_MODES.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  value={composerText}
                  onChange={(event) => setComposerText(event.target.value)}
                  placeholder="Xabar yozing..."
                  disabled={sending}
                  className={`${fieldClass} min-w-[10rem] flex-1`}
                />
                <button type="submit" disabled={sending || composerText.trim().length === 0} className={primaryButtonClass}>
                  {sending ? "..." : editingMessageId !== null ? "Qayta generatsiya qilish" : "Yuborish"}
                </button>
                {editingMessageId !== null && !sending && (
                  <button type="button" onClick={handleCancelEdit} className={secondaryButtonClass}>
                    Tahrirlashni bekor qilish
                  </button>
                )}
                {sending && (
                  <button
                    type="button"
                    onClick={handleCancel}
                    className={`${secondaryButtonClass} border-red-300 text-red-600 hover:bg-red-50 focus-visible:ring-red-500 dark:border-red-900/60 dark:text-red-400 dark:hover:bg-red-950/40`}
                  >
                    Bekor qilish
                  </button>
                )}
              </form>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
