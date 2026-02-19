/**
 * Dashboard: sidebar layout. Documents in left sidebar; chat in main area.
 * Responsive: sidebar is fixed on desktop, drawer on mobile. Zinc + lapis theme.
 */
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { PanelLeft, X, FileUp } from "lucide-react";
import { api, isLoggedIn, type Document, ApiError } from "@/lib/api";
import { UploadZone } from "../components/dashboard/UploadZone";
import { DocumentList } from "../components/dashboard/DocumentList";
import { ChatWindow } from "../components/dashboard/ChatWindow";
import { DeleteDocumentModal } from "../components/dashboard/DeleteDocumentModal";

const SIDEBAR_WIDTH = "w-72";

export default function DashboardPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null);
  const [deletingInProgress, setDeletingInProgress] = useState(false);
  const documentsRef = useRef<Document[]>([]);
  const router = useRouter();
  const hasActiveDocuments = documents.some(
    (doc) => doc.status === "pending" || doc.status === "processing"
  );

  const loadDocuments = useCallback(async () => {
    try {
      const response = await api.getDocuments();
      setDocuments(response.documents);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          router.push("/login");
          return;
        }
        setError(err.detail);
      } else {
        setError("Failed to load documents");
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!isLoggedIn()) return router.push("/login");
    loadDocuments();
  }, [router, loadDocuments]);

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
        if (reason instanceof ApiError) {
          if (reason.status === 401) {
            shouldRedirectToLogin = true;
            return;
          }
          if (reason.status === 404) {
            missingIds.add(documentId);
            return;
          }
        }

        hadPollFailures = true;
      });

      if (shouldRedirectToLogin) {
        router.push("/login");
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
  }, [hasActiveDocuments, loading, router]);

  const handleUpload = async (file: File) => {
    setError("");
    try {
      await api.uploadDocument(file);
      await loadDocuments();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          router.push("/login");
          return;
        }
        setError(err.detail);
      } else {
        setError("Upload failed");
      }
      throw err;
    }
  };

  const handleLogout = async () => {
    await api.logout();
    router.push("/login");
  };

  const handleDocumentClick = (document: Document) => {
    if (document.status !== "completed") return;
    setSelectedDocument(document);
    setSidebarOpen(false);
  };

  const handleBackToDocuments = () => {
    setSelectedDocument(null);
    setSidebarOpen(true);
  };

  const handleProcessDocument = async (doc: Document) => {
    setError("");
    try {
      await api.processDocument(doc.id);
      await loadDocuments();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          router.push("/login");
          return;
        }
        setError(err.detail);
      } else {
        setError("Failed to queue processing");
      }
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
      if (err instanceof ApiError) {
        if (err.status === 401) {
          router.push("/login");
          return;
        }
        setError(err.detail);
      } else {
        setError("Failed to delete document");
      }
    } finally {
      setDeletingInProgress(false);
    }
  };

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-3 border-b border-zinc-800 lg:border-b-0">
        <h2 className="text-section">Documents</h2>
        <button
          type="button"
          onClick={() => setSidebarOpen(false)}
          className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 lg:hidden cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
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
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Header */}
      <header className="shrink-0 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center justify-between h-14 px-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen((o) => !o)}
              className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 lg:hidden cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
              aria-label="Toggle sidebar"
            >
              <PanelLeft className="w-5 h-5" />
            </button>
            <h1 className="text-2xl font-bold font-cormorant italic text-lapis-400">
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
            fixed left-0 top-14 bottom-0 lg:relative lg:top-0 z-40 lg:z-auto
            transform transition-transform duration-200 ease-out
            ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
          `}
        >
          {sidebarContent}
        </aside>

        {/* Mobile overlay when sidebar open */}
        <button
          type="button"
          onClick={() => setSidebarOpen(false)}
          className={`
            fixed inset-0 bg-black/50 z-30 lg:hidden
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
        <main className="flex-1 min-w-0 flex flex-col p-4 lg:p-6">
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
            <div className="flex-1 min-h-0 flex flex-col">
              <ChatWindow
                document={selectedDocument}
                onBack={handleBackToDocuments}
              />
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
                className="mt-6 lg:hidden px-4 py-2 rounded-lg bg-lapis-600 hover:bg-lapis-500 text-white text-sm font-medium cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-lapis-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
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
