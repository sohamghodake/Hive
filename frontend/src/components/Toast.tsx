"use client";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type ToastType = "success" | "error" | "info";
interface Toast { id: number; message: string; type: ToastType }
interface ToastCtx { show: (message: string, type?: ToastType) => void }

const Ctx = createContext<ToastCtx>({ show: () => {} });

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const show = useCallback((message: string, type: ToastType = "success") => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  const colorMap: Record<ToastType, { text: string; bg: string; border: string }> = {
    success: { text: "var(--c-ok)",   bg: "var(--c-ok-muted)",   border: "rgba(45,212,176,0.2)" },
    error:   { text: "var(--c-err)",  bg: "var(--c-err-muted)",  border: "rgba(248,113,113,0.2)" },
    info:    { text: "var(--c-live)", bg: "var(--c-live-muted)", border: "rgba(129,140,248,0.2)" },
  };

  return (
    <Ctx.Provider value={{ show }}>
      {children}
      <div
        style={{
          position: "fixed",
          bottom: 24,
          right: 24,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          zIndex: 200,
          pointerEvents: "none",
        }}
      >
        {toasts.map((t) => {
          const c = colorMap[t.type];
          return (
            <div
              key={t.id}
              style={{
                padding: "10px 16px",
                borderRadius: 8,
                fontSize: 13,
                fontFamily: "var(--font-sans)",
                color: c.text,
                background: c.bg,
                border: `1px solid ${c.border}`,
                boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
                maxWidth: 340,
                lineHeight: 1.4,
              }}
            >
              {t.message}
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  return useContext(Ctx);
}
