import { afterEach, describe, expect, it, vi } from "vitest";
import { chatService } from "@/lib/services/chatService";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeStreamingResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("chatService", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("loads document messages", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(200, { messages: [], total: 0 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await chatService.getMessages(42);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/documents/42/messages",
      expect.objectContaining({ credentials: "include" })
    );
    expect(result).toEqual({ messages: [], total: 0 });
  });

  it("submits a non-streaming query", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse(200, {
        query: "What is this?",
        answer: "Answer text",
        sources: [],
        pipeline_meta: undefined,
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await chatService.queryDocument(42, "What is this?");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/documents/42/query",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ query: "What is this?" }),
      })
    );
    expect(result.answer).toBe("Answer text");
  });

  it("streams query events using provided callbacks", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      makeStreamingResponse([
        "event: sources\ndata: []\n\n",
        "event: token\ndata: hello\n\n",
        "event: done\ndata: {\"message_id\":5}\n\n",
      ])
    );
    vi.stubGlobal("fetch", fetchMock);

    const callbacks = {
      onSources: vi.fn(),
      onToken: vi.fn(),
      onMeta: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };

    await chatService.queryDocumentStream(42, "stream question", callbacks);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/documents/42/query/stream",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ query: "stream question" }),
        credentials: "include",
      })
    );
    expect(callbacks.onSources).toHaveBeenCalledWith([]);
    expect(callbacks.onToken).toHaveBeenCalledWith("hello");
    expect(callbacks.onDone).toHaveBeenCalledWith({ message_id: 5 });
    expect(callbacks.onError).not.toHaveBeenCalled();
  });
});
