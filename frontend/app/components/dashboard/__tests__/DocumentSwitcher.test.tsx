import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DocumentSwitcher } from "@/app/components/dashboard/DocumentSwitcher";
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

describe("DocumentSwitcher", () => {
  it("renders options for each document", () => {
    render(
      <DocumentSwitcher
        documents={[
          makeDocument({ id: 11, filename: "alpha.pdf" }),
          makeDocument({ id: 12, filename: "beta.pdf" }),
        ]}
        activeDocumentId={11}
        onSwitch={vi.fn()}
      />
    );

    const selector = screen.getByLabelText("Switch document");
    expect(selector).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "alpha.pdf" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "beta.pdf" })).toBeInTheDocument();
  });

  it("emits selected document id on change", () => {
    const onSwitch = vi.fn();

    render(
      <DocumentSwitcher
        documents={[
          makeDocument({ id: 11, filename: "alpha.pdf" }),
          makeDocument({ id: 12, filename: "beta.pdf" }),
        ]}
        activeDocumentId={11}
        onSwitch={onSwitch}
      />
    );

    fireEvent.change(screen.getByLabelText("Switch document"), {
      target: { value: "12" },
    });

    expect(onSwitch).toHaveBeenCalledWith(12);
  });
});
