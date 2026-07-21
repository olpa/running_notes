import asyncio
import logging
import os
import signal


HOST = os.environ.get("SMTP_SINK_HOST", "0.0.0.0")
PORT = int(os.environ.get("SMTP_SINK_PORT", "2525"))
COMMAND_TIMEOUT_SECONDS = int(os.environ.get("SMTP_SINK_TIMEOUT", "60"))
MAX_LINE_BYTES = 8192
MAX_RECIPIENTS = 10
REJECTION = "554 5.7.1 Outgoing delivery is disabled by Running Notes"

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("smtp-discard")


async def send_reply(writer: asyncio.StreamWriter, reply: str) -> None:
    writer.write((reply + "\r\n").encode("ascii"))
    await writer.drain()


async def handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    peer = writer.get_extra_info("peername")
    greeted = False
    mail_from = False
    recipient_count = 0
    logger.debug("connection opened peer=%s", peer)

    try:
        await send_reply(writer, "220 smtp-discard ESMTP Running Notes")
        while True:
            try:
                line = await asyncio.wait_for(
                    reader.readline(), timeout=COMMAND_TIMEOUT_SECONDS
                )
            except TimeoutError:
                await send_reply(writer, "421 4.4.2 Command timeout")
                break

            if not line:
                break
            if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
                await send_reply(writer, "500 5.5.2 Command line too long")
                break

            command_line = line.decode("utf-8", errors="replace").strip("\r\n")
            command, _, argument = command_line.partition(" ")
            command = command.upper()

            if command in {"EHLO", "HELO"}:
                greeted = True
                mail_from = False
                recipient_count = 0
                if command == "EHLO":
                    writer.write(
                        b"250-smtp-discard\r\n"
                        b"250-ENHANCEDSTATUSCODES\r\n"
                        b"250-8BITMIME\r\n"
                        b"250-SMTPUTF8\r\n"
                        b"250 SIZE 10485760\r\n"
                    )
                    await writer.drain()
                else:
                    await send_reply(writer, "250 smtp-discard")
            elif command == "NOOP":
                await send_reply(writer, "250 2.0.0 OK")
            elif command == "RSET":
                mail_from = False
                recipient_count = 0
                await send_reply(writer, "250 2.0.0 Reset")
            elif command == "QUIT":
                await send_reply(writer, "221 2.0.0 Bye")
                break
            elif command == "MAIL":
                if not greeted:
                    await send_reply(writer, "503 5.5.1 Send EHLO first")
                elif not argument.upper().startswith("FROM:"):
                    await send_reply(writer, "501 5.5.4 MAIL requires FROM")
                else:
                    mail_from = True
                    recipient_count = 0
                    await send_reply(writer, "250 2.1.0 Sender accepted")
            elif command == "RCPT":
                if not mail_from:
                    await send_reply(writer, "503 5.5.1 Send MAIL first")
                elif not argument.upper().startswith("TO:"):
                    await send_reply(writer, "501 5.5.4 RCPT requires TO")
                elif recipient_count >= MAX_RECIPIENTS:
                    await send_reply(writer, "452 4.5.3 Too many recipients")
                else:
                    recipient_count += 1
                    await send_reply(writer, "250 2.1.5 Recipient accepted")
            elif command == "DATA":
                if not mail_from or recipient_count == 0:
                    await send_reply(writer, "503 5.5.1 Need MAIL and RCPT first")
                else:
                    logger.info(
                        "delivery rejected peer=%s recipients=%d", peer, recipient_count
                    )
                    mail_from = False
                    recipient_count = 0
                    await send_reply(writer, REJECTION)
            else:
                await send_reply(writer, "502 5.5.1 Command not implemented")
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionError:
            pass
        logger.debug("connection closed peer=%s", peer)


async def main() -> None:
    shutdown_requested = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown(signal_name: str) -> None:
        logger.info("shutdown requested signal=%s", signal_name)
        shutdown_requested.set()

    handled_signals = (signal.SIGTERM, signal.SIGINT)
    for handled_signal in handled_signals:
        loop.add_signal_handler(
            handled_signal, request_shutdown, handled_signal.name
        )

    server = await asyncio.start_server(handle_client, HOST, PORT)
    addresses = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    logger.info("SMTP discard sink listening on %s", addresses)
    try:
        async with server:
            await shutdown_requested.wait()
    finally:
        for handled_signal in handled_signals:
            loop.remove_signal_handler(handled_signal)
        logger.info("SMTP discard sink stopped")


if __name__ == "__main__":
    asyncio.run(main())
