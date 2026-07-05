# Running Notes Project Overview

This repo is an early MVP for a voice-notes inbox. The user records an audio note in the browser, the backend stores it, and the note is delivered into an IMAP mailbox so it can be read from Outlook or another mail client. Transcription and richer user flows are planned, but the current work is focused on moving from a single hardcoded mailbox to independent users.

## Current Shape

The app is a small Docker Compose stack:

- `nginx` serves the static frontend from `frontend/`.
- `backend` is a FastAPI app in `backend/`.
- `dovecot` provides IMAP/LMTP using config from `dovecot/config/`.
- `state/` is the persistent SQLite state directory at runtime.
- `maildir/` is the persistent mailbox directory shared by backend and Dovecot.
- `state/users/<user-id>/notes/` stores authenticated note/audio uploads.

Dovecot authentication is configured to use SQLite users. The old `voiceinbox/voiceinbox` demo credentials should be treated as removed legacy MVP1 behavior.

## User Database

MVP2 added a SQLite database at `/state/users.db`. The schema is initialized by `backend/database.py` when the backend starts or when the admin CLI runs.

Important tables:

- `users`: application users and their IMAP identity.
- `oauth_identities`: OAuth provider mappings for Google and Microsoft sign-in.

Current `users` columns:

- `id`: stable internal user id.
- `email`: unique user email.
- `created_at`: UTC creation timestamp.
- `status`: user state, currently expected to support active vs disabled authentication later.
- `imap_username`: unique IMAP login name, equal to the normalized user email.
- `imap_password_hash`: Dovecot-compatible IMAP password hash. New and reset credentials are stored as `{SHA512-CRYPT}` hashes. The legacy disabled value is `!`.

There is intentionally no `home_dir` or `maildir_path` column. Dovecot SQL userdb derives mailbox paths from stable user identity.

## User Provisioning

Users are created offline, not through a public HTTP endpoint. This is intentional so user creation cannot accidentally be exposed by nginx.

Current command:

```bash
docker compose run --rm backend python admin.py create-user user@example.com
```

This command:

- initializes the SQLite database if needed;
- creates a row in `users`;
- assigns `imap_username` to the normalized user email;
- creates a Maildir under `maildir/users/<user-id>`;
- sets Maildir ownership using `MAIL_UID` and `MAIL_GID`, currently `1000:1000`;
- generates a one-time pronounceable IMAP password and prints it in the JSON output;
- stores only the `{SHA512-CRYPT}` hash in `imap_password_hash`.

Relevant files:

- `backend/admin.py`: admin CLI entrypoint.
- `backend/users.py`: user creation, user serialization, and Maildir provisioning.
- `backend/oauth.py`: Authlib provider registry, redirect URI/session config, and userinfo validation.
- `backend/oauth_identities.py`: OAuth identity lookup/linking and first-login user creation.
- `backend/database.py`: SQLite connection and DDL.
- `docker-compose.yml`: volume mounts and mail UID/GID env vars.
- `dovecot/config/10-mail.conf`: Dovecot mail location and UID/GID notes.

## Current Mailbox Contract

The backend provisions per-user Maildirs here inside the containers:

```text
/var/mail/voiceinbox/users/<user-id>
```

The host-visible path is:

```text
maildir/users/<user-id>
```

Dovecot is configured to use numeric `mail_uid = 1000` and `mail_gid = 1000`. The backend uses the same numeric values when creating Maildirs. SQL userdb returns each user home and `mail_path` as `/var/mail/voiceinbox/users/<user-id>` so users do not share one mailbox.

## Ticket #14: IMAP Credentials

Ticket `#14` / `MVP2-004: Generate And Manage IMAP Credentials` is implemented.

Current behavior:

- `create-user` generates a random pronounceable IMAP password when a user is created, formatted as three syllabic chunks plus four digits, for example `maviro-luneta-sokami-4827`;
- the plaintext password is printed once in the admin CLI JSON output;
- plaintext passwords are never stored;
- `users.imap_password_hash` stores `{SHA512-CRYPT}` hashes that Dovecot SQL passdb can return directly;
- `reset-imap-password` accepts the user email / IMAP username;
- resetting a password replaces the stored hash, so the previous password should stop working once SQL auth is wired up.

Current commands:

```bash
docker compose run --rm backend python admin.py create-user user@example.com
docker compose run --rm backend python admin.py reset-imap-password user@example.com
```

