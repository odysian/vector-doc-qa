import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceSidebar } from "@/app/components/dashboard/WorkspaceSidebar";
import type { Document, WorkspaceDetail } from "@/lib/api";

function makeDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: 1,
    user_id: 7,
    filename: "alpha.pdf",
    file_size: 1000,
    status: "completed",
    uploaded_at: "2026-03-10T00:00:00Z",
    processed_at: "2026-03-10T00:01:00Z",
    error_message: null,
    ...overrides,
  };
}

function makeWorkspace(overrides: Partial<WorkspaceDetail> = {}): WorkspaceDetail {
  return {
    id: 50,
    name: "Q1 Workspace",
    user_id: 7,
    document_count: 2,
    created_at: "2026-03-10T00:00:00Z",
    updated_at: "2026-03-10T00:00:00Z",
    documents: [
      makeDocument({ id: 21, filename: "alpha.pdf" }),
      makeDocument({ id: 22, filename: "beta.pdf" }),
    ],
    ...overrides,
  };
}

describe("WorkspaceSidebar", () => {
  it("renders workspace documents and active document style", () => {
    render(
      <WorkspaceSidebar
        workspace={makeWorkspace()}
        activeDocumentId={22}
        onDocumentClick={vi.fn()}
        onAddDocuments={vi.fn()}
        onDeleteWorkspace={vi.fn()}
        onRemoveDocument={vi.fn()}
        onBack={vi.fn()}
      />
    );

    const activeDocButton = screen.getByRole("button", { name: "beta.pdf" });
    const inactiveDocButton = screen.getByRole("button", { name: "alpha.pdf" });
    const activeRow = activeDocButton.closest("div.group");
    const inactiveRow = inactiveDocButton.closest("div.group");

    expect(activeRow?.className).toContain("border-lapis-500/60");
    expect(inactiveRow?.className).toContain("border-zinc-800");
  });

  it("runs document and workspace callbacks", () => {
    const workspace = makeWorkspace();
    const onDocumentClick = vi.fn();
    const onAddDocuments = vi.fn();
    const onRemoveDocument = vi.fn();

    render(
      <WorkspaceSidebar
        workspace={workspace}
        activeDocumentId={null}
        onDocumentClick={onDocumentClick}
        onAddDocuments={onAddDocuments}
        onDeleteWorkspace={vi.fn()}
        onRemoveDocument={onRemoveDocument}
        onBack={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "alpha.pdf" }));
    expect(onDocumentClick).toHaveBeenCalledWith(workspace.documents[0]);

    fireEvent.click(screen.getByRole("button", { name: "Remove beta.pdf" }));
    expect(onRemoveDocument).toHaveBeenCalledWith(22);

    fireEvent.click(screen.getByRole("button", { name: "Add document" }));
    expect(onAddDocuments).toHaveBeenCalledTimes(1);
  });
});
