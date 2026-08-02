from fastapi import HTTPException, Request

from users import get_user_by_id


def is_guest_user(user: dict) -> bool:
    return bool(user["is_guest"])


def can_change_imap_password(user: dict) -> bool:
    return not is_guest_user(user)


def require_writable_profile(user: dict) -> None:
    if is_guest_user(user):
        raise HTTPException(
            status_code=403,
            detail="Guest profile is read-only",
        )


def current_active_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = get_user_by_id(user_id)
    if user is None or user["status"] != "active":
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user
