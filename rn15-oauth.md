# RN15 OAuth Implementation Plan

Ticket: `#15` / `MVP2-005: Add OAuth Login And Web Sessions`

## Goal

Allow independent users to sign in to the web app without password registration.

## Scope

- Add OAuth provider configuration through environment variables.
- Implement OAuth login start endpoints.
- Implement OAuth callback endpoints.
- Support Microsoft OAuth.
- Support Google OAuth.
- Create a session cookie after successful login.
- Add current-user session lookup.
- Link existing OAuth identities.
- Create users on first login.
- Store provider identity rows in `oauth_identities`.

## Existing Foundation

- User rows live in `/state/users.db`.
- `backend/database.py` initializes `users` and `oauth_identities`.
- `backend/users.py:create_user(email)` creates the app user, provisions Maildir, sets `imap_username` to normalized email, and generates an IMAP app password.
- Admin user creation remains CLI-only. OAuth callback may create users after provider identity verification; do not add public admin creation endpoints.
- `imap_password` plaintext is returned once by user creation/reset and is not stored.

## Proposed Backend Shape

Endpoints:

- `GET /auth/login/google`
- `GET /auth/callback/google`
- `GET /auth/login/microsoft`
- `GET /auth/callback/microsoft`
- `POST /auth/logout`
- `GET /me`

Core helpers/modules to consider:

- `backend/oauth.py`: Authlib provider registry and redirect URI configuration.
- Starlette `SessionMiddleware`: signed cookie sessions for OAuth state and app login state.
- `backend/users.py`: add lookup helpers needed by OAuth if they do not belong in a new module.

Environment variables:

- `SESSION_SECRET`
- `SESSION_COOKIE_SECURE`
- `PUBLIC_BASE_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI` or derive from `PUBLIC_BASE_URL`
- `MICROSOFT_CLIENT_ID`
- `MICROSOFT_CLIENT_SECRET`
- `MICROSOFT_REDIRECT_URI` or derive from `PUBLIC_BASE_URL`

Provider endpoints to verify during implementation:

- Google authorization/token/userinfo endpoints.
- Microsoft authorization/token/userinfo endpoints.

## Data Flow

1. User starts login with `/auth/login/<provider>`.
2. Backend generates OAuth `state`, stores it in a short-lived signed session or state cookie, and redirects to provider.
3. Provider redirects to `/auth/callback/<provider>`.
4. Backend validates `state`.
5. Backend exchanges code for tokens.
6. Backend fetches provider identity/email.
7. Backend finds existing `oauth_identities` row by `(provider, provider_subject)`.
8. If found, load linked user.
9. If not found, find or create user by verified email, then insert `oauth_identities`.
10. Backend creates app session cookie.
11. `/me` returns the current user from the app session.

## Open Decisions

- Session storage: use Starlette signed-cookie sessions through `SessionMiddleware`.
- OAuth library: use Authlib with HTTPX via the Starlette integration.
- Whether first login should display the generated IMAP password immediately or defer that to a later account/setup page.
- Whether unverified provider emails should be rejected.
- Production cookie policy: exact `secure`, `httponly`, `samesite`, and max-age settings.

## Implementation Checklist

- [x] Inspect current `oauth_identities` schema and decide whether it needs migration.
- [x] Add backend dependencies if needed.
- [x] Add session cookie configuration loading.
- [x] Add OAuth provider configuration loading.
- [x] Add session creation/current-user/logout helpers.
- [x] Add OAuth login-start endpoint for Google.
- [ ] Add OAuth callback endpoint for Google.
- [x] Add OAuth login-start endpoint for Microsoft.
- [ ] Add OAuth callback endpoint for Microsoft.
- [ ] Add `oauth_identities` lookup/linking logic.
- [ ] Reuse `create_user(email)` for first-login user creation.
- [x] Add `/me`.
- [ ] Update README with required OAuth env vars and local callback URLs.
- [ ] Update `agents-project-overview.md`.
- [ ] Run Python compile checks.
- [ ] Run local SQLite smoke tests for identity linking and repeated login behavior.

## Acceptance Checklist

- [ ] A new Microsoft login creates a user and starts a session.
- [ ] A new Google login creates a user and starts a session.
- [ ] A repeated provider login returns the existing user.
- [ ] OAuth secrets are loaded only from environment variables.
- [ ] Session cookies are secure in production.

## Progress Log

- 2026-06-30: Created implementation planning document.
- 2026-06-30: Added signed-cookie session helpers, current-user lookup, `/me`, and logout endpoints.
- 2026-07-01: Switched to Authlib plus Starlette `SessionMiddleware`, removed custom session signing, and added Google/Microsoft login-start endpoints.
