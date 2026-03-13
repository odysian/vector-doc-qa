"use client";

import { ArrowLeft, Plus, Trash2, X } from "lucide-react";
import type { Document, WorkspaceDetail } from "@/lib/api";

interface WorkspaceSidebarProps {
  workspace: WorkspaceDetail;
  activeDocumentId: number | null;
  onDocumentClick: (doc: Document) => void;
  onAddDocuments: () => void;
  onDeleteWorkspace: () => void;
  onRemoveDocument: (docId: number) => void;
  onBack: () => void;
  disabled?: boolean;
}

export function WorkspaceSidebar({
  workspace,
  activeDocumentId,
  onDocumentClick,
  onAddDocuments,
  onDeleteWorkspace,
  onRemoveDocument,
  onBack,
  disabled = false,
}: WorkspaceSidebarProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-zinc-800 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={onBack}
            className="ui-btn ui-btn-ghost ui-btn-sm"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back
          </button>
          <button
            type="button"
            onClick={onDeleteWorkspace}
            disabled={disabled}
            className="ui-btn ui-btn-danger-outline ui-btn-sm"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete workspace
          </button>
        </div>
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
                className="ui-btn ui-btn-ghost ui-btn-sm flex-1 min-w-0 justify-start"
                title={doc.filename}
              >
                <span className="truncate">{doc.filename}</span>
              </button>
              <button
                type="button"
                onClick={() => onRemoveDocument(doc.id)}
                disabled={disabled}
                className="ui-btn ui-btn-ghost ui-btn-sm opacity-0 group-hover:opacity-100 transition-opacity"
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
          className="ui-btn ui-btn-primary ui-btn-md ui-btn-block"
        >
          <Plus className="h-4 w-4" />
          Add document
        </button>
      </div>
    </div>
  );
}
