import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import { ApiError, SessionExpiredError, isLoggedIn, type Document } from "@/lib/api";
import { chatService } from "@/lib/services/chatService";
import { documentService } from "@/lib/services/documentService";

const pushMock = vi.fn();
const routerMock = { push: pushMock };

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
}));

vi.mock("@/app/components/dashboard/PdfViewer", () => ({
  PdfViewer: () => <div>PDF Viewer</div>,
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
      queryDocument: vi.fn(),
      queryDocumentStream: vi.fn(),
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

describe("DashboardPage regression behavior", () => {
  beforeEach(() => {
    pushMock.mockReset();
    isLoggedInMock.mockReset();
    getDashboardContextMock.mockReset();
    getDocumentsMock.mockReset();
    uploadDocumentMock.mockReset();
    processDocumentMock.mockReset();
    getDocumentStatusMock.mockReset();
    deleteDocumentMock.mockReset();
    getMessagesMock.mockReset();

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

  it("queues document processing and reloads the list", async () => {
    const pendingDoc = makeDocument({
      id: 201,
      status: "pending",
      processed_at: null,
    });
    const processingDoc = makeDocument({
      id: 201,
      status: "processing",
      processed_at: null,
    });

    getDashboardContextMock.mockResolvedValueOnce({
      user: makeUser(),
      documents: [pendingDoc],
    });
    getDocumentsMock.mockResolvedValueOnce({ documents: [processingDoc], total: 1 });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Process" }));

    await waitFor(() => {
      expect(processDocumentMock).toHaveBeenCalledWith(201);
      expect(getDocumentsMock).toHaveBeenCalledTimes(1);
    });
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
    pushMock.mockReset();
    isLoggedInMock.mockReset();
    getDashboardContextMock.mockReset();
    getDocumentsMock.mockReset();
    getMessagesMock.mockReset();

    isLoggedInMock.mockReturnValue(true);
    getDashboardContextMock.mockResolvedValue({
      user: makeUser(),
      documents: [],
    });
    getMessagesMock.mockResolvedValue({ messages: [], total: 0 });
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

  it("chat section has w-full in tab mode for centering parity with PDF section", async () => {
    // jsdom defaults innerWidth to 0, which triggers tab layout
    await selectDocument();

    const chatSection = screen.getByText("Ask a question about this document")
      .closest("section");
    expect(chatSection).not.toBeNull();
    expect(chatSection!.className).toContain("w-full");
    expect(chatSection!.className).toContain("max-w-5xl");
  });
});
