const BASE = "/api/v1";

function authHeaders(): Record<string, string> {
  const token = (window as any).__CORTEX_TOKEN__;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
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
  tags: string[];
  thesis_links: string[];
  confidence: number;
  source: string;
  source_path: string | null;
  source_type: string | null;
  temporality: string | null;
  user_annotation: string | null;
  raw_input_type: string | null;
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

// API functions
export const api = {
  health: () => get<{ status: string }>("/health"),
  stats: () => get<Stats>("/stats"),
  events: (limit = 50, days?: number) =>
    get<Event[]>(`/events?limit=${limit}${days ? `&days=${days}` : ""}`),
  event: (id: string) => get<Event>(`/events/${id}`),
  eventRelated: (id: string, limit = 10) =>
    get<SearchResult[]>(`/search/related/${id}?limit=${limit}`),
  entityGraph: (objectId: string) =>
    get<RelationRow[]>(`/entity/${objectId}/graph`),
  searchEntities: (q: string, limit = 20) =>
    get<EntityResult[]>(`/entities/search?q=${encodeURIComponent(q)}&limit=${limit}`),
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
};
