import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DeleteWorkspaceModal } from "@/app/components/dashboard/DeleteWorkspaceModal";

describe("DeleteWorkspaceModal", () => {
  it("disables actions and marks delete CTA as busy while deleting", () => {
    render(
      <DeleteWorkspaceModal
        workspaceName="Roadmap"
        deleting
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const backdrop = screen.getByLabelText("Cancel");
    const cancelButton = screen
      .getAllByRole("button", { name: "Cancel" })
      .find((button) => button.className.includes("ui-btn"));
    const deleteButton = screen.getByRole("button", { name: "Deleting..." });
    if (!cancelButton) {
      throw new Error("Expected modal cancel action button");
    }

    expect(backdrop).toBeDisabled();
    expect(cancelButton).toBeDisabled();
    expect(deleteButton).toBeDisabled();
    expect(deleteButton).toHaveClass("ui-btn-busy");
  });
});
