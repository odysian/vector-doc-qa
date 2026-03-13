"use client";

import { useMemo, useState } from "react";
import { X } from "lucide-react";
import type { Document } from "@/lib/api";

interface DocumentPickerProps {
  availableDocuments: Document[];
  onAdd: (documentIds: number[]) => Promise<boolean>;
  onClose: () => void;
  maxDocuments: number;
}

export function DocumentPicker({
  availableDocuments,
  onAdd,
  onClose,
  maxDocuments,
}: DocumentPickerProps) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const remainingCapacity = Math.max(maxDocuments, 0);
  const reachedCapacity = remainingCapacity === 0;

  const sortedDocuments = useMemo(
    () => [...availableDocuments].sort((a, b) => a.filename.localeCompare(b.filename)),
    [availableDocuments]
  );

  const toggleSelection = (documentId: number) => {
    setSelectedIds((current) => {
      if (current.includes(documentId)) {
        return current.filter((id) => id !== documentId);
      }
      if (current.length >= remainingCapacity) return current;
      return [...current, documentId];
    });
  };

  const handleAdd = async () => {
    if (selectedIds.length === 0 || submitting) return;
    setSubmitting(true);
    try {
      const addSucceeded = await onAdd(selectedIds);
      if (addSucceeded) {
        onClose();
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="add-documents-title"
    >
      <button
        type="button"
        onClick={onClose}
        className="absolute inset-0 bg-black/60 cursor-default"
        aria-label="Close add documents dialog"
      />
      <div className="relative max-w-lg w-full ui-panel shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <h2 id="add-documents-title" className="text-base font-semibold text-zinc-100">
              Add documents
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              {remainingCapacity} {remainingCapacity === 1 ? "slot" : "slots"} remaining
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ui-btn ui-btn-ghost ui-btn-sm"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-80 overflow-y-auto px-5 py-4 space-y-2">
          {reachedCapacity ? (
            <p className="text-sm text-zinc-400">Workspace is at the 20 document limit.</p>
          ) : sortedDocuments.length === 0 ? (
            <p className="text-sm text-zinc-400">No completed documents available to add.</p>
          ) : (
            sortedDocuments.map((doc) => {
              const selected = selectedIds.includes(doc.id);
              const disabled = !selected && selectedIds.length >= remainingCapacity;
              return (
                <label
                  key={doc.id}
                  className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                    selected
                      ? "border-lapis-500/60 bg-lapis-500/10 text-zinc-100"
                      : "border-zinc-800 bg-zinc-800/30 text-zinc-300"
                  } ${disabled ? "opacity-50" : "cursor-pointer"}`}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    disabled={disabled}
                    onChange={() => toggleSelection(doc.id)}
                    className="h-4 w-4 rounded border-zinc-600 bg-zinc-950 text-lapis-600 focus:ring-lapis-500"
                  />
                  <span className="truncate">{doc.filename}</span>
                </label>
              );
            })
          )}
        </div>

        <div className="border-t border-zinc-800 px-5 py-4 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="ui-btn ui-btn-ghost ui-btn-md"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              void handleAdd();
            }}
            disabled={selectedIds.length === 0 || submitting}
            className="ui-btn ui-btn-primary ui-btn-md"
          >
            {submitting ? "Adding..." : "Add selected"}
          </button>
        </div>
      </div>
    </div>
  );
}
