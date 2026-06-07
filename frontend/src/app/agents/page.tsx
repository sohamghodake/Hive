"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function AgentsPage() {
  const { data: agents = [], isLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: api.agents.list,
  });

  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-2xl font-bold">Agents</h1>
      {isLoading && <p className="text-neutral-500 text-sm">Loading…</p>}
      <div className="grid grid-cols-1 gap-4">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-2"
          >
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-lg">{agent.name}</h2>
              <span className="text-xs text-neutral-500 bg-neutral-800 px-2 py-1 rounded font-mono">
                {agent.model}
              </span>
            </div>
            {agent.description && (
              <p className="text-sm text-neutral-400">{agent.description}</p>
            )}
            <div className="flex gap-2 flex-wrap mt-2">
              {agent.tools.map((t) => (
                <span key={t} className="text-xs bg-blue-900/40 text-blue-300 px-2 py-0.5 rounded">
                  {t}
                </span>
              ))}
            </div>
            <p className="text-xs text-neutral-600 mt-2">Created {formatDate(agent.created_at)}</p>
          </div>
        ))}
        {!isLoading && agents.length === 0 && (
          <p className="text-sm text-neutral-500">No agents defined yet.</p>
        )}
      </div>
    </div>
  );
}
