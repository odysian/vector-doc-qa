import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import { ApiError, SessionExpiredError, isLoggedIn, type Document } from "@/lib/api";
import { chatService } from "@/lib/services/chatService";
import { documentService } from "@/lib/services/documentService";
import { workspaceService } from "@/lib/services/workspaceService";

const pushMock = vi.fn();
const routerMock = { push: pushMock };
const pdfViewerMock = vi.fn(
  ({ filename, uploadedAt, backLabel }: { filename: string; uploadedAt: string; backLabel: string }) => (
    <div>
      <div>PDF Viewer</div>
      <div>{filename}</div>
      <div>{uploadedAt}</div>
      <div>{backLabel}</div>
    </div>
  )
);

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
}));

vi.mock("@/app/components/dashboard/PdfViewer", () => ({
  PdfViewer: (props: { filename: string; uploadedAt: string; backLabel: string }) => pdfViewerMock(props),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    isLoggedIn: vi.fn(),
  };
});

vi.mock("@/lib/services/documentService", async () => {
  const actual = await vi.importActual<typeof import("@/lib/services/documentService")>(
    "@/lib/services/documentService"
  );
  return {
    ...actual,
    documentService: {
      ...actual.documentService,
      getDashboardContext: vi.fn(),
      getDocuments: vi.fn(),
      uploadDocument: vi.fn(),
      processDocument: vi.fn(),
      getDocumentStatus: vi.fn(),
      deleteDocument: vi.fn(),
    },
  };
});

vi.mock("@/lib/services/chatService", async () => {
  const actual = await vi.importActual<typeof import("@/lib/services/chatService")>(
    "@/lib/services/chatService"
  );
  return {
    ...actual,
    chatService: {
      ...actual.chatService,
      getMessages: vi.fn(),
      getWorkspaceMessages: vi.fn(),
      queryWorkspace: vi.fn(),
      queryDocument: vi.fn(),
      queryDocumentStream: vi.fn(),
    },
  };
});

vi.mock("@/lib/services/workspaceService", async () => {
  const actual = await vi.importActual<typeof import("@/lib/services/workspaceService")>(
    "@/lib/services/workspaceService"
  );
  return {
    ...actual,
    workspaceService: {
      ...actual.workspaceService,
      getWorkspaces: vi.fn(),
      getWorkspace: vi.fn(),
      addWorkspaceDocuments: vi.fn(),
      removeWorkspaceDocument: vi.fn(),
      createWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    },
  };
});

const isLoggedInMock = vi.mocked(isLoggedIn);
const getDashboardContextMock = vi.mocked(documentService.getDashboardContext);
const getDocumentsMock = vi.mocked(documentService.getDocuments);
const uploadDocumentMock = vi.mocked(documentService.uploadDocument);
const processDocumentMock = vi.mocked(documentService.processDocument);
const getDocumentStatusMock = vi.mocked(documentService.getDocumentStatus);
const deleteDocumentMock = vi.mocked(documentService.deleteDocument);
const getMessagesMock = vi.mocked(chatService.getMessages);
const getWorkspaceMessagesMock = vi.mocked(chatService.getWorkspaceMessages);
const getWorkspacesMock = vi.mocked(workspaceService.getWorkspaces);
const getWorkspaceMock = vi.mocked(workspaceService.getWorkspace);
const addWorkspaceDocumentsMock = vi.mocked(workspaceService.addWorkspaceDocuments);
const removeWorkspaceDocumentMock = vi.mocked(workspaceService.removeWorkspaceDocument);
const deleteWorkspaceMock = vi.mocked(workspaceService.deleteWorkspace);

