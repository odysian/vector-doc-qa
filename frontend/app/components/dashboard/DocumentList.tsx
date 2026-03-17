/**
 * Document List: Sidebar list. Row 1: title + buttons. Row 2: status icon + size.
 * Upload date moved to chat header. Compact spacing.
 */
"use client";

import { useState } from "react";
import {
  Play,
  Trash2,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
} from "lucide-react";
import { type Document } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";

interface DocumentListProps {
  documents: Document[];
  onDocumentClick: (document: Document) => void;
  onProcessDocument: (document: Document) => Promise<void>;
  onDeleteDocument: (document: Document) => void;
  hideDeleteActions?: boolean;
}

function StatusIcon({
  status,
  processing,
}: {
  status: Document["status"];
  processing: boolean;
}) {
  const base = "w-4 h-4 shrink-0";
  if (processing || status === "pending" || status === "processing")
    return (
      <Loader2
        className={`${base} text-yellow-400 animate-spin`}
        aria-label="Processing"
      />
    );
  switch (status) {
    case "completed":
      return (
        <CheckCircle2
          className={`${base} text-green-400`}
          aria-label="Completed"
        />
      );
    case "failed":
      return (
        <XCircle className={`${base} text-red-400`} aria-label="Failed" />
      );
    default:
      return <Clock className={`${base} text-zinc-400`} aria-label="Pending" />;
  }
}

export function DocumentList({
  documents,
  onDocumentClick,
  onProcessDocument,
  onDeleteDocument,
  hideDeleteActions = false,
}: DocumentListProps) {
  const [processingId, setProcessingId] = useState<number | null>(null);

  const isClickable = (doc: Document) => doc.status === "completed";
  const canQueue = (doc: Document) => doc.status === "failed";

  const handleProcess = async (e: React.MouseEvent, doc: Document) => {
    e.stopPropagation();
    if (!canQueue(doc) || processingId !== null) return;
    setProcessingId(doc.id);
    try {
      await onProcessDocument(doc);
    } finally {
      setProcessingId(null);
    }
  };

  const handleDelete = (e: React.MouseEvent, doc: Document) => {
    e.stopPropagation();
    onDeleteDocument(doc);
  };

  if (documents.length === 0) {
    return (
      <p className="text-center py-6 text-empty">
        No documents yet. Upload a PDF above.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => {
        const clickable = isClickable(doc);
        const showProcess = canQueue(doc);
        const isProcessing = processingId === doc.id;
        const actionLabel = doc.status === "failed" ? "Retry" : "Process";
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
            className={`group rounded-lg border transition-colors p-3 outline-none ${
              clickable
                ? "bg-zinc-800/50 border-zinc-700 hover:border-lapis-500/40 hover:bg-zinc-800 cursor-pointer focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
                : "bg-zinc-800/30 border-zinc-800 cursor-not-allowed opacity-80"
            }`}
          >
            {/* Row 1: title + buttons */}
            <div className="flex items-center gap-2 min-w-0">
              <h3
                className="text-zinc-100 font-medium text-sm truncate flex-1 min-w-0"
                title={doc.filename}
              >
                {doc.filename}
              </h3>
              <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity duration-150">
                {showProcess && (
                  <button
                    type="button"
                    onClick={(e) => handleProcess(e, doc)}
                    disabled={isProcessing || processingId !== null}
                    title={actionLabel}
                    className="ui-btn ui-btn-secondary ui-btn-sm"
                    aria-label={actionLabel}
                  >
                    {isProcessing ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Play className="w-4 h-4" />
                    )}
                  </button>
                )}
                {!hideDeleteActions && (
                  <button
                    type="button"
                    onClick={(e) => handleDelete(e, doc)}
                    title="Delete"
                    className="ui-btn ui-btn-danger-outline ui-btn-sm"
                    aria-label="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
            {/* Row 2: status icon + file size */}
            <div className="flex items-center gap-2 mt-1.5 text-meta-bright">
              <StatusIcon
                status={doc.status}
                processing={isProcessing}
              />
              <span>{formatFileSize(doc.file_size)}</span>
              {doc.status === "failed" && doc.error_message && (
                <span
                  className="truncate text-error max-w-[120px]"
                  title={doc.error_message}
                >
                  Failed
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
