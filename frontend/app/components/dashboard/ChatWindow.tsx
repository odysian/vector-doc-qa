"use client";

import { useState, useRef, useEffect, SyntheticEvent } from "react";
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

export function ChatWindow({ document, onBack }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

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

    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      // Call the API
      const response = await api.queryDocument(document.id, userMsg);

      // Add AI response with Sources
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
    <div className="flex flex-col h-[600px] bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-900/50 backdrop-blur">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="text-zinc-400 hover:text-white transition-colors text-sm font-medium"
          >
            ← Back to Documents
          </button>
          <div className="h-4 w-px bg-zinc-700"></div>
          <h2 className="font-medium text-zinc-100 flex items-center gap-2">
            <span className="text-zinc-400">Context:</span>
            <span className="text-lapis-400 italic">{document.filename}</span>
          </h2>
        </div>
      </div>

      {/* Messages Area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth"
      >
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-zinc-500 space-y-4">
            <div className="p-4 bg-zinc-800/50 rounded-full">
              {/* Simple 'Chat' Icon placeholder */}
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

        {messages.map((msg, i) => (
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

            {/* Citations / Sources (Only for Assistant) */}
            {msg.sources && msg.sources.length > 0 && (
              <div className="mt-2 ml-2 max-w-[85%] space-y-2">
                <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-1">
                  <span>Sources</span>
                  <span className="bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded-full text-[9px]">
                    {msg.sources.length}
                  </span>
                </p>
                <div className="grid gap-2">
                  {msg.sources.map((source, idx) => (
                    <div
                      key={idx}
                      className="bg-zinc-950/50 border border-zinc-800/50 p-3 rounded-lg hover:border-lapis-500/30 transition-colors group"
                    >
                      <p className="text-xs text-zinc-400 italic mb-1 group-hover:text-lapis-300">
                        &quot;...{source.content.substring(0, 120).trim()}...&quot;
                      </p>
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] text-zinc-600">
                          Relevance: {(source.similarity * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}

        {loading && (
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
            className="bg-lapis-600 hover:bg-lapis-500 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed text-white px-6 py-2 rounded-xl text-sm font-medium transition-all shadow-lg shadow-lapis-900/20 flex items-center"
          >
            {loading ? "Sending..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}
