const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export type Agent = {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  model: string;
  tools: string[];
  created_at: string;
  updated_at: string;
};

export type Run = {
  id: string;
  agent_id: string | null;
  status: "pending" | "running" | "completed" | "failed";
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  error: string | null;
  metadata: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type Step = {
  id: string;
  run_id: string;
  sequence: number;
  node: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
};

export type ToolCall = {
  id: string;
  tool_name: string;
  mcp_server: string | null;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  error: string | null;
  duration_ms: number | null;
  called_at: string;
};

export type RunDetail = Run & { steps: Step[]; tool_calls: ToolCall[] };

export type Document = {
  id: string;
  name: string;
  content_type: string;
  size_bytes: number | null;
  embedded: boolean;
  created_at: string;
};

export const api = {
  agents: {
    list: () => apiFetch<Agent[]>("/api/agents"),
    get: (id: string) => apiFetch<Agent>(`/api/agents/${id}`),
    create: (body: Partial<Agent>) =>
      apiFetch<Agent>("/api/agents", { method: "POST", body: JSON.stringify(body) }),
    delete: (id: string) => apiFetch<void>(`/api/agents/${id}`, { method: "DELETE" }),
  },
  runs: {
    list: () => apiFetch<Run[]>("/api/runs"),
    get: (id: string) => apiFetch<RunDetail>(`/api/runs/${id}`),
    create: (body: { agent_id: string; input: Record<string, unknown> }) =>
      apiFetch<Run>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  },
  documents: {
    list: () => apiFetch<Document[]>("/api/documents"),
    delete: (id: string) => apiFetch<void>(`/api/documents/${id}`, { method: "DELETE" }),
  },
};
