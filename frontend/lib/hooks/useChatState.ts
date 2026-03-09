import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, SessionExpiredError, type Document, type PipelineMeta, type QueryResponse } from "@/lib/api";
import { chatService } from "@/lib/services/chatService";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: QueryResponse["sources"];
  pipeline_meta?: PipelineMeta;
  streaming?: boolean;
  retry_query?: string;
}

interface QueryStreamCallbacks {
  onSources: (sources: QueryResponse["sources"]) => void;
  onToken: (token: string) => void;
  onMeta: (meta: PipelineMeta) => void;
  onDone: (data: { message_id: number }) => void;
  onError: (detail: string) => void;
}

interface UseChatStateOptions {
  document: Document;
  onSessionExpired?: () => void;
}

export interface UseChatStateResult {
  messages: ChatMessage[];
  loadingHistory: boolean;
  isStreaming: boolean;
  submitQuery: (query: string) => Promise<void>;
  stopActiveStream: () => void;
}

const isAbortError = (err: unknown): boolean => {
  return (
    (err instanceof DOMException && err.name === "AbortError")
    || (typeof err === "object" && err !== null && "name" in err && err.name === "AbortError")
  );
};

export function useChatState({
  document,
  onSessionExpired,
}: UseChatStateOptions): UseChatStateResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const activeStreamAbortRef = useRef<AbortController | null>(null);
  const streamInFlightRef = useRef(false);
  const isMountedRef = useRef(true);
  const isStreaming = messages.some((message) => message.role === "assistant" && message.streaming);

  const handleSessionExpired = useCallback(() => {
    onSessionExpired?.();
  }, [onSessionExpired]);

  const updateStreamingAssistant = useCallback((updater: (message: ChatMessage) => ChatMessage) => {
    setMessages((prev) => {
      const streamingIndex = prev.findIndex(
        (message) => message.role === "assistant" && message.streaming
      );
      if (streamingIndex === -1) return prev;

      const next = [...prev];
      next[streamingIndex] = updater(next[streamingIndex]);
      return next;
    });
  }, []);

  const appendStreamError = useCallback((errorMessage: string, retryQuery: string) => {
    setMessages((prev) => {
      const streamingIndex = prev.findIndex(
        (message) => message.role === "assistant" && message.streaming
      );
      if (streamingIndex === -1) {
        return [...prev, { role: "assistant", content: errorMessage, retry_query: retryQuery }];
      }

      const next = [...prev];
      const current = next[streamingIndex];
      next[streamingIndex] = {
        ...current,
        content: current.content ? `${current.content}\n\n${errorMessage}` : errorMessage,
        streaming: false,
        retry_query: retryQuery,
      };
      return next;
    });
  }, []);

  const markStreamStopped = useCallback((retryQuery: string) => {
    updateStreamingAssistant((message) => ({
      ...message,
      content: message.content
        ? `${message.content}\n\nStopped. You can retry this response.`
        : "Stopped. You can retry this response.",
      streaming: false,
      retry_query: retryQuery,
    }));
  }, [updateStreamingAssistant]);

  const stopActiveStream = useCallback(() => {
    activeStreamAbortRef.current?.abort();
  }, []);

  const submitQuery = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed || streamInFlightRef.current) return;

    streamInFlightRef.current = true;
    const streamController = new AbortController();
    activeStreamAbortRef.current?.abort();
    activeStreamAbortRef.current = streamController;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: trimmed },
      { role: "assistant", content: "", streaming: true },
    ]);

    const callbacks: QueryStreamCallbacks = {
      onSources: (sources) => {
        if (!isMountedRef.current || streamController.signal.aborted) return;
        updateStreamingAssistant((message) => ({
          ...message,
          sources,
        }));
      },
      onToken: (token) => {
        if (!isMountedRef.current || streamController.signal.aborted) return;
        updateStreamingAssistant((message) => ({
          ...message,
          content: `${message.content}${token}`,
        }));
      },
      onMeta: (pipelineMeta) => {
        if (!isMountedRef.current || streamController.signal.aborted) return;
        updateStreamingAssistant((message) => ({
          ...message,
          pipeline_meta: pipelineMeta,
        }));
      },
      onDone: () => {
        if (!isMountedRef.current || streamController.signal.aborted) return;
        updateStreamingAssistant((message) => ({
          ...message,
          streaming: false,
        }));
        activeStreamAbortRef.current = null;
        streamInFlightRef.current = false;
      },
      onError: (detail) => {
        if (!isMountedRef.current || streamController.signal.aborted) return;
        appendStreamError(`Error: ${detail}`, trimmed);
        activeStreamAbortRef.current = null;
        streamInFlightRef.current = false;
      },
    };

    try {
      await chatService.queryDocumentStream(document.id, trimmed, callbacks, {
        signal: streamController.signal,
      });
    } catch (err) {
      if (isAbortError(err)) {
        if (isMountedRef.current) {
          markStreamStopped(trimmed);
        }
        streamInFlightRef.current = false;
        return;
      }

      let errorMessage = "Error: Failed to get answer. Please try again.";

      if (err instanceof ApiError) {
        if (err.status === 400) {
          errorMessage =
            "This document hasn't been processed yet. Please process it first before asking questions.";
        } else if (err.status === 404) {
          errorMessage = "Document not found.";
        } else if (err instanceof SessionExpiredError) {
          handleSessionExpired();
          return;
        } else if (err.status === 401) {
          errorMessage = "Your session has expired. Please log in again.";
        } else {
          errorMessage = `Error: ${err.detail}`;
        }
      }

      appendStreamError(errorMessage, trimmed);
    } finally {
      if (activeStreamAbortRef.current === streamController) {
        activeStreamAbortRef.current = null;
      }
      streamInFlightRef.current = false;
    }
  }, [appendStreamError, document.id, handleSessionExpired, markStreamStopped, updateStreamingAssistant]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      activeStreamAbortRef.current?.abort();
      streamInFlightRef.current = false;
    };
  }, []);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        setLoadingHistory(true);
        const response = await chatService.getMessages(document.id);

        const loadedMessages: ChatMessage[] = response.messages.map((msg) => ({
          role: msg.role,
          content: msg.content,
          sources: msg.sources,
          pipeline_meta: msg.pipeline_meta,
        }));
        setMessages(loadedMessages);
      } catch (err) {
        if (err instanceof SessionExpiredError) {
          handleSessionExpired();
          return;
        }
        console.error("Failed to load message history:", err);
      } finally {
        setLoadingHistory(false);
      }
    };

    void loadHistory();
  }, [document.id, handleSessionExpired]);

  return {
    messages,
    loadingHistory,
    isStreaming,
    submitQuery,
    stopActiveStream,
  };
}
