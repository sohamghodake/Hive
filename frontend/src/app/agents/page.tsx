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
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "40px 40px" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: "0 0 4px 0" }}>
            Platform
          </p>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 600, color: "var(--c-text-1)", margin: 0 }}>
            Agents
          </h1>
        </div>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", fontVariantNumeric: "tabular-nums" }}>
          {agents.length} registered
        </span>
      </div>

      {isLoading && <p style={{ fontSize: 13, color: "var(--c-text-3)" }}>Loading…</p>}

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {agents.map((agent) => (
          <div key={agent.id} className="hive-card" style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Header row */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
              <div>
                <h2 style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 600, color: "var(--c-text-1)", margin: "0 0 4px 0" }}>
                  {agent.name}
                </h2>
                {agent.description && (
                  <p style={{ fontSize: 13, color: "var(--c-text-2)", margin: 0 }}>
                    {agent.description}
                  </p>
                )}
              </div>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  padding: "4px 10px",
                  borderRadius: 6,
                  color: "var(--c-accent)",
                  background: "var(--c-accent-muted)",
                  border: "1px solid var(--c-accent-border)",
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }}
              >
                {agent.model}
              </span>
            </div>

            {/* System prompt */}
            {agent.system_prompt && (
              <p
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--c-text-3)",
                  background: "var(--c-raised)",
                  borderLeft: "2px solid var(--c-border)",
                  padding: "8px 12px",
                  borderRadius: "0 6px 6px 0",
                  lineHeight: 1.6,
                  margin: 0,
                }}
              >
                {agent.system_prompt.slice(0, 150)}
                {agent.system_prompt.length > 150 ? "…" : ""}
              </p>
            )}

            {/* Tools + meta */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {agent.tools.map((t) => (
                  <span
                    key={t}
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 4,
                      color: "var(--c-live)",
                      background: "var(--c-live-muted)",
                    }}
                  >
                    {t}
                  </span>
                ))}
                {agent.tools.length === 0 && (
                  <span style={{ fontSize: 11, color: "var(--c-text-3)" }}>No tools</span>
                )}
              </div>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", flexShrink: 0 }}>
                {formatDate(agent.created_at)}
              </span>
            </div>
          </div>
        ))}

        {!isLoading && agents.length === 0 && (
          <div className="hive-card" style={{ padding: "40px 24px", textAlign: "center" }}>
            <p style={{ fontSize: 13, color: "var(--c-text-3)" }}>
              No agents yet. POST to /api/agents to create one.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
