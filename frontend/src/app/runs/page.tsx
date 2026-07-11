"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { statusColor, statusMuted, formatDate, durationMs } from "@/lib/utils";

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

const COL = "110px 110px 1fr 120px 120px 70px";
const HEADS = ["Run ID", "Status", "Agent", "Started", "Finished", "Duration"];

export default function RunsPage() {
  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: api.runs.list,
    refetchInterval: 4000,
  });

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "40px 40px" }}>
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
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", fontVariantNumeric: "tabular-nums" }}>
          {runs.length} total
        </span>
      </div>

      {isLoading && (
        <p style={{ fontSize: 13, color: "var(--c-text-3)" }}>Loading…</p>
      )}

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

        {runs.map((run) => (
          <Link
            key={run.id}
            href={`/runs/${run.id}`}
            className="hive-row"
            style={{
              display: "grid",
              gridTemplateColumns: COL,
              gap: 16,
              alignItems: "center",
              padding: "13px 20px",
              borderBottom: "1px solid var(--c-divider)",
              textDecoration: "none",
            }}
          >
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-2)" }}>
              {run.id.slice(0, 8)}
            </span>
            <StatusPill status={run.status} />
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {run.agent_id ? run.agent_id.slice(0, 8) : "—"}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
              {formatDate(run.started_at)}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
              {formatDate(run.finished_at)}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
              {durationMs(run.started_at, run.finished_at)}
            </span>
          </Link>
        ))}

        {!isLoading && runs.length === 0 && (
          <p style={{ padding: "40px 20px", textAlign: "center", fontSize: 13, color: "var(--c-text-3)" }}>
            No runs yet.
          </p>
        )}
      </div>
    </div>
  );
}
