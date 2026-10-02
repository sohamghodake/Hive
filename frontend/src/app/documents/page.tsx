"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, type Document } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/Toast";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function UploadIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden>
      <path d="M6.5 1V8.5M4 3.5L6.5 1L9 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M1 11H12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function FileIcon({ type }: { type: string }) {
  const isCode = type.includes("javascript") || type.includes("python") || type.includes("json") || type.includes("xml");
  const isPdf  = type.includes("pdf");
  return (
    <svg width="14" height="16" viewBox="0 0 14 16" fill="none" style={{ flexShrink: 0 }}>
      <path d="M2 1h7l3 3v11H2V1z" stroke={isPdf ? "var(--c-err)" : isCode ? "var(--c-live)" : "var(--c-text-3)"} strokeWidth="1.2" fill="none"/>
      <path d="M9 1v3h3" stroke={isPdf ? "var(--c-err)" : isCode ? "var(--c-live)" : "var(--c-text-3)"} strokeWidth="1.2"/>
      <path d="M4 7h6M4 9.5h6M4 12h4" stroke="var(--c-border)" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function PreviewModal({ doc, onClose }: { doc: Document; onClose: () => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["doc-content", doc.id],
    queryFn: () => api.documents.getContent(doc.id),
  });

  return (
    <Modal open onClose={onClose} title={doc.name} width={680}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", gap: 12 }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, padding: "2px 8px", borderRadius: 4, color: "var(--c-live)", background: "var(--c-live-muted)" }}>
            {doc.content_type}
          </span>
          {doc.size_bytes != null && (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", alignSelf: "center" }}>
              {(doc.size_bytes / 1024).toFixed(1)} KB
            </span>
          )}
        </div>
        <div
          style={{
            background: "var(--c-raised)",
            border: "1px solid var(--c-border)",
            borderRadius: 8,
            padding: 16,
            maxHeight: 480,
            overflowY: "auto",
          }}
        >
          {isLoading && <p style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-3)", margin: 0 }}>Loading…</p>}
          {isError  && <p style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-err)", margin: 0 }}>Failed to load content.</p>}
          {data && (
            <pre style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-2)", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", lineHeight: 1.7 }}>
              {data.content}
            </pre>
          )}
        </div>
      </div>
    </Modal>
  );
}

function DeleteConfirm({ doc, onCancel, onConfirm, isPending }: {
  doc: Document; onCancel: () => void; onConfirm: () => void; isPending: boolean;
}) {
  return (
    <Modal open onClose={onCancel} title="Delete Document">
      <p style={{ fontSize: 13, color: "var(--c-text-2)", marginBottom: 20 }}>
        Delete <strong style={{ color: "var(--c-text-1)", fontFamily: "var(--font-mono)" }}>{doc.name}</strong>? This cannot be undone.
      </p>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <button className="hive-btn hive-btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="hive-btn hive-btn-danger" disabled={isPending} onClick={onConfirm}>
          {isPending ? "Deleting…" : "Delete"}
        </button>
      </div>
    </Modal>
  );
}

const COL = "1fr 150px 80px 120px 100px";

