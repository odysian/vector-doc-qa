import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  isLoggedIn,
  type Document,
  SessionExpiredError,
} from "@/lib/api";
import { documentService } from "@/lib/services/documentService";

const SPLIT_LAYOUT_MIN_WIDTH = 1120;
const SPLIT_LAYOUT_RESTORE_WIDTH = 1240;
const POLL_INITIAL_DELAY_MS = 3000;
const POLL_MAX_DELAY_MS = 10000;

const getInitialUseTabLayout = (): boolean => {
  if (typeof window === "undefined") return true;
  return window.innerWidth < SPLIT_LAYOUT_MIN_WIDTH;
};

export type MobileTab = "pdf" | "chat";

interface CitationTarget {
  page: number;
  snippet?: string;
}

interface UseDashboardStateOptions {
  onSessionExpired: () => void;
}

export interface UseDashboardStateResult {
  documents: Document[];
  loading: boolean;
  error: string;
  selectedDocument: Document | null;
  sidebarOpen: boolean;
  documentToDelete: Document | null;
  deletingInProgress: boolean;
  highlightPage: number | null;
  highlightSnippet: string | null;
  mobileTab: MobileTab;
  useTabLayout: boolean;
  desktopSidebarCollapsed: boolean;
  workspaceElement: HTMLDivElement | null;
  isDemoUser: boolean;
  hasActiveDocuments: boolean;
  handleUpload: (file: File) => Promise<void>;
  handleLogout: () => Promise<void>;
  handleDocumentClick: (document: Document) => void;
  handleBackToDocuments: () => void;
  handleCitationClick: (citation: CitationTarget) => void;
  handleProcessDocument: (doc: Document) => Promise<void>;
  handleDeleteDocument: (doc: Document) => void;
  handleConfirmDelete: () => Promise<void>;
  handleCancelDelete: () => void;
  setSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>;
  setWorkspaceElement: React.Dispatch<React.SetStateAction<HTMLDivElement | null>>;
  setMobileTab: React.Dispatch<React.SetStateAction<MobileTab>>;
  setDesktopSidebarCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
}

