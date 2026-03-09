import { api, type QueryResponse } from "@/lib/api";
import type { MessageListResponse, PipelineMeta } from "@/lib/api.types";

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
    return api.getMessages(documentId);
  },

  queryDocument: async (documentId: number, query: string): Promise<QueryResponse> => {
    return api.queryDocument(documentId, query);
  },

  queryDocumentStream: async (
    documentId: number,
    query: string,
    callbacks: QueryStreamCallbacks,
    options: QueryStreamOptions = {}
  ): Promise<void> => {
    await api.queryDocumentStream(documentId, query, callbacks, options);
  },
};
