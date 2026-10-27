"""Token-authenticated GitHub API shared by the action and agent tool nodes."""

import os
import re
from urllib.parse import parse_qs, quote, urlsplit

import httpx


class GitProviderError(ValueError):
    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def api_base_url(provider, server_url=""):
    if provider != "github":
        raise GitProviderError("Unsupported Git provider.")
    default = "https://api.github.com"
    if not server_url:
        return default
    try:
        parsed = urlsplit(str(server_url))
        port = parsed.port
    except ValueError:
        raise GitProviderError("Invalid GitHub server URL.") from None
    allowed = {host.strip().lower() for host in os.getenv("GIT_PROVIDER_ALLOWED_HOSTS", "").split(",") if host.strip()}
    public = {"github.com", "api.github.com"}
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or port not in (None, 443)
            or parsed.hostname.lower() not in allowed | public):
        raise GitProviderError("Use HTTPS and an administrator-approved GitHub server host.")
    path = parsed.path.rstrip("/")
    if parsed.hostname.lower() in public:
        if path:
            raise GitProviderError("Use the GitHub server root URL.")
        return default
    if path not in ("", "/api/v3"):
        raise GitProviderError("Use the server root or its API root URL.")
    return f"https://{parsed.hostname.lower()}/api/v3"


def repository_path(provider, repository):
    if provider != "github":
        raise GitProviderError("Unsupported Git provider.")
    value = str(repository or "").strip()
    parts = value.split("/")
    if (len(parts) != 2 or any(part in ("", ".", "..") for part in parts)
            or not re.fullmatch(r"[\w.-]+/[\w.-]+", value, re.ASCII)):
        raise GitProviderError("Enter the repository as owner/repository.")
    return "/repos/" + "/".join(quote(part, safe="") for part in parts)


def bounded_int(value, default, minimum, maximum, label):
    try:
        result = int(default if value in (None, "") else value)
    except (TypeError, ValueError):
        raise GitProviderError(f"{label} must be a whole number.") from None
    if isinstance(value, bool) or str(result) != str(value if value not in (None, "") else default):
        raise GitProviderError(f"{label} must be a whole number.")
    if not minimum <= result <= maximum:
        raise GitProviderError(f"{label} must be between {minimum} and {maximum}.")
    return result


class GitProviderClient:
    def __init__(self, provider, secret, timeout=30):
        self.provider = provider
        self.base_url = api_base_url(provider, secret.get("server_url", ""))
        token = secret.get("access_token")
        if not isinstance(token, str) or not token.strip() or any(char.isspace() for char in token):
            raise GitProviderError("A valid access token is required in the selected credential.")
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}
        self.timeout = bounded_int(timeout, 30, 5, 120, "Timeout")

    async def request(self, method, path, *, params=None, data=None):
        if not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path:
            raise GitProviderError("Invalid GitHub API endpoint.")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.request(method, self.base_url + path, headers=self.headers, params=params, json=data)
        except httpx.TimeoutException:
            raise GitProviderError("GitHub request timed out.") from None
        except httpx.RequestError:
            raise GitProviderError("Could not connect to GitHub.") from None
        if not 200 <= response.status_code < 300:
            reasons = {401: "Check the access token.", 403: "Check token permissions or rate limits.",
                       404: "Check the repository and token access.", 422: "Check the operation fields.",
                       429: "Rate limit reached; try again later."}
            raise GitProviderError(f"GitHub API returned HTTP {response.status_code}. "
                              + reasons.get(response.status_code, "The request could not be completed."),
                              status_code=response.status_code)
        if response.status_code == 204:
            return None, response.headers
        try:
            return response.json(), response.headers
        except ValueError:
            raise GitProviderError("GitHub returned invalid JSON.") from None

    async def test_connection(self):
        data, _ = await self.request("GET", "/user")
        return data

    async def action(self, values):
        resource, _, operation = str(values.get("operation", "repository.get")).partition(".")
        allowed = {"repository": {"get"}, "commit": {"get", "list"},
                   "issue": {"get", "list", "create", "update", "comment"},
                   "pull_request": {"get", "list", "create", "update", "comment"}}
        if resource not in allowed or operation not in allowed[resource]:
            raise GitProviderError("Unsupported GitHub operation.")
        root = repository_path(self.provider, values.get("repository"))
        collections = {"commit": "commits", "issue": "issues", "pull_request": "pulls"}
        path = root if resource == "repository" else root + "/" + collections[resource]
        if resource == "commit" and operation == "get":
            ref = str(values.get("commit_sha") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9_./-]+", ref) or any(part in ("", ".", "..") for part in ref.split("/")):
                raise GitProviderError("A valid commit SHA or ref is required.")
            path += "/" + quote(ref, safe="")
        elif resource in ("issue", "pull_request") and operation in ("get", "update", "comment"):
            number = bounded_int(values.get("number"), 0, 1, 2147483647, "Issue/PR number")
            if operation == "comment":
                path = root + "/issues"
            path += f"/{number}"
        if operation == "comment":
            path += "/comments"
        method = {"create": "POST", "comment": "POST", "update": "PATCH"}.get(operation, "GET")
        params, body = {}, None
        page = bounded_int(values.get("page"), 1, 1, 1000000, "Page")
        per_page = bounded_int(values.get("per_page"), 30, 1, 100, "Page size")
        if operation == "list":
            params.update(page=page, per_page=per_page)
            if resource in ("issue", "pull_request"):
                state = values.get("state") or "open"
                if state not in {"open", "closed", "all"}:
                    raise GitProviderError("Invalid issue/PR state filter.")
                params["state"] = state
        if method != "GET":
            fields = {"title", "body", "state", "head", "base", "draft", "labels", "assignees"}
            if resource == "issue":
                fields -= {"head", "base", "draft"}
            body = {key: values[key] for key in fields if values.get(key) not in (None, "")}
            if operation == "comment":
                comment = values.get("comment") or values.get("body")
                if not isinstance(comment, str) or not comment.strip():
                    raise GitProviderError("Comment text is required.")
                body = {"body": comment}
            elif operation == "create":
                required = ["title", "head", "base"] if resource == "pull_request" else ["title"]
                if any(not isinstance(body.get(key), str) or not body[key].strip() for key in required):
                    raise GitProviderError("Required fields: " + ", ".join(required) + ".")
            elif not body:
                raise GitProviderError("Provide at least one field to update.")
        data, headers = await self.request(method, path, params=params or None, data=body)
        # GitHub's issues endpoint also returns PRs; keep the Issue resource precise.
        if resource == "issue" and operation == "list" and isinstance(data, list):
            data = [item for item in data if "pull_request" not in item]
        result = {"success": True, "provider": "github", "operation": f"{resource}.{operation}", "data": data}
        if operation == "list":
            next_page = None
            if headers.get("x-next-page", "").isdigit():
                next_page = int(headers["x-next-page"])
            else:
                for link in headers.get("link", "").split(","):
                    if 'rel="next"' in link:
                        candidate = parse_qs(urlsplit(link.split(";")[0].strip(" <> ")).query).get("page", [""])[0]
                        if candidate.isdigit():
                            next_page = int(candidate)
            result.update(page=page, per_page=per_page, next_page=next_page, has_next_page=next_page is not None)
            if headers.get("x-total", "").isdigit():
                result["total_count"] = int(headers["x-total"])
        return result
