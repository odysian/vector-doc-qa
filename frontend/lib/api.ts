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
  PipelineMeta,
} from "./api.types";
import { ApiError } from "./api.types";
import { fullUrl } from "./api/config";
import {
  clearAuthTokens,
  getCsrfToken,
  requestWithAuthRefresh,
  saveAuthTokens,
} from "./api/http";

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

// ---------------------------------------------------------------------------
// Auth state helpers
// ---------------------------------------------------------------------------

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
  saveAuthTokens(tokens);
}

const DEMO_CREDENTIALS: LoginCredentials = {
  username: "demo",
  password: "demo",
};

/**
 * Log in with the seeded demo account and persist csrf_token locally.
 * Used by both landing and login "Try Demo" entrypoints.
 */
export async function loginAsDemo(): Promise<void> {
  const response = await api.login(DEMO_CREDENTIALS);
  saveTokens(response);
}

// ---------------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------------

/**
 * Sends a request to the backend with cookies included.
 * Adds X-CSRF-Token header for CSRF protection (double-submit pattern).
 * On 401, attempts a silent token refresh once and retries the request.
 * If the refresh also fails, clears leftover localStorage tokens and throws
 * a typed session error for the UI boundary to handle.
 */
async function apiRequest(path: string, options: RequestInit = {}) {
  const isFormData = options.body instanceof FormData;

  const response = await requestWithAuthRefresh(path, (csrfToken) => ({
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      ...options.headers,
    },
  }));

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
   * Log in; backend sets httpOnly auth cookies and returns csrf_token.
   * subsequent requests rely on cookies; csrf_token is persisted locally.
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
    clearAuthTokens();
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

  /** Download a document PDF for in-app viewing. */
  getDocumentFile: async (documentId: number): Promise<Blob> => {
    const response = await requestWithAuthRefresh(
      `/api/documents/${documentId}/file`,
      (csrfToken) => ({
        method: "GET",
        headers: {
          ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        },
      })
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Failed to load document" }));
      throw new ApiError(response.status, error.detail || "Failed to load document");
    }

    return response.blob();
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

  /**
   * RAG Q&A stream: read token updates from SSE using fetch + ReadableStream.
   * EventSource cannot be used here because it does not support POST or headers.
   */
  queryDocumentStream: async (
    documentId: number,
    query: string,
    callbacks: QueryStreamCallbacks,
    options: QueryStreamOptions = {}
  ): Promise<void> => {
    const response = await requestWithAuthRefresh(
      `/api/documents/${documentId}/query/stream`,
      (csrfToken) => ({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        },
        body: JSON.stringify({ query }),
        signal: options.signal,
      })
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Request failed" }));
      throw new ApiError(response.status, error.detail || "Request failed");
    }

    if (!response.body) {
      throw new ApiError(500, "Streaming response unavailable");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamTerminated = false;

    const emitDone = (data: { message_id: number }) => {
      if (streamTerminated) return;
      streamTerminated = true;
      callbacks.onDone(data);
    };

    const emitError = (detail: string) => {
      if (streamTerminated) return;
      streamTerminated = true;
      callbacks.onError(detail);
    };

    const parseFrame = (frame: string) => {
      const lines = frame.split("\n");
      let event = "";
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith("event:")) {
          event = line.slice("event:".length).trim();
        } else if (line.startsWith("data:")) {
          const rawValue = line.slice("data:".length);
          // SSE field parsing drops one optional leading space after ":".
          dataLines.push(rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue);
        }
      }

      if (!event || dataLines.length === 0) return;

      const data = dataLines.join("\n");

      try {
        if (event === "sources") {
          callbacks.onSources(JSON.parse(data) as QueryResponse["sources"]);
          return;
        }
        if (event === "token") {
          callbacks.onToken(data);
          return;
        }
        if (event === "meta") {
          callbacks.onMeta(JSON.parse(data) as PipelineMeta);
          return;
        }
        if (event === "done") {
          emitDone(JSON.parse(data) as { message_id: number });
          return;
        }
        if (event === "error") {
          const parsed = JSON.parse(data) as { detail?: string };
          emitError(parsed.detail || "Query failed");
        }
      } catch {
        emitError("Failed to parse streaming event");
      }
    };

    const flushFrames = () => {
      let frameBoundary = buffer.indexOf("\n\n");
      while (frameBoundary !== -1) {
        const frame = buffer.slice(0, frameBoundary);
        buffer = buffer.slice(frameBoundary + 2);
        if (frame.trim()) {
          parseFrame(frame);
        }
        frameBoundary = buffer.indexOf("\n\n");
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replaceAll("\r\n", "\n");
        flushFrames();
      }

      buffer += decoder.decode().replaceAll("\r\n", "\n");
      flushFrames();
      if (buffer.trim()) {
        parseFrame(buffer);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw err;
      }
      emitError("Stream connection failed");
    } finally {
      reader.releaseLock();
    }

    if (!streamTerminated && !options.signal?.aborted) {
      emitError("Stream ended unexpectedly");
    }
  },

  /** Get chat history (user + assistant messages) for a document. */
  getMessages: async (documentId: number): Promise<MessageListResponse> => {
    return apiRequest(`/api/documents/${documentId}/messages`);
  },
};
