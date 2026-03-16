import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { ChatWindow } from "@/app/components/dashboard/ChatWindow";
import { chatService } from "@/lib/services/chatService";
import type { Document } from "@/lib/api";

vi.mock("@/lib/services/chatService", async () => {
  const actual = await vi.importActual<typeof import("@/lib/services/chatService")>(
    "@/lib/services/chatService"
  );
  return {
    ...actual,
    chatService: {
      ...actual.chatService,
      getMessages: vi.fn(),
      queryDocumentStream: vi.fn(),
    },
  };
});

const getMessagesMock = vi.mocked(chatService.getMessages);

const documentFixture: Document = {
  id: 7,
  user_id: 1,
  filename: "guide.pdf",
  file_size: 1024,
  status: "completed",
  uploaded_at: "2026-03-02T12:00:00Z",
  processed_at: "2026-03-02T12:01:00Z",
  error_message: null,
};

function setupWithAssistantMessage(content: string) {
  getMessagesMock.mockResolvedValueOnce({
    messages: [
      {
        id: 1,
        document_id: documentFixture.id,
        user_id: documentFixture.user_id,
        role: "assistant",
        content,
        created_at: "2026-03-10T09:00:00Z",
      },
    ],
    total: 1,
  });
  return render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
}

describe("ChatWindow markdown rendering", () => {
  beforeEach(() => {
    getMessagesMock.mockResolvedValue({ messages: [], total: 0 });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders bold markdown as <strong> in assistant messages", async () => {
    const { container } = setupWithAssistantMessage("This is **bold text** here.");
    await waitFor(() => {
      expect(container.querySelector("strong")).not.toBeNull();
    });
    expect(container.querySelector("strong")?.textContent).toBe("bold text");
  });

  it("renders bullet lists as <ul> in assistant messages", async () => {
    const { container } = setupWithAssistantMessage("- First item\n- Second item");
    await waitFor(() => {
      expect(container.querySelector("ul")).not.toBeNull();
    });
    expect(container.querySelectorAll("li")).toHaveLength(2);
  });

  it("renders heading markdown as heading element in assistant messages", async () => {
    const { container } = setupWithAssistantMessage("### Section Title");
    await waitFor(() => {
      expect(container.querySelector("h3")).not.toBeNull();
    });
    expect(container.querySelector("h3")?.textContent).toBe("Section Title");
  });

  it("renders inline code with monospace element in assistant messages", async () => {
    const { container } = setupWithAssistantMessage("Use `console.log` for output.");
    await waitFor(() => {
      expect(container.querySelector("code")).not.toBeNull();
    });
    expect(container.querySelector("code")?.textContent).toBe("console.log");
  });

  it("blocks javascript: protocol links — renders as span, not anchor", async () => {
    const { container } = setupWithAssistantMessage("[click me](javascript:alert(1))");
    await waitFor(() => {
      expect(screen.getByText("click me")).toBeInTheDocument();
    });
    // Must not render as an anchor with the unsafe href
    expect(container.querySelector("a[href^='javascript:']")).toBeNull();
    // Must render as a plain span
    expect(screen.getByText("click me").tagName.toLowerCase()).toBe("span");
  });

  it("blocks data: protocol links — renders as span, not anchor", async () => {
    const { container } = setupWithAssistantMessage("[payload](data:text/html,<script>x</script>)");
    await waitFor(() => {
      expect(screen.getByText("payload")).toBeInTheDocument();
    });
    expect(container.querySelector("a[href^='data:']")).toBeNull();
    expect(screen.getByText("payload").tagName.toLowerCase()).toBe("span");
  });

  it("allows https: links — renders as anchor with noopener", async () => {
    const { container } = setupWithAssistantMessage("[safe link](https://example.com)");
    await waitFor(() => {
      expect(container.querySelector("a")).not.toBeNull();
    });
    const anchor = container.querySelector("a");
    expect(anchor?.getAttribute("href")).toBe("https://example.com");
    expect(anchor?.getAttribute("rel")).toBe("noopener noreferrer");
    expect(anchor?.getAttribute("target")).toBe("_blank");
  });

  it("keeps user messages as plain text — does not render markdown", async () => {
    getMessagesMock.mockResolvedValueOnce({
      messages: [
        {
          id: 2,
          document_id: documentFixture.id,
          user_id: documentFixture.user_id,
          role: "user",
          content: "**not bold** just text",
          created_at: "2026-03-10T09:01:00Z",
        },
      ],
      total: 1,
    });
    const { container } = render(<ChatWindow document={documentFixture} onBack={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText("**not bold** just text")).toBeInTheDocument();
    });
    // No <strong> element — user messages are plain whitespace-pre-wrap
    expect(container.querySelector("strong")).toBeNull();
  });
});
