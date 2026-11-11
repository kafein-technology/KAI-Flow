"""Send one email through a reusable SMTP credential without extra dependencies."""

import smtplib
import ssl
import time
from contextlib import contextmanager
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any, Dict

import httpx
from email_validator import EmailNotValidError, validate_email

from ..base import (
    NodeInput, NodeOutput, NodePosition, NodeProperty, NodePropertyType,
    NodeType, ProcessorNode,
)


SMTP_PROVIDERS = {
    "google": {"host": "smtp.gmail.com", "port": 587, "security": "starttls"},
}


def _smtp_access_token(secret: Dict[str, Any], timeout: int, on_token_refresh=None) -> str:
    if secret.get("provider") != "google":
        raise ValueError("OAuth2 is supported only for Google Gmail.")
    fields = {}
    for name in ("client_id", "client_secret", "refresh_token"):
        value = secret.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"OAuth {name.replace('_', ' ').title()} is required.")
        fields[name] = value.strip()
    endpoint, scope = "https://oauth2.googleapis.com/token", "https://mail.google.com/"
    try:
        with httpx.Client(timeout=min(timeout, 30)) as client:
            response = client.post(endpoint, data={**fields, "grant_type": "refresh_token", "scope": scope})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise ValueError("OAuth token refresh failed. Check the client credentials, refresh token, SMTP permissions, and administrator policy.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str) or not payload["access_token"].strip():
        raise ValueError("OAuth provider did not return an access token.")
    token_type = payload.get("token_type", "Bearer")
    if not isinstance(token_type, str) or token_type.lower() != "bearer":
        raise ValueError("OAuth provider returned an unsupported token type.")
    granted = payload.get("scope")
    if granted is not None and (not isinstance(granted, str) or scope not in granted.split()):
        raise ValueError(f"Authorize the refresh token with the SMTP permission {scope}.")
    token = payload["access_token"]
    if not token.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in token):
        raise ValueError("OAuth provider returned an invalid access token.")
    refreshed = payload.get("refresh_token")
    if refreshed is not None and (not isinstance(refreshed, str) or not refreshed.strip()):
        raise ValueError("OAuth provider returned an invalid refresh token.")
    if refreshed and refreshed != fields["refresh_token"]:
        if on_token_refresh:
            on_token_refresh(fields["refresh_token"], refreshed)
        secret["refresh_token"] = refreshed
    return token


def _integer(value: Any, label: str, maximum: int) -> int:
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be an integer between 1 and {maximum}.") from None
    if not 1 <= number <= maximum:
        raise ValueError(f"{label} must be between 1 and {maximum}.")
    return number


