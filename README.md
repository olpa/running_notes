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

Create the initial user from the command line before exposing the deployment:

```
docker compose run --rm backend python admin.py create-user user@example.com
```

This creates the SQLite user row and provisions a Maildir at `maildir/users/<user-id>`. The generated IMAP username is printed as JSON. IMAP login remains disabled until the IMAP credential ticket is implemented.

