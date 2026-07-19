# Running notes

Early experiments towards a MVP

- Record a note
- The service transcribes it
- Get the result in Outlook or other mail client

## Local setup

The default Compose stack includes nginx, backend, Dovecot, and the boringproxy client. Because boringproxy is intentionally part of the running development stack, `BORINGPROXY_TOKEN` must be set before starting Compose. OAuth sessions also require `SESSION_SECRET`.

The boringproxy client image is built locally from `boringproxy/Dockerfile`, using the pinned upstream `v0.10.0` release. No boringproxy binary needs to be installed or mounted from the host.

```
export SESSION_SECRET=<at-least-32-random-characters>
export BORINGPROXY_TOKEN=<boringproxy-token>
docker compose up
```

Afterwards, create a user and point the IMAP client to `localhost:11993`. Use the user email as the IMAP username and the one-time password printed by the admin command. The default loopback-only host ports are HTTP `18080`, HTTPS `18443`, IMAP `10143`, and IMAPS `11993`; override them with `HTTP_PORT`, `HTTPS_PORT`, `IMAP_PORT`, and `IMAPS_PORT` in `.env` if needed.

## Container configuration

Compose persists shared application state in `./state`, mounted as `/state` in the backend and read-only in Dovecot. SQLite user and OAuth identity rows live in `/state/users.db`. Backend and Dovecot share `./maildir` at `/var/mail/voiceinbox`; backend provisions per-user Maildirs under `/var/mail/voiceinbox/users/<user-id>`, and Dovecot SQL userdb derives each user mailbox path from the same stable user id.

Backend and Dovecot both use numeric mail ownership `1000:1000` through `MAIL_UID`, `MAIL_GID`, and Dovecot `mail_uid`/`mail_gid`, so backend-created Maildirs are writable by Dovecot. The old single shared mailbox model is not used.

## Create a user

Create the initial user from the command line before exposing the deployment:

```
docker compose run --rm backend python admin.py create-user user@example.com
```

This creates the SQLite user row and provisions a Maildir at `maildir/users/<user-id>`. Provisioned Maildirs are owned by the numeric `MAIL_UID`/`MAIL_GID` configured for the backend and Dovecot, currently `1000:1000`. The IMAP username, equal to the normalized user email, and one-time pronounceable IMAP password are printed as JSON. Plaintext IMAP passwords are not stored.

IMAP password hashes are stored in Dovecot-compatible `{SHA512-CRYPT}` format in `users.imap_password_hash`, so SQL passdb can return the stored value directly.

Regenerate a user IMAP password with either their email address or IMAP username:

```
docker compose run --rm backend python admin.py reset-imap-password user@example.com
```

The reset command prints the new plaintext password once and replaces the previous stored hash.

## Guest user

The backend automatically creates a fixed guest user on startup if it does not
already exist. Its email defaults to `public@<PUBLIC_IMAP_HOST>` and can be changed
with `GUEST_USER_EMAIL`. When `PUBLIC_IMAP_HOST` is unset, the hostname from
`PUBLIC_BASE_URL` is used. An existing legacy `public@handsfree.vc` guest is renamed
in place so its mailbox and credentials are preserved. `GUEST_USER_PASSWORD` is required and sets the initial
IMAP password when that account is first created. The guest is an ordinary active user, except that its
IMAP password cannot be regenerated through the web portal or API. Set or reset
its password with the server admin CLI:

```
docker compose run --rm backend python admin.py reset-imap-password public@notes-dev.handsfree.vc
```

The automatic creation is idempotent and never reapplies
`GUEST_USER_PASSWORD` or resets an existing password.
The authenticated guest's IMAP setup page displays this configured password;
ordinary users never receive it. If an administrator resets the guest password
with the CLI, `GUEST_USER_PASSWORD` must be updated to the newly printed value
before recreating the backend, so the displayed password remains accurate.
The guest mailbox is read-only over IMAP: clients can list mailboxes and read or
download messages, but cannot change flags, append, move, expunge, create, or
delete mail. Web recordings continue to arrive through LMTP. Other users retain
normal read-write IMAP access.

Visitors can enter the shared account without registering through
`POST /auth/guest` or the **Try without registering** button. Guest sessions can
record normally. The portal displays a prominent warning that guest recordings
and mailbox credentials are shared publicly and must not be used for private or
sensitive information.

Guest cumulative quotas are derived from the ordinary per-user quotas using
`GUEST_QUOTA_FACTOR`, which defaults to `10`. This gives the shared guest 1,000
notes per UTC day and 2.5 GiB total stored audio with the default user quotas.
The 25 MiB per-upload limit is not multiplied. `GUEST_RETENTION_HOURS` defaults
to `24`; an hourly backend task removes expired guest source recordings and the
corresponding messages from the guest Maildir. Registered-user data is not
subject to this retention task.

The reserved profile-update endpoint is `PATCH /me`. Profile editing is not yet
implemented, so ordinary users receive `501`. The guest restriction is already
enforced first and returns `403`, safeguarding the read-only profile contract
when profile editing is implemented later.

## Verify IMAP authentication

After creating a user, verify Dovecot resolves the generated credentials through SQLite:

```
docker compose exec dovecot doveadm auth test <imap_username> <imap_password>
docker compose exec dovecot doveadm user <imap_username>
```

Unknown users, inactive users, disabled password hashes, and invalid passwords should fail.

## Recorder uploads

