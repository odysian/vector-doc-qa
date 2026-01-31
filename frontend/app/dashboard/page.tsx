/**
 * Dashboard: main app view after login. Lists documents, uploads PDFs, and
 * opens a document in ChatWindow for RAG Q&A. Redirects to login if not authenticated.
 */
"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, type Document, ApiError } from "@/lib/api";
import { UploadZone } from "../components/dashboard/UploadZone";
import { DocumentList } from "../components/dashboard/DocumentList";
import { ChatWindow } from "../components/dashboard/ChatWindow";

/**
 * Renders header (logo + logout), then either document list + upload zone or
 * ChatWindow when a document is selected. Loads documents on mount; 401 responses redirect to login.
 */
export default function DashboardPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const router = useRouter();

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
    const token = localStorage.getItem("token");
    if (!token) return router.push("/login");
    loadDocuments();
  }, [router, loadDocuments]);

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

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  const handleDocumentClick = (document: Document) => {
    if (document.status !== "completed") return;
    setSelectedDocument(document);
  };

  const handleBackToDocuments = () => {
    setSelectedDocument(null);
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
        setError("Failed to start processing");
      }
    }
  };

  const handleDeleteDocument = async (doc: Document) => {
    if (!confirm(`Delete "${doc.filename}"? This cannot be undone.`)) return;
    setError("");
    try {
      await api.deleteDocument(doc.id);
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
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Header */}
      <div className="border-b border-zinc-800 bg-zinc-900/50">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-3xl font-bold font-cormorant italic text-lapis-400">
            Quaero
          </h1>
          <button
            type="button"
            onClick={handleLogout}
            className="text-sm text-zinc-400 hover:text-zinc-300 cursor-pointer"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center min-h-[40vh] gap-6">
            <h2
              className="text-4xl font-bold font-cormorant italic text-lapis-400 quaero-logo-loading"
              aria-hidden
            >
              Quaero
            </h2>
            <p className="text-zinc-500 text-sm">Loading your documents...</p>
          </div>
        ) : selectedDocument ? (
          <ChatWindow document={selectedDocument} onBack={handleBackToDocuments} />
        ) : (
          <>
            <UploadZone onUpload={handleUpload} />

            {error && (
              <div className="mb-6 bg-red-900/20 border border-red-900/50 text-red-400 p-4 rounded-lg">
                {error}
              </div>
            )}

            <h2 className="text-xl font-semibold text-zinc-100 mb-4">
              Your Documents ({documents.length})
            </h2>

            <DocumentList
              documents={documents}
              onDocumentClick={handleDocumentClick}
              onProcessDocument={handleProcessDocument}
              onDeleteDocument={handleDeleteDocument}
            />
          </>
        )}
      </div>
    </div>
  );
}
