"""Credential-scoped Google OAuth helpers used by Google API nodes.

KAI-Flow stores the OAuth client id, client secret, and refresh token in the
encrypted user credential. Nothing in this module depends on deployment
environment variables, so an exported workflow can be installed in any
environment and connected with a credential created there.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

TOKEN_URI = "https://oauth2.googleapis.com/token"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

logger = logging.getLogger(__name__)


class GoogleOAuthError(Exception):
    """Raised when an encrypted Google OAuth credential cannot be used."""


def _required_text(secret: Mapping[str, Any], key: str, label: str) -> str:
    value = str(secret.get(key) or "").strip()
    if not value:
        raise GoogleOAuthError(f"Gmail credential is missing {label}.")
    return value


def gmail_credentials(secret: Mapping[str, Any]) -> Credentials:
    """Build Google credentials from one saved Gmail credential."""
    if not isinstance(secret, Mapping):
        raise GoogleOAuthError("The Gmail credential could not be read.")

    client_id = _required_text(secret, "client_id", "OAuth Client ID")
    client_secret = _required_text(secret, "client_secret", "OAuth Client Secret")
    refresh_token = _required_text(secret, "refresh_token", "Refresh Token")

    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=GMAIL_SCOPES,
    )


def _refresh_error_code(exc: RefreshError) -> str:
    """Extract only Google's non-sensitive OAuth error identifier."""
    known_codes = (
        "invalid_client",
        "invalid_grant",
        "invalid_scope",
        "unauthorized_client",
        "access_denied",
        "invalid_request",
        "deleted_client",
    )
    for argument in exc.args:
        if isinstance(argument, Mapping):
            code = str(argument.get("error") or "").strip().lower()
            if code in known_codes:
                return code
        text = str(argument).lower()
        for code in known_codes:
            if code in text:
                return code
    return ""


def access_token_for(secret: Mapping[str, Any]) -> str:
    """Exchange the credential's refresh token for a short-lived access token."""
    credentials = gmail_credentials(secret)
    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        code = _refresh_error_code(exc)
        logger.warning("Gmail OAuth token refresh rejected (error=%s)", code or "unknown")
        if code in {"invalid_client", "deleted_client"}:
            raise GoogleOAuthError(
                "Google rejected the OAuth Client ID or Client Secret."
            ) from exc
        if code == "invalid_grant":
            raise GoogleOAuthError(
                "Google rejected the Refresh Token. It may be expired, revoked, or issued "
                "for a different OAuth client."
            ) from exc
        if code == "invalid_scope":
            raise GoogleOAuthError(
                "The Refresh Token was not authorized for the Gmail modify scope. Create a "
                "new token with https://www.googleapis.com/auth/gmail.modify."
            ) from exc
        if code == "unauthorized_client":
            raise GoogleOAuthError(
                "This OAuth client is not allowed to refresh Gmail tokens. Verify that the "
                "token was created with the same Web application Client ID and Secret."
            ) from exc
        if code == "access_denied":
            raise GoogleOAuthError(
                "Google denied Gmail access. Verify the OAuth consent screen, test user, "
                "and Workspace administrator policy."
            ) from exc
        if code == "invalid_request":
            raise GoogleOAuthError(
                "Google considered the token refresh request incomplete. Re-enter the OAuth "
                "Client ID, Client Secret, and Refresh Token."
            ) from exc
        raise GoogleOAuthError(
            "Google could not refresh the Gmail access token. Verify the credential and "
            f"the Gmail API configuration (OAuth error: {code or 'unknown'})."
        ) from exc
    except Exception as exc:
        raise GoogleOAuthError(
            "Google authentication could not be reached. Check the network and credential."
        ) from exc

    token = str(credentials.token or "").strip()
    if not token:
        raise GoogleOAuthError("Google returned an empty Gmail access token.")
    return token


__all__ = [
    "GMAIL_SCOPES",
    "GoogleOAuthError",
    "access_token_for",
    "gmail_credentials",
]
