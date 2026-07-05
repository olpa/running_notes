# Running notes

Early experiments towards a MVP

- Record a note
- The service transcribes it
- Get the result in Outlook or other mail client

## Local setup

```
docker compose up
...
./scripts/create_sample_message.sh 
```

Afterwards, create a user and point the IMAP client to `localhost`. Use the user email as the IMAP username and the one-time password printed by the admin command.

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
