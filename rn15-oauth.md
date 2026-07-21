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
- `backend/users.py:create_user(email)` creates CLI-managed users. OAuth users are created from `(provider, provider_subject)` and receive a persisted mailbox alias.
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
9. If not found, create a distinct user from `(provider, provider_subject)`, then insert `oauth_identities`. Email equality never links identities.
10. Backend creates app session cookie.
11. `/me` returns the current user from the app session.

## Open Decisions

- Session storage: use Starlette signed-cookie sessions through `SessionMiddleware`.
- OAuth library: use Authlib with HTTPX via the Starlette integration.
- Whether first login should display the generated IMAP password immediately or defer that to a later account/setup page.
- Whether unverified provider emails should be rejected.
- Production cookie policy: exact `secure`, `httponly`, `samesite`, and max-age settings. Decided: Starlette signed cookie sessions, `running_notes_session`, `SameSite=Lax`, 14-day max age, secure by default, and insecure cookies rejected when `APP_ENV=production`.

## Implementation Checklist

- [x] Define the clean `oauth_identities` schema.
- [x] Add backend dependencies if needed.
- [x] Add session cookie configuration loading.
- [x] Add OAuth provider configuration loading.
- [x] Add session creation/current-user/logout helpers.
- [x] Add OAuth login-start endpoint for Google.
- [x] Add OAuth callback endpoint for Google.
- [x] Add OAuth login-start endpoint for Microsoft.
- [x] Add OAuth callback endpoint for Microsoft.
- [x] Add `oauth_identities` lookup/linking logic.
- [x] Create first-login users from the stable provider and `sub` identity.
- [x] Add `/me`.
- [x] Update README with required OAuth env vars and local callback URLs.
- [ ] Update `agents-project-overview.md`.
- [x] Run Python compile checks.
- [x] Run local SQLite smoke tests for identity linking and repeated login behavior.

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
- 2026-07-01: Added Google/Microsoft callback route, userinfo extraction, OAuth identity linking, first-login user creation, and session assignment.
- 2026-07-01: Hardened auth configuration and callback behavior: minimum session secret length, secure-cookie production guard, explicit session cookie settings, session clearing on login/finalized callback, verified-email enforcement, duplicate identity race handling, and Authlib OAuth error handling.
- 2026-07-21: Stopped linking OAuth identities by email. New identities are isolated by `(provider, sub)` and receive persisted, collision-resolved mailbox aliases. Development restarts from a clean database; no legacy migration is included.