export default function DocumentsPage() {
  const qc = useQueryClient();
  const { show } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);

  const [preview, setPreview]   = useState<Document | null>(null);
  const [delTarget, setDelTarget] = useState<Document | null>(null);

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: api.documents.list,
    // Indexing runs after upload returns; poll until every document is searchable.
    refetchInterval: (q) => (q.state.data?.some((d) => !d.embedded) ? 2000 : false),
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${BASE}/api/documents`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    onSuccess: (doc) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      show(`Uploaded "${doc.name}"`, "success");
      if (fileRef.current) fileRef.current.value = "";
    },
    onError: (e) => show(String(e), "error"),
  });

  const deleteDoc = useMutation({
    mutationFn: (id: string) => api.documents.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      show("Document deleted", "success");
      setDelTarget(null);
    },
    onError: (e) => show(String(e), "error"),
  });

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "40px 40px" }}>
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
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {upload.isPending && (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-live)" }}>Uploading…</span>
          )}
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
            {docs.length} {docs.length === 1 ? "document" : "documents"}
          </span>
          <button className="hive-btn hive-btn-primary" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
            <UploadIcon /> Upload
          </button>
        </div>
        <input
          ref={fileRef}
          type="file"
          style={{ display: "none" }}
          accept=".txt,.md,.py,.js,.ts,.json,.csv,.html,.xml,.yaml,.yml,.pdf"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload.mutate(f);
          }}
        />
      </div>

      {/* Info banner */}
      <div
        className="hive-card"
        style={{ padding: "12px 16px", marginBottom: 20, display: "flex", alignItems: "center", gap: 10 }}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
          <circle cx="7" cy="7" r="6" stroke="var(--c-live)" strokeWidth="1.2"/>
          <path d="M7 6v4M7 4.5v.5" stroke="var(--c-live)" strokeWidth="1.4" strokeLinecap="round"/>
        </svg>
        <span style={{ fontSize: 12, color: "var(--c-text-3)" }}>
          Uploads are split into chunks and embedded locally (bge-small, pgvector) for{" "}
          <code style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-live)", background: "var(--c-live-muted)", padding: "1px 5px", borderRadius: 3 }}>search_documents</code>
          . PDFs are text-extracted. Grant the tool to an agent — or use{" "}
          <code style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-live)", background: "var(--c-live-muted)", padding: "1px 5px", borderRadius: 3 }}>contract-reviewer</code>
          {" "}or{" "}
          <code style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-live)", background: "var(--c-live-muted)", padding: "1px 5px", borderRadius: 3 }}>knowledge-assistant</code>.
        </span>
      </div>

      <div className="hive-card" style={{ overflow: "hidden" }}>
        {/* Table header */}
        <div style={{ display: "grid", gridTemplateColumns: COL, gap: 16, padding: "10px 20px", borderBottom: "1px solid var(--c-border)" }}>
          {["Name", "Type", "Size", "Added", ""].map((h) => (
            <span key={h} style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)" }}>
              {h}
            </span>
          ))}
        </div>

        {isLoading && (
          <p style={{ padding: "24px 20px", fontSize: 13, color: "var(--c-text-3)", margin: 0 }}>Loading…</p>
        )}

        {docs.map((doc) => (
          <div
            key={doc.id}
            className="hive-row"
            style={{ display: "grid", gridTemplateColumns: COL, gap: 16, alignItems: "center", padding: "12px 20px", borderBottom: "1px solid var(--c-divider)" }}
          >
            {/* Name */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
              <FileIcon type={doc.content_type} />
              <button
                onClick={() => setPreview(doc)}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0, textAlign: "left", minWidth: 0 }}
              >
                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--c-text-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>
                  {doc.name}
                </span>
              </button>
              <span
                title={doc.embedded ? "Chunked and embedded — searchable" : "Embedding in progress"}
                className={doc.embedded ? "" : "anim-pulse"}
                style={{
                  fontFamily: "var(--font-mono)", fontSize: 10, padding: "1px 6px", borderRadius: 4, flexShrink: 0,
                  color: doc.embedded ? "var(--c-ok)" : "var(--c-warn)",
                  background: doc.embedded ? "var(--c-ok-muted)" : "var(--c-warn-muted)",
                }}
              >
                {doc.embedded ? "indexed" : "indexing…"}
              </span>
            </div>

            {/* Type */}
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {doc.content_type}
            </span>

            {/* Size */}
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)", fontVariantNumeric: "tabular-nums" }}>
              {doc.size_bytes != null ? `${(doc.size_bytes / 1024).toFixed(1)} KB` : "—"}
            </span>

            {/* Added */}
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
              {formatDate(doc.created_at)}
            </span>

            {/* Actions */}
            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
              <button
                className="hive-btn hive-btn-ghost"
                style={{ padding: "4px 10px", fontSize: 11 }}
                onClick={() => setPreview(doc)}
              >
                Preview
              </button>
              <button
                className="hive-btn hive-btn-danger"
                style={{ padding: "4px 10px", fontSize: 11 }}
                onClick={() => setDelTarget(doc)}
              >
                Delete
              </button>
            </div>
          </div>
        ))}

        {!isLoading && docs.length === 0 && (
          <div style={{ padding: "48px 20px", textAlign: "center" }}>
            <p style={{ fontSize: 13, color: "var(--c-text-3)", margin: "0 0 16px 0" }}>
              No documents yet. Upload a text file to add it to the knowledge base.
            </p>
            <button className="hive-btn hive-btn-primary" onClick={() => fileRef.current?.click()}>
              <UploadIcon /> Upload your first document
            </button>
          </div>
        )}
      </div>

      {preview   && <PreviewModal doc={preview}   onClose={() => setPreview(null)} />}
      {delTarget && (
        <DeleteConfirm
          doc={delTarget}
          onCancel={() => setDelTarget(null)}
          onConfirm={() => deleteDoc.mutate(delTarget.id)}
          isPending={deleteDoc.isPending}
        />
      )}
    </div>
  );
}
