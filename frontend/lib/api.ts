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

// ---------------------------------------------------------------------------
// Token storage helpers
// ---------------------------------------------------------------------------

function getToken(): string | null {
  if (typeof window === "undefined") return null; // safe during SSR (Next.js)
  return localStorage.getItem("access_token");
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

/** Persist both tokens after login, register, or a successful refresh. */
export function saveTokens(tokens: {
  access_token: string;
  refresh_token: string;
}): void {
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

function clearTokens(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

/** Builds full URL from a path; only place that prepends API_URL. */
function fullUrl(path: string): string {
  return `${API_URL}${path}`;
}

// ---------------------------------------------------------------------------
// Silent token refresh with single-flight lock
// ---------------------------------------------------------------------------

// Module-level promise so concurrent 401s share one refresh attempt
let refreshPromise: Promise<AuthResponse | null> | null = null;

async function refreshAccessToken(): Promise<AuthResponse | null> {
  // If a refresh is already in flight, piggyback on it
  if (refreshPromise) return refreshPromise;

  refreshPromise = doRefresh();
  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

/**
 * Sends the refresh token to the backend and updates localStorage on success.
 * Uses raw fetch (not apiRequest) to avoid triggering another 401 refresh cycle.
 */
async function doRefresh(): Promise<AuthResponse | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  const response = await fetch(fullUrl("/api/auth/refresh"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) return null;

  const tokens: AuthResponse = await response.json();
  saveTokens(tokens);
  return tokens;
}

// ---------------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------------

/**
 * Sends a request to the backend. Adds Authorization when a token exists.
 * Omits Content-Type for FormData so the browser sets multipart/form-data.
 * On 401, attempts a silent token refresh once and retries the request.
 * If the refresh also fails, clears tokens and redirects to /login.
 */
async function apiRequest(path: string, options: RequestInit = {}) {
  const token = getToken();
  const isFormData = options.body instanceof FormData;
  const headers: HeadersInit = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  let response = await fetch(fullUrl(path), { ...options, headers });

  // On 401, attempt one silent refresh then retry
  if (response.status === 401) {
    const newTokens = await refreshAccessToken();
    if (newTokens) {
      const retryHeaders: HeadersInit = {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        Authorization: `Bearer ${newTokens.access_token}`,
        ...options.headers,
      };
      response = await fetch(fullUrl(path), { ...options, headers: retryHeaders });
    } else {
      // Refresh failed — session is dead
      clearTokens();
      window.location.href = "/login";
      throw new ApiError(401, "Session expired");
    }
  }

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    throw new ApiError(response.status, error.detail || "Request failed");
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Public API methods
// ---------------------------------------------------------------------------

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

  /** Log in; returns access_token + refresh_token. Use saveTokens() to persist. */
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    return apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  },

  /**
   * Invalidate the refresh token on the backend, then clear tokens locally.
   * Best-effort: network/server errors are swallowed so logout always completes.
   */
  logout: async (): Promise<void> => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      await fetch(fullUrl("/api/auth/logout"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {}); // backend may be unreachable — local clear still happens
    }
    clearTokens();
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
