const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

interface LoginCredentials {
  username: string;
  password: string;
}

interface RegisterData {
  username: string;
  email: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
}

interface User {
  id: number;
  username: string;
  email: string;
  created_at: string;
}

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

interface DocumentListResponse {
  documents: Document[];
  total: number;
}

// Search & Query types
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

// Helper to get auth token from localStorage
function getToken(): string | null {
  // Check window to prevent server crash
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

// Helper to make authenticated requests
async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${url}`, {
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

// Auth API functions
export const api = {
  // Register
  register: async (data: RegisterData): Promise<User> => {
    return fetchWithAuth("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // Login
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    return fetchWithAuth("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  },

  // Get current user
  getCurrentUser: async (): Promise<User> => {
    return fetchWithAuth("/api/auth/me");
  },

  // Get documents
  getDocuments: async (): Promise<DocumentListResponse> => {
    return fetchWithAuth("/api/documents/");
  },

  // Upload document
  uploadDocument: async (file: File): Promise<Document> => {
    const formData = new FormData();
    formData.append("file", file);

    const token = getToken();
    const response = await fetch(`${API_URL}/api/documents/upload`, {
      method: "POST",
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Upload failed" }));
      throw new ApiError(response.status, error.detail || "Upload failed");
    }

    return response.json();
  },

  // Process document
  processDocument: async (documentId: number): Promise<{ message: string }> => {
    return fetchWithAuth(`/api/documents/${documentId}/process`, {
      method: "POST",
    });
  },

  // Query document (RAG Q&A)
  queryDocument: async (
    documentId: number,
    query: string
  ): Promise<QueryResponse> => {
    return fetchWithAuth(`/api/documents/${documentId}/query`, {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  },
};
