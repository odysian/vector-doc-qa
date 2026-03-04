/**
 * Dashboard: sidebar layout. Documents in left sidebar; chat in main area.
 * Responsive: sidebar is fixed on desktop, drawer on mobile. Zinc + lapis theme.
 */
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { PanelLeft, X, FileUp } from "lucide-react";
import { api, isLoggedIn, type Document, ApiError, SessionExpiredError } from "@/lib/api";
import { UploadZone } from "../components/dashboard/UploadZone";
import { DocumentList } from "../components/dashboard/DocumentList";
import { ChatWindow } from "../components/dashboard/ChatWindow";
import { DeleteDocumentModal } from "../components/dashboard/DeleteDocumentModal";

const SIDEBAR_WIDTH = "w-72";
const SPLIT_LAYOUT_MIN_WIDTH = 1120;
const SPLIT_LAYOUT_RESTORE_WIDTH = 1240;
const PdfViewer = dynamic(
  () => import("../components/dashboard/PdfViewer").then((mod) => mod.PdfViewer),
  { ssr: false }
);

export default function DashboardPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null);
  const [deletingInProgress, setDeletingInProgress] = useState(false);
  const [highlightPage, setHighlightPage] = useState<number | null>(null);
  const [mobileTab, setMobileTab] = useState<"pdf" | "chat">("chat");
  const [useTabLayout, setUseTabLayout] = useState(true);
  const [desktopSidebarCollapsed, setDesktopSidebarCollapsed] = useState(false);
  const documentsRef = useRef<Document[]>([]);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const hasActiveDocuments = documents.some(
    (doc) => doc.status === "pending" || doc.status === "processing"
  );
  const handleSessionExpired = useCallback(() => {
    router.push("/login");
  }, [router]);

  const isSessionExpired = useCallback((err: unknown): boolean => {
    return err instanceof SessionExpiredError || (err instanceof ApiError && err.status === 401);
  }, []);

  const handleApiError = useCallback(
    (err: unknown, fallbackMessage: string): boolean => {
      if (isSessionExpired(err)) {
        handleSessionExpired();
        return true;
      }

      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError(fallbackMessage);
      }
      return false;
    },
    [handleSessionExpired, isSessionExpired]
  );

  const loadDocuments = useCallback(async () => {
    try {
      const response = await api.getDocuments();
      setDocuments(response.documents);
    } catch (err) {
      handleApiError(err, "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [handleApiError]);

  useEffect(() => {
    if (!isLoggedIn()) return handleSessionExpired();
    loadDocuments();
  }, [handleSessionExpired, loadDocuments]);

  useEffect(() => {
    documentsRef.current = documents;
  }, [documents]);

  useEffect(() => {
    if (!selectedDocument) return;
    const updatedDocument = documents.find((doc) => doc.id === selectedDocument.id);

    if (!updatedDocument) {
      setSelectedDocument(null);
      return;
    }

    if (updatedDocument !== selectedDocument) {
      setSelectedDocument(updatedDocument);
    }
  }, [documents, selectedDocument]);

  useEffect(() => {
    if (loading || !hasActiveDocuments) return;

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let delayMs = 3000;

    const scheduleNextPoll = () => {
      if (cancelled) return;
      timeoutId = setTimeout(pollStatuses, delayMs);
    };

    const pollStatuses = async () => {
      const activeDocuments = documentsRef.current.filter(
        (doc) => doc.status === "pending" || doc.status === "processing"
      );

      if (activeDocuments.length === 0 || cancelled) return;

      const targetIds = activeDocuments.map((doc) => doc.id);
      const results = await Promise.allSettled(
        targetIds.map((id) => api.getDocumentStatus(id))
      );

      if (cancelled) return;

      let shouldRedirectToLogin = false;
      let hadPollFailures = false;
      const missingIds = new Set<number>();
      const statusById = new Map<number, Awaited<ReturnType<typeof api.getDocumentStatus>>>();

      results.forEach((result, index) => {
        const documentId = targetIds[index];
        if (result.status === "fulfilled") {
          statusById.set(documentId, result.value);
          return;
        }

        const reason = result.reason;
        if (isSessionExpired(reason)) {
          shouldRedirectToLogin = true;
          return;
        }

        if (reason instanceof ApiError && reason.status === 404) {
          missingIds.add(documentId);
          return;
        }

        hadPollFailures = true;
      });

      if (shouldRedirectToLogin) {
        handleSessionExpired();
        return;
      }

      if (statusById.size > 0 || missingIds.size > 0) {
        setDocuments((prev) =>
          prev
            .filter((doc) => !missingIds.has(doc.id))
            .map((doc) => {
              const status = statusById.get(doc.id);
              if (!status) return doc;
              return {
                ...doc,
                status: status.status,
                processed_at: status.processed_at,
                error_message: status.error_message,
              };
            })
        );
      }

      if (hadPollFailures && statusById.size === 0) {
        delayMs = Math.min(delayMs * 2, 10000);
      } else {
        delayMs = Math.min(Math.floor(delayMs * 1.5), 10000);
      }

      scheduleNextPoll();
    };

    scheduleNextPoll();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [hasActiveDocuments, loading, handleSessionExpired, isSessionExpired]);

  useEffect(() => {
    const workspace = workspaceRef.current;
    if (!workspace) return;

    let frameId: number | null = null;

    const updateLayoutMode = (width: number) => {
      setUseTabLayout((current) => {
        if (current) {
          return width < SPLIT_LAYOUT_RESTORE_WIDTH;
        }
        return width < SPLIT_LAYOUT_MIN_WIDTH;
      });
    };

    updateLayoutMode(Math.floor(workspace.clientWidth));

    const observer = new ResizeObserver((entries) => {
      const [entry] = entries;
      if (!entry) return;

      if (frameId !== null) window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(() => {
        updateLayoutMode(Math.floor(entry.contentRect.width));
      });
    });

    observer.observe(workspace);

    return () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      observer.disconnect();
    };
  }, [selectedDocument?.id]);

  const handleUpload = async (file: File) => {
    setError("");
    try {
      await api.uploadDocument(file);
      await loadDocuments();
    } catch (err) {
      const redirected = handleApiError(err, "Upload failed");
      if (!redirected) {
        throw err;
      }
    }
  };

  const handleLogout = async () => {
    await api.logout();
    handleSessionExpired();
  };

  const handleDocumentClick = (document: Document) => {
    if (document.status !== "completed") return;
    setSelectedDocument(document);
    setHighlightPage(null);
    setMobileTab("chat");
    setSidebarOpen(false);
  };

  const handleBackToDocuments = () => {
    setSelectedDocument(null);
    setHighlightPage(null);
    setSidebarOpen(true);
  };

  const handleCitationClick = (page: number) => {
    setMobileTab("pdf");
    setHighlightPage((current) => {
      if (current === page) {
        window.setTimeout(() => setHighlightPage(page), 0);
        return null;
      }
      return page;
    });
  };

  const handleProcessDocument = async (doc: Document) => {
    setError("");
    try {
      await api.processDocument(doc.id);
      await loadDocuments();
    } catch (err) {
      handleApiError(err, "Failed to queue processing");
    }
  };

  const handleDeleteDocument = (doc: Document) => {
    setDocumentToDelete(doc);
  };

  const handleConfirmDelete = async () => {
    if (!documentToDelete) return;
    const doc = documentToDelete;
    setDeletingInProgress(true);
    setError("");
    try {
      await api.deleteDocument(doc.id);
      setDocumentToDelete(null);
      if (selectedDocument?.id === doc.id) setSelectedDocument(null);
      await loadDocuments();
    } catch (err) {
      handleApiError(err, "Failed to delete document");
    } finally {
      setDeletingInProgress(false);
    }
  };

  const showPdfPane = !useTabLayout || mobileTab === "pdf";
  const showChatPane = !useTabLayout || mobileTab === "chat";

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-3 border-b border-zinc-800 xl:border-b-0">
        <h2 className="text-section">Documents</h2>
        <button
          type="button"
          onClick={() => setSidebarOpen(false)}
          className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 xl:hidden cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
          aria-label="Close sidebar"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        <UploadZone onUpload={handleUpload} />
        {error && (
          <div className="bg-red-900/20 border border-red-900/50 text-error p-3 rounded-lg text-body-sm">
            {error}
          </div>
        )}
        {loading ? (
          <p className="text-empty">Loading...</p>
        ) : (
          <DocumentList
            documents={documents}
            onDocumentClick={handleDocumentClick}
            onProcessDocument={handleProcessDocument}
            onDeleteDocument={handleDeleteDocument}
          />
        )}
      </div>
    </div>
  );

  return (
    <div className="h-screen overflow-hidden bg-zinc-950 flex flex-col">
      {/* Header */}
      <header className="shrink-0 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center justify-between h-14 px-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen((o) => !o)}
              className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 xl:hidden cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              aria-label="Toggle sidebar"
            >
              <PanelLeft className="w-5 h-5" />
            </button>
            <button
              type="button"
              onClick={() => setDesktopSidebarCollapsed((collapsed) => !collapsed)}
              className="hidden xl:inline-flex p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              aria-label={desktopSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={desktopSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <PanelLeft
                className={`w-5 h-5 transition-transform ${desktopSidebarCollapsed ? "rotate-180" : ""}`}
              />
            </button>
            <h1 className="text-3xl leading-none font-bold font-cormorant italic text-lapis-400">
              Quaero
            </h1>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="text-sm text-zinc-400 hover:text-zinc-300 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 rounded"
          >
            Logout
          </button>
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Sidebar: drawer on mobile, fixed on desktop */}
        <aside
          className={`
            ${SIDEBAR_WIDTH} shrink-0 flex flex-col bg-zinc-900 border-r border-zinc-800
            fixed left-0 top-14 bottom-0 xl:relative xl:top-0 z-40 xl:z-auto
            transform transition-[transform,width] duration-200 ease-out
            ${sidebarOpen ? "translate-x-0" : "-translate-x-full xl:translate-x-0"}
            ${desktopSidebarCollapsed ? "xl:w-0 xl:border-r-0 xl:overflow-hidden xl:pointer-events-none" : "xl:w-72"}
          `}
        >
          {sidebarContent}
        </aside>

        {/* Mobile overlay when sidebar open */}
        <button
          type="button"
          onClick={() => setSidebarOpen(false)}
          className={`
            fixed inset-0 bg-black/50 z-30 xl:hidden
            ${sidebarOpen ? "block" : "hidden"}
          `}
          aria-label="Close sidebar"
        />

        {/* Delete confirmation modal */}
        {documentToDelete && (
          <DeleteDocumentModal
            document={documentToDelete}
            deleting={deletingInProgress}
            onConfirm={handleConfirmDelete}
            onCancel={() => setDocumentToDelete(null)}
          />
        )}

        {/* Main: chat or empty state */}
        <main className="flex-1 min-w-0 min-h-0 flex flex-col p-4 xl:p-6">
          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-6">
              <h2
                className="text-4xl font-bold font-cormorant italic text-lapis-400 quaero-logo-loading"
                aria-hidden
              >
                Quaero
              </h2>
              <p className="text-empty">Loading your documents...</p>
            </div>
          ) : selectedDocument ? (
            <div ref={workspaceRef} className="flex-1 min-h-0 flex flex-col">
              {useTabLayout && (
                <div className="mb-3 inline-flex w-full max-w-md self-center rounded-lg border border-zinc-800 bg-zinc-900 p-1">
                <button
                  type="button"
                  onClick={() => setMobileTab("pdf")}
                  className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 ${
                    mobileTab === "pdf"
                      ? "bg-lapis-600 text-white"
                      : "text-zinc-300 hover:bg-zinc-800"
                  }`}
                >
                  PDF
                </button>
                <button
                  type="button"
                  onClick={() => setMobileTab("chat")}
                  className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 ${
                    mobileTab === "chat"
                      ? "bg-lapis-600 text-white"
                      : "text-zinc-300 hover:bg-zinc-800"
                  }`}
                >
                  Chat
                </button>
                </div>
              )}

              <div className={`flex-1 min-h-0 flex gap-4 ${useTabLayout ? "flex-col items-center" : "flex-row"}`}>
                <section
                  className={`${showPdfPane ? "flex" : "hidden"} min-h-0 min-w-0 w-full ${
                    useTabLayout ? "flex-1 max-w-5xl" : "flex-[1.15] basis-[56%]"
                  }`}
                >
                  <PdfViewer
                    documentId={selectedDocument.id}
                    highlightPage={highlightPage}
                    onSessionExpired={handleSessionExpired}
                  />
                </section>

                <section
                  className={`${showChatPane ? "flex" : "hidden"} min-h-0 min-w-0 w-full ${
                    useTabLayout ? "flex-1 max-w-5xl" : "flex-[0.95] basis-[44%]"
                  }`}
                >
                  <ChatWindow
                    document={selectedDocument}
                    onBack={handleBackToDocuments}
                    onCitationClick={handleCitationClick}
                    onSessionExpired={handleSessionExpired}
                  />
                </section>
              </div>
            </div>
          ) : documents.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center px-4 max-w-md mx-auto">
              <div className="p-4 rounded-full bg-zinc-800/50 mb-4">
                <FileUp className="w-12 h-12 text-lapis-400" aria-hidden />
              </div>
              <h2 className="text-xl font-semibold text-zinc-200 mb-2">
                No documents yet
              </h2>
              <p className="text-empty mb-8">
                Upload your first PDF to ask questions and get answers from your
                files.
              </p>
              <div className="w-full">
                <UploadZone onUpload={handleUpload} />
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
              <div className="p-4 rounded-full bg-zinc-800/50 mb-4">
                <PanelLeft className="w-10 h-10 text-lapis-400/80" />
              </div>
              <h2 className="text-xl font-semibold text-zinc-200 mb-2">
                Select a document
              </h2>
              <p className="text-empty max-w-sm">
                Choose a document from the sidebar to start asking questions and
                get answers from your files.
              </p>
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                className="mt-6 xl:hidden px-4 py-2 rounded-lg bg-lapis-600 hover:bg-lapis-500 text-white text-sm font-medium cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              >
                Open documents
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
