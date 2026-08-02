from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

import config
from autoconfig import (
    AutoconfigRequestError,
    outlook_request_email,
    outlook_response_xml,
    thunderbird_config_xml,
)
from users import InvalidEmailError, normalize_email

router = APIRouter()


@router.post("/autodiscover/autodiscover.xml")
@router.post("/Autodiscover/Autodiscover.xml")
async def outlook_autodiscover(request: Request):
    body = await request.body()
    if len(body) > 64 * 1024:
        raise HTTPException(status_code=413, detail="Autodiscover request is too large")
    try:
        email = normalize_email(outlook_request_email(body))
    except (AutoconfigRequestError, InvalidEmailError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if email.rsplit("@", 1)[1] != config.public_imap_host().lower():
        raise HTTPException(status_code=400, detail="Unsupported email domain")
    return Response(
        outlook_response_xml(
            email, config.public_imap_host(), config.PUBLIC_IMAP_PORT, config.PUBLIC_SMTP_PORT
        ),
        media_type="application/xml",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/.well-known/autoconfig/mail/config-v1.1.xml")
def thunderbird_autoconfig():
    return Response(
        thunderbird_config_xml(
            config.public_imap_host(), config.PUBLIC_IMAP_PORT, config.PUBLIC_SMTP_PORT
        ),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
