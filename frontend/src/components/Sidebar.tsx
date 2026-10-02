"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ThemeToggle } from "./ThemeToggle";

/** Small heartbeat so a dead backend is obvious instead of surfacing as
    every page silently rendering empty. */
function ApiStatus() {
  const { isSuccess, isError } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15000,
    retry: false,
  });

  const color = isSuccess ? "var(--c-ok)" : isError ? "var(--c-err)" : "var(--c-text-3)";
  const label = isSuccess ? "API online" : isError ? "API offline" : "Connecting…";

  return (
    <span
      title={label}
      style={{ display: "inline-flex", alignItems: "center", gap: 5, fontFamily: "var(--font-mono)", fontSize: 10, color }}
    >
      <span
        className={isError ? "anim-pulse" : ""}
        style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0 }}
      />
      {isSuccess ? "online" : isError ? "offline" : "…"}
    </span>
  );
}

function HiveHex() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden>
      <polygon
        points="11,1.5 19.5,6.25 19.5,15.75 11,20.5 2.5,15.75 2.5,6.25"
        stroke="var(--c-accent)"
        strokeWidth="1.4"
        fill="var(--c-accent-muted)"
        strokeLinejoin="round"
      />
      <polygon
        points="11,6.5 15,8.75 15,13.25 11,15.5 7,13.25 7,8.75"
        fill="var(--c-accent)"
        opacity="0.55"
      />
    </svg>
  );
}

const navLinks = [
  {
    href: "/",
    exact: true,
    label: "Overview",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <rect x="1" y="1" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.3" />
        <rect x="8.5" y="1" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.3" />
        <rect x="1" y="8.5" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.3" />
        <rect x="8.5" y="8.5" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.3" />
      </svg>
    ),
  },
  {
    href: "/runs",
    exact: false,
    label: "Runs",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <path d="M3 2L12 7.5L3 13V2Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    href: "/agents",
    exact: false,
    label: "Agents",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <circle cx="7.5" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.3" />
        <path d="M1.5 14C1.5 11.5 4.5 9.5 7.5 9.5C10.5 9.5 13.5 11.5 13.5 14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/documents",
    exact: false,
    label: "Documents",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <path d="M3 1.5H9.5L12.5 4.5V13.5H3V1.5Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
        <path d="M9.5 1.5V4.5H12.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M5 7.5H10M5 10H8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/workspace",
    exact: false,
    label: "Workspace",
    icon: (
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
        <rect x="1.5" y="1.5" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.3" />
        <path d="M1.5 5.5H13.5" stroke="currentColor" strokeWidth="1.3" />
        <circle cx="4.5" cy="3.5" r="0.7" fill="currentColor" />
        <circle cx="7" cy="3.5" r="0.7" fill="currentColor" />
        <path d="M4 8.5L6 10.5L4 12.5M7.5 12.5H11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      style={{
        width: 210,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--c-surface)",
        borderRight: "1px solid var(--c-border)",
      }}
    >
      {/* Wordmark */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 20px",
          height: 56,
          borderBottom: "1px solid var(--c-border)",
          flexShrink: 0,
        }}
      >
        <HiveHex />
        <span
          style={{
            fontFamily: "var(--font-display)",
            fontSize: 15,
            fontWeight: 700,
            letterSpacing: "-0.02em",
            color: "var(--c-text-1)",
          }}
        >
          Hive
        </span>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "16px 12px", display: "flex", flexDirection: "column", gap: 2 }}>
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            textTransform: "uppercase",
            letterSpacing: "0.09em",
            color: "var(--c-text-3)",
            padding: "0 12px",
            marginBottom: 8,
          }}
        >
          Platform
        </p>
        {navLinks.map((link) => {
          const active = link.exact
            ? pathname === link.href
            : pathname.startsWith(link.href);

          return (
            <Link
              key={link.href}
              href={link.href}
              className="hive-row"
              style={{
                position: "relative",
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 12px",
                borderRadius: 8,
                fontSize: 13,
                fontFamily: "var(--font-sans)",
                fontWeight: active ? 500 : 400,
                color: active ? "var(--c-accent)" : "var(--c-text-2)",
                background: active ? "var(--c-accent-muted)" : "transparent",
                textDecoration: "none",
              }}
            >
              {active && (
                <span
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 8,
                    bottom: 8,
                    width: 2,
                    borderRadius: 99,
                    background: "var(--c-accent)",
                  }}
                />
              )}
              <span style={{ color: active ? "var(--c-accent)" : "var(--c-text-3)", display: "flex" }}>
                {link.icon}
              </span>
              {link.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div
        style={{
          padding: "12px",
          borderTop: "1px solid var(--c-border)",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        <ThemeToggle />
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 4px" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--c-text-3)" }}>
            v0.2.0
          </span>
          <ApiStatus />
        </div>
      </div>
    </aside>
  );
}
