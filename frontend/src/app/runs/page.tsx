"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type Run } from "@/lib/api";
import { formatDate, durationMs } from "@/lib/utils";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { EmptyState, ErrorState, PageHeader, Skeleton, StatusPill } from "@/components/ui";

function taskOf(input: Record<string, unknown> | null): string {
  if (!input) return "—";
  const v = input.task ?? input.message;
  return v ? String(v) : "—";
}

function NewRunModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const { show } = useToast();
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });
  const [agentId, setAgentId] = useState("");
  const [task, setTask] = useState("");

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

  const selected = agents.find((a) => a.id === agentId);

  return (
    <Modal open={open} onClose={onClose} title="New Run">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="form-field">
          <label className="hive-label" htmlFor="rp-agent">Agent</label>
          <select id="rp-agent" className="hive-select" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
            <option value="">Select an agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {selected && (
            <p className="hive-hint">
              {selected.model} · {selected.tools.length
                ? `${selected.tools.length} tool${selected.tools.length > 1 ? "s" : ""}`
                : "no tools"}
            </p>
          )}
        </div>
        <div className="form-field">
          <label className="hive-label" htmlFor="rp-task">Task</label>
          <textarea
            id="rp-task"
            className="hive-textarea"
            placeholder="Describe the task for the agent…"
            rows={5}
            value={task}
            onChange={(e) => setTask(e.target.value)}
          />
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, paddingTop: 4 }}>
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