Recording uploads require a signed web session. Audio is accepted only as WebM (`audio/webm`), capped by `MAX_UPLOAD_BYTES` which defaults to 25 MiB, and stored under `state/users/<user-id>/notes/<note-id>/`. Note IDs use the UTC timestamp plus a random suffix. Each user is limited to `MAX_USER_NOTES_PER_DAY` notes per UTC day (default 100) and `MAX_USER_NOTE_BYTES` total stored audio (default 250 MiB).


## User portal

After OAuth login, the web portal provides recorder, IMAP setup, and account pages. The IMAP setup page shows only client connection settings: host, port, security mode, and the IMAP username. It never exposes server filesystem paths.

Portal IMAP settings are returned by `GET /me/imap-settings` and are controlled with these environment variables:

```
PUBLIC_IMAP_HOST=notes-dev.handsfree.vc
PUBLIC_IMAP_PORT=993
PUBLIC_IMAP_SECURITY=TLS
```

If `PUBLIC_IMAP_HOST` is unset, the backend derives the host from `PUBLIC_BASE_URL`.

## TLS certificates

boringproxy forwards HTTPS and IMAPS as raw TCP. TLS terminates inside this stack: nginx serves HTTPS on container port 443 and Dovecot serves IMAPS on container port 993. Compose maps those listeners to loopback-only host ports `18443` and `11993` by default.

By default, both services use the existing Let's Encrypt certificate at these ignored local paths:

```
certs/letsencrypt/live/notes.handsfree.vc/fullchain.pem
certs/letsencrypt/live/notes.handsfree.vc/privkey.pem
```

Override either path in `.env` when using a different certificate:

```
TLS_CERTIFICATE_PATH=/path/to/fullchain.pem
TLS_PRIVATE_KEY_PATH=/path/to/privkey.pem
```

The files must exist before starting the stack. After replacing or renewing them, recreate nginx and Dovecot so they load the new certificate:

```
docker compose up -d --force-recreate nginx dovecot
```

Configure boringproxy with TCP-level tunnels targeting host ports `18443` for nginx and `11993` for Dovecot (or the corresponding overrides). Do not enable TLS termination in boringproxy. Verify both local listeners before configuring the public tunnels:

```
openssl s_client \
  -connect 127.0.0.1:18443 \
  -servername notes-dev.handsfree.vc \
  -verify_hostname notes-dev.handsfree.vc \
  -verify_return_error </dev/null
```

```
openssl s_client \
  -connect 127.0.0.1:11993 \
  -servername notes-dev.handsfree.vc \
  -verify_hostname notes-dev.handsfree.vc \
  -verify_return_error </dev/null
```

Once boringproxy forwards public ports 443 and 993, run the checks against the public hostname.

Signed-in non-guest users can regenerate their own IMAP app password from the account page. The endpoint is `POST /me/imap-password`; it replaces the stored Dovecot password hash and returns the new plaintext password only in that response. The configured guest receives `403` from this endpoint and has no regeneration control in the portal.

## Minimal observability

Backend logs default to `INFO` and can be changed with `LOG_LEVEL`. Raw logs are intended to reconstruct a user activation and note delivery path without exposing secrets.

Expected backend log events include:

- OAuth login started and completed, with provider, user id, and email where available.
- OAuth identity linked or reused.
- User creation and Maildir provisioning failures.
- IMAP password generation/regeneration without plaintext passwords or hashes.
- Note upload with note id, user id, email, byte count, and content type.
- LMTP delivery success, refusal, or failure with note id and recipient.

Dovecot auth logs are available in the Dovecot container logs. Failed auth attempts are made verbose with `auth_verbose = yes`; successful IMAP logins should appear as standard `imap-login Login` lines. Logs must not include OAuth tokens, OAuth authorization codes, session secrets, session cookies, plaintext IMAP passwords, or password hashes.

See `OBSERVABILITY.md` for report-writing guidance and rules for adding new observability points.

## Web session configuration

OAuth web sessions require `SESSION_SECRET` with at least 32 characters. Local HTTP development should set `SESSION_COOKIE_SECURE=false`; production must leave secure cookies enabled and set `APP_ENV=production`.

OAuth login can be configured with Google and Microsoft client credentials through environment variables. `PUBLIC_BASE_URL` defaults to `http://localhost` in local Compose and is used to derive callback URLs unless provider-specific redirect URI variables are set.

Required for sessions:

```
APP_ENV=production
SESSION_SECRET=<at-least-32-random-characters>
SESSION_COOKIE_SECURE=true
```

Optional provider configuration:

```
PUBLIC_BASE_URL=http://localhost
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost/auth/callback/google
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
MICROSOFT_REDIRECT_URI=http://localhost/auth/callback/microsoft
```

Login start endpoints:

```
/auth/login/google
/auth/login/microsoft
```

Callback endpoints configured with providers:

```
/auth/callback/google
/auth/callback/microsoft
```

## Web mailbox

The authenticated portal includes a read-only Messages page. It shows the
newest messages in the user's INBOX and plays audio MIME attachments without
exposing Maildir paths or offering reply, forward, flag, move, or delete actions.

WEB_MESSAGE_LIMIT is read when the backend starts, defaults to 100, and must be
a positive integer. It is an administrator limit and cannot be overridden by a
web request.

The backend does not read Maildir files for this page. It uses Dovecot's internal
doveadm HTTP interface, which is restricted to the fetch command and reachable
only on the Compose backend network. Configure a strong shared secret before
starting or recreating the stack:

    DOVEADM_PASSWORD=<strong-random-secret>
    WEB_MESSAGE_LIMIT=100

The same DOVEADM_PASSWORD is supplied to the backend and Dovecot containers. It
grants mailbox read access and must not be logged, committed, or exposed on a
host port.
