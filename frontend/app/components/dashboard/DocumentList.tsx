/**
 * Document List: Display area for uploaded documents and their processing
 * status. Only completed documents open the chat; others show disabled state.
 * Process (pending/failed) and Delete actions per row.
 */
"use client";

import { useState } from "react";
import { Play, Trash2, Loader2 } from "lucide-react";
import { type Document } from "@/lib/api";
import { formatFileSize, formatDate } from "@/lib/utils";

interface DocumentListProps {
  documents: Document[];
  onDocumentClick: (document: Document) => void;
  onProcessDocument: (document: Document) => Promise<void>;
  onDeleteDocument: (document: Document) => Promise<void>;
}

/**
 * Renders list of documents. Completed docs open ChatWindow; processing/pending/failed
 * show disabled styling. Process button for pending/failed; Delete for all.
 */
export function DocumentList({
  documents,
  onDocumentClick,
  onProcessDocument,
  onDeleteDocument,
}: DocumentListProps) {
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const getStatusColor = (status: Document["status"]) => {
    switch (status) {
      case "completed":
        return "text-green-400 bg-green-900/20";
      case "processing":
        return "text-yellow-400 bg-yellow-900/20";
      case "failed":
        return "text-red-400 bg-red-900/20";
      default:
        return "text-zinc-400 bg-zinc-800/50";
    }
  };

  const isClickable = (doc: Document) => doc.status === "completed";
  const canProcess = (doc: Document) =>
    doc.status === "pending" || doc.status === "failed";

  const handleProcess = async (e: React.MouseEvent, doc: Document) => {
    e.stopPropagation();
    if (!canProcess(doc) || processingId !== null) return;
    setProcessingId(doc.id);
    try {
      await onProcessDocument(doc);
    } finally {
      setProcessingId(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, doc: Document) => {
    e.stopPropagation();
    if (deletingId !== null) return;
    setDeletingId(doc.id);
    try {
      await onDeleteDocument(doc);
    } finally {
      setDeletingId(null);
    }
  };

  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-zinc-500">
        No documents yet. Upload a PDF to get started.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {documents.map((doc) => {
        const clickable = isClickable(doc);
        const showProcess = canProcess(doc);
        const isProcessing = processingId === doc.id;
        const isDeleting = deletingId === doc.id;
        return (
          <div
            key={doc.id}
            onClick={() => clickable && onDocumentClick(doc)}
            role="button"
            tabIndex={clickable ? 0 : undefined}
            onKeyDown={(e) => {
              if (clickable && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                onDocumentClick(doc);
              }
            }}
            aria-disabled={!clickable}
            className={`rounded-lg p-4 border transition-colors ${
              clickable
                ? "bg-zinc-900 border-zinc-800 hover:border-lapis-500/50 hover:bg-zinc-800/50 cursor-pointer"
                : "bg-zinc-900/70 border-zinc-800 cursor-not-allowed opacity-75"
            }`}
          >
            <div className="flex justify-between items-start gap-3">
              <div className="flex-1 min-w-0">
                <h3 className="text-zinc-100 font-medium mb-1 truncate">
                  {doc.filename}
                </h3>
                <div className="flex items-center gap-3 text-sm text-zinc-400">
                  <span>{formatFileSize(doc.file_size)}</span>
                  <span>•</span>
                  <span>{formatDate(doc.uploaded_at)}</span>
                </div>
                {doc.status === "failed" && doc.error_message && (
                  <p
                    className="mt-2 text-xs text-red-400/90 truncate"
                    title={doc.error_message}
                  >
                    {doc.error_message}
                  </p>
                )}
                {doc.status === "processing" && (
                  <p className="mt-2 text-xs text-zinc-500">
                    Processing… check back in a moment.
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {showProcess && (
                  <button
                    type="button"
                    onClick={(e) => handleProcess(e, doc)}
                    disabled={isProcessing || processingId !== null}
                    title={doc.status === "failed" ? "Retry processing" : "Process document"}
                    className="p-2 rounded-lg text-lapis-400 hover:bg-lapis-500/20 hover:text-lapis-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                    aria-label={doc.status === "failed" ? "Retry processing" : "Process document"}
                  >
                    {isProcessing ? (
                      <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
                    ) : (
                      <Play className="w-4 h-4" aria-hidden />
                    )}
                  </button>
                )}
                <button
                  type="button"
                  onClick={(e) => handleDelete(e, doc)}
                  disabled={isDeleting}
                  title="Delete document"
                  className="p-2 rounded-lg text-zinc-400 hover:bg-red-500/20 hover:text-red-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
                  aria-label="Delete document"
                >
                  {isDeleting ? (
                    <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
                    ) : (
                      <Trash2 className="w-4 h-4" aria-hidden />
                    )}
                </button>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(doc.status)}`}
                >
                  {doc.status}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
