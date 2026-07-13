const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type Agent = {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  model: string;
  tools: string[];
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AgentCreate = {
  name: string;
  description?: string;
  system_prompt: string;
  model: string;
  tools: string[];
};

export type Run = {
  id: string;
  agent_id: string | null;
  status: "pending" | "running" | "completed" | "failed";
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  error: string | null;
  run_metadata: Record<string, unknown>;
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
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
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

export type WorkspaceFile = {
  name: string;
  path: string;
  is_dir: boolean;
  size: number | null;
};

export type Document = {
  id: string;
  name: string;
  content_type: string;
  size_bytes: number | null;
  embedded: boolean;
  created_at: string;
};

export const AVAILABLE_TOOLS = [
  { id: "read_file",       label: "read_file",       desc: "Read files from workspace" },
  { id: "write_file",      label: "write_file",      desc: "Write files to workspace" },
  { id: "list_files",      label: "list_files",      desc: "List files in workspace" },
  { id: "web_search",      label: "web_search",      desc: "Search the web" },
  { id: "query_database",  label: "query_database",  desc: "Run SQL queries" },
  { id: "http_get",        label: "http_get",        desc: "Fetch URLs via HTTP" },
  { id: "list_documents",  label: "list_documents",  desc: "List knowledge base documents" },
  { id: "read_document",   label: "read_document",   desc: "Read a document from knowledge base" },
] as const;

export const MODELS = [
  { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B (default)" },
  { id: "llama-3.1-8b-instant",    label: "Llama 3.1 8B (fast)" },
  { id: "gemma2-9b-it",            label: "Gemma 2 9B" },
  { id: "mixtral-8x7b-32768",      label: "Mixtral 8x7B" },
] as const;

export const SYSTEM_PROMPT_PRESETS = [
  {
    label: "Research assistant",
    prompt: "You are a research assistant. Answer questions clearly and concisely, citing sources when you search the web. Break down complex topics into understandable explanations.",
  },
  {
    label: "Code helper",
    prompt: "You are an expert software engineer. Help with debugging, code review, and implementation questions. Write clean, well-reasoned code with brief explanations.",
  },
  {
    label: "Data analyst",
    prompt: "You are a data analyst with SQL expertise. When asked about data, query the database to get real numbers. Present findings clearly with key insights highlighted.",
  },
  {
    label: "General assistant",
    prompt: "You are a helpful assistant. Complete tasks accurately and efficiently. Use available tools when needed to gather information or take actions.",
  },
] as const;

export const api = {
  agents: {
    list:   ()                    => apiFetch<Agent[]>("/api/agents"),
    get:    (id: string)          => apiFetch<Agent>(`/api/agents/${id}`),
    create: (body: AgentCreate)   => apiFetch<Agent>("/api/agents",        { method: "POST",   body: JSON.stringify(body) }),
    delete: (id: string)          => apiFetch<void>(`/api/agents/${id}`,   { method: "DELETE" }),
  },
  runs: {
    list:   ()              => apiFetch<Run[]>("/api/runs"),
    get:    (id: string)    => apiFetch<RunDetail>(`/api/runs/${id}`),
    create: (agentId: string, task: string) =>
      apiFetch<Run>("/api/runs", {
        method: "POST",
        body: JSON.stringify({ agent_id: agentId, input: { task } }),
      }),
    delete: (id: string)    => apiFetch<void>(`/api/runs/${id}`, { method: "DELETE" }),
  },
  documents: {
    list:       ()           => apiFetch<Document[]>("/api/documents"),
    getContent: (id: string) => apiFetch<{ id: string; name: string; content: string; content_type: string }>(`/api/documents/${id}/content`),
    delete:     (id: string) => apiFetch<void>(`/api/documents/${id}`, { method: "DELETE" }),
  },
  workspace: {
    list:    (dir?: string) => apiFetch<WorkspaceFile[]>(`/api/workspace/files${dir ? `?directory=${encodeURIComponent(dir)}` : ""}`),
    read:    (path: string) => apiFetch<{ path: string; content: string }>(`/api/workspace/files/content?path=${encodeURIComponent(path)}`),
    delete:  (path: string) => apiFetch<{ deleted: string }>(`/api/workspace/files?path=${encodeURIComponent(path)}`, { method: "DELETE" }),
  },
};
