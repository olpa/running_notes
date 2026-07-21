from xml.etree import ElementTree
from xml.sax.saxutils import escape


OUTLOOK_REQUEST_NAMESPACE = (
    "http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006"
)
OUTLOOK_RESPONSE_NAMESPACE = (
    "http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006"
)
OUTLOOK_ACCOUNT_NAMESPACE = (
    "http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a"
)
class AutoconfigRequestError(ValueError):
    pass


def outlook_request_email(body: bytes) -> str:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise AutoconfigRequestError("Invalid Autodiscover XML") from exc

    email = root.findtext(f".//{{{OUTLOOK_REQUEST_NAMESPACE}}}EMailAddress")
    if email is None:
        email = next(
            (
                element.text
                for element in root.iter()
                if element.tag.rsplit("}", 1)[-1].lower() == "emailaddress"
            ),
            None,
        )
    if not email or not email.strip():
        raise AutoconfigRequestError("Autodiscover request has no email address")
    return email.strip()


def outlook_response_xml(
    email: str, host: str, imap_port: int, smtp_port: int
) -> bytes:
    safe_email = escape(email)
    safe_host = escape(host)
    protocols = "".join(
        _outlook_protocol(protocol_type, safe_email, safe_host, port)
        for protocol_type, port in (("IMAP", imap_port), ("SMTP", smtp_port))
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="{OUTLOOK_RESPONSE_NAMESPACE}">
  <Response xmlns="{OUTLOOK_ACCOUNT_NAMESPACE}">
    <User>
      <DisplayName>{safe_email}</DisplayName>
      <AutoDiscoverSMTPAddress>{safe_email}</AutoDiscoverSMTPAddress>
    </User>
    <Account>
      <AccountType>email</AccountType>
      <Action>settings</Action>
{protocols}    </Account>
  </Response>
</Autodiscover>
""".encode("utf-8")


def thunderbird_config_xml(host: str, imap_port: int, smtp_port: int) -> bytes:
    root = ElementTree.Element("clientConfig", {"version": "1.1"})
    provider = ElementTree.SubElement(root, "emailProvider", {"id": host})
    _plain_element(provider, "domain", host)
    _plain_element(provider, "displayName", "Running Notes")
    _plain_element(provider, "displayShortName", "Running Notes")

    incoming = ElementTree.SubElement(provider, "incomingServer", {"type": "imap"})
    _thunderbird_server(incoming, host, imap_port, "SSL")

    outgoing = ElementTree.SubElement(provider, "outgoingServer", {"type": "smtp"})
    _thunderbird_server(outgoing, host, smtp_port, "STARTTLS")
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _outlook_protocol(
    protocol_type: str,
    email: str,
    host: str,
    port: int,
) -> str:
    return f"""      <Protocol>
        <Type>{protocol_type}</Type>
        <Server>{host}</Server>
        <Port>{port}</Port>
        <LoginName>{email}</LoginName>
        <DomainRequired>off</DomainRequired>
        <SPA>off</SPA>
        <SSL>on</SSL>
        <AuthRequired>on</AuthRequired>
      </Protocol>
"""


def _thunderbird_server(
    parent: ElementTree.Element,
    host: str,
    port: int,
    socket_type: str,
) -> None:
    _plain_element(parent, "hostname", host)
    _plain_element(parent, "port", str(port))
    _plain_element(parent, "socketType", socket_type)
    _plain_element(parent, "authentication", "password-cleartext")
    _plain_element(parent, "username", "%EMAILADDRESS%")


def _plain_element(parent: ElementTree.Element, name: str, text: str) -> None:
    element = ElementTree.SubElement(parent, name)
    element.text = text
