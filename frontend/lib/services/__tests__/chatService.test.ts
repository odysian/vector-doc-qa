import { beforeEach, describe, expect, it, vi } from "vitest";
import { chatService } from "@/lib/services/chatService";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getMessages: vi.fn(),
      queryDocument: vi.fn(),
      queryDocumentStream: vi.fn(),
    },
  };
});

const getMessagesMock = vi.mocked(api.getMessages);
const queryDocumentMock = vi.mocked(api.queryDocument);
const queryDocumentStreamMock = vi.mocked(api.queryDocumentStream);

describe("chatService", () => {
  beforeEach(() => {
    getMessagesMock.mockReset();
    queryDocumentMock.mockReset();
    queryDocumentStreamMock.mockReset();
  });

  it("loads document messages", async () => {
    getMessagesMock.mockResolvedValueOnce({ messages: [], total: 0 });

    const result = await chatService.getMessages(42);

    expect(getMessagesMock).toHaveBeenCalledWith(42);
    expect(result).toEqual({ messages: [], total: 0 });
  });

  it("submits a non-streaming query", async () => {
    queryDocumentMock.mockResolvedValueOnce({
      query: "What is this?",
      answer: "Answer text",
      sources: [],
      pipeline_meta: undefined,
    });

    const result = await chatService.queryDocument(42, "What is this?");

    expect(queryDocumentMock).toHaveBeenCalledWith(42, "What is this?");
    expect(result.answer).toBe("Answer text");
  });

  it("starts streaming query with provided callbacks and options", async () => {
    queryDocumentStreamMock.mockResolvedValueOnce();
    const callbacks = {
      onSources: vi.fn(),
      onToken: vi.fn(),
      onMeta: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    };
    const options = { signal: new AbortController().signal };

    await chatService.queryDocumentStream(42, "stream question", callbacks, options);

    expect(queryDocumentStreamMock).toHaveBeenCalledWith(
      42,
      "stream question",
      callbacks,
      options
    );
  });
});
