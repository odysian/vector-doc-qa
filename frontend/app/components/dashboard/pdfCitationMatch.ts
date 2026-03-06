export interface CitationSpanMatch {
  startIndex: number;
  endIndex: number;
}

const WINDOW_SIZES = [24, 18, 12, 8, 6];
const MIN_CANDIDATE_CHARS = 24;

export const normalizeCitationText = (value: string): string => {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
};

const buildCandidatePhrases = (normalizedSnippet: string): string[] => {
  const words = normalizedSnippet.split(" ").filter(Boolean);
  if (words.length === 0) return [];

  const candidates: string[] = [];
  const seen = new Set<string>();

  for (const windowSize of WINDOW_SIZES) {
    if (words.length < windowSize) continue;

    const starts = [0, Math.floor((words.length - windowSize) / 2), words.length - windowSize];
    for (const start of starts) {
      const candidate = words.slice(start, start + windowSize).join(" ").trim();
      if (candidate.length < MIN_CANDIDATE_CHARS || seen.has(candidate)) continue;
      seen.add(candidate);
      candidates.push(candidate);
    }
  }

  if (candidates.length === 0 && normalizedSnippet.length >= MIN_CANDIDATE_CHARS) {
    candidates.push(normalizedSnippet);
  }

  return candidates;
};

export const findCitationSpanMatch = (
  spanTexts: string[],
  snippet: string
): CitationSpanMatch | null => {
  const normalizedSnippet = normalizeCitationText(snippet);
  if (!normalizedSnippet) return null;

  let pageText = "";
  const ranges: Array<{ spanIndex: number; start: number; end: number }> = [];

  spanTexts.forEach((text, spanIndex) => {
    const normalizedSpan = normalizeCitationText(text);
    if (!normalizedSpan) return;

    if (pageText.length > 0) pageText += " ";
    const start = pageText.length;
    pageText += normalizedSpan;
    ranges.push({ spanIndex, start, end: pageText.length });
  });

  if (!pageText || ranges.length === 0) return null;

  for (const candidate of buildCandidatePhrases(normalizedSnippet)) {
    const matchStart = pageText.indexOf(candidate);
    if (matchStart === -1) continue;
    const matchEnd = matchStart + candidate.length;

    const startRange = ranges.find((range) => range.end > matchStart);
    const endRange = [...ranges].reverse().find((range) => range.start < matchEnd);
    if (!startRange || !endRange || endRange.spanIndex < startRange.spanIndex) continue;

    return {
      startIndex: startRange.spanIndex,
      endIndex: endRange.spanIndex,
    };
  }

  return null;
};
