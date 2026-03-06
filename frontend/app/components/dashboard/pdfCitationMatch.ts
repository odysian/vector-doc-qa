export interface CitationSpanMatch {
  startIndex: number;
  endIndex: number;
}

const MIN_ROBUST_MATCH_WORDS = 4;
const MIN_ROBUST_MATCH_CHARS = 24;

export const normalizeCitationText = (value: string): string => {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
};

interface BestWordMatch {
  snippetStart: number;
  pageStart: number;
  length: number;
  charLength: number;
}

export const findCitationSpanMatch = (
  spanTexts: string[],
  snippet: string
): CitationSpanMatch | null => {
  const normalizedSnippet = normalizeCitationText(snippet);
  if (!normalizedSnippet) return null;
  const snippetWords = normalizedSnippet.split(" ").filter(Boolean);
  if (snippetWords.length === 0) return null;

  const pageWords: string[] = [];
  const pageWordSpanIndices: number[] = [];

  spanTexts.forEach((text, spanIndex) => {
    const normalizedSpan = normalizeCitationText(text);
    if (!normalizedSpan) return;
    const normalizedWords = normalizedSpan.split(" ").filter(Boolean);
    normalizedWords.forEach((word) => {
      pageWords.push(word);
      pageWordSpanIndices.push(spanIndex);
    });
  });

  if (pageWords.length === 0) return null;

  const pageWordPositions = new Map<string, number[]>();
  pageWords.forEach((word, index) => {
    const positions = pageWordPositions.get(word);
    if (positions) {
      positions.push(index);
    } else {
      pageWordPositions.set(word, [index]);
    }
  });

  let bestMatch: BestWordMatch | null = null;
  for (let snippetStart = 0; snippetStart < snippetWords.length; snippetStart += 1) {
    const startWord = snippetWords[snippetStart];
    const pageStarts = pageWordPositions.get(startWord);
    if (!pageStarts || pageStarts.length === 0) continue;

    const snippetWordsRemaining = snippetWords.length - snippetStart;
    if (bestMatch && snippetWordsRemaining < bestMatch.length) continue;

    for (const pageStart of pageStarts) {
      const pageWordsRemaining = pageWords.length - pageStart;
      if (bestMatch && Math.min(snippetWordsRemaining, pageWordsRemaining) < bestMatch.length) {
        continue;
      }

      let matchLength = 0;
      while (
        snippetStart + matchLength < snippetWords.length &&
        pageStart + matchLength < pageWords.length &&
        snippetWords[snippetStart + matchLength] === pageWords[pageStart + matchLength]
      ) {
        matchLength += 1;
      }
      if (matchLength === 0) continue;

      const matchedSnippet = snippetWords
        .slice(snippetStart, snippetStart + matchLength)
        .join(" ");
      const candidate: BestWordMatch = {
        snippetStart,
        pageStart,
        length: matchLength,
        charLength: matchedSnippet.length,
      };

      if (
        !bestMatch ||
        candidate.length > bestMatch.length ||
        (candidate.length === bestMatch.length && candidate.charLength > bestMatch.charLength)
      ) {
        bestMatch = candidate;
      }
    }
  }

  if (!bestMatch) return null;

  const isFullSnippetMatch = bestMatch.length === snippetWords.length;
  const isRobustPartialMatch =
    bestMatch.length >= MIN_ROBUST_MATCH_WORDS && bestMatch.charLength >= MIN_ROBUST_MATCH_CHARS;
  if (!isFullSnippetMatch && !isRobustPartialMatch) return null;

  const startIndex = pageWordSpanIndices[bestMatch.pageStart];
  const endWordIndex = bestMatch.pageStart + bestMatch.length - 1;
  const endIndex = pageWordSpanIndices[endWordIndex];
  if (startIndex === undefined || endIndex === undefined || endIndex < startIndex) return null;

  return {
    startIndex,
    endIndex,
  };
};
