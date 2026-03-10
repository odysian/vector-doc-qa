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
});
