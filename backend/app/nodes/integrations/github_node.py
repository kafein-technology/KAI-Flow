"""GitHub API actions using the existing saved-credential infrastructure."""

import json
import os
import re
from urllib.parse import parse_qs, quote, urlsplit

import httpx

from ..base import BaseNode, NodeInput, NodeOutput, NodeProperty, NodePropertyType, NodeType


class GitHubError(ValueError):
    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _credential_secret(credential):
    if not credential or credential.get("service_type") not in ("github", "header_auth"):
        raise GitHubError("Select a valid GitHub or Header Auth credential.")
    secret = credential.get("secret") or {}
    if not isinstance(secret, dict):
        raise GitHubError("The selected credential must contain an access token.")
    if credential.get("service_type") == "header_auth":
        if str(secret.get("header_name") or "").lower() != "authorization":
            raise GitHubError("Use Authorization as the credential header name.")
        token = secret.get("header_value")
        if isinstance(token, str) and token.lower().startswith("bearer "):
            token = token[7:]
        return {"access_token": token}
    return secret


def _api_base_url(server_url=""):
    default = "https://api.github.com"
    if not server_url:
        return default
    try:
        parsed = urlsplit(str(server_url))
        port = parsed.port
    except ValueError:
        raise GitHubError("Invalid GitHub server URL.") from None
    allowed = {host.strip().lower() for host in os.getenv("GIT_PROVIDER_ALLOWED_HOSTS", "").split(",") if host.strip()}
    public = {"github.com", "api.github.com"}
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or port not in (None, 443)
            or parsed.hostname.lower() not in allowed | public):
        raise GitHubError("Use HTTPS and an administrator-approved GitHub server host.")
    path = parsed.path.rstrip("/")
    if parsed.hostname.lower() in public:
        if path:
            raise GitHubError("Use the GitHub server root URL.")
        return default
    if path not in ("", "/api/v3"):
        raise GitHubError("Use the server root or its API root URL.")
    return f"https://{parsed.hostname.lower()}/api/v3"


def _repository_path(repository):
    value = str(repository or "").strip()
    parts = value.split("/")
    if (len(parts) != 2 or any(part in ("", ".", "..") for part in parts)
            or not re.fullmatch(r"[\w.-]+/[\w.-]+", value, re.ASCII)):
        raise GitHubError("Enter the repository as owner/repository.")
    return "/repos/" + "/".join(quote(part, safe="") for part in parts)


def _bounded_int(value, default, minimum, maximum, label):
    try:
        result = int(default if value in (None, "") else value)
    except (TypeError, ValueError):
        raise GitHubError(f"{label} must be a whole number.") from None
    if isinstance(value, bool) or str(result) != str(value if value not in (None, "") else default):
        raise GitHubError(f"{label} must be a whole number.")
    if not minimum <= result <= maximum:
        raise GitHubError(f"{label} must be between {minimum} and {maximum}.")
    return result


class GitHubClient:
    def __init__(self, secret, timeout=30):
        self.base_url = _api_base_url(secret.get("server_url", ""))
        token = secret.get("access_token")
        if not isinstance(token, str) or not token.strip() or any(char.isspace() for char in token):
            raise GitHubError("A valid access token is required in the selected credential.")
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}
        self.timeout = _bounded_int(timeout, 30, 5, 120, "Timeout")

    async def request(self, method, path, *, params=None, data=None):
        if not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path:
            raise GitHubError("Invalid GitHub API endpoint.")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.request(method, self.base_url + path, headers=self.headers, params=params, json=data)
        except httpx.TimeoutException:
            raise GitHubError("GitHub request timed out.") from None
        except httpx.RequestError:
            raise GitHubError("Could not connect to GitHub.") from None
        if not 200 <= response.status_code < 300:
            reasons = {401: "Check the access token.", 403: "Check token permissions or rate limits.",
                       404: "Check the repository and token access.", 422: "Check the operation fields.",
                       429: "Rate limit reached; try again later."}
            raise GitHubError(f"GitHub API returned HTTP {response.status_code}. "
                              + reasons.get(response.status_code, "The request could not be completed."),
                              status_code=response.status_code)
        if response.status_code == 204:
            return None, response.headers
        try:
            return response.json(), response.headers
        except ValueError:
            raise GitHubError("GitHub returned invalid JSON.") from None

    async def action(self, values):
        resource, _, operation = str(values.get("operation", "repository.get")).partition(".")
        allowed = {"repository": {"get"}, "commit": {"get", "list"},
                   "issue": {"get", "list", "create", "update", "comment"},
                   "pull_request": {"get", "list", "create", "update", "comment"}}
        if resource not in allowed or operation not in allowed[resource]:
            raise GitHubError("Unsupported GitHub operation.")
        root = _repository_path(values.get("repository"))
        collections = {"commit": "commits", "issue": "issues", "pull_request": "pulls"}
        path = root if resource == "repository" else root + "/" + collections[resource]
        if resource == "commit" and operation == "get":
            ref = str(values.get("commit_sha") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9_./-]+", ref) or any(part in ("", ".", "..") for part in ref.split("/")):
                raise GitHubError("A valid commit SHA or ref is required.")
            path += "/" + quote(ref, safe="")
        elif resource in ("issue", "pull_request") and operation in ("get", "update", "comment"):
            number = _bounded_int(values.get("number"), 0, 1, 2147483647, "Issue/PR number")
            if operation == "comment":
                path = root + "/issues"
            path += f"/{number}"
        if operation == "comment":
            path += "/comments"
        method = {"create": "POST", "comment": "POST", "update": "PATCH"}.get(operation, "GET")
        params, body = {}, None
        page = _bounded_int(values.get("page"), 1, 1, 1000000, "Page")
        per_page = _bounded_int(values.get("per_page"), 30, 1, 100, "Page size")
        if operation == "list":
            params.update(page=page, per_page=per_page)
            if resource in ("issue", "pull_request"):
                state = values.get("state") or "open"
                if state not in {"open", "closed", "all"}:
                    raise GitHubError("Invalid issue/PR state filter.")
                params["state"] = state
        if method != "GET":
            fields = {"title", "body", "state", "head", "base", "draft", "labels", "assignees"}
            if resource == "issue":
                fields -= {"head", "base", "draft"}
            body = {key: values[key] for key in fields if values.get(key) not in (None, "")}
            if operation == "comment":
                comment = values.get("comment") or values.get("body")
                if not isinstance(comment, str) or not comment.strip():
                    raise GitHubError("Comment text is required.")
                body = {"body": comment}
            elif operation == "create":
                required = ["title", "head", "base"] if resource == "pull_request" else ["title"]
                if any(not isinstance(body.get(key), str) or not body[key].strip() for key in required):
                    raise GitHubError("Required fields: " + ", ".join(required) + ".")
            elif not body:
                raise GitHubError("Provide at least one field to update.")
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


