"use client";

import type { Document } from "@/lib/api";

interface DocumentSwitcherProps {
  documents: Document[];
  activeDocumentId: number;
  onSwitch: (documentId: number) => void;
}

export function DocumentSwitcher({
  documents,
  activeDocumentId,
  onSwitch,
}: DocumentSwitcherProps) {
  return (
    <div className="mb-2 w-full">
      <label className="sr-only" htmlFor="workspace-document-switcher">
        Switch document
      </label>
      <select
        id="workspace-document-switcher"
        value={activeDocumentId}
        onChange={(event) => onSwitch(Number(event.target.value))}
        className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-lapis-500/20 focus:border-lapis-500"
      >
        {documents.map((doc) => (
          <option key={doc.id} value={doc.id}>
            {doc.filename}
          </option>
        ))}
      </select>
    </div>
  );
}