Full authentication verification now means running `doveadm auth test` and `doveadm user` inside the Dovecot container against generated credentials.

## Ticket #13: Dovecot SQL Authentication

Ticket `#13` / `MVP2-003: Configure Dovecot SQL Authentication` is implemented in configuration.

Current behavior:

- `dovecot/config/10-auth.conf` uses SQLite SQL auth against `/state/users.db`;
- SQL passdb selects only active users with non-disabled password hashes;
- SQL userdb selects only active users with non-disabled password hashes and returns numeric UID/GID `1000:1000`;
- SQL userdb derives `home` and `mail_path` as `/var/mail/voiceinbox/users/<user-id>`;
- static `voiceinbox/voiceinbox` authentication has been removed.

Expected verification once Docker access is available:

```bash
docker compose exec dovecot doveadm auth test <imap_username> <imap_password>
docker compose exec dovecot doveadm user <imap_username>
```

Unknown users, inactive users, disabled password hashes, and invalid passwords should fail.


## Ticket #16: Protected Recorder Uploads

Ticket `#16` / `MVP2-006: Protect Recorder Uploads With Authentication` is implemented structurally.

Current behavior:

- `POST /record` requires the signed web session and rejects anonymous uploads;
- uploads accept `audio/webm` only, including browser content types with parameters such as `audio/webm;codecs=opus`;
- each upload is read with a hard size cap, `MAX_UPLOAD_BYTES`, defaulting to 25 MiB;
- per-user quota is enforced with `MAX_USER_NOTES` and `MAX_USER_NOTE_BYTES`, defaulting to 100 notes and 250 MiB;
- note IDs use UTC timestamp plus random suffix, for example `note-20260705T083354Z-a1b2c3d4`;
- note files are stored under `state/users/<user-id>/notes/<note-id>/`;
- note metadata includes the owning `user_id`;
- `/note/<note-id>` and `/note/<note-id>/audio` are session-scoped to the current user.

## Ticket #15: OAuth Login And Web Sessions

Ticket `#15` / `MVP2-005: Add OAuth Login And Web Sessions` is implemented structurally for Google and Microsoft OAuth/OIDC.

Current behavior:

- OAuth is implemented with Authlib and Starlette `SessionMiddleware`;
- supported providers are `google` and `microsoft`;
- login start endpoints are `/auth/login/google` and `/auth/login/microsoft`;
- callback endpoints are `/auth/callback/google` and `/auth/callback/microsoft`;
- successful callbacks link or create an application user, insert `oauth_identities`, and set `request.session["user_id"]`;
- `/me` returns the current active user from the signed session;
- `/auth/logout` clears the session;
- first-login user creation reuses `create_user(email)`, so users get Maildir provisioning and generated IMAP credentials;
- Google email must be explicitly verified; Microsoft userinfo is accepted without a Google-style `email_verified` claim because Microsoft OIDC userinfo does not consistently include one;
- disabled users are rejected during session lookup and OAuth identity linking.

Session and OAuth configuration:

- `SESSION_SECRET` is required and must be at least 32 characters;
- `SESSION_COOKIE_SECURE` defaults to secure cookies and cannot be disabled when `APP_ENV=production`;
- the session cookie is `running_notes_session`, `SameSite=Lax`, path `/`, 14-day max age;
- `PUBLIC_BASE_URL` is used to derive callback URLs unless provider-specific redirect URI env vars are set;
- OAuth client IDs and secrets are loaded only from environment variables.

Relevant environment variables:

```text
APP_ENV
SESSION_SECRET
SESSION_COOKIE_SECURE
PUBLIC_BASE_URL
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI
MICROSOFT_CLIENT_ID
MICROSOFT_CLIENT_SECRET
MICROSOFT_REDIRECT_URI
```

Verification so far has used no-network fakes for Authlib callback behavior plus SQLite smoke tests for first login, repeated login, disabled users, invalid email, and unverified email paths. Real browser OAuth testing with actual Google/Microsoft credentials and configured redirect URIs is still required before considering the provider integrations fully accepted.

## Development Notes

There is no committed test suite yet. Existing verification has been done with Python compile checks and temporary SQLite/Maildir smoke tests. Keep new changes small and easy to verify from the command line.

Avoid introducing public admin HTTP routes unless there is explicit authentication and authorization in place. Admin operations should stay command-line only for now.