class GitHubNode(BaseNode):
    def __init__(self):
        super().__init__()
        operations = [("repository.get", "Get Repository")]
        for resource, label in (("commit", "Commit"), ("issue", "Issue"), ("pull_request", "Pull Request")):
            for operation in (["list", "get"] if resource == "commit" else ["list", "get", "create", "update", "comment"]):
                operations.append((f"{resource}.{operation}", f"{operation.title()} {label}"))
        properties = [
            NodeProperty(name="credential_id", displayName="Credential", type=NodePropertyType.CREDENTIAL_SELECT,
                         serviceType="header_auth", description="Create Header Auth with Authorization as the header name and your GitHub access token as the value."),
            NodeProperty(name="repository", displayName="Repository", type=NodePropertyType.TEXT, placeholder="owner/repository"),
            NodeProperty(name="operation", displayName="Operation", type=NodePropertyType.SELECT, default="repository.get",
                         options=[{"value": value, "label": label} for value, label in operations]),
        ]
        for field, label, kind in [("number", "Issue / PR Number", NodePropertyType.NUMBER),
                                   ("commit_sha", "Commit SHA / Ref", NodePropertyType.TEXT),
                                   ("title", "Title", NodePropertyType.TEXT),
                                   ("body", "Description", NodePropertyType.TEXT_AREA),
                                   ("comment", "Comment", NodePropertyType.TEXT_AREA),
                                   ("head", "Source Branch", NodePropertyType.TEXT),
                                   ("base", "Target Branch", NodePropertyType.TEXT),
                                   ("state", "State Filter / State", NodePropertyType.TEXT)]:
            properties.append(NodeProperty(name=field, displayName=label, type=kind, required=False))
        properties += [
            NodeProperty(name="additional_fields", displayName="Additional Fields (JSON)", type=NodePropertyType.JSON_EDITOR,
                         required=False, default="{}", description="Operation fields such as labels, assignees or draft. Connected JSON input can also supply operation fields."),
            NodeProperty(name="page", displayName="Page", type=NodePropertyType.NUMBER, default=1, min=1, required=False),
            NodeProperty(name="per_page", displayName="Results per Page", type=NodePropertyType.NUMBER, default=30, min=1, max=100, required=False),
            NodeProperty(name="timeout", displayName="Timeout (seconds)", type=NodePropertyType.NUMBER, default=30, min=5, max=120, required=False),
        ]
        self._metadata = dict(name="GitHub", display_name="GitHub", description="Read repositories and commits; manage issues and pull requests with a saved credential.",
                              category="Integrations", node_type=NodeType.PROCESSOR,
                              icon={"name": "GitBranch", "alt": "GitHub"}, colors=["slate-400", "orange-500"],
                              inputs=[NodeInput(name="input", type="any", description="Connected JSON operation fields", required=False, is_connection=True)],
                              outputs=[NodeOutput(name="output", type="json", description="GitHub API result and pagination", is_connection=True)], properties=properties)

    async def execute(self, inputs, connected_nodes=None, **kwargs):
        secret = _credential_secret(self.get_credential(inputs.get("credential_id")))
        extra = inputs.get("additional_fields") or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                raise GitHubError("Additional fields must be a JSON object.") from None
        if not isinstance(extra, dict):
            raise GitHubError("Additional fields must be a JSON object.")
        connected = (connected_nodes or {}).get("input", inputs.get("input", {}))
        if isinstance(connected, dict) and isinstance(connected.get("output"), dict):
            connected = connected["output"]
        values = {**(connected if isinstance(connected, dict) else {}), **extra,
                  **{key: value for key, value in inputs.items() if value not in (None, "")}}
        client = GitHubClient(secret, inputs.get("timeout", 30))
        return {"output": await client.action(values)}
