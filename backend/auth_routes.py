import logging

from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

import config
import services
from application_routes import safe_application_return_path
from oauth import (
    OAuthConfigurationError,
    OAuthUserInfoError,
    UnknownOAuthProviderError,
    build_redirect_uri,
    extract_userinfo_identity,
    get_oauth_client,
    new_session_nonce,
    oauth_claims_options,
)
from oauth_identities import OAuthIdentityError, get_or_create_oauth_user
from users import get_guest_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/auth/login/{provider}")
async def oauth_login(
    provider: str,
    request: Request,
    return_to: str | None = Query(default=None),
):
    try:
        client = get_oauth_client(services.oauth, provider)
        redirect_uri = build_redirect_uri(provider)
    except UnknownOAuthProviderError:
        logger.warning("OAuth login rejected for unknown provider=%s", provider)
        raise HTTPException(status_code=404, detail="Unknown OAuth provider")
    except OAuthConfigurationError as exc:
        logger.warning("OAuth login configuration error for provider=%s", provider)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    logger.info(
        "OAuth login started provider=%s redirect_uri=%s", provider, redirect_uri
    )
    request.session.clear()
    request.session["oauth_return_to"] = safe_application_return_path(return_to)
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback/{provider}")
async def oauth_callback(provider: str, request: Request):
    return_to = safe_application_return_path(
        request.session.get("oauth_return_to")
    )
    try:
        client = get_oauth_client(services.oauth, provider)
        token = await client.authorize_access_token(
            request,
            claims_options=oauth_claims_options(provider),
        )
        provider_subject, email, email_verified = extract_userinfo_identity(
            provider, token["userinfo"]
        )
        user = get_or_create_oauth_user(
            provider,
            provider_subject,
            email,
            email_verified,
            config.public_imap_host(),
        )
    except UnknownOAuthProviderError:
        logger.warning("OAuth callback rejected for unknown provider=%s", provider)
        raise HTTPException(status_code=404, detail="Unknown OAuth provider")
    except OAuthConfigurationError as exc:
        logger.warning("OAuth callback configuration error provider=%s", provider)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OAuthUserInfoError as exc:
        logger.warning(
            "OAuth callback userinfo rejected provider=%s error=%s", provider, exc
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OAuthIdentityError as exc:
        logger.warning(
            "OAuth callback identity rejected provider=%s error=%s", provider, exc
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OAuthError as exc:
        logger.warning(
            "OAuth callback failed provider=%s error=%s",
            provider,
            exc.__class__.__name__,
        )
        raise HTTPException(status_code=400, detail="OAuth login failed") from exc
    except KeyError as exc:
        logger.warning("OAuth callback missing userinfo provider=%s", provider)
        raise HTTPException(
            status_code=400, detail="OAuth provider did not return user info"
        ) from exc

    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["login_nonce"] = new_session_nonce()
    logger.info(
        "OAuth login completed provider=%s user_id=%s email=%s",
        provider,
        user["id"],
        user["email"],
    )
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/auth/logout", status_code=204)
def logout(request: Request):
    request.session.clear()
    return None


@router.post("/auth/guest", status_code=204)
def guest_login(request: Request):
    user = get_guest_user()
    if user is None or user["status"] != "active":
        raise HTTPException(status_code=503, detail="Guest account is unavailable")

    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["login_nonce"] = new_session_nonce()
    logger.info("Guest login completed user_id=%s email=%s", user["id"], user["email"])
    return None