function makeDocument(
  overrides: Partial<Document> = {}
): Document {
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

function makeUser(overrides: Partial<{ id: number; username: string; email: string; is_demo: boolean; created_at: string }> = {}) {
  return {
    id: 1,
    username: "alice",
    email: "alice@example.com",
    is_demo: false,
    created_at: "2026-03-01T10:00:00Z",
    ...overrides,
  };
}

function makeWorkspace(overrides: Partial<{
  id: number;
  name: string;
  user_id: number;
  document_count: number;
  created_at: string;
  updated_at: string;
}> = {}) {
  return {
    id: 11,
    name: "Team Workspace",
    user_id: 1,
    document_count: 0,
    created_at: "2026-03-01T10:00:00Z",
    updated_at: "2026-03-01T10:00:00Z",
    ...overrides,
  };
}

function installResponsiveMatchMediaMock(initialWidth: number): { setWidth: (width: number) => void } {
  let currentWidth = initialWidth;
  const listenersByQuery = new Map<string, Set<(event: MediaQueryListEvent) => void>>();

  const evaluateMinWidth = (query: string): boolean => {
    const match = query.match(/\(min-width:\s*(\d+)px\)/);
    if (!match) {
      throw new Error(`Unsupported media query in test: ${query}`);
    }
    return currentWidth >= Number(match[1]);
  };

  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string): MediaQueryList => {
      const listeners = listenersByQuery.get(query) ?? new Set<(event: MediaQueryListEvent) => void>();
      listenersByQuery.set(query, listeners);
      return {
        media: query,
        get matches() {
          return evaluateMinWidth(query);
        },
        onchange: null,
        addEventListener: (type: string, listener: EventListenerOrEventListenerObject | null) => {
          if (type !== "change") return;
          if (typeof listener !== "function") return;
          listeners.add(listener as (event: MediaQueryListEvent) => void);
        },
        removeEventListener: (type: string, listener: EventListenerOrEventListenerObject | null) => {
          if (type !== "change") return;
          if (typeof listener !== "function") return;
          listeners.delete(listener as (event: MediaQueryListEvent) => void);
        },
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => true,
      } as MediaQueryList;
    }),
  });

  const setWidth = (nextWidth: number) => {
    currentWidth = nextWidth;
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      writable: true,
      value: nextWidth,
    });
    listenersByQuery.forEach((listeners, query) => {
      const event = {
        matches: evaluateMinWidth(query),
        media: query,
      } as MediaQueryListEvent;
      listeners.forEach((listener) => listener(event));
    });
  };

  setWidth(initialWidth);
  return { setWidth };
}

let setViewportWidth: (width: number) => void = () => {};

