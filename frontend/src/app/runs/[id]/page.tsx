"use client";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type RunDetail, type Step } from "@/lib/api";
import { statusColor, statusMuted, formatDate, durationMs } from "@/lib/utils";
import { Skeleton, StatusPill } from "@/components/ui";
import { useToast } from "@/components/Toast";

function SectionLabel({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
      <p className="hive-eyebrow">{children}</p>
      {right}
    </div>
  );
}

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const { show } = useToast();
  const [done, setDone] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1600);
    } catch {
      show("Clipboard unavailable in this browser", "error");
    }
  }

  return (
    <button
      className="hive-btn hive-btn-ghost"
      style={{ padding: "4px 10px", fontSize: 11 }}
      onClick={copy}
    >
      {done ? "Copied" : label}
    </button>
  );
}

function outputText(output: Record<string, unknown> | null): string {
  if (!output) return "";
  if (typeof output === "object" && "text" in output) return String(output.text);
  return JSON.stringify(output, null, 2);
}

function StepTimeline({ steps }: { steps: Step[] }) {
  if (steps.length === 0) {
    return <p style={{ fontSize: 13, color: "var(--c-text-3)", margin: 0 }}>No steps recorded.</p>;
  }

  return (
    <div>
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1;
        return (
          <div key={step.id} style={{ display: "flex", gap: 14 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 26, flexShrink: 0 }}>
              <div
                style={{
                  width: 26,
                  height: 26,
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
              {!isLast && <div style={{ width: 1, flex: 1, margin: "4px 0", minHeight: 18, background: "var(--c-border)" }} />}
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                height: 26,
                marginBottom: isLast ? 0 : 14,
                flexWrap: "wrap",
              }}
            >
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 500, color: "var(--c-text-1)" }}>
                {step.node}
              </span>
              {step.input && typeof step.input === "object" && "tool" in step.input && (
                <span className="hive-tag">{String(step.input.tool)}</span>
              )}
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
    return <p style={{ fontSize: 13, color: "var(--c-text-3)", margin: 0 }}>No tool calls recorded.</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {run.tool_calls.map((tc) => (
        <details
          key={tc.id}
          style={{
            background: "var(--c-surface)",
            border: "1px solid var(--c-border)",
            borderRadius: 10,
            overflow: "hidden",
          }}
        >
          <summary
            className="hive-row"
            style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 14px", cursor: "pointer", listStyle: "none" }}
          >
            <span
              style={{ color: tc.error ? "var(--c-err)" : "var(--c-ok)", display: "flex", flexShrink: 0 }}
              aria-hidden
            >
              {tc.error ? (
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="5.6" stroke="currentColor" strokeWidth="1.3" />
                  <path d="M5 5l4 4M9 5l-4 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                </svg>
              ) : (
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="5.6" stroke="currentColor" strokeWidth="1.3" />
                  <path d="M4.6 7.2l1.7 1.7 3.1-3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 500, color: "var(--c-live)" }}>
              {tc.tool_name}
            </span>
            {tc.error && <span style={{ fontSize: 11, color: "var(--c-err)" }}>failed</span>}
            {tc.duration_ms != null && (
              <span
                style={{
                  marginLeft: "auto",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--c-text-3)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {tc.duration_ms}ms
              </span>
            )}
          </summary>

          <div
            style={{
              padding: "12px 14px",
              borderTop: "1px solid var(--c-border)",
              display: "flex",
              flexDirection: "column",
              gap: 12,
              background: "var(--c-raised)",
            }}
          >
            <div>
              <p className="hive-eyebrow" style={{ marginBottom: 6 }}>Input</p>
              <pre
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--c-text-2)",
                  margin: 0,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  lineHeight: 1.6,
                }}
              >
                {JSON.stringify(tc.input, null, 2)}
              </pre>
            </div>
            {tc.output != null && (
              <div>
                <p className="hive-eyebrow" style={{ marginBottom: 6 }}>Output</p>
                <pre
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--c-text-2)",
                    margin: 0,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    lineHeight: 1.6,
                    maxHeight: 260,
                    overflowY: "auto",
                  }}
                >
                  {typeof tc.output === "object" && tc.output && "result" in tc.output
                    ? String((tc.output as { result: unknown }).result)
                    : JSON.stringify(tc.output, null, 2)}
                </pre>
              </div>
            )}
            {tc.error && (
              <div>
                <p className="hive-eyebrow" style={{ marginBottom: 6 }}>Error</p>
                <pre
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--c-err)",
                    margin: 0,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
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

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function LiveStream({ runId }: { runId: string }) {
  const [events, setEvents] = useState<string[]>([]);
  const ref = useRef<EventSource | null>(null);

  useEffect(() => {
    // Absolute URL on purpose: a relative path would hit the Next server's own
    // rewrite, which cannot reach the API from inside the browser sandbox.
    const es = new EventSource(`${API_BASE}/api/runs/${runId}/stream`);
    ref.current = es;
    es.onmessage = (e) => setEvents((prev) => [...prev, e.data]);
    es.onerror = () => es.close();
    return () => es.close();
  }, [runId]);

  return (
    <div className="hive-card" style={{ padding: 16, borderColor: "var(--c-live-muted)" }}>
      <SectionLabel>Live trace</SectionLabel>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {events.length === 0 && (
          <p style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-3)", margin: 0 }}>
            Waiting for the agent to emit its first step…
          </p>
        )}
        {events.map((raw, i) => {
          let line = raw;
          try {
            const ev = JSON.parse(raw);
            if (ev.type === "step") {
              const d = ev.data;
              line = `#${d.sequence}  ${d.node}${d.tool ? ` · ${d.tool}` : ""}  ${d.status}`;
            } else if (ev.type === "done") {
              line = `run ${ev.status}`;
            }
          } catch {
            /* show unparseable events verbatim */
          }
          return (
            <p
              key={i}
              className="anim-in"
              style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-2)", margin: 0, wordBreak: "break-word" }}
            >
              {line}
            </p>
          );
        })}
      </div>
    </div>
  );
}

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });
  const agentMap = Object.fromEntries(agents.map((a) => [a.id, a.name]));

  const { data: run, isLoading, isError, error } = useQuery({
    queryKey: ["run", id],
    queryFn: () => api.runs.get(id),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "running" || s === "pending" ? 2000 : false;
    },
  });

  if (isLoading) {
    return (
      <div style={{ maxWidth: 820, margin: "0 auto", padding: 40, display: "flex", flexDirection: "column", gap: 20 }}>
        <Skeleton width={160} height={12} />
        <Skeleton width={280} height={28} />
        <Skeleton height={90} />
        <Skeleton height={140} />
      </div>
    );
  }

  if (isError || !run) {
    return (
      <div style={{ maxWidth: 820, margin: "0 auto", padding: 40 }}>
        <Link href="/runs" style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-accent)", textDecoration: "none" }}>
          ← Back to runs
        </Link>
        <p style={{ fontSize: 14, color: "var(--c-err)", marginTop: 20 }}>
          {isError ? String(error).slice(0, 200) : "Run not found."}
        </p>
      </div>
    );
  }

  const inFlight = run.status === "pending" || run.status === "running";
  // When the trailing ```json block parsed into output.data, it gets its own card
  // below, so drop it from the prose instead of showing it twice.
  const hasData = !!run.output && "data" in run.output && run.output.data != null;
  const fullText = outputText(run.output);
  const result = hasData ? fullText.replace(/```json[\s\S]*?```\s*$/i, "").trim() || fullText : fullText;
  const isProse = !!run.output && typeof run.output === "object" && "text" in run.output;

  return (
    <div style={{ maxWidth: 820, margin: "0 auto", padding: "40px 40px 64px", display: "flex", flexDirection: "column", gap: 28 }}>
      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-3)" }}>
        <Link href="/runs" style={{ color: "var(--c-text-2)", textDecoration: "none" }}>Runs</Link>
        <span>/</span>
        <span style={{ color: "var(--c-text-1)" }}>{run.id.slice(0, 8)}</span>
      </div>

      {/* Title */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 className="hive-h1" style={{ fontFamily: "var(--font-mono)", fontSize: 20 }}>
          {run.id.slice(0, 8)}
        </h1>
        <StatusPill status={run.status} />
        {run.agent_id && agentMap[run.agent_id] && (
          <Link
            href="/agents"
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              padding: "3px 10px",
              borderRadius: 6,
              color: "var(--c-accent)",
              background: "var(--c-accent-muted)",
              border: "1px solid var(--c-accent-border)",
              textDecoration: "none",
            }}
          >
            {agentMap[run.agent_id]}
          </Link>
        )}
      </div>

      {/* Task */}
      <section>
        <SectionLabel>Task</SectionLabel>
        <div className="hive-card" style={{ padding: "14px 16px" }}>
          <p style={{ fontSize: 14, color: "var(--c-text-1)", margin: 0, lineHeight: 1.65 }}>
            {run.input && (run.input.task ?? run.input.message)
              ? String(run.input.task ?? run.input.message)
              : JSON.stringify(run.input)}
          </p>
        </div>
      </section>

      {/* Result first — it is what the user actually came for. */}
      {run.error && (
        <section>
          <SectionLabel>
            Error
          </SectionLabel>
          <div className="hive-card" style={{ padding: 16, borderColor: "var(--c-err)", background: "var(--c-err-muted)" }}>
            <pre
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--c-err)",
                margin: 0,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                lineHeight: 1.6,
              }}
            >
              {run.error}
            </pre>
          </div>
        </section>
      )}

      {result && (
        <section>
          <SectionLabel right={<CopyButton text={result} />}>Result</SectionLabel>
          <div className="hive-card" style={{ padding: "18px 20px", borderColor: "var(--c-ok-muted)" }}>
            <div
              style={{
                fontFamily: isProse ? "var(--font-sans)" : "var(--font-mono)",
                fontSize: isProse ? 14.5 : 12,
                color: "var(--c-text-1)",
                margin: 0,
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                lineHeight: 1.75,
              }}
            >
              {result}
            </div>
          </div>
        </section>
      )}

      {run.output && "data" in run.output && run.output.data != null && (
        <section>
          <SectionLabel right={<CopyButton text={JSON.stringify(run.output.data, null, 2)} label="Copy JSON" />}>
            Structured result
          </SectionLabel>
          <div className="hive-card" style={{ padding: 16, overflowX: "auto" }}>
            <pre style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-2)", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", lineHeight: 1.6 }}>
              {JSON.stringify(run.output.data, null, 2)}
            </pre>
          </div>
          <p className="hive-hint" style={{ marginTop: 8 }}>
            Stored as JSONB in <code>runs.output-&gt;'data'</code>, queryable in SQL.
          </p>
        </section>
      )}

      {run.output && "truncated" in run.output && (
        <p className="hive-hint" style={{ color: "var(--c-warn)", margin: 0 }}>
          The model ran out of output tokens mid-answer, so the result above is cut off.
        </p>
      )}

      {run.output && "stopped_early" in run.output && (
        <p className="hive-hint" style={{ color: "var(--c-warn)", margin: 0 }}>
          This run hit its step budget before finishing, so the result may be partial.
        </p>
      )}

      {inFlight && <LiveStream runId={run.id} />}

      {/* Meta */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
        {[
          { label: "Started", value: formatDate(run.started_at) },
          { label: "Finished", value: formatDate(run.finished_at) },
          { label: "Duration", value: durationMs(run.started_at, run.finished_at) },
          { label: "Tool calls", value: String(run.tool_calls.length) },
        ].map(({ label, value }) => (
          <div key={label} className="hive-card" style={{ padding: "12px 14px" }}>
            <p className="hive-eyebrow" style={{ marginBottom: 6 }}>{label}</p>
            <p style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--c-text-1)", margin: 0 }}>
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* Trace */}
      <section>
        <SectionLabel>Step timeline</SectionLabel>
        <div className="hive-card" style={{ padding: 18 }}>
          <StepTimeline steps={run.steps} />
        </div>
      </section>

      <section>
        <SectionLabel>Tool calls</SectionLabel>
        <ToolCallList run={run} />
      </section>
    </div>
  );
}
