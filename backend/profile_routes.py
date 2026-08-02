import logging

from fastapi import APIRouter, HTTPException, Request

import config
from auth_deps import (
    can_change_imap_password,
    current_active_user,
    is_guest_user,
    require_writable_profile,
)
from users import reset_imap_password

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/me")
def me(request: Request):
    user = current_active_user(request)
    return {
        "user": {
            **user,
            "is_guest": is_guest_user(user),
            "guest_retention_hours": (
                config.GUEST_RETENTION_HOURS if is_guest_user(user) else None
            ),
            "can_change_imap_password": can_change_imap_password(user),
        }
    }


@router.patch("/api/me")
def update_profile(request: Request):
    user = current_active_user(request)
    require_writable_profile(user)
    raise HTTPException(status_code=501, detail="Profile updates are not implemented")


@router.get("/api/me/imap-settings")
def imap_settings(request: Request):
    user = current_active_user(request)
    settings = {
        "host": config.public_imap_host(),
        "port": config.PUBLIC_IMAP_PORT,
        "smtp_port": config.PUBLIC_SMTP_PORT,
        "security": config.PUBLIC_IMAP_SECURITY,
        "username": user["imap_username"],
    }
    if not can_change_imap_password(user):
        settings["password"] = config.GUEST_USER_PASSWORD
    return {"imap": settings}


@router.post("/api/me/imap-password")
def regenerate_imap_password(request: Request):
    user = current_active_user(request)
    if not can_change_imap_password(user):
        raise HTTPException(
            status_code=403,
            detail="Guest IMAP password can only be changed by an administrator",
        )
    reset = reset_imap_password(user["imap_username"])
    logger.info(
        "IMAP password regenerated for user_id=%s email=%s imap_username=%s",
        reset["id"],
        reset["email"],
        reset["imap_username"],
    )
    return {
        "imap": {
            "username": reset["imap_username"],
            "password": reset["imap_password"],
        }
    }
