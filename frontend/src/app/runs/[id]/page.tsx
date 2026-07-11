"use client";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type RunDetail, type Step } from "@/lib/api";
import { statusColor, statusMuted, formatDate, durationMs } from "@/lib/utils";

function StatusPill({ status, large }: { status: string; large?: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: large ? "4px 10px" : "2px 8px",
        borderRadius: 6,
        fontSize: large ? 13 : 11,
        fontWeight: 500,
        textTransform: "capitalize",
        color: statusColor(status),
        background: statusMuted(status),
      }}
    >
      <span
        className={status === "running" ? "anim-pulse" : ""}
        style={{
          width: large ? 7 : 6,
          height: large ? 7 : 6,
          borderRadius: "50%",
          flexShrink: 0,
          background: statusColor(status),
        }}
      />
      {status}
    </span>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: 10,
        textTransform: "uppercase",
        letterSpacing: "0.09em",
        color: "var(--c-text-3)",
        margin: "0 0 12px 0",
      }}
    >
      {children}
    </p>
  );
}

function StepTimeline({ steps }: { steps: Step[] }) {
  if (steps.length === 0) {
    return <p style={{ fontSize: 13, color: "var(--c-text-3)" }}>No steps recorded.</p>;
  }

  return (
    <div>
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1;
        return (
          <div key={step.id} style={{ display: "flex", gap: 16 }}>
            {/* Track */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 28, flexShrink: 0 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  border: `1.5px solid ${statusColor(step.status)}`,
                  background: statusMuted(step.status),
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 10,
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                  color: statusColor(step.status),
                  flexShrink: 0,
                }}
              >
                {step.sequence}
              </div>
              {!isLast && (
                <div
                  style={{
                    width: 1,
                    flex: 1,
                    margin: "4px 0",
                    minHeight: 20,
                    background: "var(--c-border)",
                  }}
                />
              )}
            </div>

            {/* Content */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                height: 28,
                paddingBottom: isLast ? 0 : undefined,
                marginBottom: isLast ? 0 : 16,
              }}
            >
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 500, color: "var(--c-text-1)" }}>
                {step.node}
              </span>
              <StatusPill status={step.status} />
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
                {durationMs(step.started_at, step.finished_at)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ToolCallList({ run }: { run: RunDetail }) {
  if (run.tool_calls.length === 0) {
    return <p style={{ fontSize: 13, color: "var(--c-text-3)" }}>No tool calls recorded.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {run.tool_calls.map((tc) => (
        <details
          key={tc.id}
          style={{
            background: "var(--c-raised)",
            border: "1px solid var(--c-border)",
            borderRadius: 10,
            overflow: "hidden",
          }}
        >
          <summary
            className="hive-row"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "12px 16px",
              cursor: "pointer",
              listStyle: "none",
            }}
          >
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 500, color: "var(--c-live)" }}>
              {tc.tool_name}
            </span>
            {tc.mcp_server && (
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  padding: "2px 6px",
                  borderRadius: 4,
                  color: "var(--c-text-3)",
                  background: "var(--c-border)",
                }}
              >
                {tc.mcp_server}
              </span>
            )}
            {tc.error && (
              <span style={{ fontSize: 11, color: "var(--c-err)" }}>error</span>
            )}
            {tc.duration_ms != null && (
              <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", fontVariantNumeric: "tabular-nums" }}>
                {tc.duration_ms}ms
              </span>
            )}
          </summary>

          <div style={{ padding: "12px 16px", borderTop: "1px solid var(--c-border)", display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: "0 0 6px 0" }}>Input</p>
              <pre style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-2)", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", lineHeight: 1.6 }}>
                {JSON.stringify(tc.input, null, 2)}
              </pre>
            </div>
            {tc.output && (
              <div>
                <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: "0 0 6px 0" }}>Output</p>
                <pre style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-ok)", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", lineHeight: 1.6 }}>
                  {JSON.stringify(tc.output, null, 2)}
                </pre>
              </div>
            )}
            {tc.error && (
              <div>
                <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: "0 0 6px 0" }}>Error</p>
                <pre style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-err)", margin: 0, whiteSpace: "pre-wrap" }}>
                  {tc.error}
                </pre>
              </div>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}

