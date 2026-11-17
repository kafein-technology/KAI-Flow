"""API route configuration, independent of database and credential settings.

API_PREFIX is the complete path (default /api/v1).
ROOT_PATH describes a proxy mount independently of the API path.
"""

import os
import re
from collections.abc import Mapping
from urllib.parse import urlsplit


def normalize_path(value: str | None, *, name: str, default: str = "") -> str:
    path = (value or default).strip().strip("/")
    if not path:
        return ""
    if any(
        segment in {"", ".", ".."}
        or not re.fullmatch(r"[A-Za-z0-9._~-]+", segment)
        for segment in path.split("/")
    ):
        raise ValueError(f"{name} must contain URL path segments, not a URL, query or fragment")
    return path


def resolve_api_prefix(values: Mapping[str, str]) -> str:
    """Read the complete path without interpreting or splitting its segments."""
    path = normalize_path(values.get("API_PREFIX"), name="API_PREFIX", default="/api/v1")
    if not path:
        raise ValueError("API_PREFIX must be a non-empty URL path")
    return f"/{path}"


API_PREFIX = resolve_api_prefix(os.environ)
_root = normalize_path(os.getenv("ROOT_PATH"), name="ROOT_PATH")
ROOT_PATH = f"/{_root}" if _root else ""


def public_api_url(base_url: str, endpoint: str) -> str:
    """Build a published API URL, retaining an explicitly configured mount path.

    WEBHOOK_BASE_URL can be an origin or an origin with its public mount path.
    For an origin-only value, use ROOT_PATH when this app is mounted by a proxy.
    """
    base = base_url.rstrip("/")
    if not urlsplit(base).path.strip("/"):
        base += ROOT_PATH
    return f"{base}{API_PREFIX}/{endpoint.lstrip('/')}"
