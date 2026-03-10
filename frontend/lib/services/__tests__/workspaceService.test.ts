import { afterEach, describe, expect, it, vi } from "vitest";
import { workspaceService } from "@/lib/services/workspaceService";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("workspaceService", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("loads the current user's workspace list", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse(200, { workspaces: [], total: 0 })
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await workspaceService.getWorkspaces();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/workspaces/",
      expect.objectContaining({ credentials: "include" })
    );
    expect(response).toEqual({ workspaces: [], total: 0 });
  });

  it("adds documents to an existing workspace", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse(200, {
        id: 8,
        name: "Q1 Workspace",
        user_id: 1,
        document_count: 1,
        created_at: "2026-03-09T00:00:00Z",
        updated_at: "2026-03-09T00:00:00Z",
        documents: [
          {
            id: 2,
            user_id: 1,
            filename: "plan.pdf",
            file_size: 100,
            status: "completed",
            uploaded_at: "2026-03-09T00:00:00Z",
            processed_at: "2026-03-09T00:01:00Z",
            error_message: null,
          },
        ],
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await workspaceService.addWorkspaceDocuments(8, [2]);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/workspaces/8/documents",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ document_ids: [2] }),
      })
    );
    expect(response.document_count).toBe(1);
  });
});
