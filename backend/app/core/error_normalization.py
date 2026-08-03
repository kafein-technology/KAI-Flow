"""Normalize third-party execution errors into stable KAI-Flow error details."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable


_STATUS_PATTERN = re.compile(
    r"(?:error\s+code|status(?:\s+code)?|http)\s*[:=]?\s*(\d{3})",
    re.IGNORECASE,
)
_MESSAGE_PATTERN = re.compile(
    r"[\"'](?:message|detail|error_description)[\"']\s*:\s*[\"']([^\"']+)",
    re.IGNORECASE,
)
_SECRET_PATTERNS = (
    (
        re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)((?:api[_ -]?key|access[_ -]?token|secret|password)"
            r"\s*[:=]\s*)[^\s,;}]+"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
        "[REDACTED_API_KEY]",
    ),
)


@dataclass(frozen=True)
class ExecutionErrorDetails:
    """A stable public error identity plus preserved diagnostic context."""

    code: str
    category: str
    title: str
    description: str
    resolution: str
    raw_message: str
    exception_type: str
    status_code: int | None = None
    provider_code: str | None = None
    provider_message: str | None = None
    retryable: bool = False

    @property
    def display_message(self) -> str:
        status = f" (HTTP {self.status_code})" if self.status_code else ""
        message = f"[{self.code}] {self.title}{status}: {self.description}"
        if self.provider_message and self.provider_message not in message:
            message += f" Provider detail: {self.provider_message}"
        if self.resolution:
            message += f" Action: {self.resolution}"
        return message

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sanitize_error_text(value: Any, *, limit: int = 2000) -> str:
    """Remove common secret forms while retaining useful provider diagnostics."""
    text = str(value or "").strip()
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    if len(text) > limit:
        return f"{text[:limit]}..."
    return text


def _iter_error_chain(error: BaseException) -> Iterable[BaseException]:
    pending = [error]
    visited: set[int] = set()

    while pending:
        current = pending.pop(0)
        if id(current) in visited:
            continue
        visited.add(id(current))
        yield current

        for nested in (
            getattr(current, "original_error", None),
            getattr(current, "__cause__", None),
            getattr(current, "__context__", None),
        ):
            if isinstance(nested, BaseException) and id(nested) not in visited:
                pending.append(nested)


def _coerce_status(value: Any) -> int | None:
    try:
        status = int(value)
    except (TypeError, ValueError):
        return None
    return status if 100 <= status <= 599 else None


def _extract_status(chain: list[BaseException]) -> int | None:
    for error in chain:
        for value in (
            getattr(error, "status_code", None),
            getattr(error, "http_status", None),
            getattr(error, "status", None),
            getattr(getattr(error, "response", None), "status_code", None),
        ):
            status = _coerce_status(value)
            if status is not None:
                return status

        match = _STATUS_PATTERN.search(str(error))
        if match:
            return int(match.group(1))
    return None


def _extract_from_payload(payload: Any, keys: tuple[str, ...], depth: int = 0) -> Any:
    if depth > 4:
        return None

    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value not in (None, "", [], {}):
                if isinstance(value, (str, int, float)):
                    return value
                nested = _extract_from_payload(value, keys, depth + 1)
                if nested is not None:
                    return nested

        for value in payload.values():
            nested = _extract_from_payload(value, keys, depth + 1)
            if nested is not None:
                return nested

    if isinstance(payload, (list, tuple)):
        for value in payload:
            nested = _extract_from_payload(value, keys, depth + 1)
            if nested is not None:
                return nested

    return None


def _payloads(chain: list[BaseException]) -> Iterable[Any]:
    for error in chain:
        for attribute in ("body", "error", "details"):
            payload = getattr(error, attribute, None)
            if payload is not None:
                yield payload
        for argument in getattr(error, "args", ()):
            if isinstance(argument, (dict, list, tuple)):
                yield argument


def _extract_provider_detail(
    chain: list[BaseException],
) -> tuple[str | None, str | None]:
    payloads = list(_payloads(chain))
    message = None
    provider_code = None

    for payload in payloads:
        if message is None:
            message = _extract_from_payload(
                payload,
                ("message", "detail", "error_description", "description"),
            )
        if provider_code is None:
            provider_code = _extract_from_payload(
                payload,
                ("code", "error_code", "type"),
            )

    if message is None:
        for error in chain:
            match = _MESSAGE_PATTERN.search(str(error))
            if match:
                message = match.group(1)
                break

    safe_message = (
        sanitize_error_text(message, limit=500) if message is not None else None
    )
    safe_code = (
        sanitize_error_text(provider_code, limit=100)
        if provider_code is not None
        else None
    )
    return safe_message, safe_code


def _classification(
    *,
    status_code: int | None,
    exception_names: str,
    searchable: str,
) -> tuple[str, str, str, str, str, bool]:
    def result(
        code: str,
        category: str,
        title: str,
        description: str,
        resolution: str,
        retryable: bool = False,
    ) -> tuple[str, str, str, str, str, bool]:
        return code, category, title, description, resolution, retryable

    if status_code == 401 or "authenticationerror" in exception_names:
        return result(
            "AUTHENTICATION_FAILED",
            "authentication",
            "Authentication failed",
            "The provider rejected the selected credential.",
            "Verify the API key, selected credential, account status, and endpoint access.",
        )
    if any(
        phrase in searchable
        for phrase in (
            "invalid api key",
            "incorrect api key",
            "api key not valid",
            "invalid x-api-key",
            "invalid authentication credentials",
            "unauthorized",
        )
    ):
        return result(
            "AUTHENTICATION_FAILED",
            "authentication",
            "Authentication failed",
            "The provider rejected the selected credential.",
            "Verify the API key, selected credential, account status, and endpoint access.",
        )
    if any(
        phrase in searchable
        for phrase in (
            "insufficient_quota",
            "quota exceeded",
            "quota has been exceeded",
            "billing hard limit",
            "credit balance",
        )
    ):
        return result(
            "QUOTA_EXCEEDED",
            "billing",
            "Provider quota exhausted",
            "The account has no remaining quota or billing capacity for this request.",
            "Check provider billing, credits, usage limits, and organization or project selection.",
        )
    if any(
        phrase in searchable
        for phrase in (
            "context_length_exceeded",
            "maximum context length",
            "too many tokens",
            "token limit exceeded",
        )
    ):
        return result(
            "CONTEXT_LENGTH_EXCEEDED",
            "input",
            "Model context limit exceeded",
            "The prompt, history, or tool output is larger than the model context window.",
            "Reduce input size, trim history, or select a model with a larger context window.",
        )
    if "content_policy" in searchable or "content policy" in searchable:
        return result(
            "CONTENT_POLICY_BLOCKED",
            "safety",
            "Provider content policy blocked the request",
            "The provider safety policy rejected the request or generated content.",
            "Review the prompt and content policy details before retrying.",
        )
    if status_code == 403 or "permissiondenied" in exception_names:
        return result(
            "ACCESS_DENIED",
            "authorization",
            "Access denied",
            "The credential is valid but does not have permission for this operation.",
            "Grant the required role or scope and confirm model or resource access.",
        )
    if status_code == 404 or "notfounderror" in exception_names:
        return result(
            "RESOURCE_NOT_FOUND",
            "configuration",
            "Provider resource not found",
            "The configured endpoint, model, deployment, or resource does not exist.",
            "Check the base URL and the configured model or deployment name.",
        )
    if status_code == 413 or "request too large" in searchable:
        return result(
            "REQUEST_TOO_LARGE",
            "input",
            "Provider request is too large",
            "The request payload exceeds the provider size limit.",
            "Reduce attached files, document content, batch size, or prompt size.",
        )
    if status_code == 429 or "ratelimit" in exception_names:
        return result(
            "RATE_LIMITED",
            "rate_limit",
            "Provider rate limit reached",
            "The provider rejected the request because its rate or quota limit was reached.",
            "Check quota and billing, reduce request frequency, or retry after a delay.",
            True,
        )
    if status_code in (408, 504) or "timeout" in exception_names or "timed out" in searchable:
        return result(
            "PROVIDER_TIMEOUT",
            "timeout",
            "Provider request timed out",
            "The provider did not complete the request within the allowed time.",
            "Check provider latency and increase timeout only if the operation normally takes longer.",
            True,
        )
    if status_code is not None and status_code >= 500:
        return result(
            "PROVIDER_UNAVAILABLE",
            "provider",
            "Provider service unavailable",
            "The provider returned a server-side failure.",
            "Retry later and check the provider status page or server logs.",
            True,
        )
    if status_code in (400, 409, 422) or any(
        name in exception_names
        for name in ("badrequest", "unprocessableentity")
    ):
        return result(
            "PROVIDER_REQUEST_INVALID",
            "request",
            "Provider rejected the request",
            "The request is incompatible with the selected provider, model, or parameters.",
            "Review model capabilities, input data, and node parameters.",
        )
    if any(
        phrase in searchable
        for phrase in (
            "no api key",
            "missing api key",
            "credential could not be found",
            "credential has no",
            "selected credential",
        )
    ):
        return result(
            "CREDENTIAL_CONFIGURATION_ERROR",
            "configuration",
            "Credential configuration is incomplete",
            "The node cannot resolve a usable credential from its configuration.",
            "Select an existing credential and make sure all required fields are populated.",
        )
    if any(
        name in exception_names
        for name in ("apiconnectionerror", "connectionerror", "connecterror")
    ) or any(
        phrase in searchable
        for phrase in ("connection refused", "name resolution", "dns", "ssl")
    ):
        return result(
            "PROVIDER_CONNECTION_FAILED",
            "connection",
            "Provider connection failed",
            "KAI-Flow could not establish a valid connection to the provider.",
            "Check the base URL, DNS, proxy, TLS certificate, and network reachability.",
            True,
        )
    if "jsondecodeerror" in exception_names:
        return result(
            "INVALID_DATA_FORMAT",
            "data",
            "Invalid data format",
            "The node received data that could not be parsed as the expected format.",
            "Inspect the node input and the upstream output schema.",
        )
    if "typeerror" in exception_names:
        return result(
            "INVALID_NODE_INPUT",
            "input",
            "Invalid node input",
            "The node received an unsupported argument shape or value type.",
            "Check connected handles and the node input schema.",
        )
    if "valueerror" in exception_names:
        return result(
            "INVALID_NODE_CONFIGURATION",
            "configuration",
            "Invalid node configuration",
            "A node setting or input value failed validation.",
            "Review the node configuration and the provider detail below.",
        )

    return result(
        "NODE_EXECUTION_FAILED",
        "execution",
        "Node execution failed",
        "The node raised an execution error that has no specialized classification.",
        "Use the provider detail and exception type to inspect the failing integration.",
    )


def normalize_execution_error(error: BaseException) -> ExecutionErrorDetails:
    """Return a stable, actionable identity without discarding the original error."""
    chain = list(_iter_error_chain(error))
    raw_message = sanitize_error_text(error)
    status_code = _extract_status(chain)
    provider_message, provider_code = _extract_provider_detail(chain)
    exception_names = " ".join(type(item).__name__.lower() for item in chain)
    searchable = " ".join(str(item).lower() for item in chain)

    code, category, title, description, resolution, retryable = _classification(
        status_code=status_code,
        exception_names=exception_names,
        searchable=searchable,
    )

    if code == "NODE_EXECUTION_FAILED" and raw_message:
        description = raw_message
        if provider_message == raw_message:
            provider_message = None

    return ExecutionErrorDetails(
        code=code,
        category=category,
        title=title,
        description=description,
        resolution=resolution,
        raw_message=raw_message,
        exception_type=type(error).__name__,
        status_code=status_code,
        provider_code=provider_code,
        provider_message=provider_message,
        retryable=retryable,
    )
