## Summary
- add a `Try Demo` shortcut on the login page that submits seeded demo credentials
- load `is_demo` from `/api/auth/me` in dashboard startup flow and render a demo-account banner
- disable upload interactions and hide document delete actions for demo users
- extend frontend test coverage for demo login and demo/non-demo dashboard behavior

Closes #82

## Verification
- `make frontend-verify`