@contextmanager
def smtp_connection(secret: Dict[str, Any], timeout: int = 30, on_token_refresh=None):
    """Share validated TLS/auth behavior between sending and credential checks."""
    provider = secret.get("provider", "custom")
    if provider not in ("custom", *SMTP_PROVIDERS):
        raise ValueError("Select Custom SMTP or Google Gmail.")
    connection = {**SMTP_PROVIDERS.get(provider, {}), **secret}
    if provider == "google":
        security = secret.get("security", "starttls")
        if security not in ("starttls", "tls"):
            raise ValueError("Google Gmail requires STARTTLS or TLS.")
        connection.update(security=security, port=secret.get("port", 465 if security == "tls" else 587))
    host = connection.get("host", "")
    if not isinstance(host, str) or not host.strip() or any(c.isspace() or c in "/@?#\x00" for c in host):
        raise ValueError("SMTP Host must be a hostname or IP address without a URL scheme.")
    port = _integer(connection.get("port", 587), "SMTP Port", 65535)
    timeout = _integer(timeout, "Timeout", 300)
    security = connection.get("security", "starttls")
    if security not in ("starttls", "tls", "none"):
        raise ValueError("Select STARTTLS, TLS, or None for SMTP security.")
    username, password = secret.get("username") or "", secret.get("password") or ""
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValueError("SMTP username and password must be text.")
    authentication = secret.get("authentication", "oauth2" if provider != "custom" else "password" if username or password else "none")
    if authentication not in ("none", "password", "oauth2"):
        raise ValueError("Select a supported SMTP authentication method.")
    if provider != "custom" and authentication == "none":
        raise ValueError("Google Gmail requires authentication.")
    if authentication == "oauth2" and provider == "custom":
        raise ValueError("Select Google Gmail to use OAuth2.")
    if authentication == "oauth2" and host.lower().rstrip(".") != "smtp.gmail.com":
        raise ValueError("Google OAuth2 requires smtp.gmail.com. Use Custom SMTP for other servers.")
    if any(ord(c) < 32 or ord(c) == 127 for c in username):
        raise ValueError("SMTP username must not contain control characters.")
    if authentication == "password" and (not username or not password):
        raise ValueError("SMTP username and password are required for password authentication.")
    if authentication == "oauth2" and not username.strip():
        raise ValueError("An account email address is required for OAuth2.")
    if authentication == "oauth2" and not username.isascii():
        raise ValueError("OAuth account email must contain only ASCII characters.")
    if authentication != "none" and security == "none":
        raise ValueError("SMTP authentication requires STARTTLS or TLS.")
    token = _smtp_access_token(secret, timeout, on_token_refresh) if authentication == "oauth2" else None

    context = ssl.create_default_context()
    client = smtplib.SMTP_SSL(host=host, port=port, timeout=timeout, context=context) if security == "tls" else smtplib.SMTP(host=host, port=port, timeout=timeout)
    try:
        code, _ = client.ehlo()
        if code != 250:
            raise smtplib.SMTPHeloError(code, b"EHLO failed")
        if security == "starttls":
            client.starttls(context=context)
            code, _ = client.ehlo()
            if code != 250:
                raise smtplib.SMTPHeloError(code, b"EHLO failed after STARTTLS")
        if authentication == "oauth2":
            client.auth("XOAUTH2", lambda challenge=None: f"user={username}\x01auth=Bearer {token}\x01\x01" if challenge is None else "")
        elif authentication == "password":
            client.login(username, password)
        yield client
    finally:
        # QUIT failure must not turn an accepted message into a retryable failure.
        try:
            client.quit()
        except (OSError, smtplib.SMTPException):
            pass
        finally:
            client.close()


def smtp_error_message(error: Exception) -> str:
    """Do not expose SMTP server replies, which can echo credentials or recipients."""
    if isinstance(error, UnicodeError):
        return "SMTP credentials contain unsupported characters. Check the account and authentication method."
    if isinstance(error, ValueError):
        return str(error)
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "SMTP authentication failed. Check the account and server authentication policy."
    if isinstance(error, ssl.SSLCertVerificationError):
        return "SMTP certificate verification failed. Check the hostname and trusted CA certificates."
    if isinstance(error, smtplib.SMTPNotSupportedError):
        return "The SMTP server does not support the requested TLS, authentication, or message encoding."
    if isinstance(error, smtplib.SMTPResponseException):
        return f"SMTP server rejected the operation (code {error.smtp_code})."
    return "SMTP connection failed or timed out. Check the host, port, security mode, and network access."


def check_smtp_connection(secret: Dict[str, Any], on_token_refresh=None) -> None:
    """Check EHLO, TLS and optional AUTH without sending a message."""
    with smtp_connection(secret, on_token_refresh=on_token_refresh):
        pass


def _header(value: Any, label: str) -> str:
    if not isinstance(value, str) or any(c in value for c in "\r\n\x00"):
        raise ValueError(f"{label} must be text without line breaks or null characters.")
    return value


def _addresses(value: Any, label: str, required: bool = False) -> list[Address]:
    raw = _header(value, label)
    if not raw.strip():
        if required:
            raise ValueError(f"{label} requires at least one email address.")
        return []
    try:
        parsed = EmailMessage()
        parsed["To"] = raw
        header = parsed["To"]
        if header.defects or not header.addresses:
            raise ValueError()
        addresses = []
        for address in header.addresses:
            valid = validate_email(address.addr_spec, check_deliverability=False, test_environment=True)
            addresses.append(Address(display_name=address.display_name, addr_spec=valid.ascii_email or valid.normalized))
        return addresses
    except (ValueError, EmailNotValidError, IndexError):
        raise ValueError(f"{label} contains an invalid email address. Separate recipients with commas.") from None


