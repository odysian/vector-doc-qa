interface DeleteWorkspaceModalProps {
  workspaceName: string;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteWorkspaceModal({
  workspaceName,
  deleting,
  onConfirm,
  onCancel,
}: DeleteWorkspaceModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-workspace-dialog-title"
    >
      <button
        type="button"
        onClick={onCancel}
        disabled={deleting}
        className="absolute inset-0 bg-black/60 cursor-default disabled:cursor-wait"
        aria-label="Cancel"
      />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl max-w-md w-full p-6">
        <h2
          id="delete-workspace-dialog-title"
          className="text-lg font-semibold text-zinc-100 mb-2"
        >
          Delete workspace?
        </h2>
        <p className="text-zinc-400 text-sm mb-6">
          &quot;{workspaceName}&quot; will be permanently deleted. This cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={deleting}
            className="px-4 py-2 rounded-lg text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={deleting}
            className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-medium transition-colors cursor-pointer disabled:opacity-70 disabled:cursor-wait"
          >
            {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
