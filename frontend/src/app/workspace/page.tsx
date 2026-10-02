"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type WorkspaceFile } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { Modal } from "@/components/Modal";

function ext(name: string) {
  return name.includes(".") ? name.split(".").pop()!.toLowerCase() : "";
}

function FileTypeTag({ name }: { name: string }) {
  const e = ext(name);
  const map: Record<string, [string, string]> = {
    md:   ["var(--c-ok)",   "var(--c-ok-muted)"],
    txt:  ["var(--c-text-3)", "var(--c-raised)"],
    py:   ["var(--c-live)", "var(--c-live-muted)"],
    js:   ["var(--c-warn)", "var(--c-warn-muted)"],
    ts:   ["var(--c-live)", "var(--c-live-muted)"],
    json: ["var(--c-accent)", "var(--c-accent-muted)"],
    csv:  ["var(--c-ok)",   "var(--c-ok-muted)"],
    html: ["var(--c-err)",  "var(--c-err-muted)"],
    xml:  ["var(--c-err)",  "var(--c-err-muted)"],
  };
  const [color, bg] = map[e] ?? ["var(--c-text-3)", "var(--c-raised)"];
  return (
    <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, padding: "1px 6px", borderRadius: 4, color, background: bg, flexShrink: 0 }}>
      {e || "file"}
    </span>
  );
}

function FileIcon() {
  return (
    <svg width="13" height="15" viewBox="0 0 13 15" fill="none" style={{ flexShrink: 0 }}>
      <path d="M1.5 1h7l3 3v10h-10V1z" stroke="var(--c-text-3)" strokeWidth="1.1" fill="none"/>
      <path d="M8.5 1v3h3" stroke="var(--c-text-3)" strokeWidth="1.1"/>
      <path d="M3.5 6.5h6M3.5 9h6M3.5 11.5h4" stroke="var(--c-border)" strokeWidth="1" strokeLinecap="round"/>
    </svg>
  );
}

