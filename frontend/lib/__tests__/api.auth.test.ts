import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiRequest auth refresh contract", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("retries the original request after a successful refresh", async () => {
    localStorage.setItem("csrf_token", "csrf-old");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Unauthorized" }))
      .mockResolvedValueOnce(
        jsonResponse(200, { csrf_token: "csrf-new", token_type: "bearer" })
      )
      .mockResolvedValueOnce(jsonResponse(200, { documents: [], total: 0 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await api.getDocuments();

    expect(response).toEqual({ documents: [], total: 0 });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8000/api/documents/");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": "csrf-old",
      },
    });
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/api/auth/refresh");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": "csrf-old",
      },
    });
    expect(fetchMock.mock.calls[2]?.[0]).toBe("http://localhost:8000/api/documents/");
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": "csrf-new",
      },
    });
  });

  it("clears client auth state and throws session-expired error when refresh fails", async () => {
    localStorage.setItem("csrf_token", "csrf-old");
    localStorage.setItem("access_token", "legacy-access");
    localStorage.setItem("refresh_token", "legacy-refresh");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Unauthorized" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Refresh failed" }));
    vi.stubGlobal("fetch", fetchMock);
    const consoleErrorMock = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});

    try {
      await expect(api.getDocuments()).rejects.toMatchObject({
        status: 401,
        detail: "Session expired",
      } satisfies Pick<ApiError, "status" | "detail">);
    } finally {
      consoleErrorMock.mockRestore();
    }

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/api/auth/refresh");
    expect(localStorage.getItem("csrf_token")).toBeNull();
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });
});
