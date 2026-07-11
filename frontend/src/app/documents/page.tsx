"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function UploadIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden>
      <path d="M6.5 1V8.5M4 3.5L6.5 1L9 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M1 11H12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

const COL = "1fr 140px 80px 120px";

export default function DocumentsPage() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: api.documents.list,
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${BASE}/api/documents`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "40px 40px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)", margin: "0 0 4px 0" }}>
            Platform
          </p>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 600, color: "var(--c-text-1)", margin: 0 }}>
            Documents
          </h1>
        </div>
        <button
          onClick={() => fileRef.current?.click()}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 14px",
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 500,
            cursor: "pointer",
            color: "var(--c-accent)",
            background: "var(--c-accent-muted)",
            border: "1px solid var(--c-accent-border)",
            fontFamily: "var(--font-sans)",
          }}
        >
          <UploadIcon />
          Upload
        </button>
        <input
          ref={fileRef}
          type="file"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload.mutate(f);
          }}
        />
      </div>

      {upload.isPending && (
        <p style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--c-live)", marginBottom: 16 }}>
          Uploading…
        </p>
      )}
      {upload.isError && (
        <p style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--c-err)", marginBottom: 16 }}>
          {String(upload.error)}
        </p>
      )}

      <div className="hive-card" style={{ overflow: "hidden" }}>
        {/* Header */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: COL,
            gap: 16,
            padding: "10px 20px",
            borderBottom: "1px solid var(--c-border)",
          }}
        >
          {["Name", "Type", "Size", "Added"].map((h) => (
            <span
              key={h}
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                textTransform: "uppercase",
                letterSpacing: "0.09em",
                color: "var(--c-text-3)",
              }}
            >
              {h}
            </span>
          ))}
        </div>

        {docs.map((doc) => (
          <div
            key={doc.id}
            className="hive-row"
            style={{
              display: "grid",
              gridTemplateColumns: COL,
              gap: 16,
              alignItems: "center",
              padding: "13px 20px",
              borderBottom: "1px solid var(--c-divider)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
              <p style={{ fontSize: 13, fontWeight: 500, color: "var(--c-text-1)", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {doc.name}
              </p>
              {doc.embedded && (
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    padding: "1px 6px",
                    borderRadius: 4,
                    color: "var(--c-ok)",
                    background: "var(--c-ok-muted)",
                    flexShrink: 0,
                  }}
                >
                  embedded
                </span>
              )}
            </div>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {doc.content_type}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", fontVariantNumeric: "tabular-nums" }}>
              {doc.size_bytes != null ? `${(doc.size_bytes / 1024).toFixed(1)} KB` : "—"}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
              {formatDate(doc.created_at)}
            </span>
          </div>
        ))}

        {!isLoading && docs.length === 0 && (
          <p style={{ padding: "40px 20px", textAlign: "center", fontSize: 13, color: "var(--c-text-3)" }}>
            No documents yet. Upload a file to get started.
          </p>
        )}
      </div>
    </div>
  );
}
