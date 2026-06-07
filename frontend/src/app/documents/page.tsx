"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useRef } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function DocumentsPage() {
  const qc = useQueryClient();
  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: api.documents.list,
  });

  const fileRef = useRef<HTMLInputElement>(null);

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
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Documents</h1>
        <button
          onClick={() => fileRef.current?.click()}
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors"
        >
          Upload
        </button>
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload.mutate(f);
          }}
        />
      </div>

      {upload.isPending && <p className="text-blue-400 text-sm">Uploading…</p>}
      {upload.isError && <p className="text-red-400 text-sm">{String(upload.error)}</p>}

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl divide-y divide-neutral-800">
        {docs.map((doc) => (
          <div key={doc.id} className="flex items-center gap-4 px-5 py-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{doc.name}</p>
              <p className="text-xs text-neutral-500">
                {doc.content_type} · {doc.size_bytes != null ? `${doc.size_bytes} bytes` : "?"}
              </p>
            </div>
            {doc.embedded && (
              <span className="text-xs bg-green-900/40 text-green-400 px-2 py-0.5 rounded">
                embedded
              </span>
            )}
            <span className="text-xs text-neutral-500 shrink-0">{formatDate(doc.created_at)}</span>
          </div>
        ))}
        {!isLoading && docs.length === 0 && (
          <p className="px-5 py-4 text-sm text-neutral-500">No documents uploaded yet.</p>
        )}
      </div>
    </div>
  );
}
