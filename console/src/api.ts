const BASE = "/api/v1";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
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

// API functions
export const api = {
  health: () => get<{ status: string }>("/health"),
  stats: () => get<Stats>("/stats"),
  events: (limit = 50, days?: number) =>
    get<Event[]>(`/events?limit=${limit}${days ? `&days=${days}` : ""}`),
  event: (id: string) => get<Event>(`/events/${id}`),
  notifications: (status?: string, limit = 50) =>
    get<Notification[]>(
      `/notifications?limit=${limit}${status ? `&status=${status}` : ""}`
    ),
  notificationAction: (id: string, action: "read" | "ack" | "dismiss") =>
    post<Notification>(`/notifications/${id}/${action}`),
  signals: (limit = 50) => get<Signal[]>(`/signals?limit=${limit}`),
  signalFeedback: (id: string, verdict: string, note?: string) =>
    post<unknown>(`/signals/${id}/feedback`, { verdict, note }),
  digest: (days = 7) => get<Record<string, unknown>>(`/digest?days=${days}`),
};
