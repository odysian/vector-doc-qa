import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEffect, type ReactNode } from "react";
import { PdfViewer } from "@/app/components/dashboard/PdfViewer";
import { api } from "@/lib/api";

const mockPdfState = vi.hoisted(() => ({
  numPages: 2,
  spansByPage: new Map<number, string[]>(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getDocumentFile: vi.fn(),
    },
  };
});

vi.mock("react-pdf", () => {
  return {
    Document: ({
      children,
      onLoadSuccess,
    }: {
      children: ReactNode;
      onLoadSuccess?: ({ numPages }: { numPages: number }) => void;
    }) => {
      useEffect(() => {
        onLoadSuccess?.({ numPages: mockPdfState.numPages });
      }, [onLoadSuccess]);
      return <div data-testid="mock-react-pdf-document">{children}</div>;
    },
    Page: ({ pageNumber, width }: { pageNumber: number; width?: number }) => {
      const spans = mockPdfState.spansByPage.get(pageNumber) ?? [];
      return (
        <div data-testid={`mock-page-${pageNumber}`} data-width={width ?? 0}>
          <div className="react-pdf__Page__textContent">
            {spans.map((text, index) => (
              <span key={`${pageNumber}-${index}`}>{text}</span>
            ))}
          </div>
        </div>
      );
    },
    pdfjs: {
      GlobalWorkerOptions: {
        workerSrc: "",
      },
    },
  };
});

const getDocumentFileMock = vi.mocked(api.getDocumentFile);
const baseViewerProps = {
  filename: "guide.pdf",
  uploadedAt: "2026-03-02T12:00:00Z",
  onBack: () => {},
  backLabel: "Back to Documents",
};