def build_smtp_message(configuration: Dict[str, Any]) -> tuple[EmailMessage, str, list[str]]:
    """Keep visible headers separate from envelope recipients, including Bcc."""
    sender = _addresses(configuration.get("from_email", ""), "From", required=True)
    if len(sender) != 1:
        raise ValueError("From must contain exactly one email address.")
    display_name = _header(configuration.get("from_name", ""), "Sender name")
    to = _addresses(configuration.get("to", ""), "To", required=True)
    cc = _addresses(configuration.get("cc", ""), "Cc")
    bcc = _addresses(configuration.get("bcc", ""), "Bcc")
    reply_to = _addresses(configuration.get("reply_to", ""), "Reply To")
    message = EmailMessage()
    message["From"] = Address(display_name=display_name or sender[0].display_name, addr_spec=sender[0].addr_spec)
    message["To"] = to
    if cc:
        message["Cc"] = cc
    if reply_to:
        message["Reply-To"] = reply_to
    message["Subject"] = _header(configuration.get("subject", ""), "Subject")
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid()
    email_format = configuration.get("email_format", "text")
    if email_format not in ("text", "html", "both"):
        raise ValueError("Email Format must be Text, HTML, or Both.")
    for field in ("text", "html"):
        if not isinstance(configuration.get(field, ""), str):
            raise ValueError(f"{field.upper()} body must be text.")
    if email_format == "html":
        message.set_content(configuration.get("html", ""), subtype="html")
    else:
        message.set_content(configuration.get("text", ""))
        if email_format == "both":
            message.add_alternative(configuration.get("html", ""), subtype="html")
    recipients = list(dict.fromkeys(address.addr_spec for address in to + cc + bcc))
    return message, sender[0].addr_spec, recipients


