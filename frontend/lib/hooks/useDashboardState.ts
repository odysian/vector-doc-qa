import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  isLoggedIn,
  type Document,
  type Workspace,
  type WorkspaceDetail,
  SessionExpiredError,
} from "@/lib/api";
import { authService } from "@/lib/services/authService";
import { documentService } from "@/lib/services/documentService";
import { workspaceService } from "@/lib/services/workspaceService";

const SPLIT_LAYOUT_MIN_WIDTH = 1120;
const SPLIT_LAYOUT_RESTORE_WIDTH = 1240;
const POLL_INITIAL_DELAY_MS = 3000;
const POLL_MAX_DELAY_MS = 10000;

const getInitialUseTabLayout = (): boolean => {
  if (typeof window === "undefined") return true;
  return window.innerWidth < SPLIT_LAYOUT_MIN_WIDTH;
};

export type MobileTab = "pdf" | "chat";
export type DashboardMode = "documents" | "workspaces";

interface CitationTarget {
  page: number;
  snippet?: string;
  documentId?: number;
}

interface UseDashboardStateOptions {
  onSessionExpired: () => void;
}

export interface UseDashboardStateResult {
  documents: Document[];
  loading: boolean;
  error: string;
  selectedDocument: Document | null;
  dashboardMode: DashboardMode;
  workspaces: Workspace[];
  selectedWorkspace: WorkspaceDetail | null;
  viewerDocumentId: number | null;
  workspacesLoading: boolean;
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
  setDashboardMode: (mode: DashboardMode) => void;
  handleWorkspaceClick: (workspace: Workspace) => Promise<void>;
  handleCreateWorkspace: (name: string) => Promise<void>;
  handleDeleteWorkspace: (workspaceId: number, clearSelection?: boolean) => Promise<boolean>;
  handleAddWorkspaceDocuments: (documentIds: number[]) => Promise<boolean>;
  handleRemoveWorkspaceDocument: (documentId: number) => Promise<boolean>;
  handleViewerDocumentSwitch: (documentId: number) => void;
  handleBackToWorkspaces: () => void;
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
  const [dashboardModeState, setDashboardModeState] = useState<DashboardMode>("documents");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<WorkspaceDetail | null>(null);
  const [viewerDocumentId, setViewerDocumentId] = useState<number | null>(null);
  const [workspacesLoading, setWorkspacesLoading] = useState(false);
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

