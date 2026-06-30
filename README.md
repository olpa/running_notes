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

This creates the SQLite user row and provisions a Maildir at `maildir/users/<user-id>`. Provisioned Maildirs are owned by the numeric `MAIL_UID`/`MAIL_GID` configured for the backend and Dovecot, currently `5000:5000`. The IMAP username, equal to the normalized user email, and one-time pronounceable IMAP password are printed as JSON. Plaintext IMAP passwords are not stored.

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
