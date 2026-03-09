import { afterEach, describe, expect, it, vi } from "vitest";
import { authService } from "@/lib/services/authService";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("authService", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("returns true from hasActiveSession when csrf token is stored", () => {
    localStorage.setItem("csrf_token", "csrf-token");

    expect(authService.hasActiveSession()).toBe(true);
  });

  it("logs in and persists returned csrf token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, { csrf_token: "csrf-token", token_type: "bearer" }));
    vi.stubGlobal("fetch", fetchMock);

    await authService.login({ username: "alice", password: "secret" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/auth/login",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      })
    );
    expect(localStorage.getItem("csrf_token")).toBe("csrf-token");
  });

  it("registers then logs in with the same username and password", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, {
          id: 1,
          username: "alice",
          email: "alice@example.com",
          is_demo: false,
          created_at: "2026-03-08T10:00:00Z",
        })
      )
      .mockResolvedValueOnce(jsonResponse(200, { csrf_token: "csrf-token", token_type: "bearer" }));
    vi.stubGlobal("fetch", fetchMock);

    await authService.registerAndLogin({
      username: "alice",
      email: "alice@example.com",
      password: "strong-password",
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8000/api/auth/register");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/api/auth/login");
    expect(localStorage.getItem("csrf_token")).toBe("csrf-token");
  });

  it("logs in with demo credentials", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, { csrf_token: "csrf-demo", token_type: "bearer" }));
    vi.stubGlobal("fetch", fetchMock);

    await authService.loginDemo();

    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8000/api/auth/login");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    expect(localStorage.getItem("csrf_token")).toBe("csrf-demo");
  });

  it("clears local auth tokens after logout even if backend call fails", async () => {
    localStorage.setItem("csrf_token", "csrf-old");
    localStorage.setItem("access_token", "legacy-access");
    localStorage.setItem("refresh_token", "legacy-refresh");

    const fetchMock = vi.fn().mockRejectedValueOnce(new Error("network down"));
    vi.stubGlobal("fetch", fetchMock);

    await authService.logout();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/auth/logout",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      })
    );
    expect(localStorage.getItem("csrf_token")).toBeNull();
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });
});
