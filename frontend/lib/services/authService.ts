import { fullUrl } from "@/lib/api/config";
import {
  clearAuthTokens,
  getCsrfToken,
  requestJsonWithAuth,
  saveAuthTokens,
} from "@/lib/api/http";
import type {
  AuthResponse,
  LoginCredentials,
  RegisterData,
  User,
} from "@/lib/api.types";

const DEMO_CREDENTIALS: LoginCredentials = {
  username: "demo",
  password: "demo",
};

export const authService = {
  /** Fast client-side session check for routing decisions. */
  hasActiveSession: (): boolean => getCsrfToken() !== null,

  /** Raw auth login operation for compatibility callers that manage persistence. */
  loginRaw: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    return requestJsonWithAuth<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  },

  /** Raw auth register operation. */
  register: async (data: RegisterData): Promise<User> => {
    return requestJsonWithAuth<User>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /** Load the current authenticated user profile. */
  getCurrentUser: async (): Promise<User> => {
    return requestJsonWithAuth<User>("/api/auth/me");
  },

  /** Login and persist the returned CSRF token for subsequent mutating requests. */
  login: async (credentials: LoginCredentials): Promise<void> => {
    const response = await authService.loginRaw(credentials);
    saveAuthTokens(response);
  },

  /** Register a user, then login and persist CSRF token. */
  registerAndLogin: async (data: RegisterData): Promise<void> => {
    await authService.register(data);
    await authService.login({
      username: data.username,
      password: data.password,
    });
  },

  /** Login using the seeded demo account. */
  loginDemo: async (): Promise<void> => {
    await authService.login(DEMO_CREDENTIALS);
  },

  logout: async (): Promise<void> => {
    const csrf = getCsrfToken();
    await fetch(fullUrl("/api/auth/logout"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      },
    }).catch(() => {});
    clearAuthTokens();
  },
};
