import { afterEach, describe, expect, it, vi } from "vitest";
import { documentService } from "@/lib/services/documentService";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("documentService", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("loads dashboard context from auth and document endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, {
          id: 7,
          username: "alice",
          email: "alice@example.com",
          is_demo: false,
          created_at: "2026-03-08T10:00:00Z",
        })
      )
      .mockResolvedValueOnce(jsonResponse(200, { documents: [{ id: 1, filename: "a.pdf" }], total: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await documentService.getDashboardContext();

    const calledUrls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(calledUrls).toContain("http://localhost:8000/api/auth/me");
    expect(calledUrls).toContain("http://localhost:8000/api/documents/");
    expect(result.user.username).toBe("alice");
    expect(result.documents).toEqual([{ id: 1, filename: "a.pdf" }]);
  });

  it("uploads a document using multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse(200, {
        id: 2,
        filename: "report.pdf",
        original_filename: "report.pdf",
        file_size: 10,
        status: "pending",
        uploaded_at: "2026-03-09T00:00:00Z",
        processed_at: null,
        error_message: null,
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["pdf-content"], "report.pdf", { type: "application/pdf" });
    const result = await documentService.uploadDocument(file);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/documents/upload",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      })
    );
    const body = fetchMock.mock.calls[0]?.[1] && (fetchMock.mock.calls[0][1] as RequestInit).body;
    expect(body).toBeInstanceOf(FormData);
    expect(result.filename).toBe("report.pdf");
  });
});
