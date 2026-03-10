import { requestJsonWithAuth, requestResponseWithAuth } from "@/lib/api/http";
import { ApiError } from "@/lib/api.types";
import type {
  MessageListResponse,
  PipelineMeta,
  QueryResponse,
  WorkspaceQueryResponse,
} from "@/lib/api.types";

interface QueryStreamCallbacks {
  onSources: (sources: QueryResponse["sources"]) => void;
  onToken: (token: string) => void;
  onMeta: (meta: PipelineMeta) => void;
  onDone: (data: { message_id: number }) => void;
  onError: (detail: string) => void;
}

interface QueryStreamOptions {
  signal?: AbortSignal;
}

export const chatService = {
  getMessages: async (documentId: number): Promise<MessageListResponse> => {
    return requestJsonWithAuth<MessageListResponse>(
      `/api/documents/${documentId}/messages`
    );
  },

  getWorkspaceMessages: async (workspaceId: number): Promise<MessageListResponse> => {
    return requestJsonWithAuth<MessageListResponse>(
      `/api/workspaces/${workspaceId}/messages`
    );
  },

  queryDocument: async (documentId: number, query: string): Promise<QueryResponse> => {
    return requestJsonWithAuth<QueryResponse>(`/api/documents/${documentId}/query`, {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  },

  queryWorkspace: async (workspaceId: number, query: string): Promise<WorkspaceQueryResponse> => {
    return requestJsonWithAuth<WorkspaceQueryResponse>(`/api/workspaces/${workspaceId}/query`, {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  },

  queryDocumentStream: async (
    documentId: number,
    query: string,
    callbacks: QueryStreamCallbacks,
    options: QueryStreamOptions = {}
  ): Promise<void> => {
    const response = await requestResponseWithAuth(
      `/api/documents/${documentId}/query/stream`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
        signal: options.signal,
      }
    );

    if (!response.body) {
      throw new ApiError(500, "Streaming response unavailable");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamTerminated = false;

    const emitDone = (data: { message_id: number }) => {
      if (streamTerminated) return;
      streamTerminated = true;
      callbacks.onDone(data);
    };

    const emitError = (detail: string) => {
      if (streamTerminated) return;
      streamTerminated = true;
      callbacks.onError(detail);
    };

    const parseFrame = (frame: string) => {
      const lines = frame.split("\n");
      let event = "";
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith("event:")) {
          event = line.slice("event:".length).trim();
        } else if (line.startsWith("data:")) {
          const rawValue = line.slice("data:".length);
          dataLines.push(rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue);
        }
      }

      if (!event || dataLines.length === 0) return;

      const data = dataLines.join("\n");

      try {
        if (event === "sources") {
          callbacks.onSources(JSON.parse(data) as QueryResponse["sources"]);
          return;
        }
        if (event === "token") {
          callbacks.onToken(data);
          return;
        }
        if (event === "meta") {
          callbacks.onMeta(JSON.parse(data) as PipelineMeta);
          return;
        }
        if (event === "done") {
          emitDone(JSON.parse(data) as { message_id: number });
          return;
        }
        if (event === "error") {
          const parsed = JSON.parse(data) as { detail?: string };
          emitError(parsed.detail || "Query failed");
        }
      } catch {
        emitError("Failed to parse streaming event");
      }
    };

    const flushFrames = () => {
      let frameBoundary = buffer.indexOf("\n\n");
      while (frameBoundary !== -1) {
        const frame = buffer.slice(0, frameBoundary);
        buffer = buffer.slice(frameBoundary + 2);
        if (frame.trim()) {
          parseFrame(frame);
        }
        frameBoundary = buffer.indexOf("\n\n");
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replaceAll("\r\n", "\n");
        flushFrames();
      }

      buffer += decoder.decode().replaceAll("\r\n", "\n");
      flushFrames();
      if (buffer.trim()) {
        parseFrame(buffer);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw err;
      }
      emitError("Stream connection failed");
    } finally {
      reader.releaseLock();
    }

    if (!streamTerminated && !options.signal?.aborted) {
      emitError("Stream ended unexpectedly");
    }
  },
};
