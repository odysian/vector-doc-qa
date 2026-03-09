import { afterEach, describe, expect, it, vi } from "vitest";
import { api, SessionExpiredError } from "@/lib/api";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
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

    await expect(api.getDocuments()).rejects.toBeInstanceOf(SessionExpiredError);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/api/auth/refresh");
    expect(localStorage.getItem("csrf_token")).toBeNull();
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("uses a single refresh request for concurrent 401 responses", async () => {
    localStorage.setItem("csrf_token", "csrf-old");
    const refreshResult = deferred<Response>();
    let documentRequestCount = 0;

    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      void init;
      const url = String(input);

      if (url === "http://localhost:8000/api/documents/") {
        documentRequestCount += 1;
        if (documentRequestCount <= 2) {
          return Promise.resolve(jsonResponse(401, { detail: "Unauthorized" }));
        }
        return Promise.resolve(jsonResponse(200, { documents: [], total: 0 }));
      }

      if (url === "http://localhost:8000/api/auth/refresh") {
        return refreshResult.promise;
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    const firstRequest = api.getDocuments();
    const secondRequest = api.getDocuments();

    await Promise.resolve();
    refreshResult.resolve(jsonResponse(200, { csrf_token: "csrf-new", token_type: "bearer" }));

    await expect(Promise.all([firstRequest, secondRequest])).resolves.toEqual([
      { documents: [], total: 0 },
      { documents: [], total: 0 },
    ]);

    const refreshCalls = fetchMock.mock.calls.filter(
      ([url]) => String(url) === "http://localhost:8000/api/auth/refresh"
    );
    const retriedDocumentCalls = fetchMock.mock.calls.filter(
      ([url]) => String(url) === "http://localhost:8000/api/documents/"
    ).slice(2);

    expect(refreshCalls).toHaveLength(1);
    expect(retriedDocumentCalls).toHaveLength(2);
    expect(retriedDocumentCalls[0]?.[1]).toMatchObject({
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": "csrf-new",
      },
    });
    expect(retriedDocumentCalls[1]?.[1]).toMatchObject({
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": "csrf-new",
      },
    });
  });
});
