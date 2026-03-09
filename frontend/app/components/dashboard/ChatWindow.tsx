/**
 * Chat Window: Pop-up window for querying documents using RAG. Displays
 * conversation and context.
 */

"use client";

import { SyntheticEvent, useEffect, useRef, useState } from "react";
import { ArrowLeft, Settings2 } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { Document } from "@/lib/api";
import { useChatState } from "@/lib/hooks/useChatState";

interface CitationTarget {
  page: number;
  snippet?: string;
}

interface ChatWindowProps {
  document: Document;
  onBack: () => void;
  onCitationClick?: (citation: CitationTarget) => void;
  onSessionExpired?: () => void;
}

const SUGGESTED_PROMPTS = [
  "Summarize this document",
  "What are the main points?",
  "Find key dates or numbers",
];
const DEBUG_MODE_STORAGE_KEY = "quaero_debug_mode";
const HIGH_CONFIDENCE_THRESHOLD = 0.60;
const MEDIUM_CONFIDENCE_THRESHOLD = 0.43;

/**
 * Renders the pop up window with query input and message history.
 */
export function ChatWindow({
  document,
  onBack,
  onCitationClick,
  onSessionExpired,
}: ChatWindowProps) {
  const [input, setInput] = useState("");
  const [debugMode, setDebugMode] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(DEBUG_MODE_STORAGE_KEY) === "true";
  });
  const [expandedSourceIndices, setExpandedSourceIndices] = useState<Set<number>>(new Set());
  const [expandedSourceCards, setExpandedSourceCards] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const { messages, loadingHistory, isStreaming, submitQuery, stopActiveStream } = useChatState({
    document,
    onSessionExpired,
  });

  /** Toggle whether the whole "Sources" block for a message is open or collapsed. */
  const toggleSources = (messageIndex: number) => {
    setExpandedSourceIndices((prev) => {
      const next = new Set(prev);
      if (next.has(messageIndex)) next.delete(messageIndex);
      else next.add(messageIndex);
      return next;
    });
  };

  /**
   * Toggle whether one source card shows full text or just the preview.
   * Key is "messageIndex-sourceIndex" so state doesn't clash between messages.
   */
  const toggleSourceCard = (messageIndex: number, sourceIndex: number) => {
    const key = `${messageIndex}-${sourceIndex}`;
    setExpandedSourceCards((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleDebugMode = () => {
    const nextDebugMode = !debugMode;
    setDebugMode(nextDebugMode);
    if (typeof window !== "undefined") {
      localStorage.setItem(DEBUG_MODE_STORAGE_KEY, nextDebugMode ? "true" : "false");
    }
  };

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e: SyntheticEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    setInput("");
    void submitQuery(trimmed);
  };

  const handleRetry = (query: string) => {
    void submitQuery(query);
  };

  const getSourcePageLabel = (pageStart?: number | null, pageEnd?: number | null): string => {
    if (pageStart === null || pageStart === undefined) return "";
    if (pageEnd === null || pageEnd === undefined || pageEnd === pageStart) {
      return `Page ${pageStart}`;
    }
    return `Pages ${pageStart}-${pageEnd}`;
  };

  const getConfidence = (topSimilarity: number): "high" | "medium" | "low" => {
    if (topSimilarity >= HIGH_CONFIDENCE_THRESHOLD) return "high";
    if (topSimilarity >= MEDIUM_CONFIDENCE_THRESHOLD) return "medium";
    return "low";
  };

  return (
    <div className="flex flex-col w-full h-full min-h-0 max-h-full bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden shadow-xl">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-900/50 backdrop-blur">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <button
            type="button"
            onClick={onBack}
            title="Back to Documents"
            className="text-zinc-400 hover:text-white transition-colors cursor-pointer p-1 -m-1 rounded focus:outline-none focus:ring-2 focus:ring-lapis-500 focus:ring-offset-2 focus:ring-offset-zinc-900 shrink-0"
            aria-label="Back to Documents"
          >
            <ArrowLeft size={24} strokeWidth={2} />
          </button>
          <div className="h-4 w-px bg-zinc-700 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1">
            <h2 className="font-medium text-lapis-400 italic truncate text-sm sm:text-base">
              {document.filename}
            </h2>
            <p className="text-meta truncate mt-0.5">
              Uploaded {formatDate(document.uploaded_at)}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={toggleDebugMode}
          aria-pressed={debugMode}
          className={`ml-3 shrink-0 inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-lapis-500 focus:ring-offset-2 focus:ring-offset-zinc-900 ${
            debugMode
              ? "border-lapis-500/60 bg-lapis-500/10 text-lapis-300"
              : "border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-500"
          }`}
        >
          <Settings2 size={14} aria-hidden />
          <span>{debugMode ? "Debug on" : "Debug off"}</span>
        </button>
      </div>

      {/* Messages Area */}
      <div
        ref={scrollRef}
        className="messages-scroll min-h-0 flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth"
      >
        {loadingHistory && (
          <div className="h-full flex items-center justify-center">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-lapis-400 rounded-full animate-bounce" />
              <div
                className="w-2 h-2 bg-lapis-400 rounded-full animate-bounce"
                style={{ animationDelay: "150ms" }}
              />
              <div
                className="w-2 h-2 bg-lapis-400 rounded-full animate-bounce"
                style={{ animationDelay: "300ms" }}
              />
              <span className="ml-2 text-empty">Loading conversation...</span>
            </div>
          </div>
        )}

        {!loadingHistory && messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center space-y-4 px-4">
            <div className="p-4 bg-zinc-800/50 rounded-full">
              <svg
                className="w-8 h-8 text-lapis-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                />
              </svg>
            </div>
            <h3 className="text-body-sm font-medium text-zinc-200 text-center">
              Ask a question about this document
            </h3>
            <p className="text-meta text-center">
              Your questions and answers will appear here.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-2">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => {
                    void submitQuery(prompt);
                  }}
                  disabled={isStreaming}
                  className="px-3 py-2 rounded-lg bg-zinc-800/80 hover:bg-zinc-700/80 border border-zinc-700 text-zinc-300 text-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {!loadingHistory &&
          messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col ${
              msg.role === "user" ? "items-end" : "items-start"
            } ${i < messages.length - 1 ? "pb-6 mb-6 border-b border-zinc-800/60" : ""}`}
          >
            {/* Message Bubble */}
            <div
              className={`max-w-[85%] rounded-2xl p-4 shadow-sm ${
                msg.role === "user"
                  ? "bg-lapis-600 text-white rounded-tr-none"
                  : "bg-zinc-800 text-zinc-100 rounded-tl-none border border-zinc-700"
              }`}
            >
              {msg.role === "assistant" && msg.streaming && !msg.content ? (
                <div className="flex items-center gap-2 text-zinc-400">
                  <div
                    className="w-2 h-2 bg-lapis-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <div
                    className="w-2 h-2 bg-lapis-400 rounded-full animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <div
                    className="w-2 h-2 bg-lapis-400 rounded-full animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-body-sm leading-relaxed">
                  {msg.content}
                </p>
              )}
            </div>

            {debugMode && msg.role === "assistant" && msg.pipeline_meta && (
              <details className="mt-2 ml-2 max-w-[85%] text-xs text-zinc-400 group">
                <summary className="cursor-pointer list-none flex items-center gap-2 hover:text-zinc-200 transition-colors">
                  <svg
                    className="w-3 h-3 shrink-0 transition-transform group-open:rotate-90"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                  <span>
                    {(msg.pipeline_meta.total_ms / 1000).toFixed(1)}s ·{" "}
                    {(msg.pipeline_meta.avg_similarity * 100).toFixed(0)}% retrieval ·{" "}
                    {msg.pipeline_meta.chunks_retrieved} {" "}
                    {msg.pipeline_meta.chunks_retrieved === 1 ? "source" : "sources"} ·{" "}
                    {getConfidence(msg.pipeline_meta.top_similarity)} confidence
                  </span>
                </summary>
                <div className="mt-2 ml-5 space-y-1">
                  <p>Embedding: {msg.pipeline_meta.embed_ms}ms</p>
                  <p>Retrieval: {msg.pipeline_meta.retrieval_ms}ms</p>
                  <p>Generation: {msg.pipeline_meta.llm_ms}ms</p>
                  <p>Top similarity: {(msg.pipeline_meta.top_similarity * 100).toFixed(1)}%</p>
                  <p>Average similarity: {(msg.pipeline_meta.avg_similarity * 100).toFixed(1)}%</p>
                  <p>Chunks above {HIGH_CONFIDENCE_THRESHOLD.toFixed(2)}: {msg.pipeline_meta.chunks_above_threshold}</p>
                  <p>Similarity spread: {(msg.pipeline_meta.similarity_spread * 100).toFixed(1)}%</p>
                  <p>History turns included: {msg.pipeline_meta.chat_history_turns_included}</p>
                  <div className="border-t border-zinc-700/50 pt-1 mt-1">
                    <p>Total: {msg.pipeline_meta.total_ms}ms</p>
                  </div>
                </div>
              </details>
            )}

            {msg.role === "assistant" && msg.retry_query && !msg.streaming && (
              <button
                type="button"
                onClick={() => handleRetry(msg.retry_query!)}
                disabled={isStreaming}
                className="mt-2 ml-2 text-link-sm text-lapis-300 hover:text-lapis-200 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
              >
                Retry
              </button>
            )}

            {/* Citations / Sources (collapsed by default, expand on click) */}
            {msg.sources && msg.sources.length > 0 && (
              <div className="mt-2 ml-2 max-w-[85%] pt-2 border-t border-zinc-700/50">
                <button
                  type="button"
                  onClick={() => toggleSources(i)}
                  className="flex items-center gap-2 text-label-accent hover:text-lapis-300 transition-colors cursor-pointer"
                >
                  <svg
                    className={`w-3 h-3 shrink-0 transition-transform ${expandedSourceIndices.has(i) ? "rotate-90" : ""}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                  <span>Sources ({msg.sources.length})</span>
                </button>
                {expandedSourceIndices.has(i) && (
                  <div className="mt-2 grid gap-2">
                    {msg.sources.map((source, idx) => {
                      const cardKey = `${i}-${idx}`;
                      const isExpanded = expandedSourceCards.has(cardKey);
                      const previewLength = 250;
                      const preview = source.content.substring(0, previewLength).trim();
                      const remainder = source.content.substring(previewLength).trim();
                      const canJumpToPage = (
                        source.page_start !== null
                        && source.page_start !== undefined
                        && onCitationClick !== undefined
                      );
                      const pageLabel = getSourcePageLabel(source.page_start, source.page_end);

                      return (
                        <div
                          key={idx}
                          onClick={() => {
                            if (!canJumpToPage || source.page_start === null || source.page_start === undefined) return;
                            onCitationClick({
                              page: source.page_start,
                              snippet: source.content,
                            });
                          }}
                          onKeyDown={(event) => {
                            if (!canJumpToPage || source.page_start === null || source.page_start === undefined) return;
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              onCitationClick({
                                page: source.page_start,
                                snippet: source.content,
                              });
                            }
                          }}
                          role={canJumpToPage ? "button" : undefined}
                          tabIndex={canJumpToPage ? 0 : undefined}
                          className={`bg-zinc-950/50 border border-zinc-800/50 p-3 rounded-lg transition-colors ${
                            canJumpToPage
                              ? "cursor-pointer hover:border-lapis-500/60 hover:bg-zinc-900/70"
                              : "hover:border-lapis-500/30"
                          }`}
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <span className="badge-sm bg-lapis-600 text-white px-2 py-0.5 rounded">
                              {idx + 1}
                            </span>
                            {debugMode && (
                              <span className="text-meta-bright">
                                Similarity: {(source.similarity * 100).toFixed(1)}%
                              </span>
                            )}
                            <span className="text-meta-bright">
                              Excerpt {source.chunk_index}
                            </span>
                            {pageLabel && (
                              <span className="text-meta-bright">
                                {pageLabel}
                              </span>
                            )}
                          </div>

                          <p className="text-caption">
                            &quot;{preview}
                            {!isExpanded && source.content.length > previewLength ? "..." : ""}
                            {isExpanded && remainder ? " " : ""}
                            {isExpanded && remainder ? remainder : ""}&quot;
                          </p>

                          {source.content.length > previewLength && (
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                toggleSourceCard(i, idx);
                              }}
                              className="mt-2 text-link-sm hover:text-lapis-300 transition-colors cursor-pointer"
                            >
                              {isExpanded ? "Show less ▲" : "Show full context ▼"}
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

      </div>

      {/* Input Area */}
      <div className="shrink-0 p-4 border-t border-zinc-800 bg-zinc-900">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about this document..."
            className="flex-1 bg-zinc-950 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-lapis-500/20 focus:border-lapis-500 transition-all placeholder-zinc-600"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={stopActiveStream}
              className="bg-zinc-700 hover:bg-zinc-600 text-white px-6 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-zinc-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="bg-lapis-600 hover:bg-lapis-500 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed text-white px-6 py-2 rounded-xl text-sm font-medium transition-all shadow-lg shadow-lapis-900/20 flex items-center cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
            >
              Send
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
