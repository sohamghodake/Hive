import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return formatDate(iso);
}

export function durationMs(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    pending:   "var(--c-warn)",
    running:   "var(--c-live)",
    completed: "var(--c-ok)",
    failed:    "var(--c-err)",
  };
  return map[status] ?? "var(--c-text-3)";
}

export function statusMuted(status: string): string {
  const map: Record<string, string> = {
    pending:   "var(--c-warn-muted)",
    running:   "var(--c-live-muted)",
    completed: "var(--c-ok-muted)",
    failed:    "var(--c-err-muted)",
  };
  return map[status] ?? "transparent";
}
