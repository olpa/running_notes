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
