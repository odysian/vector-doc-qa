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
        className="ui-input ui-input-sm"
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