export function useDashboardState({
  onSessionExpired,
}: UseDashboardStateOptions): UseDashboardStateResult {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<Document | null>(null);
  const [deletingInProgress, setDeletingInProgress] = useState(false);
  const [highlightPage, setHighlightPage] = useState<number | null>(null);
  const [highlightSnippet, setHighlightSnippet] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<MobileTab>("chat");
  const [useTabLayout, setUseTabLayout] = useState(getInitialUseTabLayout);
  const [desktopSidebarCollapsed, setDesktopSidebarCollapsed] = useState(false);
  const [workspaceElement, setWorkspaceElement] = useState<HTMLDivElement | null>(null);
  const [isDemoUser, setIsDemoUser] = useState(false);
  const documentsRef = useRef<Document[]>([]);

  const isSessionExpired = useCallback((err: unknown): boolean => {
    return err instanceof SessionExpiredError || (err instanceof ApiError && err.status === 401);
  }, []);

  const handleSessionExpired = useCallback(() => {
    onSessionExpired();
  }, [onSessionExpired]);

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
      const response = await documentService.getDocuments();
      setDocuments(response.documents);
    } catch (err) {
      handleApiError(err, "Failed to load documents");
    }
  }, [handleApiError]);

  useEffect(() => {
    if (!isLoggedIn()) return handleSessionExpired();
    let cancelled = false;

    const loadInitialData = async () => {
      try {
        const dashboardContext = await documentService.getDashboardContext();
        if (cancelled) return;
        setIsDemoUser(dashboardContext.user.is_demo);
        setDocuments(dashboardContext.documents);
      } catch (err) {
        if (!cancelled) {
          handleApiError(err, "Failed to load documents");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadInitialData();

    return () => {
      cancelled = true;
    };
  }, [handleApiError, handleSessionExpired]);

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

  const hasActiveDocuments = documents.some(
    (doc) => doc.status === "pending" || doc.status === "processing"
  );

  useEffect(() => {
    if (loading || !hasActiveDocuments) return;

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let delayMs = POLL_INITIAL_DELAY_MS;

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
        targetIds.map((id) => documentService.getDocumentStatus(id))
      );

      if (cancelled) return;

      let shouldRedirectToLogin = false;
      let hadPollFailures = false;
      const missingIds = new Set<number>();
      const statusById = new Map<number, Awaited<ReturnType<typeof documentService.getDocumentStatus>>>();

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
        delayMs = Math.min(delayMs * 2, POLL_MAX_DELAY_MS);
      } else {
        delayMs = Math.min(Math.floor(delayMs * 1.5), POLL_MAX_DELAY_MS);
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
    if (!workspaceElement) return;

    let frameId: number | null = null;

    const updateLayoutMode = (width: number) => {
      setUseTabLayout((current) => {
        if (current) {
          return width < SPLIT_LAYOUT_RESTORE_WIDTH;
        }
        return width < SPLIT_LAYOUT_MIN_WIDTH;
      });
    };

    updateLayoutMode(Math.floor(workspaceElement.clientWidth));

    const observer = new ResizeObserver((entries) => {
      const [entry] = entries;
      if (!entry) return;

      if (frameId !== null) window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(() => {
        updateLayoutMode(Math.floor(entry.contentRect.width));
      });
    });

    observer.observe(workspaceElement);

    return () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      observer.disconnect();
    };
  }, [workspaceElement]);

  const handleUpload = async (file: File) => {
    setError("");
    try {
      await documentService.uploadDocument(file);
      await loadDocuments();
    } catch (err) {
      handleApiError(err, "Upload failed");
    }
  };

  const handleLogout = async () => {
    await documentService.logout();
    handleSessionExpired();
  };

  const handleDocumentClick = (document: Document) => {
    if (document.status !== "completed") return;
    setSelectedDocument(document);
    setHighlightPage(null);
    setHighlightSnippet(null);
    setMobileTab("chat");
    setSidebarOpen(false);
  };

  const handleBackToDocuments = () => {
    setSelectedDocument(null);
    setHighlightPage(null);
    setHighlightSnippet(null);
    setSidebarOpen(true);
  };

  const handleCitationClick = ({ page, snippet }: CitationTarget) => {
    const nextSnippet = snippet?.trim() || null;
    setMobileTab("pdf");
    setHighlightSnippet(nextSnippet);
    setHighlightPage((current) => {
      if (current === page) {
        setHighlightSnippet(null);
        window.setTimeout(() => {
          setHighlightSnippet(nextSnippet);
          setHighlightPage(page);
        }, 0);
        return null;
      }
      return page;
    });
  };

  const handleProcessDocument = async (doc: Document) => {
    setError("");
    try {
      await documentService.processDocument(doc.id);
      await loadDocuments();
    } catch (err) {
      handleApiError(err, "Failed to queue processing");
    }
  };

  const handleDeleteDocument = (doc: Document) => {
    setDocumentToDelete(doc);
  };

  const handleCancelDelete = () => {
    setDocumentToDelete(null);
  };

  const handleConfirmDelete = async () => {
    if (!documentToDelete) return;
    const doc = documentToDelete;
    setDeletingInProgress(true);
    setError("");
    try {
      await documentService.deleteDocument(doc.id);
      setDocumentToDelete(null);
      if (selectedDocument?.id === doc.id) setSelectedDocument(null);
      await loadDocuments();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setDocumentToDelete(null);
      }
      handleApiError(err, "Failed to delete document");
    } finally {
      setDeletingInProgress(false);
    }
  };

  return {
    documents,
    loading,
    error,
    selectedDocument,
    sidebarOpen,
    documentToDelete,
    deletingInProgress,
    highlightPage,
    highlightSnippet,
    mobileTab,
    useTabLayout,
    desktopSidebarCollapsed,
    workspaceElement,
    isDemoUser,
    hasActiveDocuments,
    handleUpload,
    handleLogout,
    handleDocumentClick,
    handleBackToDocuments,
    handleCitationClick,
    handleProcessDocument,
    handleDeleteDocument,
    handleConfirmDelete,
    handleCancelDelete,
    setSidebarOpen,
    setWorkspaceElement,
    setMobileTab,
    setDesktopSidebarCollapsed,
  };
}
