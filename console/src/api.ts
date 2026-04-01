const BASE = "/api/v1";

declare global {
  interface Window {
    __CORTEX_TOKEN__?: string;
  }
}

function authHeaders(): Record<string, string> {
  const token = window.__CORTEX_TOKEN__;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Simple TTL cache for GET requests
const _cache = new Map<string, { data: unknown; expires: number }>();
const CACHE_TTL_MS = 10_000; // 10 seconds

function getCached<T>(path: string): T | undefined {
  const entry = _cache.get(path);
  if (entry && Date.now() < entry.expires) return entry.data as T;
  _cache.delete(path);
  return undefined;
}

function setCache(path: string, data: unknown) {
  _cache.set(path, { data, expires: Date.now() + CACHE_TTL_MS });
}

async function get<T>(path: string, opts?: { skipCache?: boolean }): Promise<T> {
  if (!opts?.skipCache) {
    const cached = getCached<T>(path);
    if (cached !== undefined) return cached;
  }
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const data = await res.json();
  setCache(path, data);
  return data;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// Types
export interface Event {
  id: string;
  type: string;
  title: string;
  summary: string;
  content: string;
  tags: string[];
  thesis_links: string[];
  confidence: number;
  source: string;
  source_path: string | null;
  source_type: string | null;
  temporality: string | null;
  user_annotation: string | null;
  raw_input_type: string | null;
  relevance: number | null;
  created_at: string;
}

export interface Notification {
  id: string;
  source_kind: string;
  source_id: string;
  title: string;
  body: string;
  priority: string;
  status: string;
  channel: string;
  signal_id: string | null;
  related_event_ids: string[];
  created_at: string;
  delivered_at: string | null;
  acted_at: string | null;
}

export interface Signal {
  id: string;
  new_event_id: string;
  existing_event_id: string;
  signal_type: string;
  topic: string | null;
  summary: string | null;
  confidence: number;
  priority_score: number;
  evidence_strength: string | null;
  rationale: string | null;
  evidence_event_ids: string[];
  thesis_links: string[];
  created_at: string;
}

export interface Stats {
  events: number;
  entities: number;
  relations: number;
  type_distribution: Record<string, number>;
}

export interface SearchResult {
  event: Event;
  score: number;
  match_type: string;
}

export interface RelationRow {
  id: string;
  source_type: string;
  source_id: string;
  source_name: string;
  target_type: string;
  target_id: string;
  target_name: string;
  relation: string;
  confidence: number;
  source_entity_type?: string;
  target_entity_type?: string;
}

export interface GraphEntity {
  id: string;
  name: string;
  type: string;
  theses: string[];
  mention_count: number;
}

export interface ThesisLink {
  source: string;
  target: string;
  shared_events: number;
}

export interface GraphOverview {
  entities: GraphEntity[];
  relations: RelationRow[];
  thesis_links: ThesisLink[];
  all_theses: string[];
}

export interface EntityResult {
  id: string;
  type: string;
  name: string;
  aliases: string[];
  score: number;
  mention_count: number;
}

export interface Annotation {
  id: string;
  target_type: string;
  target_id: string;
  annotation: string | null;
  stance: string | null;
  created_at: string;
}

export interface SettingsResponse {
  llm: {
    configured: boolean;
    model: string;
    base_url: string;
    thesis_list: string[];
  };
  workspace: string;
  embedding_model: string;
}

export interface ThesisCoverage {
  thesis: string;
  event_count: number;
  avg_confidence: number;
  type_distribution: Record<string, number>;
  latest_update: string | null;
  days_since_update: number;
  trend_direction: string;
  confidence_delta: number | null;
  recent_avg_confidence: number | null;
  previous_avg_confidence: number | null;
  recent_event_count: number;
}

export interface StructuredThesis {
  id: string;
  text: string;
  stance: string;
  theme: string | null;
  status: string;
  expires_at: string | null;
  created_by: string;
  confirmed: boolean;
  confidence: number;
  created_at: string;
  updated_at: string;
}

export interface ThesisEvidence {
  id: string;
  thesis_id: string;
  event_id: string;
  impact: string;
  confidence_delta: number;
  rationale: string | null;
  created_at: string;
  event_title: string | null;
  event_summary: string | null;
}

async function del(path: string): Promise<unknown> {
  const res = await fetch(`${BASE}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// API functions
export const api = {
  health: () => get<{ status: string }>("/health"),
  stats: () => get<Stats>("/stats"),
  events: (limit = 50, days?: number, sort: string = "recent", offset = 0) =>
    get<Event[]>(`/events?limit=${limit}&offset=${offset}&sort=${sort}${days ? `&days=${days}` : ""}`),
  event: (id: string) => get<Event>(`/events/${id}`),
  eventRelated: (id: string, limit = 10) =>
    get<SearchResult[]>(`/search/related/${id}?limit=${limit}`),
  entityGraph: (objectId: string) =>
    get<RelationRow[]>(`/entity/${objectId}/graph`),
  searchEntities: (q: string, limit = 20) =>
    get<EntityResult[]>(`/entities/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  topEntities: (limit = 30) =>
    get<EntityResult[]>(`/entities/top?limit=${limit}`),
  graphOverview: () =>
    get<GraphOverview>("/graph/overview"),
  entityEvents: (entityId: string, limit = 20) =>
    get<Event[]>(`/entities/${entityId}/events?limit=${limit}`),
  notifications: (status?: string, limit = 50) =>
    get<Notification[]>(
      `/notifications?limit=${limit}${status ? `&status=${status}` : ""}`
    ),
  notificationAction: (id: string, action: "read" | "ack" | "dismiss") =>
    post<Notification>(`/notifications/${id}/${action}`),
  signals: (limit = 50) => get<Signal[]>(`/signals?limit=${limit}`),
  signalFeedback: (id: string, verdict: string, note?: string) =>
    post<unknown>(`/signals/${id}/feedback`, { verdict, note }),
  thesisEvidence: (thesis: string) =>
    get<Event[]>(`/thesis/${encodeURIComponent(thesis)}`),
  digest: (days = 7) => get<Record<string, unknown>>(`/digest?days=${days}`),
  search: (query: string, mode = "hybrid", limit = 20, typeFilter?: string) =>
    post<SearchResult[]>("/search", {
      query,
      mode,
      limit,
      type_filter: typeFilter || null,
    }),
  ingest: (data: {
    content?: string;
    url?: string;
    title?: string;
    source?: string;
    raw_input_type?: string;
    user_annotation?: string;
  }) => post<Event>("/events/ingest", data),
  thesisCoverage: () =>
    get<ThesisCoverage[]>("/thesis"),
  annotate: (eventId: string, annotation: string, stance?: string) =>
    post<Annotation>(`/events/${eventId}/annotate`, { annotation, stance }),
  annotations: (eventId: string) =>
    get<Annotation[]>(`/annotations/event/${eventId}`),
  updateEvent: (eventId: string, fields: { tags?: string[]; thesis_links?: string[]; title?: string }) =>
    patch<Event>(`/events/${eventId}`, fields),
  bulkNotificationAction: (action: string, ids?: string[], statusFilter?: string) =>
    post<{ updated: number; failed: number }>("/notifications/bulk-action", {
      action,
      ids: ids || undefined,
      status_filter: statusFilter || undefined,
    }),
  settings: () => get<SettingsResponse>("/settings"),
  updateLLM: (apiKey: string, model?: string, baseUrl?: string) =>
    put<{ status: string; llm_configured: boolean; model?: string }>("/settings/llm", {
      api_key: apiKey,
      model: model || "",
      base_url: baseUrl || "",
    }),

  // Structured theses
  theses: (status?: string, theme?: string) =>
    get<StructuredThesis[]>(
      `/theses?${status ? `status=${status}&` : ""}${theme ? `theme=${encodeURIComponent(theme)}` : ""}`
    ),
  createThesis: (data: { text: string; stance?: string; theme?: string; expires_at?: string; created_by?: string }) =>
    post<StructuredThesis>("/theses", data),
  getThesis: (id: string) => get<StructuredThesis>(`/theses/${id}`),
  updateThesis: (id: string, data: Record<string, unknown>) =>
    patch<StructuredThesis>(`/theses/${id}`, data),
  resolveThesis: (id: string) => post<StructuredThesis>(`/theses/${id}/resolve`),
  invalidateThesis: (id: string) => post<StructuredThesis>(`/theses/${id}/invalidate`),
  confirmThesis: (id: string) => post<StructuredThesis>(`/theses/${id}/confirm`),
  deleteThesis: (id: string) => del(`/theses/${id}`),
  thesisEvidenceList: (id: string, limit = 50) =>
    get<ThesisEvidence[]>(`/theses/${id}/evidence?limit=${limit}`),
  thesisSuggestions: (minEvents = 3) =>
    get<{ theme: string; event_count: number }[]>(`/theses/suggestions?min_events=${minEvents}`),
  generateThesesForTheme: (theme: string) =>
    post<StructuredThesis[]>(`/theses/generate/${encodeURIComponent(theme)}`),
  generateThesesAll: () =>
    post<{ generated: Record<string, number> }>("/theses/generate-all"),
};
