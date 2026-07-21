# OpenAI Build Week development log

This document records how Running Notes changed during OpenAI Build Week and how
I collaborated with ChatGPT, Codex, and GPT-5.6. The repository's dated commit
history is the source of evidence for the implementation timeline below.

This log highlights the Build Week changes most relevant to the project's
evolution and judging criteria. Subsequent commits may include usability
improvements, documentation updates, and operational fixes; the repository
history remains the complete record.

## Before Build Week

Running Notes already existed as a single-user, happy-path proof of concept. It
demonstrated the central idea—record audio in a web browser, turn the recording
into an email message, and deliver it to a dedicated IMAP mailbox. But it ran only
in a controlled, manually configured environment. It was not yet a deployable
multi-user product.

Before the submission period, I had also used ChatGPT to challenge the product
idea and help define a minimal valuable product. I used Codex in June and early
July to draft the multi-user system and investigate its technical feasibility.
That phase was deliberately controlled: I reviewed diffs closely and enforced
the structure, naming, and architecture.

Because this was a pre-existing project, only the work added during the
submission period is presented as Build Week work.

## What changed during Build Week

### July 17: production packaging and resource limits

- [Pull request #35](https://github.com/olpa/running_notes/pull/35) containerized
  boringproxy, moved TLS termination into the stack, and documented deployment.
- [Pull request #38](https://github.com/olpa/running_notes/pull/38) added daily
  note and storage quotas.

These changes moved the project beyond an application draft toward a service
that could run publicly with explicit resource boundaries.

### July 18–19: public guest experience

- [Pull request #40](https://github.com/olpa/running_notes/pull/40) added entry
  without registration, a shared guest mailbox, read-only IMAP access, larger
  aggregate quotas, a privacy warning, and automatic expiry of guest recordings.
- [Pull request #42](https://github.com/olpa/running_notes/pull/42) corrected
  deployment issues in the guest-account flow.

The guest experience gives judges and visitors a direct path through the core
workflow. Its safety constraints are part of the product design: public data is
clearly identified, mailbox mutation is blocked over IMAP, storage is bounded,
and recordings are removed after a short retention period.

### July 19: mailbox in the web application

- [Pull request #43](https://github.com/olpa/running_notes/pull/43) added a
  restricted adapter for Dovecot's HTTP API, exposed the mailbox through
  application endpoints, added a read-only Messages page with audio playback,
  documented the configuration, and fixed authentication between the backend
  and Dovecot's HTTP API.

This completed the core loop inside the product itself: record a thought, open
the mailbox, and play it back. Standard IMAP clients remain supported.

### July 21: production deployment and mail-client setup

- [Pull request #44](https://github.com/olpa/running_notes/pull/44) added a
  dedicated production Compose stack, tagged frontend and backend images,
  resource and process limits, bounded container logs, deployment commands, and
  public privacy and terms pages. It also expanded the start page so visitors
  can understand the product before signing in.
- [Pull request #45](https://github.com/olpa/running_notes/pull/45) added
  persistent Running Notes mailbox addresses, Outlook and Thunderbird
  autoconfiguration endpoints, and a fake SMTP receiver for mail-client setup.
  Running Notes is receive-only, so the receiver rejects outgoing delivery
  explicitly instead of accepting or relaying messages.

Together, these changes closed the gap between a working hosted application and
a product that can be deployed predictably and added to ordinary mail clients
without requiring users to understand the underlying mail infrastructure.

## How the collaboration worked

The three OpenAI tools played different roles:

- **ChatGPT** helped explore the problem, challenge product assumptions, and
  define the smallest product that could validate the inbox workflow.
- **Codex** helped draft the architecture and implementation. During this phase,
  I kept close control through diff review and decisions about structure,
  naming, interfaces, and system boundaries.
- **GPT-5.6** accelerated the production phase. It worked across the web
  application, FastAPI backend, Docker Compose services, nginx, boringproxy,
  SQLite, LMTP, and Dovecot, and diagnosed configuration and integration failures
  spanning those components.

During Build Week, I used my persistent remote workflow: Codex ran on the
production VPS inside `tmux`, allowing me to continue the same session from my
desktop, laptop, or phone. Typing substantial instructions on a phone is
inconvenient, so I used my [Handsfree Vibe Coding Android
app](https://handsfree.vc/) to transcribe and review spoken instructions before
pasting them into Codex.

My role was to describe the desired behavior and constraints, choose between
product and architectural alternatives, review the resulting changes, and
redirect the implementation when operational or security details required it.
This made it possible to keep the final phase highly automated without giving up
control of the system's design.

### A concrete debugging example

One production issue illustrates the difference GPT-5.6 Sol made. The Messages
page displayed only "Messages unavailable", while the backend returned HTTP
503 even after the service had been restarted. Sol traced the failure through
the backend’s Dovecot HTTP request to a configuration expression written for
Dovecot 2.3: `$ENV:DOVEADM_PASSWORD`. Running Notes uses Dovecot 2.4, where the
correct expression is `%{env:DOVEADM_PASSWORD}` and the variable must be
declared in an `import_environment` block.

Sol also discovered that Dovecot 2.4’s HTTP API expected API-key
authentication rather than the Basic authentication used by the backend. It
corrected both sides, restarted the service, verified live message retrieval
with HTTP 200 responses, ran the test suite, and committed the fix. The entire
investigation—from my report of the vague user-visible error to a verified
commit—took about fifteen minutes. Previously, finding that path through
application logs, container networking, authentication, and version-specific
Dovecot syntax would likely have cost me a working day. The result is
preserved in commit
[e5db794](https://github.com/olpa/running_notes/commit/e5db794c941bb5c12b7aa8f3f9bde53079404eca).

I was deeply impressed by what Sol accomplished. I am not sure that any model
available just two months earlier could have completed this entire multistage
task—from diagnosis across several services to a verified production fix—so
autonomously.

## Key decisions I made

### A dedicated inbox instead of email forwarding

Forwarding recordings into an existing personal inbox would have reduced the
initial infrastructure, but it would mix private thoughts with ordinary mail.
Running Notes instead exposes a dedicated IMAP mailbox: a separate workspace
that still benefits from familiar mail-client workflows.

### Audio first, without premature AI features

Transcription, summarization, and semantic search are natural future additions,
but they would obscure the first product question: does an inbox help people
return to and process spontaneous thoughts? The MVP therefore preserves the
original audio and concentrates on the capture-to-inbox loop.

### Use established mail infrastructure

The backend submits messages through LMTP and leaves mailbox delivery,
authentication, and IMAP behavior to Dovecot. This avoids recreating mature mail
infrastructure in application code.

### Constrain the public guest account

Guest access is valuable because it removes registration from the demo path, but
it creates privacy and resource risks. The guest mailbox is consequently public
and clearly labeled, read-only over IMAP, quota-limited, and subject to automatic
retention. Registered users keep independent mailboxes and normal IMAP access.

### Restrict internal mailbox access

The browser mailbox does not read Maildir files directly. It uses Dovecot's
internal HTTP interface, which is limited to the required fetch operation and is
not exposed on a host port. This keeps mailbox ownership inside Dovecot while
giving the web application only the access it needs.

## Result

The Build Week work turned an earlier prototype into a publicly running,
multi-user product with a no-registration demo path, bounded resource use, and
two ways to process recordings: in the web interface or through a standard IMAP
client.

Live application: <https://notes.handsfree.vc/>
