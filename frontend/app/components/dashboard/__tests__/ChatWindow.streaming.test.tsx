import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createEvent, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ChatWindow } from "@/app/components/dashboard/ChatWindow";
import { chatService } from "@/lib/services/chatService";
import * as useChatStateModule from "@/lib/hooks/useChatState";
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

const setComposerScrollHeight = (element: HTMLTextAreaElement, scrollHeight: number) => {
  Object.defineProperty(element, "scrollHeight", {
    configurable: true,
    value: scrollHeight,
  });
};

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
    const sendButton = screen.getByRole("button", { name: "Send message" });
    expect(sendButton).toHaveAttribute("title", "Send message");
    expect(sendButton).toHaveAttribute("aria-label", "Send message");
    expect(sendButton.textContent).toBe("");
    fireEvent.click(sendButton);

    await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1));
    const stopButton = screen.getByRole("button", { name: "Stop response" });
    expect(stopButton).toBeInTheDocument();
    expect(stopButton).toHaveAttribute("title", "Stop response");
    expect(stopButton).toHaveAttribute("aria-label", "Stop response");
    expect(stopButton.textContent).toBe("");
    expect(screen.queryByRole("button", { name: "Send message" })).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: "Follow up question" } });
    expect(screen.queryByRole("button", { name: "Send message" })).not.toBeInTheDocument();

    const streamCallbacks = queryDocumentStreamMock.mock.calls[0]?.[2] as StreamCallbacks | undefined;
    expect(streamCallbacks).toBeDefined();
    streamCallbacks?.onDone({ message_id: 100 });
    releaseStreamRef.current?.();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();
    });
    expect(screen.queryByRole("button", { name: "Stop response" })).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: "Question after done" } });
    expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();
  });

  it("submits on Enter, keeps Shift+Enter as newline path, and ignores IME enter", async () => {
    queryDocumentStreamMock.mockResolvedValue(undefined);

    render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
    await waitFor(() => {
      expect(screen.queryByText("Loading conversation...")).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Ask a question about this document...");
    fireEvent.change(input, { target: { value: "Line one" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1));
    expect(queryDocumentStreamMock.mock.calls[0]?.[1]).toBe("Line one");

    fireEvent.change(input, { target: { value: "Line one\nLine two" } });
    const shiftEnterEvent = createEvent.keyDown(input, { key: "Enter", shiftKey: true });
    fireEvent(input, shiftEnterEvent);
    expect(shiftEnterEvent.defaultPrevented).toBe(false);
    expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1);

    fireEvent.change(input, { target: { value: "Composing text" } });
    const imeEnterEvent = createEvent.keyDown(input, { key: "Enter", isComposing: true });
    fireEvent(input, imeEnterEvent);
    expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1);
  });

  it("auto-resizes composer textarea up to max height and downscales when text is removed", async () => {
    render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
    await waitFor(() => {
      expect(screen.queryByText("Loading conversation...")).not.toBeInTheDocument();
    });

    const composer = screen.getByPlaceholderText("Ask a question about this document...");

    setComposerScrollHeight(composer as HTMLTextAreaElement, 72);
    fireEvent.change(composer, { target: { value: "Short text." } });
    await waitFor(() => {
      expect((composer as HTMLTextAreaElement).style.height).toBe("72px");
    });
    expect((composer as HTMLTextAreaElement).style.overflowY).toBe("hidden");
    expect((composer as HTMLTextAreaElement).style.height).not.toBe("144px");

    setComposerScrollHeight(composer as HTMLTextAreaElement, 220);
    fireEvent.change(composer, { target: { value: "A\nB\nC\nD\nE\nF\nG\nH\nI\nJ\nK\nL\nM" } });
    await waitFor(() => {
      expect((composer as HTMLTextAreaElement).style.height).toBe("144px");
    });
    expect((composer as HTMLTextAreaElement).style.overflowY).toBe("auto");

    setComposerScrollHeight(composer as HTMLTextAreaElement, 90);
    fireEvent.change(composer, { target: { value: "Back to short." } });
    await waitFor(() => {
      expect((composer as HTMLTextAreaElement).style.height).toBe("90px");
    });
    expect((composer as HTMLTextAreaElement).style.overflowY).toBe("hidden");
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
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => {
      expect(screen.getByText("Error: Stream failed")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(container.querySelectorAll("div.rounded-2xl")).toHaveLength(2);
  });

  it("scrolls to bottom once after history load, then auto-scrolls on new messages", async () => {
    const setScrollTopSpy = vi.fn();
    const originalScrollTopDescriptor = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "scrollTop"
    );
    let mockedScrollTop = 0;
    Object.defineProperty(HTMLElement.prototype, "scrollTop", {
      configurable: true,
      get: () => mockedScrollTop,
      set: (value: number) => {
        mockedScrollTop = value;
        setScrollTopSpy(value);
      },
    });

    getMessagesMock.mockResolvedValueOnce({
      messages: [
        {
          id: 101,
          document_id: documentFixture.id,
          user_id: documentFixture.user_id,
          role: "assistant",
          content: "History answer",
          created_at: "2026-03-02T12:06:00Z",
        },
      ],
      total: 1,
    });

    queryDocumentStreamMock.mockImplementation(async (_documentId, _query, callbacks) => {
      await Promise.resolve();
      callbacks.onDone({ message_id: 200 });
    });

    try {
      render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
      await screen.findByText("History answer");

      expect(setScrollTopSpy).toHaveBeenCalledTimes(1);

      const composer = screen.getByPlaceholderText("Ask a question about this document...");
      fireEvent.change(composer, { target: { value: "Next question" } });
      fireEvent.click(screen.getByRole("button", { name: "Send message" }));
      await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1));

      expect(setScrollTopSpy.mock.calls.length).toBeGreaterThan(1);
    } finally {
      if (originalScrollTopDescriptor) {
        Object.defineProperty(HTMLElement.prototype, "scrollTop", originalScrollTopDescriptor);
      } else {
        delete (HTMLElement.prototype as unknown as Record<string, unknown>)["scrollTop"];
      }
    }
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
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

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
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1));
    expect(capturedSignal).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Stop response" }));

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
    expect(screen.queryByRole("button", { name: "Stop response" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send message" })).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

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

  it("keeps workspace citation cards clickable when source document is present", async () => {
    getWorkspaceMessagesMock.mockResolvedValueOnce({
      messages: [
        {
          id: 12,
          workspace_id: 22,
          user_id: documentFixture.user_id,
          role: "assistant",
          content: "This answer cites a workspace source.",
          sources: [
            {
              chunk_id: 55,
              content: "Workspace source content.",
              similarity: 0.94,
              chunk_index: 1,
              page_start: 2,
              document_id: 99,
              document_filename: "timeline.pdf",
            },
          ],
          created_at: "2026-03-02T12:03:00Z",
        },
      ],
      total: 1,
    });

    const onCitationClick = vi.fn();
    render(
      <ChatWindow
        workspaceId={22}
        workspaceName="Roadmap"
        workspaceDocumentIds={[99]}
        onBack={vi.fn()}
        onCitationClick={onCitationClick}
      />
    );

    await screen.findByText("This answer cites a workspace source.");
    fireEvent.click(screen.getByRole("button", { name: "Sources (1)" }));

    const pageLabel = await screen.findByText("Page 2");
    fireEvent.click(pageLabel);

    expect(pageLabel.closest("div[role='button']")).not.toBeNull();
    expect(onCitationClick).toHaveBeenCalledWith({
      page: 2,
      snippet: "Workspace source content.",
      documentId: 99,
    });
  });

  it("disables workspace citation cards when source document is absent", async () => {
    getWorkspaceMessagesMock.mockResolvedValueOnce({
      messages: [
        {
          id: 13,
          workspace_id: 22,
          user_id: documentFixture.user_id,
          role: "assistant",
          content: "This answer cites a removed workspace source.",
          sources: [
            {
              chunk_id: 56,
              content: "Source no longer in workspace.",
              similarity: 0.91,
              chunk_index: 1,
              page_start: 4,
              document_id: 77,
              document_filename: "removed.pdf",
            },
          ],
          created_at: "2026-03-02T12:04:00Z",
        },
      ],
      total: 1,
    });

    const onCitationClick = vi.fn();
    render(
      <ChatWindow
        workspaceId={22}
        workspaceName="Roadmap"
        workspaceDocumentIds={[99]}
        onBack={vi.fn()}
        onCitationClick={onCitationClick}
      />
    );

    await screen.findByText("This answer cites a removed workspace source.");
    fireEvent.click(screen.getByRole("button", { name: "Sources (1)" }));

    const pageLabel = await screen.findByText("Page 4");
    fireEvent.click(pageLabel);

    expect(pageLabel.closest("div[role='button']")).toBeNull();
    expect(pageLabel.closest("div[aria-disabled='true']")).not.toBeNull();
    expect(onCitationClick).not.toHaveBeenCalled();
  });

  it("auto-scrolls expanded sources into view and caps source list height", async () => {
    const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;
    const scrollIntoViewSpy = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoViewSpy,
    });

    try {
      getMessagesMock.mockResolvedValueOnce({
        messages: [
          {
            id: 14,
            document_id: documentFixture.id,
            user_id: documentFixture.user_id,
            role: "assistant",
            content: "Source-heavy answer.",
            sources: [
              {
                chunk_id: 60,
                content:
                  "This source is long enough to ensure it renders inside the expanded source list container.",
                similarity: 0.88,
                chunk_index: 3,
                page_start: 5,
                page_end: 5,
                document_id: 7,
                document_filename: "guide.pdf",
              },
            ],
            created_at: "2026-03-02T12:05:00Z",
          },
        ],
        total: 1,
      });

      const { container } = render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
      await screen.findByText("Source-heavy answer.");

      fireEvent.click(screen.getByRole("button", { name: "Sources (1)" }));

      const sourcesContainer = container.querySelector("[data-sources='0']");
      expect(sourcesContainer).not.toBeNull();
      expect(sourcesContainer?.className).toContain("max-h-[40vh]");
      expect(sourcesContainer?.className).toContain("overflow-y-auto");

      await waitFor(() => {
        expect(scrollIntoViewSpy).toHaveBeenCalled();
      });
    } finally {
      Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
        configurable: true,
        value: originalScrollIntoView,
      });
    }
  });

  it("shows pipeline metadata/similarity only when debug mode prop is enabled", async () => {
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

    const { rerender } = render(
      <ChatWindow
        document={documentFixture}
        debugMode={false}
        onBack={vi.fn()}
      />
    );
    await screen.findByText("Debuggable answer.");

    fireEvent.click(screen.getByRole("button", { name: "Sources (1)" }));
    expect(screen.queryByText("91.0%")).not.toBeInTheDocument();
    expect(screen.queryByText(/confidence/)).not.toBeInTheDocument();

    rerender(
      <ChatWindow
        document={documentFixture}
        debugMode
        onBack={vi.fn()}
      />
    );

    expect(screen.getByText(/confidence/)).toBeInTheDocument();
    expect(screen.getByText("91.0%")).toBeInTheDocument();
  });

  it("renders inline boundary fallback and reload control when message rendering throws", async () => {
    const reloadSpy = vi.fn();
    vi.stubGlobal("location", {
      ...(window.location as Location),
      reload: reloadSpy,
    });
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const useChatStateSpy = vi.spyOn(useChatStateModule, "useChatState").mockReturnValue({
      messages: [
        {
          id: 999,
          role: "assistant",
          user_id: documentFixture.user_id,
          created_at: "2026-03-02T12:20:00Z",
          get content(): string {
            throw new Error("message render failure");
          },
        } as { id: number; role: "assistant" | "user"; user_id: number; created_at: string; content: string },
      ],
      loadingHistory: false,
      isStreaming: false,
      canStopStream: false,
      submitQuery: vi.fn(),
      stopActiveStream: vi.fn(),
    } as ReturnType<typeof useChatStateModule.useChatState>);

    render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(
      screen.getByText("An unexpected error occurred. Reload the page to continue.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    expect(reloadSpy).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalled();

    useChatStateSpy.mockRestore();
    vi.unstubAllGlobals();
    consoleErrorSpy.mockRestore();
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
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(queryDocumentStreamMock).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(queryWorkspaceMock).toHaveBeenCalledWith(22, "How do these files connect?");
      expect(screen.getByText("They share the same timeline.")).toBeInTheDocument();
    });
  });
});
