import base64
import json
import re
from dataclasses import dataclass

import httpx

MESSAGE_KEY_PATTERN = re.compile(r"^[0-9a-fA-F]{32}:[1-9][0-9]*$")

class MailboxError(RuntimeError):
    pass

@dataclass(frozen=True)
class MailReference:
    mailbox_guid: str
    uid: int

    @property
    def key(self) -> str:
        value = f"{self.mailbox_guid}:{self.uid}".encode()
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    @classmethod
    def from_key(cls, key: str) -> "MailReference":
        try:
            value = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4)).decode()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Invalid message key") from exc
        if not MESSAGE_KEY_PATTERN.fullmatch(value):
            raise ValueError("Invalid message key")
        guid, uid = value.split(":", 1)
        return cls(guid.lower(), int(uid))

class DoveadmMailbox:
    """Read mail through Dovecot's doveadm HTTP API, never Maildir files."""
    def __init__(self, url: str, password: str, timeout_seconds: float = 15.0):
        if not password:
            raise ValueError("DOVEADM_PASSWORD is required")
        self.url, self.password, self.timeout_seconds = url, password, timeout_seconds

    def _fetch(self, user: str, fields: list[str], query: list[str]) -> list[dict]:
        payload = [["fetch", {"user": user, "field": fields, "query": query}, "mail"]]
        try:
            encoded_key = base64.b64encode(self.password.encode()).decode()
            response = httpx.post(self.url, headers={"Authorization": f"X-Dovecot-API {encoded_key}", "X-API-Key": encoded_key}, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise MailboxError("Dovecot mailbox request failed") from exc
        if not isinstance(result, list) or len(result) != 1 or len(result[0]) != 3:
            raise MailboxError("Dovecot returned an invalid response")
        kind, rows, tag = result[0]
        if kind != "doveadmResponse" or tag != "mail" or not isinstance(rows, list):
            raise MailboxError("Dovecot rejected the mailbox request")
        return rows

    def latest_references(self, user: str, limit: int) -> list[MailReference]:
        rows = self._fetch(user, ["mailbox-guid", "uid", "date.saved.unixtime"], ["mailbox", "INBOX", "all"])
        messages = []
        for row in rows:
            try:
                ref = MailReference(row["mailbox-guid"].lower(), int(row["uid"]))
                messages.append((int(row["date.saved.unixtime"]), ref.uid, ref))
            except (KeyError, TypeError, ValueError):
                continue
        messages.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in messages[:limit]]

    def fetch_messages(self, user: str, references: list[MailReference]) -> list[tuple[MailReference, bytes]]:
        if not references:
            return []
        by_guid = {}
        for ref in references:
            by_guid.setdefault(ref.mailbox_guid, []).append(ref.uid)
        fetched = {}
        for guid, uids in by_guid.items():
            rows = self._fetch(user, ["mailbox-guid", "uid", "text"], ["mailbox-guid", guid, "uid", ",".join(map(str, uids))])
            for row in rows:
                try:
                    ref = MailReference(row["mailbox-guid"].lower(), int(row["uid"]))
                    fetched[ref] = row["text"].encode("utf-8", errors="surrogateescape")
                except (AttributeError, KeyError, TypeError, ValueError):
                    continue
        return [(ref, fetched[ref]) for ref in references if ref in fetched]

    def fetch_message(self, user: str, reference: MailReference) -> bytes | None:
        messages = self.fetch_messages(user, [reference])
        return messages[0][1] if messages else None
