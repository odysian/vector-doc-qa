## Summary
Improve citation text highlight quality in the PDF viewer so highlights emphasize the most meaningful portion of the cited snippet instead of only a short nearby fragment.

Parent Spec: #69
Follow-up to: #71 and PR #88

## Problem
Current matching can succeed but may highlight only a small anchor fragment, which gives weak visual guidance and low confidence for users.

## Scope
In scope:
- Improve client-side snippet-to-text-layer matching strategy in `PdfViewer`/matching helper
- Prefer longer contiguous matches over short anchors
- Preserve page-level fallback behavior when robust match is unavailable
- Add tests that validate highlight coverage quality and fallback behavior

Out of scope:
- Backend schema/API changes
- OCR
- Guaranteed character offsets from backend

## Acceptance Criteria
- [ ] On successful match, highlight covers a meaningful contiguous phrase from the citation (not just a tiny anchor token window).
- [ ] Matching prefers the best available span coverage on the cited page.
- [ ] If robust match is not found, existing page-level highlight/scroll fallback remains intact.
- [ ] Repeat same-page citation clicks still retrigger highlight reliably.
- [ ] Delayed text-layer rendering within retry window still allows match+highlight.
- [ ] Frontend tests cover improved span coverage selection, retry timing behavior, and fallback behavior.

## Verification
- `make frontend-verify`

## Suggested Labels
- `type:task`
- `area:frontend`
