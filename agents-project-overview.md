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
- `imap_password_hash`: intended Dovecot-compatible password hash. It is currently set to `!`, meaning login is disabled until ticket `#15`.

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
- leaves `imap_password_hash` disabled as `!`.

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

## Ticket #15: IMAP Credentials

The next ticket should make IMAP credentials real. Right now users cannot authenticate because `imap_password_hash` is deliberately disabled.

Expected direction:

- add an admin command to generate or reset an IMAP password for a user;
- store only a Dovecot-compatible password hash in `users.imap_password_hash`;
- print the generated plaintext password once, at creation/reset time;
- do not store plaintext passwords;
- keep disabled/inactive users unable to authenticate once Dovecot SQL auth is added;
- choose a password hash format that Dovecot can verify from SQL in ticket `#14`.

The natural command shape would be something like:

```bash
docker compose run --rm backend python admin.py reset-imap-password user@example.com
```

or, if preferred, by `imap_username`. Use the existing admin CLI style rather than adding a public HTTP endpoint.

## Ticket #14 Comes After #15

Do not expect `doveadm auth test` to pass before `#15`. Dovecot SQL auth needs real credential hashes to test against.

Ticket `#14` should later:

- confirm Dovecot SQL/SQLite support;
- configure Dovecot SQL passdb against `/state/users.db`;
- configure SQL userdb for the derived Maildir location;
- remove static `voiceinbox/voiceinbox` auth;
- reject inactive, unknown, and invalid-password users;
- verify `doveadm user <imap_username>` resolves distinct homes/mailboxes.

## Development Notes

There is no committed test suite yet. Existing verification has been done with Python compile checks and temporary SQLite/Maildir smoke tests. Keep new changes small and easy to verify from the command line.

Avoid introducing public admin HTTP routes unless there is explicit authentication and authorization in place. Admin operations should stay command-line only for now.
