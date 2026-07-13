"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type Run } from "@/lib/api";
import { statusColor, statusMuted, timeAgo } from "@/lib/utils";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";

function StatusPill({ status }: { status: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "2px 8px",
        borderRadius: 6,
        fontSize: 11,
        fontWeight: 500,
        textTransform: "capitalize",
        color: statusColor(status),
        background: statusMuted(status),
      }}
    >
      <span
        className={status === "running" ? "anim-pulse" : ""}
        style={{ width: 6, height: 6, borderRadius: "50%", flexShrink: 0, background: statusColor(status) }}
      />
      {status}
    </span>
  );
}

function NewRunModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const { show } = useToast();
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });
  const [agentId, setAgentId] = useState("");
  const [task, setTask]       = useState("");

  const submit = useMutation({
    mutationFn: () => api.runs.create(agentId, task),
    onSuccess: (run) => {
      show("Run submitted — watching live", "info");
      setAgentId(""); setTask(""); onClose();
      router.push(`/runs/${run.id}`);
    },
    onError: (e) => show(String(e), "error"),
  });

  return (
    <Modal open={open} onClose={onClose} title="New Run">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="form-field">
          <label className="hive-label">Agent</label>
          <select className="hive-select" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
            <option value="">Select an agent…</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="hive-label">Task</label>
          <textarea
            className="hive-textarea"
            placeholder="What should the agent do?"
            rows={5}
            value={task}
            onChange={(e) => setTask(e.target.value)}
          />
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, paddingTop: 8 }}>
          <button className="hive-btn hive-btn-ghost" onClick={onClose}>Cancel</button>
          <button
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

const COL = "110px 110px 1fr 90px";

export default function OverviewPage() {
  const [newRunOpen, setNewRunOpen] = useState(false);

  const { data: runs = [] }   = useQuery({ queryKey: ["runs"],   queryFn: api.runs.list,   refetchInterval: 5000 });
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });
  const agentMap = Object.fromEntries(agents.map((a) => [a.id, a.name]));

  const completed = runs.filter((r) => r.status === "completed").length;
  const live      = runs.filter((r) => r.status === "running").length;
  const failed    = runs.filter((r) => r.status === "failed").length;
  const successRate = runs.length > 0
    ? Math.round((completed / runs.length) * 100)
    : null;

  const stats = [
    { label: "Total runs",    value: runs.length,   color: "var(--c-text-1)" },
    { label: "Completed",     value: completed,      color: "var(--c-ok)" },
    { label: "Running",       value: live,           color: "var(--c-live)" },
    { label: "Failed",        value: failed,         color: "var(--c-err)" },
    { label: "Agents",        value: agents.length,  color: "var(--c-accent)" },
    ...(successRate !== null
      ? [{ label: "Success rate", value: `${successRate}%`, color: successRate >= 70 ? "var(--c-ok)" : successRate >= 40 ? "var(--c-warn)" : "var(--c-err)" }]
      : []),
  ];

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "40px 40px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 32 }}>
        <div>
          <h1
            style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 600, color: "var(--c-text-1)", margin: "0 0 2px 0" }}
          >
            Overview
          </h1>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          </span>
        </div>
        <button className="hive-btn hive-btn-primary" onClick={() => setNewRunOpen(true)}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 2L10 6L2 10V2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
          </svg>
          New Run
        </button>
      </div>

      {/* Metrics strip */}
      <div className="hive-card" style={{ display: "flex", overflow: "hidden", marginBottom: 32 }}>
        {stats.map((s, i) => (
          <div
            key={s.label}
            style={{
              flex: 1,
              padding: "20px 24px",
              borderRight: i < stats.length - 1 ? "1px solid var(--c-border)" : undefined,
            }}
          >
            <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: "0 0 10px 0" }}>
              {s.label}
            </p>
            <p style={{ fontFamily: "var(--font-display)", fontSize: 34, fontWeight: 300, lineHeight: 1, color: s.color, fontVariantNumeric: "tabular-nums", margin: 0 }}>
              {s.value}
            </p>
          </div>
        ))}
      </div>

      {/* Recent runs */}
      <div style={{ marginBottom: 12, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: 0 }}>
          Recent runs
        </p>
        <Link href="/runs" style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-accent)", textDecoration: "none" }}>
          View all →
        </Link>
      </div>

      <div className="hive-card" style={{ overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: COL, padding: "10px 20px", borderBottom: "1px solid var(--c-border)", gap: 16 }}>
          {["Run ID", "Status", "Task", "Time"].map((h) => (
            <span key={h} style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)" }}>
              {h}
            </span>
          ))}
        </div>

        {runs.slice(0, 10).map((run) => (
          <Link
            key={run.id}
            href={`/runs/${run.id}`}
            className="hive-row"
            style={{
              display: "grid",
              gridTemplateColumns: COL,
              gap: 16,
              padding: "12px 20px",
              borderBottom: "1px solid var(--c-divider)",
              alignItems: "center",
              textDecoration: "none",
            }}
          >
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-2)" }}>
              {run.id.slice(0, 8)}
            </span>
            <StatusPill status={run.status} />
            <span style={{ fontSize: 13, color: "var(--c-text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {run.input && "task" in run.input
                ? String(run.input.task).slice(0, 80)
                : run.input && "message" in run.input
                ? String(run.input.message).slice(0, 80)
                : "—"}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", textAlign: "right" }}>
              {timeAgo(run.created_at)}
            </span>
          </Link>
        ))}

        {runs.length === 0 && (
          <div style={{ padding: "48px 20px", textAlign: "center" }}>
            <p style={{ fontSize: 13, color: "var(--c-text-3)", marginBottom: 16 }}>
              No runs yet. Create an agent and submit a task.
            </p>
            <button className="hive-btn hive-btn-primary" onClick={() => setNewRunOpen(true)}>
              Submit first run
            </button>
          </div>
        )}
      </div>

      <NewRunModal open={newRunOpen} onClose={() => setNewRunOpen(false)} />
    </div>
  );
}
