import type {
  ChatDone,
  ConversationDetail,
  ConversationList,
  ConversationSummary,
  DiscoveryReport,
  DiseaseDetail,
  EntityDetail,
  GraphEvidenceRead,
  GraphSearchHit,
  GraphSearchPage,
  GraphSliceRead,
  GraphStatus,
  IngestionStatus,
  NeighborhoodRead,
  SourceFacetRead,
  LocaleCode,
  MessageExchange,
  ModelIndicator,
  PlatformStatus,
  SessionUser,
  UiFixture,
} from "@/lib/types";

const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function getApiBaseUrl() {
  if (typeof window === "undefined") return configuredApiBaseUrl;
  try {
    const url = new URL(configuredApiBaseUrl, window.location.origin);
    const pageHost = window.location.hostname;
    if (pageHost === "localhost" || pageHost === "127.0.0.1") {
      url.hostname = pageHost;
    }
    return url.origin;
  } catch {
    return configuredApiBaseUrl;
  }
}

export const apiBaseUrl = configuredApiBaseUrl;

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "network_error", "The RareMed API is not reachable.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const payload = (await response.json().catch(() => null)) as {
    error?: { code?: string; message?: string };
  } | null;

  if (!response.ok) {
    throw new ApiError(
      response.status,
      payload?.error?.code ?? "request_failed",
      payload?.error?.message ?? "Request failed.",
    );
  }

  return payload as T;
}

export function getStatus() {
  return request<PlatformStatus>("/api/v1/status");
}

export function getDatasets() {
  return request<DiscoveryReport>("/api/v1/datasets");
}

export function getSamples() {
  return request<{ fixtures: UiFixture[]; note: string }>("/api/v1/samples");
}

export function getGraphStatus() {
  return request<GraphStatus>("/api/v1/graph/status");
}

export function getGraphStats() {
  return request<GraphStatus>("/api/v1/graph/stats");
}

export function loadGraph() {
  return request<GraphStatus>("/api/v1/graph/load", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function rollbackGraph() {
  return request<GraphStatus>("/api/v1/graph/rollback", { method: "POST" });
}

export function searchGraphDiseases(q: string) {
  return request<GraphSearchHit[]>(`/api/v1/graph/diseases?q=${encodeURIComponent(q)}`);
}

export function searchGraphPhenotypes(q: string) {
  return request<GraphSearchHit[]>(`/api/v1/graph/phenotypes?q=${encodeURIComponent(q)}`);
}

export function getDiseaseDetail(curie: string) {
  return request<DiseaseDetail>(`/api/v1/graph/diseases/${encodeURIComponent(curie)}`);
}

export function getNeighborhood(curie: string) {
  return request<NeighborhoodRead>(
    `/api/v1/graph/neighborhood?curie=${encodeURIComponent(curie)}&depth=1&limit=40`,
  );
}

export function getEntityDetail(curie: string) {
  return request<EntityDetail>(`/api/v1/graph/entities/${encodeURIComponent(curie)}`);
}

export function getGraphProvenance(curie: string) {
  return request<GraphEvidenceRead[]>(`/api/v1/graph/provenance?curie=${encodeURIComponent(curie)}`);
}

export function exploreSearch(params: {
  q: string;
  kinds?: string[];
  source?: string;
  sourceVersion?: string;
  offset?: number;
  limit?: number;
}) {
  const query = new URLSearchParams({ q: params.q });
  if (params.kinds?.length) query.set("kinds", params.kinds.join(","));
  if (params.source) query.set("source", params.source);
  if (params.sourceVersion) query.set("source_version", params.sourceVersion);
  if (params.offset) query.set("offset", String(params.offset));
  if (params.limit) query.set("limit", String(params.limit));
  return request<GraphSearchPage>(`/api/v1/graph/explore/search?${query}`);
}

export function exploreNeighborhood(params: {
  curie: string;
  depth?: number;
  limit?: number;
  kinds?: string[];
  source?: string;
}) {
  const query = new URLSearchParams({ curie: params.curie });
  query.set("depth", String(params.depth ?? 1));
  query.set("limit", String(params.limit ?? 40));
  if (params.kinds?.length) query.set("kinds", params.kinds.join(","));
  if (params.source) query.set("source", params.source);
  return request<NeighborhoodRead>(`/api/v1/graph/explore/neighborhood?${query}`);
}

export function exploreExpand(params: {
  curie: string;
  limit?: number;
  kinds?: string[];
  source?: string;
}) {
  const query = new URLSearchParams({ curie: params.curie });
  query.set("limit", String(params.limit ?? 16));
  if (params.kinds?.length) query.set("kinds", params.kinds.join(","));
  if (params.source) query.set("source", params.source);
  return request<GraphSliceRead>(`/api/v1/graph/explore/expand?${query}`);
}

export function explorePath(start: string, end: string) {
  const query = new URLSearchParams({ start, end, max_hops: "4" });
  return request<GraphSliceRead>(`/api/v1/graph/explore/path?${query}`);
}

export function exploreSources() {
  return request<SourceFacetRead[]>("/api/v1/graph/explore/sources");
}

export function getIngestionStatus() {
  return request<IngestionStatus>("/api/v1/ingestion/status");
}

export function runIngestion(strict = false) {
  return request<IngestionStatus>("/api/v1/ingestion/run", {
    method: "POST",
    body: JSON.stringify({ strict }),
  });
}

export function rollbackIngestion() {
  return request<IngestionStatus>("/api/v1/ingestion/rollback", { method: "POST" });
}

export function getMe() {
  return request<SessionUser>("/api/v1/auth/me");
}

export function registerAccount(email: string, password: string, displayName?: string) {
  return request<{ user: SessionUser }>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name: displayName || undefined }),
  });
}

