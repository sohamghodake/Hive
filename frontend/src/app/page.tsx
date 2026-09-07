"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
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
      show("Run submitted — watching live", "info");
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
          <label className="hive-label" htmlFor="run-agent">Agent</label>
          <select id="run-agent" className="hive-select" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
            <option value="">Select an agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {selected && (
            <p className="hive-hint">
              {selected.model} · {selected.tools.length
                ? `${selected.tools.length} tool${selected.tools.length > 1 ? "s" : ""}: ${selected.tools.join(", ")}`
                : "no tools — answers from the model only"}
            </p>
          )}
        </div>
        <div className="form-field">
          <label className="hive-label" htmlFor="run-task">Task</label>
          <textarea
            id="run-task"
            className="hive-textarea"
            placeholder="What should the agent do?"
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

function MetricCard({ label, value, color, hint }: { label: string; value: React.ReactNode; color: string; hint?: string }) {
  return (
    <div className="hive-card" style={{ padding: "18px 20px" }}>
      <p className="hive-eyebrow" style={{ marginBottom: 10 }}>{label}</p>
      <p
        style={{
          fontFamily: "var(--font-display)",
          fontSize: 30,
          fontWeight: 400,
          lineHeight: 1,
          color,
          fontVariantNumeric: "tabular-nums",
          margin: 0,
        }}
      >
        {value}
      </p>
      {hint && <p className="hive-hint" style={{ marginTop: 8 }}>{hint}</p>}
    </div>
  );
}

const COL = "92px 108px 1fr 130px 80px";

export default function OverviewPage() {
  const [newRunOpen, setNewRunOpen] = useState(false);

  const runsQ = useQuery({ queryKey: ["runs"], queryFn: api.runs.list, refetchInterval: 5000 });
  const agentsQ = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });

  const runs = runsQ.data ?? [];
  const agents = agentsQ.data ?? [];
  const agentMap = Object.fromEntries(agents.map((a) => [a.id, a.name]));

  const completed = runs.filter((r) => r.status === "completed").length;
  const live = runs.filter((r) => r.status === "running" || r.status === "pending").length;
  const failed = runs.filter((r) => r.status === "failed").length;
  const settled = completed + failed;
  const successRate = settled > 0 ? Math.round((completed / settled) * 100) : null;

  return (
    <div style={{ maxWidth: 1040, margin: "0 auto", padding: "40px 40px 64px" }}>
      <PageHeader
        title="Overview"
        subtitle={new Date().toLocaleDateString("en-US", {
          weekday: "long",
          month: "long",
          day: "numeric",
        })}
        actions={
          <button className="hive-btn hive-btn-primary" onClick={() => setNewRunOpen(true)}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
              <path d="M2 2L10 6L2 10V2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
            New Run
          </button>
        }
      />

      {runsQ.isError && (
        <div style={{ marginBottom: 24 }}>
          <ErrorState error={runsQ.error} onRetry={() => runsQ.refetch()} />
        </div>
      )}

      {/* Metrics */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
          marginBottom: 32,
        }}
      >
        {runsQ.isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="hive-card" style={{ padding: "18px 20px" }}>
              <Skeleton width={70} height={10} />
              <div style={{ height: 12 }} />
              <Skeleton width={50} height={30} />
            </div>
          ))
        ) : (
          <>
            <MetricCard
              label="Total runs"
              value={runs.length}
              color="var(--c-text-1)"
              hint={`${agents.length} agent${agents.length === 1 ? "" : "s"} configured`}
            />
            <MetricCard
              label="Success rate"
              value={successRate === null ? "—" : `${successRate}%`}
              color={
                successRate === null
                  ? "var(--c-text-3)"
                  : successRate >= 70
                  ? "var(--c-ok)"
                  : successRate >= 40
                  ? "var(--c-warn)"
                  : "var(--c-err)"
              }
              hint={settled > 0 ? `${completed} of ${settled} finished runs` : "no finished runs yet"}
            />
            <MetricCard
              label="In flight"
              value={live}
              color={live > 0 ? "var(--c-live)" : "var(--c-text-3)"}
              hint={live > 0 ? "running or queued" : "idle"}
            />
            <MetricCard
              label="Failed"
              value={failed}
              color={failed > 0 ? "var(--c-err)" : "var(--c-text-3)"}
              hint={failed > 0 ? "open a run to see the error" : "none"}
            />
          </>
        )}
      </div>

      {/* Recent runs */}
      <div style={{ marginBottom: 12, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <p className="hive-eyebrow">Recent runs</p>
        <Link
          href="/runs"
          style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-accent)", textDecoration: "none" }}
        >
          View all →
        </Link>
      </div>

      <div className="hive-card" style={{ overflow: "hidden" }}>
        {!runsQ.isLoading && runs.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: COL,
              padding: "10px 20px",
              borderBottom: "1px solid var(--c-border)",
              gap: 16,
            }}
          >
            {["Run", "Status", "Task", "Agent", "Time"].map((h) => (
              <span key={h} className="hive-eyebrow">{h}</span>
            ))}
          </div>
        )}

        {runsQ.isLoading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 16 }}>
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} height={36} />
            ))}
          </div>
        )}

        {!runsQ.isLoading &&
          runs.slice(0, 10).map((run) => (
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
              <span
                title={taskOf(run.input)}
                style={{
                  fontSize: 13,
                  color: "var(--c-text-1)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {taskOf(run.input)}
              </span>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--c-text-2)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {run.agent_id ? agentMap[run.agent_id] ?? "—" : "—"}
              </span>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--c-text-3)",
                  textAlign: "right",
                }}
              >
                {timeAgo(run.created_at)}
              </span>
            </Link>
          ))}

        {!runsQ.isLoading && runs.length === 0 && (
          <EmptyState
            icon={
              <svg width="20" height="20" viewBox="0 0 15 15" fill="none" aria-hidden>
                <path d="M3 2L12 7.5L3 13V2Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
              </svg>
            }
            title="No runs yet"
            description={
              agents.length === 0
                ? "Create an agent first, then submit a task to see it execute here."
                : "Submit a task to an agent and its execution trace will appear here."
            }
            action={
              agents.length === 0 ? (
                <Link href="/agents" className="hive-btn hive-btn-primary" style={{ textDecoration: "none" }}>
                  Create an agent
                </Link>
              ) : (
                <button className="hive-btn hive-btn-primary" onClick={() => setNewRunOpen(true)}>
                  Submit first run
                </button>
              )
            }
          />
        )}
      </div>

      <NewRunModal open={newRunOpen} onClose={() => setNewRunOpen(false)} />
    </div>
  );
}
