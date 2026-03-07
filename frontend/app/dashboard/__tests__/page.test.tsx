import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import { api, ApiError, SessionExpiredError, isLoggedIn, type Document } from "@/lib/api";

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
    api: {
      ...actual.api,
      getCurrentUser: vi.fn(),
      getDocuments: vi.fn(),
      uploadDocument: vi.fn(),
      processDocument: vi.fn(),
      getDocumentStatus: vi.fn(),
      deleteDocument: vi.fn(),
      getMessages: vi.fn(),
      logout: vi.fn(),
    },
  };
});

const isLoggedInMock = vi.mocked(isLoggedIn);
const getCurrentUserMock = vi.mocked(api.getCurrentUser);
const getDocumentsMock = vi.mocked(api.getDocuments);
const uploadDocumentMock = vi.mocked(api.uploadDocument);
const processDocumentMock = vi.mocked(api.processDocument);
const getDocumentStatusMock = vi.mocked(api.getDocumentStatus);
const deleteDocumentMock = vi.mocked(api.deleteDocument);
const getMessagesMock = vi.mocked(api.getMessages);

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

function makeUser(overrides: Partial<Awaited<ReturnType<typeof api.getCurrentUser>>> = {}) {
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
    getCurrentUserMock.mockReset();
    getDocumentsMock.mockReset();
    uploadDocumentMock.mockReset();
    processDocumentMock.mockReset();
    getDocumentStatusMock.mockReset();
    deleteDocumentMock.mockReset();
    getMessagesMock.mockReset();

    isLoggedInMock.mockReturnValue(true);
    getCurrentUserMock.mockResolvedValue(makeUser());
    getDocumentsMock.mockResolvedValue({ documents: [], total: 0 });
    getMessagesMock.mockResolvedValue({ messages: [], total: 0 });
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
  });

  it("renders loaded documents after successful fetch", async () => {
    const doc = makeDocument({ filename: "guide.pdf" });
    getDocumentsMock.mockResolvedValueOnce({ documents: [doc], total: 1 });

    render(<DashboardPage />);

    expect(await screen.findByText("guide.pdf")).toBeInTheDocument();
    expect(screen.getByText("Select a document")).toBeInTheDocument();
  });

  it("renders empty state when no documents are returned", async () => {
    getDocumentsMock.mockResolvedValueOnce({ documents: [], total: 0 });

    render(<DashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "No documents yet" })
    ).toBeInTheDocument();
  });

  it("renders API error text when document load fails", async () => {
    getDocumentsMock.mockRejectedValueOnce(
      new ApiError(500, "Failed to load documents from API")
    );

    render(<DashboardPage />);

    expect(
      await screen.findByText("Failed to load documents from API")
    ).toBeInTheDocument();
  });

  it("redirects to login when session refresh fails", async () => {
    getDocumentsMock.mockRejectedValueOnce(new SessionExpiredError());

    render(<DashboardPage />);

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/login");
    });
  });

  it("uploads a document and reloads the list on success", async () => {
    const doc = makeDocument();
    getDocumentsMock
      .mockResolvedValueOnce({ documents: [doc], total: 1 })
      .mockResolvedValueOnce({ documents: [doc], total: 1 });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    const fileInput = screen.getByLabelText("Upload PDF");
    const file = new File(["%PDF"], "upload.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(uploadDocumentMock).toHaveBeenCalledWith(file);
      expect(getDocumentsMock).toHaveBeenCalledTimes(2);
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

    getDocumentsMock
      .mockResolvedValueOnce({ documents: [pendingDoc], total: 1 })
      .mockResolvedValueOnce({ documents: [processingDoc], total: 1 });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Process" }));

    await waitFor(() => {
      expect(processDocumentMock).toHaveBeenCalledWith(201);
      expect(getDocumentsMock).toHaveBeenCalledTimes(2);
    });
  });

  it("deletes a document and reloads the list", async () => {
    const doc = makeDocument({ id: 301 });
    getDocumentsMock
      .mockResolvedValueOnce({ documents: [doc], total: 1 })
      .mockResolvedValueOnce({ documents: [], total: 0 });

    render(<DashboardPage />);

    await screen.findByText("alpha.pdf");
    fireEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteDocumentMock).toHaveBeenCalledWith(301);
      expect(getDocumentsMock).toHaveBeenCalledTimes(2);
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("hides demo-restricted controls and shows demo banner for demo users", async () => {
    const doc = makeDocument({ id: 302 });
    getCurrentUserMock.mockResolvedValueOnce(makeUser({ is_demo: true }));
    getDocumentsMock.mockResolvedValueOnce({ documents: [doc], total: 1 });

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
    getCurrentUserMock.mockResolvedValueOnce(makeUser({ is_demo: false }));
    getDocumentsMock.mockResolvedValueOnce({ documents: [doc], total: 1 });

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
    getCurrentUserMock.mockReset();
    getDocumentsMock.mockReset();
    getMessagesMock.mockReset();

    isLoggedInMock.mockReturnValue(true);
    getCurrentUserMock.mockResolvedValue(makeUser());
    getMessagesMock.mockResolvedValue({ messages: [], total: 0 });
  });

  async function selectDocument() {
    const doc = makeDocument();
    getDocumentsMock.mockResolvedValueOnce({ documents: [doc], total: 1 });
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
