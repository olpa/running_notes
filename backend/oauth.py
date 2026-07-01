import os

from authlib.integrations.starlette_client import OAuth

SUPPORTED_PROVIDERS = ("google", "microsoft")

GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
MICROSOFT_METADATA_URL = (
    "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
)
OAUTH_SCOPE = "openid email profile"


class UnknownOAuthProviderError(ValueError):
    pass


class OAuthConfigurationError(RuntimeError):
    pass


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
    return _required_env("SESSION_SECRET")


def session_cookie_secure() -> bool:
    value = os.environ.get("SESSION_COOKIE_SECURE", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


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
