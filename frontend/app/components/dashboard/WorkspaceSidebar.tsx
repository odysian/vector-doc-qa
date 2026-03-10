"use client";

import { ArrowLeft, Plus, X } from "lucide-react";
import type { Document, WorkspaceDetail } from "@/lib/api";

interface WorkspaceSidebarProps {
  workspace: WorkspaceDetail;
  activeDocumentId: number | null;
  onDocumentClick: (doc: Document) => void;
  onAddDocuments: () => void;
  onRemoveDocument: (docId: number) => void;
  onBack: () => void;
  disabled?: boolean;
}

export function WorkspaceSidebar({
  workspace,
  activeDocumentId,
  onDocumentClick,
  onAddDocuments,
  onRemoveDocument,
  onBack,
  disabled = false,
}: WorkspaceSidebarProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-zinc-800 space-y-2">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900 rounded"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>
        <h3 className="text-section truncate">{workspace.name}</h3>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {workspace.documents.length === 0 ? (
          <p className="text-empty text-sm">No documents in this workspace yet.</p>
        ) : (
          workspace.documents.map((doc) => (
            <div
              key={doc.id}
              className={`group flex items-center gap-2 rounded-lg border p-2 ${
                doc.id === activeDocumentId
                  ? "border-lapis-500/60 bg-lapis-500/10"
                  : "border-zinc-800 bg-zinc-800/30"
              }`}
            >
              <button
                type="button"
                onClick={() => onDocumentClick(doc)}
                className="flex-1 min-w-0 text-left text-sm text-zinc-200 hover:text-zinc-100 truncate cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900 rounded"
                title={doc.filename}
              >
                {doc.filename}
              </button>
              <button
                type="button"
                onClick={() => onRemoveDocument(doc.id)}
                disabled={disabled}
                className="opacity-0 group-hover:opacity-100 rounded p-1 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900 transition-opacity"
                aria-label={`Remove ${doc.filename}`}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))
        )}
      </div>

      <div className="p-3 border-t border-zinc-800">
        <button
          type="button"
          onClick={onAddDocuments}
          disabled={disabled}
          className="w-full inline-flex items-center justify-center gap-1 rounded-lg bg-lapis-600 px-3 py-2 text-sm font-medium text-white hover:bg-lapis-500 disabled:bg-zinc-700 disabled:text-zinc-500 disabled:cursor-not-allowed cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
        >
          <Plus className="h-4 w-4" />
          Add document
        </button>
      </div>
    </div>
  );
}
