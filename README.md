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

Afterwards, create a user and point the IMAP client to `localhost`. Use the user email as the IMAP username and the one-time password printed by the admin command.

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

## Verify IMAP authentication

After creating a user, verify Dovecot resolves the generated credentials through SQLite:

```
docker compose exec dovecot doveadm auth test <imap_username> <imap_password>
docker compose exec dovecot doveadm user <imap_username>
```

Unknown users, inactive users, disabled password hashes, and invalid passwords should fail.

## Recorder uploads

Recording uploads require a signed web session. Audio is accepted only as WebM (`audio/webm`), capped by `MAX_UPLOAD_BYTES` which defaults to 25 MiB, and stored under `state/users/<user-id>/notes/<note-id>/`. Note IDs use the UTC timestamp plus a random suffix. Per-user storage is limited by `MAX_USER_NOTES` and `MAX_USER_NOTE_BYTES`, defaulting to 100 notes and 250 MiB.


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

boringproxy forwards HTTPS and IMAPS as raw TCP. TLS terminates inside this stack: nginx serves HTTPS on port 443 and Dovecot serves IMAPS on port 993.

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

Configure boringproxy with TCP-level tunnels targeting nginx port 443 and Dovecot port 993. Do not enable TLS termination in boringproxy. Verify both local listeners before configuring the public tunnels:

```
openssl s_client \
  -connect 127.0.0.1:443 \
  -servername notes-dev.handsfree.vc \
  -verify_hostname notes-dev.handsfree.vc \
  -verify_return_error </dev/null
```

```
openssl s_client \
  -connect 127.0.0.1:993 \
  -servername notes-dev.handsfree.vc \
  -verify_hostname notes-dev.handsfree.vc \
  -verify_return_error </dev/null
```

Once boringproxy forwards public ports 443 and 993, run the checks against the public hostname.

Signed-in users can regenerate their own IMAP app password from the account page. The endpoint is `POST /me/imap-password`; it replaces the stored Dovecot password hash and returns the new plaintext password only in that response.

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