class SmtpNode(ProcessorNode):
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "SmtpNode",
            "display_name": "Send Email (SMTP)",
            "description": "Send a text or HTML email through a local or remote SMTP server.",
            "category": "Integration",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "mail", "path": "icons/smtp_mail.svg", "alt": "SMTP email"},
            "colors": ["blue-500", "cyan-600"],
            "inputs": [NodeInput(name="input", displayName="Input", type="any", description="Message fields used when the corresponding form fields are empty.", required=False, is_connection=True, direction=NodePosition.LEFT)],
            "outputs": [
                NodeOutput(name="output", displayName="Output", type="dict", description="SMTP acceptance status, message ID, recipient counts, and duration.", is_connection=True, direction=NodePosition.RIGHT),
                NodeOutput(name="success", displayName="Success", type="boolean", description="True only when all recipients were accepted by the SMTP server."),
                NodeOutput(name="error", displayName="Error", type="string", description="Safe error or partial rejection information, without server reply text."),
            ],
            "properties": [
                NodeProperty(name="credential_id", displayName="SMTP Credential", type=NodePropertyType.CREDENTIAL_SELECT, serviceType="smtp", required=True, description="SMTP server connection and optional account credentials."),
                NodeProperty(name="from_email", displayName="From", type=NodePropertyType.TEXT, default="", required=False, placeholder="sender@example.com", description="Required sender address. May also come from the connected input."),
                NodeProperty(name="from_name", displayName="Sender Name", type=NodePropertyType.TEXT, default="", required=False, description="Optional display name for the sender."),
                NodeProperty(name="to", displayName="To", type=NodePropertyType.TEXT, default="", required=False, placeholder="recipient@example.com", description="Required recipients, separated by commas. May also come from the connected input."),
                NodeProperty(name="subject", displayName="Subject", type=NodePropertyType.TEXT, default="", required=False, description="Email subject. Supports workflow expressions."),
                NodeProperty(name="email_format", displayName="Email Format", type=NodePropertyType.SELECT, default="text", required=True, description="Send plain text, HTML, or both formats.", options=[{"label": "Text", "value": "text"}, {"label": "HTML", "value": "html"}, {"label": "Both", "value": "both"}]),
                NodeProperty(name="text", displayName="Text", type=NodePropertyType.TEXT_AREA, default="", required=False, rows=5, description="Plain text body. Supports workflow expressions.", displayOptions={"show": {"email_format": ["text", "both"]}}),
                NodeProperty(name="html", displayName="HTML", type=NodePropertyType.TEXT_AREA, default="", required=False, rows=5, description="HTML body. Supports workflow expressions.", displayOptions={"show": {"email_format": ["html", "both"]}}),
                NodeProperty(name="cc", displayName="Cc", type=NodePropertyType.TEXT, default="", required=False, tabName="advanced", description="Optional copy recipients, separated by commas."),
                NodeProperty(name="bcc", displayName="Bcc", type=NodePropertyType.TEXT, default="", required=False, tabName="advanced", description="Optional hidden recipients. Excluded from transmitted message headers and node results."),
                NodeProperty(name="reply_to", displayName="Reply To", type=NodePropertyType.TEXT, default="", required=False, tabName="advanced", description="Optional reply addresses, separated by commas."),
                NodeProperty(name="timeout_seconds", displayName="Timeout (seconds)", type=NodePropertyType.NUMBER, default=30, required=False, tabName="advanced", description="Socket operation timeout, from 1 to 300 seconds."),
                NodeProperty(name="continue_on_error", displayName="Continue On Error", type=NodePropertyType.CHECKBOX, default=False, required=False, tabName="advanced", description="Return failed or unknown status instead of stopping. Never automatically resend a message."),
            ],
        }

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        started = time.monotonic()
        configuration = dict(inputs or {})
        connected = (connected_nodes or {}).get("input")
        if isinstance(connected, dict) and all(key in connected for key in ("nodeId", "success", "output")):
            connected = connected["output"]
        for field in ("from_email", "from_name", "to", "subject", "text", "html", "cc", "bcc", "reply_to"):
            if isinstance(connected, dict) and configuration.get(field) in (None, ""):
                configuration[field] = connected.get(field, "")
        output = {"status": "failed", "message_id": None, "accepted_count": 0, "rejected_count": 0, "rejections": []}
        submitting = False
        error = None
        try:
            credential_id = configuration.get("credential_id")
            credential = self.get_credential(str(credential_id)) if credential_id else None
            if not credential or credential.get("service_type") != "smtp" or not isinstance(credential.get("secret"), dict):
                raise ValueError("Select a valid SMTP credential.")
            timeout = _integer(configuration.get("timeout_seconds", 30), "Timeout", 300)
            message, sender, recipients = build_smtp_message(configuration)
            output["message_id"] = str(message["Message-ID"])
            def save_refresh_token(previous, refreshed):
                from app.core.credential_provider import credential_provider

                credential_provider.update_refresh_token_sync(
                    credential.get("user_id") or getattr(self, "user_id", None), credential_id, previous, refreshed,
                )

            with smtp_connection(credential["secret"], timeout, save_refresh_token) as client:
                submitting = True
                rejected = client.send_message(message, from_addr=sender, to_addrs=recipients)
                submitting = False
            output.update(
                status="partial" if rejected else "accepted",
                accepted_count=len(recipients) - len(rejected),
                rejected_count=len(rejected),
                rejections=[{"recipient_index": index, "code": rejected[address][0]} for index, address in enumerate(recipients) if address in rejected],
            )
            if rejected:
                error = "Some recipients were rejected. Do not resend to recipients already accepted."
        except smtplib.SMTPRecipientsRefused as exc:
            output.update(rejected_count=len(exc.recipients), rejections=[{"recipient_index": index, "code": exc.recipients[address][0]} for index, address in enumerate(recipients) if address in exc.recipients])
            error = "All recipients were rejected by the SMTP server."
        except (OSError, smtplib.SMTPException, ValueError) as exc:
            if submitting and isinstance(exc, (OSError, smtplib.SMTPServerDisconnected)) and not isinstance(exc, smtplib.SMTPResponseException):
                output.update(status="unknown", accepted_count=None, rejected_count=None)
                error = "SMTP connection lost during submission. Delivery is unknown; check the server before retrying."
            else:
                error = smtp_error_message(exc)
        if output["status"] in ("failed", "unknown") and configuration.get("continue_on_error", False) not in (True, "true", "1", 1):
            raise ValueError(error) from None
        output.update(success=output["status"] == "accepted", error=error, duration_ms=round((time.monotonic() - started) * 1000, 2))
        return {"output": output, "success": output["success"], "error": error}

    def get_required_packages(self) -> list[str]:
        return ["email-validator==2.3.0", "httpx==0.28.1"]
