"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Document as ReactPdfDocument, Page, pdfjs } from "react-pdf";
import { api, ApiError, SessionExpiredError } from "@/lib/api";
import { findCitationSpanMatch, normalizeCitationText } from "./pdfCitationMatch";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

interface PdfViewerProps {
  documentId: number;
  highlightPage?: number | null;
  highlightSnippet?: string | null;
  onSessionExpired?: () => void;
}

const MAX_RENDERED_PAGE_WIDTH = 840;
const PAGE_WIDTH_STEP = 8;
const TEXT_HIGHLIGHT_DURATION_MS = 3000;
const PAGE_HIGHLIGHT_START_DELAY_MS = 300;
const PAGE_HIGHLIGHT_DURATION_MS = 2500;
const SNIPPET_HIGHLIGHT_START_DELAY_MS = 200;
const MAX_SNIPPET_HIGHLIGHT_RETRY_FRAMES = 120;
const MIN_FALLBACK_TOKEN_LENGTH = 4;
const MAX_FALLBACK_HIGHLIGHT_SPANS = 24;
const FALLBACK_ANCHOR_TOKEN_WINDOW = 10;
const MIN_FALLBACK_SPAN_SCORE = 2;
const MIN_FALLBACK_RUN_SCORE = 4;
const MIN_FALLBACK_UNIQUE_TOKEN_MATCHES = 3;

/**
 * In-app PDF viewer that supports citation deep links with page-level fallback.
 */
