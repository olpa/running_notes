#!/usr/bin/env python3
import imaplib
import os
import shutil
import smtplib
import ssl
import time
from email.message import EmailMessage
from pathlib import Path

from users import MAIL_GID, MAIL_ROOT, MAIL_UID, get_guest_user

IMAP_HOST = os.environ.get("GUEST_IMAP_TEST_HOST", "dovecot")
IMAP_PORT = int(os.environ.get("GUEST_IMAP_TEST_PORT", "993"))
LMTP_HOST = os.environ.get("GUEST_LMTP_TEST_HOST", "dovecot")
LMTP_PORT = int(os.environ.get("GUEST_LMTP_TEST_PORT", "24"))
GUEST_PASSWORD = os.environ["GUEST_USER_PASSWORD"]


def require_denied(operation: str, action) -> None:
    try:
        status = action()[0]
    except imaplib.IMAP4.error:
        return
    if status == "OK":
        raise AssertionError(f"{operation} unexpectedly succeeded")


def attempt(action) -> None:
    try:
        action()
    except imaplib.IMAP4.error:
        pass


def main() -> None:
    guest = get_guest_user()
    if guest is None:
        raise RuntimeError("Guest user is not provisioned")

    marker = f"guest-acl-{int(time.time())}-{os.getpid()}"
    message_id = f"<{marker}@voiceinbox.local>"
    mailbox_name = f"acl-test-{marker}"
    mailbox_path = MAIL_ROOT / guest["id"] / mailbox_name
    forbidden_mailbox_path = MAIL_ROOT / guest["id"] / f"forbidden-{marker}"
    _create_test_mailbox(mailbox_path)
    _deliver_test_message(guest["imap_username"], message_id)

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=context)
    try:
        imap.login(guest["imap_username"], GUEST_PASSWORD)
        status, _ = imap.list()
        if status != "OK":
            raise AssertionError("LIST failed for guest")
        status, _ = imap.select("INBOX", readonly=True)
        if status != "OK":
            raise AssertionError("SELECT INBOX failed for guest")
        status, data = imap.search(None, "HEADER", "Message-ID", message_id)
        if status != "OK" or not data or not data[0]:
            raise AssertionError("Delivered ACL test message is not readable")
        sequence = data[0].split()[-1]
        status, uid_data = imap.uid("SEARCH", None, "HEADER", "Message-ID", message_id)
        if status != "OK" or not uid_data or not uid_data[0]:
            raise AssertionError("Delivered ACL test message has no UID")
        uid = uid_data[0].split()[-1]
        status, _ = imap.fetch(sequence, "(BODY.PEEK[HEADER])")
        if status != "OK":
            raise AssertionError("FETCH failed for guest")

        attempt(lambda: imap.store(sequence, "+FLAGS", r"(\Flagged)"))
        status, flag_data = imap.fetch(sequence, "(FLAGS)")
        if status != "OK" or b"\\Flagged" in b" ".join(
            item for item in flag_data if isinstance(item, bytes)
        ):
            raise AssertionError("STORE changed guest message flags")

        forbidden_id = f"<forbidden-{marker}@voiceinbox.local>"
        attempt(
            lambda: imap.append(
                "INBOX",
                None,
                None,
                (
                    f"Message-ID: {forbidden_id}\r\n"
                    "Subject: forbidden\r\n\r\nforbidden"
                ).encode(),
            )
        )
        if _message_exists(imap, forbidden_id):
            raise AssertionError("APPEND added a message to the guest mailbox")

        attempt(lambda: imap.copy(sequence, mailbox_name))
        imap.select(mailbox_name, readonly=True)
        if _message_exists(imap, message_id):
            raise AssertionError("COPY added a message to another mailbox")

        imap.select("INBOX", readonly=True)
        attempt(lambda: imap.uid("MOVE", uid, mailbox_name))
        if not _message_exists(imap, message_id):
            raise AssertionError("MOVE removed the message from INBOX")
        imap.select(mailbox_name, readonly=True)
        if _message_exists(imap, message_id):
            raise AssertionError("MOVE added the message to another mailbox")

        status, before = imap.select("INBOX", readonly=True)
        if status != "OK":
            raise AssertionError("Could not reselect INBOX before EXPUNGE")
        attempt(imap.expunge)
        status, after = imap.select("INBOX", readonly=True)
        if status != "OK" or before != after:
            raise AssertionError("EXPUNGE changed the guest mailbox")

        require_denied("CREATE", lambda: imap.create(f"forbidden-{marker}"))
        require_denied("DELETE", lambda: imap.delete(mailbox_name))
        print("Guest IMAP ACL verified: reads allowed; mutations denied.")
    finally:
        try:
            try:
                imap.logout()
            except imaplib.IMAP4.error:
                pass
        finally:
            shutil.rmtree(mailbox_path, ignore_errors=True)
            shutil.rmtree(forbidden_mailbox_path, ignore_errors=True)
            _remove_test_message(guest["id"], message_id.encode())


def _message_exists(imap: imaplib.IMAP4_SSL, message_id: str) -> bool:
    status, data = imap.search(None, "HEADER", "Message-ID", message_id)
    return status == "OK" and bool(data and data[0])


def _create_test_mailbox(mailbox_path: Path) -> None:
    for child in ("cur", "new", "tmp"):
        path = mailbox_path / child
        path.mkdir(parents=True, exist_ok=True)
        os.chown(path, MAIL_UID, MAIL_GID)
    os.chown(mailbox_path, MAIL_UID, MAIL_GID)


def _deliver_test_message(recipient: str, message_id: str) -> None:
    message = EmailMessage()
    message["From"] = "acl-test@voiceinbox.local"
    message["To"] = recipient
    message["Subject"] = "Guest ACL integration test"
    message["Message-ID"] = message_id
    message.set_content("Disposable guest ACL integration test.")
    with smtplib.LMTP(LMTP_HOST, LMTP_PORT) as lmtp:
        refused = lmtp.sendmail(message["From"], [recipient], message.as_bytes())
    if refused:
        raise RuntimeError(f"LMTP refused ACL test message: {refused}")


def _remove_test_message(user_id: str, message_id: bytes) -> None:
    maildir = MAIL_ROOT / user_id
    for directory in maildir.rglob("*"):
        if not directory.is_dir() or directory.name not in {"cur", "new"}:
            continue
        for message_path in directory.iterdir():
            if not message_path.is_file():
                continue
            try:
                if message_id in message_path.read_bytes()[:64 * 1024]:
                    message_path.unlink()
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    main()
