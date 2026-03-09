/**
 * Dashboard: sidebar layout. Documents in left sidebar; chat in main area.
 * Responsive: sidebar is fixed on desktop, drawer on mobile. Zinc + lapis theme.
 */
"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import { PanelLeft, X, FileUp } from "lucide-react";
import { UploadZone } from "../components/dashboard/UploadZone";
import { DocumentList } from "../components/dashboard/DocumentList";
import { ChatWindow } from "../components/dashboard/ChatWindow";
import { DeleteDocumentModal } from "../components/dashboard/DeleteDocumentModal";
import { useDashboardState } from "@/lib/hooks/useDashboardState";

const SIDEBAR_WIDTH = "w-72";
const PdfViewer = dynamic(
  () => import("../components/dashboard/PdfViewer").then((mod) => mod.PdfViewer),
  { ssr: false }
);

export default function DashboardPage() {
  const router = useRouter();
  const handleSessionExpired = useCallback(() => {
    router.push("/login");
  }, [router]);
  const {
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
    isDemoUser,
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
  } = useDashboardState({ onSessionExpired: handleSessionExpired });

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
        <UploadZone
          onUpload={handleUpload}
          disabled={isDemoUser}
          disabledReason="Create an account to upload your own documents."
        />
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
            hideDeleteActions={isDemoUser}
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
            onCancel={handleCancelDelete}
          />
        )}

        {/* Main: chat or empty state */}
        <main className="flex-1 min-w-0 min-h-0 flex flex-col p-4 xl:p-6">
          {isDemoUser && (
            <div className="mb-4 rounded-lg border border-amber-700/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              You&apos;re using a demo account.{" "}
              <Link href="/register" className="font-medium underline hover:text-amber-200">
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
          ) : selectedDocument ? (
            <div ref={setWorkspaceElement} className="flex-1 min-h-0 flex flex-col">
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
                    useTabLayout ? "flex-1 max-w-5xl" : "flex-[1.15_0_56%]"
                  }`}
                >
                  <PdfViewer
                    documentId={selectedDocument.id}
                    highlightPage={highlightPage}
                    highlightSnippet={highlightSnippet}
                    onSessionExpired={handleSessionExpired}
                  />
                </section>

                <section
                  className={`${showChatPane ? "flex" : "hidden"} min-h-0 min-w-0 w-full ${
                    useTabLayout ? "flex-1 max-w-5xl" : "flex-[0.95_0_44%]"
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