describe("DashboardPage regression behavior", () => {
  beforeEach(() => {
    const mediaController = installResponsiveMatchMediaMock(390);
    setViewportWidth = mediaController.setWidth;

    localStorage.clear();
    pushMock.mockReset();
    pdfViewerMock.mockClear();
    isLoggedInMock.mockReset();
    getDashboardContextMock.mockReset();
    getDocumentsMock.mockReset();
    uploadDocumentMock.mockReset();
    processDocumentMock.mockReset();
    getDocumentStatusMock.mockReset();
    deleteDocumentMock.mockReset();
    getMessagesMock.mockReset();
    getWorkspaceMessagesMock.mockReset();
    getWorkspacesMock.mockReset();
    getWorkspaceMock.mockReset();
    addWorkspaceDocumentsMock.mockReset();
    removeWorkspaceDocumentMock.mockReset();
    deleteWorkspaceMock.mockReset();

    globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn(),
    })) as unknown as typeof ResizeObserver;

    isLoggedInMock.mockReturnValue(true);
    getDashboardContextMock.mockResolvedValue({
      user: makeUser(),
      documents: [],
    });
    getDocumentsMock.mockResolvedValue({ documents: [], total: 0 });
    uploadDocumentMock.mockResolvedValue(makeDocument());
    processDocumentMock.mockResolvedValue({
      message: "queued",
      document_id: 101,
    });
    getDocumentStatusMock.mockResolvedValue({
      id: 101,
      status: "processing",
      processed_at: null,
      error_message: null,
    });
    deleteDocumentMock.mockResolvedValue({ message: "deleted" });
    getMessagesMock.mockResolvedValue({ messages: [], total: 0 });
    getWorkspaceMessagesMock.mockResolvedValue({ messages: [], total: 0 });
    getWorkspacesMock.mockResolvedValue({ workspaces: [], total: 0 });
    getWorkspaceMock.mockResolvedValue({
      ...makeWorkspace(),
      documents: [],
    });
    addWorkspaceDocumentsMock.mockResolvedValue({
      ...makeWorkspace(),
      documents: [],
    });
    removeWorkspaceDocumentMock.mockResolvedValue({
      ...makeWorkspace(),
      documents: [],
    });
    deleteWorkspaceMock.mockResolvedValue();
  });

  it("renders loaded documents after successful fetch", async () => {
    const doc = makeDocument({ filename: "guide.pdf" });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });

    render(<DashboardPage />);

    expect(await screen.findByText("guide.pdf")).toBeInTheDocument();
    expect(screen.getByText("Select a document")).toBeInTheDocument();
  });

  it("renders empty state when no documents are returned", async () => {
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [],
    });

    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "No documents yet" })
    ).toBeInTheDocument();
  });

  it("renders API error text when document load fails", async () => {
    getDashboardContextMock.mockRejectedValueOnce(
      new ApiError(500, "Failed to load documents from API")
    );

    render(<DashboardPage />);

    expect(
      await screen.findByText("Failed to load documents from API")
    ).toBeInTheDocument();
  });

  it("redirects to login when session refresh fails", async () => {
    getDashboardContextMock.mockRejectedValueOnce(new SessionExpiredError());

    render(<DashboardPage />);

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/login");
    });
  });

  it("uploads a document and reloads the list on success", async () => {
    const doc = makeDocument();
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });
    getDocumentsMock
      .mockResolvedValueOnce({ documents: [doc], total: 1 });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    const fileInput = screen.getByLabelText("Upload PDF");
    const file = new File(["%PDF"], "upload.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenCalledWith(file);
      expect(getDocumentsMock).toHaveBeenCalledTimes(1);
    });
  });

  it("retries failed document processing and reloads the list", async () => {
    const failedDoc = makeDocument({
      id: 201,
      status: "failed",
      processed_at: null,
      error_message: "Queue failed",
    });
    const processingDoc = makeDocument({
      id: 201,
      status: "processing",
      processed_at: null,
    });

    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [failedDoc],
    });
    getDocumentsMock.mockResolvedValueOnce({ documents: [processingDoc], total: 1 });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => {
      expect(processDocumentMock).toHaveBeenCalledWith(201);
      expect(getDocumentsMock).toHaveBeenCalledTimes(1);
    });
  });

  it("dismisses sidebar errors and allows later errors to render", async () => {
    const failedDoc = makeDocument({
      id: 202,
      status: "failed",
      processed_at: null,
      error_message: "Queue failed",
    });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [failedDoc],
    });
    processDocumentMock
      .mockRejectedValueOnce(new ApiError(500, "First queue failure"))
      .mockRejectedValueOnce(new ApiError(500, "Second queue failure"));

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("First queue failure")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss error" }));
    expect(screen.queryByText("First queue failure")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Second queue failure")).toBeInTheDocument();
  });

  it("deletes a document and reloads the list", async () => {
    const doc = makeDocument({ id: 301 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });
    getDocumentsMock.mockResolvedValueOnce({ documents: [], total: 0 });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    fireEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteDocumentMock).toHaveBeenCalledWith(301);
      expect(getDocumentsMock).toHaveBeenCalledTimes(1);
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("hides demo-restricted controls and shows demo banner for demo users", async () => {
    const doc = makeDocument({ id: 302 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser({ is_demo: true }),
      documents: [doc],
    });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    expect(
      screen.getByText(/You're using a demo account\./)
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Upload PDF")).toBeDisabled();
    expect(screen.getByText("Uploads are disabled for demo accounts")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("keeps upload and delete controls for non-demo users", async () => {
    const doc = makeDocument({ id: 303 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser({ is_demo: false }),
      documents: [doc],
    });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    expect(screen.queryByText(/You're using a demo account\./)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Upload PDF")).not.toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("renders debug toggle in app header and persists the setting", async () => {
    const doc = makeDocument({ id: 304 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    const debugBtn = screen.getByRole("button", { name: "Debug mode (Shift+D)" });
    expect(debugBtn).toBeInTheDocument();
    expect(debugBtn).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(debugBtn);

    expect(debugBtn).toHaveAttribute("aria-pressed", "true");
    expect(localStorage.getItem("quaero_debug_mode")).toBe("true");
  });

  it("keeps add-documents dialog open and shows workspace error when add fails", async () => {
    const availableDoc = makeDocument({ id: 901, filename: "workspace-source.pdf" });
    const workspace = makeWorkspace({ id: 21, name: "Roadmap", document_count: 0 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [availableDoc],
    });
    getWorkspacesMock.mockResolvedValueOnce({
      workspaces: [workspace],
      total: 1,
    });
    getWorkspaceMock.mockResolvedValueOnce({
      ...workspace,
      documents: [],
    });
    addWorkspaceDocumentsMock.mockRejectedValueOnce(new ApiError(500, "Add failed"));

    render(<DashboardPage />);

    await screen.findByText("workspace-source.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }));
    const roadmapWorkspaceText = await screen.findByText("Roadmap");
    fireEvent.click(roadmapWorkspaceText.closest("button") as HTMLButtonElement);
    fireEvent.click(await screen.findByRole("button", { name: "Add documents" }));

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByLabelText("workspace-source.pdf"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Add selected" }));

    await waitFor(() => {
      expect(addWorkspaceDocumentsMock).toHaveBeenCalledWith(21, [901]);
      expect(screen.getByText("Add failed")).toBeInTheDocument();
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("shows workspace error banner when removing a document fails", async () => {
    const workspaceDoc = makeDocument({ id: 777, filename: "remove-me.pdf" });
    const workspace = makeWorkspace({ id: 22, name: "Operations", document_count: 1 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [workspaceDoc],
    });
    getWorkspacesMock.mockResolvedValueOnce({
      workspaces: [workspace],
      total: 1,
    });
    getWorkspaceMock.mockResolvedValueOnce({
      ...workspace,
      documents: [workspaceDoc],
    });
    removeWorkspaceDocumentMock.mockRejectedValueOnce(new ApiError(500, "Remove failed"));

    render(<DashboardPage />);

    await screen.findByText("remove-me.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }));
    const operationsWorkspaceText = await screen.findByText("Operations");
    fireEvent.click(operationsWorkspaceText.closest("button") as HTMLButtonElement);
    fireEvent.click(await screen.findByRole("button", { name: "Remove remove-me.pdf" }));

    await waitFor(() => {
      expect(removeWorkspaceDocumentMock).toHaveBeenCalledWith(22, 777);
      expect(screen.getByText("Remove failed")).toBeInTheDocument();
    });
  });

  it("deletes a selected workspace after confirmation", async () => {
    const workspaceDoc = makeDocument({ id: 851, filename: "workspace-doc.pdf" });
    const workspace = makeWorkspace({ id: 31, name: "Planning", document_count: 1 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [workspaceDoc],
    });
    getWorkspacesMock.mockResolvedValueOnce({
      workspaces: [workspace],
      total: 1,
    });
    getWorkspaceMock.mockResolvedValueOnce({
      ...workspace,
      documents: [workspaceDoc],
    });

    render(<DashboardPage />);

    await screen.findByText("workspace-doc.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }));
    const workspaceButton = (await screen.findByText("Planning")).closest("button");
    fireEvent.click(workspaceButton as HTMLButtonElement);
    fireEvent.click(await screen.findByRole("button", { name: "Delete workspace" }));

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteWorkspaceMock).toHaveBeenCalledWith(31);
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(screen.getByText("No workspaces yet. Create one to group documents.")).toBeInTheDocument();
    });
  });

  it("does not delete workspace when confirmation is canceled", async () => {
    const workspace = makeWorkspace({ id: 32, name: "Roadmap", document_count: 0 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [],
    });
    getWorkspacesMock.mockResolvedValueOnce({
      workspaces: [workspace],
      total: 1,
    });
    getWorkspaceMock.mockResolvedValueOnce({
      ...workspace,
      documents: [],
    });

    render(<DashboardPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Workspaces" }));
    const workspaceButton = (await screen.findByText("Roadmap")).closest("button");
    fireEvent.click(workspaceButton as HTMLButtonElement);
    fireEvent.click(await screen.findByRole("button", { name: "Delete workspace" }));

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByText("Cancel"));

    await waitFor(() => {
      expect(deleteWorkspaceMock).not.toHaveBeenCalled();
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("keeps workspace delete modal open and shows error when delete fails", async () => {
    const workspace = makeWorkspace({ id: 33, name: "Ops", document_count: 0 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [],
    });
    getWorkspacesMock.mockResolvedValueOnce({
      workspaces: [workspace],
      total: 1,
    });
    getWorkspaceMock.mockResolvedValueOnce({
      ...workspace,
      documents: [],
    });
    deleteWorkspaceMock.mockRejectedValueOnce(new ApiError(500, "Workspace delete failed"));

    render(<DashboardPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Workspaces" }));
    const workspaceButton = (await screen.findByText("Ops")).closest("button");
    fireEvent.click(workspaceButton as HTMLButtonElement);
    fireEvent.click(await screen.findByRole("button", { name: "Delete workspace" }));

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteWorkspaceMock).toHaveBeenCalledWith(33);
      expect(screen.getByText("Workspace delete failed")).toBeInTheDocument();
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("disables workspace delete control for demo users", async () => {
    const workspace = makeWorkspace({ id: 34, name: "Demo Workspace", document_count: 0 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser({ is_demo: true }),
      documents: [],
    });
    getWorkspacesMock.mockResolvedValueOnce({
      workspaces: [workspace],
      total: 1,
    });
    getWorkspaceMock.mockResolvedValueOnce({
      ...workspace,
      documents: [],
    });

    render(<DashboardPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Workspaces" }));
    const workspaceButton = (await screen.findByText("Demo Workspace")).closest("button");
    fireEvent.click(workspaceButton as HTMLButtonElement);

    const deleteButton = await screen.findByRole("button", { name: "Delete workspace" });
    expect(deleteButton).toBeDisabled();
    fireEvent.click(deleteButton);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(deleteWorkspaceMock).not.toHaveBeenCalled();
  });
});

describe("DashboardPage layout contracts", () => {
  const ResizeObserverOrig = globalThis.ResizeObserver;

  beforeAll(() => {
    globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn(),
    }));
  });

  afterAll(() => {
    globalThis.ResizeObserver = ResizeObserverOrig;
  });

  beforeEach(() => {
    const mediaController = installResponsiveMatchMediaMock(390);
    setViewportWidth = mediaController.setWidth;

    localStorage.clear();
    pushMock.mockReset();
    pdfViewerMock.mockClear();
    isLoggedInMock.mockReset();
    getDashboardContextMock.mockReset();
    getDocumentsMock.mockReset();
    getMessagesMock.mockReset();
    getWorkspacesMock.mockReset();

    isLoggedInMock.mockReturnValue(true);
    getDashboardContextMock.mockResolvedValue({
      user: makeUser(),
      documents: [],
    });
    getMessagesMock.mockResolvedValue({ messages: [], total: 0 });
    getWorkspacesMock.mockResolvedValue({ workspaces: [], total: 0 });
  });

  async function selectDocument() {
    const doc = makeDocument();
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });
    render(<DashboardPage />);
    await screen.findByText("alpha.pdf");
    fireEvent.click(screen.getByText("alpha.pdf"));
    await screen.findByText("Ask a question about this document");
  }

  it("shows a condensed chat context bar in compact mode and removes it on desktop", async () => {
    setViewportWidth(1024);
    await selectDocument();

    expect(screen.getByTestId("chat-context-bar")).toHaveTextContent("alpha.pdf");
    expect(screen.getByRole("button", { name: "Back to Documents" })).toBeInTheDocument();

    setViewportWidth(1150);
    await waitFor(() => {
      expect(screen.queryByTestId("chat-context-bar")).not.toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Back to Documents" })).not.toBeInTheDocument();
  });

  it("chat section has w-full in tab mode for centering parity with PDF section", async () => {
    setViewportWidth(1024);
    await selectDocument();

    const chatSection = screen.getByText("Ask a question about this document")
      .closest("section");
    expect(chatSection).not.toBeNull();
    expect(chatSection!.className).toContain("w-full");
    expect(chatSection!.className).toContain("max-w-5xl");
  });

  it("derives compact and desktop layouts from 1024/1150 breakpoints", async () => {
    setViewportWidth(1024);
    await selectDocument();

    expect(screen.getByRole("button", { name: "PDF" })).toBeInTheDocument();
    const compactChatSection = screen.getByText("Ask a question about this document").closest("section");
    expect(compactChatSection).not.toBeNull();
    expect(compactChatSection!.className).toContain("max-w-5xl");

    setViewportWidth(1150);

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "PDF" })).not.toBeInTheDocument();
    });

    const desktopChatSection = screen.getByText("Ask a question about this document").closest("section");
    expect(desktopChatSection).not.toBeNull();
    expect(desktopChatSection!.className).toContain("flex-[0.9_0_40%]");
    expect(desktopChatSection!.className).toContain("min-w-72");
  });

  it("empty-state open-documents button expands collapsed desktop sidebar", async () => {
    setViewportWidth(1150);
    const doc = makeDocument();
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });

    render(<DashboardPage />);
    await screen.findByText("alpha.pdf");

    fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(screen.getByRole("complementary").className).toContain("w-0");

    fireEvent.click(screen.getByRole("button", { name: "Open documents" }));
    expect(screen.getByRole("complementary").className).not.toContain("w-0");
  });

  it("keeps compact sidebar as overlay and does not push panes", async () => {
    setViewportWidth(1024);
    const doc = makeDocument();
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });

    render(<DashboardPage />);
    await screen.findByText("alpha.pdf");
    fireEvent.click(screen.getByText("alpha.pdf"));
    await screen.findByText("Ask a question about this document");

    const sidebar = screen.getByRole("complementary");
    expect(sidebar.className).toContain("fixed");
    expect(sidebar.className).toContain("-translate-x-full");

    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));
    await waitFor(() => {
      expect(screen.getByRole("complementary").className).toContain("translate-x-0");
    });

    const main = screen.getByRole("main");
    expect(main.className).toContain("flex-1 min-w-0");
  });

  it("removes document switcher and closes compact drawer after workspace document switch", async () => {
    setViewportWidth(1024);
    const alphaDoc = makeDocument({ id: 411, filename: "alpha.pdf" });
    const betaDoc = makeDocument({
      id: 412,
      filename: "beta.pdf",
      uploaded_at: "2026-03-03T10:00:00Z",
    });
    const workspace = makeWorkspace({ id: 61, name: "Roadmap", document_count: 2 });
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [alphaDoc, betaDoc],
    });
    getWorkspacesMock.mockResolvedValueOnce({ workspaces: [workspace], total: 1 });
    getWorkspaceMock.mockResolvedValueOnce({
      ...workspace,
      documents: [alphaDoc, betaDoc],
    });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Workspaces" }));
    const workspaceButton = (await screen.findByText("Roadmap")).closest("button");
    fireEvent.click(workspaceButton as HTMLButtonElement);
    fireEvent.click(await screen.findByRole("button", { name: "PDF" }));

    expect(screen.queryByLabelText("Switch document")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(pdfViewerMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filename: "alpha.pdf",
          uploadedAt: alphaDoc.uploaded_at,
          backLabel: "Back to Workspaces",
        })
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));
    await waitFor(() => {
      expect(screen.getByRole("complementary").className).toContain("translate-x-0");
    });

    fireEvent.click(within(screen.getByRole("complementary")).getByRole("button", { name: "beta.pdf" }));
    await waitFor(() => {
      expect(screen.getByRole("complementary").className).toContain("-translate-x-full");
    });
    await waitFor(() => {
      expect(pdfViewerMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          filename: "beta.pdf",
          uploadedAt: betaDoc.uploaded_at,
          backLabel: "Back to Workspaces",
        })
      );
    });
  });

  it("keeps mobile backdrop visibility controlled by hidden/block utilities", async () => {
    setViewportWidth(1024);
    const doc = makeDocument();
    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [doc],
    });

    render(<DashboardPage />);
    await screen.findByText("alpha.pdf");

    const getBackdrop = () => {
      const backdrop = screen
        .getAllByRole("button", { name: "Close sidebar" })
        .find((button) => button.className.includes("fixed inset-0"));
      expect(backdrop).toBeDefined();
      return backdrop as HTMLButtonElement;
    };

    expect(getBackdrop().classList.contains("hidden")).toBe(true);
    expect(getBackdrop().classList.contains("block")).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));

    await waitFor(() => {
      expect(getBackdrop().className).toContain("block");
    });
    expect(getBackdrop().classList.contains("hidden")).toBe(false);

    fireEvent.click(getBackdrop());

    await waitFor(() => {
      expect(getBackdrop().classList.contains("hidden")).toBe(true);
    });
    expect(getBackdrop().classList.contains("block")).toBe(false);
  });
});