function DeleteRunConfirm({
  run, onCancel, onConfirm, isPending,
}: { run: Run; onCancel: () => void; onConfirm: () => void; isPending: boolean }) {
  return (
    <Modal open onClose={onCancel} title="Delete Run">
      <p style={{ fontSize: 13, color: "var(--c-text-2)", marginBottom: 20, lineHeight: 1.6 }}>
        Delete run{" "}
        <strong style={{ fontFamily: "var(--font-mono)", color: "var(--c-text-1)" }}>
          {run.id.slice(0, 8)}
        </strong>
        ? Its steps and tool-call records are removed too. This cannot be undone.
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

const COL = "88px 104px 150px 1fr 118px 70px 44px";
const HEADS = ["Run", "Status", "Agent", "Task", "Started", "Took", ""];
const FILTERS = ["all", "running", "completed", "failed"] as const;
type Filter = (typeof FILTERS)[number];

export default function RunsPage() {
  const qc = useQueryClient();
  const { show } = useToast();
  const [newRunOpen, setNewRunOpen] = useState(false);
  const [delTarget, setDelTarget] = useState<Run | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");

  const runsQ = useQuery({ queryKey: ["runs"], queryFn: api.runs.list, refetchInterval: 4000 });
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });

  const runs = runsQ.data ?? [];
  const agentMap = Object.fromEntries(agents.map((a) => [a.id, a.name]));

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: runs.length, running: 0, completed: 0, failed: 0 };
    for (const r of runs) {
      // "pending" is not its own tab — it reads as in-flight to the user.
      const k = r.status === "pending" ? "running" : r.status;
      if (k in c) c[k] += 1;
    }
    return c;
  }, [runs]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return runs.filter((r) => {
      const status = r.status === "pending" ? "running" : r.status;
      if (filter !== "all" && status !== filter) return false;
      if (!q) return true;
      const agentName = r.agent_id ? agentMap[r.agent_id] ?? "" : "";
      return (
        r.id.toLowerCase().includes(q) ||
        agentName.toLowerCase().includes(q) ||
        taskOf(r.input).toLowerCase().includes(q)
      );
    });
  }, [runs, filter, search, agentMap]);

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
    <div style={{ maxWidth: 1140, margin: "0 auto", padding: "40px 40px 64px" }}>
      <PageHeader
        eyebrow="Platform"
        title="Runs"
        subtitle="Every task submitted to an agent, with its full execution trace."
        actions={
          <button className="hive-btn hive-btn-primary" onClick={() => setNewRunOpen(true)}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
              <path d="M6 1V11M1 6H11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            New Run
          </button>
        }
      />

      {runsQ.isError && (
        <div style={{ marginBottom: 20 }}>
          <ErrorState error={runsQ.error} onRetry={() => runsQ.refetch()} />
        </div>
      )}

      {/* Filter + search */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 4, padding: 3, borderRadius: 9, background: "var(--c-raised)", border: "1px solid var(--c-border)" }}>
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: "5px 12px",
                borderRadius: 6,
                border: "none",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 500,
                textTransform: "capitalize",
                fontFamily: "var(--font-sans)",
                background: filter === f ? "var(--c-surface)" : "transparent",
                color: filter === f ? "var(--c-text-1)" : "var(--c-text-3)",
                transition: "background 120ms ease, color 120ms ease",
              }}
            >
              {f}
              <span style={{ marginLeft: 6, fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--c-text-3)" }}>
                {counts[f] ?? 0}
              </span>
            </button>
          ))}
        </div>

        <input
          className="hive-input"
          style={{ flex: 1, minWidth: 200, maxWidth: 320 }}
          placeholder="Search by task, agent, or run id…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search runs"
        />
      </div>

      <div className="hive-card" style={{ overflow: "hidden" }}>
        {visible.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: COL,
              gap: 14,
              padding: "10px 20px",
              borderBottom: "1px solid var(--c-border)",
            }}
          >
            {HEADS.map((h, i) => (
              <span key={i} className="hive-eyebrow">{h}</span>
            ))}
          </div>
        )}

        {runsQ.isLoading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 16 }}>
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} height={36} />
            ))}
          </div>
        )}

        {visible.map((run) => (
          <div
            key={run.id}
            className="hive-row"
            style={{
              display: "grid",
              gridTemplateColumns: COL,
              gap: 14,
              alignItems: "center",
              padding: "12px 20px",
              borderBottom: "1px solid var(--c-divider)",
            }}
          >
            <Link
              href={`/runs/${run.id}`}
              style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-accent)", textDecoration: "none" }}
            >
              {run.id.slice(0, 8)}
            </Link>
            <StatusPill status={run.status} />
            <span
              style={{ fontSize: 12, color: "var(--c-text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
            >
              {run.agent_id ? agentMap[run.agent_id] ?? run.agent_id.slice(0, 8) : "—"}
            </span>
            <Link
              href={`/runs/${run.id}`}
              title={taskOf(run.input)}
              style={{
                fontSize: 13,
                color: "var(--c-text-1)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                textDecoration: "none",
              }}
            >
              {taskOf(run.input)}
            </Link>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
              {formatDate(run.started_at)}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
              {durationMs(run.started_at, run.finished_at)}
            </span>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                className="hive-icon-btn danger"
                disabled={run.status === "running"}
                onClick={() => setDelTarget(run)}
                aria-label={`Delete run ${run.id.slice(0, 8)}`}
                title={run.status === "running" ? "Cannot delete a running run" : "Delete run"}
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
                  <path d="M2.5 3.5h9M5.5 3.5V2.5h3v1M3.5 3.5l.6 8h5.8l.6-8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        ))}

        {!runsQ.isLoading && visible.length === 0 && (
          <EmptyState
            icon={
              <svg width="20" height="20" viewBox="0 0 15 15" fill="none" aria-hidden>
                <path d="M3 2L12 7.5L3 13V2Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
              </svg>
            }
            title={runs.length === 0 ? "No runs yet" : "No matching runs"}
            description={
              runs.length === 0
                ? "Submit a task to an agent and its execution trace will appear here."
                : "Try a different search term or filter."
            }
            action={
              runs.length === 0 ? (
                <button className="hive-btn hive-btn-primary" onClick={() => setNewRunOpen(true)}>
                  Submit your first run
                </button>
              ) : (
                <button
                  className="hive-btn hive-btn-ghost"
                  onClick={() => {
                    setFilter("all");
                    setSearch("");
                  }}
                >
                  Clear filters
                </button>
              )
            }
          />
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
