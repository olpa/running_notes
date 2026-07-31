import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

import config
import services
from audio import InvalidAudioRange, parse_audio_byte_range
from auth_deps import current_active_user
from mailbox import MailboxError, MailReference, references_with_requested
from messages import extract_audio, parse_message_summary

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/messages")
def list_messages(
    request: Request,
    include: str | None = Query(default=None),
):
    user = current_active_user(request)
    try:
        references = services.mailbox.latest_references(
            user["imap_username"], config.WEB_MESSAGE_LIMIT
        )
        references, requested_reference = references_with_requested(
            references, include
        )
        raw_messages = services.mailbox.fetch_messages(user["imap_username"], references)
    except MailboxError as exc:
        logger.exception("Dovecot message listing failed user_id=%s", user["id"])
        raise HTTPException(status_code=503, detail="Mailbox is unavailable") from exc
    messages = []
    for reference, raw in raw_messages:
        try:
            messages.append(parse_message_summary(raw, reference.key))
        except Exception:
            logger.warning("Ignoring malformed mailbox message user_id=%s uid=%s", user["id"], reference.uid)
    requested_message_found = (
        requested_reference is not None
        and any(message["id"] == requested_reference.key for message in messages)
        if include
        else None
    )
    return {
        "messages": messages,
        "limit": config.WEB_MESSAGE_LIMIT,
        "requested_message_found": requested_message_found,
    }


@router.get("/api/messages/{message_key}/audio/{audio_index}")
def message_audio(message_key: str, audio_index: int, request: Request):
    user = current_active_user(request)
    try:
        reference = MailReference.from_key(message_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Message not found") from exc
    try:
        raw = services.mailbox.fetch_message(user["imap_username"], reference)
    except MailboxError as exc:
        logger.exception("Dovecot audio fetch failed user_id=%s", user["id"])
        raise HTTPException(status_code=503, detail="Mailbox is unavailable") from exc
    if raw is None:
        raise HTTPException(status_code=404, detail="Message not found")
    audio = extract_audio(raw, audio_index)
    if audio is None:
        raise HTTPException(status_code=404, detail="Audio attachment not found")
    payload, content_type, _filename = audio
    headers = {"Accept-Ranges": "bytes"}
    requested_range = request.headers.get("range")
    if requested_range is None:
        return Response(payload, media_type=content_type, headers=headers)

    try:
        start, end = parse_audio_byte_range(requested_range, len(payload))
    except InvalidAudioRange as exc:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{len(payload)}"},
        ) from exc

    headers["Content-Range"] = f"bytes {start}-{end}/{len(payload)}"
    return Response(
        payload[start : end + 1],
        status_code=206,
        media_type=content_type,
        headers=headers,
    )


@router.delete("/api/messages/{message_key}", status_code=204)
def delete_message(message_key: str, request: Request):
    user = current_active_user(request)
    if user["is_guest"]:
        raise HTTPException(
            status_code=403,
            detail="Guest users cannot delete messages",
        )
    try:
        reference = MailReference.from_key(message_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Message not found") from exc
    try:
        deleted = services.mailbox.delete_message(user["imap_username"], reference)
    except MailboxError as exc:
        logger.exception("Dovecot message deletion failed user_id=%s", user["id"])
        raise HTTPException(status_code=503, detail="Mailbox is unavailable") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")
    logger.info(
        "Message deleted user_id=%s mailbox_guid=%s uid=%s",
        user["id"],
        reference.mailbox_guid,
        reference.uid,
    )
