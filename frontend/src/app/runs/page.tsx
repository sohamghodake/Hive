"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { statusColor, formatDate } from "@/lib/utils";
import Link from "next/link";

export default function RunsPage() {
  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: api.runs.list,
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="text-2xl font-bold">Runs</h1>
      {isLoading && <p className="text-neutral-500 text-sm">Loading…</p>}
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
        <div className="grid grid-cols-5 gap-4 px-5 py-2 text-xs text-neutral-500 uppercase tracking-wider">
          <span>ID</span>
          <span>Status</span>
          <span>Agent</span>
          <span>Started</span>
          <span>Finished</span>
        </div>
        {runs.map((run) => (
          <Link
            key={run.id}
            href={`/runs/${run.id}`}
            className="grid grid-cols-5 gap-4 items-center px-5 py-3 hover:bg-neutral-800/50 transition-colors"
          >
            <span className="font-mono text-sm">{run.id.slice(0, 8)}…</span>
            <span className={`text-sm font-medium capitalize ${statusColor(run.status)}`}>
              {run.status}
            </span>
            <span className="text-sm text-neutral-400">{run.agent_id?.slice(0, 8) ?? "—"}</span>
            <span className="text-xs text-neutral-500">{formatDate(run.started_at)}</span>
            <span className="text-xs text-neutral-500">{formatDate(run.finished_at)}</span>
          </Link>
        ))}
        {!isLoading && runs.length === 0 && (
          <p className="px-5 py-4 text-sm text-neutral-500">No runs yet.</p>
        )}
      </div>
    </div>
  );
}