export function loginAccount(email: string, password: string) {
  return request<{ user: SessionUser }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logoutAccount() {
  return request<void>("/api/v1/auth/logout", { method: "POST" });
}

export function listUsers() {
  return request<SessionUser[]>("/api/v1/admin/users");
}

export function listConversations(params?: {
  q?: string;
  includeArchived?: boolean;
  archivedOnly?: boolean;
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.q) query.set("q", params.q);
  if (params?.includeArchived) query.set("include_archived", "true");
  if (params?.archivedOnly) query.set("archived_only", "true");
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const suffix = query.toString() ? `?${query}` : "";
  return request<ConversationList>(`/api/v1/conversations${suffix}`);
}

export function createConversation(locale: LocaleCode) {
  return request<ConversationDetail>("/api/v1/conversations", {
    method: "POST",
    body: JSON.stringify({ locale }),
  });
}

export function getConversation(id: string, params?: { limit?: number; before?: string }) {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.before) query.set("before", params.before);
  const suffix = query.toString() ? `?${query}` : "";
  return request<ConversationDetail>(`/api/v1/conversations/${id}${suffix}`);
}

export function updateConversation(id: string, body: { title?: string; archived?: boolean }) {
  return request<ConversationSummary>(`/api/v1/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function postMessage(id: string, content: string, locale: LocaleCode) {
  return request<MessageExchange>(`/api/v1/conversations/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, locale }),
  });
}

export function deleteConversation(id: string) {
  return request<void>(`/api/v1/conversations/${id}`, { method: "DELETE" });
}

export function getModelStatus() {
  return request<ModelIndicator>("/api/v1/models");
}

export type ChatStreamBody = {
  messages: { role: "user" | "assistant"; content: string }[];
  locale: LocaleCode;
  conversation_id?: string;
  regenerate?: boolean;
};

export type ChatStreamHandlers = {
  onToken: (text: string) => void;
  onThinking: (text: string) => void;
  onDone: (done: ChatDone) => void;
  signal?: AbortSignal;
};

export async function streamChat(body: ChatStreamBody, handlers: ChatStreamHandlers) {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/v1/chat`, {
      method: "POST",
      credentials: "include",
      headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: handlers.signal,
    });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiError(0, "network_error", "The RareMed API is not reachable.");
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string };
    } | null;
    throw new ApiError(
      response.status,
      payload?.error?.code ?? "request_failed",
      payload?.error?.message ?? "Request failed.",
    );
  }
  if (!response.body) {
    throw new ApiError(502, "generation_failed", "The model returned an empty stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const parsed = parseSseBlock(block);
        if (!parsed) continue;
        if (parsed.event === "token") handlers.onToken(String(parsed.data.text ?? ""));
        else if (parsed.event === "thinking") handlers.onThinking(String(parsed.data.text ?? ""));
        else if (parsed.event === "error") {
          throw new ApiError(
            503,
            String(parsed.data.code ?? "generation_failed"),
            String(parsed.data.message ?? "The model stopped before it finished a reply."),
          );
        } else if (parsed.event === "done") handlers.onDone(parsed.data as ChatDone);
      }
    }
  } catch (error) {
    if (isAbort(error)) throw error;
    throw error;
  }
}

export function parseSseBlock(block: string): { event: string; data: Record<string, unknown> } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  return { event, data: JSON.parse(dataLines.join("\n")) as Record<string, unknown> };
}

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}
