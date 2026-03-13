/**
 * Delete document confirmation modal. Presentational: parent owns state and
 * performs the delete; this component only renders the dialog and calls
 * onConfirm / onCancel.
 */
import type { Document } from "@/lib/api";

interface DeleteDocumentModalProps {
  /** The document the user is about to delete (filename shown in message). */
  document: Document;
  /** True while the parent is performing the delete (disables buttons, shows "Deleting…"). */
  deleting: boolean;
  /** Called when the user clicks Delete. Parent should call the API then close. */
  onConfirm: () => void;
  /** Called when the user clicks Cancel or the backdrop. Parent should close without deleting. */
  onCancel: () => void;
}

export function DeleteDocumentModal({
  document,
  deleting,
  onConfirm,
  onCancel,
}: DeleteDocumentModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
    >
      <button
        type="button"
        onClick={onCancel}
        disabled={deleting}
        className="absolute inset-0 bg-black/60 cursor-default disabled:cursor-wait"
        aria-label="Cancel"
      />
      <div className="relative ui-panel max-w-md w-full p-6 shadow-xl">
        <h2
          id="delete-dialog-title"
          className="text-lg font-semibold text-zinc-100 mb-2"
        >
          Delete document?
        </h2>
        <p className="text-zinc-400 text-sm mb-6">
          &quot;{document.filename}&quot; will be permanently deleted. This
          cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={deleting}
            className="ui-btn ui-btn-ghost ui-btn-md"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={deleting}
            className="ui-btn ui-btn-danger ui-btn-md disabled:cursor-wait"
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
