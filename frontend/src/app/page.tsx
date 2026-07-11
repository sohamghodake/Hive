"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, type Run } from "@/lib/api";
import { statusColor, statusMuted, timeAgo } from "@/lib/utils";

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
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          flexShrink: 0,
          background: statusColor(status),
        }}
      />
      {status}
    </span>
  );
}

const COL = "110px 110px 1fr 90px";

export default function OverviewPage() {
  const { data: runs = [] }   = useQuery({ queryKey: ["runs"],   queryFn: api.runs.list });
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });

  const completed = runs.filter((r) => r.status === "completed").length;
  const live      = runs.filter((r) => r.status === "running").length;
  const failed    = runs.filter((r) => r.status === "failed").length;

  const stats = [
    { label: "Total runs",  value: runs.length,   color: "var(--c-text-1)" },
    { label: "Completed",   value: completed,      color: "var(--c-ok)" },
    { label: "Running",     value: live,           color: "var(--c-live)" },
    { label: "Failed",      value: failed,         color: "var(--c-err)" },
    { label: "Agents",      value: agents.length,  color: "var(--c-accent)" },
  ];

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "40px 40px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 32 }}>
        <h1
          style={{
            fontFamily: "var(--font-display)",
            fontSize: 22,
            fontWeight: 600,
            color: "var(--c-text-1)",
            margin: 0,
          }}
        >
          Overview
        </h1>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--c-text-3)",
          }}
        >
          {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
        </span>
      </div>

      {/* Metrics strip */}
      <div
        className="hive-card"
        style={{ display: "flex", overflow: "hidden", marginBottom: 32 }}
      >
        {stats.map((s, i) => (
          <div
            key={s.label}
            style={{
              flex: 1,
              padding: "20px 24px",
              borderRight: i < stats.length - 1 ? "1px solid var(--c-border)" : undefined,
            }}
          >
            <p
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                textTransform: "uppercase",
                letterSpacing: "0.09em",
                color: "var(--c-text-3)",
                margin: "0 0 10px 0",
              }}
            >
              {s.label}
            </p>
            <p
              style={{
                fontFamily: "var(--font-display)",
                fontSize: 36,
                fontWeight: 300,
                lineHeight: 1,
                color: s.color,
                fontVariantNumeric: "tabular-nums",
                margin: 0,
              }}
            >
              {s.value}
            </p>
          </div>
        ))}
      </div>

      {/* Recent runs */}
      <div style={{ marginBottom: 12, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            textTransform: "uppercase",
            letterSpacing: "0.09em",
            color: "var(--c-text-3)",
            margin: 0,
          }}
        >
          Recent runs
        </p>
        <Link
          href="/runs"
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            color: "var(--c-accent)",
            textDecoration: "none",
          }}
        >
          View all →
        </Link>
      </div>

      <div className="hive-card" style={{ overflow: "hidden" }}>
        {/* Table header */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: COL,
            padding: "10px 20px",
            borderBottom: "1px solid var(--c-border)",
            gap: 16,
          }}
        >
          {["Run ID", "Status", "Task", "Time"].map((h) => (
            <span
              key={h}
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                textTransform: "uppercase",
                letterSpacing: "0.09em",
                color: "var(--c-text-3)",
              }}
            >
              {h}
            </span>
          ))}
        </div>

        {runs.slice(0, 8).map((run) => (
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
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--c-text-2)",
              }}
            >
              {run.id.slice(0, 8)}
            </span>
            <StatusPill status={run.status} />
            <span
              style={{
                fontSize: 13,
                color: "var(--c-text-2)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {run.input && "task" in run.input
                ? String(run.input.task).slice(0, 80)
                : run.input && "message" in run.input
                ? String(run.input.message).slice(0, 80)
                : "—"}
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

        {runs.length === 0 && (
          <p
            style={{
              padding: "40px 20px",
              textAlign: "center",
              fontSize: 13,
              color: "var(--c-text-3)",
            }}
          >
            No runs yet — create an agent and submit a task.
          </p>
        )}
      </div>
    </div>
  );
}
