/**
 * Dashboard: sidebar layout. Documents/workspaces in left sidebar; chat in main area.
 * Responsive: sidebar is fixed on desktop, drawer on mobile.
 */
"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import { PanelLeft, X, FileUp, Settings2 } from "lucide-react";
import { UploadZone } from "../components/dashboard/UploadZone";
import { DocumentList } from "../components/dashboard/DocumentList";
import { ChatWindow } from "../components/dashboard/ChatWindow";
import { DeleteDocumentModal } from "../components/dashboard/DeleteDocumentModal";
import { DeleteWorkspaceModal } from "../components/dashboard/DeleteWorkspaceModal";
import { WorkspaceList } from "../components/dashboard/WorkspaceList";
import { WorkspaceSidebar } from "../components/dashboard/WorkspaceSidebar";
import { DocumentPicker } from "../components/dashboard/DocumentPicker";
import { useDashboardState } from "@/lib/hooks/useDashboardState";

const SIDEBAR_WIDTH = "w-72";
const MAX_DOCUMENTS_PER_WORKSPACE = 20;
const PdfViewer = dynamic(
  () =>
    import("../components/dashboard/PdfViewer").then((mod) => mod.PdfViewer),
  { ssr: false },
);

export default function DashboardPage() {
  const router = useRouter();
  const [documentPickerOpen, setDocumentPickerOpen] = useState(false);
  const [workspaceToDelete, setWorkspaceToDelete] = useState<{
    id: number;
    name: string;
    clearSelection: boolean;
  } | null>(null);
  const [deletingWorkspace, setDeletingWorkspace] = useState(false);
  const handleSessionExpired = useCallback(() => {
    router.push("/login");
  }, [router]);
  const {
    documents,
    loading,
    error,
    selectedDocument,
    dashboardMode,
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
    layoutMode,
    desktopSidebarCollapsed,
    debugMode,
    isDemoUser,
    toggleDebugMode,
    clearError,
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
    setMobileTab,
    setDesktopSidebarCollapsed,
  } = useDashboardState({ onSessionExpired: handleSessionExpired });

  const handleConfirmWorkspaceDelete = useCallback(async () => {
    if (!workspaceToDelete) return;

    setDeletingWorkspace(true);
    const deleted = await handleDeleteWorkspace(
      workspaceToDelete.id,
      workspaceToDelete.clearSelection,
    );

    if (deleted) {
      setWorkspaceToDelete(null);
    }
    setDeletingWorkspace(false);
  }, [handleDeleteWorkspace, workspaceToDelete]);

  const handleCancelWorkspaceDelete = useCallback(() => {
    if (deletingWorkspace) return;
    setWorkspaceToDelete(null);
  }, [deletingWorkspace]);

  const viewerDocument = useMemo(() => {
    if (dashboardMode === "documents") {
      return selectedDocument;
    }

    if (!selectedWorkspace || !viewerDocumentId) {
      return null;
    }

    return (
      selectedWorkspace.documents.find((doc) => doc.id === viewerDocumentId) ||
      null
    );
  }, [dashboardMode, selectedDocument, selectedWorkspace, viewerDocumentId]);

  const availableWorkspaceDocuments = useMemo(() => {
    if (!selectedWorkspace) return [];
    const currentWorkspaceDocIds = new Set(
      selectedWorkspace.documents.map((doc) => doc.id),
    );
    return documents.filter(
      (doc) =>
        doc.status === "completed" && !currentWorkspaceDocIds.has(doc.id),
    );
  }, [documents, selectedWorkspace]);

  const workspaceCapacityRemaining = Math.max(
    MAX_DOCUMENTS_PER_WORKSPACE - (selectedWorkspace?.documents.length ?? 0),
    0,
  );

  const useTabLayout = layoutMode !== "desktop";
  const isDesktopLayout = layoutMode === "desktop";
  const showPdfPane = !useTabLayout || mobileTab === "pdf";
  const showChatPane = !useTabLayout || mobileTab === "chat";
  const chatContextTitle =
    dashboardMode === "workspaces"
      ? selectedWorkspace?.name || viewerDocument?.filename || "Workspace"
      : viewerDocument?.filename || "Document";
  const chatContextDate = viewerDocument?.uploaded_at || "";
  const viewerBackLabel =
    dashboardMode === "workspaces" ? "Back to Workspaces" : "Back to Documents";
  const handleViewerBack =
    dashboardMode === "workspaces" ? handleBackToWorkspaces : handleBackToDocuments;
  const errorBanner = error ? (
    <div className="ui-alert-error text-body-sm flex items-start gap-2">
      <p className="flex-1 min-w-0">{error}</p>
      <button
        type="button"
        onClick={clearError}
        className="ui-btn ui-btn-ghost ui-btn-sm"
        aria-label="Dismiss error"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  ) : null;

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <div
        className={`flex items-center justify-between p-3 border-b border-zinc-800 ${
          isDesktopLayout ? "border-b-0" : ""
        }`}
      >
        <div className="ui-segmented">
          <button
            type="button"
            onClick={() => setDashboardMode("documents")}
            className={`ui-segmented-option ui-segmented-option-sm ${dashboardMode === "documents" ? "ui-segmented-option-active" : ""}`}
          >
            Documents
          </button>
          <button
            type="button"
            onClick={() => setDashboardMode("workspaces")}
            className={`ui-segmented-option ui-segmented-option-sm ${dashboardMode === "workspaces" ? "ui-segmented-option-active" : ""}`}
          >
            Workspaces
          </button>
        </div>
        <button
          type="button"
          onClick={() => setSidebarOpen(false)}
          className={`ui-btn ui-btn-ghost ui-btn-sm ${isDesktopLayout ? "hidden" : ""}`}
          aria-label="Close sidebar"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {dashboardMode === "documents" ? (
          <>
            <UploadZone
              onUpload={handleUpload}
              disabled={isDemoUser}
              disabledReason="Create an account to upload your own documents."
            />
            {errorBanner}
            {loading ? (
              <p className="text-empty">Loading...</p>
            ) : (
              <DocumentList
                documents={documents}
                onDocumentClick={handleDocumentClick}
                onProcessDocument={handleProcessDocument}
                onDeleteDocument={handleDeleteDocument}
                hideDeleteActions={isDemoUser}
              />
            )}
          </>
        ) : selectedWorkspace ? (
          <>
            {errorBanner}
            <WorkspaceSidebar
              workspace={selectedWorkspace}
              activeDocumentId={viewerDocumentId}
              onDocumentClick={(doc) => handleViewerDocumentSwitch(doc.id)}
              onAddDocuments={() => setDocumentPickerOpen(true)}
              onDeleteWorkspace={() =>
                setWorkspaceToDelete({
                  id: selectedWorkspace.id,
                  name: selectedWorkspace.name,
                  clearSelection: true,
                })
              }
              onRemoveDocument={(docId) => {
                void handleRemoveWorkspaceDocument(docId);
              }}
              onBack={handleBackToWorkspaces}
              disabled={isDemoUser}
            />
          </>
        ) : (
          <>
            {errorBanner}
            {workspacesLoading ? (
              <p className="text-empty">Loading workspaces...</p>
            ) : (
              <WorkspaceList
                workspaces={workspaces}
                onWorkspaceClick={(workspace) => {
                  void handleWorkspaceClick(workspace);
                }}
                onCreate={handleCreateWorkspace}
                disabled={isDemoUser}
              />
            )}
          </>
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
              className={`ui-btn ui-btn-ghost ui-btn-sm ${isDesktopLayout ? "hidden" : ""}`}
              aria-label="Toggle sidebar"
            >
              <PanelLeft className="w-5 h-5" />
            </button>
            <button
              type="button"
              onClick={() =>
                setDesktopSidebarCollapsed((collapsed) => !collapsed)
              }
              className={`ui-btn ui-btn-ghost ui-btn-sm ${isDesktopLayout ? "inline-flex" : "hidden"}`}
              aria-label={
                desktopSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
              }
              title={
                desktopSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
              }
            >
              <PanelLeft
                className={`w-5 h-5 transition-transform ${desktopSidebarCollapsed ? "rotate-180" : ""}`}
              />
            </button>
            <h1 className="text-3xl leading-none font-bold font-cormorant italic text-lapis-400">
              Quaero
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggleDebugMode}
              aria-pressed={debugMode}
              className={`ui-btn ui-btn-sm ${
                debugMode ? "ui-btn-secondary" : "ui-btn-ghost"
              }`}
            >
              <Settings2 size={14} aria-hidden />
              <span>{debugMode ? "Debug on" : "Debug off"}</span>
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="ui-btn ui-btn-ghost ui-btn-sm"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Sidebar: drawer on mobile, fixed on desktop */}
        <aside
          className={`
            shrink-0 flex flex-col bg-zinc-900 border-r border-zinc-800
            transform transition-[transform,width] duration-200 ease-out
            ${
              isDesktopLayout
                ? "relative top-0 left-auto bottom-auto z-auto translate-x-0"
                : `fixed left-0 top-14 bottom-0 z-40 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`
            }
            ${isDesktopLayout && desktopSidebarCollapsed ? "w-0 border-r-0 overflow-hidden pointer-events-none" : "w-72"}
          `}
        >
          {sidebarContent}
        </aside>

        {/* Mobile overlay when sidebar open */}
        <button
          type="button"
          onClick={() => setSidebarOpen(false)}
          className={`
            fixed inset-0 bg-black/50 z-30
            ${!isDesktopLayout && sidebarOpen ? "block" : "hidden"}
          `}
          aria-label="Close sidebar"
        />

        {/* Delete confirmation modal */}
        {documentToDelete && (
          <DeleteDocumentModal
            document={documentToDelete}
            deleting={deletingInProgress}
            onConfirm={handleConfirmDelete}
            onCancel={handleCancelDelete}
          />
        )}

        {workspaceToDelete && (
          <DeleteWorkspaceModal
            workspaceName={workspaceToDelete.name}
            deleting={deletingWorkspace}
            onConfirm={() => {
              void handleConfirmWorkspaceDelete();
            }}
            onCancel={handleCancelWorkspaceDelete}
          />
        )}

        {documentPickerOpen && selectedWorkspace && (
          <DocumentPicker
            availableDocuments={availableWorkspaceDocuments}
            maxDocuments={workspaceCapacityRemaining}
            onAdd={handleAddWorkspaceDocuments}
            onClose={() => setDocumentPickerOpen(false)}
          />
        )}

        {/* Main area */}
        <main className="flex-1 min-w-0 min-h-0 flex flex-col p-4 xl:p-6">
          {isDemoUser && (
            <div className="mb-4 rounded-lg border border-amber-700/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              You&apos;re using a demo account.{" "}
              <Link
                href="/register"
                className="font-medium underline hover:text-amber-200"
              >
                Create an account
              </Link>{" "}
              to upload your own documents.
            </div>
          )}
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
          ) : dashboardMode === "workspaces" &&
            selectedWorkspace &&
            selectedWorkspace.documents.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center px-4 max-w-md mx-auto">
              <div className="p-4 rounded-full bg-zinc-800/50 mb-4">
                <FileUp className="w-12 h-12 text-lapis-400" aria-hidden />
              </div>
              <h2 className="text-xl font-semibold text-zinc-200 mb-2">
                Add documents to this workspace
              </h2>
              <p className="text-empty mb-8">
                Add documents to start asking cross-document questions with
                citations.
              </p>
              <button
                type="button"
                onClick={() => setDocumentPickerOpen(true)}
                disabled={isDemoUser}
                className="ui-btn ui-btn-primary ui-btn-md"
              >
                Add documents
              </button>
            </div>
          ) : (dashboardMode === "documents" && selectedDocument) ||
            (dashboardMode === "workspaces" &&
              selectedWorkspace &&
              viewerDocument) ? (
            <div className="flex-1 min-h-0 flex flex-col">
              {useTabLayout && (
                <div className="mb-3 ui-segmented w-full max-w-md self-center">
                  <button
                    type="button"
                    onClick={() => setMobileTab("pdf")}
                    className={`ui-segmented-option ui-segmented-option-md flex-1 ${mobileTab === "pdf" ? "ui-segmented-option-active" : ""}`}
                  >
                    PDF
                  </button>
                  <button
                    type="button"
                    onClick={() => setMobileTab("chat")}
                    className={`ui-segmented-option ui-segmented-option-md flex-1 ${mobileTab === "chat" ? "ui-segmented-option-active" : ""}`}
                  >
                    Chat
                  </button>
                </div>
              )}

              <div
                className={`flex-1 min-h-0 flex gap-4 ${useTabLayout ? "flex-col items-center" : "flex-row"}`}
              >
                <section
                  className={`${showPdfPane ? "flex" : "hidden"} min-h-0 min-w-0 w-full ${
                    useTabLayout ? "flex-1 max-w-5xl" : "flex-[1.2_0_60%]"
                  }`}
                >
                  <div className="w-full h-full min-h-0 flex flex-col">
                    {viewerDocument && (
                      <PdfViewer
                        documentId={viewerDocument.id}
                        filename={viewerDocument.filename}
                        uploadedAt={viewerDocument.uploaded_at}
                        onBack={handleViewerBack}
                        backLabel={viewerBackLabel}
                        highlightPage={highlightPage}
                        highlightSnippet={highlightSnippet}
                        onSessionExpired={handleSessionExpired}
                      />
                    )}
                  </div>
                </section>

                <section
                  className={`${showChatPane ? "flex" : "hidden"} min-h-0 min-w-0 w-full ${
                    useTabLayout
                      ? "flex-1 max-w-5xl"
                      : "flex-[0.9_0_40%] min-w-72"
                  }`}
                >
                  {dashboardMode === "documents" && selectedDocument ? (
                    <ChatWindow
                      document={selectedDocument}
                      onBack={handleBackToDocuments}
                      debugMode={debugMode}
                      onToggleDebugMode={toggleDebugMode}
                      showContextBar={useTabLayout}
                      contextTitle={chatContextTitle}
                      contextDate={chatContextDate}
                      onCitationClick={handleCitationClick}
                      onSessionExpired={handleSessionExpired}
                    />
                  ) : selectedWorkspace ? (
                    <ChatWindow
                      workspaceId={selectedWorkspace.id}
                      workspaceName={selectedWorkspace.name}
                      workspaceDocumentIds={selectedWorkspace.documents.map(
                        (doc) => doc.id,
                      )}
                      onBack={handleBackToWorkspaces}
                      debugMode={debugMode}
                      onToggleDebugMode={toggleDebugMode}
                      showContextBar={useTabLayout}
                      contextTitle={chatContextTitle}
                      contextDate={chatContextDate}
                      onCitationClick={handleCitationClick}
                      onSessionExpired={handleSessionExpired}
                    />
                  ) : null}
                </section>
              </div>
            </div>
          ) : dashboardMode === "workspaces" ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
              <div className="p-4 rounded-full bg-zinc-800/50 mb-4">
                <PanelLeft className="w-10 h-10 text-lapis-400/80" />
              </div>
              <h2 className="text-xl font-semibold text-zinc-200 mb-2">
                Select a workspace
              </h2>
              <p className="text-empty max-w-sm">
                Choose a workspace from the sidebar to start cross-document
                chat.
              </p>
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
                <UploadZone
                  onUpload={handleUpload}
                  disabled={isDemoUser}
                  disabledReason="Create an account to upload your own documents."
                />
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
                onClick={() => {
                  setSidebarOpen(true);
                  setDesktopSidebarCollapsed(false);
                }}
                className="mt-6 ui-btn ui-btn-primary ui-btn-md"
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
