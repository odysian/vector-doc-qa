import { afterEach, describe, expect, it, vi } from "vitest";
import { api, SessionExpiredError } from "@/lib/api";
import type { PipelineMeta, QueryResponse } from "@/lib/api";

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

describe("api.queryDocumentStream", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("assembles multi-chunk SSE frames and dispatches events in order", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      makeStreamingResponse([
        "event: sources\ndata: [{\"chunk_id\":1,",
        "\"content\":\"Source\",\"similarity\":0.91,\"chunk_index\":0}]\n\n",
        "event: token\ndata: Hel",
        "lo\n\n",
        "event: meta\ndata: {\"embed_ms\":12,\"retrieval_ms\":8,",
        "\"llm_ms\":40,\"total_ms\":60,\"top_similarity\":0.91,\"avg_similarity\":0.88,\"chunks_retrieved\":1,",
        "\"chunks_above_threshold\":1,\"similarity_spread\":0,\"chat_history_turns_included\":2}\n\n",
        "event: done\ndata: {\"message_id\":77}\n\n",
      ])
    );
    vi.stubGlobal("fetch", fetchMock);
    localStorage.setItem("csrf_token", "csrf-test-token");

    const eventOrder: string[] = [];
    const tokens: string[] = [];
    const sources: QueryResponse["sources"][] = [];
    const metas: PipelineMeta[] = [];
    const donePayloads: Array<{ message_id: number }> = [];
    const errors: string[] = [];

    await api.queryDocumentStream(42, "What is this?", {
      onSources: (data) => {
        eventOrder.push("sources");
        sources.push(data);
      },
      onToken: (token) => {
        eventOrder.push("token");
        tokens.push(token);
      },
      onMeta: (meta) => {
        eventOrder.push("meta");
        metas.push(meta);
      },
      onDone: (data) => {
        eventOrder.push("done");
        donePayloads.push(data);
      },
      onError: (detail) => {
        errors.push(detail);
      },
    });

    expect(eventOrder).toEqual(["sources", "token", "meta", "done"]);
    expect(tokens).toEqual(["Hello"]);
    expect(sources).toEqual([
      [{ chunk_id: 1, content: "Source", similarity: 0.91, chunk_index: 0 }],
    ]);
    expect(metas).toEqual([
      {
        embed_ms: 12,
        retrieval_ms: 8,
        llm_ms: 40,
        total_ms: 60,
        top_similarity: 0.91,
        avg_similarity: 0.88,
        chunks_retrieved: 1,
        chunks_above_threshold: 1,
        similarity_spread: 0,
        chat_history_turns_included: 2,
      },
    ]);
    expect(donePayloads).toEqual([{ message_id: 77 }]);
    expect(errors).toEqual([]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("emits terminal fallback when stream closes without done or error", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      makeStreamingResponse([
        "event: sources\ndata: []\n\n",
        "event: token\ndata: partial answer\n\n",
      ])
    );
    vi.stubGlobal("fetch", fetchMock);

    const onDone = vi.fn();
    const onError = vi.fn();

    await api.queryDocumentStream(99, "incomplete stream", {
      onSources: vi.fn(),
      onToken: vi.fn(),
      onMeta: vi.fn(),
      onDone,
      onError,
    });

    expect(onDone).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith("Stream ended unexpectedly");
  });

  it("throws SessionExpiredError when stream auth refresh fails", async () => {
    localStorage.setItem("csrf_token", "csrf-old");
    localStorage.setItem("access_token", "legacy-access");
    localStorage.setItem("refresh_token", "legacy-refresh");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Unauthorized" }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Refresh failed" }), { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      api.queryDocumentStream(42, "question", {
        onSources: vi.fn(),
        onToken: vi.fn(),
        onMeta: vi.fn(),
        onDone: vi.fn(),
        onError: vi.fn(),
      })
    ).rejects.toBeInstanceOf(SessionExpiredError);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(localStorage.getItem("csrf_token")).toBeNull();
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });
});
