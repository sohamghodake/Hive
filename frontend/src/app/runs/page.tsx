"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type Run } from "@/lib/api";
import { statusColor, statusMuted, formatDate, durationMs } from "@/lib/utils";
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
      show("Run submitted", "info");
      setAgentId("");
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
          <select className="hive-select" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
            <option value="">Select an agent…</option>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="hive-label">Task</label>
          <textarea
            className="hive-textarea"
            placeholder="Describe the task for the agent…"
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

function DeleteRunConfirm({ run, onCancel, onConfirm, isPending }: {
  run: Run; onCancel: () => void; onConfirm: () => void; isPending: boolean;
}) {
  return (
    <Modal open onClose={onCancel} title="Delete Run">
      <p style={{ fontSize: 13, color: "var(--c-text-2)", marginBottom: 20 }}>
        Delete run <strong style={{ fontFamily: "var(--font-mono)", color: "var(--c-text-1)" }}>{run.id.slice(0, 8)}…</strong>? All steps and tool call records will be removed.
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

const COL = "110px 110px 160px 1fr 100px 80px";
const HEADS = ["Run ID", "Status", "Agent", "Task", "Started", ""];

export default function RunsPage() {
  const qc = useQueryClient();
  const { show } = useToast();
  const [newRunOpen, setNewRunOpen]     = useState(false);
  const [delTarget, setDelTarget]       = useState<Run | null>(null);

  const { data: runs = [],   isLoading: runsLoading } = useQuery({ queryKey: ["runs"],   queryFn: api.runs.list,   refetchInterval: 4000 });
  const { data: agents = [] }                          = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });

  const agentMap = Object.fromEntries(agents.map((a) => [a.id, a.name]));

  const deleteRun = useMutation({
    mutationFn: (id: string) => api.runs.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      show("Run deleted", "success");
      setDelTarget(null);
    },
    onError: (e) => show(String(e), "error"),
  });

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "40px 40px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: "0 0 4px 0" }}>
            Platform
          </p>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 600, color: "var(--c-text-1)", margin: 0 }}>
            Runs
          </h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", fontVariantNumeric: "tabular-nums" }}>
            {runs.length} total
          </span>
          <button className="hive-btn hive-btn-primary" onClick={() => setNewRunOpen(true)}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1V11M1 6H11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            New Run
          </button>
        </div>
      </div>

      {runsLoading && <p style={{ fontSize: 13, color: "var(--c-text-3)" }}>Loading…</p>}

      <div className="hive-card" style={{ overflow: "hidden" }}>
        {/* Header row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: COL,
            gap: 16,
            padding: "10px 20px",
            borderBottom: "1px solid var(--c-border)",
          }}
        >
          {HEADS.map((h) => (
            <span key={h} style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)" }}>
              {h}
            </span>
          ))}
        </div>

        {runs.map((run) => (
          <div
            key={run.id}
            className="hive-row"
            style={{ display: "grid", gridTemplateColumns: COL, gap: 16, alignItems: "center", padding: "13px 20px", borderBottom: "1px solid var(--c-divider)" }}
          >
            <Link
              href={`/runs/${run.id}`}
              style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-2)", textDecoration: "none" }}
            >
              {run.id.slice(0, 8)}
            </Link>
            <StatusPill status={run.status} />
            <span style={{ fontSize: 12, color: "var(--c-text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {run.agent_id ? (agentMap[run.agent_id] ?? run.agent_id.slice(0, 8)) : "—"}
            </span>
            <Link
              href={`/runs/${run.id}`}
              style={{ fontSize: 12, color: "var(--c-text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textDecoration: "none" }}
            >
              {run.input && "task" in run.input
                ? String(run.input.task).slice(0, 70)
                : run.input && "message" in run.input
                ? String(run.input.message).slice(0, 70)
                : "—"}
            </Link>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
              {formatDate(run.started_at)}
            </span>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                className="hive-btn hive-btn-danger"
                style={{ padding: "3px 10px", fontSize: 11 }}
                disabled={run.status === "running"}
                onClick={() => setDelTarget(run)}
                title={run.status === "running" ? "Cannot delete a running run" : "Delete run"}
              >
                Delete
              </button>
            </div>
          </div>
        ))}

        {!runsLoading && runs.length === 0 && (
          <div style={{ padding: "48px 20px", textAlign: "center" }}>
            <p style={{ fontSize: 13, color: "var(--c-text-3)", marginBottom: 16 }}>No runs yet.</p>
            <button className="hive-btn hive-btn-primary" onClick={() => setNewRunOpen(true)}>
              Submit your first run
            </button>
          </div>
        )}
      </div>

      <NewRunModal open={newRunOpen} onClose={() => setNewRunOpen(false)} />
      {delTarget && (
        <DeleteRunConfirm
          run={delTarget}
          onCancel={() => setDelTarget(null)}
          onConfirm={() => deleteRun.mutate(delTarget.id)}
          isPending={deleteRun.isPending}
        />
      )}
    </div>
  );
}
