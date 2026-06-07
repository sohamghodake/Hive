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

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    pending: "text-yellow-500",
    running: "text-blue-500",
    completed: "text-green-500",
    failed: "text-red-500",
  };
  return map[status] ?? "text-gray-400";
}
