"use client";
import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "hive-theme";

/** Applied before paint by the inline script in layout.tsx; kept in sync here. */
function apply(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

const OPTIONS: { value: Theme; label: string; icon: React.ReactNode }[] = [
  {
    value: "light",
    label: "Light",
    icon: (
      <svg width="13" height="13" viewBox="0 0 15 15" fill="none" aria-hidden>
        <circle cx="7.5" cy="7.5" r="3" stroke="currentColor" strokeWidth="1.3" />
        <path
          d="M7.5 1v1.5M7.5 12.5V14M14 7.5h-1.5M2.5 7.5H1M12 3l-1 1M4 11l-1 1M12 12l-1-1M4 4L3 3"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    value: "dark",
    label: "Dark",
    icon: (
      <svg width="13" height="13" viewBox="0 0 15 15" fill="none" aria-hidden>
        <path
          d="M13 9.3A5.8 5.8 0 015.7 2a5.9 5.9 0 107.3 7.3z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    value: "system",
    label: "System",
    icon: (
      <svg width="13" height="13" viewBox="0 0 15 15" fill="none" aria-hidden>
        <rect x="1.5" y="2.5" width="12" height="8" rx="1.3" stroke="currentColor" strokeWidth="1.3" />
        <path d="M5.5 13h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
    ),
  },
];

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "system";
    setTheme(stored);
    setMounted(true);
  }, []);

  function choose(next: Theme) {
    setTheme(next);
    apply(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* private mode — the choice simply will not persist */
    }
  }

  return (
    <div
      role="group"
      aria-label="Color theme"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 2,
        padding: 3,
        borderRadius: 8,
        background: "var(--c-raised)",
        border: "1px solid var(--c-border)",
      }}
    >
      {OPTIONS.map((opt) => {
        const active = mounted && theme === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => choose(opt.value)}
            title={opt.label}
            aria-label={opt.label}
            aria-pressed={active}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "5px 0",
              borderRadius: 6,
              cursor: "pointer",
              border: "none",
              background: active ? "var(--c-surface)" : "transparent",
              color: active ? "var(--c-accent)" : "var(--c-text-3)",
              transition: "background 120ms ease, color 120ms ease",
            }}
          >
            {opt.icon}
          </button>
        );
      })}
    </div>
  );
}
