export interface CitationSpanMatch {
  startIndex: number;
  endIndex: number;
}

const WINDOW_SIZES = [24, 18, 12, 8, 6, 4];
const MIN_CANDIDATE_CHARS = 24;
const MIN_ANCHORED_CANDIDATE_CHARS = 12;
const MAX_CANDIDATES = 120;

export const normalizeCitationText = (value: string): string => {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
};

const buildCandidatePhrases = (
  normalizedSnippet: string,
  options?: { anchoredOnly?: boolean; minChars?: number }
): string[] => {
  const words = normalizedSnippet.split(" ").filter(Boolean);
  if (words.length === 0) return [];
  const anchoredOnly = options?.anchoredOnly ?? false;
  const minChars = options?.minChars ?? MIN_CANDIDATE_CHARS;

  const candidates: string[] = [];
  const seen = new Set<string>();

  if (anchoredOnly && normalizedSnippet.length >= minChars) {
    seen.add(normalizedSnippet);
    candidates.push(normalizedSnippet);
  }

  for (const windowSize of WINDOW_SIZES) {
    if (words.length < windowSize) continue;

    if (anchoredOnly) {
      const candidate = words.slice(0, windowSize).join(" ").trim();
      if (candidate.length >= minChars && !seen.has(candidate)) {
        seen.add(candidate);
        candidates.push(candidate);
        if (candidates.length >= MAX_CANDIDATES) return candidates;
      }
      continue;
    }

    const starts: number[] = [];
    const maxStart = words.length - windowSize;
    const step = Math.max(1, Math.floor(windowSize / 2));
    for (let start = 0; start <= maxStart; start += step) {
      starts.push(start);
    }
    if (starts[starts.length - 1] !== maxStart) starts.push(maxStart);

    for (const start of starts) {
      const candidate = words.slice(start, start + windowSize).join(" ").trim();
      if (candidate.length < minChars || seen.has(candidate)) continue;
      seen.add(candidate);
      candidates.push(candidate);
      if (candidates.length >= MAX_CANDIDATES) return candidates;
    }
  }

  if (!anchoredOnly && candidates.length === 0 && normalizedSnippet.length >= minChars) {
    candidates.push(normalizedSnippet);
  }

  return candidates;
};

const findMatchFromCandidates = (
  pageText: string,
  ranges: Array<{ spanIndex: number; start: number; end: number }>,
  candidates: string[]
): CitationSpanMatch | null => {
  for (const candidate of candidates) {
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

  const anchoredMatch = findMatchFromCandidates(
    pageText,
    ranges,
    buildCandidatePhrases(normalizedSnippet, {
      anchoredOnly: true,
      minChars: MIN_ANCHORED_CANDIDATE_CHARS,
    })
  );
  if (anchoredMatch) return anchoredMatch;

  return findMatchFromCandidates(pageText, ranges, buildCandidatePhrases(normalizedSnippet));
};