function ViewerModal({ file, onClose }: { file: WorkspaceFile; onClose: () => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["ws-file", file.path],
    queryFn: () => api.workspace.read(file.path),
    staleTime: 0,
  });

  const isMarkdown = ext(file.name) === "md";

  return (
    <Modal open onClose={onClose} title={file.path} width={760}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <FileTypeTag name={file.name} />
          {data && (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
              {data.content.length.toLocaleString()} chars
            </span>
          )}
        </div>
        <div style={{ background: "var(--c-raised)", border: "1px solid var(--c-border)", borderRadius: 8, padding: 16, maxHeight: 520, overflowY: "auto" }}>
          {isLoading && <p style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-3)", margin: 0 }}>Loading…</p>}
          {isError   && <p style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-err)",    margin: 0 }}>Failed to load file.</p>}
          {data && (
            <pre style={{
              fontFamily: isMarkdown ? "var(--font-sans)" : "var(--font-mono)",
              fontSize: isMarkdown ? 13 : 12,
              color: "var(--c-text-2)",
              margin: 0,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              lineHeight: 1.75,
            }}>
              {data.content}
            </pre>
          )}
        </div>
        {data && (
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              className="hive-btn hive-btn-ghost"
              style={{ fontSize: 12 }}
              onClick={() => {
                const blob = new Blob([data.content], { type: "text/plain" });
                const url  = URL.createObjectURL(blob);
                const a    = document.createElement("a");
                a.href     = url;
                a.download = file.name;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              Download
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}

function DeleteConfirm({ path, onCancel, onConfirm, isPending }: {
  path: string; onCancel: () => void; onConfirm: () => void; isPending: boolean;
}) {
  return (
    <Modal open onClose={onCancel} title="Delete File">
      <p style={{ fontSize: 13, color: "var(--c-text-2)", marginBottom: 20 }}>
        Delete <strong style={{ fontFamily: "var(--font-mono)", color: "var(--c-text-1)" }}>{path}</strong> from the workspace? This cannot be undone.
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

export default function WorkspacePage() {
  const qc = useQueryClient();
  const { show } = useToast();

  const [viewing,    setViewing]    = useState<WorkspaceFile | null>(null);
  const [delTarget,  setDelTarget]  = useState<string | null>(null);
  const [dir,        setDir]        = useState("");

  const { data: files = [], isLoading, refetch } = useQuery({
    queryKey: ["workspace-files", dir],
    queryFn:  () => api.workspace.list(dir),
    refetchInterval: 10000,
  });
  // Folders first, then files, each alphabetical.
  const entries = [...files].sort((a, b) => Number(b.is_dir) - Number(a.is_dir) || a.path.localeCompare(b.path));
  const crumbs = dir ? dir.split("/") : [];

  function open(file: WorkspaceFile) {
    if (file.is_dir) setDir(file.path);
    else setViewing(file);
  }

  const deleteFile = useMutation({
    mutationFn: (path: string) => api.workspace.delete(path),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace-files"] });  // prefix-matches every folder
      show("File deleted", "success");
      setDelTarget(null);
    },
    onError: (e) => show(String(e), "error"),
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
            Workspace
          </h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-3)" }}>
            {entries.length} {entries.length === 1 ? "item" : "items"}
          </span>
          <button className="hive-btn hive-btn-ghost" onClick={() => refetch()} style={{ fontSize: 12 }}>
            Refresh
          </button>
        </div>
      </div>

      {/* Info banner */}
      <div className="hive-card" style={{ padding: "12px 16px", marginBottom: 20, display: "flex", alignItems: "center", gap: 10 }}>
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
          <circle cx="7" cy="7" r="6" stroke="var(--c-accent)" strokeWidth="1.2"/>
          <path d="M7 6v4M7 4.5v.5" stroke="var(--c-accent)" strokeWidth="1.4" strokeLinecap="round"/>
        </svg>
        <span style={{ fontSize: 12, color: "var(--c-text-3)" }}>
          Reports agents write land here — e.g.{" "}
          <code style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-accent)", background: "var(--c-accent-muted)", padding: "1px 5px", borderRadius: 3 }}>contract-reviewer</code>
          {" "}and{" "}
          <code style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-accent)", background: "var(--c-accent-muted)", padding: "1px 5px", borderRadius: 3 }}>pr-reviewer</code>
          {" "}write to <code style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>reviews/</code>.
        </span>
      </div>

      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10, fontFamily: "var(--font-mono)", fontSize: 12 }}>
        <button onClick={() => setDir("")} style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: dir ? "var(--c-accent)" : "var(--c-text-1)", fontFamily: "inherit", fontSize: "inherit" }}>
          workspace
        </button>
        {crumbs.map((c, i) => {
          const path = crumbs.slice(0, i + 1).join("/");
          const last = i === crumbs.length - 1;
          return (
            <span key={path} style={{ display: "flex", gap: 6 }}>
              <span style={{ color: "var(--c-text-3)" }}>/</span>
              <button onClick={() => setDir(path)} disabled={last} style={{ background: "none", border: "none", padding: 0, cursor: last ? "default" : "pointer", color: last ? "var(--c-text-1)" : "var(--c-accent)", fontFamily: "inherit", fontSize: "inherit" }}>
                {c}
              </button>
            </span>
          );
        })}
      </div>

      <div className="hive-card" style={{ overflow: "hidden" }}>
        {/* Header row */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 60px 120px", gap: 16, padding: "10px 20px", borderBottom: "1px solid var(--c-border)" }}>
          {["File", "Type", ""].map((h) => (
            <span key={h} style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.09em", color: "var(--c-text-3)" }}>
              {h}
            </span>
          ))}
        </div>

        {isLoading && (
          <p style={{ padding: "24px 20px", fontSize: 13, color: "var(--c-text-3)", margin: 0 }}>Loading…</p>
        )}

        {dir && (
          <button
            className="hive-row"
            onClick={() => setDir(crumbs.slice(0, -1).join("/"))}
            style={{ display: "block", width: "100%", textAlign: "left", padding: "10px 20px", border: "none", borderBottom: "1px solid var(--c-divider)", background: "transparent", cursor: "pointer", fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--c-text-2)" }}
          >
            ↑ ..
          </button>
        )}

        {entries.map((file) => (
          <div
            key={file.path}
            className="hive-row"
            style={{ display: "grid", gridTemplateColumns: "1fr 60px 120px", gap: 16, alignItems: "center", padding: "12px 20px", borderBottom: "1px solid var(--c-divider)" }}
          >
            {/* Name */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
              {file.is_dir ? <span aria-hidden style={{ fontSize: 14 }}>📁</span> : <FileIcon />}
              <button
                onClick={() => open(file)}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0, textAlign: "left", minWidth: 0 }}
              >
                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--c-text-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>
                  {file.name}{file.is_dir ? "/" : ""}
                </span>
              </button>
            </div>

            {/* Type tag */}
            {file.is_dir ? <span className="hive-tag">folder</span> : <FileTypeTag name={file.name} />}

            {/* Actions */}
            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
              <button
                className="hive-btn hive-btn-ghost"
                style={{ padding: "4px 10px", fontSize: 11 }}
                onClick={() => open(file)}
              >
                {file.is_dir ? "Open" : "View"}
              </button>
              {!file.is_dir && (
                <button
                  className="hive-btn hive-btn-danger"
                  style={{ padding: "4px 10px", fontSize: 11 }}
                  onClick={() => setDelTarget(file.path)}
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}

        {!isLoading && entries.length === 0 && (
          <div style={{ padding: "48px 20px", textAlign: "center" }}>
            <p style={{ fontSize: 24, margin: "0 0 12px 0" }}>📂</p>
            <p style={{ fontSize: 14, fontWeight: 500, color: "var(--c-text-1)", margin: "0 0 6px 0" }}>Workspace is empty</p>
            <p style={{ fontSize: 13, color: "var(--c-text-3)", margin: "0 0 20px 0", maxWidth: 360, marginInline: "auto" }}>
              Run the <strong>market-researcher</strong> agent with a research topic, or the <strong>file-manager</strong> agent to create files. They'll appear here automatically.
            </p>
          </div>
        )}
      </div>

      {viewing   && <ViewerModal file={viewing} onClose={() => setViewing(null)} />}
      {delTarget && (
        <DeleteConfirm
          path={delTarget}
          onCancel={() => setDelTarget(null)}
          onConfirm={() => deleteFile.mutate(delTarget)}
          isPending={deleteFile.isPending}
        />
      )}
    </div>
  );
}
