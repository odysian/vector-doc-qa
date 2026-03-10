import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatWindow } from "@/app/components/dashboard/ChatWindow";
import { chatService } from "@/lib/services/chatService";
import type { Document, PipelineMeta, QueryResponse } from "@/lib/api";

vi.mock("@/lib/services/chatService", async () => {
  const actual = await vi.importActual<typeof import("@/lib/services/chatService")>(
    "@/lib/services/chatService"
  );
  return {
    ...actual,
    chatService: {
      ...actual.chatService,
      getMessages: vi.fn(),
      getWorkspaceMessages: vi.fn(),
      queryWorkspace: vi.fn(),
      queryDocumentStream: vi.fn(),
    },
  };
});

const getMessagesMock = vi.mocked(chatService.getMessages);
const getWorkspaceMessagesMock = vi.mocked(chatService.getWorkspaceMessages);
const queryWorkspaceMock = vi.mocked(chatService.queryWorkspace);
const queryDocumentStreamMock = vi.mocked(chatService.queryDocumentStream);

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
    getWorkspaceMessagesMock.mockResolvedValue({ messages: [], total: 0 });
    queryWorkspaceMock.mockReset();
    queryDocumentStreamMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows stop control during streaming and restores send on done", async () => {
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
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: "Follow up question" } });
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument();

    const streamCallbacks = queryDocumentStreamMock.mock.calls[0]?.[2] as StreamCallbacks | undefined;
    expect(streamCallbacks).toBeDefined();
    streamCallbacks?.onDone({ message_id: 100 });
    releaseStreamRef.current?.();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
    });
    expect(screen.queryByRole("button", { name: "Stop" })).not.toBeInTheDocument();

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

    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(container.querySelectorAll("div.rounded-2xl")).toHaveLength(2);
  });

  it("retries failed responses with the original query", async () => {
    queryDocumentStreamMock
      .mockImplementationOnce(async (_documentId, _query, callbacks) => {
        await Promise.resolve();
        callbacks.onError("Stream failed");
      })
      .mockImplementationOnce(async (_documentId, _query, callbacks) => {
        await Promise.resolve();
        callbacks.onToken("Recovered answer");
        callbacks.onDone({ message_id: 202 });
      });

    render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
    await waitFor(() => {
      expect(screen.queryByText("Loading conversation...")).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Ask a question about this document...");
    fireEvent.change(input, { target: { value: "Retry this question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    const retryButton = await screen.findByRole("button", { name: "Retry" });
    fireEvent.click(retryButton);

    await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(2));
    expect(queryDocumentStreamMock.mock.calls[1]?.[1]).toBe("Retry this question");
    expect(await screen.findByText("Recovered answer")).toBeInTheDocument();
  });

  it("stops an active stream, then retries with the original query", async () => {
    let capturedSignal: AbortSignal | undefined;
    let stoppedStreamCallbacks: StreamCallbacks | undefined;
    const originalQuery = "Please stop this";

    queryDocumentStreamMock
      .mockImplementationOnce(async (_documentId, _query, callbacks, options) => {
        stoppedStreamCallbacks = callbacks as StreamCallbacks;
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
      })
      .mockImplementationOnce(async (_documentId, _query, callbacks) => {
        await Promise.resolve();
        callbacks.onToken("Recovered after stop");
        callbacks.onDone({ message_id: 404 });
      });

    render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
    await waitFor(() => {
      expect(screen.queryByText("Loading conversation...")).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Ask a question about this document...");
    fireEvent.change(input, { target: { value: originalQuery } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1));
    expect(capturedSignal).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));

    await waitFor(() => {
      expect(capturedSignal?.aborted).toBe(true);
    });
    stoppedStreamCallbacks?.onToken("Zombie token after stop");
    expect(screen.queryByText("Zombie token after stop")).not.toBeInTheDocument();

    expect(await screen.findByText("Stopped. You can retry this response.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(2));
    expect(queryDocumentStreamMock.mock.calls[1]?.[1]).toBe(originalQuery);
    expect(await screen.findByText("Recovered after stop")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
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

  it("prevents duplicate stream placeholders on rapid double-submit", async () => {
    const releaseStreamRef: { current: (() => void) | null } = { current: null };

    queryDocumentStreamMock.mockImplementation(
      async () => {
        await new Promise<void>((resolve) => {
          releaseStreamRef.current = () => resolve();
        });
      }
    );

    const { container } = render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
    await waitFor(() => {
      expect(screen.queryByText("Loading conversation...")).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Ask a question about this document...");
    fireEvent.change(input, { target: { value: "No duplicates please" } });

    const form = input.closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form as HTMLFormElement);
    fireEvent.submit(form as HTMLFormElement);

    await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1));
    expect(container.querySelectorAll("div.rounded-2xl")).toHaveLength(2);

    const streamCallbacks = queryDocumentStreamMock.mock.calls[0]?.[2] as StreamCallbacks | undefined;
    streamCallbacks?.onDone({ message_id: 303 });
    releaseStreamRef.current?.();
  });

  it("shows source page ranges and deep-links on citation click", async () => {
    getMessagesMock.mockResolvedValueOnce({
      messages: [
        {
          id: 1,
          document_id: documentFixture.id,
          user_id: documentFixture.user_id,
          role: "assistant",
          content: "The answer is supported by this excerpt.",
          sources: [
            {
              chunk_id: 11,
              content: "Cited section content for pages three and four.",
              similarity: 0.98,
              chunk_index: 2,
              page_start: 3,
              page_end: 4,
              document_id: 15,
              document_filename: "source.pdf",
            },
          ],
          created_at: "2026-03-02T12:02:00Z",
        },
      ],
      total: 1,
    });

    const onCitationClick = vi.fn();
    render(
      <ChatWindow
        document={documentFixture}
        onBack={vi.fn()}
        onCitationClick={onCitationClick}
      />
    );

    await screen.findByText("The answer is supported by this excerpt.");
    fireEvent.click(screen.getByRole("button", { name: "Sources (1)" }));

    const pageRangeLabel = await screen.findByText("Pages 3-4");
    fireEvent.click(pageRangeLabel);

    expect(onCitationClick).toHaveBeenCalledWith({
      page: 3,
      snippet: "Cited section content for pages three and four.",
      documentId: 15,
    });
  });

  it("toggles debug mode and shows pipeline metadata/similarity from history", async () => {
    localStorage.removeItem("quaero_debug_mode");
    getMessagesMock.mockResolvedValueOnce({
      messages: [
        {
          id: 2,
          document_id: documentFixture.id,
          user_id: documentFixture.user_id,
          role: "assistant",
          content: "Debuggable answer.",
          sources: [
            {
              chunk_id: 3,
              content: "Debug source content.",
              similarity: 0.91,
              chunk_index: 0,
            },
          ],
          pipeline_meta: {
            embed_ms: 11,
            retrieval_ms: 12,
            llm_ms: 13,
            total_ms: 36,
            top_similarity: 0.91,
            avg_similarity: 0.89,
            chunks_retrieved: 1,
            chunks_above_threshold: 1,
            similarity_spread: 0,
            chat_history_turns_included: 2,
          },
          created_at: "2026-03-02T12:02:00Z",
        },
      ],
      total: 1,
    });

    render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
    await screen.findByText("Debuggable answer.");

    fireEvent.click(screen.getByRole("button", { name: "Sources (1)" }));
    expect(screen.queryByText(/Similarity:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/confidence/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Debug off" }));

    expect(screen.getByRole("button", { name: "Debug on" })).toBeInTheDocument();
    expect(localStorage.getItem("quaero_debug_mode")).toBe("true");
    expect(screen.getByText(/confidence/)).toBeInTheDocument();
    expect(screen.getByText("Similarity: 91.0%")).toBeInTheDocument();
  });

  it("submits workspace queries through non-streaming workspace endpoint", async () => {
    queryWorkspaceMock.mockResolvedValueOnce({
      query: "How do these files connect?",
      answer: "They share the same timeline.",
      sources: [
        {
          chunk_id: 42,
          content: "Timeline snippet.",
          similarity: 0.91,
          chunk_index: 1,
          page_start: 2,
          document_id: 99,
          document_filename: "timeline.pdf",
        },
      ],
    });

    render(<ChatWindow workspaceId={22} workspaceName="Roadmap" onBack={vi.fn()} />);
    await waitFor(() => {
      expect(screen.queryByText("Loading conversation...")).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Ask a question across this workspace...");
    fireEvent.change(input, { target: { value: "How do these files connect?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(queryDocumentStreamMock).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(queryWorkspaceMock).toHaveBeenCalledWith(22, "How do these files connect?");
      expect(screen.getByText("They share the same timeline.")).toBeInTheDocument();
    });
  });
});
