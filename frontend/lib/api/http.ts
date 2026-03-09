import type { AuthResponse } from "../api.types";
import { SessionExpiredError } from "../api.types";
import { fullUrl } from "./config";

/**
 * Read the CSRF token stored in localStorage after login/refresh.
 * Safe to call during SSR (returns null when window is not available).
 */
export function getCsrfToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("csrf_token");
}

/** Persist the CSRF token from an auth response into localStorage. */
export function saveAuthTokens(tokens: AuthResponse): void {
  localStorage.setItem("csrf_token", tokens.csrf_token);
}

/** Clear client-side auth hints from localStorage. */
export function clearAuthTokens(): void {
  localStorage.removeItem("csrf_token");
  localStorage.removeItem("access_token");  // legacy cleanup
  localStorage.removeItem("refresh_token"); // legacy cleanup
}

// Module-level promise so concurrent 401s share one refresh attempt.
let refreshPromise: Promise<boolean> | null = null;

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
    saveAuthTokens(data);
  }

  return response.ok;
}

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
 * Sends an authenticated request with one silent refresh retry on 401.
 * The request factory is called before the first request and again after
 * refresh so callers automatically pick up the rotated CSRF token.
 */
export async function requestWithAuthRefresh(
  path: string,
  buildRequest: (csrfToken: string | null) => RequestInit
): Promise<Response> {
  let response = await fetch(fullUrl(path), {
    ...buildRequest(getCsrfToken()),
    credentials: "include",
  });

  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (!refreshed) {
      clearAuthTokens();
      throw new SessionExpiredError();
    }

    response = await fetch(fullUrl(path), {
      ...buildRequest(getCsrfToken()),
      credentials: "include",
    });
  }

  return response;
}
