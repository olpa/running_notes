import re


APPLICATION_RETURN_PATH = re.compile(
    r"^/(?:record|imap|account|messages(?:/[A-Za-z0-9_-]+)?)$"
)


def safe_application_return_path(value: str | None) -> str:
    if value and APPLICATION_RETURN_PATH.fullmatch(value):
        return value
    return "/record"
