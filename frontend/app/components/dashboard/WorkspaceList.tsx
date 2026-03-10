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
          className="inline-flex items-center gap-1 rounded-md border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-300 hover:text-zinc-100 hover:border-zinc-500 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
        >
          <Plus className="h-3.5 w-3.5" />
          Create
        </button>
      </div>

      {isCreating && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-800/40 p-2.5 space-y-2">
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={100}
            placeholder="Workspace name"
            className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-lapis-500/20 focus:border-lapis-500"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setIsCreating(false);
                setName("");
              }}
              className="rounded-md px-2.5 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                void handleCreate();
              }}
              disabled={!name.trim() || creating}
              className="rounded-md bg-lapis-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-lapis-500 disabled:bg-zinc-700 disabled:text-zinc-500 disabled:cursor-not-allowed cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
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
              className="w-full rounded-lg border border-zinc-800 bg-zinc-800/30 p-3 text-left hover:border-lapis-500/40 hover:bg-zinc-800/50 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
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
