import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DeleteDocumentModal } from "@/app/components/dashboard/DeleteDocumentModal";
import type { Document } from "@/lib/api";

function makeDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: 1,
    user_id: 9,
    filename: "alpha.pdf",
    file_size: 100,
    status: "completed",
    uploaded_at: "2026-03-10T00:00:00Z",
    processed_at: "2026-03-10T00:01:00Z",
    error_message: null,
    ...overrides,
  };
}

describe("DeleteDocumentModal", () => {
  it("disables actions and marks delete CTA as busy while deleting", () => {
    render(
      <DeleteDocumentModal
        document={makeDocument()}
        deleting
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const backdrop = screen.getByLabelText("Cancel");
    const cancelButton = screen
      .getAllByRole("button", { name: "Cancel" })
      .find((button) => button.className.includes("ui-btn"));
    const deleteButton = screen.getByRole("button", { name: "Deleting…" });
    if (!cancelButton) {
      throw new Error("Expected modal cancel action button");
    }

    expect(backdrop).toBeDisabled();
    expect(cancelButton).toBeDisabled();
    expect(deleteButton).toBeDisabled();
    expect(deleteButton).toHaveClass("ui-btn-busy");
  });
});
