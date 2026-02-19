/**
 * API client: all HTTP calls to the backend go through this file.
 * Auth is now handled via httpOnly cookies set by the backend.
 * The non-httpOnly csrf_token cookie is read by JS and echoed as
 * X-CSRF-Token on every mutating request (double-submit CSRF pattern).
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
} from "./api.types";
import { ApiError } from "./api.types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Re-export so components can do: import { api, Document, ApiError } from "@/lib/api"
export { ApiError } from "./api.types";
export type {
  Document,
  DocumentStatusResponse,
  SearchResult,
  QueryResponse,
  MessageResponse,
  MessageListResponse,
} from "./api.types";

// ---------------------------------------------------------------------------
// Auth state helpers
// ---------------------------------------------------------------------------

/**
 * Read the CSRF token stored in localStorage after login/refresh.
 * The token arrives in the JSON response body because the backend sets it as a
 * cookie on its own domain — which document.cookie on Vercel cannot read (see
 * ADR-001). Safe to call during SSR (returns null when window is not available).
 */
function getCsrfToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("csrf_token");
}

/**
 * Instant auth check based on the CSRF token in localStorage.
 * Use for UI routing decisions (redirect to /login or /dashboard).
 * Not a security guarantee — actual auth is enforced by the backend
 * on every request via the httpOnly access_token cookie.
 */
export function isLoggedIn(): boolean {
  return getCsrfToken() !== null;
}

/**
 * Persist the CSRF token from a login or refresh response into localStorage.
 * The backend returns it in the JSON body because it cannot be read from
 * document.cookie across domains (see ADR-001). The httpOnly auth cookies are
 * set by the backend automatically — only the CSRF token needs JS storage.
 */
export function saveTokens(tokens: AuthResponse): void {
  localStorage.setItem("csrf_token", tokens.csrf_token);
}

/**
 * Clear the CSRF token from localStorage on logout or session expiry.
 * Also removes legacy auth keys left over from before the cookie migration.
 * Does NOT touch cookies — only the backend can clear those via Max-Age=0.
 */
function clearTokens(): void {
  localStorage.removeItem("csrf_token");
  localStorage.removeItem("access_token");  // legacy cleanup
  localStorage.removeItem("refresh_token"); // legacy cleanup
}

/** Builds full URL from a path; only place that prepends API_URL. */
function fullUrl(path: string): string {
  return `${API_URL}${path}`;
}

// ---------------------------------------------------------------------------
// Silent token refresh with single-flight lock
// ---------------------------------------------------------------------------

// Module-level promise so concurrent 401s share one refresh attempt
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = doRefresh();
  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

/**
 * Ask the backend to rotate the refresh token.
 * No request body — the httpOnly refresh_token cookie is the credential.
 * The backend responds with Set-Cookie headers and a JSON body that includes
 * a fresh csrf_token. We save it so subsequent requests use the new value.
 * Uses raw fetch (not apiRequest) to avoid a 401 refresh cycle.
 */
async function doRefresh(): Promise<boolean> {
  const csrf = getCsrfToken();
  const response = await fetch(fullUrl("/api/auth/refresh"), {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
  });
  if (response.ok) {
    const data: AuthResponse = await response.json();
    saveTokens(data); // persist rotated CSRF token
  }
  return response.ok;
}

// ---------------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------------

/**
 * Sends a request to the backend with cookies included.
 * Adds X-CSRF-Token header for CSRF protection (double-submit pattern).
 * On 401, attempts a silent token refresh once and retries the request.
 * If the refresh also fails, clears leftover localStorage tokens and
 * redirects to /login.
 */
async function apiRequest(path: string, options: RequestInit = {}) {
  const csrf = getCsrfToken();
  const isFormData = options.body instanceof FormData;

  const headers: HeadersInit = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    // Include CSRF token when we have it; backend skips check on GET/safe methods
    ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    ...options.headers,
  };

  let response = await fetch(fullUrl(path), {
    ...options,
    headers,
    credentials: "include", // send httpOnly cookies cross-origin
  });

  // On 401, attempt one silent refresh then retry
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      // Re-read CSRF token — the refresh response set a new one
      const newCsrf = getCsrfToken();
      const retryHeaders: HeadersInit = {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(newCsrf ? { "X-CSRF-Token": newCsrf } : {}),
        ...options.headers,
      };
      response = await fetch(fullUrl(path), {
        ...options,
        headers: retryHeaders,
        credentials: "include",
      });
    } else {
      // Refresh failed — session is dead; clear any stale localStorage values
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

  /**
   * Log in; returns the token body for backward compatibility.
   * The backend also sets httpOnly auth cookies — those are what
   * subsequent requests rely on. saveTokens() is now a no-op.
   */
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    return apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  },

  /**
   * Invalidate the session on the backend (deletes the refresh token row
   * and clears cookies via Set-Cookie: Max-Age=0). Best-effort: network
   * errors are swallowed so logout always completes locally.
   */
  logout: async (): Promise<void> => {
    const csrf = getCsrfToken();
    await fetch(fullUrl("/api/auth/logout"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      },
      // No body — the refresh_token httpOnly cookie is the credential
    }).catch(() => {}); // backend may be unreachable — local clear still happens
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

  /** Queue processing (chunking + embedding) for an uploaded/failed document. */
  processDocument: async (
    documentId: number
  ): Promise<{ message: string; document_id: number }> => {
    return apiRequest(`/api/documents/${documentId}/process`, {
      method: "POST",
    });
  },

  /** Poll lightweight processing status for one document. */
  getDocumentStatus: async (documentId: number): Promise<DocumentStatusResponse> => {
    return apiRequest(`/api/documents/${documentId}/status`);
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