export function PdfViewer({
  documentId,
  highlightPage,
  highlightSnippet,
  onSessionExpired,
}: PdfViewerProps) {
  const [pdfData, setPdfData] = useState<Uint8Array | null>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [loadingFile, setLoadingFile] = useState(true);
  const [loadingPages, setLoadingPages] = useState(true);
  const [error, setError] = useState<string>("");
  const [pageWidth, setPageWidth] = useState(720);
  const [activeHighlightPage, setActiveHighlightPage] = useState<number | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const pagesContainerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const highlightedTextSpansRef = useRef<HTMLElement[]>([]);
  const textHighlightTimerRef = useRef<number | null>(null);

  const pdfFile = useMemo(() => {
    if (!pdfData) return null;
    return { data: pdfData };
  }, [pdfData]);

  useEffect(() => {
    let cancelled = false;

    const loadPdf = async () => {
      setLoadingFile(true);
      setLoadingPages(true);
      setError("");
      setPdfData(null);
      setNumPages(0);
      pageRefs.current.clear();

      try {
        const blob = await api.getDocumentFile(documentId);
        if (cancelled) return;

        const buffer = await blob.arrayBuffer();
        if (cancelled) return;

        setPdfData(new Uint8Array(buffer));
      } catch (err) {
        if (cancelled) return;
        if (err instanceof SessionExpiredError) {
          onSessionExpired?.();
          return;
        }
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError("Failed to load PDF file");
        }
      } finally {
        if (!cancelled) {
          setLoadingFile(false);
        }
      }
    };

    loadPdf();

    return () => {
      cancelled = true;
    };
  }, [documentId, onSessionExpired]);

  useEffect(() => {
    const pagesContainer = pagesContainerRef.current;
    if (!pagesContainer) return;

    let frameId: number | null = null;

    const updateWidth = (containerWidth: number) => {
      // Snap to a small width grid to avoid noisy resize loops and repaint flashes.
      const boundedWidth = Math.min(Math.max(containerWidth - 2, 260), MAX_RENDERED_PAGE_WIDTH);
      const nextWidth = Math.round(boundedWidth / PAGE_WIDTH_STEP) * PAGE_WIDTH_STEP;
      setPageWidth((current) =>
        Math.abs(current - nextWidth) >= PAGE_WIDTH_STEP ? nextWidth : current
      );
    };

    updateWidth(Math.floor(pagesContainer.clientWidth));
    const observer = new ResizeObserver((entries) => {
      const [entry] = entries;
      if (!entry) return;

      if (frameId !== null) window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(() => {
        updateWidth(Math.floor(entry.contentRect.width));
      });
    });
    observer.observe(pagesContainer);

    return () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      observer.disconnect();
    };
  }, []);

  const clearTextHighlight = useCallback(() => {
    highlightedTextSpansRef.current.forEach((span) => {
      span.classList.remove("citation-text-highlight");
    });
    highlightedTextSpansRef.current = [];

    if (textHighlightTimerRef.current !== null) {
      window.clearTimeout(textHighlightTimerRef.current);
      textHighlightTimerRef.current = null;
    }
  }, []);

  const tryHighlightSnippet = useCallback(
    (targetPage: number, snippet: string): boolean => {
      const target = pageRefs.current.get(targetPage);
      if (!target) return false;

      const spans = Array.from(target.querySelectorAll(".react-pdf__Page__textContent span"))
        .concat(Array.from(target.querySelectorAll(".textLayer span")))
        .filter((node): node is HTMLElement => node instanceof HTMLElement);
      const uniqueSpans = Array.from(new Set(spans));
      if (uniqueSpans.length === 0) return false;

      const match = findCitationSpanMatch(
        uniqueSpans.map((span) => span.textContent ?? ""),
        snippet
      );
      let matchedSpans: HTMLElement[] = [];
      if (match) {
        matchedSpans = uniqueSpans.slice(match.startIndex, match.endIndex + 1);
      } else {
        // Fallback: highlight the strongest contiguous token-overlap region on the page.
        const snippetTokens = normalizeCitationText(snippet)
          .split(" ")
          .filter((word) => word.length >= MIN_FALLBACK_TOKEN_LENGTH);
        if (snippetTokens.length === 0) return false;

        const snippetTokenSet = new Set(snippetTokens);
        const anchorTokenSet = new Set(snippetTokens.slice(0, FALLBACK_ANCHOR_TOKEN_WINDOW));
        const spanWords = uniqueSpans.map((span) =>
          normalizeCitationText(span.textContent ?? "").split(" ").filter(Boolean)
        );
        const spanScores = spanWords.map((words) =>
          words.reduce((score, word) => (snippetTokenSet.has(word) ? score + 1 : score), 0)
        );
        const anchorScores = spanWords.map((words) =>
          words.reduce((score, word) => (anchorTokenSet.has(word) ? score + 1 : score), 0)
        );

        let bestIndex = -1;
        let bestCombinedScore = 0;
        let bestScore = 0;
        spanScores.forEach((score, index) => {
          const combinedScore = score + (anchorScores[index] ?? 0) * 2;
          if (
            combinedScore > bestCombinedScore
            || (combinedScore === bestCombinedScore && score > bestScore)
          ) {
            bestCombinedScore = combinedScore;
            bestScore = score;
            bestIndex = index;
          }
        });
        if (bestIndex === -1 || bestScore < MIN_FALLBACK_SPAN_SCORE) return false;

        const startIndex = bestIndex;
        let endIndex = bestIndex;
        while (endIndex < uniqueSpans.length - 1 && spanScores[endIndex + 1] > 0) {
          endIndex += 1;
        }

        const fallbackSpanCount = Math.min(endIndex - startIndex + 1, MAX_FALLBACK_HIGHLIGHT_SPANS);
        const fallbackEnd = startIndex + fallbackSpanCount;
        const runTotalScore = spanScores
          .slice(startIndex, fallbackEnd)
          .reduce((sum, score) => sum + score, 0);
        const matchedFallbackTokens = new Set(
          spanWords
            .slice(startIndex, fallbackEnd)
            .flat()
            .filter((word) => snippetTokenSet.has(word))
        );
        if (
          runTotalScore < MIN_FALLBACK_RUN_SCORE
          || matchedFallbackTokens.size < MIN_FALLBACK_UNIQUE_TOKEN_MATCHES
        ) {
          return false;
        }
        matchedSpans = uniqueSpans.slice(startIndex, fallbackEnd);
      }

      if (matchedSpans.length === 0) return false;

      clearTextHighlight();
      matchedSpans.forEach((span) => {
        span.classList.add("citation-text-highlight");
      });
      highlightedTextSpansRef.current = matchedSpans;

      textHighlightTimerRef.current = window.setTimeout(() => {
        clearTextHighlight();
      }, TEXT_HIGHLIGHT_DURATION_MS);
      return true;
    },
    [clearTextHighlight]
  );

  useEffect(() => {
    return () => {
      clearTextHighlight();
    };
  }, [clearTextHighlight]);

  useEffect(() => {
    if (!highlightPage || !numPages) return;

    const targetPage = Math.max(1, Math.min(highlightPage, numPages));
    const snippet = highlightSnippet?.trim() || "";
    let frameId: number | null = null;
    let snippetFrameId: number | null = null;
    let snippetStartTimer: number | null = null;
    let highlightStartTimer: number | null = null;
    let highlightTimer: number | null = null;
    let attempts = 0;
    let snippetAttempts = 0;

    // Citations can arrive before page wrappers mount, so retry briefly.
    const scrollToTarget = () => {
      const target = pageRefs.current.get(targetPage);
      if (!target) {
        if (attempts < 20) {
          attempts += 1;
          frameId = window.requestAnimationFrame(scrollToTarget);
        }
        return;
      }

      target.scrollIntoView({ behavior: "smooth", block: "center" });
      clearTextHighlight();
      // Start page-level fallback highlight after smooth-scroll has begun.
      setActiveHighlightPage((current) => (current === targetPage ? null : current));
      highlightStartTimer = window.setTimeout(() => {
        setActiveHighlightPage(targetPage);
        highlightTimer = window.setTimeout(() => {
          setActiveHighlightPage((current) => (current === targetPage ? null : current));
        }, PAGE_HIGHLIGHT_DURATION_MS);
      }, PAGE_HIGHLIGHT_START_DELAY_MS);

      if (snippet) {
        const highlightSnippetOnceReady = () => {
          if (tryHighlightSnippet(targetPage, snippet)) return;
          if (snippetAttempts < MAX_SNIPPET_HIGHLIGHT_RETRY_FRAMES) {
            snippetAttempts += 1;
            snippetFrameId = window.requestAnimationFrame(highlightSnippetOnceReady);
          }
        };

        // Let smooth scrolling begin before trying transient text highlight.
        snippetStartTimer = window.setTimeout(() => {
          highlightSnippetOnceReady();
        }, SNIPPET_HIGHLIGHT_START_DELAY_MS);
      }
    };

    scrollToTarget();

    return () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      if (snippetFrameId !== null) window.cancelAnimationFrame(snippetFrameId);
      if (snippetStartTimer !== null) window.clearTimeout(snippetStartTimer);
      if (highlightStartTimer !== null) window.clearTimeout(highlightStartTimer);
      if (highlightTimer !== null) window.clearTimeout(highlightTimer);
    };
  }, [highlightPage, highlightSnippet, numPages, clearTextHighlight, tryHighlightSnippet]);

  const onDocumentLoadSuccess = ({ numPages: loadedPages }: { numPages: number }) => {
    setNumPages(loadedPages);
    setLoadingPages(false);
  };

  const onDocumentLoadError = (err: Error) => {
    setError(err.message || "Failed to render PDF");
    setLoadingPages(false);
  };

  return (
    <div className="flex h-full min-h-0 w-full flex-1 flex-col rounded-lg border border-zinc-800 bg-zinc-900 shadow-xl overflow-hidden">
      <div className="shrink-0 border-b border-zinc-800 px-4 py-3">
        <h3 className="text-sm font-medium text-zinc-200">PDF Viewer</h3>
      </div>

      <div ref={scrollContainerRef} className="flex-1 min-h-0 overflow-y-auto p-3">
        {loadingFile && (
          <div className="h-full min-h-48 flex items-center justify-center text-zinc-400">
            <div className="flex items-center gap-3">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-600 border-t-lapis-400" />
              <span className="text-body-sm">Loading PDF...</span>
            </div>
          </div>
        )}

        {!loadingFile && error && (
          <div className="h-full min-h-48 flex items-center justify-center">
            <div className="max-w-sm rounded-lg border border-red-900/50 bg-red-900/20 p-4 text-center">
              <p className="text-error text-body-sm">{error}</p>
            </div>
          </div>
        )}

        {!loadingFile && !error && pdfFile && (
          <ReactPdfDocument
            file={pdfFile}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="h-full min-h-48 flex items-center justify-center text-zinc-400">
                <div className="flex items-center gap-3">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-600 border-t-lapis-400" />
                  <span className="text-body-sm">Rendering pages...</span>
                </div>
              </div>
            }
          >
            <div ref={pagesContainerRef} className="mx-auto w-full max-w-6xl space-y-4 pb-4">
              {Array.from({ length: numPages }, (_, index) => {
                const pageNumber = index + 1;
                const isHighlighted = activeHighlightPage === pageNumber;

                return (
                  <div
                    key={pageNumber}
                    ref={(node) => {
                      if (node) pageRefs.current.set(pageNumber, node);
                      else pageRefs.current.delete(pageNumber);
                    }}
                    className={`mx-auto w-fit overflow-hidden rounded-lg border bg-zinc-950/70 transition-colors duration-200 ${
                      isHighlighted
                        ? "border-lapis-400/70 ring-1 ring-lapis-400/45 bg-lapis-900/10"
                        : "border-zinc-800"
                    }`}
                  >
                    <div className="border-b border-zinc-800 px-3 py-2">
                      <p className="text-meta">Page {pageNumber}</p>
                    </div>
                    <div className="flex justify-center">
                      <Page
                        pageNumber={pageNumber}
                        width={pageWidth}
                        renderAnnotationLayer={false}
                        renderTextLayer
                        loading={null}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </ReactPdfDocument>
        )}

        {!loadingFile && !error && pdfFile && !loadingPages && numPages === 0 && (
          <div className="h-full min-h-48 flex items-center justify-center text-zinc-400">
            <p className="text-body-sm">No pages found in this PDF.</p>
          </div>
        )}
      </div>
    </div>
  );
}
