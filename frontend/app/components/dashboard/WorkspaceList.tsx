"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import type { Workspace } from "@/lib/api";

interface WorkspaceListProps {
  workspaces: Workspace[];
  onWorkspaceClick: (workspace: Workspace) => void;
  onCreate: (name: string) => Promise<void>;
  disabled?: boolean;
}

export function WorkspaceList({
  workspaces,
  onWorkspaceClick,
  onCreate,
  disabled = false,
}: WorkspaceListProps) {
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    const trimmed = name.trim();
    if (!trimmed || creating) return;

    setCreating(true);
    try {
      await onCreate(trimmed);
      setName("");
      setIsCreating(false);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-section">Workspaces</h3>
        <button
          type="button"
          onClick={() => setIsCreating((current) => !current)}
          disabled={disabled}
          className="ui-btn ui-btn-neutral ui-btn-sm"
        >
          <Plus className="h-3.5 w-3.5" />
          Create
        </button>
      </div>

      {isCreating && (
        <div className="ui-panel p-2.5 space-y-2">
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={100}
            placeholder="Workspace name"
            className="ui-input ui-input-sm"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setIsCreating(false);
                setName("");
              }}
              className="ui-btn ui-btn-ghost ui-btn-sm"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                void handleCreate();
              }}
              disabled={!name.trim() || creating}
              className="ui-btn ui-btn-primary ui-btn-sm"
            >
              {creating ? "Creating..." : "Create"}
            </button>
          </div>
        </div>
      )}

      {workspaces.length === 0 ? (
        <p className="text-empty text-sm">No workspaces yet. Create one to group documents.</p>
      ) : (
        <div className="space-y-2">
          {workspaces.map((workspace) => (
            <button
              key={workspace.id}
              type="button"
              onClick={() => onWorkspaceClick(workspace)}
              className="ui-btn ui-btn-neutral ui-btn-md ui-btn-block flex-col items-start gap-1"
            >
              <p className="text-sm font-medium text-zinc-100 truncate">{workspace.name}</p>
              <p className="text-xs text-zinc-400 mt-1">
                {workspace.document_count} {workspace.document_count === 1 ? "document" : "documents"}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
