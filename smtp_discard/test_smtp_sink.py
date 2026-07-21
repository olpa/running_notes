import asyncio
import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path

from smtp_sink import REJECTION, handle_client


class SmtpDiscardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def connect(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.assertTrue((await reader.readline()).startswith(b"220 "))
        return reader, writer

    async def test_rejects_delivery_at_data_without_reading_a_body(self):
        reader, writer = await self.connect()
        writer.write(
            b"EHLO dovecot\r\n"
            b"MAIL FROM:<sender@example.com>\r\n"
            b"RCPT TO:<recipient@example.com>\r\n"
            b"DATA\r\n"
        )
        await writer.drain()

        self.assertEqual(b"250-smtp-discard\r\n", await reader.readline())
        self.assertEqual(b"250-ENHANCEDSTATUSCODES\r\n", await reader.readline())
        self.assertEqual(b"250-8BITMIME\r\n", await reader.readline())
        self.assertEqual(b"250-SMTPUTF8\r\n", await reader.readline())
        self.assertEqual(b"250 SIZE 10485760\r\n", await reader.readline())
        self.assertTrue((await reader.readline()).startswith(b"250 "))
        self.assertTrue((await reader.readline()).startswith(b"250 "))
        self.assertEqual((REJECTION + "\r\n").encode(), await reader.readline())

        writer.write(b"QUIT\r\n")
        await writer.drain()
        self.assertTrue((await reader.readline()).startswith(b"221 "))
        writer.close()
        await writer.wait_closed()

    async def test_requires_a_complete_envelope_before_data(self):
        reader, writer = await self.connect()
        writer.write(b"EHLO dovecot\r\nDATA\r\nQUIT\r\n")
        await writer.drain()

        for _ in range(5):
            await reader.readline()
        self.assertTrue((await reader.readline()).startswith(b"503 "))
        self.assertTrue((await reader.readline()).startswith(b"221 "))
        writer.close()
        await writer.wait_closed()


class SmtpDiscardShutdownTests(unittest.TestCase):
    def test_process_exits_cleanly_on_sigterm(self):
        environment = os.environ.copy()
        environment["SMTP_SINK_HOST"] = "127.0.0.1"
        environment["SMTP_SINK_PORT"] = "0"
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("smtp_sink.py"))],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                line = process.stdout.readline()
                if "SMTP discard sink listening" in line:
                    break
            else:
                self.fail("SMTP discard sink did not start")

            process.send_signal(signal.SIGTERM)
            self.assertEqual(0, process.wait(timeout=5))
            output = process.stdout.read()
            self.assertIn("shutdown requested signal=SIGTERM", output)
            self.assertIn("SMTP discard sink stopped", output)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()


if __name__ == "__main__":
    unittest.main()
