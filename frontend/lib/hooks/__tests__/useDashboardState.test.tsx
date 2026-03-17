import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Document, Workspace, WorkspaceDetail } from "@/lib/api";
import type { User } from "@/lib/api.types";
import * as api from "@/lib/api";
import { SessionExpiredError } from "@/lib/api";
import { useDashboardState } from "@/lib/hooks/useDashboardState";
import { authService } from "@/lib/services/authService";
import { documentService } from "@/lib/services/documentService";
import { workspaceService } from "@/lib/services/workspaceService";

const onSessionExpiredMock = vi.fn();
const isLoggedInMock = vi.spyOn(api, "isLoggedIn");

function makeDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: 101,
    user_id: 1,
    filename: "alpha.pdf",
    file_size: 2048,
    status: "completed",
    uploaded_at: "2026-03-01T10:00:00Z",
    processed_at: "2026-03-01T10:01:00Z",
    error_message: null,
    ...overrides,
  };
}

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    username: "alice",
    email: "alice@example.com",
    is_demo: false,
    created_at: "2026-03-01T10:00:00Z",
    ...overrides,
  };
}

function makeWorkspace(overrides: Partial<Workspace> = {}): Workspace {
  return {
    id: 21,
    name: "Roadmap",
    user_id: 1,
    document_count: 1,
    created_at: "2026-03-01T10:00:00Z",
    updated_at: "2026-03-01T10:00:00Z",
    ...overrides,
  };
}

function makeWorkspaceDetail(overrides: Partial<WorkspaceDetail> = {}): WorkspaceDetail {
  const baseWorkspace = makeWorkspace();
  return {
    ...baseWorkspace,
    documents: [makeDocument({ id: 501, filename: "workspace-source.pdf" })],
    ...overrides,
  };
}

function setupHookHarness() {
  const hook = renderHook(() => useDashboardState({ onSessionExpired: onSessionExpiredMock }));
  return { hook };
}

describe("useDashboardState", () => {
  const getDashboardContextMock = vi.spyOn(documentService, "getDashboardContext");
  const getDocumentsMock = vi.spyOn(documentService, "getDocuments");
  const uploadDocumentMock = vi.spyOn(documentService, "uploadDocument");
  const getDocumentStatusMock = vi.spyOn(documentService, "getDocumentStatus");
  const authLogoutMock = vi.spyOn(authService, "logout");
  const getWorkspaceMock = vi.spyOn(workspaceService, "getWorkspace");

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    onSessionExpiredMock.mockReset();
    isLoggedInMock.mockReturnValue(true);
    getDashboardContextMock.mockResolvedValue({
      user: makeUser(),
      documents: [],
    });
    getDocumentsMock.mockResolvedValue({ documents: [], total: 0 });
    uploadDocumentMock.mockResolvedValue(makeDocument());
    getDocumentStatusMock.mockResolvedValue({
      id: 101,
      status: "processing",
      processed_at: null,
      error_message: null,
    });
    authLogoutMock.mockResolvedValue();
    getWorkspaceMock.mockResolvedValue(makeWorkspaceDetail());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads dashboard context into state and clears loading", async () => {
    const doc = makeDocument({ id: 1, filename: "guide.pdf" });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });

    const { hook } = setupHookHarness();

    await waitFor(() => {
      expect(hook.result.current.loading).toBe(false);
    });

    expect(hook.result.current.documents).toEqual([doc]);
    expect(hook.result.current.isDemoUser).toBe(false);
  });

  it("applies persisted debug mode preference on initial render", async () => {
    localStorage.setItem("quaero_debug_mode", "false");

    const { hook } = setupHookHarness();

    // Assert immediately so initial paint reflects persisted preference.
    expect(hook.result.current.debugMode).toBe(false);
  });

  it(
    "redirects on polling session-expired errors",
    async () => {
    const pending = makeDocument({
      id: 201,
      status: "processing",
    });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [pending],
    });
    getDocumentStatusMock.mockRejectedValueOnce(new SessionExpiredError());

    const { hook } = setupHookHarness();

    await waitFor(() => {
      expect(hook.result.current.loading).toBe(false);
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 3200));
    });

      await waitFor(() => {
        expect(onSessionExpiredMock).toHaveBeenCalledTimes(1);
      });
      expect(hook.result.current.documents).toEqual([pending]);
    },
    9000
  );

  it("reloads documents after upload", async () => {
    const doc = makeDocument({ id: 301 });
    const refreshed = makeDocument({ id: 302, filename: "new.pdf" });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });
    getDocumentsMock.mockResolvedValue({ documents: [doc, refreshed], total: 2 });

    const { hook } = setupHookHarness();
    await waitFor(() => {
      expect(hook.result.current.loading).toBe(false);
    });

    await act(async () => {
      await hook.result.current.handleUpload(
        new File(["%PDF"], "upload.pdf", { type: "application/pdf" })
      );
    });

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenCalledTimes(1);
      expect(getDocumentsMock).toHaveBeenCalledTimes(1);
      expect(hook.result.current.documents).toEqual([doc, refreshed]);
    });
  });

  it("logs out through authService and then redirects to login", async () => {
    const { hook } = setupHookHarness();
    await waitFor(() => {
      expect(hook.result.current.loading).toBe(false);
    });

    await act(async () => {
      await hook.result.current.handleLogout();
    });

    expect(authLogoutMock).toHaveBeenCalledTimes(1);
    expect(onSessionExpiredMock).toHaveBeenCalledTimes(1);
  });

  it("does not apply workspace citation highlights when source document is absent", async () => {
    const workspace = makeWorkspace({ id: 44, name: "Ops", document_count: 1 });
    getWorkspaceMock.mockResolvedValueOnce(
      makeWorkspaceDetail({
        id: workspace.id,
        name: workspace.name,
        document_count: workspace.document_count,
        documents: [makeDocument({ id: 601, filename: "present.pdf" })],
      })
    );

    const { hook } = setupHookHarness();
    await waitFor(() => {
      expect(hook.result.current.loading).toBe(false);
    });

    await act(async () => {
      await hook.result.current.handleWorkspaceClick(workspace);
    });

    await waitFor(() => {
      expect(hook.result.current.selectedWorkspace?.id).toBe(44);
    });

    act(() => {
      hook.result.current.handleCitationClick({
        page: 7,
        snippet: "  Missing source citation  ",
        documentId: 999,
      });
    });

    expect(hook.result.current.viewerDocumentId).toBe(601);
    expect(hook.result.current.mobileTab).toBe("chat");
    expect(hook.result.current.highlightPage).toBeNull();
    expect(hook.result.current.highlightSnippet).toBeNull();
  });
});
