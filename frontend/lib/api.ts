/**
 * API client: all HTTP calls to the backend go through this file.
 * Uses path-only URLs; base URL is applied in one place (fullUrl).
 */

import type {
  LoginCredentials,
  RegisterData,
  AuthResponse,
  User,
  Document,
  DocumentListResponse,
  QueryResponse,
  MessageListResponse,
} from "./api.types";
import { ApiError } from "./api.types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Re-export so components can do: import { api, Document, ApiError } from "@/lib/api"
export { ApiError } from "./api.types";
export type {
  Document,
  SearchResult,
  QueryResponse,
  MessageResponse,
  MessageListResponse,
} from "./api.types";

function getToken(): string | null {
  if (typeof window === "undefined") return null; // safe during SSR (Next.js)
  return localStorage.getItem("token");
}

/** Builds full URL from a path; only place that prepends API_URL. */
function fullUrl(path: string): string {
  return `${API_URL}${path}`;
}

/**
 * Sends a request to the backend. Adds Authorization when a token exists (works for
 * login/register too: no token yet, so no header). Omits Content-Type for FormData
 * so the browser can set multipart/form-data with boundary.
 */
async function apiRequest(path: string, options: RequestInit = {}) {
  const token = getToken();
  const isFormData = options.body instanceof FormData;
  const headers: HeadersInit = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  const response = await fetch(fullUrl(path), {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    throw new ApiError(response.status, error.detail || "Request failed");
  }
  return response.json();
}

/**
 * Backend API methods. Use these from components instead of calling fetch directly.
 */
export const api = {
  /** Create a new user account (no auth required). */
  register: async (data: RegisterData): Promise<User> => {
    return apiRequest("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /** Log in; returns access_token for use in later requests. */
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    return apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  },

  /** Get the currently logged-in user (requires auth). */
  getCurrentUser: async (): Promise<User> => {
    return apiRequest("/api/auth/me");
  },

  /** List documents for the current user. */
  getDocuments: async (): Promise<DocumentListResponse> => {
    return apiRequest("/api/documents/");
  },

  /** Upload a file; backend will store it and create a document record. */
  uploadDocument: async (file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append("file", file);
    return apiRequest("/api/documents/upload", {
      method: "POST",
      body: formData,
    });
  },

  /** Trigger processing (chunking + embedding) for an uploaded document. */
  processDocument: async (documentId: number): Promise<{ message: string }> => {
    return apiRequest(`/api/documents/${documentId}/process`, {
      method: "POST",
    });
  },

  /** Delete a document and its file. */
  deleteDocument: async (documentId: number): Promise<{ message: string }> => {
    return apiRequest(`/api/documents/${documentId}`, {
      method: "DELETE",
    });
  },

  /** RAG Q&A: ask a question about a document and get answer + sources. */
  queryDocument: async (
    documentId: number,
    query: string
  ): Promise<QueryResponse> => {
    return apiRequest(`/api/documents/${documentId}/query`, {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  },

  /** Get chat history (user + assistant messages) for a document. */
  getMessages: async (documentId: number): Promise<MessageListResponse> => {
    return apiRequest(`/api/documents/${documentId}/messages`);
  },
};
