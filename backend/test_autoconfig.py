import unittest
from xml.etree import ElementTree

from autoconfig import (
    AutoconfigRequestError,
    outlook_request_email,
    outlook_response_xml,
    thunderbird_config_xml,
)


class AutoconfigTests(unittest.TestCase):
    def test_reads_outlook_request_email(self):
        body = b"""<?xml version="1.0"?>
        <Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
          <Request><EMailAddress>User@notes.example</EMailAddress></Request>
        </Autodiscover>"""
        self.assertEqual("User@notes.example", outlook_request_email(body))

    def test_rejects_outlook_request_without_email(self):
        with self.assertRaises(AutoconfigRequestError):
            outlook_request_email(b"<Autodiscover />")

    def test_outlook_response_uses_dynamic_ports(self):
        root = ElementTree.fromstring(
            outlook_response_xml("user@notes.example", "notes.example", 994, 588)
        )
        protocols = {
            child.findtext("{*}Type"): child
            for child in root.findall(".//{*}Protocol")
        }
        self.assertEqual("994", protocols["IMAP"].findtext("{*}Port"))
        self.assertEqual("588", protocols["SMTP"].findtext("{*}Port"))
        self.assertEqual(
            "user@notes.example", protocols["SMTP"].findtext("{*}LoginName")
        )

    def test_thunderbird_response_uses_dynamic_ports(self):
        root = ElementTree.fromstring(
            thunderbird_config_xml("notes.example", 994, 588)
        )
        incoming = root.find(".//incomingServer")
        outgoing = root.find(".//outgoingServer")
        self.assertEqual("994", incoming.findtext("port"))
        self.assertEqual("SSL", incoming.findtext("socketType"))
        self.assertEqual("588", outgoing.findtext("port"))
        self.assertEqual("STARTTLS", outgoing.findtext("socketType"))
        self.assertEqual("%EMAILADDRESS%", outgoing.findtext("username"))


if __name__ == "__main__":
    unittest.main()
