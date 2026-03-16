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

  it("supports stream stop + retry callback behavior", async () => {
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

    await waitFor(() => {
      expect(hook.result.current.loadingHistory).toBe(false);
    });

    await act(async () => {
      const firstSubmit = hook.result.current.submitQuery("Original question");
      hook.result.current.stopActiveStream();
      capturedCallbacks?.onToken("should be ignored after stop");
      await firstSubmit;
      await hook.result.current.submitQuery("Original question");
    });

    await waitFor(() => {
      expect(queryDocumentStreamMock).toHaveBeenCalledTimes(2);
    });

    expect(queryDocumentStreamMock.mock.calls[0]?.[1]).toBe("Original question");
    expect(queryDocumentStreamMock.mock.calls[1]?.[1]).toBe("Original question");
    expect(hook.result.current.messages.some((message) => message.content.includes("Recovered"))).toBe(
      true
    );
    expect(hook.result.current.messages.at(-1)?.retry_query).toBeUndefined();
    expect(capturedSignal?.aborted).toBe(true);
  });
});
