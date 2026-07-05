import os
import secrets

from authlib.integrations.starlette_client import OAuth

SUPPORTED_PROVIDERS = ("google", "microsoft")

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
MICROSOFT_METADATA_URL = (
    "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
)
OAUTH_SCOPE = "openid email profile"
SESSION_COOKIE_NAME = "running_notes_session"
SESSION_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
SESSION_SAME_SITE = "lax"
MIN_SESSION_SECRET_LENGTH = 32


class UnknownOAuthProviderError(ValueError):
    pass


class OAuthConfigurationError(RuntimeError):
    pass


class OAuthUserInfoError(ValueError):
    pass


def extract_userinfo_identity(provider: str, userinfo: dict) -> tuple[str, str, bool]:
    _validate_provider(provider)

    provider_subject = userinfo.get("sub")
    if not isinstance(provider_subject, str) or not provider_subject:
        raise OAuthUserInfoError("OAuth provider did not return a subject")

    email = userinfo.get("email") or userinfo.get("preferred_username")
    if not isinstance(email, str) or not email:
        raise OAuthUserInfoError("OAuth provider did not return an email")

    email_verified = _email_verified(provider, userinfo)
    if not email_verified:
        raise OAuthUserInfoError("OAuth provider did not verify the email")

    return provider_subject, email, email_verified


def create_oauth_registry() -> OAuth:
    oauth = OAuth()

    if _provider_configured("google"):
        oauth.register(
            name="google",
            client_id=_required_env("GOOGLE_CLIENT_ID"),
            client_secret=_required_env("GOOGLE_CLIENT_SECRET"),
            server_metadata_url=GOOGLE_METADATA_URL,
            client_kwargs={"scope": OAUTH_SCOPE},
        )

    if _provider_configured("microsoft"):
        oauth.register(
            name="microsoft",
            client_id=_required_env("MICROSOFT_CLIENT_ID"),
            client_secret=_required_env("MICROSOFT_CLIENT_SECRET"),
            server_metadata_url=MICROSOFT_METADATA_URL,
            client_kwargs={"scope": OAUTH_SCOPE},
        )

    return oauth


def get_oauth_client(oauth: OAuth, provider: str):
    _validate_provider(provider)
    client = oauth.create_client(provider)
    if client is None:
        raise OAuthConfigurationError(f"{provider} OAuth is not configured")
    return client


def build_redirect_uri(provider: str) -> str:
    _validate_provider(provider)

    explicit_redirect_uri = os.environ.get(_redirect_uri_env(provider), "").strip()
    if explicit_redirect_uri:
        return explicit_redirect_uri

    public_base_url = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not public_base_url:
        raise OAuthConfigurationError(
            f"{_redirect_uri_env(provider)} or PUBLIC_BASE_URL is required"
        )
    return f"{public_base_url}/auth/callback/{provider}"


def session_secret() -> str:
    secret = _required_env("SESSION_SECRET")
    if len(secret) < MIN_SESSION_SECRET_LENGTH:
        raise OAuthConfigurationError(
            f"SESSION_SECRET must be at least {MIN_SESSION_SECRET_LENGTH} characters"
        )
    return secret


def session_cookie_secure() -> bool:
    value = os.environ.get("SESSION_COOKIE_SECURE", "true").strip().lower()
    secure = value not in {"0", "false", "no", "off"}
    if not secure and _app_env() == "production":
        raise OAuthConfigurationError(
            "SESSION_COOKIE_SECURE cannot be disabled in production"
        )
    return secure


def new_session_nonce() -> str:
    return secrets.token_urlsafe(16)


def _email_verified(provider: str, userinfo: dict) -> bool:
    value = userinfo.get("email_verified")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    # Microsoft OIDC userinfo does not consistently include a Google-style
    # email_verified claim. The account identity itself is still verified by
    # Microsoft before the authorization code is issued.
    return provider == "microsoft"


def _app_env() -> str:
    return (
        os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or "development"
    ).strip().lower()


def _provider_configured(provider: str) -> bool:
    return bool(
        os.environ.get(_client_id_env(provider), "").strip()
        or os.environ.get(_client_secret_env(provider), "").strip()
    )


def _validate_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise UnknownOAuthProviderError(provider)


def _client_id_env(provider: str) -> str:
    return f"{provider.upper()}_CLIENT_ID"


def _client_secret_env(provider: str) -> str:
    return f"{provider.upper()}_CLIENT_SECRET"


def _redirect_uri_env(provider: str) -> str:
    return f"{provider.upper()}_REDIRECT_URI"


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise OAuthConfigurationError(f"{name} is required")
    return value
