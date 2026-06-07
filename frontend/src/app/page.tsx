"use client";
import { useQuery } from "@tanstack/react-query";
import { api, type Run } from "@/lib/api";
import { statusColor, formatDate } from "@/lib/utils";
import Link from "next/link";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5">
      <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

export default function OverviewPage() {
  const { data: runs = [] } = useQuery({ queryKey: ["runs"], queryFn: api.runs.list });
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: api.agents.list });

  const active = runs.filter((r) => r.status === "running").length;
  const completed = runs.filter((r) => r.status === "completed").length;
  const failed = runs.filter((r) => r.status === "failed").length;

  return (
    <div className="space-y-8 max-w-5xl">
      <h1 className="text-2xl font-bold">Overview</h1>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Total Runs" value={runs.length} />
        <StatCard label="Active" value={active} />
        <StatCard label="Completed" value={completed} />
        <StatCard label="Agents" value={agents.length} />
      </div>

      <section>
        <h2 className="text-lg font-semibold mb-3">Recent Runs</h2>
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
          {runs.slice(0, 8).map((run) => (
            <Link
              key={run.id}
              href={`/runs/${run.id}`}
              className="flex items-center justify-between px-5 py-3 hover:bg-neutral-800/50 transition-colors"
            >
              <span className="font-mono text-sm text-neutral-400">{run.id.slice(0, 8)}</span>
              <span className={`text-sm font-medium capitalize ${statusColor(run.status)}`}>
                {run.status}
              </span>
              <span className="text-xs text-neutral-500">{formatDate(run.created_at)}</span>
            </Link>
          ))}
          {runs.length === 0 && (
            <p className="px-5 py-4 text-sm text-neutral-500">No runs yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}
