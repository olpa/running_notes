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

Afterwards, point the IMAP client to the `localhost`. The credentials are `voiceinbox/voiceinbox`.

## Create a user

The MVP2 user database is initialized when the backend starts. Create a user with:

```
curl -X POST http://localhost/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com"}'
```

This creates the SQLite user row and provisions a Maildir at `maildir/users/<user-id>`. The generated IMAP username is returned in the response. IMAP login remains disabled until the IMAP credential ticket is implemented.

