"use client";

import {
  Archive,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Paperclip,
  Plus,
  ArrowUp,
  Square,
  Trash2,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { MessageContent } from "@/components/chat/message-content";
import { ModelStatus } from "@/components/chat/model-status";
import { UploadDialog } from "@/components/chat/upload-dialog";
import { Disclaimer } from "@/components/disclaimer";
import { LanguageMenu } from "@/components/language-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  createConversation,
  deleteConversation,
  getConversation,
  getSamples,
  listConversations,
  streamChat,
  updateConversation,
} from "@/lib/api";
import { conversationGroup, formatTimestamp } from "@/lib/format";
import { useLocale } from "@/lib/i18n";
import { useStoredFlag } from "@/lib/use-stored-flag";
import { cn } from "@/lib/utils";
import type { ChatDone, ChatMessage, ConversationSummary, UiFixture } from "@/lib/types";

const DEFAULT_TITLE = "New conversation";

export function ChatWorkspace() {
  const { t, locale, direction } = useLocale();
  const router = useRouter();
  const params = useSearchParams();
  const requestedId = params.get("c");
  const [collapsed, setCollapsed] = useStoredFlag("raremed.sidebar", false);
  const [showTimestamps] = useStoredFlag("raremed.timestamps", true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [search, setSearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [threadMessages, setThreadMessages] = useState<ChatMessage[]>([]);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const [failedId, setFailedId] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [listLoading, setListLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [listFailed, setListFailed] = useState(false);
  const [fixture, setFixture] = useState<UiFixture | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const threadVersion = useRef(0);
  const generation = useRef(0);
  const streamingRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const [thinking, setThinking] = useState<Record<string, string>>({});
  const [diagnostics, setDiagnostics] = useState<Record<string, ChatDone>>({});
  const activeId = requestedId ?? createdId;
  const messages = requestedId == null || loadedId === requestedId ? threadMessages : [];
  const threadLoading = Boolean(requestedId) && loadedId !== requestedId && failedId !== requestedId;

  const refreshList = useCallback(async () => {
    const payload = await listConversations({
      q: search,
      includeArchived: showArchived,
      archivedOnly: showArchived,
      limit: 50,
    });
    setConversations(payload.items);
    return payload.items;
  }, [search, showArchived]);

  useEffect(() => {
    let cancelled = false;
    listConversations({ q: search, includeArchived: showArchived, archivedOnly: showArchived, limit: 50 })
      .then((payload) => {
        if (cancelled) return;
        setConversations(payload.items);
        setListFailed(false);
        setListLoading(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setListFailed(true);
        setErrorCode(error instanceof ApiError ? error.code : "request_failed");
        setListLoading(false);
      });
    getSamples()
      .then((payload) => {
        if (!cancelled) setFixture(payload.fixtures[0] ?? null);
      })
      .catch(() => {
        if (!cancelled) setFixture(null);
      });
    return () => {
      cancelled = true;
    };
  }, [search, showArchived]);

  useEffect(() => {
    if (!requestedId || streamingRef.current) return;
    const version = threadVersion.current;
    let cancelled = false;
    getConversation(requestedId)
      .then((detail) => {
        if (cancelled || version !== threadVersion.current) return;
        setThreadMessages(detail.messages);
        setHasMoreMessages(Boolean(detail.has_more));
        setLoadedId(requestedId);
        setFailedId(null);
      })
      .catch((error: unknown) => {
        if (cancelled || version !== threadVersion.current) return;
        setFailedId(requestedId);
        setErrorCode(error instanceof ApiError ? error.code : "request_failed");
      });
    return () => {
      cancelled = true;
    };
  }, [requestedId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [threadMessages, loadedId, sending]);

  function cancelGeneration() {
    generation.current += 1;
    streamingRef.current = false;
    abortRef.current?.abort();
    abortRef.current = null;
  }

  function openConversation(id: string) {
    cancelGeneration();
    setMobileOpen(false);
    if (id !== requestedId) {
      setLoadedId(null);
      setThreadMessages([]);
    }
    router.replace(`/chat?c=${id}`);
  }

  function startNew() {
    cancelGeneration();
    setMobileOpen(false);
    setCreatedId(null);
    setLoadedId(null);
    setThreadMessages([]);
    setErrorCode(null);
    router.replace("/chat");
  }

  function stop() {
    abortRef.current?.abort();
  }

  async function runTurn(history: ChatMessage[], regenerate: boolean) {
    const token = generation.current + 1;
    generation.current = token;
    const controller = new AbortController();
    abortRef.current = controller;
    streamingRef.current = true;
    setSending(true);
    setErrorCode(null);
    const assistant = history.findLast((item) => item.role === "assistant");
    const assistantId = assistant?.id;
    let conversationId = activeId;
    if (!regenerate && !conversationId) {
      try {
        const created = await createConversation(locale);
        if (token !== generation.current) return;
        conversationId = created.id;
        threadVersion.current += 1;
        setCreatedId(created.id);
        setLoadedId(created.id);
        router.replace(`/chat?c=${created.id}`);
      } catch (error) {
        if (token === generation.current) {
          setErrorCode(error instanceof ApiError ? error.code : "request_failed");
        }
      }
    }
    try {
      await streamChat(
        {
          messages: history
            .filter((item) => (item.role === "user" || item.role === "assistant") && item.content.trim())
            .filter((item) => item.id !== assistantId)
            .map((item) => ({ role: item.role as "user" | "assistant", content: item.content })),
          locale,
          conversation_id: conversationId ?? undefined,
          regenerate,
        },
        {
          signal: controller.signal,
          onToken: (text) => {
            if (!assistantId || token !== generation.current) return;
            setThreadMessages((current) =>
              current.map((item) =>
                item.id === assistantId ? { ...item, content: item.content + text } : item,
              ),
            );
          },
          onThinking: (text) => {
            if (!assistantId || token !== generation.current) return;
            setThinking((current) => ({ ...current, [assistantId]: `${current[assistantId] ?? ""}${text}` }));
          },
          onDone: (done) => {
            if (!assistantId || token !== generation.current) return;
            setDiagnostics((current) => ({ ...current, [assistantId]: done }));
            if (done.conversation_id && done.conversation_id !== conversationId) {
              conversationId = done.conversation_id;
              threadVersion.current += 1;
              setCreatedId(done.conversation_id);
              setLoadedId(done.conversation_id);
              router.replace(`/chat?c=${done.conversation_id}`);
            }
            if (!done.saved && conversationId) setErrorCode("database_unavailable");
          },
        },
      );
      if (token === generation.current) await refreshList().catch(() => undefined);
    } catch (error) {
      if (token !== generation.current) return;
      if (error instanceof DOMException && error.name === "AbortError") {
        setDiagnostics((current) =>
          assistantId
            ? {
                ...current,
                [assistantId]: {
                  model: "qwen3:4b",
                  provider: "ollama",
                  elapsed_ms: 0,
                  eval_count: null,
                  tokens_per_second: null,
                  stopped: true,
                  saved: false,
                  think: false,
                },
              }
            : current,
        );
        setThreadMessages((current) =>
          current.map((item) =>
            item.id === assistantId ? { ...item, status: "interrupted" } : item,
          ),
        );
        await refreshList().catch(() => undefined);
        return;
      }
      setErrorCode(error instanceof ApiError ? error.code : "request_failed");
      if (assistantId) {
        setThreadMessages((current) =>
          current.filter((item) => item.id !== assistantId || item.content.trim() !== ""),
        );
      }
    } finally {
      if (token === generation.current) {
        streamingRef.current = false;
        abortRef.current = null;
        setSending(false);
      }
    }
  }

  async function send() {
    const content = draft.trim();
    if (!content || sending) return;
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      conversation_id: activeId ?? "local",
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    const assistantMessage: ChatMessage = {
      id: crypto.randomUUID(),
      conversation_id: activeId ?? "local",
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };
    const history = [...(requestedId == null || loadedId === requestedId ? threadMessages : []), userMessage, assistantMessage];
    setThreadMessages(history);
    setDraft("");
    if (!requestedId) setLoadedId(null);
    await runTurn(history, false);
  }

  async function regenerate() {
    if (sending) return;
    const current = requestedId == null || loadedId === requestedId ? threadMessages : [];
    const lastAssistant = [...current].reverse().find((item) => item.role === "assistant");
    const lastUser = [...current].reverse().find((item) => item.role === "user");
    if (!lastAssistant || !lastUser) return;
    setThreadMessages((items) =>
      items.map((item) => (item.id === lastAssistant.id ? { ...item, content: "" } : item)),
    );
    setThinking((items) => ({ ...items, [lastAssistant.id]: "" }));
    await runTurn(
      current.map((item) => (item.id === lastAssistant.id ? { ...item, content: "" } : item)),
      true,
    );
  }

  async function loadEarlier() {
    if (!activeId || threadMessages.length === 0) return;
    const oldest = threadMessages[0];
    try {
      const detail = await getConversation(activeId, { before: oldest.id, limit: 50 });
      setThreadMessages((current) => [...detail.messages, ...current]);
      setHasMoreMessages(Boolean(detail.has_more));
    } catch (error) {
      setErrorCode(error instanceof ApiError ? error.code : "request_failed");
    }
  }

  async function renameConversation(id: string, title: string) {
    try {
      await updateConversation(id, { title });
      await refreshList();
    } catch (error) {
      setErrorCode(error instanceof ApiError ? error.code : "request_failed");
    }
  }

  async function archiveConversation(id: string, archived: boolean) {
    try {
      await updateConversation(id, { archived });
      if (archived && activeId === id) startNew();
      await refreshList();
    } catch (error) {
      setErrorCode(error instanceof ApiError ? error.code : "request_failed");
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const id = pendingDelete;
    setPendingDelete(null);
    try {
      await deleteConversation(id);
      if (activeId === id) startNew();
      await refreshList();
    } catch (error) {
      setErrorCode(error instanceof ApiError ? error.code : "request_failed");
    }
  }

  const activeTitle =
    conversations.find((item) => item.id === activeId)?.title ?? t("newConversation");
  const title = activeTitle === DEFAULT_TITLE ? t("newConversation") : activeTitle;
  const errorText = errorCode
    ? t(
        errorCode === "network_error"
          ? "apiOffline"
          : errorCode === "database_unavailable"
            ? "databaseUnavailable"
            : errorCode === "ollama_unavailable"
              ? "ollamaUnavailable"
              : errorCode === "model_missing"
                ? "modelMissingDetail"
                : errorCode === "provider_not_configured"
                  ? "providerNotConfigured"
                  : errorCode === "generation_failed"
                    ? "generationFailed"
                    : errorCode === "unauthenticated"
                      ? "sessionExpired"
                      : "requestFailed",
      )
    : null;

  const list = (
    <ConversationList
      items={conversations}
      activeId={activeId}
      loading={listLoading}
      failed={listFailed}
      showTimestamps={showTimestamps}
      search={search}
      showArchived={showArchived}
      onSearch={setSearch}
      onToggleArchived={() => setShowArchived((current) => !current)}
      onOpen={openConversation}
      onDelete={setPendingDelete}
      onCreate={startNew}
      onRename={renameConversation}
      onArchive={archiveConversation}
    />
  );

  return (
    <div className="flex h-dvh bg-background">
      <aside
        className={cn(
          "hidden h-full min-h-0 border-e bg-sidebar md:flex md:flex-col",
          collapsed ? "w-[4.5rem]" : "w-72",
        )}
      >
        <div className="flex items-center gap-2 px-3 py-3">
          <BrandMark className="size-7" />
          {collapsed ? null : (
            <div className="min-w-0">
              <p className="truncate font-heading text-sm">{t("product")}</p>
              <p className="truncate text-[11px] text-muted-foreground uppercase">{t("decisionSupport")}</p>
            </div>
          )}
        </div>
        {collapsed ? (
          <div className="flex flex-col items-center gap-2 px-2">
            <Button variant="outline" size="icon" aria-label={t("newConversation")} onClick={startNew}>
              <Plus />
            </Button>
          </div>
        ) : (
          list
        )}
        <div className="mt-auto border-t p-2">
          <Button
            variant="ghost"
            className="w-full justify-start"
            aria-label={collapsed ? t("expandSidebar") : t("collapseSidebar")}
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            {collapsed ? null : <span>{t("collapseSidebar")}</span>}
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-2 border-b px-3 sm:px-4">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label={t("mobileMenu")}
            onClick={() => setMobileOpen(true)}
          >
            <Menu />
          </Button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{title}</p>
            <p className="truncate text-[11px] text-muted-foreground">{t("roleLabel")}</p>
          </div>
          <ModelStatus />
          <LanguageMenu />
          <ThemeToggle />
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-8">
            {errorText ? (
              <p className="rounded-xl border border-copper/40 bg-accent px-3 py-2 text-sm" role="status">
                {errorText}
              </p>
            ) : null}
            {threadLoading ? (
              <div className="space-y-3" aria-busy="true">
                <div className="h-16 animate-pulse rounded-2xl bg-muted" />
                <div className="h-16 animate-pulse rounded-2xl bg-muted" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-start gap-4 py-16">
                <p className="text-xs tracking-[0.16em] text-copper uppercase">{t("versionLabel")}</p>
                <h1 className="font-heading text-3xl">{t("emptyTitle")}</h1>
                <p className="max-w-lg text-sm leading-6 text-muted-foreground">{t("emptyBody")}</p>
                <p className="max-w-lg text-sm leading-6 text-muted-foreground">{t("chatNotice")}</p>
                <Disclaimer text={t("disclaimer")} />
              </div>
            ) : (
              <>
              {hasMoreMessages ? (
                <Button type="button" variant="outline" size="sm" onClick={() => void loadEarlier()}>
                  {t("loadEarlier")}
                </Button>
              ) : null}
              {messages.map((message, index) => {
                const report = diagnostics[message.id];
                const thought = thinking[message.id];
                const lastAssistant = message.role === "assistant" && index === messages.length - 1;
                return (
                  <article
                    key={message.id}
                    className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
                  >
                    <div
                      className={cn(
                        "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6",
                        message.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-card ring-1 ring-foreground/10",
                      )}
                    >
                      <p className="mb-1 text-[11px] opacity-70">
                        {message.role === "user" ? t("you") : t("assistant")}
                        {message.role === "assistant" ? ` · ${t("decisionSupport")}` : ""}
                      </p>
                      {thought ? (
                        <details className="mb-2 text-xs text-muted-foreground">
                          <summary>{t("thinking")}</summary>
                          <p dir="auto" className="mt-1 whitespace-pre-wrap">{thought}</p>
                        </details>
                      ) : null}
                      {message.role === "user" ? (
                        <p dir="auto" className="whitespace-pre-wrap">{message.content}</p>
                      ) : message.content ? (
                        <MessageContent content={message.content} />
                      ) : sending && lastAssistant ? (
                        <span className="inline-block h-4 w-2 animate-pulse bg-current" aria-label={t("generating")} />
                      ) : null}
                      {showTimestamps ? (
                        <p className="mt-2 text-[11px] opacity-60">
                          {formatTimestamp(message.created_at, locale)}
                        </p>
                      ) : null}
                      {process.env.NODE_ENV === "development" && report && (report.elapsed_ms > 0 || report.stopped) ? (
                        <p className="mt-2 text-[11px] opacity-60">
                          {report.stopped && !report.elapsed_ms
                            ? t("stopped")
                            : `${(report.elapsed_ms / 1000).toFixed(1)} s${
                                report.tokens_per_second != null ? ` · ${report.tokens_per_second} tok/s` : ""
                              }`}
                        </p>
                      ) : null}
                      {message.status === "interrupted" ? (
                        <p className="mt-2 text-[11px] text-copper">{t("interrupted")}</p>
                      ) : null}
                      {lastAssistant && !sending && (message.content || message.status === "interrupted") ? (
                        <Button type="button" variant="ghost" size="sm" className="mt-2" onClick={() => void regenerate()}>
                          {t("regenerate")}
                        </Button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
              </>
            )}
            <div ref={endRef} />
          </div>
        </div>

        <form
          className="border-t bg-background px-3 py-3 sm:px-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (sending) stop();
            else void send();
          }}
        >
          <div className="mx-auto w-full max-w-3xl">
            <div className="rounded-2xl bg-card p-2 ring-1 ring-foreground/10">
              <label className="sr-only" htmlFor="composer">
                {t("messagePlaceholder")}
              </label>
              <Textarea
                id="composer"
                value={draft}
                maxLength={8000}
                placeholder={t("messagePlaceholder")}
                className="max-h-40 min-h-16 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    if (sending) stop();
                    else void send();
                  }
                }}
              />
              <div className="flex items-center gap-2 px-1 pt-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t("attach")}
                  onClick={() => setUploadOpen(true)}
                >
                  <Paperclip />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={!fixture}
                  onClick={() => fixture && setDraft(fixture.text)}
                >
                  {t("insertFixture")}
                </Button>
                <span className="ms-auto text-[11px] text-muted-foreground">
                  {draft.length > 7000 ? `${draft.length}/8000 ${t("characters")}` : t("composerHint")}
                </span>
                {sending ? (
                  <Button type="button" size="icon" aria-label={t("stop")} onClick={stop}>
                    <Square />
                  </Button>
                ) : (
                  <Button type="submit" size="icon" aria-label={t("send")} disabled={draft.trim() === ""}>
                    <ArrowUp />
                  </Button>
                )}
              </div>
            </div>
            {fixture ? (
              <p className="px-2 pt-2 text-[11px] text-muted-foreground">{fixture.notice}</p>
            ) : (
              <p className="px-2 pt-2 text-[11px] text-muted-foreground">{t("fixtureMissing")}</p>
            )}
          </div>
        </form>
      </div>

      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side={direction === "rtl" ? "right" : "left"} className="w-80 bg-sidebar">
          <SheetHeader>
            <SheetTitle>{t("conversations")}</SheetTitle>
          </SheetHeader>
          {list}
        </SheetContent>
      </Sheet>
      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
      <Dialog open={pendingDelete !== null} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("deleteTitle")}</DialogTitle>
            <DialogDescription>{t("confirmDelete")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingDelete(null)}>
              {t("cancel")}
            </Button>
            <Button variant="destructive" onClick={() => void confirmDelete()}>
              {t("delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ConversationList({
  items,
  activeId,
  loading,
  failed,
  showTimestamps,
  search,
  showArchived,
  onSearch,
  onToggleArchived,
  onOpen,
  onDelete,
  onCreate,
  onRename,
  onArchive,
}: {
  items: ConversationSummary[];
  activeId: string | null;
  loading: boolean;
  failed: boolean;
  showTimestamps: boolean;
  search: string;
  showArchived: boolean;
  onSearch: (value: string) => void;
  onToggleArchived: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onCreate: () => void;
  onRename: (id: string, title: string) => void;
  onArchive: (id: string, archived: boolean) => void;
}) {
  const { t, locale } = useLocale();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const groups = ["today", "yesterday", "previous7Days", "previous30Days", "older"] as const;
  const grouped = groups
    .map((key) => ({
      key,
      items: items.filter((item) => conversationGroup(item.updated_at) === key),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 px-2">
      <Button variant="outline" className="justify-start" onClick={onCreate}>
        <Plus />
        {t("newConversation")}
      </Button>
      <Input
        value={search}
        onChange={(event) => onSearch(event.target.value)}
        placeholder={t("searchConversations")}
        aria-label={t("searchConversations")}
      />
      <Button type="button" variant="ghost" size="sm" className="justify-start" onClick={onToggleArchived}>
        <Archive />
        {showArchived ? t("savedThreads") : t("showArchived")}
      </Button>
      <p className="px-2 text-[11px] tracking-wide text-muted-foreground uppercase">
        {showArchived ? t("archived") : t("savedThreads")}
      </p>
      <ScrollArea className="min-h-0 flex-1">
        {loading ? (
          <div className="space-y-2 p-1" aria-busy="true">
            <div className="h-12 animate-pulse rounded-lg bg-muted" />
            <div className="h-12 animate-pulse rounded-lg bg-muted" />
          </div>
        ) : items.length === 0 && !failed ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">{t("noConversations")}</p>
        ) : items.length === 0 ? null : (
          <div className="flex flex-col gap-3 pe-2">
            {grouped.map((group) => (
              <div key={group.key}>
                <p className="px-2 pb-1 text-[11px] text-muted-foreground uppercase">{t(group.key)}</p>
                <ul className="flex flex-col gap-1" aria-label={t(group.key)}>
                  {group.items.map((item) => {
                    const label = item.title === DEFAULT_TITLE ? t("newConversation") : item.title;
                    const active = item.id === activeId;
                    return (
                      <li key={item.id}>
                        <div
                          className={cn(
                            "group flex items-start gap-1 rounded-lg px-2 py-2",
                            active ? "bg-sidebar-accent ring-1 ring-primary/40" : "hover:bg-sidebar-accent/70",
                          )}
                          aria-current={active ? "true" : undefined}
                        >
                          {editingId === item.id ? (
                            <form
                              className="min-w-0 flex-1"
                              onSubmit={(event) => {
                                event.preventDefault();
                                if (draftTitle.trim()) onRename(item.id, draftTitle.trim());
                                setEditingId(null);
                              }}
                            >
                              <Input
                                value={draftTitle}
                                aria-label={t("titlePlaceholder")}
                                onChange={(event) => setDraftTitle(event.target.value)}
                                autoFocus
                              />
                            </form>
                          ) : (
                            <button type="button" className="min-w-0 flex-1 text-start" onClick={() => onOpen(item.id)}>
                              <span className="block truncate text-sm">{label}</span>
                              {showTimestamps ? (
                                <span className="block truncate text-[11px] text-muted-foreground">
                                  {formatTimestamp(item.updated_at, locale)}
                                </span>
                              ) : null}
                            </button>
                          )}
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            aria-label={t("rename")}
                            onClick={() => {
                              setEditingId(item.id);
                              setDraftTitle(item.title);
                            }}
                          >
                            {t("rename").slice(0, 1)}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            aria-label={item.archived ? t("unarchive") : t("archive")}
                            onClick={() => onArchive(item.id, !item.archived)}
                          >
                            <Archive />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            aria-label={t("deleteConversation")}
                            onClick={() => onDelete(item.id)}
                          >
                            <Trash2 />
                          </Button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