function LiveStream({ runId }: { runId: string }) {
  const [events, setEvents] = useState<string[]>([]);
  const ref = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(`/api/runs/${runId}/stream`);
    ref.current = es;
    es.onmessage = (e) => setEvents((prev) => [...prev, e.data]);
    es.onerror = () => es.close();
    return () => es.close();
  }, [runId]);

  if (events.length === 0) return null;

  return (
    <div className="hive-card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 4 }}>
      <SectionLabel>Live trace</SectionLabel>
      {events.map((e, i) => (
        <p key={i} style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-2)", margin: 0 }}>
          {e}
        </p>
      ))}
    </div>
  );
}

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: run, isLoading } = useQuery({
    queryKey: ["run", id],
    queryFn: () => api.runs.get(id),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "running" || s === "pending" ? 2000 : false;
    },
  });

  if (isLoading) {
    return <div style={{ padding: 40 }}><p style={{ fontSize: 13, color: "var(--c-text-3)" }}>Loading…</p></div>;
  }

  if (!run) {
    return <div style={{ padding: 40 }}><p style={{ fontSize: 13, color: "var(--c-err)" }}>Run not found.</p></div>;
  }

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "40px 40px", display: "flex", flexDirection: "column", gap: 32 }}>
      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-3)" }}>
        <Link href="/runs" style={{ color: "var(--c-text-3)", textDecoration: "none" }}>Runs</Link>
        <span>/</span>
        <span style={{ color: "var(--c-text-2)" }}>{run.id.slice(0, 8)}</span>
      </div>

      {/* Title */}
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <h1 style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 600, color: "var(--c-text-1)", margin: 0 }}>
          {run.id.slice(0, 8)}<span style={{ color: "var(--c-text-3)" }}>…</span>
        </h1>
        <StatusPill status={run.status} large />
      </div>

      {/* Meta strip */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {[
          { label: "Started",  value: formatDate(run.started_at) },
          { label: "Finished", value: formatDate(run.finished_at) },
          { label: "Duration", value: durationMs(run.started_at, run.finished_at) },
        ].map(({ label, value }) => (
          <div key={label} className="hive-card" style={{ padding: "12px 16px" }}>
            <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: "0 0 6px 0" }}>
              {label}
            </p>
            <p style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--c-text-1)", margin: 0 }}>
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* Input */}
      {run.input && (
        <section>
          <SectionLabel>Input</SectionLabel>
          <div className="hive-card" style={{ padding: 16, overflowX: "auto" }}>
            <pre style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-2)", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", lineHeight: 1.6 }}>
              {JSON.stringify(run.input, null, 2)}
            </pre>
          </div>
        </section>
      )}

      {(run.status === "pending" || run.status === "running") && <LiveStream runId={run.id} />}

      {/* Steps */}
      <section>
        <SectionLabel>Step Timeline</SectionLabel>
        <StepTimeline steps={run.steps} />
      </section>

      {/* Tool calls */}
      <section>
        <SectionLabel>Tool Calls</SectionLabel>
        <ToolCallList run={run} />
      </section>

      {/* Output */}
      {run.output && (
        <section>
          <SectionLabel>Output</SectionLabel>
          <div className="hive-card" style={{ padding: 16, overflowX: "auto", borderColor: "var(--c-ok-muted)" }}>
            <pre style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--c-ok)", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", lineHeight: 1.6 }}>
              {typeof run.output === "object" && "text" in run.output
                ? String(run.output.text)
                : JSON.stringify(run.output, null, 2)}
            </pre>
          </div>
        </section>
      )}

      {/* Error */}
      {run.error && (
        <section>
          <SectionLabel>Error</SectionLabel>
          <div className="hive-card" style={{ padding: 16, borderColor: "var(--c-err-muted)" }}>
            <pre style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-err)", margin: 0, whiteSpace: "pre-wrap" }}>
              {run.error}
            </pre>
          </div>
        </section>
      )}
    </div>
  );
}
