"""Endpoint handling and connection checks for decision API credentials."""

from __future__ import annotations

import math
from typing import Any, Dict
from urllib.parse import urlsplit, urlunsplit

import httpx


ENDPOINT_PATHS = {
    "systemone": "/v1/systemone",
    "decisions": "/api/alpha/decisions",
}


def selected_endpoint_path(secret: Dict[str, Any]) -> str:
    # Credentials saved before custom endpoints existed retain their protocol.
    selection = secret.get("endpoint_type")
    selection = "/v1/systemone" if selection is None else str(selection)
    if selection in ("", "custom"):
        return ""
    path = ENDPOINT_PATHS.get(selection, selection)
    if path not in ENDPOINT_PATHS.values():
        raise ValueError("Select a supported decision endpoint path.")
    return path


def decision_endpoint(secret: Dict[str, Any]) -> str:
    endpoint_path = selected_endpoint_path(secret)
    base_url = str(secret.get("base_url") or "").strip()
    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password or parts.fragment:
        raise ValueError("Base URL must be an HTTP or HTTPS URL without credentials or a fragment.")
    if not endpoint_path:
        return base_url
    if parts.query:
        raise ValueError("Base URL must not contain a query when a preset endpoint is selected.")
    base_segments = [segment for segment in parts.path.split("/") if segment]
    target_segments = endpoint_path.strip("/").split("/")
    overlap = 0
    for size in range(1, min(len(base_segments), len(target_segments)) + 1):
        if base_segments[-size:] == target_segments[:size]:
            overlap = size
    path = "/" + "/".join(base_segments + target_segments[overlap:])
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def decision_models_endpoint(secret: Dict[str, Any]) -> str | None:
    """Use model discovery only for known protocols; never guess a custom URL."""
    endpoint = urlsplit(decision_endpoint(secret))
    decision_path = selected_endpoint_path(secret)
    if not decision_path:
        return None
    prefix = endpoint.path[: -len(decision_path)].rstrip("/")
    models_path = "/v1/models" if decision_path == "/v1/systemone" else "/api/v1/models"
    return urlunsplit((endpoint.scheme, endpoint.netloc, prefix + models_path, "", ""))


async def test_decision_connection(secret: Dict[str, Any]) -> None:
    """Verify the configured endpoint and model with one small decision request."""
    endpoint = decision_endpoint(secret)
    model = str(secret.get("model_name") or "").strip()
    if not model:
        raise ValueError("Enter a model to test the Decision Model connection.")
    headers = {"Accept": "application/json"}
    api_key = str(secret.get("api_key") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=4.0)) as client:
        response = await client.post(endpoint, headers=headers, json={
            "model": model,
            "state": "This is a connection test.",
            "questions": {
                "connection_test": {"type": "noul", "instructions": "Is this a connection test?"},
            },
        })
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError:
            raise ValueError("Decision endpoint returned invalid JSON.") from None
    answers = payload.get("answers") if isinstance(payload, dict) else None
    answer = answers.get("connection_test") if isinstance(answers, dict) else None
    probability = answer.get("noul") if isinstance(answer, dict) else None
    if (
        not isinstance(answer, dict) or answer.get("type") != "noul"
        or isinstance(probability, bool) or not isinstance(probability, (int, float))
        or not math.isfinite(probability) or not 0 <= probability <= 1
    ):
        raise ValueError("Decision endpoint did not return a valid connection-test answer.")
