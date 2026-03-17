import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Document, PipelineMeta, QueryResponse } from "@/lib/api";
import { useChatState } from "@/lib/hooks/useChatState";
import { chatService } from "@/lib/services/chatService";
import { SessionExpiredError } from "@/lib/api";

vi.mock("@/lib/services/chatService", async () => {
  const actual = await vi.importActual<typeof import("@/lib/services/chatService")>(
    "@/lib/services/chatService"
  );
  return {
    ...actual,
    chatService: {
      ...actual.chatService,
      getMessages: vi.fn(),
      queryDocumentStream: vi.fn(),
    },
  };
});

const getMessagesMock = vi.mocked(chatService.getMessages);
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

function setupHookHarness(onSessionExpired = vi.fn()) {
  const hook = renderHook(() => useChatState({ document: documentFixture, onSessionExpired }));
  return { hook, onSessionExpired };
}

describe("useChatState", () => {
  beforeEach(() => {
    getMessagesMock.mockResolvedValue({ messages: [], total: 0 });
    queryDocumentStreamMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("loads history into state on mount", async () => {
    getMessagesMock.mockResolvedValueOnce({
      messages: [
        {
          id: 11,
          document_id: documentFixture.id,
          user_id: documentFixture.user_id,
          role: "assistant",
          content: "History answer",
          created_at: "2026-03-02T12:03:00Z",
        },
      ],
      total: 1,
    });

    const { hook } = setupHookHarness();

    await waitFor(() => {
      expect(hook.result.current.loadingHistory).toBe(false);
    });

    expect(hook.result.current.messages).toEqual([
      {
        role: "assistant",
        content: "History answer",
        created_at: "2026-03-02T12:03:00Z",
      },
    ]);
  });

  it("redirects when history load is rejected as session expired", async () => {
    const onSessionExpired = vi.fn();
    getMessagesMock.mockRejectedValueOnce(new SessionExpiredError());

    setupHookHarness(onSessionExpired);

    await waitFor(() => {
      expect(onSessionExpired).toHaveBeenCalledTimes(1);
    });
  });

  it("redirects when query stream fails with session expired", async () => {
    const onSessionExpired = vi.fn();
    queryDocumentStreamMock.mockRejectedValueOnce(new SessionExpiredError("Session expired"));

    const { hook } = setupHookHarness(onSessionExpired);
    await waitFor(() => {
      expect(hook.result.current.loadingHistory).toBe(false);
    });

    await act(async () => {
      await hook.result.current.submitQuery("What does it say?");
    });

    await waitFor(() => {
      expect(onSessionExpired).toHaveBeenCalledTimes(1);
      expect(queryDocumentStreamMock).toHaveBeenCalledTimes(1);
    });
  });

  it("drains tokens at 35ms intervals before finalising the message", async () => {
    vi.useFakeTimers();

    let capturedCallbacks: StreamCallbacks | undefined;
    queryDocumentStreamMock.mockImplementationOnce(async (_documentId, _query, callbacks) => {
      capturedCallbacks = callbacks as StreamCallbacks;
      // Simulate SSE: emit tokens then done synchronously so the mock resolves.
      callbacks.onToken("Hello");
      callbacks.onToken(" world");
      callbacks.onDone({ message_id: 1 });
    });

    const { hook } = setupHookHarness();

    await act(async () => {
      await vi.runAllTimersAsync(); // flush history load
    });

    await act(async () => {
      void hook.result.current.submitQuery("What?");
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(capturedCallbacks).toBeDefined();

    // Tokens should not have rendered yet — they are queued.
    const assistantAfterCallbacks = hook.result.current.messages.find(
      (m) => m.role === "assistant" && m.streaming
    );
    expect(assistantAfterCallbacks?.content).toBe("");

    // Advance one tick: first token renders.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(35);
    });
    const afterFirstTick = hook.result.current.messages.find((m) => m.role === "assistant");
    expect(afterFirstTick?.content).toBe("Hello");
    expect(afterFirstTick?.streaming).toBe(true);

    // Advance second tick: second token renders.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(35);
    });
    const afterSecondTick = hook.result.current.messages.find((m) => m.role === "assistant");
    expect(afterSecondTick?.content).toBe("Hello world");
    expect(afterSecondTick?.streaming).toBe(true);

    // Advance third tick: queue empty + done → message finalised.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(35);
    });
    const finalMessage = hook.result.current.messages.find((m) => m.role === "assistant");
    expect(finalMessage?.content).toBe("Hello world");
    expect(finalMessage?.streaming).toBe(false);
    expect(hook.result.current.isStreaming).toBe(false);
  });

  it("streaming cursor stays visible until queue is drained, not just until done event", async () => {
    vi.useFakeTimers();

    queryDocumentStreamMock.mockImplementationOnce(async (_documentId, _query, callbacks) => {
      callbacks.onToken("token1");
      callbacks.onToken("token2");
      callbacks.onDone({ message_id: 2 });
    });

    const { hook } = setupHookHarness();
    await act(async () => { await vi.runAllTimersAsync(); });

    await act(async () => {
      void hook.result.current.submitQuery("Q");
      await vi.advanceTimersByTimeAsync(0);
    });

    // Done event arrived but queue not yet drained — still streaming.
    expect(hook.result.current.isStreaming).toBe(true);

    // Drain all queued tokens.
    await act(async () => { await vi.advanceTimersByTimeAsync(35 * 3); });

    expect(hook.result.current.isStreaming).toBe(false);
  });

  it("stop/abort discards the queue so no tokens render after stop", async () => {
    vi.useFakeTimers();

    let capturedCallbacks: StreamCallbacks | undefined;
    let capturedSignal: AbortSignal | undefined;

    queryDocumentStreamMock.mockImplementationOnce(async (_documentId, _query, callbacks, options) => {
      capturedCallbacks = callbacks as StreamCallbacks;
      capturedSignal = options?.signal;
      await new Promise<void>((resolve, reject) => {
        capturedSignal?.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        }, { once: true });
      });
    });

    const { hook } = setupHookHarness();
    await act(async () => { await vi.runAllTimersAsync(); });

    await act(async () => {
      void hook.result.current.submitQuery("Q");
      await vi.advanceTimersByTimeAsync(0);
    });

    // Push tokens into the queue before stopping.
    await act(async () => {
      capturedCallbacks?.onToken("should-not-render");
    });

    // Stop — this should clear the queue.
    await act(async () => {
      hook.result.current.stopActiveStream();
      await vi.runAllTimersAsync();
    });

    const assistantMsg = hook.result.current.messages.find((m) => m.role === "assistant");
    expect(assistantMsg?.content).not.toContain("should-not-render");
    expect(capturedSignal?.aborted).toBe(true);
  });

  it("supports stream stop + retry callback behavior", async () => {
    vi.useFakeTimers();

    let capturedCallbacks: StreamCallbacks | undefined;
    let capturedSignal: AbortSignal | undefined;

    queryDocumentStreamMock.mockImplementationOnce(async (_documentId, _query, callbacks, options) => {
      capturedCallbacks = callbacks as StreamCallbacks;
      capturedSignal = options?.signal;
      await new Promise<void>((resolve, reject) => {
        if (!capturedSignal) {
          resolve();
          return;
        }

        capturedSignal.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        }, { once: true });
      });
    });

    queryDocumentStreamMock.mockImplementationOnce(async (_documentId, _query, callbacks) => {
      await Promise.resolve();
      callbacks.onToken("Recovered");
      callbacks.onDone({ message_id: 301 });
    });

    const { hook } = setupHookHarness();

    await act(async () => { await vi.runAllTimersAsync(); });

    // Phase 1: start first stream and abort it.
    await act(async () => {
      const firstSubmit = hook.result.current.submitQuery("Original question");
      hook.result.current.stopActiveStream();
      capturedCallbacks?.onToken("should be ignored after stop");
      await firstSubmit;
    });

    // Phase 2: submit retry — void to avoid awaiting while drain interval is pending.
    await act(async () => {
      void hook.result.current.submitQuery("Original question");
      // Flush microtasks so the mock fires its callbacks before we advance timers.
      await vi.advanceTimersByTimeAsync(0);
    });

    // Drain the second stream's queued token and let the message finalise.
    await act(async () => { await vi.advanceTimersByTimeAsync(35 * 3); });

    expect(queryDocumentStreamMock).toHaveBeenCalledTimes(2);
    expect(queryDocumentStreamMock.mock.calls[0]?.[1]).toBe("Original question");
    expect(queryDocumentStreamMock.mock.calls[1]?.[1]).toBe("Original question");
    expect(hook.result.current.messages.some((message) => message.content.includes("Recovered"))).toBe(
      true
    );
    expect(hook.result.current.messages.at(-1)?.retry_query).toBeUndefined();
    expect(capturedSignal?.aborted).toBe(true);
  });
});
