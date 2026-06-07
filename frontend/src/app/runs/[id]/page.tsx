"use client";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, type RunDetail } from "@/lib/api";
import { statusColor, formatDate } from "@/lib/utils";
import { useParams } from "next/navigation";

function StepTimeline({ run }: { run: RunDetail }) {
  return (
    <div className="space-y-2">
      {run.steps.map((step) => (
        <div key={step.id} className="flex items-center gap-4 bg-neutral-800 rounded-lg px-4 py-3">
          <span className="text-neutral-500 text-xs w-6 text-right">{step.sequence}</span>
          <span className="font-mono text-sm">{step.node}</span>
          <span className={`ml-auto text-xs font-medium capitalize ${statusColor(step.status)}`}>
            {step.status}
          </span>
          <span className="text-xs text-neutral-500">{formatDate(step.started_at)}</span>
        </div>
      ))}
      {run.steps.length === 0 && (
        <p className="text-sm text-neutral-500">No steps recorded yet.</p>
      )}
    </div>
  );
}

function ToolCallList({ run }: { run: RunDetail }) {
  return (
    <div className="space-y-2">
      {run.tool_calls.map((tc) => (
        <details key={tc.id} className="bg-neutral-800 rounded-lg px-4 py-3 group">
          <summary className="flex items-center gap-3 cursor-pointer list-none">
            <span className="font-mono text-sm text-blue-400">{tc.tool_name}</span>
            {tc.mcp_server && (
              <span className="text-xs text-neutral-500 bg-neutral-700 px-2 py-0.5 rounded">
                {tc.mcp_server}
              </span>
            )}
            {tc.duration_ms != null && (
              <span className="ml-auto text-xs text-neutral-500">{tc.duration_ms}ms</span>
            )}
            {tc.error && <span className="text-red-500 text-xs">error</span>}
          </summary>
          <div className="mt-3 space-y-2 text-xs font-mono">
            <div>
              <span className="text-neutral-500">input: </span>
              <pre className="text-neutral-300 whitespace-pre-wrap break-all">
                {JSON.stringify(tc.input, null, 2)}
              </pre>
            </div>
            {tc.output && (
              <div>
                <span className="text-neutral-500">output: </span>
                <pre className="text-green-400 whitespace-pre-wrap break-all">
                  {JSON.stringify(tc.output, null, 2)}
                </pre>
              </div>
            )}
            {tc.error && (
              <div>
                <span className="text-neutral-500">error: </span>
                <pre className="text-red-400">{tc.error}</pre>
              </div>
            )}
          </div>
        </details>
      ))}
      {run.tool_calls.length === 0 && (
        <p className="text-sm text-neutral-500">No tool calls recorded.</p>
      )}
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
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 space-y-1 font-mono text-xs">
      <p className="text-neutral-500 mb-2">Live trace</p>
      {events.map((e, i) => (
        <p key={i} className="text-neutral-300">{e}</p>
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
      const status = query.state.data?.status;
      return status === "running" || status === "pending" ? 2000 : false;
    },
  });

  if (isLoading) return <p className="text-neutral-500 text-sm">Loading…</p>;
  if (!run) return <p className="text-red-400 text-sm">Run not found.</p>;

  return (
    <div className="space-y-8 max-w-4xl">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold font-mono">{run.id.slice(0, 8)}…</h1>
        <span className={`text-base font-medium capitalize ${statusColor(run.status)}`}>
          {run.status}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-4 text-sm">
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <p className="text-neutral-500 text-xs mb-1">Started</p>
          <p>{formatDate(run.started_at)}</p>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <p className="text-neutral-500 text-xs mb-1">Finished</p>
          <p>{formatDate(run.finished_at)}</p>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4">
          <p className="text-neutral-500 text-xs mb-1">Steps</p>
          <p>{run.steps.length}</p>
        </div>
      </div>

      {(run.status === "pending" || run.status === "running") && <LiveStream runId={run.id} />}

      <section>
        <h2 className="text-lg font-semibold mb-3">Step Timeline</h2>
        <StepTimeline run={run} />
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-3">Tool Calls</h2>
        <ToolCallList run={run} />
      </section>

      {run.output && (
        <section>
          <h2 className="text-lg font-semibold mb-3">Output</h2>
          <pre className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 text-sm font-mono text-neutral-300 whitespace-pre-wrap break-all">
            {JSON.stringify(run.output, null, 2)}
          </pre>
        </section>
      )}

      {run.error && (
        <section>
          <h2 className="text-lg font-semibold mb-3 text-red-400">Error</h2>
          <pre className="bg-neutral-900 border border-red-900/50 rounded-xl p-4 text-sm font-mono text-red-400 whitespace-pre-wrap">
            {run.error}
          </pre>
        </section>
      )}
    </div>
  );
}
