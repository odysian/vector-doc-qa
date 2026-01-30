/**
 * Chat Window: Pop-up window for querying documents using RAG. Displays
 * conversation and context.
 */

"use client";

import { useState, useRef, useEffect, SyntheticEvent } from "react";
import { ArrowLeft } from "lucide-react";
import { type Document, api, type QueryResponse, ApiError } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: QueryResponse["sources"];
}

interface ChatWindowProps {
  document: Document;
  onBack: () => void;
}

/**
 * Renders the pop up window with query input and message history.
 */
export function ChatWindow({ document, onBack }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [expandedSourceIndices, setExpandedSourceIndices] = useState<Set<number>>(new Set());
  const [expandedSourceCards, setExpandedSourceCards] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

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


  useEffect(() => {
    const loadHistory = async () => {
      try {
        setLoadingHistory(true);
        const response = await api.getMessages(document.id);

        const loadedMessages: Message[] = response.messages.map((msg) => ({
          role: msg.role,
          content: msg.content,
          sources: msg.sources as QueryResponse["sources"],
        }));
        setMessages(loadedMessages);
      } catch (err) {
        console.error("Failed to load message history:", err);
      } finally {
        setLoadingHistory(false);
      }
    };

    loadHistory();
  }, [document.id]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);




  const handleSubmit = async (e: SyntheticEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput("");

    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      const response = await api.queryDocument(document.id, userMsg);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer,
          sources: response.sources,
        },
      ]);
    } catch (err) {
      let errorMessage = "Error: Failed to get answer. Please try again.";

      if (err instanceof ApiError) {
        if (err.status === 400) {
          errorMessage = "This document hasn't been processed yet. Please process it first before asking questions.";
        } else if (err.status === 404) {
          errorMessage = "Document not found.";
        } else if (err.status === 401) {
          errorMessage = "Your session has expired. Please log in again.";
        } else {
          errorMessage = `Error: ${err.detail}`;
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: errorMessage,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-[320px] h-[calc(100vh-10rem)] bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-900/50 backdrop-blur">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            title="Back to Documents"
            className="text-zinc-400 hover:text-white transition-colors cursor-pointer p-1 -m-1 rounded focus:outline-none focus:ring-2 focus:ring-lapis-500 focus:ring-offset-2 focus:ring-offset-zinc-900"
            aria-label="Back to Documents"
          >
            <ArrowLeft size={24} strokeWidth={2} className="shrink-0" />
          </button>
          <div className="h-4 w-px bg-zinc-700"></div>
          <h2 className="font-medium text-zinc-100 text-lapis-400 italic truncate">
            {document.filename}
          </h2>
        </div>
      </div>

      {/* Messages Area */}
      <div
        ref={scrollRef}
        className="messages-scroll flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth"
      >
        {loadingHistory && (
          <div className="h-full flex items-center justify-center text-zinc-500">
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
              <span className="ml-2">Loading conversation...</span>
            </div>
          </div>
        )}

        {!loadingHistory && messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-zinc-500 space-y-4">
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
            <p className="text-sm">Ask a question to analyze this document.</p>
          </div>
        )}

        {!loadingHistory &&
          messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col ${
              msg.role === "user" ? "items-end" : "items-start"
            }`}
          >
            {/* Message Bubble */}
            <div
              className={`max-w-[85%] rounded-2xl p-4 shadow-sm ${
                msg.role === "user"
                  ? "bg-lapis-600 text-white rounded-tr-none"
                  : "bg-zinc-800 text-zinc-100 rounded-tl-none border border-zinc-700"
              }`}
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {msg.content}
              </p>
            </div>

            {/* Citations / Sources (collapsed by default, expand on click) */}
            {msg.sources && msg.sources.length > 0 && (
              <div className="mt-2 ml-2 max-w-[85%]">
                <button
                  type="button"
                  onClick={() => toggleSources(i)}
                  className="flex items-center gap-2 text-[10px] font-bold text-lapis-400 uppercase tracking-wider hover:text-lapis-300 transition-colors cursor-pointer"
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

                      return (
                        <div
                          key={idx}
                          className="bg-zinc-950/50 border border-zinc-800/50 p-3 rounded-lg hover:border-lapis-500/30 transition-colors"
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <span className="bg-lapis-600 text-white text-[10px] font-bold px-2 py-0.5 rounded">
                              {idx + 1}
                            </span>
                            <span className="text-[10px] text-zinc-500">
                              Relevance: {(source.similarity * 100).toFixed(0)}%
                            </span>
                            <span className="text-[10px] text-zinc-600">
                              Excerpt {source.chunk_index}
                            </span>
                          </div>

                          <p className="text-xs text-zinc-400 italic">
                            &quot;{preview}
                            {!isExpanded && source.content.length > previewLength ? "..." : ""}
                            {isExpanded && remainder ? " " : ""}
                            {isExpanded && remainder ? remainder : ""}&quot;
                          </p>

                          {source.content.length > previewLength && (
                            <button
                              type="button"
                              onClick={() => toggleSourceCard(i, idx)}
                              className="mt-2 text-[10px] text-lapis-400 hover:text-lapis-300 transition-colors cursor-pointer"
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

        {!loadingHistory && loading && (
          <div className="flex justify-start">
            <div className="bg-zinc-800 border border-zinc-700 text-zinc-400 rounded-2xl rounded-tl-none p-4 flex items-center gap-2">
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
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-zinc-800 bg-zinc-900">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about this document..."
            className="flex-1 bg-zinc-950 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-lapis-500/20 focus:border-lapis-500 transition-all placeholder-zinc-600"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-lapis-600 hover:bg-lapis-500 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed text-white px-6 py-2 rounded-xl text-sm font-medium transition-all shadow-lg shadow-lapis-900/20 flex items-center cursor-pointer"
          >
            {loading ? "Sending..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}
