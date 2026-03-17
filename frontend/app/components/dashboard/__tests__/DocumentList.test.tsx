import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DocumentList } from "@/app/components/dashboard/DocumentList";
import type { Document } from "@/lib/api";

function makeDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: 1,
    user_id: 1,
    filename: "alpha.pdf",
    file_size: 2048,
    status: "completed",
    uploaded_at: "2026-03-10T00:00:00Z",
    processed_at: "2026-03-10T00:01:00Z",
    error_message: null,
    ...overrides,
  };
}

describe("DocumentList", () => {
  it("renders row status icons for queued, processing, completed, and failed states", () => {
    render(
      <DocumentList
        documents={[
          makeDocument({ id: 11, status: "pending", filename: "queued.pdf" }),
          makeDocument({ id: 12, status: "processing", filename: "processing.pdf" }),
          makeDocument({ id: 13, status: "completed", filename: "processed.pdf" }),
          makeDocument({ id: 14, status: "failed", filename: "failed.pdf", error_message: "Boom" }),
        ]}
        onDocumentClick={vi.fn()}
        onProcessDocument={vi.fn().mockResolvedValue(undefined)}
        onDeleteDocument={vi.fn()}
        hideDeleteActions
      />
    );

    expect(screen.getAllByLabelText("Processing")).toHaveLength(2);
    expect(screen.getByLabelText("Completed")).toBeInTheDocument();
    expect(screen.getByLabelText("Failed")).toBeInTheDocument();
  });

  it("hides process action for queued/processing rows and keeps retry for failed rows", async () => {
    const onProcessDocument = vi.fn().mockResolvedValue(undefined);
    const failedDoc = makeDocument({
      id: 22,
      status: "failed",
      filename: "needs-retry.pdf",
      error_message: "Retry me",
    });

    render(
      <DocumentList
        documents={[
          makeDocument({ id: 20, status: "pending", filename: "queued.pdf" }),
          makeDocument({ id: 21, status: "processing", filename: "processing.pdf" }),
          failedDoc,
        ]}
        onDocumentClick={vi.fn()}
        onProcessDocument={onProcessDocument}
        onDeleteDocument={vi.fn()}
        hideDeleteActions
      />
    );

    expect(screen.queryByRole("button", { name: "Process" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => {
      expect(onProcessDocument).toHaveBeenCalledWith(failedDoc);
    });
  });

  it("action wrapper uses group-focus-within for keyboard reveal and media-scoped opacity for touch safety", () => {
    const { container } = render(
      <DocumentList
        documents={[makeDocument()]}
        onDocumentClick={vi.fn()}
        onProcessDocument={vi.fn().mockResolvedValue(undefined)}
        onDeleteDocument={vi.fn()}
      />
    );

    // Row must carry `group` so Tailwind group-* variants apply.
    const row = container.querySelector('[role="button"]');
    expect(row?.className).toContain("group");

    // Find the action wrapper by locating the delete button's parent div.
    const deleteBtn = screen.getByRole("button", { name: "Delete" });
    const wrapper = deleteBtn.parentElement!;

    // group-focus-within so row-level keyboard focus reveals actions (not just focus inside wrapper).
    expect(wrapper.className).toContain("group-focus-within:opacity-100");

    // opacity-0 is media-scoped only — touch devices (no hover) should see actions by default.
    // Split on whitespace to check for a *standalone* opacity-0 class, not one nested inside a modifier.
    expect(wrapper.className.split(/\s+/)).not.toContain("opacity-0");
    expect(wrapper.className).toContain("[@media(hover:hover)]:opacity-0");
    expect(wrapper.className).toContain("[@media(hover:hover)]:group-hover:opacity-100");
  });

  it("action buttons are present in the DOM for completed and failed rows even when visually hidden", () => {
    render(
      <DocumentList
        documents={[
          makeDocument({ id: 1, status: "completed", filename: "ready.pdf" }),
          makeDocument({ id: 2, status: "failed", filename: "broken.pdf" }),
        ]}
        onDocumentClick={vi.fn()}
        onProcessDocument={vi.fn().mockResolvedValue(undefined)}
        onDeleteDocument={vi.fn()}
      />
    );

    // Both delete buttons are in the DOM (opacity hides them, not display:none).
    const deleteButtons = screen.getAllByRole("button", { name: "Delete" });
    expect(deleteButtons).toHaveLength(2);

    // The failed row's retry button is also present.
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
