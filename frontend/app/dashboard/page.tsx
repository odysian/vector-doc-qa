// frontend/app/dashboard/page.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, type Document, ApiError } from "@/lib/api";
import { UploadZone } from "../components/dashboard/UploadZone";
import { DocumentList } from "../components/dashboard/DocumentList";
import { ChatWindow } from "../components/dashboard/ChatWindow";

export default function DashboardPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const router = useRouter();

  // Fetch Data
  const loadDocuments = useCallback(async () => {
    try {
      const response = await api.getDocuments();
      setDocuments(response.documents);
    } catch (err) {
      // Handle API errors with proper status code checking
      if (err instanceof ApiError) {
        if (err.status === 401) {
          // Unauthorized - redirect to login
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

  // Handle Action
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
    setSelectedDocument(document);
  };

  const handleBackToDocuments = () => {
    setSelectedDocument(null);
  };

  if (loading) return <div className="p-8 text-zinc-400">Loading...</div>;

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Header */}
      <div className="border-b border-zinc-800 bg-zinc-900/50">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-3xl font-bold font-cormorant italic text-lapis-400">
            Quaero
          </h1>
          <button
            onClick={handleLogout}
            className="text-sm text-zinc-400 hover:text-zinc-300"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        {selectedDocument ? (
          // Show ChatWindow when a document is selected
          <ChatWindow document={selectedDocument} onBack={handleBackToDocuments} />
        ) : (
          // Show document list and upload zone when no document is selected
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

            <DocumentList documents={documents} onDocumentClick={handleDocumentClick} />
          </>
        )}
      </div>
    </div>
  );
}
