"use client";
import { statusColor, statusMuted } from "@/lib/utils";

/** Consistent page heading used by every route. */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: 20,
        marginBottom: 28,
        flexWrap: "wrap",
      }}
    >
      <div style={{ minWidth: 0 }}>
        {eyebrow && <p className="hive-eyebrow" style={{ marginBottom: 5 }}>{eyebrow}</p>}
        <h1 className="hive-h1">{title}</h1>
        {subtitle && (
          <p style={{ fontSize: 13, color: "var(--c-text-2)", margin: "6px 0 0 0", lineHeight: 1.5 }}>
            {subtitle}
          </p>
        )}
      </div>
      {actions && <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>{actions}</div>}
    </header>
  );
}

export function StatusPill({ status }: { status: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 9px",
        borderRadius: 6,
        fontSize: 11,
        fontWeight: 500,
        textTransform: "capitalize",
        color: statusColor(status),
        background: statusMuted(status),
        whiteSpace: "nowrap",
      }}
    >
      <span
        className={status === "running" || status === "pending" ? "anim-pulse" : ""}
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

export function Skeleton({ width = "100%", height = 14 }: { width?: number | string; height?: number }) {
  return <div className="hive-skeleton" style={{ width, height }} />;
}

/** Placeholder rows that match the real list's rhythm, so the layout does not
    jump when data lands. */
export function SkeletonRows({ rows = 4, height = 44 }: { rows?: number; height?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 16 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height={height} />
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "56px 24px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 48,
          height: 48,
          borderRadius: 12,
          background: "var(--c-raised)",
          border: "1px solid var(--c-border)",
          color: "var(--c-text-3)",
          marginBottom: 16,
        }}
      >
        {icon}
      </div>
      <p style={{ fontSize: 15, fontWeight: 600, color: "var(--c-text-1)", margin: "0 0 6px 0" }}>
        {title}
      </p>
      <p style={{ fontSize: 13, color: "var(--c-text-2)", margin: 0, maxWidth: 380, lineHeight: 1.6 }}>
        {description}
      </p>
      {action && <div style={{ marginTop: 20 }}>{action}</div>}
    </div>
  );
}

/** Inline error surface for failed queries — previously these failed silently. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div
      className="hive-card"
      style={{
        padding: "20px 24px",
        borderColor: "var(--c-err-muted)",
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
      }}
    >
      <span style={{ color: "var(--c-err)", flexShrink: 0, marginTop: 1 }}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
          <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4" />
          <path d="M8 5v3.5M8 11h.01" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: "var(--c-text-1)", margin: "0 0 4px 0" }}>
          Could not load data
        </p>
        <p
          style={{
            fontSize: 12,
            color: "var(--c-text-2)",
            margin: 0,
            fontFamily: "var(--font-mono)",
            wordBreak: "break-word",
          }}
        >
          {String(error).slice(0, 200)}
        </p>
      </div>
      {onRetry && (
        <button className="hive-btn hive-btn-ghost" style={{ padding: "5px 12px", fontSize: 12 }} onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
