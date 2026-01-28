const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
    throw new Error(error.detail || "Request failed");
  }
  return response.json();
}

// Auth API functions
export const api = {
  register: async (data: RegisterData): Promise<User> => {
    return fetchWithAuth("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    return fetchWithAuth("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  },

  getCurrentUser: async (): Promise<User> => {
    return fetchWithAuth("/api/auth/me");
  },
};