  const loadWorkspaces = useCallback(async () => {
    try {
      setWorkspacesLoading(true);
      const response = await workspaceService.getWorkspaces();
      setWorkspaces(response.workspaces);
    } catch (err) {
      handleApiError(err, "Failed to load workspaces");
    } finally {
      setWorkspacesLoading(false);
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
    await authService.logout();
    handleSessionExpired();
  };

  const handleDocumentClick = (document: Document) => {
    if (document.status !== "completed") return;
    setDashboardModeState("documents");
    setSelectedWorkspace(null);
    setViewerDocumentId(null);
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

  const handleCitationClick = ({ page, snippet, documentId }: CitationTarget) => {
    const nextSnippet = snippet?.trim() || null;

    if (selectedWorkspace && documentId) {
      const hasDocument = selectedWorkspace.documents.some((doc) => doc.id === documentId);
      if (hasDocument) {
        setViewerDocumentId(documentId);
      }
    }

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

  const setDashboardMode = useCallback((mode: DashboardMode) => {
    setError("");
    setDashboardModeState(mode);

    if (mode === "documents") {
      setSelectedWorkspace(null);
      setViewerDocumentId(null);
      return;
    }

    setSelectedDocument(null);
    setHighlightPage(null);
    setHighlightSnippet(null);
    setMobileTab("chat");
    void loadWorkspaces();
  }, [loadWorkspaces]);

  const handleWorkspaceClick = useCallback(async (workspace: Workspace) => {
    setError("");
    try {
      setWorkspacesLoading(true);
      const workspaceDetail = await workspaceService.getWorkspace(workspace.id);
      setDashboardModeState("workspaces");
      setSelectedDocument(null);
      setSelectedWorkspace(workspaceDetail);
      setViewerDocumentId(workspaceDetail.documents[0]?.id ?? null);
      setHighlightPage(null);
      setHighlightSnippet(null);
      setMobileTab("chat");
      setSidebarOpen(false);
    } catch (err) {
      handleApiError(err, "Failed to load workspace");
    } finally {
      setWorkspacesLoading(false);
    }
  }, [handleApiError]);

  const handleCreateWorkspace = useCallback(async (name: string) => {
    const trimmedName = name.trim();
    if (!trimmedName) return;

    setError("");
    try {
      const workspace = await workspaceService.createWorkspace(trimmedName);
      setWorkspaces((prev) => [workspace, ...prev]);
    } catch (err) {
      handleApiError(err, "Failed to create workspace");
    }
  }, [handleApiError]);

  const handleDeleteWorkspace = useCallback(async (workspaceId: number, clearSelection = false) => {
    setError("");
    try {
      await workspaceService.deleteWorkspace(workspaceId);
      setWorkspaces((prev) => prev.filter((workspace) => workspace.id !== workspaceId));
      if (clearSelection) {
        setSelectedWorkspace(null);
        setViewerDocumentId(null);
        setHighlightPage(null);
        setHighlightSnippet(null);
      } else {
        setSelectedWorkspace((current) => (current?.id === workspaceId ? null : current));
      }
      return true;
    } catch (err) {
      handleApiError(err, "Failed to delete workspace");
      return false;
    }
  }, [handleApiError]);

  const handleAddWorkspaceDocuments = useCallback(async (documentIds: number[]) => {
    if (!selectedWorkspace || documentIds.length === 0) return false;

    setError("");
    try {
      const workspace = await workspaceService.addWorkspaceDocuments(
        selectedWorkspace.id,
        documentIds
      );
      setSelectedWorkspace(workspace);
      setViewerDocumentId((current) => {
        if (current && workspace.documents.some((doc) => doc.id === current)) {
          return current;
        }
        return workspace.documents[0]?.id ?? null;
      });
      setWorkspaces((prev) =>
        prev.map((item) =>
          item.id === workspace.id
            ? {
              ...item,
              name: workspace.name,
              updated_at: workspace.updated_at,
              document_count: workspace.document_count,
            }
            : item
        )
      );
      return true;
    } catch (err) {
      handleApiError(err, "Failed to add documents to workspace");
      return false;
    }
  }, [handleApiError, selectedWorkspace]);

  const handleRemoveWorkspaceDocument = useCallback(async (documentId: number) => {
    if (!selectedWorkspace) return false;

    setError("");
    try {
      const workspace = await workspaceService.removeWorkspaceDocument(
        selectedWorkspace.id,
        documentId
      );
      setSelectedWorkspace(workspace);
      setViewerDocumentId((current) => {
        if (!workspace.documents.length) return null;
        if (current && workspace.documents.some((doc) => doc.id === current)) {
          return current;
        }
        return workspace.documents[0].id;
      });
      setWorkspaces((prev) =>
        prev.map((item) =>
          item.id === workspace.id
            ? {
              ...item,
              name: workspace.name,
              updated_at: workspace.updated_at,
              document_count: workspace.document_count,
            }
            : item
        )
      );
      return true;
    } catch (err) {
      handleApiError(err, "Failed to remove document from workspace");
      return false;
    }
  }, [handleApiError, selectedWorkspace]);

  const handleViewerDocumentSwitch = useCallback((documentId: number) => {
    setViewerDocumentId(documentId);
    setHighlightPage(null);
    setHighlightSnippet(null);
  }, []);

  const handleBackToWorkspaces = useCallback(() => {
    setSelectedWorkspace(null);
    setViewerDocumentId(null);
    setHighlightPage(null);
    setHighlightSnippet(null);
    setSidebarOpen(true);
    void loadWorkspaces();
  }, [loadWorkspaces]);

  return {
    documents,
    loading,
    error,
    selectedDocument,
    dashboardMode: dashboardModeState,
    workspaces,
    selectedWorkspace,
    viewerDocumentId,
    workspacesLoading,
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
    setDashboardMode,
    handleWorkspaceClick,
    handleCreateWorkspace,
    handleDeleteWorkspace,
    handleAddWorkspaceDocuments,
    handleRemoveWorkspaceDocument,
    handleViewerDocumentSwitch,
    handleBackToWorkspaces,
    setSidebarOpen,
    setWorkspaceElement,
    setMobileTab,
    setDesktopSidebarCollapsed,
  };
}
