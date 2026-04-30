# Admin Token Auth Design

## Goal

Protect the admin review surface without changing the public API or introducing a full login system.

## Recommended Approach

Use a shared secret sent in an `X-Admin-Token` header on admin-only requests.

This keeps the public feed and detail endpoints open, keeps the admin integration lightweight, and fits the current MVP stage better than a session-based auth system.

## Backend Design

- Add `ADMIN_API_TOKEN` to backend settings.
- Add a reusable admin-auth dependency in the backend.
- Require that dependency for all `/admin/*` routes.
- Reject missing or incorrect tokens with `401 Unauthorized`.
- Preserve the current public endpoints exactly as they are.

## Frontend Design

- Add a lightweight admin token entry field in the app UI.
- Store the token in `localStorage` so the editor does not need to re-enter it on every refresh.
- Only call admin endpoints when a token is present.
- Send `X-Admin-Token` on admin API requests only.
- Show a clear admin access state when the token is missing or rejected.

## UX Expectations

- Public readers can still browse the feed and incident detail views with no auth.
- Editors can unlock the review queue by entering the shared token.
- If the token is invalid, the UI should show a specific access error rather than a generic load failure.

## Error Handling

- Missing token: do not attempt admin queue fetch until a token is entered.
- Invalid token: backend returns `401`, frontend shows an admin-auth error state.
- Public feed failures remain separate from admin-auth failures.

## Testing

- Backend tests for:
  - `401` on missing token
  - `401` on incorrect token
  - `200` for valid token
- Frontend tests for:
  - hidden/locked admin state before token entry
  - successful admin queue load after token submission
  - clear auth error message on `401`

## Documentation Updates

- Add `ADMIN_API_TOKEN` to `.env.example`.
- Update `README.md` to explain the admin token requirement.
- Update MVP status and launch checklist docs to reflect that admin routes are protected by a shared secret once this slice lands.
