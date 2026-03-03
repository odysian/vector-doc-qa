import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatWindow } from "@/app/components/dashboard/ChatWindow";
import { api } from "@/lib/api";
import type { Document, PipelineMeta, QueryResponse } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getMessages: vi.fn(),
      queryDocumentStream: vi.fn(),
    },
  };
});

const getMessagesMock = vi.mocked(api.getMessages);
const queryDocumentStreamMock = vi.mocked(api.queryDocumentStream);

interface StreamCallbacks {
  onSources: (sources: QueryResponse["sources"]) => void;
  onToken: (token: string) => void;
  onMeta: (meta: PipelineMeta) => void;
  onDone: (data: { message_id: number }) => void;
  onError: (detail: string) => void;
}

const documentFixture: Document = {
  id: 7,
  user_id: 1,
  filename: "guide.pdf",
  file_size: 1024,
  status: "completed",
  uploaded_at: "2026-03-02T12:00:00Z",
  processed_at: "2026-03-02T12:01:00Z",
  error_message: null,
};

describe("ChatWindow streaming lifecycle", () => {
  beforeEach(() => {
    getMessagesMock.mockResolvedValue({ messages: [], total: 0 });
    queryDocumentStreamMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("disables send controls during streaming and re-enables on done", async () => {
    const releaseStreamRef: { current: (() => void) | null } = { current: null };

    queryDocumentStreamMock.mockImplementation(
      async () => {
        await new Promise<void>((resolve) => {
          releaseStreamRef.current = () => resolve();
        });
      }
    );

    render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
    await waitFor(() => {
      expect(screen.queryByText("Loading conversation...")).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Ask a question about this document...");
    fireEvent.change(input, { target: { value: "First question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Sending..." })).toBeDisabled();

    fireEvent.change(input, { target: { value: "Follow up question" } });
    expect(screen.getByRole("button", { name: "Sending..." })).toBeDisabled();

    const streamCallbacks = queryDocumentStreamMock.mock.calls[0]?.[2] as StreamCallbacks | undefined;
    expect(streamCallbacks).toBeDefined();
    streamCallbacks?.onDone({ message_id: 100 });
    releaseStreamRef.current?.();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
    });

    fireEvent.change(input, { target: { value: "Question after done" } });
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("appends streaming errors without duplicating assistant bubbles", async () => {
    queryDocumentStreamMock.mockImplementation(async (_documentId, _query, callbacks) => {
      await Promise.resolve();
      callbacks.onError("Stream failed");
    });

    const { container } = render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
    await waitFor(() => {
      expect(screen.queryByText("Loading conversation...")).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Ask a question about this document...");
    fireEvent.change(input, { target: { value: "Trigger error" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(screen.getByText("Error: Stream failed")).toBeInTheDocument();
    });

    expect(container.querySelectorAll("div.rounded-2xl")).toHaveLength(2);
  });

  it("aborts active stream on unmount cleanup", async () => {
    let capturedSignal: AbortSignal | undefined;

    queryDocumentStreamMock.mockImplementation(async (_documentId, _query, _callbacks, options) => {
      capturedSignal = options?.signal;
      await new Promise<void>((resolve, reject) => {
        if (!capturedSignal) {
          resolve();
          return;
        }

        if (capturedSignal.aborted) {
          reject(new DOMException("aborted", "AbortError"));
          return;
        }

        capturedSignal.addEventListener(
          "abort",
          () => reject(new DOMException("aborted", "AbortError")),
          { once: true }
        );
      });
    });

    const { unmount } = render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);

    const input = screen.getByPlaceholderText("Ask a question about this document...");
    fireEvent.change(input, { target: { value: "Abort me" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1));
    expect(capturedSignal).toBeDefined();
    expect(capturedSignal?.aborted).toBe(false);

    unmount();

    await waitFor(() => {
      expect(capturedSignal?.aborted).toBe(true);
    });
  });
});
