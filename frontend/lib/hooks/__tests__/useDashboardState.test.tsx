import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Document } from "@/lib/api";
import type { User } from "@/lib/api.types";
import * as api from "@/lib/api";
import { SessionExpiredError } from "@/lib/api";
import { useDashboardState } from "@/lib/hooks/useDashboardState";
import { documentService } from "@/lib/services/documentService";

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

function setupHookHarness() {
  const hook = renderHook(() => useDashboardState({ onSessionExpired: onSessionExpiredMock }));
  return { hook };
}

describe("useDashboardState", () => {
  const getDashboardContextMock = vi.spyOn(documentService, "getDashboardContext");
  const getDocumentsMock = vi.spyOn(documentService, "getDocuments");
  const uploadDocumentMock = vi.spyOn(documentService, "uploadDocument");
  const getDocumentStatusMock = vi.spyOn(documentService, "getDocumentStatus");

  beforeEach(() => {
    vi.clearAllMocks();
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
});
