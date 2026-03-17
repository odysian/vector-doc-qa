/**
 * Chat Window: Pop-up window for querying documents using RAG. Displays
 * conversation and context.
 */

"use client";

import { type ComponentPropsWithoutRef, KeyboardEvent, SyntheticEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowLeft, Check, Copy, Send, Square } from "lucide-react";
import { formatDate } from "@/lib/utils";
import type { Document } from "@/lib/api";
import { useChatState } from "@/lib/hooks/useChatState";
import { ErrorBoundary } from "./ErrorBoundary";

interface CitationTarget {
  page: number;
  snippet?: string;
  documentId?: number;
}

interface ChatWindowProps {
  document?: Document;
  workspaceId?: number;
  workspaceName?: string;
  workspaceDocumentIds?: number[];
  debugMode?: boolean;
  onToggleDebugMode?: () => void;
  showContextBar?: boolean;
  contextTitle?: string;
  contextDate?: string;
  onBack: () => void;
  onCitationClick?: (citation: CitationTarget) => void;
  onSessionExpired?: () => void;
}

function CopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    // Guard: clipboard API unavailable in some browsers/contexts.
    if (!navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(content);
      // Only show success after confirmed write.
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Write denied or failed — no false-success feedback.
    }
  };
  return (
    <button
      type="button"
      onClick={() => { void handleCopy(); }}
      title={copied ? "Copied!" : "Copy response"}
      aria-label="Copy response"
      className="ui-btn ui-btn-ghost ui-btn-sm mt-1 ml-2"
    >
      {copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
    </button>
  );
}

const SUGGESTED_PROMPTS = [
  "Summarize this document",
  "What are the main points?",
  "Find key dates or numbers",
];
const HIGH_CONFIDENCE_THRESHOLD = 0.5864;
const MEDIUM_CONFIDENCE_THRESHOLD = 0.3699;

// Only allow http/https/mailto links; unsafe protocols (javascript:, data:, etc.)
// are rendered as plain spans so assistant content can never produce clickable injection payloads.
const markdownComponents = {
  a({ href, children }: ComponentPropsWithoutRef<"a">) {
    const isSafe = href != null && /^(https?:\/\/|mailto:)/i.test(href);
    return isSafe ? (
      <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
    ) : (
      <span>{children}</span>
    );
  },
};

/**
 * Renders the pop up window with query input and message history.
 */
