# Running Notes

**Your inbox for thoughts. Capture now. Process later.**

Good ideas often arrive while walking, cooking, driving, or between meetings. Voice memo applications make them easy to record but just as easy to forget. Running Notes puts each recording in a dedicated inbox, where it can be processed using familiar mail tools and habits—or by email automation agents.

**Try it:** <https://notes.handsfree.vc/>

## How it works

1. Log in, or enter the public guest account without registering.
2. Record a voice note in the browser.
3. Find the recording as an audio attachment in Running Notes, Outlook, Apple Mail, Thunderbird, or another IMAP client.

Running Notes provides a separate mailbox rather than forwarding recordings to your personal email address. Notes stay apart from ordinary mail while retaining familiar inbox features such as folders, flags, search, and archiving.

The current MVP focuses on validating this workflow. It does not transcribe or summarize recordings.

> **Guest privacy:** The guest account and its recordings are shared publicly.
> Do not use it for private or sensitive information. Guest recordings expire
> automatically after 24 hours.

---

## Developer documentation

Self-hosting, architecture, Build Week, and licensing details follow.

### Self-hosting

See [OPERATING.md](OPERATING.md) for self-hosting, configuration, and operational
instructions.

### Architecture

The browser records audio with the MediaRecorder API and uploads it to a FastAPI backend. The backend creates an email message and submits it over LMTP to Dovecot, which provides the dedicated IMAP mailboxes. The application is packaged as a Docker Compose stack with nginx and boringproxy for public access.

### Built with Codex during OpenAI Build Week

Running Notes began before OpenAI Build Week as a single-user, happy-path proof
of concept that ran only in a controlled, manually configured environment.
During the hackathon period, I used Codex and GPT-5.6 to turn that draft into a
production system:

- Containerized deployment and TLS termination
- Upload quotas
- A public guest experience with automatic retention
- A browser mailbox backed by Dovecot's restricted HTTP API
- Mail-client autoconfiguration and a fake SMTP receiver

I made the central product and engineering decisions:

- Use a dedicated IMAP mailbox instead of forwarding to personal email
- Keep the MVP focused on audio instead of adding premature transcription
- Build on LMTP and Dovecot rather than reimplementing mail infrastructure
- Introduce a guest account
- Make public guest access read-only, quota-limited, and short-lived

ChatGPT helped me challenge the product idea and define a minimal valuable product. Codex helped draft the architecture and implementation under close diff review. GPT-5.6 accelerated the difficult final stretch: packaging the services, diagnosing integration and configuration problems, and bringing the system into production. I directed the work through requirements and constraints, reviewed changes, and checked architecture, naming, security boundaries, and production behavior.

The dated commits distinguish the pre-existing prototype from the additions made
during the submission period.

> **📋 See the [Build Week development log](./BUILD_WEEK.md) for the detailed timeline, decisions, and evidence.**

### License

Running Notes is free software licensed under the [GNU General Public License
version 3 or later](LICENSE). If you need to use it under different terms,
contact the author to discuss an alternative license.

## Colophon

- [Source code](https://github.com/olpa/running_notes/)
- Oleg Parashchenko, olpa at uucode com
