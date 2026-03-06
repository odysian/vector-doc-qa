import { describe, expect, it } from "vitest";
import { findCitationSpanMatch, normalizeCitationText } from "@/app/components/dashboard/pdfCitationMatch";

describe("pdfCitationMatch", () => {
  it("normalizes punctuation and whitespace", () => {
    expect(normalizeCitationText("  Revenue:\n$5M (Q4)!  ")).toBe("revenue 5m q4");
  });

  it("finds span range when snippet appears across neighboring spans", () => {
    const spans = [
      "Acme Corp posted",
      "Q4 revenue",
      "of $5M with strong growth",
      "and expanded margins",
    ];

    const match = findCitationSpanMatch(
      spans,
      "Q4 revenue of $5M with strong growth and expanded margins."
    );

    expect(match).toEqual({
      startIndex: 1,
      endIndex: 3,
    });
  });

  it("prefers the longest contiguous snippet match over shorter anchor fragments", () => {
    const spans = [
      "Revenue growth and expanded margins are highlighted in summary notes.",
      "Additional short anchor phrases can appear more than once.",
      "Detailed findings include",
      "Q4 revenue of $5M with strong growth and expanded margins",
      "with improved retention outcomes in enterprise accounts.",
    ];

    const match = findCitationSpanMatch(
      spans,
      "The report states Q4 revenue of $5M with strong growth and expanded margins with improved retention outcomes in enterprise accounts."
    );

    expect(match).toEqual({
      startIndex: 3,
      endIndex: 4,
    });
  });

  it("returns null when only a short weak overlap is found", () => {
    const match = findCitationSpanMatch(
      ["Risk section: revenue growth appears once in the appendix."],
      "The cited section says revenue growth accelerated due to stronger retention and net expansion."
    );

    expect(match).toBeNull();
  });

  it("returns null when snippet candidate cannot be found", () => {
    const match = findCitationSpanMatch(
      ["Security policy requires rotation every ninety days."],
      "Quarterly revenue hit five million with double-digit growth."
    );

    expect(match).toBeNull();
  });
});