describe("PdfViewer citation highlight behavior", () => {
  let scrollIntoViewSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockPdfState.numPages = 2;
    mockPdfState.spansByPage.clear();
    getDocumentFileMock.mockReset();
    getDocumentFileMock.mockResolvedValue({
      arrayBuffer: vi.fn().mockResolvedValue(new ArrayBuffer(16)),
    } as unknown as Blob);

    scrollIntoViewSpy = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoViewSpy,
    });

    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      }
    );
    vi.stubGlobal(
      "requestAnimationFrame",
      (callback: FrameRequestCallback) => {
        callback(performance.now());
        return 0;
      }
    );
    vi.stubGlobal(
      "cancelAnimationFrame",
      () => {}
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders context header and calls the back action", async () => {
    const onBack = vi.fn();
    render(
      <PdfViewer
        {...baseViewerProps}
        documentId={7}
        onBack={onBack}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("guide.pdf")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Back to Documents" }));

    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("supports zoom in/out and fit-width reset controls", async () => {
    const { getByTestId } = render(<PdfViewer {...baseViewerProps} documentId={7} />);

    await waitFor(() => {
      expect(getDocumentFileMock).toHaveBeenCalledWith(7);
      expect(screen.getByText("Page 1")).toBeInTheDocument();
    });

    const page = getByTestId("mock-page-1");
    const initialWidth = Number(page.getAttribute("data-width"));
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));

    await waitFor(() => {
      expect(Number(page.getAttribute("data-width"))).toBeGreaterThan(initialWidth);
    });

    fireEvent.click(screen.getByRole("button", { name: "Fit width" }));
    await waitFor(() => {
      expect(Number(page.getAttribute("data-width"))).toBe(initialWidth);
    });
  });

  it("navigates to next page via arrow button", async () => {
    mockPdfState.numPages = 3;

    render(<PdfViewer {...baseViewerProps} documentId={8} />);
    await waitFor(() => {
      expect(screen.getByText("1 / 3")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Next page" }));

    await waitFor(() => {
      expect(scrollIntoViewSpy).toHaveBeenCalled();
    });
  });

  it("applies transient text highlight when snippet matching succeeds", async () => {
    mockPdfState.spansByPage.set(1, [
      "Acme Corp posted",
      "Q4 revenue",
      "of $5M with strong growth",
      "and expanded margins",
    ]);

    const { container } = render(
      <PdfViewer
        {...baseViewerProps}
        documentId={7}
        highlightPage={1}
        highlightSnippet="Q4 revenue of $5M with strong growth and expanded margins."
      />
    );

    await waitFor(() => {
      expect(getDocumentFileMock).toHaveBeenCalledWith(7);
      expect(screen.getByText("Page 1")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(scrollIntoViewSpy).toHaveBeenCalled();
      const highlighted = container.querySelectorAll(".citation-text-highlight");
      expect(highlighted).toHaveLength(3);
    });

    await waitFor(() => {
      expect(container.querySelectorAll(".citation-text-highlight")).toHaveLength(0);
    }, { timeout: 4200 });
  });

  it("reapplies text highlight when the same-page citation is retriggered", async () => {
    mockPdfState.spansByPage.set(1, [
      "Acme Corp posted",
      "Q4 revenue",
      "of $5M with strong growth",
      "and expanded margins",
    ]);

    const { container, rerender } = render(
      <PdfViewer
        {...baseViewerProps}
        documentId={7}
        highlightPage={1}
        highlightSnippet="Q4 revenue of $5M with strong growth and expanded margins."
      />
    );

    await waitFor(() => {
      expect(container.querySelectorAll(".citation-text-highlight")).toHaveLength(3);
    });
    await waitFor(() => {
      expect(container.querySelectorAll(".citation-text-highlight")).toHaveLength(0);
    }, { timeout: 4200 });

    rerender(
      <PdfViewer
        {...baseViewerProps}
        documentId={7}
        highlightPage={null}
        highlightSnippet={null}
      />
    );
    rerender(
      <PdfViewer
        {...baseViewerProps}
        documentId={7}
        highlightPage={1}
        highlightSnippet="Q4 revenue of $5M with strong growth and expanded margins."
      />
    );

    await waitFor(() => {
      expect(scrollIntoViewSpy).toHaveBeenCalledTimes(2);
      expect(container.querySelectorAll(".citation-text-highlight")).toHaveLength(3);
    });
  });

  it("highlights snippet when text layer becomes available during retry window", async () => {
    const queuedFrames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      queuedFrames.push(callback);
      return queuedFrames.length;
    });
    vi.stubGlobal("cancelAnimationFrame", () => {});

    const { container, rerender } = render(
      <PdfViewer
        {...baseViewerProps}
        documentId={7}
        highlightPage={1}
        highlightSnippet="Q4 revenue of $5M with strong growth and expanded margins."
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Page 1")).toBeInTheDocument();
      expect(container.querySelectorAll(".citation-text-highlight")).toHaveLength(0);
      expect(queuedFrames.length).toBeGreaterThan(0);
    });

    mockPdfState.spansByPage.set(1, [
      "Acme Corp posted",
      "Q4 revenue",
      "of $5M with strong growth",
      "and expanded margins",
    ]);
    rerender(
      <PdfViewer
        {...baseViewerProps}
        documentId={7}
        highlightPage={1}
        highlightSnippet="Q4 revenue of $5M with strong growth and expanded margins."
      />
    );

    await act(async () => {
      while (queuedFrames.length > 0) {
        const callback = queuedFrames.shift();
        callback?.(performance.now());
        await Promise.resolve();
      }
    });

    await waitFor(() => {
      expect(container.querySelectorAll(".citation-text-highlight")).toHaveLength(3);
    });
  });

  it("falls back to page-level highlight when snippet does not match", async () => {
    mockPdfState.spansByPage.set(2, [
      "Security policy mandates credential rotation every ninety days.",
      "Use MFA for all privileged actions.",
    ]);

    render(
      <PdfViewer
        {...baseViewerProps}
        documentId={11}
        highlightPage={2}
        highlightSnippet="Quarterly revenue hit five million with double-digit growth."
      />
    );

    const pageHeading = await screen.findByText("Page 2");
    const pageWrapper = pageHeading.parentElement?.parentElement;

    await waitFor(() => {
      expect(scrollIntoViewSpy).toHaveBeenCalled();
      expect(pageWrapper).toBeTruthy();
      expect(pageWrapper?.className).toContain("border-lapis-400/70");
      expect(document.querySelectorAll(".citation-text-highlight")).toHaveLength(0);
    });
  });

  it("does not apply text highlight for weak single-token overlap", async () => {
    mockPdfState.spansByPage.set(2, [
      "Security policy mandates credential rotation every ninety days.",
      "Use MFA for all privileged actions.",
    ]);

    render(
      <PdfViewer
        {...baseViewerProps}
        documentId={12}
        highlightPage={2}
        highlightSnippet="Policy exceptions require annual board signoff for temporary contractors."
      />
    );

    const pageHeading = await screen.findByText("Page 2");
    const pageWrapper = pageHeading.parentElement?.parentElement;

    await waitFor(() => {
      expect(scrollIntoViewSpy).toHaveBeenCalled();
      expect(pageWrapper?.className).toContain("border-lapis-400/70");
      expect(document.querySelectorAll(".citation-text-highlight")).toHaveLength(0);
    });
  });

  it("applies text highlight for strong overlap when exact phrase match is unavailable", async () => {
    mockPdfState.spansByPage.set(2, [
      "Password policy requires credential rotation every ninety days.",
      "Privileged access reviews and incident response ownership are mandatory.",
    ]);

    const { container } = render(
      <PdfViewer
        {...baseViewerProps}
        documentId={13}
        highlightPage={2}
        highlightSnippet="Credential policy and access ownership controls are mandatory during incident drills."
      />
    );

    await waitFor(() => {
      expect(scrollIntoViewSpy).toHaveBeenCalled();
      expect(container.querySelectorAll(".citation-text-highlight").length).toBeGreaterThan(0);
    });
  });
});
