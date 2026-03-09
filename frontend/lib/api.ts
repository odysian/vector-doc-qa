/**
 * Compatibility API facade.
 * Public exports stay stable while domain services own endpoint operations.
 */

import type {
  LoginCredentials,
  RegisterData,
  AuthResponse,
  User,
  Document,
  DocumentListResponse,
  DocumentStatusResponse,
  QueryResponse,
  MessageListResponse,
  PipelineMeta,
} from "./api.types";
import { getCsrfToken, saveAuthTokens } from "./api/http";
import { authService } from "./services/authService";
import { chatService } from "./services/chatService";
import { documentService } from "./services/documentService";

// Re-export so components can do: import { api, Document, ApiError } from "@/lib/api"
export { ApiError } from "./api.types";
export { SessionExpiredError } from "./api.types";
export type {
  Document,
  DocumentStatusResponse,
  SearchResult,
  QueryResponse,
  PipelineMeta,
  MessageResponse,
  MessageListResponse,
} from "./api.types";

interface QueryStreamCallbacks {
  onSources: (sources: QueryResponse["sources"]) => void;
  onToken: (token: string) => void;
  onMeta: (meta: PipelineMeta) => void;
  onDone: (data: { message_id: number }) => void;
  onError: (detail: string) => void;
}

interface QueryStreamOptions {
  signal?: AbortSignal;
}

/**
 * Instant auth check based on local CSRF token presence.
 * Use for UI routing decisions only.
 */
export function isLoggedIn(): boolean {
  return getCsrfToken() !== null;
}

/** Persist CSRF token from auth response into localStorage. */
export function saveTokens(tokens: AuthResponse): void {
  saveAuthTokens(tokens);
}

const DEMO_CREDENTIALS: LoginCredentials = {
  username: "demo",
  password: "demo",
};

/** Log in with seeded demo credentials and persist csrf token. */
export async function loginAsDemo(): Promise<void> {
  const response = await api.login(DEMO_CREDENTIALS);
  saveTokens(response);
}

/**
 * Stable public API surface for existing callers.
 * Implementations delegate to domain services.
 */
export const api = {
  register: async (data: RegisterData): Promise<User> => {
    return authService.register(data);
  },

  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    return authService.loginRaw(credentials);
  },

  logout: async (): Promise<void> => {
    await authService.logout();
  },

  getCurrentUser: async (): Promise<User> => {
    return authService.getCurrentUser();
  },

  getDocuments: async (): Promise<DocumentListResponse> => {
    return documentService.getDocuments();
  },

  uploadDocument: async (file: File): Promise<Document> => {
    return documentService.uploadDocument(file);
  },

  processDocument: async (
    documentId: number
  ): Promise<{ message: string; document_id: number }> => {
    return documentService.processDocument(documentId);
  },

  getDocumentStatus: async (documentId: number): Promise<DocumentStatusResponse> => {
    return documentService.getDocumentStatus(documentId);
  },

  getDocumentFile: async (documentId: number): Promise<Blob> => {
    return documentService.getDocumentFile(documentId);
  },

  deleteDocument: async (documentId: number): Promise<{ message: string }> => {
    return documentService.deleteDocument(documentId);
  },

  queryDocument: async (
    documentId: number,
    query: string
  ): Promise<QueryResponse> => {
    return chatService.queryDocument(documentId, query);
  },

  queryDocumentStream: async (
    documentId: number,
    query: string,
    callbacks: QueryStreamCallbacks,
    options: QueryStreamOptions = {}
  ): Promise<void> => {
    await chatService.queryDocumentStream(documentId, query, callbacks, options);
  },

  getMessages: async (documentId: number): Promise<MessageListResponse> => {
    return chatService.getMessages(documentId);
  },
};
