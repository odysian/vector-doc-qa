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

  it("returns null when snippet candidate cannot be found", () => {
    const match = findCitationSpanMatch(
      ["Security policy requires rotation every ninety days."],
      "Quarterly revenue hit five million with double-digit growth."
    );

    expect(match).toBeNull();
  });
});
