import { api, type Document } from "@/lib/api";
import type { User } from "@/lib/api.types";

export interface DashboardContext {
  user: User;
  documents: Document[];
}

export const documentService = {
  /** Initial dashboard context load (user + document list) to keep orchestration in one place. */
  getDashboardContext: async (): Promise<DashboardContext> => {
    const [user, documentsResponse] = await Promise.all([
      api.getCurrentUser(),
      api.getDocuments(),
    ]);

    return {
      user,
      documents: documentsResponse.documents,
    };
  },

  getDocuments: () => api.getDocuments(),
  uploadDocument: (file: File) => api.uploadDocument(file),
  processDocument: (documentId: number) => api.processDocument(documentId),
  getDocumentStatus: (documentId: number) => api.getDocumentStatus(documentId),
  deleteDocument: (documentId: number) => api.deleteDocument(documentId),
  logout: () => api.logout(),
};
