"""Actual loopback SMTP/HTTP delivery, protocol errors and credential redaction."""

import json
import socketserver
import threading
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from app.core.config import Settings
from app.services import notification_service, subscription_service


class SMTPHandler(socketserver.StreamRequestHandler):
    """Minimal local receiving server; never relays email to an external address."""

    def handle(self) -> None:
        self.wfile.write(b"220 localhost SMTP test receiver\r\n")
        while line := self.rfile.readline():
            command = line.split(b" ", 1)[0].strip().upper()
            if command in {b"EHLO", b"HELO"}:
                self.wfile.write(b"250-localhost\r\n250 SIZE 1000000\r\n")
            elif command == b"DATA":
                self.wfile.write(b"354 Send message\r\n")
                body = []
                while (line := self.rfile.readline()) != b".\r\n":
                    if not line:
                        return
                    body.append(line[1:] if line.startswith(b"..") else line)
                self.server.messages.append(b"".join(body))
                self.wfile.write(b"250 Accepted\r\n")
            elif command == b"QUIT":
                self.wfile.write(b"221 Bye\r\n")
                return
            else:
                self.wfile.write(b"250 OK\r\n")


@pytest.fixture
def smtp_receiver():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SMTPHandler)
    server.messages = []
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_real_smtp_unicode_subject_body_and_message_identity(
    monkeypatch, smtp_receiver
):
    settings = Settings(
        APP_ENV="test",
        EMAIL_NOTIFICATIONS_ENABLED=True,
        SMTP_HOST="127.0.0.1",
        SMTP_PORT=smtp_receiver.server_address[1],
        SMTP_FROM="miningintel@localhost",
        SMTP_STARTTLS=False,
        SMTP_SSL=False,
        SMTP_USERNAME="",
    )
    monkeypatch.setattr(subscription_service, "get_settings", lambda: settings)
    subscription_service.send_email(
        "local-recipient@example.test",
        "锂价预警 +4%",
        "碳酸锂报价 121000 CNY/吨。\nhttps://example.test/evidence",
        "stable-notice-id",
    )
    message = BytesParser(policy=policy.default).parsebytes(smtp_receiver.messages[0])
    assert message["Subject"] == "锂价预警 +4%"
    assert "121000 CNY/吨" in message.get_content()
    assert message["Message-ID"] == "<stable-notice-id@miningintel.local>"


class WebhookHandler(BaseHTTPRequestHandler):
    """Loopback robot endpoint implementing each provider's acknowledgement format."""

    def log_message(self, fmt: str, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.messages.append((self.path, payload))
        self.send_response(429 if self.path == "/limited" else 200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        answer = (
            b"ok"
            if self.path == "/slack"
            else json.dumps(
                {"code": 0, "errcode": 0 if self.path != "/rejected" else 400}
            ).encode()
        )
        self.wfile.write(answer)


@pytest.fixture
def webhook_receiver():
    server = ThreadingHTTPServer(("127.0.0.1", 0), WebhookHandler)
    server.messages = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


async def test_real_local_webhooks_validate_provider_acknowledgements(
    monkeypatch, webhook_receiver
):
    root = f"http://127.0.0.1:{webhook_receiver.server_address[1]}"
    settings = Settings(
        APP_ENV="test",
        WEBHOOK_NOTIFICATIONS_ENABLED=True,
        SLACK_WEBHOOK_URL=root + "/slack",
        FEISHU_WEBHOOK_URL=root + "/feishu",
        WECOM_WEBHOOK_URL=root + "/wecom",
        FEISHU_WEBHOOK_SECRET="local-test-signature",
    )
    monkeypatch.setattr(notification_service, "get_settings", lambda: settings)
    for channel in ("slack", "feishu", "wecom"):
        assert (
            await notification_service.send_webhook(channel, "矿产资源日报") == "sent"
        )
    assert webhook_receiver.messages[0][1]["text"] == "矿产资源日报"
    assert webhook_receiver.messages[1][1]["content"]["text"] == "矿产资源日报"
    assert "sign" in webhook_receiver.messages[1][1]
    assert webhook_receiver.messages[2][1]["msgtype"] == "text"
    settings.WECOM_WEBHOOK_URL = type(settings.WECOM_WEBHOOK_URL)(root + "/rejected")
    with pytest.raises(RuntimeError, match="Robot rejected"):
        await notification_service.send_webhook("wecom", "拒绝")
    settings.WECOM_WEBHOOK_URL = type(settings.WECOM_WEBHOOK_URL)(root + "/limited")
    assert await notification_service.send_webhook("wecom", "限速") == "rate_limited"


async def test_disabled_and_non_provider_webhooks_never_send(monkeypatch):
    settings = Settings(WEBHOOK_NOTIFICATIONS_ENABLED=False)
    monkeypatch.setattr(notification_service, "get_settings", lambda: settings)
    assert await notification_service.send_webhook("slack", "日报") == "disabled"
    settings.WEBHOOK_NOTIFICATIONS_ENABLED = True
    settings.SLACK_WEBHOOK_URL = type(settings.SLACK_WEBHOOK_URL)(
        "http://169.254.169.254/metadata"
    )
    with pytest.raises(ValueError, match="Unsupported"):
        await notification_service.send_webhook("slack", "日报")
