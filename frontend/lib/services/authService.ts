import { api, isLoggedIn, saveTokens } from "@/lib/api";
import type { LoginCredentials, RegisterData } from "@/lib/api.types";

const DEMO_CREDENTIALS: LoginCredentials = {
  username: "demo",
  password: "demo",
};

export const authService = {
  /** Fast client-side session check for routing decisions. */
  hasActiveSession: (): boolean => isLoggedIn(),

  /** Login and persist the returned CSRF token for subsequent mutating requests. */
  login: async (credentials: LoginCredentials): Promise<void> => {
    const response = await api.login(credentials);
    saveTokens(response);
  },

  /** Register a user, then login and persist CSRF token. */
  registerAndLogin: async (data: RegisterData): Promise<void> => {
    await api.register(data);
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
    await api.logout();
  },
};
