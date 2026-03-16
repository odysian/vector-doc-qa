import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import { useDashboardState } from "@/lib/hooks/useDashboardState";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/hooks/useDashboardState", () => ({
  useDashboardState: vi.fn(),
}));

vi.mock("@/app/components/dashboard/ChatWindow", () => ({
  ChatWindow: () => {
    throw new Error("chat boundary test error");
  },
}));

const useDashboardStateMock = vi.mocked(useDashboardState);

const documentFixture = {
  id: 101,
  user_id: 1,
  filename: "alpha.pdf",
  file_size: 2048,
  status: "completed",
  uploaded_at: "2026-03-01T10:00:00Z",
  processed_at: "2026-03-01T10:01:00Z",
  error_message: null,
};

describe("DashboardPage page-level ErrorBoundary", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders page fallback and reload control when child throws", () => {
    useDashboardStateMock.mockReturnValue({
      documents: [documentFixture],
      loading: false,
      error: "",
      dashboardMode: "documents",
      workspaces: [],
      selectedWorkspace: null,
      viewerDocumentId: null,
      workspacesLoading: false,
      sidebarOpen: false,
      documentToDelete: null,
      deletingInProgress: false,
      highlightPage: null,
      highlightSnippet: null,
      mobileTab: "chat",
      layoutMode: "mobile",
      desktopSidebarCollapsed: false,
      debugMode: false,
      isDemoUser: false,
      toggleDebugMode: vi.fn(),
      clearError: vi.fn(),
      selectedDocument: documentFixture,
      handleUpload: vi.fn(),
      handleLogout: vi.fn(),
      handleDocumentClick: vi.fn(),
      handleBackToDocuments: vi.fn(),
      handleCitationClick: vi.fn(),
      handleProcessDocument: vi.fn(),
      handleDeleteDocument: vi.fn(),
      handleConfirmDelete: vi.fn(),
      handleCancelDelete: vi.fn(),
      setDashboardMode: vi.fn(),
      handleWorkspaceClick: vi.fn(),
      handleCreateWorkspace: vi.fn(),
      handleDeleteWorkspace: vi.fn(),
      handleAddWorkspaceDocuments: vi.fn(),
      handleRemoveWorkspaceDocument: vi.fn(),
      handleViewerDocumentSwitch: vi.fn(),
      handleBackToWorkspaces: vi.fn(),
      setSidebarOpen: vi.fn(),
      setMobileTab: vi.fn(),
      setDesktopSidebarCollapsed: vi.fn(),
    });

    const reloadSpy = vi.fn();
    vi.stubGlobal("location", {
      ...(window.location as Location),
      reload: reloadSpy,
    });
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    try {
      render(<DashboardPage />);

      expect(screen.getByText("Something went wrong")).toBeInTheDocument();
      expect(
        screen.getByText("An unexpected error occurred. Reload the page to continue.")
      ).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Reload" }));
      expect(reloadSpy).toHaveBeenCalledTimes(1);
      expect(consoleErrorSpy).toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
      consoleErrorSpy.mockRestore();
    }
  });
});