export function ChatWindow({
  document,
  workspaceId,
  workspaceName,
  workspaceDocumentIds,
  debugMode = false,
  showContextBar = false,
  contextTitle,
  contextDate,
  onBack,
  onCitationClick,
  onSessionExpired,
}: ChatWindowProps) {
  const isWorkspaceMode = workspaceId !== undefined;
  const [input, setInput] = useState("");
  const [expandedSourceIndices, setExpandedSourceIndices] = useState<Set<number>>(new Set());
  const [expandedSourceCards, setExpandedSourceCards] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const hasLoadedHistoryRef = useRef(false);
  const skipPostHistoryScrollRef = useRef(false);
  const { messages, loadingHistory, isStreaming, canStopStream, submitQuery, stopActiveStream } = useChatState({
    document,
    workspaceId,
    onSessionExpired,
  });

  /** Toggle whether the whole "Sources" block for a message is open or collapsed. */
  const toggleSources = useCallback((messageIndex: number) => {
    setExpandedSourceIndices((prev) => {
      const next = new Set(prev);
      const expanding = !next.has(messageIndex);
      if (expanding) next.add(messageIndex);
      else next.delete(messageIndex);

      // After expanding, scroll the sources container into view
      if (expanding) {
        requestAnimationFrame(() => {
          const container = scrollRef.current?.querySelector(`[data-sources="${messageIndex}"]`);
          if (container && typeof container.scrollIntoView === "function") {
            container.scrollIntoView({ behavior: "smooth", block: "end" });
          }
        });
      }
      return next;
    });
  }, []);

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

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "auto") => {
    const container = scrollRef.current;
    if (!container) return;
    if (typeof container.scrollTo === "function") {
      container.scrollTo({
        top: container.scrollHeight,
        behavior,
      });
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, []);

  useLayoutEffect(() => {
    if (loadingHistory) {
      hasLoadedHistoryRef.current = false;
      skipPostHistoryScrollRef.current = false;
      return;
    }

    if (!hasLoadedHistoryRef.current) {
      scrollToBottom("auto");
      hasLoadedHistoryRef.current = true;
      // Skip the next generic message-driven auto-scroll run so initial render doesn't jump twice.
      skipPostHistoryScrollRef.current = true;
    }
  }, [loadingHistory, scrollToBottom]);

  // Keep chat at bottom for live updates after initial history load.
  useLayoutEffect(() => {
    if (!hasLoadedHistoryRef.current) return;
    if (skipPostHistoryScrollRef.current) {
      skipPostHistoryScrollRef.current = false;
      return;
    }
    scrollToBottom("auto");
  }, [messages, loadingHistory, scrollToBottom]);

  const submitCurrentInput = () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    void submitQuery(trimmed);
  };

  const handleSubmit = (e: SyntheticEvent) => {
    e.preventDefault();
    submitCurrentInput();
  };

  const resizeComposer = useCallback(() => {
    const composer = composerRef.current;
    if (!composer) return;
    const maxHeight = 144;
    composer.style.height = "auto";
    const nextHeight = Math.min(composer.scrollHeight, maxHeight);
    composer.style.height = `${nextHeight}px`;
    composer.style.overflowY = nextHeight === maxHeight ? "auto" : "hidden";
  }, []);

  useEffect(() => {
    resizeComposer();
  }, [input, resizeComposer]);

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter") return;
    if (event.nativeEvent.isComposing) return;
    if (event.shiftKey) return;

    event.preventDefault();
    submitCurrentInput();
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

  const MessageRow = ({
    msg,
    index,
  }: {
    msg: (typeof messages)[number];
    index: number;
  }) => (
    <div
      data-testid={`message-row-${msg.role}`}
      className={`group flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
      title={msg.role === "assistant" && msg.created_at ? formatDate(msg.created_at) : undefined}
    >
      {/* Message Bubble — user keeps lapis bubble; assistant renders flat at full width */}
      {msg.role === "user" ? (
        <div
          className="max-w-[85%] rounded-2xl px-3.5 py-2.5 shadow-sm bg-lapis-600 text-white rounded-tr-none"
          title={msg.created_at ? formatDate(msg.created_at) : undefined}
        >
          <p className="whitespace-pre-wrap text-body-sm leading-relaxed">
            {msg.content}
          </p>
        </div>
      ) : (
        <div className="w-full py-1 text-zinc-100">
          {msg.streaming && !msg.content ? (
            <div className="flex items-center gap-2 text-zinc-400">
              <div className="w-2 h-2 bg-lapis-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <div className="w-2 h-2 bg-lapis-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <div className="w-2 h-2 bg-lapis-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          ) : (
            <>
              <div className="chat-prose text-body-sm leading-relaxed">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {msg.content}
                </ReactMarkdown>
              </div>
              {msg.streaming && msg.content && (
                <span className="streaming-cursor" aria-hidden />
              )}
            </>
          )}
        </div>
      )}

      {msg.role === "assistant" && !msg.streaming && (
        <div className="flex items-start">
          {msg.content && <CopyButton content={msg.content} />}
          {debugMode && msg.pipeline_meta && (
            <details className="mt-2 ml-2 text-xs text-zinc-400 group">
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
                  {msg.pipeline_meta.chunks_retrieved}{" "}
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
                <p>Chunks above retrieval threshold: {msg.pipeline_meta.chunks_above_threshold}</p>
                <p>Similarity spread: {(msg.pipeline_meta.similarity_spread * 100).toFixed(1)}%</p>
                <p>History turns included: {msg.pipeline_meta.chat_history_turns_included}</p>
                <div className="border-t border-zinc-700/50 pt-1 mt-1">
                  <p>Total: {msg.pipeline_meta.total_ms}ms</p>
                </div>
              </div>
            </details>
          )}
        </div>
      )}

      {msg.role === "assistant" && msg.retry_query && !msg.streaming && (
        <button
          type="button"
          onClick={() => handleRetry(msg.retry_query!)}
          disabled={isStreaming}
          className="ui-btn ui-btn-ghost ui-btn-sm mt-2 ml-2"
        >
          Retry
        </button>
      )}

      {/* Citations / Sources (collapsed by default, expand on click) */}
      {msg.sources && msg.sources.length > 0 && (
        <div className="mt-2 ml-2 pt-2 border-t border-zinc-700/50">
          <button
            type="button"
            onClick={() => toggleSources(index)}
            className="ui-btn ui-btn-ghost ui-btn-sm"
          >
            <svg
              className={`w-3 h-3 shrink-0 transition-transform ${expandedSourceIndices.has(index) ? "rotate-90" : ""}`}
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
          {expandedSourceIndices.has(index) && (
            <div data-sources={index} className="mt-2 grid gap-1.5 max-h-[40vh] overflow-y-auto">
              {msg.sources.map((source, sourceIndex) => {
                const cardKey = `${index}-${sourceIndex}`;
                const isExpanded = expandedSourceCards.has(cardKey);
                const previewLength = 150;
                const preview = source.content.substring(0, previewLength).trim();
                const remainder = source.content.substring(previewLength).trim();
                const hasPageStart = source.page_start !== null && source.page_start !== undefined;
                const isWorkspaceSourcePresent = !isWorkspaceMode || (
                  source.document_id !== undefined
                  && workspaceDocumentIds?.includes(source.document_id) === true
                );
                const canJumpToPage = (
                  hasPageStart
                  && onCitationClick !== undefined
                  && isWorkspaceSourcePresent
                );
                const isDisabledWorkspaceSource = isWorkspaceMode && hasPageStart && !isWorkspaceSourcePresent;
                const pageLabel = getSourcePageLabel(source.page_start, source.page_end);

                return (
                  <div
                    key={sourceIndex}
                    onClick={() => {
                      if (!canJumpToPage || source.page_start === null || source.page_start === undefined) return;
                      onCitationClick({
                        page: source.page_start,
                        snippet: source.content,
                        documentId: source.document_id,
                      });
                    }}
                    onKeyDown={(event) => {
                      if (!canJumpToPage || source.page_start === null || source.page_start === undefined) return;
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onCitationClick({
                          page: source.page_start,
                          snippet: source.content,
                          documentId: source.document_id,
                        });
                      }
                    }}
                    role={canJumpToPage ? "button" : undefined}
                    tabIndex={canJumpToPage ? 0 : undefined}
                    aria-disabled={isDisabledWorkspaceSource || undefined}
                    className={`bg-zinc-950/50 border border-zinc-800/50 px-2.5 py-2 rounded-lg transition-colors ${
                      canJumpToPage
                        ? "cursor-pointer hover:border-lapis-500/60 hover:bg-zinc-900/70"
                        : isDisabledWorkspaceSource
                          ? "cursor-not-allowed opacity-60"
                          : "hover:border-lapis-500/30"
                    }`}
                  >
                    <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                      <span className="badge-sm bg-lapis-600 text-white px-1.5 py-0.5 rounded">
                        {sourceIndex + 1}
                      </span>
                      {source.document_filename && (
                        <span className="text-meta-bright font-medium truncate max-w-full">
                          {source.document_filename}
                        </span>
                      )}
                      {pageLabel && (
                        <span className="text-meta rounded border border-zinc-700/80 px-1.5 py-0.5">
                          {pageLabel}
                        </span>
                      )}
                      {debugMode && (
                        <span className="text-meta rounded border border-zinc-700/80 px-1.5 py-0.5">
                          {(source.similarity * 100).toFixed(1)}%
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
                          toggleSourceCard(index, sourceIndex);
                        }}
                        className="ui-btn ui-btn-ghost ui-btn-sm mt-2"
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
  );

  const resolvedContextTitle = contextTitle
    || (isWorkspaceMode ? (workspaceName || "Workspace") : (document?.filename || "Document"));
  const resolvedContextDate = contextDate || document?.uploaded_at || "";

  return (
    <div className="ui-panel flex flex-col w-full h-full min-h-0 max-h-full overflow-hidden shadow-xl">
      {showContextBar && (
        <div
          data-testid="chat-context-bar"
          className="shrink-0 flex items-center gap-1.5 border-b border-zinc-800 bg-zinc-900/50 px-2.5 py-1.5"
        >
          <button
            type="button"
            onClick={onBack}
            title={isWorkspaceMode ? "Back to Workspaces" : "Back to Documents"}
            className="ui-btn ui-btn-ghost ui-btn-sm shrink-0"
            aria-label={isWorkspaceMode ? "Back to Workspaces" : "Back to Documents"}
          >
            <ArrowLeft size={18} strokeWidth={2} />
          </button>
          <p className="min-w-0 truncate text-sm text-zinc-200">
            <span className="font-medium text-lapis-400 italic">{resolvedContextTitle}</span>
            {resolvedContextDate && (
              <span className="text-meta"> · {formatDate(resolvedContextDate)}</span>
            )}
          </p>
        </div>
      )}

      {/* Messages Area */}
      <ErrorBoundary variant="inline">
        <div
          ref={scrollRef}
          className="messages-scroll min-h-0 flex-1 overflow-y-auto px-3 py-3 space-y-4"
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
                {isWorkspaceMode
                  ? "Ask a question across workspace documents"
                  : "Ask a question about this document"}
              </h3>
              <p className="text-meta text-center">
                {isWorkspaceMode
                  ? "Your cross-document questions and answers will appear here."
                  : "Your questions and answers will appear here."}
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
                    className="ui-btn ui-btn-neutral ui-btn-md"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {!loadingHistory &&
            messages.map((msg, index) => (
              <ErrorBoundary key={index} variant="inline">
                <MessageRow msg={msg} index={index} />
              </ErrorBoundary>
            ))}

      </div>
    </ErrorBoundary>

      {/* Input Area */}
      <div className="shrink-0 px-3 py-3 border-t border-zinc-800 bg-zinc-900">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <textarea
            ref={composerRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleComposerKeyDown}
            rows={1}
            placeholder={
              isWorkspaceMode
                ? "Ask a question across this workspace..."
                : "Ask a question about this document..."
            }
            className="ui-input flex-1 resize-none overflow-y-hidden min-h-[44px] max-h-36 leading-relaxed"
            title="Enter to send, Shift+Enter for newline"
          />
          {isStreaming && canStopStream ? (
            <button
              type="button"
              onClick={stopActiveStream}
              aria-label="Stop response"
              title="Stop response"
              className="ui-btn ui-btn-neutral ui-btn-sm shrink-0 self-stretch px-2"
            >
              <Square size={16} strokeWidth={2} aria-hidden />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              aria-label="Send message"
              title="Send message"
              className="ui-btn ui-btn-primary ui-btn-sm shrink-0 self-stretch px-2"
            >
              <Send size={16} strokeWidth={2} aria-hidden />
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
