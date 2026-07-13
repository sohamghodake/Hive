"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, type Agent, type AgentCreate, AVAILABLE_TOOLS, MODELS, SYSTEM_PROMPT_PRESETS } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";

const EMPTY_FORM: AgentCreate = {
  name: "",
  description: "",
  system_prompt: "",
  model: "llama-3.3-70b-versatile",
  tools: ["read_file", "web_search"],
};

function AgentFormModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { show } = useToast();
  const [form, setForm] = useState<AgentCreate>(EMPTY_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof AgentCreate, string>>>({});

  const create = useMutation({
    mutationFn: () => api.agents.create(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      show("Agent created successfully", "success");
      setForm(EMPTY_FORM);
      setErrors({});
      onClose();
    },
    onError: (e) => show(String(e), "error"),
  });

  function validate() {
    const errs: typeof errors = {};
    if (!form.name.trim()) errs.name = "Name is required";
    if (!form.system_prompt.trim()) errs.system_prompt = "System prompt is required";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function toggleTool(id: string) {
    setForm((f) => ({
      ...f,
      tools: f.tools.includes(id) ? f.tools.filter((t) => t !== id) : [...f.tools, id],
    }));
  }

  return (
    <Modal open={open} onClose={onClose} title="New Agent" width={560}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* Name */}
        <div className="form-field">
          <label className="hive-label">Name *</label>
          <input
            className="hive-input"
            placeholder="research-assistant"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          {errors.name && <p style={{ fontSize: 11, color: "var(--c-err)", margin: 0 }}>{errors.name}</p>}
        </div>

        {/* Description */}
        <div className="form-field">
          <label className="hive-label">Description</label>
          <input
            className="hive-input"
            placeholder="Brief description of what this agent does"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </div>

        {/* System Prompt */}
        <div className="form-field">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
            <label className="hive-label" style={{ margin: 0 }}>System Prompt *</label>
            <div style={{ display: "flex", gap: 4 }}>
              {SYSTEM_PROMPT_PRESETS.map((p) => (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => setForm({ ...form, system_prompt: p.prompt })}
                  style={{
                    fontSize: 10,
                    fontFamily: "var(--font-mono)",
                    padding: "2px 7px",
                    borderRadius: 4,
                    cursor: "pointer",
                    color: "var(--c-text-3)",
                    background: "transparent",
                    border: "1px solid var(--c-border)",
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          <textarea
            className="hive-textarea"
            placeholder="You are a helpful assistant..."
            rows={4}
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
          />
          {errors.system_prompt && <p style={{ fontSize: 11, color: "var(--c-err)", margin: 0 }}>{errors.system_prompt}</p>}
        </div>

        {/* Model */}
        <div className="form-field">
          <label className="hive-label">Model</label>
          <select
            className="hive-select"
            value={form.model}
            onChange={(e) => setForm({ ...form, model: e.target.value })}
          >
            {MODELS.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
        </div>

        {/* Tools */}
        <div className="form-field">
          <label className="hive-label">Tools</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {AVAILABLE_TOOLS.map((t) => (
              <button
                key={t.id}
                type="button"
                title={t.desc}
                className={`tool-chip ${form.tools.includes(t.id) ? "active" : ""}`}
                onClick={() => toggleTool(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, paddingTop: 8 }}>
          <button type="button" className="hive-btn hive-btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="hive-btn hive-btn-primary"
            disabled={create.isPending}
            onClick={() => validate() && create.mutate()}
          >
            {create.isPending ? "Creating…" : "Create Agent"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function RunModal({
  open,
  onClose,
  preselectedAgentId,
}: {
  open: boolean;
  onClose: () => void;
  preselectedAgentId?: string;
}) {
  const router = useRouter();
  const { show } = useToast();
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });
  const [agentId, setAgentId] = useState(preselectedAgentId ?? "");
  const [task, setTask] = useState("");

  useEffect(() => {
    if (preselectedAgentId) setAgentId(preselectedAgentId);
  }, [preselectedAgentId]);

  const submit = useMutation({
    mutationFn: () => api.runs.create(agentId, task),
    onSuccess: (run) => {
      show("Run submitted", "info");
      setTask("");
      onClose();
      router.push(`/runs/${run.id}`);
    },
    onError: (e) => show(String(e), "error"),
  });

  return (
    <Modal open={open} onClose={onClose} title="New Run">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="form-field">
          <label className="hive-label">Agent</label>
          <select
            className="hive-select"
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
          >
            <option value="">Select an agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label className="hive-label">Task</label>
          <textarea
            className="hive-textarea"
            placeholder="What should the agent do?"
            rows={4}
            value={task}
            onChange={(e) => setTask(e.target.value)}
          />
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, paddingTop: 8 }}>
          <button type="button" className="hive-btn hive-btn-ghost" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className="hive-btn hive-btn-primary"
            disabled={!agentId || !task.trim() || submit.isPending}
            onClick={() => submit.mutate()}
          >
            {submit.isPending ? "Submitting…" : "Run Agent"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function DeleteConfirm({
  agent,
  onCancel,
  onConfirm,
  isPending,
}: {
  agent: Agent;
  onCancel: () => void;
  onConfirm: () => void;
  isPending: boolean;
}) {
  return (
    <Modal open onClose={onCancel} title="Delete Agent">
      <p style={{ fontSize: 13, color: "var(--c-text-2)", marginBottom: 20 }}>
        Delete <strong style={{ color: "var(--c-text-1)", fontFamily: "var(--font-mono)" }}>{agent.name}</strong>? This cannot be undone.
      </p>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <button className="hive-btn hive-btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="hive-btn hive-btn-danger" disabled={isPending} onClick={onConfirm}>
          {isPending ? "Deleting…" : "Delete"}
        </button>
      </div>
    </Modal>
  );
}

export default function AgentsPage() {
  const qc = useQueryClient();
  const { show } = useToast();
  const { data: agents = [], isLoading } = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });

  const [createOpen, setCreateOpen] = useState(false);
  const [runAgentId, setRunAgentId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Agent | null>(null);

  const deleteAgent = useMutation({
    mutationFn: (id: string) => api.agents.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] });
      show("Agent deleted", "success");
      setDeleteTarget(null);
    },
    onError: (e) => show(String(e), "error"),
  });

  function PlusIcon() {
    return (
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
        <path d="M6.5 1V12M1 6.5H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "40px 40px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: "0 0 4px 0" }}>
            Platform
          </p>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 600, color: "var(--c-text-1)", margin: 0 }}>
            Agents
          </h1>
        </div>
        <button className="hive-btn hive-btn-primary" onClick={() => setCreateOpen(true)}>
          <PlusIcon /> New Agent
        </button>
      </div>

      {isLoading && <p style={{ fontSize: 13, color: "var(--c-text-3)" }}>Loading…</p>}

      {!isLoading && agents.length === 0 && (
        <div className="hive-card" style={{ padding: "48px 24px", textAlign: "center" }}>
          <p style={{ fontSize: 22, margin: "0 0 8px 0" }}>🤖</p>
          <p style={{ fontSize: 14, fontWeight: 500, color: "var(--c-text-1)", margin: "0 0 6px 0" }}>No agents yet</p>
          <p style={{ fontSize: 13, color: "var(--c-text-3)", margin: "0 0 20px 0" }}>Create an agent to start running tasks.</p>
          <button className="hive-btn hive-btn-primary" onClick={() => setCreateOpen(true)}>
            <PlusIcon /> Create your first agent
          </button>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {agents.map((agent) => (
          <div key={agent.id} className="hive-card" style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
              <div style={{ minWidth: 0 }}>
                <h2 style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 600, color: "var(--c-text-1)", margin: "0 0 3px 0" }}>
                  {agent.name}
                </h2>
                {agent.description && (
                  <p style={{ fontSize: 13, color: "var(--c-text-2)", margin: 0 }}>{agent.description}</p>
                )}
              </div>
              <div style={{ display: "flex", gap: 8, flexShrink: 0, alignItems: "center" }}>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    padding: "4px 10px",
                    borderRadius: 6,
                    color: "var(--c-accent)",
                    background: "var(--c-accent-muted)",
                    border: "1px solid var(--c-accent-border)",
                  }}
                >
                  {agent.model}
                </span>
              </div>
            </div>

            {/* System prompt preview */}
            {agent.system_prompt && (
              <p
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--c-text-3)",
                  background: "var(--c-raised)",
                  borderLeft: "2px solid var(--c-border)",
                  padding: "7px 12px",
                  borderRadius: "0 6px 6px 0",
                  lineHeight: 1.6,
                  margin: 0,
                }}
              >
                {agent.system_prompt.slice(0, 120)}{agent.system_prompt.length > 120 ? "…" : ""}
              </p>
            )}

            {/* Footer: tools + actions */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                {agent.tools.map((t) => (
                  <span
                    key={t}
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      padding: "2px 8px",
                      borderRadius: 4,
                      color: "var(--c-live)",
                      background: "var(--c-live-muted)",
                    }}
                  >
                    {t}
                  </span>
                ))}
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", alignSelf: "center", marginRight: 4 }}>
                  {formatDate(agent.created_at)}
                </span>
                <button
                  className="hive-btn hive-btn-ghost"
                  style={{ padding: "5px 12px", fontSize: 12 }}
                  onClick={() => setRunAgentId(agent.id)}
                >
                  ▶ Run
                </button>
                <button
                  className="hive-btn hive-btn-danger"
                  style={{ padding: "5px 12px", fontSize: 12 }}
                  onClick={() => setDeleteTarget(agent)}
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <AgentFormModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <RunModal
        open={runAgentId !== null}
        onClose={() => setRunAgentId(null)}
        preselectedAgentId={runAgentId ?? undefined}
      />
      {deleteTarget && (
        <DeleteConfirm
          agent={deleteTarget}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => deleteAgent.mutate(deleteTarget.id)}
          isPending={deleteAgent.isPending}
        />
      )}
    </div>
  );
}
