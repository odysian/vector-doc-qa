import { render, screen, waitFor } from "@testing-library/react";
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
    Page: ({ pageNumber }: { pageNumber: number }) => {
      const spans = mockPdfState.spansByPage.get(pageNumber) ?? [];
      return (
        <div data-testid={`mock-page-${pageNumber}`}>
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

  it("applies transient text highlight when snippet matching succeeds", async () => {
    mockPdfState.spansByPage.set(1, [
      "Acme Corp posted",
      "Q4 revenue",
      "of $5M with strong growth",
      "and expanded margins",
    ]);

    const { container } = render(
      <PdfViewer
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
      expect(highlighted.length).toBeGreaterThan(0);
    });

    await waitFor(() => {
      expect(container.querySelectorAll(".citation-text-highlight")).toHaveLength(0);
    }, { timeout: 2500 });
  });

  it("falls back to page-level highlight when snippet does not match", async () => {
    mockPdfState.spansByPage.set(2, [
      "Security policy mandates credential rotation every ninety days.",
      "Use MFA for all privileged actions.",
    ]);

    render(
      <PdfViewer
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
});
