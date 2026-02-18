/**
 * API request/response types and error class.
 * Keeps the API contract in one place for use by api.ts and components.
 */

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

// Auth
export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  csrf_token: string; // returned in body for cross-domain clients (see ADR-001)
  token_type: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  created_at: string;
}

// Documents
export interface Document {
  id: number;
  user_id: number;
  filename: string;
  file_size: number;
  status: "pending" | "processing" | "completed" | "failed";
  uploaded_at: string;
  processed_at: string | null;
  error_message: string | null;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

// Search & Query
export interface SearchResult {
  chunk_id: number;
  content: string;
  similarity: number;
  chunk_index: number;
}

export interface QueryResponse {
  query: string;
  answer: string;
  sources: SearchResult[];
}

// Messages
export interface MessageResponse {
  id: number;
  document_id: number;
  user_id: number;
  role: "user" | "assistant";
  content: string;
  sources?: Array<{
    chunk_id: number;
    content: string;
    chunk_index: number;
    similarity: number;
  }>;
  created_at: string;
}

export interface MessageListResponse {
  messages: MessageResponse[];
  total: number;
}
