# Observability

This project currently uses raw container logs as its observability layer. The goal is to reconstruct user activation, note upload, and mail delivery paths without logging secrets.

## Create A Report From Logs

Start by collecting backend and Dovecot logs for the time window under investigation:

```bash
docker compose logs --since 2h backend dovecot
```

For a known user email, filter for the activation and upload path:

```bash
docker compose logs --since 2h backend dovecot | grep 'user@example.com'
```

For a known note id, filter for upload and LMTP delivery:

```bash
docker compose logs --since 2h backend dovecot | grep 'note-YYYYMMDDTHHMMSSZ-xxxxxxxx'
```

A useful incident or smoke-test report should include:

- Time window and environment.
- User email and user id, if visible.
- OAuth provider.
- Whether an OAuth identity was linked or reused.
- Whether the user was created.
- Whether an IMAP password was generated or regenerated.
- Note id, upload byte count, and content type.
- LMTP delivery result: delivered, refused recipient, or failed exception.
- Dovecot IMAP auth evidence: failed auth reason or successful `imap-login Login` line.
- Any missing expected log line.

Expected backend event sequence for first login and upload:

```text
OAuth login started provider=<provider>
IMAP password generated for new user_id=<id> email=<email> imap_username=<email>
User created user_id=<id> email=<email> imap_username=<email>
OAuth identity linked provider=<provider> user_id=<id> email=<email>
OAuth login completed provider=<provider> user_id=<id> email=<email>
Note uploaded note_id=<note-id> user_id=<id> email=<email> bytes=<n> content_type=<type>
LMTP delivered note <note-id> to <email>
```

Expected backend event sequence for repeated login:

```text
OAuth login started provider=<provider>
OAuth identity reused provider=<provider> user_id=<id> email=<email>
OAuth login completed provider=<provider> user_id=<id> email=<email>
```

Expected backend event sequence for IMAP password regeneration:

```text
IMAP password generated for existing user_id=<id> email=<email> imap_username=<email>
IMAP password hash replaced for user_id=<id> email=<email> imap_username=<email>
IMAP password regenerated for user_id=<id> email=<email> imap_username=<email>
```

Delivery failures should include the note id and recipient. Refused recipients are logged as an error with the refused-recipient map returned by LMTP. SMTP exceptions are logged with stack traces.

Do not include secrets in reports. In particular, redact or omit:

- OAuth authorization codes.
- OAuth access, refresh, or ID tokens.
- Session cookies.
- `SESSION_SECRET`.
- Plaintext IMAP passwords.
- IMAP password hashes.
- Provider client secrets.

## Add New Observability Points

Use normal Python logging:

```python
logger.info("Action completed user_id=%s email=%s", user_id, email)
```

Prefer stable identifiers and operational context:

- `user_id`
- `email`
- `imap_username`
- `provider`
- `note_id`
- recipient email
- byte counts
- content type
- failure category

Avoid high-cardinality or sensitive values:

- OAuth token payloads.
- OAuth authorization codes.
- request headers containing cookies or authorization.
- session contents.
- plaintext passwords.
- password hashes.
- full audio contents or message bodies.
- filesystem paths visible only inside containers, unless the event is explicitly about storage diagnostics.

Choose log levels consistently:

- `info`: expected lifecycle events, such as login started, login completed, note uploaded, user created, password regenerated, delivery succeeded.
- `warning`: rejected user input, OAuth provider/config/userinfo issues, disabled users, recoverable identity conflicts.
- `error`: refused delivery, quota/storage problems that block a user action and need operator attention.
- `exception`: unexpected exceptions where a traceback is useful.

Every new user-facing workflow should have enough logs to answer:

- Who initiated it?
- Which stable object was affected?
- Did the workflow complete?
- If it failed, at which external or internal boundary did it fail?
- What non-secret value lets an operator correlate the next log line?

When adding a log point, review the rendered log message before committing. The message should be useful when copied into a report, and it must not require access to private request bodies or secrets to understand what happened.
