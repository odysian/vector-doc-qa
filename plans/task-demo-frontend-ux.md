## Summary

Add "Try Demo" button on login page, demo user restrictions in the dashboard UI, and an informational banner prompting account creation.

Parent Spec: #79

**Depends on:** Task 1 (demo seed infrastructure) for `is_demo` field in `/api/auth/me`.

## Scope

**In scope:**
- "Try Demo" button on login page that auto-fills demo credentials and submits
- After login as demo user (`is_demo: true` from `/api/auth/me`):
  - Upload zone disabled or hidden, with tooltip/message
  - Delete button hidden on document cards
  - Subtle banner: "You're using a demo account. Create an account to upload your own documents."
- `is_demo` field added to frontend `User` type

**Out of scope:**
- Backend changes (handled in Task 1)
- Demo document generation (handled in Task 2)
- Restricting query endpoints for demo user (demo user can query freely)

## Files

- `app/login/page.tsx` (demo button)
- `app/components/dashboard/UploadZone.tsx` (disabled state)
- `app/components/dashboard/DocumentList.tsx` (hide delete)
- `app/dashboard/page.tsx` (banner, pass `isDemo` to children)
- `lib/api.types.ts` (add `is_demo` to User type)

## Acceptance Criteria

- [ ] "Try Demo" button visible on login page
- [ ] Clicking "Try Demo" logs in with demo credentials
- [ ] Upload zone shows disabled state with explanation for demo user
- [ ] Delete button hidden for demo user
- [ ] Banner visible with link/prompt to create account
- [ ] Non-demo users see no changes (no regression)
- [ ] `make frontend-verify` passes

## Verification

```bash
make frontend-verify
```
