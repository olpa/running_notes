# Running Notes Project Overview

This repo is an early MVP for a voice-notes inbox. The user records an audio note in the browser, the backend stores it, and the note is delivered into an IMAP mailbox so it can be read from Outlook or another mail client. Transcription and richer user flows are planned, but the current work is focused on moving from a single hardcoded mailbox to independent users.

## Current Shape

The app is a small Docker Compose stack:

- `nginx` serves the static frontend from `frontend/`.
- `backend` is a FastAPI app in `backend/`.
- `dovecot` provides IMAP/LMTP using config from `dovecot/config/`.
- `state/` is the persistent SQLite state directory at runtime.
- `maildir/` is the persistent mailbox directory shared by backend and Dovecot.
- `data/` stores uploaded note/audio data.

The old local demo still mentions `voiceinbox/voiceinbox` in places because Dovecot SQL auth has not been implemented yet. Treat that as legacy MVP1 behavior.

## User Database

MVP2 added a SQLite database at `/state/users.db`. The schema is initialized by `backend/database.py` when the backend starts or when the admin CLI runs.

Important tables:

- `users`: application users and their IMAP identity.
- `oauth_identities`: future OAuth provider mappings.

Current `users` columns:

- `id`: stable internal user id.
- `email`: unique user email.
- `created_at`: UTC creation timestamp.
- `status`: user state, currently expected to support active vs disabled authentication later.
- `imap_username`: unique IMAP login name.
- `imap_password_hash`: Dovecot-compatible IMAP password hash. New and reset credentials are stored as `{SHA512-CRYPT}` hashes. The legacy disabled value is `!`.

There is intentionally no `home_dir` or `maildir_path` column. Dovecot should derive mailbox paths from stable user identity during the SQL auth work.

## User Provisioning

Users are created offline, not through a public HTTP endpoint. This is intentional so user creation cannot accidentally be exposed by nginx.

Current command:

```bash
docker compose run --rm backend python admin.py create-user user@example.com
```

This command:

- initializes the SQLite database if needed;
- creates a row in `users`;
- assigns a generated `imap_username`;
- creates a Maildir under `maildir/users/<user-id>`;
- sets Maildir ownership using `MAIL_UID` and `MAIL_GID`, currently `5000:5000`;
- generates a one-time plaintext IMAP password and prints it in the JSON output;
- stores only the `{SHA512-CRYPT}` hash in `imap_password_hash`.

Relevant files:

- `backend/admin.py`: admin CLI entrypoint.
- `backend/users.py`: user creation and Maildir provisioning.
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

Dovecot is configured to use numeric `mail_uid = 5000` and `mail_gid = 5000`. The backend uses the same numeric values when creating Maildirs. Future Dovecot SQL userdb work must return or derive each user mailbox path as `/var/mail/voiceinbox/users/<user-id>` so users do not share one mailbox.

## Ticket #14: IMAP Credentials

Ticket `#14` / `MVP2-004: Generate And Manage IMAP Credentials` is implemented.

Current behavior:

- `create-user` generates a random IMAP password when a user is created;
- the plaintext password is printed once in the admin CLI JSON output;
- plaintext passwords are never stored;
- `users.imap_password_hash` stores `{SHA512-CRYPT}` hashes that Dovecot SQL passdb can return directly;
- `reset-imap-password` accepts either user email or IMAP username;
- resetting a password replaces the stored hash, so the previous password should stop working once SQL auth is wired up.

Current commands:

```bash
docker compose run --rm backend python admin.py create-user user@example.com
docker compose run --rm backend python admin.py reset-imap-password user@example.com
```

Full authentication verification still depends on Dovecot SQL auth, because static `voiceinbox/voiceinbox` auth has not been removed yet.

## Ticket #13: Dovecot SQL Authentication

The next ticket should replace the hardcoded IMAP account with SQL-backed users.

Ticket `#13` should:

- confirm Dovecot SQL/SQLite support;
- configure Dovecot SQL passdb against `/state/users.db`;
- configure SQL userdb for the derived Maildir location;
- remove static `voiceinbox/voiceinbox` auth;
- reject inactive, unknown, and invalid-password users;
- verify `doveadm auth test <imap_username> <password>` works for generated credentials;
- verify `doveadm user <imap_username>` resolves distinct homes/mailboxes.

## Development Notes

There is no committed test suite yet. Existing verification has been done with Python compile checks and temporary SQLite/Maildir smoke tests. Keep new changes small and easy to verify from the command line.

Avoid introducing public admin HTTP routes unless there is explicit authentication and authorization in place. Admin operations should stay command-line only for now.
