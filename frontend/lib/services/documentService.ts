import { requestBlobWithAuth, requestJsonWithAuth } from "@/lib/api/http";
import type {
  Document,
  DocumentListResponse,
  DocumentStatusResponse,
  User,
} from "@/lib/api.types";
import { authService } from "@/lib/services/authService";

export interface DashboardContext {
  user: User;
  documents: Document[];
}

export const documentService = {
  /** Initial dashboard context load (user + document list) to keep orchestration in one place. */
  getDashboardContext: async (): Promise<DashboardContext> => {
    const [user, documentsResponse] = await Promise.all([
      authService.getCurrentUser(),
      documentService.getDocuments(),
    ]);

    return {
      user,
      documents: documentsResponse.documents,
    };
  },

  /** Load the current user's document list. */
  getDocuments: async (): Promise<DocumentListResponse> => {
    return requestJsonWithAuth<DocumentListResponse>("/api/documents/");
  },

  /** Upload a PDF and return the created document model. */
  uploadDocument: async (file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append("file", file);
    return requestJsonWithAuth<Document>("/api/documents/upload", {
      method: "POST",
      body: formData,
    });
  },

  /** Trigger background processing for a document. */
  processDocument: async (
    documentId: number
  ): Promise<{ message: string; document_id: number }> => {
    return requestJsonWithAuth<{ message: string; document_id: number }>(
      `/api/documents/${documentId}/process`,
      { method: "POST" }
    );
  },

  /** Get current processing status for one document. */
  getDocumentStatus: async (documentId: number): Promise<DocumentStatusResponse> => {
    return requestJsonWithAuth<DocumentStatusResponse>(
      `/api/documents/${documentId}/status`
    );
  },

  /** Download a PDF file for local rendering. */
  getDocumentFile: async (documentId: number): Promise<Blob> => {
    return requestBlobWithAuth(`/api/documents/${documentId}/file`);
  },

  /** Delete a document and its persisted content. */
  deleteDocument: async (documentId: number): Promise<{ message: string }> => {
    return requestJsonWithAuth<{ message: string }>(`/api/documents/${documentId}`, {
      method: "DELETE",
    });
  },

  /** Route dashboard logout through the auth domain boundary. */
  logout: async (): Promise<void> => {
    await authService.logout();
  },
};
